"""Rosbag and video signals per second, in video time, for the timeline in tools/annotator.html.

Usage:
    python scripts/timeline.py

Tracks (one value per second of video):
    psm1 grasps, psm2 grasps   jaw closures in the last GRASP_WINDOW seconds
    psm1 roll, psm2 roll       wrist roll speed (rad/s), smoothed; needle passes are big roll motions
    occlusion                  share of the image covered by instruments (scripts/occlusion.py), if run
    image motion               frame-to-frame change in the video (scripts/video_motion.py), if run
Videos without a rosbag (the May pilots) get only the video tracks.
Bands (8 mm only): which tool was mounted on each arm, from the tool log.

Output: results/timeline/<video>.json
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from bagio import DERIVED_DIR
from project import SYNC_FILE, VIDEO_DIR

OCCLUSION_DIR = Path("data/derived/occlusion/video")
MOTION_DIR = Path("data/derived/video")
OUT_DIR = Path("results/timeline")
ARMS = ["psm1", "psm2"]
GRASP_WINDOW = 10  # s
JAW_CLOSED_RAD = 0.1  # jaw angle below this counts as closed
JAW_OPEN_RAD = 0.3  # above this counts as open (the dead band ignores jitter)
ROLL_SMOOTH = 5  # s


def video_seconds(video):
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(VIDEO_DIR / f"{video}.mp4")]
    return int(float(subprocess.run(command, capture_output=True, text=True, check=True).stdout))


def per_second(t_video, values, length, how):
    """Put samples into 1 s bins of video time; how is 'sum' or 'mean'."""
    bins = pd.Series(values).groupby(np.floor(t_video).astype(int)).agg(how)
    return bins.reindex(range(length), fill_value=0).fillna(0).to_numpy()


def grasp_track(bag, arm, offset, length):
    jaw = pd.read_parquet(DERIVED_DIR / bag / f"{arm}_jaw.parquet").dropna()
    state = pd.Series(np.select([jaw.pos_jaw < JAW_CLOSED_RAD, jaw.pos_jaw > JAW_OPEN_RAD], [0.0, 1.0], np.nan)).ffill()
    closes = ((state.shift() == 1) & (state == 0)).astype(float).to_numpy()
    counts = per_second(jaw.t.to_numpy() + offset, closes, length, "sum")
    return pd.Series(counts).rolling(GRASP_WINDOW, min_periods=1).sum().to_numpy()


def roll_track(bag, arm, offset, length):
    d = pd.read_parquet(DERIVED_DIR / bag / f"{arm}.parquet", columns=["t", "pos_outer_roll"]).dropna()
    speed = (d.pos_outer_roll.diff().abs() / d.t.diff()).clip(upper=20).fillna(0).to_numpy()
    mean_speed = per_second(d.t.to_numpy() + offset, speed, length, "mean")
    return pd.Series(mean_speed).rolling(ROLL_SMOOTH, center=True, min_periods=1).mean().to_numpy()


def occlusion_track(video, length):
    path = OCCLUSION_DIR / f"{video}.parquet"
    if not path.exists():
        return None
    d = pd.read_parquet(path)
    return per_second(d.t_video.to_numpy(), d.occlusion.to_numpy(), length, "mean")


def motion_track(video, length):
    path = MOTION_DIR / f"{video}.parquet"
    if not path.exists():
        return None
    d = pd.read_parquet(path)
    return per_second(d.t.to_numpy(), d.motion.to_numpy(), length, "mean")


def video_tracks(video, length):
    """Tracks that need only the video: occlusion and image motion."""
    tracks = []
    for name, values in [("occlusion", occlusion_track(video, length)), ("image motion", motion_track(video, length))]:
        if values is not None:
            tracks.append({"name": name, "values": rounded(values)})
    return tracks


def tool_bands(bag, offset):
    """(arm, start, end, tool) in video time, from the 8 mm tool log; empty for 3 mm."""
    path = DERIVED_DIR / bag / "tool_events.csv"
    events = pd.read_csv(path, dtype={"value": str}, keep_default_na=False) if path.stat().st_size > 30 else None
    if events is None:
        return []
    bands = []
    for arm in ARMS:
        types = events[(events.arm == arm) & (events.event == "type")]
        ends = list(types.t.iloc[1:]) + [np.inf]
        bands += [{"track": f"{arm} tool", "start": round(t + offset, 1), "end": round(min(end, 1e7) + offset, 1),
                   "label": tool.split(":")[0]} for t, end, tool in zip(types.t, ends, types.value) if tool]
    return bands


def rounded(values):
    return [round(float(v), 4) for v in values]


def video_timeline(row):
    length = video_seconds(row.video)
    tracks = []
    for arm in ARMS:
        tracks.append({"name": f"{arm} grasps", "values": rounded(grasp_track(row.bag, arm, row.offset, length))})
        tracks.append({"name": f"{arm} roll", "values": rounded(roll_track(row.bag, arm, row.offset, length))})
    tracks += video_tracks(row.video, length)
    return {"video": f"{row.video}.mp4", "step": 1, "tracks": tracks, "bands": tool_bands(row.bag, row.offset)}


def video_only_timeline(video):
    tracks = video_tracks(video, video_seconds(video))
    return {"video": f"{video}.mp4", "step": 1, "tracks": tracks, "bands": []}


def save(timeline):
    name = timeline["video"].replace(".mp4", "")
    (OUT_DIR / f"{name}.json").write_text(json.dumps(timeline))
    names = ", ".join(t["name"] for t in timeline["tracks"])
    print(f"{name}: {names}; {len(timeline['bands'])} tool bands", flush=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sync = pd.read_csv(SYNC_FILE)
    for row in sync.itertuples():
        save(video_timeline(row))
    for video in sorted(p.stem for p in VIDEO_DIR.glob("*.mp4")):
        if video not in set(sync.video):
            save(video_only_timeline(video))


if __name__ == "__main__":
    main()
