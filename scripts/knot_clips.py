"""Short sped-up clips of every knot-tying window, for counting throws by eye in tools/knot_count.html.

Usage:
    python scripts/knot_clips.py

Needs results/sutures/stitches.csv (scripts/suture_times.py). For each completed stitch, cuts the
knot-tying window (needle through to knot tightened, plus PAD seconds each side) from the left eye,
at SPEED times speed, with a label in the corner.

Output, in results/sutures/knot_clips/ (regenerable, not in git):
    <pig>_<block>_<number>.mp4
    clips.js   list of clips, loaded by tools/knot_count.html
"""

import json
import subprocess
from pathlib import Path

import pandas as pd

VIDEO_DIR = Path("data/video")
STITCHES = Path("results/sutures/stitches.csv")
OUT_DIR = Path("results/sutures/knot_clips")
PAD = 2  # s before and after the knot-tying window
SPEED = 3
WIDTH = 480
LEFT_EYE = "crop=960:1040:0:40"
MONTHS = {"may": "May", "jun": "Jun", "aug": "Aug", "oct": "Oct"}


def pig_of(video):
    return video.split("_")[1][:5]  # 'pig_oct08-2026-...' -> 'oct08'


def pig_label(pig):
    return f"{MONTHS[pig[:3]]} {int(pig[3:])}"


def cut_clip(video, start, duration, label, path):
    text = label.replace(":", "\\:")
    filters = (f"{LEFT_EYE},scale={WIDTH}:-2,setpts=PTS/{SPEED},"
               f"drawtext=text='{text}':fontcolor=white:fontsize=18:x=6:y=6:box=1:boxcolor=black@0.5")
    command = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{duration:.2f}",
               "-i", str(VIDEO_DIR / f"{video}.mp4"), "-vf", filters, "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(command, check=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stitches = pd.read_csv(STITCHES)
    stitches = stitches[~stitches.failed & stitches.knot_s.notna()]
    clips = []
    for s in stitches.itertuples():
        pig, block = pig_of(s.video), s.block
        knot_start = s.start_s + s.bite_s
        name = f"{pig}_{block}_{s.number}.mp4"
        label = f"{pig_label(pig)} - {block.replace('_', ' ')} {s.number} - {SPEED}x"
        cut_clip(s.video, knot_start - PAD, s.knot_s + 2 * PAD, label, OUT_DIR / name)
        clips.append({"id": f"{pig}_{block}_{s.number}", "video": s.video, "pig": pig_label(pig), "block": block,
                      "number": int(s.number), "knot_start_s": round(knot_start, 1), "knot_s": round(s.knot_s, 1),
                      "src": f"../results/sutures/knot_clips/{name}"})
        print(name, flush=True)
    text = "// Written by scripts/knot_clips.py\nconst KNOT_CLIPS = " + json.dumps(clips, indent=1) + ";\n"
    (OUT_DIR / "clips.js").write_text(text)
    print(f"{len(clips)} clips")


if __name__ == "__main__":
    main()
