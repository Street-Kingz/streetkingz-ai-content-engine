import os
import subprocess
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import imageio_ffmpeg

load_dotenv()
client = OpenAI()

SOURCE_FOLDER = "/Users/ben/Desktop/Street Kingz/Tiktoks"
OUTPUT_FOLDER = "voice_audio"
VOICE_LIBRARY_FILE = "ben_voice_library.txt"

VIDEO_EXTENSIONS = (".mov", ".mp4", ".m4v")


def ensure_output_folder():
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)


def get_ffmpeg_path():
    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_audio(video_path, audio_path):
    ffmpeg = get_ffmpeg_path()

    command = [
        ffmpeg,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "aac",
        "-b:a", "128k",
        str(audio_path),
    ]

    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def transcribe_audio(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file
        )

    return transcript.text.strip()


def main():
    ensure_output_folder()

    source = Path(SOURCE_FOLDER)

    if not source.exists():
        raise FileNotFoundError(f"Source folder not found: {SOURCE_FOLDER}")

    videos = [
        file for file in source.iterdir()
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
    ]

    videos = sorted(videos)

    if not videos:
        print("No videos found.")
        return

    print(f"Found {len(videos)} videos.")
    print("Starting transcription...")

    with open(VOICE_LIBRARY_FILE, "w", encoding="utf-8") as output:
        output.write("BEN VOICE LIBRARY\n")
        output.write("=================\n\n")

        for index, video in enumerate(videos, start=1):
            print(f"[{index}/{len(videos)}] Processing {video.name}")

            audio_path = Path(OUTPUT_FOLDER) / f"{video.stem}.m4a"

            try:
                extract_audio(video, audio_path)
                transcript = transcribe_audio(audio_path)

                output.write(f"FILE: {video.name}\n")
                output.write("TRANSCRIPT:\n")
                output.write(transcript)
                output.write("\n\n---\n\n")

                print("Done")

            except Exception as e:
                output.write(f"FILE: {video.name}\n")
                output.write(f"ERROR: {e}\n\n---\n\n")
                print(f"ERROR: {e}")

    print(f"Voice library created: {os.path.abspath(VOICE_LIBRARY_FILE)}")


if __name__ == "__main__":
    main()