"""Knot throws: throws per knot and time per throw, 3 mm vs 8 mm.

Usage:
    python scripts/knot_throws.py [median|mode]     (default: median)

Needs results/sutures/stitches.csv (scripts/suture_times.py) and results/sutures/knot_throws.csv
(exported from tools/knot_count.html). Counts are matched to stitches by video and knot start time
(within MATCH_S), not by stitch number, so relabelled stitches keep the right count.

Time per throw = knot tying time (needle through to knot tightened) / throws.

Two summaries, to compare:
    median  median (IQR) per system; dashed median lines in the time panel.
    mode    most likely value: the most common count for throws, and the main peak of the smoothed density
            (Gaussian kernel, SMOOTHING_S wide) for times, medians alongside. Only the main peak is used:
            secondary peaks change with the smoothing width and are not reliable with 23-39 knots.
Per pig there are only 4-13 knots, so pigs are always summarised by medians.

Output, in results/sutures/throws/<median|mode>/:
    knots.csv          one row per knot: pig, system, block, number, throws, knot time, time per throw
    by_system.csv      most likely values (modes, peaks) and medians per system
    by_pig.csv         medians per pig
    knot_throws.md     tables, figure link and caption
    figures/knot_throws.png and .pdf   (a) throws per knot, (b) time per throw; no title, caption in the md
"""

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from project import (GRID, MUTED, SYSTEM_COLORS, SYSTEM_NAMES, TEXT, pig_order, short_name,  # noqa: E402
                     system_by_video, use_figure_font)

STITCHES = Path("results/sutures/stitches.csv")
COUNTS = Path("results/sutures/knot_throws.csv")
BASE_DIR = Path("results/sutures/throws")
SUMMARIES = ["median", "mode"]
summary_kind = "median"  # set in main()
SYSTEMS = ["3mm", "8mm"]
MATCH_S = 2  # s, knot start times closer than this are the same knot
AXIS_STEP_S = 10  # s, the time axis of panel b ends on a multiple of this
SMOOTHING_S = 8  # s, kernel width of the smoothed time distributions
PEAK_PROMINENCE = 0.2  # a secondary peak must rise this share of the main peak above its surroundings
FIG_WIDTH = 7

use_figure_font()


# ---------- data ----------

def knot_table():
    """Completed stitches with their throw count, matched by video and knot start time."""
    stitches = pd.read_csv(STITCHES)
    stitches = stitches[~stitches.failed & stitches.knot_s.notna()].copy()
    stitches["knot_start_s"] = stitches.start_s + stitches.bite_s
    counts = pd.read_csv(COUNTS, keep_default_na=False)
    counts = counts[counts.throws != ""].assign(throws=lambda d: d.throws.astype(int))
    knots = pd.merge_asof(stitches.sort_values("knot_start_s"),
                          counts.sort_values("knot_start_s")[["video", "knot_start_s", "throws"]],
                          on="knot_start_s", by="video", direction="nearest", tolerance=MATCH_S)
    knots = knots.dropna(subset=["throws"]).assign(throws=lambda d: d.throws.astype(int))
    systems = system_by_video()
    knots["system"] = knots.video.map(systems)
    knots["pig"] = knots.video.map(short_name)
    knots["per_throw_s"] = knots.knot_s / knots.throws
    return knots[knots.system.isin(SYSTEMS)]


def by_pig(knots):
    """Medians per pig (too few knots per pig for a stable peak)."""
    pigs = knots.groupby(["system", "video", "pig"]).agg(
        knots=("throws", "size"), throws=("throws", "median"), knot_s=("knot_s", "median"),
        per_throw_s=("per_throw_s", "median")).reset_index()
    systems = system_by_video()
    return pigs.iloc[sorted(range(len(pigs)), key=lambda i: pig_order(pigs.video.iloc[i], systems))]


# ---------- most likely values ----------

def density(values, grid):
    """Gaussian kernel density with a fixed width of SMOOTHING_S seconds."""
    return gaussian_kde(values, bw_method=SMOOTHING_S / np.std(values, ddof=1))(grid)


def density_peaks(values):
    """Peak locations of the smoothed density, highest first."""
    grid = np.linspace(0, values.max() + 3 * SMOOTHING_S, 2000)
    curve = density(values, grid)
    found, props = find_peaks(curve, prominence=PEAK_PROMINENCE * curve.max())
    return list(grid[found[np.argsort(-curve[found])]])


def describe(values):
    """Median, quartiles and the main density peak of one measure."""
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    return {"median": median, "q1": q1, "q3": q3}


def system_summary(knots):
    rows = []
    for system in SYSTEMS:
        own = knots[knots.system == system]
        row = {"system": system, "knots": len(own), "pigs": own.pig.nunique(), "throws_mode": own.throws.mode().iloc[0],
               "per_throw_peak_s": density_peaks(own.per_throw_s.to_numpy())[0],
               "knot_peak_s": density_peaks(own.knot_s.to_numpy())[0]}
        for measure in ["throws", "knot_s", "per_throw_s"]:
            row.update({f"{measure}_{k}": v for k, v in describe(own[measure]).items()})
        rows.append(row)
    return pd.DataFrame(rows).set_index("system")


# ---------- figure ----------

def style_axes(ax, xlabel, ylabel):
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel, color=TEXT, fontsize=9)
    ax.set_ylabel(ylabel, color=TEXT, fontsize=9)


def throws_panel(ax, knots):
    """Share of knots with 1, 2, 3 ... throws, bars side by side; a marker above each system's median or mode."""
    values = np.arange(knots.throws.min(), knots.throws.max() + 1)
    width = 0.38
    shares = {}
    for i, system in enumerate(SYSTEMS):
        own = knots[knots.system == system].throws
        shares[system] = own.value_counts(normalize=True).reindex(values, fill_value=0) * 100
        ax.bar(values + (i - 0.5) * width, shares[system], width=width, color=SYSTEM_COLORS[system],
               label=SYSTEM_NAMES[system])
    top = max(share.max() for share in shares.values())
    for i, system in enumerate(SYSTEMS):
        own = knots[knots.system == system].throws
        value = own.median() if summary_kind == "median" else own.mode().iloc[0]
        ax.plot(value + (i - 0.5) * width, top * 1.08, marker="v", markersize=7, color=SYSTEM_COLORS[system])
    ax.set_ylim(0, top * 1.15)
    ax.set_xticks(values)
    style_axes(ax, "Throws per knot", "Share of knots (%)")


def per_throw_panel(ax, knots):
    """Smoothed distribution of time per throw, filled per system; dashed medians, or a marker over each peak."""
    top = np.ceil((knots.per_throw_s.max() + 2 * SMOOTHING_S) / AXIS_STEP_S) * AXIS_STEP_S
    grid = np.linspace(0, top, 400)
    curves = {}
    for system in SYSTEMS:
        own = knots[knots.system == system].per_throw_s.to_numpy()
        curves[system] = density(own, grid)  # probability density (1/s); area under each curve = 1
        ax.fill_between(grid, curves[system], color=SYSTEM_COLORS[system], alpha=0.15, linewidth=0)
        ax.plot(grid, curves[system], color=SYSTEM_COLORS[system], linewidth=2, label=SYSTEM_NAMES[system])
    height = max(c.max() for c in curves.values())
    for system in SYSTEMS:
        own = knots[knots.system == system].per_throw_s.to_numpy()
        if summary_kind == "median":
            ax.axvline(np.median(own), color=SYSTEM_COLORS[system], linewidth=1.2, linestyle="--")
        else:
            ax.plot(density_peaks(own)[0], height * 1.08, marker="v", markersize=7, color=SYSTEM_COLORS[system])
    ax.set_xlim(0, top)
    ax.set_ylim(0, height * 1.15)
    style_axes(ax, "Time per throw (s)", "Density (1/s)")


def figure(knots):
    fig, (left, right) = plt.subplots(1, 2, figsize=(FIG_WIDTH, 2.8))
    throws_panel(left, knots)
    per_throw_panel(right, knots)
    left.legend(frameon=False, fontsize=8, labelcolor=TEXT, loc="upper left")
    for ax, letter in [(left, "a"), (right, "b")]:
        ax.text(-0.14, 1.04, letter, transform=ax.transAxes, fontsize=10, fontweight="bold", color=TEXT)
    fig.tight_layout()
    figure_dir = OUT_DIR / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf"]:
        fig.savefig(figure_dir / f"knot_throws.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)
    return "figures/knot_throws.png"


# ---------- markdown ----------

def iqr_text(r, measure, fmt="{:.0f}"):
    median, q1, q3 = (getattr(r, f"{measure}_{k}") for k in ("median", "q1", "q3"))
    return f"{fmt.format(median)} ({fmt.format(q1)}-{fmt.format(q3)})"


def system_lines(summary):
    if summary_kind == "median":
        header = "| system | knots (pigs) | throws per knot | knot tying (s) | time per throw (s) |"
        cells = lambda r: [iqr_text(r, "throws"), iqr_text(r, "knot_s"), iqr_text(r, "per_throw_s")]
    else:
        header = "| system | knots (pigs) | throws per knot: most common | knot tying (s): peak | time per throw (s): peak |"
        cells = lambda r: [f"{r.throws_mode:.0f} (median {r.throws_median:.0f})",
                           f"{r.knot_peak_s:.0f} (median {r.knot_s_median:.0f})",
                           f"{r.per_throw_peak_s:.0f} (median {r.per_throw_s_median:.0f})"]
    lines = [header, "|---|---|---|---|---|"]
    for system, r in summary.iterrows():
        lines.append(f"| {SYSTEM_NAMES[system]} | {r.knots:.0f} ({r.pigs:.0f}) | " + " | ".join(cells(r)) + " |")
    return lines


SUMMARY_NOTES = {
    "median": "Median (interquartile range). All knots of a system are pooled.",
    "mode": ("Most likely value: the most common count for throws, and the main peak of the smoothed density for "
             "times. Medians alongside. All knots of a system are pooled. Secondary peaks are not reported: they "
             "change with the smoothing width and are not reliable with this many knots."),
}


def table_lines(table):
    lines = ["| pig | system | knots | throws | knot tying (s) | time per throw (s) |", "|---|---|---|---|---|---|"]
    for r in table.itertuples():
        cells = [r.pig, SYSTEM_NAMES[r.system], f"{r.knots:.0f}", f"{r.throws:.1f}", f"{r.knot_s:.0f}",
                 f"{r.per_throw_s:.0f}"]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def distribution_lines(knots):
    counts = knots.groupby("system").throws.value_counts().unstack(fill_value=0)
    header = "| system | " + " | ".join(f"{c} throws" for c in counts.columns) + " |"
    lines = [header, "|" + "---|" * (len(counts.columns) + 1)]
    for system, row in counts.iterrows():
        lines.append(f"| {SYSTEM_NAMES[system]} | " + " | ".join(str(v) for v in row) + " |")
    return lines


def limitation_lines(knots):
    """Knot tying includes pulling the thread through, which is slower with fresh, long suture."""
    knots = knots.sort_values(["video", "start_s"])
    first = knots.groupby(["video", "block"]).cumcount() == 0
    medians = knots.groupby([knots.system, first]).agg(knot=("knot_s", "median"), per_throw=("per_throw_s", "median"))
    lines = ["## Limitations", "",
             "Knot tying is timed from needle through to knot tightened, so it includes pulling the thread all the "
             "way through after the bite. With fresh, long suture this takes longer and is not throwing, so early "
             "knots and their time per throw are overestimated. The first knot of each block is slower:", "",
             "| system | knot tying, first of block (s) | later (s) | time per throw, first of block (s) | later (s) |",
             "|---|---|---|---|---|"]
    for system in SYSTEMS:
        f, later = medians.loc[(system, True)], medians.loc[(system, False)]
        lines.append(f"| {SYSTEM_NAMES[system]} | {f.knot:.0f} | {later.knot:.0f} | {f.per_throw:.0f} | "
                     f"{later.per_throw:.0f} |")
    return lines + ["", "Medians. Thread length was not recorded, so this is indirect evidence."]


def marker_caption(t3, t8):
    if summary_kind == "median":
        return (f"Triangles (a) and dashed lines (b): medians, {t3.throws_median:.0f} vs {t8.throws_median:.0f} "
                f"throws and {t3.per_throw_s_median:.0f} s vs {t8.per_throw_s_median:.0f} s per throw.")
    return (f"Triangles: most likely value, {t3.throws_mode:.0f} vs {t8.throws_mode:.0f} throws and "
            f"{t3.per_throw_peak_s:.0f} s vs {t8.per_throw_peak_s:.0f} s per throw.")


def markdown(knots, summary, table, figure_path):
    t3, t8 = summary.loc["3mm"], summary.loc["8mm"]
    caption = (f"**Knot throws, 3 mm vs 8 mm.** (a) Share of knots by number of throws. (b) Time per throw: knot "
               f"tying time (needle through to knot tightened) divided by the number of throws, shown as a probability "
               f"density (Gaussian kernel {SMOOTHING_S} s wide; the area under each curve is 1). Purple: 3 mm ({t3.knots:.0f} knots, {t3.pigs:.0f} pigs). Teal: 8 mm "
               f"({t8.knots:.0f} knots, {t8.pigs:.0f} pigs). {marker_caption(t3, t8)} "
               f"Throws were counted from video clips of each knot.")
    lines = ["# Knot throws", "", "Written by `scripts/knot_throws.py`; re-run it after new counts.", "",
             f"![Knot throws]({figure_path})", "", caption, "", "## Per system", ""]
    lines += system_lines(summary)
    lines += ["", SUMMARY_NOTES[summary_kind], "", "## Per pig (medians)", ""]
    lines += table_lines(table) + ["", "## Knots by number of throws", ""] + distribution_lines(knots)
    lines += [""] + limitation_lines(knots) + [""]
    (OUT_DIR / "knot_throws.md").write_text("\n".join(lines))


def main():
    global summary_kind, OUT_DIR
    summary_kind = sys.argv[1] if len(sys.argv) > 1 else "median"
    if summary_kind not in SUMMARIES:
        raise SystemExit(f"summary must be one of {SUMMARIES}")
    OUT_DIR = BASE_DIR / summary_kind
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    knots = knot_table()
    table = by_pig(knots)
    summary = system_summary(knots)
    summary.round(1).to_csv(OUT_DIR / "by_system.csv")
    knots[["pig", "system", "block", "number", "throws", "knot_s", "per_throw_s", "video"]].round(1).to_csv(
        OUT_DIR / "knots.csv", index=False)
    table.round(2).to_csv(OUT_DIR / "by_pig.csv", index=False)
    markdown(knots, summary, table, figure(knots))
    print(summary.round(1).to_string())


if __name__ == "__main__":
    main()
