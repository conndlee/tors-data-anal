"""Sample frames from each video for labelling tool masks (visual field work).

Usage:
    python scripts/sample_label_frames.py

Takes FRAMES_PER_VIDEO random times per video (fixed seed, so it is repeatable),
skipping the first and last EDGE seconds, and saves the left eye at full size.

Output:
    data/derived/occlusion/frames/<video>_<time>.png
    data/derived/occlusion/frames.csv   video, system, t_video, file
"""

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from bagio import SYSTEM_BY_BAG

VIDEO_DIR = Path("data/video")
OUT_DIR = Path("data/derived/occlusion")
SYNC_FILE = Path("results/sync/offsets.csv")
FRAMES_PER_VIDEO = 25
EDGE = 300  # s
SEED = 0
LEFT_EYE = "crop=960:1040:0:40"


def video_duration(video):
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]
    return float(subprocess.run(command, capture_output=True, text=True, check=True).stdout)


def save_frame(video, t, path):
    command = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video),
               "-frames:v", "1", "-vf", LEFT_EYE, str(path)]
    subprocess.run(command, check=True)


def sample_video(video, system, rng):
    times = np.sort(rng.uniform(EDGE, video_duration(video) - EDGE, FRAMES_PER_VIDEO))
    rows = []
    for t in times:
        path = OUT_DIR / "frames" / f"{video.stem}_{t:07.1f}.png"
        save_frame(video, t, path)
        rows.append({"video": video.name, "system": system, "t_video": round(t, 1), "file": path.name})
    return rows


def main():
    (OUT_DIR / "frames").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    sync = pd.read_csv(SYNC_FILE)
    rows = []
    for row in sync.itertuples():
        rows += sample_video(VIDEO_DIR / f"{row.video}.mp4", SYSTEM_BY_BAG[row.bag], rng)
        print(f"{row.video}: done", flush=True)
    pd.DataFrame(rows).to_csv(OUT_DIR / "frames.csv", index=False)


if __name__ == "__main__":
    main()
