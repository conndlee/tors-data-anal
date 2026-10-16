"""Write a table of which topics each rosbag has.

Usage:
    python scripts/topic_matrix.py [bag_dir] [output_csv]

Defaults: bag_dir = data/rosbags, output_csv = results/audit/topic_matrix.csv
One row per topic, one column per bag. Cells hold the message count, blank if the topic is missing.
"""

import csv
import sys
from pathlib import Path

from rosbags.rosbag1 import Reader


def topic_counts(path):
    with Reader(path) as reader:
        return {topic: info.msgcount for topic, info in reader.topics.items()}


def main():
    bag_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/rosbags")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results/audit/topic_matrix.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {bag.name: topic_counts(bag) for bag in sorted(bag_dir.glob("*.bag"))}
    all_topics = sorted(set().union(*counts.values()))

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", *counts])
        for topic in all_topics:
            writer.writerow([topic, *(per_bag.get(topic, "") for per_bag in counts.values())])


if __name__ == "__main__":
    main()
