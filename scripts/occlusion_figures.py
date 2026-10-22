"""Figures for the visual field comparison (3 mm vs 8 mm), plus a markdown file of captions.

Usage:
    python scripts/occlusion_figures.py

The images carry no titles or captions, so they can be placed anywhere;
results/occlusion/figures/figures.md links each image with its caption and numbers.

1. occlusion_distribution: share of the image covered by instruments, per frame,
   for 3 mm and 8 mm (main trials, frames pooled by system). Black frames and frames
   with no instrument in view (under IN_VIEW, e.g. tool swaps) are dropped.
2. occlusion_example_8mm / _3mm: one suturing frame per system, left eye at full size,
   with the instrument mask shaded. Picked by eye (see EXAMPLES).

Output: results/occlusion/figures/
"""

import subprocess
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from scipy.stats import gaussian_kde

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from project import GRID, LEFT_EYE, MUTED, SYSTEM_COLORS, TEXT, VIDEO_DIR, case_id, use_figure_font  # noqa: E402
from train_tool_seg import MODEL_FILE, SIZE, make_model, normalise  # noqa: E402

use_figure_font()

OCCLUSION_DIR = Path("data/derived/occlusion/video")
RESULT_DIR = Path("results/occlusion")
FIGURE_DIR = RESULT_DIR / "figures"
DARK = 20
IN_VIEW = 1  # % of the image
SMOOTHING = 1.5  # points of occlusion; kernel width of the smoothed distribution
# 3 mm purple, 8 mm teal (project.SYSTEM_COLORS). The masks in the example images use the same colours,
# so plot and images match; teal stays visible on the grey metal of the 8 mm instruments.
COLORS = SYSTEM_COLORS
COLOR_NAMES = {"3mm": "purple", "8mm": "teal"}
NAMES = {"3mm": "3 mm", "8mm": "8 mm"}
EXAMPLES = [  # (system, video, time in s, how it was picked, output file)
    ("8mm", "pig_oct07-2026-10-07_14.31.12", 6462,
     "picked by eye from {case} frames at 26-27% (per-second values)", "occlusion_example_8mm.png"),
    ("3mm", "pig_may29-2026-05-29_09.34.18", 6127,
     "picked by eye from 3 mm frames at 10-12% (per-second values)", "occlusion_example_3mm.png"),
    ("3mm", "pig_jun15-2026-06-15_10.14.18", 4828,
     "backup for the 3 mm example; picked by eye from 3 mm frames at 10-12%", "occlusion_example_3mm_backup.png"),
]


# ---------- figure 1: distribution ----------

def frames_by_system():
    segments = pd.read_csv(RESULT_DIR / "segments.csv").query("trial == 'main'")
    frames = {}
    for segment in segments.itertuples():
        d = pd.read_parquet(OCCLUSION_DIR / f"{segment.video}.parquet")
        occlusion = d[d.brightness >= DARK].occlusion * 100
        frames.setdefault(segment.system, []).append(occlusion[occlusion >= IN_VIEW])
    return {system: pd.concat(parts) for system, parts in frames.items()}, \
        {system: len(parts) for system, parts in frames.items()}


def style_axes(ax):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def smoothed_density(values, grid):
    """Gaussian kernel density with a fixed width of SMOOTHING points (per percentage point; area = 1)."""
    kde = gaussian_kde(values, bw_method=SMOOTHING / values.std(ddof=1))
    return kde(grid)


def distribution_figure():
    """Draw the distribution; return per-system numbers for the caption."""
    values, pigs = frames_by_system()
    grid = np.linspace(0, 60, 601)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    stats = {}
    for system in sorted(values):
        share = smoothed_density(values[system].to_numpy(), grid)
        ax.fill_between(grid, share, color=COLORS[system], alpha=0.12, linewidth=0)
        ax.plot(grid, share, color=COLORS[system], linewidth=2, label=NAMES[system])
        median = values[system].median()
        ax.axvline(median, color=COLORS[system], linewidth=1.2, linestyle="--")
        stats[system] = {"median": median, "pigs": pigs[system], "frames": len(values[system])}
    style_axes(ax)
    ax.set_xlim(0, 60)
    ax.set_xlabel("Share of the camera image covered by instruments (%)", color=TEXT, fontsize=10)
    ax.set_ylabel("Density (per % of image)", color=TEXT, fontsize=10)
    ax.legend(frameon=False, fontsize=9, loc="upper right", labelcolor=TEXT)
    for suffix in ["png", "pdf"]:
        fig.savefig(FIGURE_DIR / f"occlusion_distribution.{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return stats


# ---------- figure 2: example frames ----------

def read_frame(video, t):
    command = ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(VIDEO_DIR / f"{video}.mp4"),
               "-frames:v", "1", "-vf", LEFT_EYE, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1040, 960, 3)


def frame_mask(model, frame):
    image = torch.from_numpy(frame.copy()).permute(2, 0, 1).float()[None].cuda() / 255
    small = F.interpolate(image, size=SIZE, mode="bilinear", align_corners=False)
    with torch.inference_mode():
        logits = model(normalise(small))["out"]
    return (F.interpolate(logits, size=frame.shape[:2], mode="bilinear")[0, 0] > 0).cpu().numpy()


def overlay(frame, mask, color):
    rgb = np.array(matplotlib.colors.to_rgb(color)) * 255
    out = frame.astype(float)
    out[mask] = 0.55 * out[mask] + 0.45 * rgb
    return out.astype(np.uint8)


def example_images():
    """Save one masked frame per system; return what the captions need."""
    model = make_model()
    model.load_state_dict(torch.load(MODEL_FILE))
    model.eval()
    examples = []
    for system, video, t, picked, name in EXAMPLES:
        frame = read_frame(video, t)
        mask = frame_mask(model, frame)
        Image.fromarray(overlay(frame, mask, COLORS[system])).save(FIGURE_DIR / name)
        examples.append({"system": system, "video": video, "t": t, "picked": picked,
                         "covered": mask.mean() * 100, "file": name})
    return examples


# ---------- captions ----------

def pig_level_line(system):
    table = pd.read_csv(RESULT_DIR / "summary_by_system.csv").query("trials == 'main trials' and system == @system")
    row = table.iloc[0]
    return f"{100 * row['median']:.1f}% (range {100 * row['min']:.1f}-{100 * row['max']:.1f}%)"


def write_markdown(stats, examples):
    s3, s8 = stats["3mm"], stats["8mm"]
    lines = [
        "# Visual field figures",
        "",
        "Written by `scripts/occlusion_figures.py`; re-run it to update the images and numbers.",
        "",
        "## Occlusion distribution",
        "",
        "![Occlusion distribution](occlusion_distribution.png)",
        "",
        f"**Instrument occlusion of the camera view, 3 mm vs 8 mm tools.** "
        f"Share of the left-eye camera image covered by the robotic instruments, per video frame "
        f"(1 frame per second, frames with instruments in view), shown as a probability density "
        f"(Gaussian kernel {SMOOTHING} points wide; the area under each curve is 1). "
        f"Purple: 3 mm ({s3['pigs']} pigs, {s3['frames']:,} frames). "
        f"Teal: 8 mm ({s8['pigs']} pigs, {s8['frames']:,} frames). "
        f"Dashed lines: medians, {s3['median']:.1f}% (3 mm) and {s8['median']:.1f}% (8 mm). "
        f"Median of the per-pig medians: 3 mm {pig_level_line('3mm')}, 8 mm {pig_level_line('8mm')}. "
        f"Instruments were segmented with a DeepLabV3 model trained on 120 hand-labelled frames.",
        "",
        "Vector version: [occlusion_distribution.pdf](occlusion_distribution.pdf)",
        "",
        "## Example frames",
        "",
    ]
    for ex in examples:
        if "backup" in ex["file"]:
            lines += ["## Backup example", ""]
        lines += [
            f"![{NAMES[ex['system']]} example]({ex['file']})",
            "",
            f"**{NAMES[ex['system']]} tools during suturing.** Instrument mask shaded "
            f"({COLOR_NAMES[ex['system']]}); "
            f"{ex['covered']:.0f}% of the image is covered. "
            f"Source: {case_id(ex['video'])} at {ex['t']} s of video, left eye; {ex['picked'].format(case=case_id(ex['video']))}.",
            "",
        ]
    (FIGURE_DIR / "figures.md").write_text("\n".join(lines))


def main():
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    stats = distribution_figure()
    examples = example_images()
    write_markdown(stats, examples)
    print("saved to", FIGURE_DIR)


if __name__ == "__main__":
    main()
