"""Fit the tool tip lengths in each 30 s window, to see which tool type was mounted.

Only works for bags that logged /PSM*/measured_cp (of the 3 mm bags, only 2026-06-16).
The tip is the end of the wrist plus two lengths: the wrist link "A" and the tip offset "z".
Different 3 mm tools have different lengths, so a change in the best fit marks a tool change.

Usage:
    python scripts/tip_type_windows.py [bag]

Output: data/derived/<bag>/tip_type_windows.csv
    arm, t (window start, s since bag start), a_mm, z_mm, err_mm (median fit error), type
    type: "long" (z >= LONG_TIP mm, grasper-like) or "short" (tip close to the wrist)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import check_tool_file as fk

A_VALUES = np.arange(0, 0.0101, 0.001)
Z_VALUES = np.arange(0, 0.0121, 0.001)
MAX_ERROR = 0.5  # mm, windows fitting worse than this are dropped
LONG_TIP = 4  # mm


def tip_parts(joints, q_row, rule):
    """Tip = p + a * u + z * v. Returns p, u, v for one joint vector (a = z = 0 in joints)."""
    frame = np.eye(4)
    for joint, q in zip(joints[:5], q_row[:5]):
        frame = frame @ fk.joint_transform(joint, q, rule)
    u = (frame @ fk.dh_modified(joints[5]["alpha"], 0, 0, 0))[:3, 0]
    frame = frame @ fk.joint_transform(joints[5], q_row[5], rule)
    return frame[:3, 3], u, frame[:3, 1]  # the tip offset runs along frame 6's y axis


def best_lengths(p, u, v, logged):
    """Grid search a and z; returns (error mm, a m, z m)."""
    best = (np.inf, 0.0, 0.0)
    for a in A_VALUES:
        for z in Z_VALUES:
            points = p + a * u + z * v
            rotation, shift = fk.fit_rigid(points, logged)
            error = np.median(np.linalg.norm(points @ rotation.T + shift - logged, axis=1)) * 1000
            best = min(best, (error, a, z))
    return best


def arm_windows(bag, arm, joints, rule):
    matched = fk.match_joints(fk.read_logged_poses(bag, arm), bag, arm)
    q = matched[[f"pos_{name}" for name in fk.JOINTS]].to_numpy()
    p, u, v = (np.array(part) for part in zip(*[tip_parts(joints, row, rule) for row in q]))
    logged = matched[["x", "y", "z"]].to_numpy()
    window_ids = np.floor(matched.t.to_numpy() / fk.WINDOW)
    rows = []
    for window in np.unique(window_ids):
        keep = window_ids == window
        if keep.sum() < fk.MIN_POSES or np.ptp(logged[keep], axis=0).max() < fk.MIN_SPREAD:
            continue
        error, a, z = best_lengths(p[keep], u[keep], v[keep], logged[keep])
        rows.append({"arm": arm, "t": window * fk.WINDOW, "a_mm": a * 1000, "z_mm": z * 1000, "err_mm": round(error, 3)})
    return rows


def main():
    tool = fk.load_tool_file(fk.TOOL_FILE)
    bag = Path(sys.argv[1]) if len(sys.argv) > 1 else fk.BAG
    joints = fk.ARM_DH + [dict(joint) for joint in tool["DH"]["joints"]]
    joints[5]["A"] = 0.0
    rule = fk.ANGLE_RULES["q + offset"]
    rows = [row for arm in fk.ARMS for row in arm_windows(bag, arm, joints, rule)]
    table = pd.DataFrame(rows).query("err_mm < @MAX_ERROR")
    table["type"] = np.where(table.z_mm >= LONG_TIP, "long", "short")
    table.to_csv(fk.DERIVED_DIR / bag.stem / "tip_type_windows.csv", index=False)
    print(table.groupby(["arm", "type"]).size().to_string())


if __name__ == "__main__":
    main()
