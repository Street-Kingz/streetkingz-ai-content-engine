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


def parse_weekly_plan(plan_text):
    if not plan_text:
        return {}

    video_blocks = re.split(r"\n(?=DAY:\s*\d+)", plan_text.strip())
    days = {}

    for block in video_blocks:
        day_match = re.search(r"DAY:\s*(\d+)", block)
        post_match = re.search(r"POST NUMBER:\s*(\d+)", block)
        title_match = re.search(r"VIDEO TITLE:\s*(.+)", block)
        type_match = re.search(r"VIDEO TYPE:\s*(.+)", block)
        topic_match = re.search(r"TOPIC:\s*(.+)", block)

        if not day_match:
            continue

        post_number = int(post_match.group(1)) if post_match else len(days) + 1
        day = ((post_number - 1) // 3) + 1

        video = {
            "post_number": post_match.group(1).strip() if post_match else "",
            "title": title_match.group(1).strip() if title_match else "Untitled Video",
            "type": type_match.group(1).strip() if type_match else "",
            "topic": topic_match.group(1).strip() if topic_match else "",
            "full_text": block.strip(),
        }

        days.setdefault(day, []).append(video)

    return dict(sorted(days.items()))


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
    plan = read_weekly_plan()

    if not plan:
        plan = ""

    days = parse_weekly_plan(plan)

    return render_template(
        "weekly_plan.html",
        plan=plan,
        days=days,
    )


if __name__ == "__main__":
    app.run(debug=True)