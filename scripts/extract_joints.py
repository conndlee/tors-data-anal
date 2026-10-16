"""Extract joint data from each rosbag into small parquet tables (run once; slow).

Usage:
    python scripts/extract_joints.py [bag ...]

Defaults to every bag in data/rosbags. To go faster, run one process per bag:
    ls data/rosbags/*.bag | xargs -P 6 -n 1 python scripts/extract_joints.py

Output, per bag, in data/derived/<bag>/:
    psm1.parquet, psm2.parquet, psm1_jaw.parquet, psm2_jaw.parquet, mtml.parquet, mtmr.parquet
        t        seconds since bag start (bag receive time; header stamps are unreliable)
        pos_<j>  position of joint <j> (rad or m)
        eff_<j>  effort of joint <j> (Nm or N)
        Joints are matched by name, so a joint missing from a message is NaN.
    tool_changes.csv  (8 mm bags only) t, arm, tool
"""

import sys

import numpy as np
import pandas as pd

from bagio import DERIVED_DIR, bags_from_args, open_bag, read_messages

JOINT_TOPICS = {
    "/PSM1/measured_js": "psm1",
    "/PSM2/measured_js": "psm2",
    "/PSM1/jaw/measured_js": "psm1_jaw",
    "/PSM2/jaw/measured_js": "psm2_jaw",
    "/MTML/measured_js": "mtml",
    "/MTMR/measured_js": "mtmr",
}
TOOL_TOPICS = {"/PSM1/tool_type": "psm1", "/PSM2/tool_type": "psm2"}


class JointBuffer:
    """Collects messages for one topic, grouped by joint-name list (6 or 7 joints)."""

    def __init__(self):
        self.groups = {}

    def add(self, t, msg):
        group = self.groups.setdefault(tuple(msg.name), {"t": [], "pos": [], "eff": []})
        group["t"].append(t)
        group["pos"].append(msg.position)
        group["eff"].append(msg.effort)

    def to_frame(self):
        frames = [group_frame(names, group) for names, group in self.groups.items()]
        return pd.concat(frames).sort_values("t", ignore_index=True)


def group_frame(names, group):
    frame = pd.DataFrame({"t": group["t"]})
    positions = np.array(group["pos"])
    efforts = np.array(group["eff"])
    for i, name in enumerate(names):
        frame[f"pos_{name}"] = positions[:, i]
        frame[f"eff_{name}"] = efforts[:, i]
    return frame


def read_joint_tables(reader, start):
    buffers = {name: JointBuffer() for name in JOINT_TOPICS.values()}
    for topic, t, msg in read_messages(reader, JOINT_TOPICS):
        buffers[JOINT_TOPICS[topic]].add(t - start, msg)
    return {name: buffer.to_frame() for name, buffer in buffers.items()}


def read_tool_changes(reader, start):
    rows = [
        {"t": t - start, "arm": TOOL_TOPICS[topic], "tool": msg.data}
        for topic, t, msg in read_messages(reader, TOOL_TOPICS)
    ]
    return pd.DataFrame(rows, columns=["t", "arm", "tool"]).query("tool != ''")


def extract_bag(path):
    out_dir = DERIVED_DIR / path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    with open_bag(path) as reader:
        start = reader.start_time / 1e9
        tables = read_joint_tables(reader, start)
        tools = read_tool_changes(reader, start)
    for name, table in tables.items():
        table.to_parquet(out_dir / f"{name}.parquet", index=False)
    tools.to_csv(out_dir / "tool_changes.csv", index=False)


def main():
    for bag in bags_from_args(sys.argv[1:]):
        print(f"extracting {bag.name} ...", flush=True)
        extract_bag(bag)
        print(f"done: {bag.name}", flush=True)


if __name__ == "__main__":
    main()
