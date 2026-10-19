# Plan: time per stitch

## Goal

Time every stitch, and each part of the repair, in every recording. Compare 3 mm and 8 mm.
All stitches are simple interrupted. The repair has three parts, each marked as a block:
muscle repair (usually one stitch), hard palate suturing, and soft palate suturing (decided 2026-10-19).

## What counts as one stitch

- **Start:** the needle first touches tissue.
- **End:** the last throw of the knot is tightened.
  Cutting is done by the external assistant, so it is not part of stitch time.
- Each stitch belongs to the block that contains its start.
- A stitch that is abandoned (needle pulled out, stitch redone) is marked, not deleted.

Also mark, for each stitch:

- **needle through:** the needle is fully out on the far side, after both edges.
  If a bite is redone, mark only the final pass.
- **cut:** the assistant cuts the suture. It is marked after the stitch ends, outside the stitch span,
  so stitch time covers only work with the robotic tools.
  Each cut belongs to the stitch that most recently ended before it, even if the next stitch has already started.

This splits each stitch into phases:

- **Bite:** start to needle through.
- **Knot:** needle through to end.
- **Assistant access** (exploratory): end to cut.
  Smaller tools may leave the assistant more room and a clearer view.
  It also depends on how ready the assistant was, so it is reported as descriptive only.

## How it is recorded

1. Use `tools/annotator.html` on each video.
   Load `results/timeline/<video>.json` with the Timeline button (from `scripts/timeline.py`).
   It shows grasps, wrist roll, occlusion and (8 mm) the mounted tool under the video.
   Click it to jump there; the lower strip zooms on 10 minutes around now.
2. Keys:
   - `1` `2` `3`: one block around the muscle repair, the soft palate suturing and the hard palate suturing.
     Each block gives that part's duration; together they are the window for "occlusion during suturing".
   - `x`: start and end of each stitch. Stitches are numbered within their block.
   - `n`: needle through (one per stitch).
   - `u`: cut by the assistant.
   - `d`: needle drop.
   The Check column flags a stitch with no or several `n`, a stitch outside any block,
   an `n` outside a stitch, a stitch with no cut or two cuts, and a cut with no stitch before it.
   Open the page with `?practice` to test without saving anything.
3. Watch at 2-3x speed (`]`), and slow down (`[`) near each start and end.
4. Export one CSV per video into `results/annotations/`.
5. Times are video seconds. `results/sync/offsets.csv` converts them to bag time.

## Checks

- One person annotates everything.
- That person re-does 2 videos (one per system) a week later.
  We report how well the two passes agree (stitch durations, ICC).
- Stitch counts are checked against the surgeon's notes, if any.

## Analysis

- `scripts/suture_times.py` reads the CSVs. It writes one row per stitch:
  video, system, pig, block, stitch number, start, end, duration, bite time, knot time, assistant access time.
- Also one row per block: video, system, block, duration, number of stitches.
- Report median and range per system, for stitch time and for each block's duration, with every value shown.
- Model: stitch duration ~ system + block, with pig as a random effect.
  With 2 vs 4 pigs this is mostly descriptive.
- Also look at stitch number, for a learning effect within one surgery.

## Procedure notes

- Jun 15 (3 mm): no muscle repair was done, so it has no muscle_repair block (confirmed 2026-10-20).
  Muscle repair comparisons use the pigs that had one.

## Questions for the team

- Are knots tied with instruments in every case?
- Do the May pilot videos get annotated at all?

## Steps

1. Annotator: muscle / hard palate / soft palate blocks, stitch key, checks, timeline strip. (done 2026-10-19)
2. Annotate one 3 mm (Jun 16) and one 8 mm (Oct 8) video by hand, then review the definitions together.
3. Check whether grasp and roll patterns line up with the hand-marked stitches.
   If they do: add suggested stitch boundaries, and faster playback outside likely suturing.
4. Annotate the rest.
5. Write `scripts/suture_times.py` and the figures.
