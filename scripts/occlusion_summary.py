"""Summarise instrument occlusion per video segment and per tool system.

Usage:
    python scripts/occlusion_summary.py

Needs data/derived/occlusion/video/<video>.parquet (scripts/occlusion.py) and
results/occlusion/segments.csv (hand-made: which system was used when, and which
trials are pilots; an empty end_s means "to the end of the video").

Frames darker than DARK (recorder left running) are dropped.
"In view" frames are those with at least IN_VIEW of the image covered, so
stretches with the instruments out of the picture (e.g. tool swaps) can be left out.

Output:
    results/occlusion/summary_by_segment.csv   one row per video segment
    results/occlusion/summary_by_system.csv    per system: median and range of the segment medians
"""

from pathlib import Path

import numpy as np
import pandas as pd

OCCLUSION_DIR = Path("data/derived/occlusion/video")
RESULT_DIR = Path("results/occlusion")
DARK = 20  # mean grey level (0-255); black frames are near 0
IN_VIEW = 0.01  # share of the image
TRIAL_SETS = {"main trials": ["main"], "main + pilots": ["main", "pilot"]}


def load_segments():
    segments = pd.read_csv(RESULT_DIR / "segments.csv")
    segments["end_s"] = segments.end_s.fillna(np.inf)
    return segments


def segment_frames(segment):
    frames = pd.read_parquet(OCCLUSION_DIR / f"{segment.video}.parquet")
    inside = (frames.t_video >= segment.start_s) & (frames.t_video < segment.end_s)
    return frames[inside]


def segment_row(segment):
    frames = segment_frames(segment)
    lit = frames[frames.brightness >= DARK]
    in_view = lit[lit.occlusion >= IN_VIEW]
    return {
        "video": segment.video, "system": segment.system, "trial": segment.trial,
        "start_s": segment.start_s, "end_s": segment.end_s,
        "frames": len(frames), "dark_dropped": len(frames) - len(lit),
        "share_in_view": round(len(in_view) / max(len(lit), 1), 3),
        "median": lit.occlusion.median(), "p25": lit.occlusion.quantile(0.25),
        "p75": lit.occlusion.quantile(0.75), "mean": lit.occlusion.mean(),
        "median_in_view": in_view.occlusion.median(),
    }


def system_rows(by_segment):
    rows = []
    for name, trials in TRIAL_SETS.items():
        chosen = by_segment[by_segment.trial.isin(trials)]
        for system, group in chosen.groupby("system"):
            rows.append({
                "trials": name, "system": system, "segments": len(group),
                "median": group["median"].median(), "min": group["median"].min(), "max": group["median"].max(),
                "median_in_view": group.median_in_view.median(),
                "min_in_view": group.median_in_view.min(), "max_in_view": group.median_in_view.max(),
            })
    return pd.DataFrame(rows)


def main():
    by_segment = pd.DataFrame([segment_row(s) for s in load_segments().itertuples()])
    by_system = system_rows(by_segment)
    by_segment.round(4).to_csv(RESULT_DIR / "summary_by_segment.csv", index=False)
    by_system.round(4).to_csv(RESULT_DIR / "summary_by_system.csv", index=False)
    columns = ["video", "system", "trial", "frames", "dark_dropped", "share_in_view", "median", "median_in_view"]
    print(by_segment[columns].round(3).to_string(index=False), "\n")
    print(by_system.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
