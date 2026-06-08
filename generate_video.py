import os
import csv
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

CSV_FILE = "street_kingz_master_clip_database.csv"
VOICE_LIBRARY_FILE = "ben_voice_library.txt"


def load_clips(csv_file):
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV not found: {csv_file}")

    with open(csv_file, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_voice_library(voice_file):
    if not os.path.exists(voice_file):
        print(f"Voice library not found: {voice_file}")
        return ""

    with open(voice_file, "r", encoding="utf-8") as file:
        return file.read()[:12000]


def detect_topic(video_request):
    request = video_request.lower()

    if any(word in request for word in ["wheel", "wheels", "barrel brush", "brush", "alloy", "spokes"]):
        return {
            "topic": "wheels",
            "include_categories": ["wheels", "foam", "general", "product"],
            "include_words": ["wheel", "wheels", "barrel", "brush", "foam", "rinse", "spoke", "alloy"],
            "exclude_categories": ["drying", "glass", "interior"],
            "exclude_words": ["towel", "drying towel", "glass", "interior", "windscreen"]
        }

    if any(word in request for word in ["dry", "drying", "towel", "1200", "800"]):
        return {
            "topic": "drying",
            "include_categories": ["drying", "general", "product"],
            "include_words": ["dry", "drying", "towel", "1200", "800", "water", "wet"],
            "exclude_categories": ["wheels", "glass", "interior"],
            "exclude_words": ["wheel", "barrel brush", "foam cannon", "glass", "interior"]
        }

    if any(word in request for word in ["glass", "window", "windscreen"]):
        return {
            "topic": "glass",
            "include_categories": ["glass", "general", "product"],
            "include_words": ["glass", "window", "windscreen", "waffle", "smudge"],
            "exclude_categories": ["wheels", "drying", "interior"],
            "exclude_words": ["wheel", "barrel brush", "drying towel", "interior"]
        }

    if any(word in request for word in ["interior", "scrub pad", "inside"]):
        return {
            "topic": "interior",
            "include_categories": ["interior", "general", "product"],
            "include_words": ["interior", "inside", "scrub", "pad"],
            "exclude_categories": ["wheels", "drying", "glass"],
            "exclude_words": ["wheel", "drying towel", "glass"]
        }

    return {
        "topic": "general",
        "include_categories": [],
        "include_words": [],
        "exclude_categories": [],
        "exclude_words": []
    }


def clip_text(clip):
    return " ".join([
        clip.get("folder", ""),
        clip.get("relative_folder", ""),
        clip.get("suggested_filename", ""),
        clip.get("product", ""),
        clip.get("category", ""),
        clip.get("story_role", ""),
        clip.get("simple_description", ""),
        clip.get("primary_action", ""),
        clip.get("shot_type", ""),
        clip.get("best_use", ""),
        clip.get("tags", ""),
    ]).lower()


def filter_relevant_clips(clips, topic_info):
    if topic_info["topic"] == "general":
        return clips

    filtered = []

    for clip in clips:
        text = clip_text(clip)
        category = clip.get("category", "").lower()

        if category in topic_info["exclude_categories"]:
            continue

        if any(word in text for word in topic_info["exclude_words"]):
            continue

        category_match = category in topic_info["include_categories"]
        word_match = any(word in text for word in topic_info["include_words"])

        if category_match or word_match:
            filtered.append(clip)

    return filtered


def limit_clips_for_prompt(clips, max_clips=80):
    def score_clip(clip):
        score = 0

        try:
            score += int(float(clip.get("hook_score", 0) or 0))
            score += int(float(clip.get("demo_score", 0) or 0))
            score += int(float(clip.get("reveal_score", 0) or 0))
            score += int(float(clip.get("visual_interest_score", 0) or 0))
        except ValueError:
            pass

        role = clip.get("story_role", "").lower()

        if role == "problem":
            score += 8
        elif role == "solution":
            score += 6
        elif role == "result":
            score += 8
        elif role == "product_showcase":
            score += 5

        return score

    return sorted(clips, key=score_clip, reverse=True)[:max_clips]


def format_clips_for_prompt(clips):
    formatted = []

    for clip in clips:
        formatted.append(
            f"""
Original Filename: {clip.get("original_filename", "")}
Folder: {clip.get("folder", "")}
Relative Folder: {clip.get("relative_folder", "")}
Suggested Filename: {clip.get("suggested_filename", "")}
Product: {clip.get("product", "")}
Category: {clip.get("category", "")}
Story Role: {clip.get("story_role", "")}
Description: {clip.get("simple_description", "")}
Primary Action: {clip.get("primary_action", "")}
Shot Type: {clip.get("shot_type", "")}
Hook Score: {clip.get("hook_score", "")}
Demo Score: {clip.get("demo_score", "")}
Reveal Score: {clip.get("reveal_score", "")}
B-roll Score: {clip.get("broll_score", "")}
Visual Interest Score: {clip.get("visual_interest_score", "")}
Best Use: {clip.get("best_use", "")}
Tags: {clip.get("tags", "")}
"""
        )

    return "\n---\n".join(formatted)


def generate_video_plan(video_request, clips, voice_library):
    topic_info = detect_topic(video_request)
    relevant_clips = filter_relevant_clips(clips, topic_info)
    relevant_clips = limit_clips_for_prompt(relevant_clips)

    if not relevant_clips:
        relevant_clips = limit_clips_for_prompt(clips)

    clips_text = format_clips_for_prompt(relevant_clips)

    prompt = f"""
You are creating short-form TikTok content for Street Kingz.

Brand:
Street Kingz sells car detailing products to everyday car owners.
The audience is weekend warriors, not professional detailers.
The brand is practical, blunt, slightly sarcastic, and anti-overcomplication.

Detected request topic:
{topic_info["topic"]}

CRITICAL CLIP SELECTION RULES:
- Only use clips relevant to the detected topic.
- Do not mix unrelated product categories.
- Do not use drying towel clips in wheel brush videos.
- Do not use wheel clips in drying towel videos.
- Do not use glass clips in wheel or drying videos.
- Build videos using relevant story roles:
  - problem clips for the opening
  - solution clips for product/use
  - result clips for the ending
- If the database lacks relevant problem/result footage, say so in MISSING FOOTAGE.
- Use original filenames exactly.
- Do not invent filenames.

CRITICAL:
Do not write generic marketing copy.
Do not write like a TikTok agency.
Do not write like an American sales page.
Do not force jokes.
Do not say:
- "your wheels will thank you"
- "your ride"
- "game changer"
- "next level"
- "transform your car"
- "premium quality"
- "rocket science"
- "weekend mate"
- "no hype"

BEN VOICE LIBRARY:
Study these real transcripts from Ben's existing Street Kingz videos.
Copy the structure, rhythm, and bluntness.
Do not quote them directly unless it naturally fits.
Use them to understand how Ben actually talks.

{voice_library}

BEN STYLE RULES:
- Start from a relatable situation, complaint, observation, or reply.
- Product comes after the problem, not before.
- Use casual phrasing.
- Short sentences.
- Swearing is allowed only if it sounds natural.
- Ben often admits laziness, confusion, or annoyance.
- Ben often says "Get yours."
- Ben explains products practically, not technically.
- Ben takes the piss without sounding like a comedian.
- Avoid polished marketing language.

Common Ben structures:
1. Observation → problem → product → proof → Get yours.
2. Comment/reply → blunt answer → explanation → product use → Get yours.
3. Relatable inconvenience → why it is annoying → simple fix → product → Get yours.

User request:
"{video_request}"

Available relevant clip database:
{clips_text}

CONTENT STRATEGY:

Determine:

Primary Goal:
Secondary Goal:

Choose from:
- Sales
- Engagement
- Education
- Trust Building
- Product Awareness

Then create concepts that maximise those goals.

Task:
Create THREE different 20-30 second TikTok video concepts using ONLY the available clips.

Concept 1:
Deadpan Sales

Concept 2:
Educational

Concept 3:
Satisfying / ASMR

Rules:
- Choose 4 to 8 clips only per concept.
- Use original filenames exactly.
- Do not invent filenames.
- Prefer a proper story arc:
  1. Problem
  2. Product/use
  3. Result
  4. CTA
- Maximum 65 words of voiceover.
- CTA should be plain.
- Do not use hashtags unless specifically asked.
- Keep captions short and usable.
- Prefer simple language.
- Avoid fake humour.
- Avoid fake enthusiasm.
- Avoid corporate language.
- Do not overexplain.
- Do not make every concept sound the same.

For each concept return:

VIDEO TITLE:
CONTENT TYPE:
PRIMARY GOAL:
SECONDARY GOAL:
HOOK:
VOICEOVER:
CLIP SEQUENCE:
1.
2.
3.
4.
CAPTION:
ON-SCREEN TEXT:
MISSING FOOTAGE:
CTA:

SCORING:
HOOK POTENTIAL: /10
SALES POTENTIAL: /10
RETENTION POTENTIAL: /10
OVERALL SCORE: /10

--------------------------------------------------

After all three concepts return:

WINNER:

WHY IT WON:

MISSING FOOTAGE PRIORITY:

1.
2.
3.

FILMING ROI SCORE:

For each missing shot rate:

HIGH ROI
MEDIUM ROI
LOW ROI

Explain briefly why.
"""

    print(f"Detected topic: {topic_info['topic']}")
    print(f"Using {len(relevant_clips)} relevant clips.")

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


def main():
    clips = load_clips(CSV_FILE)
    voice_library = load_voice_library(VOICE_LIBRARY_FILE)

    if not clips:
        print("No clips found in CSV.")
        return

    print(f"Loaded {len(clips)} clips from {CSV_FILE}")

    if voice_library:
        print(f"Loaded voice library from {VOICE_LIBRARY_FILE}")
    else:
        print("Continuing without voice library.")

    video_request = input("What video do you want to create? ")

    result = generate_video_plan(video_request, clips, voice_library)

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)


if __name__ == "__main__":
    main()