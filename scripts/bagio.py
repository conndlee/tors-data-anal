"""Shared helpers for reading the rosbags and knowing which trial is which."""

from pathlib import Path

from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

from project import DERIVED_DIR  # noqa: F401  (re-exported for the bag scripts)

BAG_DIR = Path("data/rosbags")
TYPESTORE = get_typestore(Stores.ROS1_NOETIC)

# Which tool system each bag used. June = 3 mm, August/October = 8 mm (confirmed 2026-10-14).
SYSTEM_BY_BAG = {
    "2026-06-15-10-13-45": "3mm",
    "2026-06-16-09-58-51": "3mm",
    "2026-08-18-10-10-38": "8mm",
    "2026-08-19-12-08-59": "8mm",
    "2026-10-07-14-42-15": "8mm",
    "2026-10-08-13-19-59": "8mm",
}


def open_bag(path):
    return AnyReader([Path(path)], default_typestore=TYPESTORE)


def read_messages(reader, topics):
    """Yield (topic, bag time in s, message). Yields nothing if the bag has none of the topics.

    Note: rosbags treats an empty connection list as "all topics", so we must check first.
    """
    connections = [c for c in reader.connections if c.topic in topics]
    if not connections:
        return
    for conn, timestamp, raw in reader.messages(connections=connections):
        yield conn.topic, timestamp / 1e9, reader.deserialize(raw, conn.msgtype)


def bags_from_args(args):
    """Bag paths from the command line, or every bag in BAG_DIR."""
    return [Path(arg) for arg in args] or sorted(BAG_DIR.glob("*.bag"))
