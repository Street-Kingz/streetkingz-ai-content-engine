import os
import cv2
import csv
import base64
import time
import json
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v")
TEST_LIMIT = 9999
OUTPUT_FILE = "street_kingz_master_clip_database.csv"

PRODUCT_LOOKUP = {
    "800": "Street Kingz 800gsm XL Drying Towel",
    "1200": "Street Kingz 1200gsm Heavy Duty Drying Towel",
    "barrel brush": "Street Kingz XL Barrel Brush or Small Barrel Brush",
    "small barrel brush": "Street Kingz Small Barrel Brush",
    "wash mitt": "Street Kingz Microfibre Wash Mitt",
    "buckets": "Street Kingz detailing bucket / grit guard content",
    "foam cannon": "Street Kingz Premium Snow Foam Lance",
    "dirty wheels": "Dirty wheel problem footage",
    "cleaning wheels": "Wheel cleaning solution footage",
    "clean wheels": "Clean wheel result footage",
    "before wash": "Dirty car / before wash problem footage",
    "jetwash prewash": "Pre-wash footage",
    "jetwash snow": "Snow foam footage",
    "jetwash rinse": "Rinse footage",
    "clean car": "Clean car result footage",
}


def clean_path(path):
    return path.strip().strip("'").strip('"').replace("\\ ", " ")


def get_folder_context(video_path, root_folder):
    video_path = Path(video_path)
    root_folder = Path(root_folder)

    parent_folder = video_path.parent.name
    relative_folder = str(video_path.parent.relative_to(root_folder))

    folder_key = parent_folder.lower()

    return {
        "folder": parent_folder,
        "relative_folder": relative_folder,
        "folder_context": PRODUCT_LOOKUP.get(folder_key, parent_folder),
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


def empty_row(video_path, folder_info, error_message):
    return {
        "original_filename": os.path.basename(video_path),
        "folder": folder_info["folder"],
        "relative_folder": folder_info["relative_folder"],
        "suggested_filename": "",
        "product": "",
        "category": "",
        "story_role": "",
        "simple_description": error_message,
        "primary_action": "",
        "shot_type": "",
        "hook_score": "",
        "demo_score": "",
        "reveal_score": "",
        "broll_score": "",
        "visual_interest_score": "",
        "best_use": "",
        "tags": "",
    }


def analyse_video(video_path, root_folder):
    folder_info = get_folder_context(video_path, root_folder)
    images = extract_frames(video_path)

    if not images:
        return empty_row(video_path, folder_info, "ERROR: No readable frames extracted")

    prompt = f"""
You are analysing video clips for Street Kingz, a UK car detailing product brand.

Brand context:
Street Kingz sells simple car detailing products to everyday car owners.
The audience is weekend warriors, not professional detailers.
The content system needs clips to build:
Problem -> Solution -> Result videos.

Known Street Kingz products:
- 800gsm XL Drying Towel
- 1200gsm Heavy Duty Drying Towel
- XL Barrel Brush
- Small Barrel Brush
- Microfibre Wash Mitt
- Foam Cannon / Snow Foam Lance
- Buckets and grit guards
- Glass Cleaner
- Interior Cleaner
- Shampoo

Folder context:
Parent folder: "{folder_info["folder"]}"
Relative folder: "{folder_info["relative_folder"]}"
This likely means: "{folder_info["folder_context"]}"

Important rules:
- Do not invent products that are not shown.
- If the product is unclear, say "unclear".
- Use folder context to guide your answer.
- Suggested filename should be lowercase, hyphen-separated, and end in .mov.
- category must be one of: drying, wheels, foam, interior, glass, product, general
- story_role must be one of: problem, solution, result, product_showcase, broll
- shot_type must be one of: hook, demo, reveal, broll, product_shot
- simple_description must be under 8 words.
- primary_action must be under 5 words.
- tags must be comma-separated plain words, not hashtags.
- scores must be numbers only from 1 to 10.
- scores must vary honestly.

Scoring guidance:
- hook_score = how good the clip is as the opening 1-3 seconds
- demo_score = how clearly it demonstrates product use
- reveal_score = how clearly it shows a result or transformation
- broll_score = how useful it is as filler/supporting footage
- visual_interest_score = how visually satisfying or scroll-stopping it is

Return ONLY valid JSON in this exact structure:

{{
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
}}
"""

    try:
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

        result = json.loads(response.output_text)

        return {
            "original_filename": os.path.basename(video_path),
            "folder": folder_info["folder"],
            "relative_folder": folder_info["relative_folder"],
            "suggested_filename": result.get("suggested_filename", ""),
            "product": result.get("product", ""),
            "category": result.get("category", ""),
            "story_role": result.get("story_role", ""),
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

    except Exception as e:
        return empty_row(video_path, folder_info, f"ERROR: {e}")


def find_videos_recursive(root_folder):
    root = Path(root_folder)

    videos = [
        file for file in root.rglob("*")
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
    ]

    return sorted(videos)


def main():
    root_folder = clean_path(input("Enter master library folder path: "))

    if not os.path.isdir(root_folder):
        raise NotADirectoryError(f"Folder not found: {root_folder}")

    videos = find_videos_recursive(root_folder)
    videos = videos[:TEST_LIMIT]

    if not videos:
        print("No video files found.")
        return

    fields = [
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

    print(f"Found {len(videos)} videos.")
    print(f"Writing results to {OUTPUT_FILE}")
    print("Starting recursive master analysis...")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        csvfile.flush()

        for index, video_path in enumerate(videos, start=1):
            print(f"[{index}/{len(videos)}] Analysing {video_path.relative_to(root_folder)}")

            row = analyse_video(video_path, root_folder)
            writer.writerow(row)
            csvfile.flush()

            time.sleep(0.3)

    print("Done.")
    print(f"CSV created: {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()