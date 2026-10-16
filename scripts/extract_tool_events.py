"""Extract every tool event from each rosbag (8 mm bags have them; 3 mm bags do not).

Usage:
    python scripts/extract_tool_events.py [bag ...]

Topics, per arm:
    /PSM*/io/tool            tool sensor: 0 = no tool, 1 = tool present, 2 = in between (inserting)
    /PSM*/tool_type          tool name set by the console; '' when the tool is removed
    /PSM*/tool_type_request  console asks the operator to pick the tool type from a list

So the tool names in the 8 mm bags were chosen by the operator, not read from the tool.

Output: data/derived/<bag>/tool_events.csv
    t      seconds since bag start
    arm    psm1 / psm2
    event  sensor / type / request
    value  sensor: 0, 1 or 2; type: tool name ('' = removed); request: blank
"""

import sys

import pandas as pd

from bagio import DERIVED_DIR, bags_from_args, open_bag, read_messages

TOPICS = {
    "/PSM1/io/tool": ("psm1", "sensor"),
    "/PSM2/io/tool": ("psm2", "sensor"),
    "/PSM1/tool_type": ("psm1", "type"),
    "/PSM2/tool_type": ("psm2", "type"),
    "/PSM1/tool_type_request": ("psm1", "request"),
    "/PSM2/tool_type_request": ("psm2", "request"),
}
VALUE_BY_EVENT = {
    "sensor": lambda msg: int(msg.buttons[0]),
    "type": lambda msg: msg.data,
    "request": lambda msg: "",
}


def tool_events(path):
    rows = []
    with open_bag(path) as reader:
        start = reader.start_time / 1e9
        for topic, t, msg in read_messages(reader, TOPICS):
            arm, event = TOPICS[topic]
            rows.append({"t": round(t - start, 3), "arm": arm, "event": event, "value": VALUE_BY_EVENT[event](msg)})
    return pd.DataFrame(rows, columns=["t", "arm", "event", "value"])


def main():
    for bag in bags_from_args(sys.argv[1:]):
        events = tool_events(bag)
        events.to_csv(DERIVED_DIR / bag.stem / "tool_events.csv", index=False)
        print(f"{bag.stem}: {len(events)} tool events", flush=True)


if __name__ == "__main__":
    main()
