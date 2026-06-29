import os
import re
import csv
import shutil
import subprocess
from pathlib import Path

MASTER_CLIP_FOLDER = "/Users/ben/Desktop/B Roll"
MASTER_DATABASE = "street_kingz_master_clip_database.csv"
OUTPUT_ROOT = "Edit Packs"


def clean_filename(name):
    name = name.strip()
    name = re.sub(r"[^\w\s.-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:80]


def load_database():
    if not os.path.exists(MASTER_DATABASE):
        raise FileNotFoundError(f"Database not found: {MASTER_DATABASE}")

    rows = []

    with open(MASTER_DATABASE, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            rows.append(row)

    return rows


def build_file_index(rows):
    index = {}

    for row in rows:
        filename = row.get("original_filename", "").strip()
        relative_folder = row.get("relative_folder", "").strip()

        if not filename:
            continue

        full_path = Path(MASTER_CLIP_FOLDER) / relative_folder / filename
        key = filename.lower()

        if key not in index:
            index[key] = []

        index[key].append({
            "full_path": full_path,
            "row": row
        })

    return index


def extract_filenames_from_plan(plan_text):
    possible_files = re.findall(
        r"[A-Za-z0-9_()'’,-]+\.(?:mov|MOV|mp4|MP4|m4v|M4V)",
        plan_text
    )

    cleaned = []

    for file in possible_files:
        file = file.strip()
        file = file.replace("(", "").replace(")", "")
        file = file.replace("–", "-")
        file = re.sub(r"^\d+\.\s*", "", file).strip()

        if file not in cleaned:
            cleaned.append(file)

    return cleaned


def choose_match(filename, matches):
    existing = [match for match in matches if match["full_path"].exists()]

    if existing:
        return existing[0]

    return matches[0]


def create_edit_pack(video_title, filenames, file_index, plan_text, output_root=None):
    safe_title = clean_filename(video_title)

    if output_root:
        output_folder = Path(output_root) / safe_title
    else:
        output_folder = Path(OUTPUT_ROOT) / safe_title

    output_folder.mkdir(parents=True, exist_ok=True)

    copied = []
    missing = []

    for index, filename in enumerate(filenames, start=1):
        lookup_key = filename.lower()
        matches = file_index.get(lookup_key)

        if not matches:
            missing.append(filename)
            continue

        selected = choose_match(filename, matches)
        source_path = selected["full_path"]

        if not source_path.exists():
            missing.append(filename)
            continue

        row = selected["row"]
        role = row.get("story_role", "clip") or "clip"
        description = row.get("simple_description", "clip") or "clip"

        safe_description = clean_filename(description)
        extension = source_path.suffix

        output_name = f"{index:02d}_{role}_{safe_description}_{source_path.stem}{extension}"
        destination = output_folder / output_name

        shutil.copy2(source_path, destination)

        copied.append({
            "order": index,
            "original": filename,
            "copied_as": output_name,
            "source": str(source_path),
            "role": role,
            "description": description,
        })

    plan_file = output_folder / "video_plan.txt"

    with open(plan_file, "w", encoding="utf-8") as file:
        file.write(f"VIDEO TITLE:\n{video_title}\n\n")
        file.write("COPIED CLIPS:\n")

        for item in copied:
            file.write(
                f"{item['order']}. {item['copied_as']}\n"
                f"   Original: {item['original']}\n"
                f"   Role: {item['role']}\n"
                f"   Description: {item['description']}\n"
                f"   Source: {item['source']}\n\n"
            )

        if missing:
            file.write("\nMISSING CLIPS:\n")
            for item in missing:
                file.write(f"- {item}\n")

        file.write("\nFULL PLAN:\n")
        file.write(plan_text)

    return output_folder, copied, missing


def open_in_finder(path):
    subprocess.run(["open", str(path)])


def main():
    print("Paste one generated video plan below.")
    print("When finished, type END on a new line and press Enter.\n")

    lines = []

    while True:
        line = input()

        if line.strip() == "END":
            break

        lines.append(line)

    plan_text = "\n".join(lines)

    if not plan_text.strip():
        print("No plan pasted.")
        return

    title_match = re.search(r"VIDEO TITLE:\s*(.+)", plan_text, re.IGNORECASE)

    if title_match:
        video_title = title_match.group(1).strip()
    else:
        video_title = input("Video title not found. Enter title: ").strip()

    filenames = extract_filenames_from_plan(plan_text)

    if not filenames:
        print("No video filenames found in the pasted plan.")
        return

    print(f"\nFound {len(filenames)} clip filename(s):")
    for file in filenames:
        print(f"- {file}")

    rows = load_database()
    file_index = build_file_index(rows)

    output_folder, copied, missing = create_edit_pack(
        video_title,
        filenames,
        file_index,
        plan_text
    )

    print(f"\nEdit pack created: {output_folder.resolve()}")
    print(f"Copied clips: {len(copied)}")
    print(f"Missing clips: {len(missing)}")

    if missing:
        print("\nMissing:")
        for item in missing:
            print(f"- {item}")

    open_in_finder(output_folder)


if __name__ == "__main__":
    main()