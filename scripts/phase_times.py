"""Stitch phase times, 3 mm vs 8 mm: bite, knot tying and assistant.

Needs results/sutures/stitches.csv (scripts/suture_times.py).

Phases per completed stitch:
    bite         stitch start to needle through
    knot tying   needle through to knot tightened
    assistant    knot tightened to cut (the May 29 outlier is already removed in stitches.csv)

The times are skewed (a few bites take over 10 min), so each stitch is shown as a dot with the median and
interquartile range, rather than a smoothed density whose long tails would flatten the peaks.

Output, in results/sutures/phase_times/:
    by_system.csv     median (IQR) per phase and system
    phase_times.md    table, figure link and caption
    figures/phase_times.png and .pdf   one panel per phase; no title, caption in the md
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from project import GRID, MUTED, SYSTEM_COLORS, SYSTEM_NAMES, TEXT, system_by_video, use_figure_font  # noqa: E402

STITCHES = Path("results/sutures/stitches.csv")
OUT_DIR = Path("results/sutures/phase_times")
SYSTEMS = ["3mm", "8mm"]
PHASES = {"bite_s": "Bite", "knot_s": "Knot tying", "assistant_s": "Assistant"}
JITTER = 0.12  # half width of the dot spread around each system's position
BOX_WIDTH = 0.5
FIG_WIDTH = 7
SEED = 0

use_figure_font()


def stitch_table():
    """Completed stitches of the main trials, with their system."""
    stitches = pd.read_csv(STITCHES)
    stitches = stitches[~stitches.failed].copy()
    stitches["system"] = stitches.video.map(system_by_video())
    return stitches[stitches.system.isin(SYSTEMS)]


def summary(stitches):
    rows = []
    for system in SYSTEMS:
        for column, name in PHASES.items():
            values = stitches.loc[stitches.system == system, column].dropna()
            q1, median, q3 = np.percentile(values, [25, 50, 75])
            rows.append({"system": system, "phase": name, "n": len(values), "pigs": stitches[stitches.system == system].video.nunique(),
                         "median_s": median, "q1_s": q1, "q3_s": q3})
    return pd.DataFrame(rows)


# ---------- figure ----------

def style_axes(ax, title):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(title, color=TEXT, fontsize=9)


def phase_panel(ax, stitches, column, rng):
    """One dot per stitch, an IQR box and a thick median line per system."""
    for x, system in enumerate(SYSTEMS):
        values = stitches.loc[stitches.system == system, column].dropna().to_numpy() / 60
        color = SYSTEM_COLORS[system]
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        ax.add_patch(plt.Rectangle((x - BOX_WIDTH / 2, q1), BOX_WIDTH, q3 - q1, facecolor=color, alpha=0.15,
                                   edgecolor=color, linewidth=1))
        ax.plot([x - BOX_WIDTH / 2, x + BOX_WIDTH / 2], [median, median], color=color, linewidth=2.5)
        ax.scatter(x + rng.uniform(-JITTER, JITTER, len(values)), values, s=12, color=color, alpha=0.7,
                   linewidths=0)
    ax.set_xlim(-0.6, len(SYSTEMS) - 0.4)
    ax.set_ylim(bottom=0)
    ax.set_xticks(range(len(SYSTEMS)), [SYSTEM_NAMES[s] for s in SYSTEMS])
    style_axes(ax, PHASES[column])


def figure(stitches):
    rng = np.random.default_rng(SEED)
    fig, axes = plt.subplots(1, len(PHASES), figsize=(FIG_WIDTH, 2.8))
    for ax, column, letter in zip(axes, PHASES, "abc"):
        phase_panel(ax, stitches, column, rng)
        ax.text(-0.22, 1.04, letter, transform=ax.transAxes, fontsize=10, fontweight="bold", color=TEXT)
    axes[0].set_ylabel("Time per stitch (min)", color=TEXT, fontsize=9)
    fig.tight_layout()
    figure_dir = OUT_DIR / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf"]:
        fig.savefig(figure_dir / f"phase_times.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)
    return "figures/phase_times.png"


# ---------- markdown ----------

def markdown(table, figure_path):
    counts = table.groupby("system")[["n", "pigs"]].max()
    t3, t8 = counts.loc["3mm"], counts.loc["8mm"]
    caption = ("**Stitch phase times, 3 mm vs 8 mm.** (a) Bite: stitch start to needle through. (b) Knot tying: "
               "needle through to knot tightened. (c) Assistant: knot tightened to cut by the surgical assistant. "
               f"Each dot is one completed stitch; boxes show the interquartile range and thick lines the median. "
               f"Purple: 3 mm (up to {t3.n:.0f} stitches, {t3.pigs:.0f} pigs). Teal: 8 mm ({t8.n:.0f} stitches, "
               f"{t8.pigs:.0f} pigs). One 3 mm assistant time (May 29) is left out as an outlier.")
    lines = ["# Stitch phase times", "", "Written by `scripts/phase_times.py`; re-run it after new annotations.", "",
             f"![Stitch phase times]({figure_path})", "", caption, "", "## Median (IQR), minutes", "",
             "| phase | 3 mm | 8 mm |", "|---|---|---|"]
    for name in PHASES.values():
        cells = []
        for system in SYSTEMS:
            r = table[(table.system == system) & (table.phase == name)].iloc[0]
            cells.append(f"{r.median_s / 60:.1f} ({r.q1_s / 60:.1f}-{r.q3_s / 60:.1f}), n = {r.n:.0f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "All completed stitches of a system pooled. Pigs: 3 mm May 29, Jun 15, Jun 16; "
              "8 mm Aug 18, Aug 19, Oct 7, Oct 8.", ""]
    (OUT_DIR / "phase_times.md").write_text("\n".join(lines))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stitches = stitch_table()
    table = summary(stitches)
    table.round(1).to_csv(OUT_DIR / "by_system.csv", index=False)
    markdown(table, figure(stitches))
    print(table.round(0).to_string(index=False))


if __name__ == "__main__":
    main()
