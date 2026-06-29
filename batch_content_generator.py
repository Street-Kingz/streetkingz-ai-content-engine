import os
import csv
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

CSV_FILE = "street_kingz_master_clip_database.csv"
VOICE_LIBRARY_FILE = "ben_voice_library.txt"
OUTPUT_FILE = "street_kingz_7_day_content_plan.txt"


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


def score_clip(clip):
    score = 0

    for field in ["hook_score", "demo_score", "reveal_score", "visual_interest_score"]:
        try:
            score += int(float(clip.get(field, 0) or 0))
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


def filter_topic(clips, topic):
    topic = topic.lower()

    topic_rules = {
        "wheels": {
            "include": ["wheel", "wheels", "barrel", "brush", "spoke", "alloy", "foam", "rinse"],
            "exclude": ["drying towel", "windscreen", "glass", "interior"]
        },
        "drying": {
            "include": ["dry", "drying", "towel", "1200", "800", "water", "wet"],
            "exclude": ["wheel", "barrel brush", "glass", "interior"]
        },
        "foam": {
            "include": ["foam", "snow", "lance", "cannon", "shampoo", "prewash"],
            "exclude": ["glass", "interior"]
        },
        "glass": {
            "include": ["glass", "window", "windscreen", "waffle", "smudge"],
            "exclude": ["wheel", "drying towel", "interior"]
        },
        "interior": {
            "include": ["interior", "inside", "scrub", "pad"],
            "exclude": ["wheel", "drying towel", "glass"]
        },
        "general": {
            "include": [],
            "exclude": []
        }
    }

    rules = topic_rules.get(topic, topic_rules["general"])

    if topic == "general":
        return clips

    filtered = []

    for clip in clips:
        text = clip_text(clip)

        if any(word in text for word in rules["exclude"]):
            continue

        if any(word in text for word in rules["include"]):
            filtered.append(clip)

    return filtered


def select_best_clips(clips, max_clips=120):
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


def build_campaign_context(primary_product="", secondary_product="", weekly_focus="", focus_strength="Light"):
    primary_product = (primary_product or "").strip()
    secondary_product = (secondary_product or "").strip()
    weekly_focus = (weekly_focus or "").strip()
    focus_strength = (focus_strength or "Light").strip().title()

    if focus_strength not in ["Light", "Medium", "Heavy"]:
        focus_strength = "Light"

    if not primary_product and not secondary_product and not weekly_focus:
        return """
CAMPAIGN BRIEF:
No campaign focus provided.

Rules:
- Do not invent trends, weather angles, seasonal topics, or topical hooks.
- Generate evergreen Street Kingz content only.
- Focus on usable videos from the available clips.
"""

    return f"""
CAMPAIGN BRIEF:
Primary Product: {primary_product if primary_product else "None provided"}
Secondary Product: {secondary_product if secondary_product else "None provided"}
Weekly Focus: {weekly_focus if weekly_focus else "None provided"}
Focus Strength: {focus_strength}

Campaign rules:
- Use the campaign brief as steering, not as a forced script.
- Do not force weak relevance.
- Do not make every video about the campaign unless Focus Strength is Heavy.
- If Focus Strength is Light, influence roughly 3-5 videos.
- If Focus Strength is Medium, influence roughly 6-9 videos.
- If Focus Strength is Heavy, influence roughly 10-14 videos.
- Blank fields must be ignored completely.
- If Weekly Focus is blank, do not invent a topical angle.
- Keep the content grounded in available clips.
"""


def generate_batch_plan(
    video_count,
    topics,
    clips,
    voice_library,
    primary_product="",
    secondary_product="",
    weekly_focus="",
    focus_strength="Light",
):
    selected_clips = []

    for topic in topics:
        topic_clips = filter_topic(clips, topic)
        selected_clips.extend(select_best_clips(topic_clips, max_clips=80))

    seen = set()
    unique_clips = []

    for clip in selected_clips:
        key = (clip.get("relative_folder", ""), clip.get("original_filename", ""))

        if key not in seen:
            seen.add(key)
            unique_clips.append(clip)

    unique_clips = select_best_clips(unique_clips, max_clips=160)

    clips_text = format_clips_for_prompt(unique_clips)
    campaign_context = build_campaign_context(
        primary_product=primary_product,
        secondary_product=secondary_product,
        weekly_focus=weekly_focus,
        focus_strength=focus_strength,
    )

    prompt = f"""
You are creating a 7-day TikTok content plan for Street Kingz.

Goal:
Create {video_count} short-form video plans so Ben can post 3 pieces of content per day without spending several evenings creating content.

Brand:
Street Kingz sells car detailing products to everyday car owners.
The audience is weekend warriors, not professional detailers.
The brand is practical, blunt, slightly sarcastic, and anti-overcomplication.

Core content rule:
Every video should have a clear reason to exist.

Avoid generic "product is good" videos.

Strong structures:
1. Problem → product/use → result
2. Annoying situation → simple fix → product → get yours
3. Common mistake → better way → proof
4. Comment/reply style → answer → product/use
5. Satisfying visual → simple caption/CTA

{campaign_context}

BEN VOICE LIBRARY:
Study these real transcripts from Ben's existing Street Kingz videos.
Copy the structure, rhythm, and bluntness.
Do not quote them directly unless it naturally fits.

{voice_library}

VOICE RULES:
- Start from a relatable situation, complaint, observation, or reply.
- Product comes after the problem.
- Keep voiceovers short enough to record quickly.
- Swearing is allowed only if it sounds natural.
- Ben often says "Get yours."
- Do not write like an agency.
- Do not write polished marketing lines.
- Do not say "game changer", "next level", "transform your car", "your ride", or "your wheels will thank you".

Available clip database:
{clips_text}

Topics to cover:
{", ".join(topics)}

Task:
Create exactly {video_count} video plans.

Content mix:
- 7 sales/product videos
- 5 educational videos
- 4 satisfying/ASMR-style videos
- 3 problem/solution videos
- 2 comment/reply-style videos

Rules:
- Use only available clips.
- Use original filenames exactly.
- Do not invent filenames.
- Do not mix unrelated product categories.
- Choose 4 to 8 clips per video.
- Prefer videos that can be edited quickly.
- Prefer varied topics across the week.
- Avoid repeating the same exact clip sequence too often.
- If clips are missing, state that clearly.
- Voiceover max 65 words.
- Caption max 12 words.
- CTA should be plain.
- Campaign focus should guide the content mix only where relevant.
- If no campaign focus was provided, keep the plan evergreen.

For each video return:

DAY:
POST NUMBER:
VIDEO TYPE:
TOPIC:
VIDEO TITLE:
HOOK:
VOICEOVER:
CLIP SEQUENCE:
1.
2.
3.
4.
CAPTION:
ON-SCREEN TEXT:
CTA:
MISSING FOOTAGE:
WHY THIS VIDEO EXISTS:
SALES POTENTIAL: /10
RETENTION POTENTIAL: /10
EDITING DIFFICULTY: Easy / Medium / Hard

After all videos return:

WEEKLY SUMMARY:
- Best sales video:
- Best engagement video:
- Fastest video to make:
- Highest ROI missing footage:
- Suggested filming priority:
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text


def main():
    clips = load_clips(CSV_FILE)
    voice_library = load_voice_library(VOICE_LIBRARY_FILE)

    print(f"Loaded {len(clips)} clips from {CSV_FILE}")

    if voice_library:
        print(f"Loaded voice library from {VOICE_LIBRARY_FILE}")
    else:
        print("Continuing without voice library.")

    video_count_input = input("How many videos do you want? Press Enter for 21: ").strip()
    video_count = int(video_count_input) if video_count_input else 21

    topics_input = input("Topics to include? Press Enter for wheels,drying,foam,glass,interior: ").strip()

    if topics_input:
        topics = [topic.strip().lower() for topic in topics_input.split(",")]
    else:
        topics = ["wheels", "drying", "foam", "glass", "interior"]

    primary_product = input("Primary product? Press Enter to skip: ").strip()
    secondary_product = input("Secondary product? Press Enter to skip: ").strip()
    weekly_focus = input("Weekly focus? Press Enter for evergreen content: ").strip()
    focus_strength = input("Focus strength? Light / Medium / Heavy. Press Enter for Light: ").strip() or "Light"

    print(f"Generating {video_count} videos.")
    print(f"Topics: {', '.join(topics)}")

    if primary_product or secondary_product or weekly_focus:
        print("Campaign focus active.")
    else:
        print("No campaign focus. Evergreen content only.")

    result = generate_batch_plan(
        video_count,
        topics,
        clips,
        voice_library,
        primary_product=primary_product,
        secondary_product=secondary_product,
        weekly_focus=weekly_focus,
        focus_strength=focus_strength,
    )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(result)

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)
    print(f"\nSaved to: {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()