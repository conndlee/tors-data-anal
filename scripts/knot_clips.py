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

from project import LEFT_EYE, VIDEO_DIR, pig_tag, short_name

STITCHES = Path("results/sutures/stitches.csv")
OUT_DIR = Path("results/sutures/knot_clips")
PAD = 2  # s before and after the knot-tying window
SPEED = 3
WIDTH = 480


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
        pig, block = pig_tag(s.video), s.block
        knot_start = s.start_s + s.bite_s
        name = f"{pig}_{block}_{s.number}.mp4"
        label = f"{short_name(s.video)} - {block.replace('_', ' ')} {s.number} - {SPEED}x"
        cut_clip(s.video, knot_start - PAD, s.knot_s + 2 * PAD, label, OUT_DIR / name)
        clips.append({"id": f"{pig}_{block}_{s.number}", "video": s.video, "pig": short_name(s.video), "block": block,
                      "number": int(s.number), "knot_start_s": round(knot_start, 1), "knot_s": round(s.knot_s, 1),
                      "src": f"../results/sutures/knot_clips/{name}"})
        print(name, flush=True)
    text = "// Written by scripts/knot_clips.py\nconst KNOT_CLIPS = " + json.dumps(clips, indent=1) + ";\n"
    (OUT_DIR / "clips.js").write_text(text)
    print(f"{len(clips)} clips")


if __name__ == "__main__":
    main()
