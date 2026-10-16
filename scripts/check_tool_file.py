"""Check a 3 mm tool file against the tip poses the robot logged live.

The robot logged /PSM*/measured_cp using the real tool file at the time.
We recompute the tip from /PSM*/measured_js with the tool file we have,
then compare. The logged poses are in the camera (ECM) frame, which moves whenever
the camera moves, and the 3 mm bags do not log the camera. So the recording is cut
into short windows and one rigid transform is fitted per window.

Usage:
    python scripts/check_tool_file.py [tool.json] [bag]

Reports the position error (mm) and rotation error (deg) after alignment,
for the wrist point (end of shaft) and for the tool tip, under each way of
reading the outer_roll "theta" and "offset" fields.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

from bagio import DERIVED_DIR, open_bag

TOOL_FILE = Path("data/tools/3MM_GRASPER_420020.json")
BAG = Path("data/rosbags/2026-06-16-09-58-51.bag")
ARMS = ["psm1", "psm2"]
KEEP_EVERY = 10  # deserialize 1 in 10 poses (about 10 per second)
WINDOW = 30  # s, the camera is assumed still within one window
MIN_POSES = 100  # skip windows with fewer matched poses
MIN_SPREAD = 0.01  # m, skip windows where the tip barely moved (fit is not constrained)
MAX_GAP = 0.005  # s, largest allowed time gap between a pose and its joint sample

# Standard dVRK PSM arm joints (modified DH): outer yaw, outer pitch, insertion.
ARM_DH = [
    {"alpha": np.pi / 2, "A": 0.0, "theta": 0.0, "D": 0.0, "offset": np.pi / 2, "type": "revolute"},
    {"alpha": -np.pi / 2, "A": 0.0, "theta": 0.0, "D": 0.0, "offset": -np.pi / 2, "type": "revolute"},
    {"alpha": np.pi / 2, "A": 0.0, "theta": 0.0, "D": 0.0, "offset": -0.4318, "type": "prismatic"},
]
JOINTS = ["outer_yaw", "outer_pitch", "outer_insertion", "outer_roll", "outer_wrist_pitch", "outer_wrist_yaw"]

# Ways to turn a revolute joint value q into the DH angle.
ANGLE_RULES = {
    "q + offset": lambda q, j: q + j["offset"],
    "q + theta + offset": lambda q, j: q + j["theta"] + j["offset"],
    "q + theta": lambda q, j: q + j["theta"],
}


def load_tool_file(path):
    """Read a dVRK tool file, which is JSON with // and /* */ comments."""
    text = path.read_text()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text)


def dh_modified(alpha, a, theta, d):
    """Craig's modified DH: Rx(alpha) Tx(a) Rz(theta) Tz(d)."""
    ca, sa, ct, st = np.cos(alpha), np.sin(alpha), np.cos(theta), np.sin(theta)
    return np.array([
        [ct, -st, 0, a],
        [st * ca, ct * ca, -sa, -d * sa],
        [st * sa, ct * sa, ca, d * ca],
        [0, 0, 0, 1],
    ])


def joint_transform(joint, q, angle_rule):
    if joint["type"] == "prismatic":
        return dh_modified(joint["alpha"], joint["A"], joint["theta"], joint["D"] + q + joint["offset"])
    return dh_modified(joint["alpha"], joint["A"], angle_rule(q, joint), joint["D"])


def forward_kinematics(joints, q_row, angle_rule, tooltip):
    """Return (wrist point frame, tip frame) for one joint vector."""
    frame = np.eye(4)
    for joint, q in zip(joints[:4], q_row[:4]):
        frame = frame @ joint_transform(joint, q, angle_rule)
    wrist = frame.copy()
    for joint, q in zip(joints[4:], q_row[4:]):
        frame = frame @ joint_transform(joint, q, angle_rule)
    return wrist, frame @ tooltip


def read_logged_poses(bag, arm):
    topic = f"/{arm.upper()}/measured_cp"
    rows = []
    with open_bag(bag) as reader:
        start = reader.start_time / 1e9
        connections = [c for c in reader.connections if c.topic == topic]
        for i, (conn, timestamp, raw) in enumerate(reader.messages(connections=connections)):
            if i % KEEP_EVERY:
                continue
            msg = reader.deserialize(raw, conn.msgtype)
            p, o = msg.pose.position, msg.pose.orientation
            rows.append({"t": timestamp / 1e9 - start, "frame_id": msg.header.frame_id,
                         "x": p.x, "y": p.y, "z": p.z, "qx": o.x, "qy": o.y, "qz": o.z, "qw": o.w})
    return pd.DataFrame(rows).sort_values("t", ignore_index=True)


def match_joints(poses, bag, arm):
    joints = pd.read_parquet(DERIVED_DIR / bag.stem / f"{arm}.parquet")
    joints = joints[["t"] + [f"pos_{name}" for name in JOINTS]].dropna()
    matched = pd.merge_asof(poses, joints, on="t", direction="nearest", tolerance=MAX_GAP)
    return matched.dropna(ignore_index=True)


def fit_rigid(source, target):
    """Kabsch: rotation R and translation p so that R @ source + p ~ target."""
    sc, tc = source.mean(axis=0), target.mean(axis=0)
    u, _, vt = np.linalg.svd((source - sc).T @ (target - tc))
    sign = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1, 1, sign]) @ u.T
    return rotation, tc - rotation @ sc


def compare(computed, logged):
    """Position error (mm) and rotation error (deg) after one rigid alignment."""
    rotation, shift = fit_rigid(computed[:, :3, 3], logged[:, :3, 3])
    position_error = np.linalg.norm(computed[:, :3, 3] @ rotation.T + shift - logged[:, :3, 3], axis=1) * 1000
    aligned = Rotation.from_matrix(rotation @ computed[:, :3, :3])
    angle_error = np.degrees((aligned.inv() * Rotation.from_matrix(logged[:, :3, :3])).magnitude())
    return position_error, angle_error


def compare_windows(computed, logged, times):
    """Run compare() on each time window separately and pool the errors."""
    window_ids = np.floor(times / WINDOW)
    position_errors, angle_errors = [], []
    for window in np.unique(window_ids):
        keep = window_ids == window
        spread = np.ptp(logged[keep, :3, 3], axis=0).max() if keep.sum() else 0
        if keep.sum() < MIN_POSES or spread < MIN_SPREAD:
            continue
        position_error, angle_error = compare(computed[keep], logged[keep])
        position_errors.append(position_error)
        angle_errors.append(angle_error)
    return np.concatenate(position_errors), np.concatenate(angle_errors), len(position_errors)


def logged_frames(matched):
    frames = np.tile(np.eye(4), (len(matched), 1, 1))
    frames[:, :3, :3] = Rotation.from_quat(matched[["qx", "qy", "qz", "qw"]].to_numpy()).as_matrix()
    frames[:, :3, 3] = matched[["x", "y", "z"]].to_numpy()
    return frames


def summary(label, errors):
    return f"{label}: median {np.median(errors):6.2f}, 95th pct {np.percentile(errors, 95):6.2f}"


def check_arm(matched, joints, tooltip):
    logged = logged_frames(matched)
    times = matched.t.to_numpy()
    q = matched[[f"pos_{name}" for name in JOINTS]].to_numpy()
    for rule_name, rule in ANGLE_RULES.items():
        frames = [forward_kinematics(joints, q_row, rule, tooltip) for q_row in q]
        wrist_pos, _, _ = compare_windows(np.array([f[0] for f in frames]), logged, times)
        tip_pos, tip_rot, n_windows = compare_windows(np.array([f[1] for f in frames]), logged, times)
        print(f"  angle = {rule_name} ({n_windows} windows of {WINDOW} s)")
        print(f"    wrist point vs logged, {summary('position mm', wrist_pos)}")
        print(f"    tool tip    vs logged, {summary('position mm', tip_pos)}, {summary('rotation deg', tip_rot)}")


def main():
    tool_path = Path(sys.argv[1]) if len(sys.argv) > 1 else TOOL_FILE
    bag = Path(sys.argv[2]) if len(sys.argv) > 2 else BAG
    tool = load_tool_file(tool_path)
    joints = ARM_DH + tool["DH"]["joints"]
    tooltip = np.array(tool["tooltip-offset"])
    print(f"tool file: {tool_path.name}\nbag: {bag.name}")
    for arm in ARMS:
        poses = read_logged_poses(bag, arm)
        matched = match_joints(poses, bag, arm)
        print(f"\n{arm}: {len(matched)} matched poses, frames {poses.frame_id.unique().tolist()}")
        check_arm(matched, joints, tooltip)


if __name__ == "__main__":
    main()
