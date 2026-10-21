# Plan: rosbag measures per stitch and phase

## Idea

The video annotations give a time window for every phase:
bite, knot tying, assistant, the gaps between stitches, and the blocks.
The sync turns each window into rosbag time: `t_bag = t_video - offset` (`results/sync/offsets.csv`).
So we can measure what the robot did inside each phase, and compare 3 mm with 8 mm phase by phase.

## Limits

- Only signals in both systems' bags are compared:
  joint angles and efforts, the jaw, and the master consoles (MTMs).
  8 mm-only data (tip poses, force estimates, clutch topics) can only describe 8 mm.
- 3 mm tip lengths are uncertain, so comparisons use the shaft-end point and joint angles.
- May 29 has no rosbag: rosbag measures are 2 (3 mm) vs 4 (8 mm) pigs.
- The 3 mm and 8 mm hardware differ, so raw efforts are not directly comparable.

## Candidate measures

### Tier 1: solid, comparable

- Grasp count per phase (jaw closures): needle regrasps in the bite, wraps in knot tying.
- Idle share: time with both arms still. Hesitation or waiting vs active work.
- Shaft motion per phase: path length and speed of the shaft-end point.
- Wrist use: roll, wrist pitch and wrist yaw travel per phase.
- Gap content: moving vs idle, insertion changes (repositioning).

### Tier 2: useful, with care

- Smoothness: a jerk-based score of the shaft-end motion.
- Insertion depth and workspace per block: reach for the hard vs soft palate.
- Bimanual activity: share of time both arms move at once.
- Surgeon hand motion (MTMs): only if motion scaling was the same in both systems.

### Tier 3: needs validation first

- Grip and joint effort per phase, for the force question.
  Raw effort includes gravity and friction: compare to a free-motion baseline, within each system first.
- Automatic phase detection from jaw and wrist patterns, to check manual marks or speed up annotation.

## Steps

1. Sync check: plot jaw and roll traces with the phase marks for one stitch per pig.
   Confirm the marks line up with the robot data.
2. Extraction: `scripts/stitch_kinematics.py` writes one row per stitch x phase x arm
   with the Tier 1 measures to `results/kinematics/`.
3. Presentation: a per-pig table with a mean row per system (like overview_stats),
   plus one example trace figure.
4. Tier 2, then Tier 3 once a baseline method is agreed.

## Questions

1. Which measures matter most for the paper?
2. Do the arms have fixed roles (for example, PSM1 always the needle driver)?
3. Was motion scaling (master to instrument) the same in both systems?
4. Is force still a priority? If so, plan a baseline calibration step.
