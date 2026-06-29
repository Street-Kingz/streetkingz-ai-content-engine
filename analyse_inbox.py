import os
import cv2
import csv
import json
import base64
import shutil
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

INBOX_FOLDER = Path("Inbox")
QUARANTINE_FOLDER = Path("Quarantine")
MASTER_BROLL_FOLDER = Path("/Users/ben/Desktop/B Roll")
MASTER_DATABASE = Path("street_kingz_master_clip_database.csv")

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v", ".MOV", ".MP4", ".M4V")
MIN_DURATION_SECONDS = 3

FIELDS = [
    "original_filename",
    "folder",
    "relative_folder",
    "suggested_filename",
    "product",
    "category",
    "story_role",
    "simple_description",
    "primary_action",
    "shot_type",
    "hook_score",
    "demo_score",
    "reveal_score",
    "broll_score",
    "visual_interest_score",
    "best_use",
    "tags",
]

CATEGORY_TO_FOLDER = {
    "drying": "Drying Inbox",
    "wheels": "Wheels Inbox",
    "foam": "Foam Inbox",
    "interior": "Interior Inbox",
    "glass": "Glass Inbox",
    "product": "Product Showcase",
    "general": "General Inbox",
}


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


def extract_frames(video_path, frame_samples=5):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return []

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if frame_count <= 0:
        cap.release()
        return []

    positions = [
        int(frame_count * 0.1),
        int(frame_count * 0.3),
        int(frame_count * 0.5),
        int(frame_count * 0.7),
        int(frame_count * 0.9),
    ]

    images = []

    for pos in positions[:frame_samples]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        success, frame = cap.read()

        if success:
            success_encode, buffer = cv2.imencode(".jpg", frame)

            if success_encode:
                images.append({
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{base64.b64encode(buffer).decode()}"
                })

    cap.release()
    return images


def safe_move(source, destination_folder):
    destination_folder.mkdir(parents=True, exist_ok=True)

    destination = destination_folder / source.name

    if destination.exists():
        stem = source.stem
        suffix = source.suffix
        counter = 1

        while destination.exists():
            destination = destination_folder / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.move(str(source), str(destination))
    return destination


def quarantine(video_path, reason):
    destination = safe_move(video_path, QUARANTINE_FOLDER)

    return {
        "status": "quarantined",
        "original": video_path.name,
        "destination": str(destination),
        "reason": reason,
    }


def analyse_video(video_path):
    info = get_video_info(video_path)

    if not info:
        return None, "Unreadable video"

    if info["duration"] < MIN_DURATION_SECONDS:
        return None, f"Too short: {info['duration']:.1f}s"

    images = extract_frames(video_path)

    if not images:
        return None, "No readable frames extracted"

    prompt = """
You are analysing a Street Kingz car detailing B-roll clip.

Street Kingz sells simple car detailing products to everyday car owners.
The content system uses clips to build TikTok videos.

Classify the clip accurately.

Rules:
- Do not invent products.
- If product is unclear, use "unclear".
- If category is unclear, use "unclear".
- If the clip looks accidental, unusable, mostly floor, mostly sky, mostly black, badly blurred, or not car detailing content, set usable to false.
- Be strict. Low-quality clips should not be filed into the main library.
- category must be one of: drying, wheels, foam, interior, glass, product, general, unclear
- story_role must be one of: problem, solution, result, product_showcase, broll, unclear
- shot_type must be one of: hook, demo, reveal, broll, product_shot, unclear
- suggested_filename should be lowercase, hyphen-separated, and end in .mov
- simple_description under 8 words
- primary_action under 5 words
- scores are numbers from 1 to 10
- confidence must be a number from 1 to 10

Return ONLY valid JSON:

{
  "usable": true,
  "confidence": 8,
  "suggested_filename": "",
  "product": "",
  "category": "",
  "story_role": "",
  "simple_description": "",
  "primary_action": "",
  "shot_type": "",
  "hook_score": "",
  "demo_score": "",
  "reveal_score": "",
  "broll_score": "",
  "visual_interest_score": "",
  "best_use": "",
  "tags": ""
}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    *images
                ]
            }
        ]
    )

    try:
        result = json.loads(response.output_text)
    except json.JSONDecodeError:
        return None, "AI returned invalid JSON"

    return result, None


def append_to_database(row):
    file_exists = MASTER_DATABASE.exists()

    with open(MASTER_DATABASE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def process_video(video_path):
    result, error = analyse_video(video_path)

    if error:
        return quarantine(video_path, error)

    usable = result.get("usable", False)
    confidence = int(result.get("confidence", 0) or 0)
    category = (result.get("category", "") or "").strip().lower()
    story_role = (result.get("story_role", "") or "").strip().lower()

    if not usable:
        return quarantine(video_path, "AI marked unusable")

    if confidence < 7:
        return quarantine(video_path, f"Low confidence: {confidence}/10")

    if category == "unclear" or story_role == "unclear":
        return quarantine(video_path, "Unclear category or story role")

    if category == "general":
        return quarantine(
            video_path,
            f"General category requires manual review: {confidence}/10"
        )

    folder_name = CATEGORY_TO_FOLDER.get(category, "General Inbox")
    destination_folder = MASTER_BROLL_FOLDER / folder_name
    moved_path = safe_move(video_path, destination_folder)

    row = {
        "original_filename": moved_path.name,
        "folder": folder_name,
        "relative_folder": folder_name,
        "suggested_filename": result.get("suggested_filename", ""),
        "product": result.get("product", ""),
        "category": category,
        "story_role": story_role,
        "simple_description": result.get("simple_description", ""),
        "primary_action": result.get("primary_action", ""),
        "shot_type": result.get("shot_type", ""),
        "hook_score": result.get("hook_score", ""),
        "demo_score": result.get("demo_score", ""),
        "reveal_score": result.get("reveal_score", ""),
        "broll_score": result.get("broll_score", ""),
        "visual_interest_score": result.get("visual_interest_score", ""),
        "best_use": result.get("best_use", ""),
        "tags": result.get("tags", ""),
    }

    append_to_database(row)

    return {
        "status": "filed",
        "original": video_path.name,
        "destination": str(moved_path),
        "category": category,
        "story_role": story_role,
        "confidence": confidence,
    }


def run_inbox_analysis():
    INBOX_FOLDER.mkdir(exist_ok=True)
    QUARANTINE_FOLDER.mkdir(exist_ok=True)

    videos = [
        file for file in sorted(INBOX_FOLDER.iterdir())
        if file.exists() and file.is_file() and file.suffix in VIDEO_EXTENSIONS
    ]

    if not videos:
        return []

    results = []

    for video in videos:
        try:
            result = process_video(video)
            results.append(result)

        except Exception as e:
            try:
                result = quarantine(video, f"ERROR: {e}")
            except Exception:
                result = {
                    "status": "quarantined",
                    "original": video.name,
                    "destination": "",
                    "reason": f"ERROR: {e}",
                }

            results.append(result)

    return results


if __name__ == "__main__":
    results = run_inbox_analysis()

    filed = [r for r in results if r["status"] == "filed"]
    quarantined = [r for r in results if r["status"] == "quarantined"]

    print(f"Filed: {len(filed)}")
    print(f"Quarantined: {len(quarantined)}")