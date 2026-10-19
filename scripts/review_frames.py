"""Frames and data for tools/tool_review.html (3 mm tool swap review).

Usage:
    python scripts/review_frames.py

For each 3 mm candidate (results/tools/<video>_candidates.csv) we save a strip of
left-eye frames around the candidate time, so a person can see whether a tool
left and a different one came back.

Also makes contact sheets (one frame every SHEET_STEP seconds) for scanning the
stretches between candidates, where the rosbag evidence may have missed a swap.

Output, in results/review/:
    frames/<video>/<candidate>_<offset>.jpg
    sheets/<video>_<nn>.jpg
    review_data.js   (loaded by the page; a .js file so it works when opened from disk)
"""

import json
import subprocess
from pathlib import Path

import pandas as pd

from bagio import SYSTEM_BY_BAG

VIDEO_DIR = Path("data/video")
TOOLS_DIR = Path("results/tools")
OUT_DIR = Path("results/review")
SYNC_FILE = Path("results/sync/offsets.csv")
OFFSETS = [-40, -15, 0, 15, 40, 80]  # s around the candidate
LEFT_EYE = "crop=960:1040:0:40"
FRAME_WIDTH = 960  # full left-eye width, so frames stay sharp when enlarged
SHEET_WIDTH = 320  # contact-sheet tiles stay small
SHEET_STEP = 20  # s
SHEET_TILE = "6x6"


def save_frame(video, t, path):
    filters = f"{LEFT_EYE},scale={FRAME_WIDTH}:-1"
    command = ["ffmpeg", "-v", "error", "-y", "-ss", str(max(t, 0)), "-i", str(video),
               "-frames:v", "1", "-vf", filters, "-q:v", "3", str(path)]
    subprocess.run(command, check=True)


def save_sheets(video):
    """Contact sheets need a full pass through the video, so existing ones are kept."""
    existing = sorted(p.name for p in (OUT_DIR / "sheets").glob(f"{video.stem}_*.jpg"))
    if existing:
        return existing
    label = "drawtext=text='%{pts\\:hms}':fontcolor=yellow:fontsize=22:x=4:y=4:box=1:boxcolor=black@0.5"
    filters = f"fps=1/{SHEET_STEP},{LEFT_EYE},scale={SHEET_WIDTH}:-1,{label},tile={SHEET_TILE}"
    out = OUT_DIR / "sheets" / f"{video.stem}_%02d.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", filters, "-q:v", "4", str(out)], check=True)
    return sorted(p.name for p in (OUT_DIR / "sheets").glob(f"{video.stem}_*.jpg"))


def candidate_record(video, index, row):
    folder = OUT_DIR / "frames" / video.stem
    frames = []
    for offset in OFFSETS:
        path = folder / f"{index:03d}_{offset:+d}.jpg"
        save_frame(video, row.t_video + offset, path)
        frames.append({"offset": offset, "src": f"../results/review/frames/{video.stem}/{path.name}"})
    return {"id": f"{video.stem}#{index}", "video": video.name, "arm": row.arm, "t_video": row.t_video,
            "t_bag": row.t_bag, "score": int(row.score), "evidence": row.evidence, "frames": frames}


def video_record(video):
    (OUT_DIR / "frames" / video.stem).mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(TOOLS_DIR / f"{video.stem}_candidates.csv")
    candidates = [candidate_record(video, i, row) for i, row in enumerate(table.itertuples())]
    sheets = [f"../results/review/sheets/{name}" for name in save_sheets(video)]
    print(f"{video.stem}: {len(candidates)} candidates, {len(sheets)} sheets", flush=True)
    return {"video": video.name, "candidates": candidates, "sheets": sheets, "sheet_step": SHEET_STEP}


def videos_3mm():
    sync = pd.read_csv(SYNC_FILE)
    return [VIDEO_DIR / f"{row.video}.mp4" for row in sync.itertuples() if SYSTEM_BY_BAG[row.bag] == "3mm"]


def main():
    (OUT_DIR / "sheets").mkdir(parents=True, exist_ok=True)
    data = [video_record(video) for video in videos_3mm()]
    text = "// Written by scripts/review_frames.py\nconst REVIEW_DATA = " + json.dumps(data, indent=1) + ";\n"
    (OUT_DIR / "review_data.js").write_text(text)


if __name__ == "__main__":
    main()
