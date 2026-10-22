# Suture timing (draft)

Written by `scripts/suture_times.py` from `results/annotations/`; re-run it after new annotations.

## Procedure time

![Procedure time](figures/procedure.png)

**Total procedure time.** One row per case, from the start of dissection (0) to the cut of the last stitch; the number is the total in minutes. Shaded bars: annotated phases. Purple bars: stitches, from the needle first touching tissue to the assistant's cut.

| case | system | total (min) | dissection (min) | first stitch to last cut (min) | stitches |
|---|---|---|---|---|---|
| P01 | 3 mm | 100 | 19 | 77 | 4 |
| P02 | 3 mm | 116 | 46 | 52 | 6 |
| P03 | 3 mm | 149 | 61 | 83 | 13 |
| P04 | 8 mm | 76 | 32 | 38 | 7 |
| P05 | 8 mm | 75 | 18 | 53 | 13 |
| P06 | 8 mm | 113 | 27 | 77 | 8 |
| P07 | 8 mm | 62 | 8.8 | 50 | 11 |

Median per system:

| system | total (min) | dissection (min) | first stitch to last cut (min) | stitches |
|---|---|---|---|---|
| 3 mm | 116 | 46 | 77 | 6.0 |
| 8 mm | 75 | 23 | 52 | 9.5 |


## All cases

![Overview](figures/overview.png)

**Stitch timelines, 3 mm vs 8 mm.** One row per case, aligned at its first stitch. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut).

## All cases, with numbers

![Overview with numbers](figures/overview_stats.png)

**Stitch timelines with per-case numbers.** Left: as above. Right: Stitches, number of stitches; Stitch, mean stitch time (needle first touches tissue to knot tightened); Gap, mean time from the end of one stitch (knot tightened) to the start of the next; Span, first stitch to last cut. Bold rows: mean of the cases in each system.

## P01

![Timeline](figures/timeline_pig_may29-2026-05-29_09.34.18.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P02

![Timeline](figures/timeline_pig_jun15-2026-06-15_10.14.18.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P03

![Timeline](figures/timeline_pig_jun16-2026-06-16_09.57.53.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P04

![Timeline](figures/timeline_pig_aug18-2026-08-18_10.10.14.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P05

![Timeline](figures/timeline_pig_aug19-2026-08-19_12.09.17.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P06

![Timeline](figures/timeline_pig_oct07-2026-10-07_14.31.12.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## P07

![Timeline](figures/timeline_pig_oct08-2026-10-08_13.19.52.png)

**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to last throw tightened) and assistant (light purple, tightened to the assistant's cut). Brackets below: each whole stitch, from the needle first touching tissue to the assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)

## Summary per measure (seconds)

| block | measure | n | mean | SD | median | min | max |
|---|---|---|---|---|---|---|---|
| all blocks | stitch | 62 | 280 | 183 | 216 | 116 | 1265 |
| all blocks | bite | 62 | 130 | 141 | 78 | 28 | 832 |
| all blocks | knot tying | 62 | 150 | 73 | 132 | 45 | 473 |
| all blocks | assistant | 61 | 38 | 23 | 32 | 14 | 161 |
| all blocks | gap | 55 | 150 | 199 | 67 | 22 | 1082 |
| muscle repair | stitch | 7 | 370 | 212 | 338 | 182 | 815 |
| muscle repair | bite | 7 | 230 | 187 | 185 | 76 | 628 |
| muscle repair | knot tying | 7 | 140 | 30 | 137 | 106 | 186 |
| muscle repair | assistant | 7 | 44 | 16 | 39 | 27 | 69 |
| muscle repair | gap | 7 | 117 | 70 | 86 | 53 | 248 |
| soft palate | stitch | 31 | 309 | 211 | 268 | 116 | 1265 |
| soft palate | bite | 31 | 137 | 151 | 90 | 28 | 832 |
| soft palate | knot tying | 31 | 172 | 93 | 143 | 45 | 473 |
| soft palate | assistant | 30 | 41 | 28 | 32 | 15 | 161 |
| soft palate | gap | 29 | 198 | 259 | 67 | 22 | 1082 |
| hard palate | stitch | 24 | 216 | 107 | 177 | 125 | 553 |
| hard palate | bite | 24 | 91 | 95 | 65 | 28 | 460 |
| hard palate | knot tying | 24 | 124 | 35 | 111 | 84 | 213 |
| hard palate | assistant | 24 | 32 | 14 | 28 | 14 | 67 |
| hard palate | gap | 19 | 90 | 76 | 62 | 27 | 293 |

## Blocks

| case | block | duration (s) | stitches | time stitching (%) |
|---|---|---|---|---|
| P04 | soft palate | 1158 | 4 | 80 |
| P04 | hard palate | 1119 | 3 | 65 |
| P05 | muscle repair | 825 | 2 | 65 |
| P05 | soft palate | 1062 | 5 | 77 |
| P05 | hard palate | 1408 | 6 | 68 |
| P02 | soft palate | 2001 | 4 | 59 |
| P02 | hard palate | 1150 | 2 | 92 |
| P03 | muscle repair | 1005 | 2 | 69 |
| P03 | soft palate | 1663 | 5 | 80 |
| P03 | hard palate | 2124 | 6 | 55 |
| P03 | soft palate | 147 | 5 | 909 |
| P01 | soft palate | 5588 | 4 | 47 |
| P06 | muscle repair | 1314 | 1 | 62 |
| P06 | soft palate | 2765 | 4 | 57 |
| P06 | hard palate | 952 | 3 | 56 |
| P07 | muscle repair | 672 | 2 | 81 |
| P07 | soft palate | 1447 | 5 | 76 |
| P07 | hard palate | 926 | 4 | 78 |

## Stitches (seconds)

| case | block | number | stitch | bite | knot tying | assistant | gap to next |
|---|---|---|---|---|---|---|---|
| P04 | soft palate | 1 | 268 | 135 | 133 | 49 | 66 |
| P04 | soft palate | 2 | 274 | 90 | 185 | 53 | 60 |
| P04 | soft palate | 3 | 215 | 45 | 169 | 26 | 33 |
| P04 | soft palate | 4 | 175 | 52 | 123 | 41 | 97 |
| P04 | hard palate | 1 | 292 | 143 | 149 | 17 | 293 |
| P04 | hard palate | 2 | 197 | 73 | 123 | 39 | 43 |
| P04 | hard palate | 3 | 239 | 105 | 134 | 15 |  |
| P05 | muscle repair | 1 | 354 | 185 | 169 | 52 | 53 |
| P05 | muscle repair | 2 | 182 | 76 | 106 | 39 | 156 |
| P05 | soft palate | 1 | 209 | 80 | 129 | 30 | 36 |
| P05 | soft palate | 2 | 176 | 30 | 145 | 31 | 67 |
| P05 | soft palate | 3 | 119 | 40 | 79 | 46 | 52 |
| P05 | soft palate | 4 | 139 | 34 | 104 | 16 | 22 |
| P05 | soft palate | 5 | 180 | 135 | 45 | 72 | 126 |
| P05 | hard palate | 1 | 164 | 68 | 96 | 36 | 44 |
| P05 | hard palate | 2 | 133 | 28 | 105 | 67 | 71 |
| P05 | hard palate | 3 | 196 | 35 | 161 | 32 | 93 |
| P05 | hard palate | 4 | 169 | 55 | 113 | 24 | 63 |
| P05 | hard palate | 5 | 177 | 68 | 109 | 23 | 59 |
| P05 | hard palate | 6 | 125 | 42 | 84 | 19 |  |
| P02 | soft palate | 1 | 224 | 81 | 143 | 68 | 69 |
| P02 | soft palate | 2 | 185 | 46 | 139 | 29 | 379 |
| P02 | soft palate | 3 | 431 | 283 | 147 | 161 | 316 |
| P02 | soft palate | 4 | 335 | 117 | 218 | 31 | 41 |
| P02 | hard palate | 1 | 505 | 292 | 213 | 34 | 43 |
| P02 | hard palate | 2 | 553 | 460 | 94 | 32 |  |
| P03 | muscle repair | 1 | 298 | 161 | 137 | 69 | 86 |
| P03 | muscle repair | 2 | 399 | 256 | 143 | 37 | 248 |
| P03 | soft palate | 1 | 387 | 229 | 158 | 40 | 55 |
| P03 | soft palate | 2 | 226 | 122 | 104 | 34 | 178 |
| P03 | soft palate | 3 | 295 | 47 | 248 | 39 | 55 |
| P03 | soft palate | 4 | 314 | 57 | 258 | 33 | 435 |
| P03 | hard palate | 1 | 307 | 125 | 182 | 30 | 44 |
| P03 | hard palate | 2 | 211 | 92 | 118 | 54 | 131 |
| P03 | hard palate | 3 | 151 | 61 | 90 | 18 | 31 |
| P03 | hard palate | 4 | 165 | 55 | 109 | 24 | 213 |
| P03 | hard palate | 5 | 137 | 47 | 90 | 20 | 242 |
| P03 | hard palate | 6 | 202 | 50 | 151 | 14 | 27 |
| P03 | soft palate | 5 | 116 | 33 | 82 | 21 |  |
| P01 | soft palate | 1 | 1265 | 832 | 433 | 42 | 1082 |
| P01 | soft palate | 2 | 429 | 159 | 270 | 81 | 167 |
| P01 | soft palate | 3 | 432 | 254 | 178 | 65 | 717 |
| P01 | soft palate | 4 | 503 | 307 | 196 |  |  |
| P06 | muscle repair | 1 | 815 | 628 | 186 | 28 | 139 |
| P06 | soft palate | 1 | 305 | 194 | 111 | 23 | 302 |
| P06 | soft palate | 2 | 561 | 88 | 473 | 26 | 59 |
| P06 | soft palate | 3 | 368 | 120 | 249 | 29 | 766 |
| P06 | soft palate | 4 | 335 | 146 | 189 | 43 | 255 |
| P06 | hard palate | 1 | 218 | 72 | 145 | 61 | 82 |
| P06 | hard palate | 2 | 172 | 71 | 100 | 49 | 59 |
| P06 | hard palate | 3 | 144 | 47 | 97 | 40 |  |
| P07 | muscle repair | 1 | 338 | 208 | 131 | 59 | 62 |
| P07 | muscle repair | 2 | 203 | 94 | 109 | 27 | 76 |
| P07 | soft palate | 1 | 189 | 58 | 132 | 27 | 34 |
| P07 | soft palate | 2 | 180 | 65 | 115 | 15 | 61 |
| P07 | soft palate | 3 | 147 | 28 | 120 | 15 | 30 |
| P07 | soft palate | 4 | 255 | 125 | 131 | 21 | 156 |
| P07 | soft palate | 5 | 334 | 211 | 123 | 29 | 31 |
| P07 | hard palate | 1 | 242 | 55 | 187 | 26 | 62 |
| P07 | hard palate | 2 | 137 | 37 | 100 | 41 | 42 |
| P07 | hard palate | 3 | 176 | 35 | 141 | 24 | 69 |
| P07 | hard palate | 4 | 163 | 69 | 94 | 24 |  |

## Annotation checks

- P01, soft palate stitch 4: assistant time left out as an outlier.
- P07, soft palate stitch 5: 2 needle_through marks; the last one is used.
- P03, soft palate: block marked 2 times; its stitch count and time stitching (%) include the stitches of every span.
