import csv
import os
import re
from collections import Counter
from flask import Flask, render_template, redirect, url_for

from batch_content_generator import (
    load_clips,
    load_voice_library,
    generate_batch_plan,
    CSV_FILE,
    VOICE_LIBRARY_FILE,
    OUTPUT_FILE,
)

from create_edit_pack import (
    load_database as load_edit_pack_database,
    build_file_index,
    extract_filenames_from_plan,
    create_edit_pack,
    open_in_finder,
)

app = Flask(__name__)

MASTER_DATABASE = CSV_FILE
WEEKLY_PLAN_FILE = OUTPUT_FILE


def load_database():
    if not os.path.exists(MASTER_DATABASE):
        return []

    with open(MASTER_DATABASE, "r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def read_weekly_plan():
    if not os.path.exists(WEEKLY_PLAN_FILE):
        return None

    with open(WEEKLY_PLAN_FILE, "r", encoding="utf-8") as file:
        return file.read()


def extract_field(block, label):
    pattern = rf"{label}:\s*(.*?)(?=\n[A-Z][A-Z\s/&]+:|\n\d+\.|\Z)"
    match = re.search(pattern, block, re.DOTALL)

    if not match:
        return ""

    return match.group(1).strip()


def extract_clip_sequence(block):
    match = re.search(
        r"CLIP SEQUENCE:\s*(.*?)(?=\nCAPTION:|\nON-SCREEN TEXT:|\nCTA:|\Z)",
        block,
        re.DOTALL
    )

    if not match:
        return ""

    return match.group(1).strip()


def parse_weekly_plan(plan_text):
    if not plan_text:
        return {}, {}

    video_blocks = re.split(r"\n(?=DAY:\s*\d+)", plan_text.strip())
    days = {}
    videos_by_post = {}

    for block in video_blocks:
        day_match = re.search(r"DAY:\s*(\d+)", block)
        post_match = re.search(r"POST NUMBER:\s*(\d+)", block)

        if not day_match or not post_match:
            continue

        post_number = int(post_match.group(1))
        day = ((post_number - 1) // 3) + 1

        video = {
            "id": post_number,
            "day": day,
            "post_number": post_number,
            "title": extract_field(block, "VIDEO TITLE") or "Untitled Video",
            "type": extract_field(block, "VIDEO TYPE"),
            "topic": extract_field(block, "TOPIC"),
            "hook": extract_field(block, "HOOK"),
            "voiceover": extract_field(block, "VOICEOVER"),
            "clip_sequence": extract_clip_sequence(block),
            "caption": extract_field(block, "CAPTION"),
            "onscreen_text": extract_field(block, "ON-SCREEN TEXT"),
            "cta": extract_field(block, "CTA"),
            "missing_footage": extract_field(block, "MISSING FOOTAGE"),
            "why": extract_field(block, "WHY THIS VIDEO EXISTS"),
            "sales": extract_field(block, "SALES POTENTIAL"),
            "retention": extract_field(block, "RETENTION POTENTIAL"),
            "difficulty": extract_field(block, "EDITING DIFFICULTY"),
            "full_text": block.strip(),
        }

        days.setdefault(day, []).append(video)
        videos_by_post[post_number] = video

    return dict(sorted(days.items())), videos_by_post


@app.route("/")
def dashboard():
    clips = load_database()

    total_clips = len(clips)
    story_roles = Counter(clip.get("story_role", "unknown") or "unknown" for clip in clips)
    categories = Counter(clip.get("category", "unknown") or "unknown" for clip in clips)
    folders = Counter(clip.get("folder", "unknown") or "unknown" for clip in clips)

    weekly_plan_exists = os.path.exists(WEEKLY_PLAN_FILE)

    return render_template(
        "index.html",
        total_clips=total_clips,
        story_roles=story_roles,
        categories=categories,
        folders=folders,
        weekly_plan_exists=weekly_plan_exists,
    )


@app.route("/generate-weekly")
def generate_weekly():
    clips = load_clips(CSV_FILE)
    voice_library = load_voice_library(VOICE_LIBRARY_FILE)

    result = generate_batch_plan(
        video_count=21,
        topics=["wheels", "drying", "foam", "glass", "interior"],
        clips=clips,
        voice_library=voice_library,
    )

    with open(WEEKLY_PLAN_FILE, "w", encoding="utf-8") as file:
        file.write(result)

    return redirect(url_for("weekly_plan"))


@app.route("/weekly-plan")
def weekly_plan():
    plan = read_weekly_plan() or ""
    days, _ = parse_weekly_plan(plan)

    return render_template(
        "weekly_plan.html",
        plan=plan,
        days=days,
        message=None,
    )


@app.route("/create-edit-pack/<int:post_number>")
def create_single_edit_pack(post_number):
    plan = read_weekly_plan() or ""
    days, videos_by_post = parse_weekly_plan(plan)

    video = videos_by_post.get(post_number)

    if not video:
        return render_template(
            "weekly_plan.html",
            plan=plan,
            days=days,
            message=f"Could not find post {post_number}.",
        )

    rows = load_edit_pack_database()
    file_index = build_file_index(rows)
    filenames = extract_filenames_from_plan(video["clip_sequence"])

    output_folder, copied, missing = create_edit_pack(
        video_title=f"Day {video['day']} Video {video['post_number']} - {video['title']}",
        filenames=filenames,
        file_index=file_index,
        plan_text=video["full_text"],
    )

    open_in_finder(output_folder)

    return render_template(
        "weekly_plan.html",
        plan=plan,
        days=days,
        message=f"Created edit pack for Post {post_number}. Copied {len(copied)} clip(s). Missing {len(missing)}.",
    )


if __name__ == "__main__":
    app.run(debug=True)