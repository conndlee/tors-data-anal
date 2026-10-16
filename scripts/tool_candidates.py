"""Candidate tool swaps from rosbag evidence, for a person to confirm in the video.

Usage:
    python scripts/tool_candidates.py

No single joint signal finds swaps reliably, so we collect several kinds of
evidence per arm, group evidence within GROUP seconds, and score each group:

    tip_switch   3  best-fit tip length changes type (only bags with measured_cp; tip_type_windows.py)
    retraction   2  insertion below RETRACTED for over MIN_RETRACTION seconds
    freeze_jump  2  wrist still for MIN_FREEZE seconds, then a jump within JUMP_AFTER seconds
    jump         1  wrist joint value jumps by over JUMP rad in one sample, on this arm only
                    (jumps on both arms at once are system events and are ignored)

8 mm bags are included so the scores can be checked against their logged swaps.

Output: results/tools/<video>_candidates.csv
    video, arm, t_bag, t_video, score, evidence, logged (8 mm only: a logged swap within GROUP s)
"""

from pathlib import Path

import numpy as np
import pandas as pd

from bagio import DERIVED_DIR, SYSTEM_BY_BAG

SYNC_FILE = Path("results/sync/offsets.csv")
OUTPUT_DIR = Path("results/tools")
ARMS = ["psm1", "psm2"]
WRIST = ["pos_outer_roll", "pos_outer_wrist_pitch", "pos_outer_wrist_yaw"]
WEIGHTS = {"tip_switch": 3, "retraction": 2, "freeze_jump": 2, "jump": 1}
GROUP = 90  # s
JUMP = 0.3  # rad
SAME_TIME = 1  # s, jumps on both arms closer than this are one system event
RETRACTED = 0.03  # m
MIN_RETRACTION = 5  # s
STILL = 1e-3  # rad, largest wrist range within one second that counts as still
MIN_FREEZE = 20  # s
JUMP_AFTER = 60  # s


def load_arm(bag, arm):
    columns = ["t", "pos_outer_insertion"] + WRIST
    return pd.read_parquet(DERIVED_DIR / bag / f"{arm}.parquet", columns=columns).dropna()


def runs(mask, t, min_length):
    """(start, end) times of stretches where mask is True for at least min_length seconds."""
    edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    pairs = [(t[s], t[e - 1]) for s, e in zip(edges[0::2], edges[1::2])]
    return [(s, e) for s, e in pairs if e - s >= min_length]


def jump_times(d):
    step = d[WRIST].diff().abs().max(axis=1)
    t = d.t[step > JUMP].to_numpy()
    return t[np.r_[True, np.diff(t) > 10]] if len(t) else t


def retraction_times(d):
    return [s for s, _ in runs((d.pos_outer_insertion < RETRACTED).to_numpy(), d.t.to_numpy(), MIN_RETRACTION)]


def freeze_jump_times(d, jumps):
    seconds = d.t.astype(int)
    still = d.groupby(seconds)[WRIST].agg(lambda x: x.max() - x.min()).max(axis=1) < STILL
    freezes = runs(still.to_numpy(), still.index.to_numpy(), MIN_FREEZE)
    return [jumps[(jumps >= s) & (jumps <= e + JUMP_AFTER)][0] for s, e in freezes
            if np.any((jumps >= s) & (jumps <= e + JUMP_AFTER))]


def tip_switch_times(bag, arm):
    path = DERIVED_DIR / bag / "tip_type_windows.csv"
    if not path.exists():
        return []
    w = pd.read_csv(path).query("arm == @arm").sort_values("t")
    # a switch needs the new type to hold for two windows in a row
    steady = w[w.type.eq(w.type.shift(-1))]
    changed = steady.type.ne(steady.type.shift())
    return steady.t[changed].iloc[1:].tolist()


def arm_evidence(bag, arm, other_jumps):
    d = load_arm(bag, arm)
    jumps = jump_times(d)
    alone = [t for t in jumps if not np.any(np.abs(other_jumps - t) < SAME_TIME)]
    evidence = [(t, "jump") for t in alone]
    evidence += [(t, "retraction") for t in retraction_times(d)]
    evidence += [(t, "freeze_jump") for t in freeze_jump_times(d, np.array(alone))]
    evidence += [(t, "tip_switch") for t in tip_switch_times(bag, arm)]
    return sorted(evidence)


def group_evidence(evidence):
    """Group evidence closer than GROUP seconds; returns (first time, score, description)."""
    groups = []
    for t, kind in evidence:
        if groups and t - groups[-1][-1][0] < GROUP:
            groups[-1].append((t, kind))
        else:
            groups.append([(t, kind)])
    return [(g[0][0], sum(WEIGHTS[k] for _, k in g), " + ".join(sorted({k for _, k in g}))) for g in groups]


def logged_swaps(bag):
    path = DERIVED_DIR / bag / "tool_events.csv"
    events = pd.read_csv(path, dtype={"value": str}, keep_default_na=False) if path.stat().st_size > 30 else None
    if events is None:
        return {arm: np.array([]) for arm in ARMS}
    removed = events[(events.event == "sensor") & (events.value == "0")]
    return {arm: removed[removed.arm == arm].t.to_numpy() for arm in ARMS}


def bag_candidates(bag, video, offset):
    jumps = {arm: jump_times(load_arm(bag, arm)) for arm in ARMS}
    logged = logged_swaps(bag)
    rows = []
    for arm, other in zip(ARMS, reversed(ARMS)):
        for t, score, evidence in group_evidence(arm_evidence(bag, arm, jumps[other])):
            near_logged = bool(np.any(np.abs(logged[arm] - t) < GROUP)) if SYSTEM_BY_BAG[bag] == "8mm" else ""
            rows.append({"video": f"{video}.mp4", "arm": arm, "t_bag": round(t, 1), "t_video": round(t + offset, 1),
                         "score": score, "evidence": evidence, "logged": near_logged})
    return pd.DataFrame(rows).sort_values("t_video")


def main():
    sync = pd.read_csv(SYNC_FILE)
    for row in sync.itertuples():
        table = bag_candidates(row.bag, row.video, row.offset)
        table.to_csv(OUTPUT_DIR / f"{row.video}_candidates.csv", index=False)
        print(f"{row.video}: {len(table)} candidates, {(table.score >= 2).sum()} with score >= 2")


if __name__ == "__main__":
    main()
