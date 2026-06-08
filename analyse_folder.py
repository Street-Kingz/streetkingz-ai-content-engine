import os
import cv2
import csv
import base64
import time
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v")
TEST_LIMIT = 999

PRODUCT_LOOKUP = {
    "800": "Street Kingz 800gsm XL Drying Towel",
    "1200": "Street Kingz 1200gsm Heavy Duty Drying Towel",
    "barrel brush": "Street Kingz XL Barrel Brush or Small Barrel Brush",
    "wash mitt": "Street Kingz Microfibre Wash Mitt",
    "buckets": "Street Kingz detailing bucket / grit guard content",
    "foam cannon": "Street Kingz Premium Snow Foam Lance",
    "dirty wheels": "Dirty wheel footage",
    "cleaning wheels": "Wheel cleaning footage",
    "clean wheels": "Clean wheel result footage",
    "before wash": "Dirty car / before wash footage",
    "jetwash prewash": "Pre-wash jetwash footage",
    "jetwash snow": "Snow foam footage",
    "jetwash rinse": "Rinse footage",
    "clean car": "Clean car result footage",
}


def clean_path(path):
    return path.strip().strip("'").strip('"').replace("\\ ", " ")


def get_folder_context(video_path):
    folder_name = os.path.basename(os.path.dirname(video_path))
    folder_key = folder_name.lower()
    return folder_name, PRODUCT_LOOKUP.get(folder_key, folder_name)


def extract_frames(video_path, frame_samples=5):
    cap = cv2.VideoCapture(video_path)

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


def empty_row(video_path, folder_name, error_message):
    return {
        "original_filename": os.path.basename(video_path),
        "folder": folder_name,
        "suggested_filename": "",
        "product": "",
        "category": "",
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


def analyse_video(video_path):
    folder_name, folder_context = get_folder_context(video_path)
    images = extract_frames(video_path)

    if not images:
        return empty_row(video_path, folder_name, "ERROR: No readable frames extracted")

    prompt = f"""
You are analysing video clips for Street Kingz, a UK car detailing product brand.

Brand context:
Street Kingz sells premium but simple car detailing products to everyday car owners.
The tone is straightforward, slightly sarcastic, practical, and not aimed at professional detailers.

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
The uploaded video came from folder: "{folder_name}"
This likely means: "{folder_context}"

Important rules:
- Do not invent products that are not shown.
- If the product is unclear, say "unclear".
- Use the folder context to guide your answer.
- Keep the answer practical for making TikTok videos.
- Suggested filename should be lowercase, hyphen-separated, and end in .mov.
- category must be one of: drying, wheels, foam, interior, glass, product, general
- shot_type must be one of: hook, demo, reveal, broll, product_shot
- simple_description must be under 8 words.
- primary_action must be under 5 words.
- tags must be comma-separated plain words, not hashtags.
- scores must be numbers only from 1 to 10.
- scores must vary honestly. Do not give every clip similar scores.

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
            "folder": folder_name,
            "suggested_filename": result.get("suggested_filename", ""),
            "product": result.get("product", ""),
            "category": result.get("category", ""),
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
        return empty_row(video_path, folder_name, f"ERROR: {e}")


def main():
    folder_path = clean_path(input("Enter folder path: "))

    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"Folder not found: {folder_path}")

    videos = [
        os.path.join(folder_path, file)
        for file in os.listdir(folder_path)
        if file.lower().endswith(VIDEO_EXTENSIONS)
    ]

    videos = sorted(videos)[:TEST_LIMIT]

    if not videos:
        print("No video files found.")
        return

    output_file = "street_kingz_clip_database.csv"

    fields = [
        "original_filename",
        "folder",
        "suggested_filename",
        "product",
        "category",
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
    print(f"Test limit: {TEST_LIMIT}")
    print(f"Writing results to {output_file}")
    print("Starting analysis...")

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()

        for index, video_path in enumerate(videos, start=1):
            print(f"[{index}/{len(videos)}] Analysing {os.path.basename(video_path)}")

            row = analyse_video(video_path)
            writer.writerow(row)

            time.sleep(0.3)

    print("Done.")
    print(f"CSV created: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    main()