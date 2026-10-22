"""Combined suture figure for the manuscript, single column, three stacked panels (draft).

Usage:
    python scripts/suture_figure.py

    a  Suture phases: needle passage, knot tying and assistant time per stitch, 3 mm vs 8 mm side by side.
       Dots per stitch, IQR box, median line. Log time axis: phases differ tenfold and needle passage has
       a long tail (up to 14 min), so a linear axis would flatten the assistant times.
    b  Throws per knot: share of knots, grouped bars, a triangle over each system's most common count.
    c  Time per throw: probability density (Gaussian kernel, knot_throws.SMOOTHING_S wide), a triangle
       over each system's main peak (mode).

Data come from scripts/phase_times.py and scripts/knot_throws.py, so the numbers match their tables.
Drawn at COLUMN_IN wide, so the PDF can be placed at 100 % and the text stays at FONT_PT.

Output, in results/sutures/combined/:
    suture_figure.png and .pdf   no title, caption in suture_figure.md
    suture_figure.md             figure link and caption
"""

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

import knot_throws as kt  # noqa: E402
import phase_times as pt  # noqa: E402
from project import GRID, MUTED, SYSTEM_COLORS, SYSTEM_NAMES, TEXT  # noqa: E402

OUT_DIR = Path("results/sutures/combined")
SYSTEMS = ["3mm", "8mm"]
PHASES = {"bite_s": "Needle\npassage", "knot_s": "Knot\ntying", "assistant_s": "Assistant"}
COLUMN_IN = 3.35  # single journal column (8.5 cm)
HEIGHT_IN = 6.6
FONT_PT, TICK_PT = 8, 7
OFFSET = 0.2  # each system's distance from the phase position
BOX_WIDTH = 0.32
JITTER = 0.07
TIME_TICKS_MIN = [0.25, 0.5, 1, 2, 5, 10]
SEED = 0


def style_axes(ax, xlabel, ylabel):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=TICK_PT)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel, color=TEXT, fontsize=FONT_PT)
    ax.set_ylabel(ylabel, color=TEXT, fontsize=FONT_PT)


def marker(ax, x, y, system):
    ax.plot(x, y, marker="v", markersize=5, color=SYSTEM_COLORS[system], linestyle="none")


# ---------- panels ----------

def phase_panel(ax, stitches):
    """Per phase, the two systems side by side: dots per stitch, IQR box, median line (minutes, log axis)."""
    rng = np.random.default_rng(SEED)
    for p, column in enumerate(PHASES):
        for i, system in enumerate(SYSTEMS):
            values = stitches.loc[stitches.system == system, column].dropna().to_numpy() / 60
            x, color = p + (i - 0.5) * 2 * OFFSET, SYSTEM_COLORS[system]
            q1, median, q3 = np.percentile(values, [25, 50, 75])
            ax.add_patch(plt.Rectangle((x - BOX_WIDTH / 2, q1), BOX_WIDTH, q3 - q1, facecolor=color, alpha=0.15,
                                       edgecolor=color, linewidth=0.8))
            ax.plot([x - BOX_WIDTH / 2, x + BOX_WIDTH / 2], [median, median], color=color, linewidth=2)
            ax.scatter(x + rng.uniform(-JITTER, JITTER, len(values)), values, s=7, color=color, alpha=0.7,
                       linewidths=0, label=SYSTEM_NAMES[system] if p == 0 else None)
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator(TIME_TICKS_MIN))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_yticklabels([f"{t:g}" for t in TIME_TICKS_MIN])
    ax.set_ylim(0.2, 16)
    ax.set_xlim(-0.55, len(PHASES) - 0.45)
    ax.set_xticks(range(len(PHASES)), list(PHASES.values()))
    style_axes(ax, "", "Time per stitch (min)")
    ax.tick_params(axis="x", length=0)


def throws_panel(ax, knots):
    """Share of knots by throw count, grouped bars; a triangle over each system's most common count."""
    values = np.arange(knots.throws.min(), knots.throws.max() + 1)
    width = 0.38
    shares = {s: knots[knots.system == s].throws.value_counts(normalize=True).reindex(values, fill_value=0) * 100
              for s in SYSTEMS}
    top = max(share.max() for share in shares.values())
    for i, system in enumerate(SYSTEMS):
        ax.bar(values + (i - 0.5) * width, shares[system], width=width, color=SYSTEM_COLORS[system])
        mode = knots[knots.system == system].throws.mode().iloc[0]
        marker(ax, mode + (i - 0.5) * width, top * 1.1, system)
    ax.set_ylim(0, top * 1.18)
    ax.set_xticks(values)
    style_axes(ax, "Throws per knot", "Knots (%)")


def per_throw_panel(ax, knots):
    """Smoothed density of time per throw; a triangle over each system's main peak."""
    top = np.ceil((knots.per_throw_s.max() + 2 * kt.SMOOTHING_S) / kt.AXIS_STEP_S) * kt.AXIS_STEP_S
    grid = np.linspace(0, top, 400)
    curves = {}
    for system in SYSTEMS:
        own = knots[knots.system == system].per_throw_s.to_numpy()
        curves[system] = kt.density(own, grid)
        ax.fill_between(grid, curves[system], color=SYSTEM_COLORS[system], alpha=0.15, linewidth=0)
        ax.plot(grid, curves[system], color=SYSTEM_COLORS[system], linewidth=1.5)
    height = max(c.max() for c in curves.values())
    for system in SYSTEMS:
        peak = kt.density_peaks(knots[knots.system == system].per_throw_s.to_numpy())[0]
        marker(ax, peak, height * 1.1, system)
    ax.set_xlim(0, top)
    ax.set_ylim(0, height * 1.18)
    style_axes(ax, "Time per throw (s)", "Density (1/s)")


# ---------- figure and caption ----------

def figure(stitches, knots):
    fig, axes = plt.subplots(3, 1, figsize=(COLUMN_IN, HEIGHT_IN), gridspec_kw={"height_ratios": [1.3, 1, 1]})
    phase_panel(axes[0], stitches)
    throws_panel(axes[1], knots)
    per_throw_panel(axes[2], knots)
    axes[0].legend(frameon=False, fontsize=TICK_PT, labelcolor=TEXT, loc="upper right", ncol=2, markerscale=1.6,
                   handletextpad=0.2, columnspacing=0.8)
    for ax, letter in zip(axes, "abc"):
        ax.text(-0.2, 1.02, letter, transform=ax.transAxes, fontsize=FONT_PT + 1, fontweight="bold", color=TEXT)
    fig.tight_layout(h_pad=1.2)
    fig.align_ylabels(axes)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf"]:
        fig.savefig(OUT_DIR / f"suture_figure.{suffix}", dpi=300)  # no tight bbox: keep the exact column width
    plt.close(fig)


def caption(stitches, knots):
    n = {s: (stitches[stitches.system == s].shape[0], stitches[stitches.system == s].video.nunique(),
             (knots.system == s).sum()) for s in SYSTEMS}
    modes = {s: knots[knots.system == s].throws.mode().iloc[0] for s in SYSTEMS}
    peaks = {s: kt.density_peaks(knots[knots.system == s].per_throw_s.to_numpy())[0] for s in SYSTEMS}
    return (f"**Suturing with 3 mm and 8 mm instruments.** (a) Time per stitch in each phase: needle passage (stitch "
            f"start to needle through), knot tying (needle through to knot tightened) and assistant (knot tightened to "
            f"cut). Each dot is one completed stitch; boxes show the interquartile range and lines the median. "
            f"Logarithmic time axis. (b) Share of knots by number of throws; triangles mark the most common count "
            f"({modes['3mm']:.0f} for 3 mm, {modes['8mm']:.0f} for 8 mm). (c) Time per throw (knot tying time divided by throws), shown as "
            f"a probability density (Gaussian kernel {kt.SMOOTHING_S} s wide; area under each curve is 1); triangles "
            f"mark the main peak ({peaks['3mm']:.0f} s for 3 mm, {peaks['8mm']:.0f} s for 8 mm). Purple: 3 mm "
            f"({n['3mm'][0]} stitches, {n['3mm'][2]} knots counted, {n['3mm'][1]} pigs). Teal: 8 mm ({n['8mm'][0]} "
            f"stitches, {n['8mm'][2]} knots counted, {n['8mm'][1]} pigs). One 3 mm assistant time "
            f"({pt.excluded_assistant_cases(stitches)}) is left out as an outlier.")


def main():
    stitches = pt.stitch_table()
    knots = kt.knot_table()
    figure(stitches, knots)
    lines = ["# Suture figure (draft)", "", "Written by `scripts/suture_figure.py`.", "",
             "![Suture figure](suture_figure.png)", "", caption(stitches, knots), "",
             "Vector version: [suture_figure.pdf](suture_figure.pdf)", ""]
    (OUT_DIR / "suture_figure.md").write_text("\n".join(lines))
    print("saved to", OUT_DIR)


if __name__ == "__main__":
    main()
