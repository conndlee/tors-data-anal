"""Tool swaps for each 8 mm video, ready to import into tools/annotator.html.

Usage:
    python scripts/tool_events.py

Needs data/derived/<bag>/tool_events.csv (extract_tool_events.py) and
results/sync/offsets.csv (sync_video.py).

A swap is a "tool_out" span: from the tool sensor reading 0 (tool removed)
to it next reading 1 (a tool is in). The note has the arm and the next tool
name the operator picked in the console (8 mm names are chosen by hand there).

3 mm bags do not log tool events; 3 mm swaps are reviewed with tools/tool_review.html.

Output: results/tools/<video>_tools.csv  (annotator CSV format, times in video seconds)
"""

from pathlib import Path

import pandas as pd

from bagio import DERIVED_DIR, SYSTEM_BY_BAG

SYNC_FILE = Path("results/sync/offsets.csv")
OUTPUT_DIR = Path("results/tools")
CSV_COLUMNS = ["video", "event", "start_s", "end_s", "duration_s", "note"]
MERGE_GAP = 30  # s


def next_value(events, kind, after, test):
    """First event of this kind after a time whose value passes test, or None."""
    later = events[(events.event == kind) & (events.t > after)]
    later = later[later.value.map(test)]
    return later.iloc[0] if len(later) else None


def arm_swaps(events, arm):
    events = events[events.arm == arm]
    rows = []
    for removed in events[(events.event == "sensor") & (events.value == "0")].itertuples():
        inserted = next_value(events, "sensor", removed.t, lambda v: v == "1")
        named = next_value(events, "type", removed.t, lambda v: v != "")
        end = inserted.t if inserted is not None else removed.t
        tool = named.value if named is not None else "unknown"
        rows.append({"start": removed.t, "end": end, "note": f"{arm} -> {tool} (logged)"})
    return rows


def merge_close(rows):
    """Merge swaps that start within MERGE_GAP of the previous one ending (sensor flicker while seating a tool)."""
    merged = []
    for row in sorted(rows, key=lambda r: r["start"]):
        if merged and row["start"] - merged[-1]["end"] < MERGE_GAP:
            merged[-1] = {**row, "start": merged[-1]["start"]}
        else:
            merged.append(row)
    return merged


def swap_table(bag, video, offset):
    events = pd.read_csv(DERIVED_DIR / bag / "tool_events.csv", dtype={"value": str}, keep_default_na=False)
    table = pd.DataFrame([row for arm in ["psm1", "psm2"] for row in merge_close(arm_swaps(events, arm))])
    table["video"] = f"{video}.mp4"
    table["event"] = "tool_out"
    table["start_s"] = (table.start + offset).round(3)
    table["end_s"] = (table.end + offset).round(3)
    table["duration_s"] = (table.end_s - table.start_s).round(3)
    return table.sort_values("start_s")[CSV_COLUMNS]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sync = pd.read_csv(SYNC_FILE)
    for row in sync.itertuples():
        if SYSTEM_BY_BAG[row.bag] != "8mm":
            continue
        table = swap_table(row.bag, row.video, row.offset)
        table.to_csv(OUTPUT_DIR / f"{row.video}_tools.csv", index=False)
        print(f"{row.video}: {len(table)} tool swaps")


if __name__ == "__main__":
    main()
