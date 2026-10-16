"""Audit how clean the key joint data is in each rosbag.

Usage:
    python scripts/audit_bags.py [bag ...]

Defaults to every bag in data/rosbags. Writes one report per bag to results/audit/<bag>.txt:
joint names, effort, time gaps, header vs bag time, and tool changes.

Bags are scanned one after another; to go faster, run one process per bag:
    ls data/rosbags/*.bag | xargs -P 6 -n 1 python scripts/audit_bags.py
"""

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from bagio import bags_from_args, open_bag, read_messages

JOINT_TOPICS = [
    "/PSM1/measured_js",
    "/PSM2/measured_js",
    "/PSM1/jaw/measured_js",
    "/PSM2/jaw/measured_js",
    "/MTML/measured_js",
    "/MTMR/measured_js",
]
TOOL_TOPICS = ["/PSM1/tool_type", "/PSM2/tool_type"]
GAP_THRESHOLD_S = 0.5


@dataclass
class TopicStats:
    count: int = 0
    joint_sets: Counter = field(default_factory=Counter)
    effort_messages: int = 0
    stamp_offsets: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    last_time: float = None

    def add(self, bag_time, msg):
        self.count += 1
        self.joint_sets[tuple(msg.name)] += 1
        self.effort_messages += bool(np.any(msg.effort))
        self.stamp_offsets.append(stamp_seconds(msg) - bag_time)
        self.record_gap(bag_time)
        self.last_time = bag_time

    def record_gap(self, bag_time):
        gap = bag_time - (self.last_time or bag_time)
        if gap > GAP_THRESHOLD_S:
            self.gaps.append((self.last_time, gap))


def stamp_seconds(msg):
    return msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9


# ---------- per-bag scan ----------

def scan_joint_topics(reader):
    stats = {}
    for topic, bag_time, msg in read_messages(reader, JOINT_TOPICS):
        stats.setdefault(topic, TopicStats()).add(bag_time, msg)
    return stats


def read_tool_changes(reader):
    changes = [(bag_time, topic, msg.data) for topic, bag_time, msg in read_messages(reader, TOOL_TOPICS)]
    return [change for change in changes if change[2]]


# ---------- report ----------

def describe_topic(topic, stats, bag_start):
    offsets = np.array(stats.stamp_offsets)
    lines = [
        f"  {topic}: {stats.count} msgs, {stats.effort_messages / stats.count:.0%} with nonzero effort",
        f"    header - bag time (s): median {np.median(offsets):+.3f}, min {offsets.min():+.3f}, max {offsets.max():+.3f}",
        f"    gaps > {GAP_THRESHOLD_S} s: {len(stats.gaps)}, total {sum(g for _, g in stats.gaps):.1f} s",
    ]
    lines += [f"      at {start - bag_start:8.1f} s, length {gap:.1f} s" for start, gap in stats.gaps[:10]]
    lines += [f"    joints ({n} msgs): {list(names)}" for names, n in stats.joint_sets.items()]
    return lines


def describe_bag(path):
    with open_bag(path) as reader:
        start = reader.start_time / 1e9
        stats = scan_joint_topics(reader)
        tools = read_tool_changes(reader)
        duration = reader.duration / 1e9

    lines = [f"===== {path.name}  duration {duration:.0f} s ({duration / 60:.1f} min)"]
    for topic in JOINT_TOPICS:
        lines += describe_topic(topic, stats[topic], start) if topic in stats else [f"  {topic}: MISSING"]
    lines.append(f"  tool changes: {len(tools)}")
    lines += [f"    {t - start:8.1f} s  {topic}  {name}" for t, topic, name in tools]
    return lines


def main():
    bags = bags_from_args(sys.argv[1:])
    output_dir = Path("results/audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    for bag in bags:
        print(f"scanning {bag.name} ...", flush=True)
        report_path = output_dir / f"{bag.stem}.txt"
        report_path.write_text("\n".join(describe_bag(bag)) + "\n")
        print(f"done: {report_path}", flush=True)


if __name__ == "__main__":
    main()
