"""Find the time offset between each video and its rosbag.

Usage:
    python scripts/sync_video.py

Needs data/derived/<bag>/psm*.parquet (extract_joints.py) and
data/derived/video/<video>.parquet (video_motion.py).

Method: both files are named by their start clock time, which gives a rough offset.
The robot and the screen recorder ran on different clocks, so we refine it by
cross-correlating tool activity in the bag (joint motion) with image motion in the
video, searching SEARCH seconds around the rough offset.

    video time = bag time + offset

Output: results/sync/offsets.csv
    bag, video, rough_offset, offset, peak (correlation at best offset),
    offset_first_half, offset_second_half (should agree with offset; a gap means drift)
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import correlate

from bagio import DERIVED_DIR, SYSTEM_BY_BAG

VIDEO_DIR = Path("data/video")
MOTION_DIR = DERIVED_DIR / "video"
OUTPUT = Path("results/sync/offsets.csv")
STEP = 0.1  # s, both signals are resampled to this grid (matches video_motion FPS)
SEARCH = 900  # s, search this far either side of the rough offset
INSERTION_SCALE = 10  # insertion is in m; scale so 1 cm counts like 0.1 rad


def bag_clock(bag):
    return datetime.strptime(bag, "%Y-%m-%d-%H-%M-%S")


def video_clock(video):
    """'pig_jun16-2026-06-16_09.57.53' -> datetime."""
    return datetime.strptime(video.split("-", 1)[1], "%Y-%m-%d_%H.%M.%S")


def video_for_bag(bag):
    day = bag[:10]
    matches = [p.stem for p in VIDEO_DIR.glob(f"*{day}*.mp4")]
    return matches[0] if matches else None


def binned(t, values, length):
    """Sum values into STEP-wide bins starting at 0."""
    bins = (t / STEP).astype(int)
    keep = (bins >= 0) & (bins < length)
    return np.bincount(bins[keep], weights=values[keep], minlength=length)


def arm_activity(bag, arm, length):
    d = pd.read_parquet(DERIVED_DIR / bag / f"{arm}.parquet")
    columns = [c for c in d.columns if c.startswith("pos_") and c != "pos_jaw"]
    step = d[columns].diff().abs().fillna(0)
    step["pos_outer_insertion"] *= INSERTION_SCALE
    return binned(d.t.to_numpy(), step.sum(axis=1).to_numpy(), length)


def bag_activity(bag):
    duration = pd.read_parquet(DERIVED_DIR / bag / "psm1.parquet", columns=["t"]).t.max()
    length = int(duration / STEP) + 1
    return arm_activity(bag, "psm1", length) + arm_activity(bag, "psm2", length)


def normalise(signal):
    """Log-compress spikes, then zero mean and unit variance."""
    s = np.log1p(signal / (np.median(signal) + 1e-9))
    return (s - s.mean()) / (s.std() + 1e-9)


def best_offset(bag_signal, video_signal, rough):
    """Offset (s) maximising correlation, within SEARCH of rough. Returns (offset, peak)."""
    a, b = normalise(bag_signal), normalise(video_signal)
    corr = correlate(b, a, mode="full", method="fft") / min(len(a), len(b))
    lags = (np.arange(len(corr)) - (len(a) - 1)) * STEP
    window = np.abs(lags - rough) <= SEARCH
    best = np.argmax(np.where(window, corr, -np.inf))
    return round(lags[best], 1), round(corr[best], 3)


def half_offsets(bag_signal, video_signal, offset):
    """Sync each half of the bag separately, to check for drift."""
    middle = len(bag_signal) // 2
    first, _ = best_offset(bag_signal[:middle], video_signal, offset)
    shift = middle * STEP
    second, _ = best_offset(bag_signal[middle:], video_signal, offset + shift)
    return first, round(second - shift, 1)


def sync_row(bag):
    video = video_for_bag(bag)
    rough = (bag_clock(bag) - video_clock(video)).total_seconds()
    bag_signal = bag_activity(bag)
    video_signal = pd.read_parquet(MOTION_DIR / f"{video}.parquet").motion.to_numpy()
    offset, peak = best_offset(bag_signal, video_signal, rough)
    first, second = half_offsets(bag_signal, video_signal, offset)
    return {"bag": bag, "video": video, "rough_offset": rough, "offset": offset, "peak": peak,
            "offset_first_half": first, "offset_second_half": second}


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = [sync_row(bag) for bag in SYSTEM_BY_BAG]
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT, index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
