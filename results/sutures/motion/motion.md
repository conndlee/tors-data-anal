# Instrument motion per stitch phase

Written by `scripts/phase_motion.py`. Both instruments summed; joints that are the same kind on both systems. Median (interquartile range) over stitches. 3 mm: 19 stitches, 2 pigs; 8 mm: 39 stitches, 4 pigs. May 29 has no rosbag.

## Absolute (per phase)

| measure | Bite, 3 mm | Bite, 8 mm | Knot tying, 3 mm | Knot tying, 8 mm |
|---|---|---|---|---|
| Shaft motion (mm) | 395 (265-1039) | 427 (269-721) | 1204 (1034-1557) | 1072 (906-1262) |
| Roll (rad) | 21 (11-41) | 21 (15-35) | 36 (29-42) | 40 (34-47) |
| Wrist pitch + yaw (rad) | 29 (18-76) | 30 (17-41) | 58 (47-74) | 54 (44-63) |
| Grasps (count) | 10 (6-22) | 14 (9-24) | 21 (16-26) | 23 (21-30) |
| Idle (both still) (s) | 16 (7-29) | 8.9 (4.9-17.1) | 12 (6-15) | 9.3 (7.1-13.3) |

## Normalised by phase duration (per minute; idle as % of the phase)

| measure | Bite, 3 mm | Bite, 8 mm | Knot tying, 3 mm | Knot tying, 8 mm |
|---|---|---|---|---|
| Shaft motion (mm/min) | 302 (284-341) | 359 (324-400) | 528 (469-650) | 523 (469-577) |
| Roll (rad/min) | 12 (11-15) | 20 (17-22) | 15 (14-17) | 20 (16-21) |
| Wrist pitch + yaw (rad/min) | 21 (18-24) | 23 (21-26) | 25 (23-27) | 25 (22-32) |
| Grasps (per min) | 7.4 (6.4-8.5) | 12 (9-14) | 9.3 (8.0-10.0) | 12 (10-13) |
| Idle (both still) (% of phase) | 14 (12-16) | 14 (10-16) | 7.1 (5.5-8.7) | 8.0 (6.1-9.9) |

## Workspace (per instrument; volumes of both instruments added)

| measure | Bite, 3 mm | Bite, 8 mm | Knot tying, 3 mm | Knot tying, 8 mm |
|---|---|---|---|---|
| Workspace volume, whole phase (cm³) | 1.5 (1.0-2.4) [n=19] | 2.1 (1.0-3.3) [n=39] | 6.9 (3.6-10.4) [n=19] | 5.9 (4.0-7.7) [n=39] |
| Workspace volume, first 60 s (cm³) | 1.0 (0.6-1.3) [n=12] | 1.6 (1.1-2.2) [n=24] | 3.7 (2.1-5.8) [n=19] | 3.1 (2.2-3.9) [n=38] |
| Spread around own centre (mm) | 4.4 (4.1-4.9) [n=19] | 5.1 (4.6-6.0) [n=39] | 6.6 (5.5-7.4) [n=19] | 6.6 (6.1-7.1) [n=39] |

n = phases included; the first-60-s volume leaves out phases shorter than 60 s.

## Per pig, normalised (medians)

| pig | phase | duration (s) | Shaft motion | Roll | Wrist pitch + yaw | Grasps | Idle (both still) |
|---|---|---|---|---|---|---|---|
| Jun 15 · 3 mm | Bite | 200 | 250 | 11 | 19 | 8.3 | 15 |
| Jun 15 · 3 mm | Knot tying | 145 | 444 | 16 | 24 | 10 | 7.7 |
| Jun 16 · 3 mm | Bite | 61 | 308 | 13 | 22 | 6.9 | 13 |
| Jun 16 · 3 mm | Knot tying | 137 | 571 | 15 | 25 | 8.7 | 6.6 |
| Aug 18 · 8 mm | Bite | 90 | 369 | 20 | 21 | 12 | 9.9 |
| Aug 18 · 8 mm | Knot tying | 134 | 536 | 17 | 21 | 13 | 8.2 |
| Aug 19 · 8 mm | Bite | 55 | 344 | 18 | 26 | 12 | 12 |
| Aug 19 · 8 mm | Knot tying | 106 | 556 | 20 | 33 | 13 | 6.2 |
| Oct 7 · 8 mm | Bite | 104 | 383 | 23 | 25 | 13 | 13 |
| Oct 7 · 8 mm | Knot tying | 166 | 459 | 19 | 24 | 10 | 8.1 |
| Oct 8 · 8 mm | Bite | 65 | 354 | 21 | 20 | 11 | 15 |
| Oct 8 · 8 mm | Knot tying | 123 | 510 | 17 | 22 | 11 | 9.8 |

Still: shaft end slower than 2 mm/s and wrist slower than 0.1 rad/s, for both instruments. Grasps: jaw closing below 0.1 rad after opening above 0.3 rad.
