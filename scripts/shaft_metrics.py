"""Shaft-level metrics for each arm in each bag. No tool kinematics needed.

The "wrist point" is the end of the shaft. It comes from the first three arm joints only:
yaw and pitch about the remote center of motion (RCM), and insertion depth.
These joints are the same hardware for the 3 mm and 8 mm tools, so the numbers are comparable.
Positions are relative to the RCM, so inaccurate base frames do not matter.

Usage:
    python scripts/shaft_metrics.py

Reads data/derived/<bag>/ (from extract_joints.py). Writes results/shaft/metrics.csv.

Caveat: this uses the whole recording, including setup and tool changes.
Once the videos are annotated, compute the same metrics per procedure step instead.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull

from bagio import DERIVED_DIR, SYSTEM_BY_BAG

GAP_S = 0.5            # longer than this between samples = recording gap, not motion
JAW_CLOSED_RAD = 0.1   # jaw angle below this counts as closed
JAW_OPEN_RAD = 0.3     # jaw angle above this counts as open
ARMS = ["psm1", "psm2"]
OUTPUT = "results/shaft/metrics.csv"


# ---------- geometry ----------

def wrist_point(psm):
    """Wrist point (m) in the RCM frame, from yaw, pitch and insertion."""
    yaw = psm["pos_outer_yaw"].to_numpy()
    pitch = psm["pos_outer_pitch"].to_numpy()
    depth = psm["pos_outer_insertion"].to_numpy()
    direction = np.column_stack([np.sin(yaw) * np.cos(pitch), -np.sin(pitch), -np.cos(yaw) * np.cos(pitch)])
    return depth[:, None] * direction


def recorded_minutes(t):
    dt = np.diff(t)
    return dt[dt <= GAP_S].sum() / 60


def path_length(points, t):
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    return steps[np.diff(t) <= GAP_S].sum()


def hull_volume(points):
    """Convex hull volume (m^3) of the wrist point, ignoring the outer 1% on each axis."""
    sample = points[::10]
    low, high = np.percentile(sample, [1, 99], axis=0)
    inside = np.all((sample >= low) & (sample <= high), axis=1)
    return ConvexHull(sample[inside]).volume


def spread(values):
    """Width of the middle 90% of values."""
    p5, p95 = np.percentile(values, [5, 95])
    return p95 - p5


# ---------- jaw and effort ----------

def count_grasps(jaw_angle):
    """Count open -> closed transitions, with a dead band so jitter is not counted."""
    state = pd.Series(np.select([jaw_angle < JAW_CLOSED_RAD, jaw_angle > JAW_OPEN_RAD], [0.0, 1.0], np.nan)).ffill()
    return int(((state.shift() == 1) & (state == 0)).sum())


def effort_stats(psm):
    """Raw effort on the three arm joints (Nm for yaw/pitch, N for insertion).
    Includes gravity and friction, so treat as a first look, not as tissue force."""
    stats = {}
    for joint in ["yaw", "pitch", "insertion"]:
        effort = psm[f"eff_outer_{joint}"].abs()
        stats[f"eff_{joint}_p95"] = effort.quantile(0.95)
        stats[f"eff_{joint}_max"] = effort.max()
    return stats


# ---------- per arm ----------

def arm_metrics(psm, jaw):
    t = psm["t"].to_numpy()
    points = wrist_point(psm)
    minutes = recorded_minutes(t)
    path = path_length(points, t)
    grasps = count_grasps(jaw["pos_jaw"].to_numpy())
    return {
        "recorded_min": minutes,
        "path_m": path,
        "path_m_per_min": path / minutes,
        "insertion_p5_mm": np.percentile(psm["pos_outer_insertion"], 5) * 1000,
        "insertion_p95_mm": np.percentile(psm["pos_outer_insertion"], 95) * 1000,
        "yaw_spread_deg": np.degrees(spread(psm["pos_outer_yaw"])),
        "pitch_spread_deg": np.degrees(spread(psm["pos_outer_pitch"])),
        "hull_cm3": hull_volume(points) * 1e6,
        "grasps": grasps,
        "grasps_per_min": grasps / minutes,
        **effort_stats(psm),
    }


def bag_rows(bag, system):
    folder = DERIVED_DIR / bag
    rows = []
    for arm in ARMS:
        psm = pd.read_parquet(folder / f"{arm}.parquet")
        jaw = pd.read_parquet(folder / f"{arm}_jaw.parquet")
        rows.append({"bag": bag, "system": system, "arm": arm, **arm_metrics(psm, jaw)})
    return rows


def main():
    # tool_changes.csv is written last by extract_joints.py, so it marks a finished extraction
    bags = [(bag, system) for bag, system in SYSTEM_BY_BAG.items() if (DERIVED_DIR / bag / "tool_changes.csv").exists()]
    rows = [row for bag, system in bags for row in bag_rows(bag, system)]
    table = pd.DataFrame(rows)
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT, index=False)
    print(table.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
