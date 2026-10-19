"""Convert tool-swap candidates into a CSV the video annotator can import.

Usage:
    python scripts/candidates_to_annotator.py [min_score]

Reads results/tools/<video>_candidates.csv (scripts/tool_candidates.py) and writes
results/tools/<video>_candidates_annotator.csv: one "tool_check" point per candidate
at its video time, with the arm, score and rosbag evidence in the note.
Candidates scoring below min_score (default 2) are left out.

Import it with "Import CSV" in tools/annotator.html; it adds to existing marks.
To record a decision, mark the real swap with key t (tool_change), or use tools/tool_review.html.
"""

import sys
from pathlib import Path

import pandas as pd

TOOLS_DIR = Path("results/tools")
CSV_COLUMNS = ["video", "event", "start_s", "end_s", "duration_s", "note"]


def convert(path, min_score):
    candidates = pd.read_csv(path).query("score >= @min_score")
    table = pd.DataFrame({
        "video": candidates.video,
        "event": "tool_check",
        "start_s": candidates.t_video,
        "end_s": candidates.t_video,
        "duration_s": 0.0,
        "note": candidates.arm + " candidate, score " + candidates.score.astype(str) + ": " + candidates.evidence,
    })
    out = path.with_name(path.stem + "_annotator.csv")
    table[CSV_COLUMNS].to_csv(out, index=False)
    return out, len(table)


def main():
    min_score = float(sys.argv[1]) if len(sys.argv) > 1 else 2
    for path in sorted(TOOLS_DIR.glob("*_candidates.csv")):
        out, count = convert(path, min_score)
        print(f"{out}: {count} candidates")


if __name__ == "__main__":
    main()
