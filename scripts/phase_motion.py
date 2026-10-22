"""Instrument motion during the bite and knot tying phases of each stitch, 3 mm vs 8 mm.

Usage:
    python scripts/phase_motion.py

Needs results/sutures/stitches.csv (scripts/suture_times.py), results/sync/offsets.csv and the joint tables
in data/derived/<bag>/ (scripts/extract_joints.py). Videos without a rosbag (May 29) are left out.

Phases: bite = needle first touches tissue -> needle through; knot tying = needle through -> knot tightened.
Both instruments are summed. All measures use joints that are the same kind on both systems:
    shaft_mm     path of the shaft end (wrist point), from arm yaw, pitch and the wrist depth below the pivot
                 (insertion joint corrected for each system's tool shaft length)
    roll_rad     wrist roll rotation
    wrist_rad    wrist pitch + wrist yaw rotation
    grasps       jaw closures (open -> closed, with a dead band)
    idle_s       time with both instruments still
Each is given absolute (per phase) and normalised by the phase duration (per minute; idle as % of the phase).
Workspace, per instrument, from the shaft-end positions (both instruments added for volumes):
    volume_cm3     convex hull volume over the whole phase
    volume60_cm3   convex hull volume over the first WORKSPACE_S seconds (removes the effect of phase length;
                   phases shorter than that are left out)
    spread_mm      mean distance from the instrument's own centre during the phase, averaged over instruments
Signals are averaged into BIN_S bins first, so sensor jitter is not counted as motion.

Output, in results/sutures/motion/:
    phases.csv     one row per stitch x phase
    by_pig.csv     medians per case and phase
    motion.md      per-system median (IQR) tables, absolute and per minute
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, QhullError

from project import DERIVED_DIR, SYNC_FILE, SYSTEM_NAMES, case_id, pig_order, system_by_video

STITCHES = Path("results/sutures/stitches.csv")
NO_ROSBAG = "pig_may29-2026-05-29_09.34.18"  # recording without a rosbag (P01)
OUT_DIR = Path("results/sutures/motion")
ARMS = ["psm1", "psm2"]
SYSTEMS = ["3mm", "8mm"]
BIN_S = 0.05  # s
WORKSPACE_S = 60  # s, window for the fixed-length workspace volume
JAW_CLOSED, JAW_OPEN = 0.1, 0.3  # rad; closing below CLOSED after being above OPEN counts as a grasp
STILL_MM_S = 2  # mm/s, shaft-end speed below this counts as still
STILL_RAD_S = 0.1  # rad/s, wrist speed (roll + pitch + yaw) below this counts as still
INSERTION_OFFSET_M = -0.4318  # dVRK PSM insertion joint offset
# Tool shaft length D (pivot-side DH value of the roll joint): 3 mm from the validated grasper file
# (data/tools/3MM_GRASPER_420020.json), 8 mm from the standard large needle driver file.
TOOL_LENGTH_M = {"3mm": 0.363, "8mm": 0.4162}
JOINTS = ["outer_yaw", "outer_pitch", "outer_insertion", "outer_roll", "outer_wrist_pitch", "outer_wrist_yaw"]
MEASURES = {"shaft_mm": ("Shaft motion", "mm", "mm/min"), "roll_rad": ("Roll", "rad", "rad/min"),
            "wrist_rad": ("Wrist pitch + yaw", "rad", "rad/min"), "grasps": ("Grasps", "count", "per min"),
            "idle_s": ("Idle (both still)", "s", "% of phase")}
PHASES = {"bite": "Bite", "knot": "Knot tying"}
WORKSPACE = {"volume_cm3": "Workspace volume, whole phase (cm³)",
             "volume60_cm3": f"Workspace volume, first {WORKSPACE_S} s (cm³)",
             "spread_mm": "Spread around own centre (mm)"}


# ---------- signals ----------

def wrist_point_mm(d, system):
    """Shaft end in the remote-centre frame (mm), from yaw, pitch and the depth of the wrist below the pivot.

    The insertion joint is not the depth: the dVRK puts the wrist at insertion - 0.4318 m + the tool's shaft
    length D, and D differs between the 3 mm and 8 mm instruments."""
    depth = (d.pos_outer_insertion + INSERTION_OFFSET_M + TOOL_LENGTH_M[system]) * 1000
    yaw, pitch = d.pos_outer_yaw, d.pos_outer_pitch
    return np.column_stack([np.sin(yaw) * np.cos(pitch), -np.sin(pitch), -np.cos(yaw) * np.cos(pitch)]) * depth.to_numpy()[:, None]


def arm_signals(bag, arm, system):
    """Per BIN_S bin: shaft step (mm), roll step, wrist step (rad), and grasp events, indexed by bag time."""
    d = pd.read_parquet(DERIVED_DIR / bag / f"{arm}.parquet", columns=["t"] + [f"pos_{j}" for j in JOINTS]).dropna()
    d = d.groupby((d.t / BIN_S).astype(int)).mean()
    out = pd.DataFrame(index=d.index * BIN_S)
    points = wrist_point_mm(d, system)
    out[["x", "y", "z"]] = points
    out["shaft_mm"] = np.r_[0, np.linalg.norm(np.diff(points, axis=0), axis=1)]
    out["roll_rad"] = d.pos_outer_roll.diff().abs().fillna(0).to_numpy()
    out["wrist_rad"] = (d.pos_outer_wrist_pitch.diff().abs() + d.pos_outer_wrist_yaw.diff().abs()).fillna(0).to_numpy()
    out["grasps"] = grasp_events(bag, arm).reindex(d.index, fill_value=0).to_numpy()
    out["still"] = (out.shaft_mm / BIN_S < STILL_MM_S) & ((out.roll_rad + out.wrist_rad) / BIN_S < STILL_RAD_S)
    return out


def grasp_events(bag, arm):
    """Jaw closures per BIN_S bin."""
    jaw = pd.read_parquet(DERIVED_DIR / bag / f"{arm}_jaw.parquet").dropna()
    state = pd.Series(np.select([jaw.pos_jaw < JAW_CLOSED, jaw.pos_jaw > JAW_OPEN], [0.0, 1.0], np.nan)).ffill()
    closes = ((state.shift() == 1) & (state == 0)).astype(int).to_numpy()
    return pd.Series(closes).groupby((jaw.t.to_numpy() / BIN_S).astype(int)).sum()


def both_arms(bag, system):
    """Both instruments: motion summed, still only when both are still."""
    arms = [arm_signals(bag, arm, system) for arm in ARMS]
    joined = arms[0].join(arms[1], how="inner", lsuffix="_1", rsuffix="_2")
    out = pd.DataFrame(index=joined.index)
    for measure in ["shaft_mm", "roll_rad", "wrist_rad", "grasps"]:
        out[measure] = joined[f"{measure}_1"] + joined[f"{measure}_2"]
    out["idle_s"] = (joined.still_1 & joined.still_2) * BIN_S
    for arm in ["1", "2"]:
        out[[f"x{arm}", f"y{arm}", f"z{arm}"]] = joined[[f"x_{arm}", f"y_{arm}", f"z_{arm}"]].to_numpy()
    return out


# ---------- workspace ----------

def hull_cm3(points):
    """Convex hull volume of shaft-end positions (mm) in cm³; 0 if there are too few or flat points."""
    try:
        return ConvexHull(points).volume / 1000
    except (QhullError, ValueError):
        return 0.0


def spread_mm(points):
    return np.linalg.norm(points - points.mean(axis=0), axis=1).mean()


def workspace(window):
    """Workspace measures for one phase window (both instruments)."""
    arms = [window[[f"x{a}", f"y{a}", f"z{a}"]].to_numpy() for a in ("1", "2")]
    first = window[window.index < window.index.min() + WORKSPACE_S]
    long_enough = window.index.max() - window.index.min() >= WORKSPACE_S - BIN_S
    first_arms = [first[[f"x{a}", f"y{a}", f"z{a}"]].to_numpy() for a in ("1", "2")]
    return {"volume_cm3": sum(hull_cm3(p) for p in arms),
            "volume60_cm3": sum(hull_cm3(p) for p in first_arms) if long_enough else np.nan,
            "spread_mm": np.mean([spread_mm(p) for p in arms])}


# ---------- per phase ----------

def phase_windows(s):
    needle = s.start_s + s.bite_s
    return {"bite": (s.start_s, needle), "knot": (needle, s.end_s)}


def phase_rows(stitches, video, bag, offset, system):
    signals = both_arms(bag, system)
    rows = []
    for s in stitches.itertuples():
        for phase, (start, end) in phase_windows(s).items():
            window = signals[(signals.index >= start - offset) & (signals.index < end - offset)]
            totals = window[list(MEASURES)].sum().to_dict()
            rows.append({"video": video, "block": s.block, "number": s.number, "phase": phase,
                         "duration_s": end - start, **totals, **workspace(window)})
    return rows


def phase_table():
    stitches = pd.read_csv(STITCHES)
    stitches = stitches[~stitches.failed & stitches.knot_s.notna()]
    sync = pd.read_csv(SYNC_FILE).set_index("video")
    systems = system_by_video()
    rows = []
    for video, own in stitches.groupby("video"):
        if video in sync.index:  # May 29 has no rosbag
            rows += phase_rows(own, video, sync.loc[video, "bag"], sync.loc[video, "offset"], systems[video])
    table = pd.DataFrame(rows)
    table["system"] = table.video.map(system_by_video())
    table["case"] = table.video.map(case_id)
    return normalise(table[table.system.isin(SYSTEMS)])


def normalise(table):
    minutes = table.duration_s / 60
    for measure in ["shaft_mm", "roll_rad", "wrist_rad", "grasps"]:
        table[f"{measure}_per_min"] = table[measure] / minutes
    table["idle_s_per_min"] = 100 * table.idle_s / table.duration_s  # % of the phase
    return table


# ---------- summaries ----------

def iqr(values):
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    fmt = "{:.1f}" if abs(median) < 10 else "{:.0f}"
    return f"{fmt.format(median)} ({fmt.format(q1)}-{fmt.format(q3)})"


def system_lines(table, suffix):
    """One table: measure rows, columns per phase and system, median (IQR) over stitches."""
    header = "| measure | " + " | ".join(f"{PHASES[p]}, {SYSTEM_NAMES[s]}" for p in PHASES for s in SYSTEMS) + " |"
    lines = [header, "|" + "---|" * (1 + len(PHASES) * len(SYSTEMS))]
    for measure, (name, absolute, per_min) in MEASURES.items():
        unit = absolute if suffix == "" else per_min
        cells = [iqr(table[(table.phase == p) & (table.system == s)][measure + suffix]) for p in PHASES for s in SYSTEMS]
        lines.append(f"| {name} ({unit}) | " + " | ".join(cells) + " |")
    return lines


def workspace_lines(table):
    header = "| measure | " + " | ".join(f"{PHASES[p]}, {SYSTEM_NAMES[s]}" for p in PHASES for s in SYSTEMS) + " |"
    lines = [header, "|" + "---|" * (1 + len(PHASES) * len(SYSTEMS))]
    for measure, name in WORKSPACE.items():
        cells = []
        for p in PHASES:
            for s in SYSTEMS:
                values = table[(table.phase == p) & (table.system == s)][measure].dropna()
                cells.append(f"{iqr(values)} [n={len(values)}]" if len(values) else "–")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return lines


def by_pig(table):
    columns = ["duration_s"] + [m + suffix for m in MEASURES for suffix in ("", "_per_min")] + list(WORKSPACE)
    pigs = table.groupby(["system", "video", "case", "phase"])[columns].median().reset_index()
    systems = system_by_video()
    order = sorted(range(len(pigs)), key=lambda i: (pig_order(pigs.video.iloc[i], systems), pigs.phase.iloc[i]))
    return pigs.iloc[order]


def pig_lines(pigs, suffix):
    header = "| case | phase | duration (s) | " + " | ".join(MEASURES[m][0] for m in MEASURES) + " |"
    lines = [header, "|" + "---|" * (3 + len(MEASURES))]
    for r in pigs.itertuples():
        values = [getattr(r, m + suffix) for m in MEASURES]
        cells = [f"{v:.1f}" if abs(v) < 10 else f"{v:.0f}" for v in values]
        lines.append(f"| {r.case}, {SYSTEM_NAMES[r.system]} | {PHASES[r.phase]} | {r.duration_s:.0f} | " + " | ".join(cells) + " |")
    return lines


def markdown(table, pigs):
    counts = table[table.phase == "bite"].groupby("system").agg(stitches=("case", "size"), pigs=("case", "nunique"))
    lines = ["# Instrument motion per stitch phase", "",
             "Written by `scripts/phase_motion.py`. Both instruments summed; joints that are the same kind on both "
             "systems. Median (interquartile range) over stitches. " +
             "; ".join(f"{SYSTEM_NAMES[s]}: {r.stitches} stitches, {r.pigs} pigs" for s, r in counts.iterrows()) +
             f". {case_id(NO_ROSBAG)} has no rosbag.", "",
             "## Absolute (per phase)", ""] + system_lines(table, "")
    lines += ["", "## Normalised by phase duration (per minute; idle as % of the phase)", ""] + system_lines(table, "_per_min")
    lines += ["", "## Workspace (per instrument; volumes of both instruments added)", ""] + workspace_lines(table)
    lines += ["", f"n = phases included; the first-{WORKSPACE_S}-s volume leaves out phases shorter than {WORKSPACE_S} s.",
              "", "## Per case, normalised (medians)", ""] + pig_lines(pigs, "_per_min")
    lines += ["", f"Still: shaft end slower than {STILL_MM_S} mm/s and wrist slower than {STILL_RAD_S} rad/s, for both "
              f"instruments. Grasps: jaw closing below {JAW_CLOSED} rad after opening above {JAW_OPEN} rad.", ""]
    (OUT_DIR / "motion.md").write_text("\n".join(lines))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = phase_table()
    pigs = by_pig(table)
    table.round(3).to_csv(OUT_DIR / "phases.csv", index=False)
    pigs.round(3).to_csv(OUT_DIR / "by_pig.csv", index=False)
    markdown(table, pigs)
    print("\n".join(system_lines(table, "")))
    print()
    print("\n".join(system_lines(table, "_per_min")))
    print()
    print("\n".join(workspace_lines(table)))


if __name__ == "__main__":
    main()
