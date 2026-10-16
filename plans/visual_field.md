# Plan: visual field occlusion

## Goal

Measure how much of the camera image the instruments cover.
Compare 3 mm and 8 mm.

## Measure

- **Occlusion:** the share of the image covered by robotic instruments (shaft, wrist and jaws).
- Use the left eye only, below the window title bar.
- Do not count the retractor, teeth, needle or suture.
- Report it per frame, then summarise per surgical step and per stitch.
  Main number: median occlusion during suturing.

## Problem: camera distance

The camera was not always at the same distance from the tissue.
A closer camera makes every tool look bigger.

- Report occlusion as is: it is what the surgeon actually saw.
  The surgeon chose the camera position for each system, so this is the clinically relevant view.
- Mention camera position in the limitations.
- Optional (decided 2026-10-16): a size check from the shaft width in pixels near the tip.
  Only if a reviewer asks whether the camera was closer for one system.

## How the tools are found

Colour alone is not enough: teeth and the retractor are also grey and white.

1. **Sample frames.** Take about 150 frames spread over all 6 videos, only while tools are in view.
2. **Label them.** Draw tool masks with click-assisted segmentation (SAM 2) on the GPU.
   A person clicks on each tool; the model fills in the mask; the person corrects it.
3. **Train.** Fine-tune a small segmentation model on about 120 frames.
   Keep about 30 frames to test it.
4. **Check.** Target: over 0.85 overlap (IoU) with the hand labels on the test frames.
5. **Run.** Apply it to 1 frame per second over each whole video (scripts/occlusion.py).
   Then summarise inside the annotated steps, once they exist.

Quick baseline first: a colour threshold on a few frames.
It shows how hard the problem is, and gives a first rough number.

## Analysis

- `scripts/occlusion.py` writes one row per second: video time, bag time, occlusion.
- Report median and range per system, per step.
- Plots: occlusion over time for each video; per-system boxplots.
- Example figure: the same step in 3 mm and 8 mm, with tool masks drawn on.

## Needs

- Python packages: `torch`, `opencv`, and SAM 2 (into the `tors1` env).
- Step annotations (from the suture-timing work) to choose the windows.

## Steps

1. Sample frames and run the colour baseline. (now)
2. Install the packages and set up click-assisted labelling.
3. Label, train, check.
4. Run on all videos and write the analysis.
