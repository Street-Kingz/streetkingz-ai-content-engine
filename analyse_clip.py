import os
import cv2
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

VIDEO_PATH = input("Enter video path: ").strip().strip("'").strip('"').replace("\\ ", " ")

if not os.path.exists(VIDEO_PATH):
    raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

FOLDER_NAME = os.path.basename(os.path.dirname(VIDEO_PATH))

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

folder_key = FOLDER_NAME.lower()
folder_context = PRODUCT_LOOKUP.get(folder_key, FOLDER_NAME)

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise ValueError(f"OpenCV could not open video: {VIDEO_PATH}")

frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

if frame_count <= 0:
    raise ValueError(f"No readable frames found in video: {VIDEO_PATH}")

positions = [
    int(frame_count * 0.1),
    int(frame_count * 0.3),
    int(frame_count * 0.5),
    int(frame_count * 0.7),
    int(frame_count * 0.9),
]

images = []

for pos in positions:
    cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
    success, frame = cap.read()

    if success:
        success_encode, buffer = cv2.imencode(".jpg", frame)

        if success_encode:
            images.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{base64.b64encode(buffer).decode()}"
                }
            )

cap.release()

if not images:
    raise ValueError("No frames could be extracted. AI analysis cancelled.")

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
The uploaded video came from folder: "{FOLDER_NAME}"
This likely means: "{folder_context}"

Important rules:
- Do not invent products that are not shown.
- If the product is unclear, say "unclear".
- Use the folder context to guide your answer.
- Keep the answer practical for making TikTok videos.
- Suggested filename should be lowercase, hyphen-separated, and end in .mov.

Return ONLY in this format:

Description:
Suggested Filename:
Product:
Shot Type:
Hook Score /10:
Demo Score /10:
B-roll Score /10:
Best Use:
Tags:
Three TikTok Ideas:
1.
2.
3.
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

print(response.output_text)