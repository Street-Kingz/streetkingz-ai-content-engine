import os
import cv2
import csv
import json
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v")
SECTION_LENGTH_SECONDS = 2
MAX_SECTIONS_TO_ANALYSE = 12
OUTPUT_FILE = "clip_section_analysis.csv"


def clean_path(path):
    return path.strip().strip("'").strip('"').replace("\\ ", " ")


def get_video_info(video_path):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return None

    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.release()

    if fps <= 0:
        return None

    duration = frame_count / fps

    return {
        "frame_count": frame_count,
        "fps": fps,
        "duration": duration,
    }


def extract_frame_at_time(video_path, timestamp_seconds):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(timestamp_seconds * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    success, frame = cap.read()

    cap.release()

    if not success:
        return None

    success_encode, buffer = cv2.imencode(".jpg", frame)

    if not success_encode:
        return None

    return {
        "type": "input_image",
        "image_url": f"data:image/jpeg;base64,{base64.b64encode(buffer).decode()}"
    }


def build_sections(duration):
    sections = []

    start = 0.0

    while start < duration:
        end = min(start + SECTION_LENGTH_SECONDS, duration)
        midpoint = start + ((end - start) / 2)

        sections.append({
            "start": round(start, 1),
            "end": round(end, 1),
            "midpoint": round(midpoint, 1),
        })

        start += SECTION_LENGTH_SECONDS

    return sections[:MAX_SECTIONS_TO_ANALYSE]


def analyse_sections(video_path, sections):
    content = []

    section_labels = []

    for index, section in enumerate(sections, start=1):
        frame = extract_frame_at_time(video_path, section["midpoint"])

        if frame:
            section_labels.append(
                f"Section {index}: {section['start']}s to {section['end']}s"
            )

            content.append({
                "type": "input_text",
                "text": f"Section {index}: {section['start']}s to {section['end']}s"
            })

            content.append(frame)

    if not content:
        raise ValueError("No frames could be extracted for section analysis.")

    prompt = """
You are analysing short sections of a Street Kingz car detailing clip.

Goal:
Identify the best timestamp sections to use in TikTok edits.

For EACH section, score:

- visual_interest_score: how visually useful/satisfying the shot is
- product_visibility_score: how clearly the product/tool is visible
- demo_quality_score: how clearly it shows useful action
- hook_score: how good this section is as the first 1-2 seconds
- reveal_score: how good it is as a result/reveal moment

Scores must be numbers from 1 to 10.

Also provide:
- action_summary under 6 words
- best_use: hook, demo, reveal, broll, avoid
- reason under 12 words

Important:
- Do not score everything the same.
- If the section looks boring, rate it low.
- If the section is visually unclear, rate it low.
- Prefer sections with clear action, visible product, dirt removal, foam movement, water movement, or clean reveal.

Return ONLY valid JSON in this exact structure:

{
  "sections": [
    {
      "section_number": 1,
      "visual_interest_score": "",
      "product_visibility_score": "",
      "demo_quality_score": "",
      "hook_score": "",
      "reveal_score": "",
      "action_summary": "",
      "best_use": "",
      "reason": ""
    }
  ]
}
"""

    content.insert(0, {"type": "input_text", "text": prompt})

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": content
            }
        ]
    )

    return json.loads(response.output_text)


def analyse_video(video_path):
    info = get_video_info(video_path)

    if not info:
        raise ValueError(f"Could not read video: {video_path}")

    sections = build_sections(info["duration"])
    result = analyse_sections(video_path, sections)

    rows = []

    for item in result.get("sections", []):
        section_number = int(item.get("section_number", 0))

        if section_number < 1 or section_number > len(sections):
            continue

        section = sections[section_number - 1]

        rows.append({
            "filename": os.path.basename(video_path),
            "start": section["start"],
            "end": section["end"],
            "duration": round(info["duration"], 1),
            "visual_interest_score": item.get("visual_interest_score", ""),
            "product_visibility_score": item.get("product_visibility_score", ""),
            "demo_quality_score": item.get("demo_quality_score", ""),
            "hook_score": item.get("hook_score", ""),
            "reveal_score": item.get("reveal_score", ""),
            "action_summary": item.get("action_summary", ""),
            "best_use": item.get("best_use", ""),
            "reason": item.get("reason", ""),
        })

    return rows


def main():
    path = clean_path(input("Enter video or folder path: "))
    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(f"Path not found: {input_path}")

    if input_path.is_file():
        videos = [input_path]
    else:
        videos = [
            file for file in sorted(input_path.iterdir())
            if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
        ]

    if not videos:
        print("No video files found.")
        return

    fields = [
        "filename",
        "start",
        "end",
        "duration",
        "visual_interest_score",
        "product_visibility_score",
        "demo_quality_score",
        "hook_score",
        "reveal_score",
        "action_summary",
        "best_use",
        "reason",
    ]

    print(f"Found {len(videos)} video(s).")
    print(f"Writing to {OUTPUT_FILE}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()

        for index, video in enumerate(videos, start=1):
            print(f"[{index}/{len(videos)}] Analysing {video.name}")

            try:
                rows = analyse_video(video)

                for row in rows:
                    writer.writerow(row)

                csvfile.flush()
                print("Done")

            except Exception as e:
                writer.writerow({
                    "filename": video.name,
                    "start": "",
                    "end": "",
                    "duration": "",
                    "visual_interest_score": "",
                    "product_visibility_score": "",
                    "demo_quality_score": "",
                    "hook_score": "",
                    "reveal_score": "",
                    "action_summary": f"ERROR: {e}",
                    "best_use": "",
                    "reason": "",
                })
                csvfile.flush()
                print(f"ERROR: {e}")

    print(f"Finished. CSV created: {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()