import os
import cv2
from pathlib import Path

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v")


def clean_path(path):
    return path.strip().strip("'").strip('"').replace("\\ ", " ")


def get_duration(video_path):
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        return None

    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.release()

    if fps <= 0:
        return None

    return frame_count / fps


def main():
    folder_path = clean_path(input("Enter folder path: "))

    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    videos = [
        file for file in folder.iterdir()
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
    ]

    if not videos:
        print("No video files found.")
        return

    durations = []

    print("\nClip Lengths:\n")

    for video in sorted(videos):
        duration = get_duration(video)

        if duration is None:
            print(f"{video.name}: unreadable")
        else:
            durations.append(duration)
            print(f"{video.name}: {duration:.1f} seconds")

    if durations:
        print("\nSummary:")
        print(f"Clips scanned: {len(durations)}")
        print(f"Shortest: {min(durations):.1f}s")
        print(f"Longest: {max(durations):.1f}s")
        print(f"Average: {sum(durations) / len(durations):.1f}s")


if __name__ == "__main__":
    main()