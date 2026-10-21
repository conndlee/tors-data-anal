"""Motion signal for each video, used to sync video time to rosbag time.

Usage:
    python scripts/video_motion.py [video ...]

Defaults to every video in data/video. Slow (decodes the whole video), so run in background.

The videos are screen recordings of two stereo windows side by side, each with a
title bar. We keep only the left eye below its title bar, shrink it, and take the
mean absolute difference between frames.

Output, per video, in data/derived/video/<video>.parquet:
    t       seconds since video start
    motion  mean absolute grey-level change since the previous sample (0-255)
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from project import LEFT_EYE, VIDEO_DIR

OUTPUT_DIR = Path("data/derived/video")
FPS = 10
WIDTH, HEIGHT = 96, 104
CHUNK = 1000  # frames read at a time


def decode_command(video):
    filters = f"fps={FPS},{LEFT_EYE},scale={WIDTH}:{HEIGHT},format=gray"
    return ["ffmpeg", "-v", "error", "-i", str(video), "-vf", filters, "-f", "rawvideo", "-"]


def read_frames(video):
    """Yield blocks of small grey frames, shape (n, HEIGHT, WIDTH)."""
    frame_size = WIDTH * HEIGHT
    with subprocess.Popen(decode_command(video), stdout=subprocess.PIPE) as process:
        while True:
            raw = process.stdout.read(frame_size * CHUNK)
            if len(raw) < frame_size:
                return
            usable = len(raw) - len(raw) % frame_size
            yield np.frombuffer(raw[:usable], np.uint8).reshape(-1, HEIGHT, WIDTH)


def motion_signal(video):
    values = []
    previous = None
    for block in read_frames(video):
        frames = block.astype(np.int16)
        if previous is not None:
            frames = np.concatenate([previous[None], frames])
        values.extend(np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)))
        previous = frames[-1]
    t = (np.arange(len(values)) + 1) / FPS
    return pd.DataFrame({"t": t, "motion": values})


def videos_from_args(args):
    return [Path(arg) for arg in args] or sorted(VIDEO_DIR.glob("*.mp4"))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for video in videos_from_args(sys.argv[1:]):
        print(f"start: {video.name}", flush=True)
        motion_signal(video).to_parquet(OUTPUT_DIR / f"{video.stem}.parquet", index=False)
        print(f"done: {video.name}", flush=True)


if __name__ == "__main__":
    main()
