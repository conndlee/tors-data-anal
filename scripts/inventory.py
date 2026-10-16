"""List what is inside each rosbag and video in the data folder.

Usage:
    python scripts/inventory.py [data_dir]

data_dir defaults to ./data
"""

import json
import subprocess
import sys
from pathlib import Path

from rosbags.rosbag1 import Reader

BAG_EXTENSIONS = {".bag"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov"}


def find_files(data_dir, extensions):
    return sorted(p for p in data_dir.rglob("*") if p.suffix.lower() in extensions)


def describe_bag(path):
    with Reader(path) as reader:
        seconds = reader.duration / 1e9
        print(f"\n{path}  ({seconds:.1f} s)")
        for topic, info in sorted(reader.topics.items()):
            rate = info.msgcount / seconds if seconds > 0 else 0
            print(f"  {topic:50s} {info.msgtype:45s} {info.msgcount:8d} msgs  {rate:7.1f} Hz")


def describe_video(path):
    command = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    result = json.loads(subprocess.run(command, capture_output=True, text=True).stdout)
    stream = result["streams"][0]
    seconds = float(result["format"]["duration"])
    print(f"{path}  {stream['width']}x{stream['height']}  {stream['r_frame_rate']} fps  {seconds:.1f} s")


def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")

    bags = find_files(data_dir, BAG_EXTENSIONS)
    print(f"=== Rosbags ({len(bags)}) ===")
    for bag in bags:
        describe_bag(bag)

    videos = find_files(data_dir, VIDEO_EXTENSIONS)
    print(f"\n=== Videos ({len(videos)}) ===")
    for video in videos:
        describe_video(video)


if __name__ == "__main__":
    main()
