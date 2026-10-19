"""Stitch timing from annotator exports: tables, a timeline figure and a markdown summary.

Usage:
    python scripts/suture_times.py [annotation.csv ...]

Defaults to every results/annotations/*_events.csv (Export CSV from tools/annotator.html).

Per stitch (x ... x), with its needle_through (n) and the assistant's cut (u):
    bite       start -> needle through (the last n inside the stitch, i.e. the final pass)
    knot       needle through -> end (last throw tightened)
    assistant  end -> cut (the cut paired with the stitch that most recently ended before it)
    gap        end -> start of the next stitch
Each stitch belongs to the block (muscle_repair, soft_palate, hard_palate) containing its start.

Output, in results/sutures/:
    stitches.csv, blocks.csv, summary.csv
    figures/timeline_<video>.png and .pdf   one detailed timeline per pig
    figures/overview.png and .pdf           all pigs stacked, 3 mm then 8 mm, aligned at the first stitch
    sutures.md   tables, figure links and captions
"""

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

import matplotlib.font_manager  # noqa: E402

# Journal look: Arial-style sans-serif (Arial if installed, else Liberation Sans, which has Arial's metrics).
INSTALLED_FONTS = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next(f for f in ["Arial", "Liberation Sans", "DejaVu Sans"] if f in INSTALLED_FONTS)

ANNOTATION_DIR = Path("results/annotations")
OUT_DIR = Path("results/sutures")
SEGMENTS_FILE = Path("results/occlusion/segments.csv")  # which system each video used
BLOCKS = ["muscle_repair", "soft_palate", "hard_palate"]
PHASE_EVENTS = ["dissection", "incision"] + BLOCKS
PHASES = ["bite", "knot", "assistant"]
# One-hue purple ramp around #842996 (the knot colour), dark -> light, so the three stages of a stitch
# read as one family and still separate in greyscale. Contrast on white: 12.5, 7.7 and 2.8 to 1.
PHASE_COLORS = {"bite": "#531a5e", "knot": "#842996", "assistant": "#cc7ddb"}
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


# ---------- tables ----------

def load_events(path):
    events = pd.read_csv(path, keep_default_na=False)
    events["video"] = events.video.str.replace(".mp4", "", regex=False)
    return events.sort_values("start_s", ignore_index=True)


def block_of(t, blocks):
    inside = blocks[(blocks.start_s <= t) & (t <= blocks.end_s)]
    return inside.event.iloc[0] if len(inside) else "no block"


def paired_cut(stitch_end, stitches, cuts):
    """The cut whose most recently ended stitch is this one (first such cut), or NaN."""
    for cut in cuts:
        ended = stitches[stitches.end_s <= cut]
        if len(ended) and ended.end_s.max() == stitch_end:
            return cut
    return np.nan


def stitch_table(events):
    stitches = events[events.event == "stitch"].reset_index(drop=True)
    needles = events[events.event == "needle_through"].start_s.to_numpy()
    cuts = events[events.event == "cut"].start_s.to_numpy()
    blocks = events[events.event.isin(BLOCKS)]
    rows = []
    for i, s in stitches.iterrows():
        inside = needles[(needles >= s.start_s) & (needles <= s.end_s)]
        needle = inside.max() if len(inside) else np.nan
        cut = paired_cut(s.end_s, stitches, cuts)
        next_start = stitches.start_s.iloc[i + 1] if i + 1 < len(stitches) else np.nan
        rows.append({
            "video": s.video, "block": block_of(s.start_s, blocks), "start_s": s.start_s, "end_s": s.end_s,
            "stitch_s": s.end_s - s.start_s, "bite_s": needle - s.start_s, "knot_s": s.end_s - needle,
            "assistant_s": cut - s.end_s, "gap_s": next_start - s.end_s,
            "needle_marks": len(inside), "cut_s": cut, "note": s.note,
        })
    table = pd.DataFrame(rows)
    table.insert(2, "number", table.groupby("block").cumcount() + 1)
    return table


def block_table(events, stitches):
    rows = []
    for b in events[events.event.isin(BLOCKS)].itertuples():
        own = stitches[stitches.block == b.event]
        rows.append({"video": b.video, "block": b.event, "start_s": b.start_s, "end_s": b.end_s,
                     "duration_s": b.end_s - b.start_s, "stitches": len(own),
                     "stitching_pct": 100 * own.stitch_s.sum() / (b.end_s - b.start_s)})
    return pd.DataFrame(rows)


def summary_table(stitches):
    rows = []
    order = [b for b in BLOCKS if b in set(stitches.block)]
    groups = [("all blocks", stitches)] + [(name, stitches[stitches.block == name]) for name in order]
    for name, group in groups:
        for measure in ["stitch_s", "bite_s", "knot_s", "assistant_s", "gap_s"]:
            values = group[measure].dropna()
            rows.append({"block": name, "measure": measure.replace("_s", ""), "n": len(values),
                         "mean_s": values.mean(), "sd_s": values.std(), "median_s": values.median(),
                         "min_s": values.min(), "max_s": values.max()})
    return pd.DataFrame(rows)


# ---------- figures ----------

STITCH_HEIGHT = 0.35
FIG_WIDTH = 7  # inches: the journal double-column width
BRACKET_TICK = 0.05  # height of bracket end ticks, in lane units
MONTHS = {"may": "May", "jun": "Jun", "aug": "Aug", "oct": "Oct"}


def minutes(seconds):
    return seconds / 60


def short_name(video):
    """'pig_oct08-2026-10-08_13.19.52' -> 'Oct 8'."""
    tag = video.split("_")[1][:5]
    return f"{MONTHS.get(tag[:3], tag[:3])} {int(tag[3:])}"


def draw_segments(ax, segments, lane, height):
    """Adjacent coloured segments (start_min, end_min, color) on one lane, touching with no gap.
    A hairline edge in the segment's own colour avoids light seams between segments in PDF viewers."""
    for start, end, color in segments:
        ax.add_patch(matplotlib.patches.Rectangle((start, lane - height / 2), end - start, height,
                                                  facecolor=color, edgecolor=color, linewidth=0.3))


def stitch_segments(s, origin=0):
    """Bite, knot and (if cut) assistant segments of one stitch, in minutes from origin (seconds)."""
    start, needle, end = (minutes(t - origin) for t in (s.start_s, s.start_s + s.bite_s, s.end_s))
    segments = [(start, needle, PHASE_COLORS["bite"]), (needle, end, PHASE_COLORS["knot"])]
    if not np.isnan(s.cut_s):
        segments.append((end, minutes(s.cut_s - origin), PHASE_COLORS["assistant"]))
    return segments


def draw_bracket(ax, x0, x1, y, label, direction, fontsize):
    """A bracket from x0 to x1 (minutes) at height y; ticks point up (direction=1) or down (-1); label beyond the line."""
    x0, x1 = x0 + 0.05, x1 - 0.05
    tick = y + direction * BRACKET_TICK
    ax.plot([x0, x0, x1, x1], [tick, y, y, tick], color=MUTED, linewidth=0.8, solid_joinstyle="miter")
    label_y, align = (y - 0.04, "top") if direction > 0 else (y + 0.03, "bottom")
    ax.text((x0 + x1) / 2, label_y, label, ha="center", va=align, fontsize=fontsize, color=MUTED)


def add_legend(ax):
    handles = [matplotlib.patches.Patch(color=PHASE_COLORS[p], label=p) for p in PHASES]
    ax.legend(handles=handles, frameon=False, fontsize=8, ncol=3, loc="upper right", bbox_to_anchor=(1, -0.18),
              labelcolor=MUTED, handlelength=1.2, handleheight=0.9, columnspacing=1.2)


def style_axes(ax, xlabel):
    span = np.diff(ax.get_xlim())[0]
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(5 if span <= 70 else 10))
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9, loc="left")
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, left=False, length=3)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def save_figure(fig, name):
    figure_dir = OUT_DIR / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "pdf"]:
        fig.savefig(figure_dir / f"{name}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}.png"


def timeline_figure(events, stitches, video):
    """Detailed timeline for one pig: phase brackets above, stitches, stitch brackets below."""
    lane = 1.0
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, 1.35))
    for s in stitches.itertuples():
        draw_segments(ax, stitch_segments(s), lane, STITCH_HEIGHT)
        whole_stitch_end = s.end_s if np.isnan(s.cut_s) else s.cut_s  # bracket includes the assistant's cut
        draw_bracket(ax, minutes(s.start_s), minutes(whole_stitch_end), lane - STITCH_HEIGHT / 2 - 0.06, str(s.number), 1, 7)
    for e in events[events.event.isin(PHASE_EVENTS)].itertuples():
        label = e.event.replace("_", " ")
        draw_bracket(ax, minutes(e.start_s), minutes(e.end_s), lane + STITCH_HEIGHT / 2 + 0.12, label, -1, 8.5)
    times = events[events.event.isin(PHASE_EVENTS + ["stitch", "cut"])]
    ax.set_xlim(minutes(times.start_s.min()) - 1, minutes(times.end_s.max()) + 1)
    ax.set_ylim(0.6, 1.5)
    ax.set_yticks([])
    style_axes(ax, "Video time (min)")
    add_legend(ax)
    return save_figure(fig, f"timeline_{video}")


def system_by_video():
    if not SEGMENTS_FILE.exists():
        return {}
    segments = pd.read_csv(SEGMENTS_FILE).query("trial == 'main'")
    return dict(zip(segments.video, segments.system))


def overview_figure(stitches):
    """All pigs stacked, 3 mm then 8 mm, each aligned at its first stitch."""
    systems = system_by_video()
    videos = sorted(stitches.video.unique(), key=lambda v: (systems.get(v, "?"), v))
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, 0.4 * len(videos) + 0.7))
    for row, video in enumerate(reversed(videos)):
        own = stitches[stitches.video == video]
        origin = own.start_s.min()
        for s in own.itertuples():
            draw_segments(ax, stitch_segments(s, origin), row, 0.5)
    labels = [f"{short_name(v)} · {systems.get(v, '?').replace('mm', ' mm')}" for v in reversed(videos)]
    ax.set_yticks(range(len(videos)), labels)
    ax.set_ylim(-0.6, len(videos) - 0.4)
    last = stitches.cut_s.fillna(stitches.end_s) - stitches.groupby("video").start_s.transform("min")
    ax.set_xlim(-0.5, minutes(last.max()) + 0.5)
    for row in range(1, len(videos)):  # a thin line between the 3 mm and 8 mm groups
        if systems.get(list(reversed(videos))[row]) != systems.get(list(reversed(videos))[row - 1]):
            ax.axhline(row - 0.5, color=GRID, linewidth=1)
    style_axes(ax, "Minutes from the first stitch")
    add_legend(ax)
    return save_figure(fig, "overview")


# ---------- markdown ----------

def markdown_table(table, columns, rename):
    shown = table[columns].copy()
    if "block" in shown:
        shown["block"] = shown.block.str.replace("_", " ")
    shown = shown.rename(columns=rename)
    lines = ["| " + " | ".join(shown.columns) + " |", "|" + "---|" * len(shown.columns)]
    for row in shown.itertuples(index=False):
        lines.append("| " + " | ".join(format_cell(v) for v in row) + " |")
    return lines


def format_cell(value):
    if isinstance(value, float):
        return "" if np.isnan(value) else f"{value:.0f}" if abs(value) >= 10 else f"{value:.1f}"
    return str(value)


def check_lines(stitches, blocks):
    lines = []
    for s in stitches.itertuples():
        where = f"{short_name(s.video)}, {s.block.replace('_', ' ')} stitch {s.number}"
        if s.needle_marks != 1:
            lines.append(f"- {where}: {s.needle_marks} needle_through marks; the last one is used.")
        if np.isnan(s.cut_s):
            lines.append(f"- {where}: no cut.")
    for b in blocks[blocks.stitches == 0].itertuples():
        lines.append(f"- {short_name(b.video)}, {b.block.replace('_', ' ')}: block has no stitches marked.")
    return lines or ["- None."]


STITCH_KEY = ("bite (dark purple, needle first touches tissue to needle through), knot (purple, needle through to "
              "last throw tightened) and assistant (light purple, tightened to the assistant's cut)")


def write_markdown(stitches, blocks, summary, figures, overview):
    lines = ["# Suture timing (draft)", "",
             "Written by `scripts/suture_times.py` from `results/annotations/`; re-run it after new annotations.", "",
             "## All pigs", "", f"![Overview]({overview})", "",
             f"**Stitch timelines, 3 mm vs 8 mm.** One row per pig, aligned at its first stitch. Each bar is one "
             f"stitch, split into {STITCH_KEY}.", ""]
    for video, figure in figures.items():
        lines += [f"## {short_name(video)} (`{video}`)", "", f"![Timeline]({figure})", "",
                  f"**Procedure timeline.** Brackets above: annotated phases. Each bar is one stitch, split into "
                  f"{STITCH_KEY}. Brackets below: each whole stitch, from the needle first touching tissue to the "
                  f"assistant's cut, numbered within each phase. (Stitch time in the tables is start to knot tightened.)", ""]
    lines += ["## Summary per measure (seconds)", ""]
    lines += markdown_table(summary, ["block", "measure", "n", "mean_s", "sd_s", "median_s", "min_s", "max_s"],
                            {"mean_s": "mean", "sd_s": "SD", "median_s": "median", "min_s": "min", "max_s": "max"})
    lines += ["", "## Blocks", ""]
    lines += markdown_table(blocks, ["video", "block", "duration_s", "stitches", "stitching_pct"],
                            {"duration_s": "duration (s)", "stitching_pct": "time stitching (%)"})
    lines += ["", "## Stitches (seconds)", ""]
    lines += markdown_table(stitches, ["block", "number", "stitch_s", "bite_s", "knot_s", "assistant_s", "gap_s"],
                            {"stitch_s": "stitch", "bite_s": "bite", "knot_s": "knot", "assistant_s": "assistant",
                             "gap_s": "gap to next"})
    lines += ["", "## Annotation checks", ""] + check_lines(stitches, blocks) + [""]
    (OUT_DIR / "sutures.md").write_text("\n".join(lines))


def main():
    paths = [Path(a) for a in sys.argv[1:]] or sorted(ANNOTATION_DIR.glob("*_events.csv"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_stitches, all_blocks, figures = [], [], {}
    for path in paths:
        events = load_events(path)
        stitches = stitch_table(events)
        video = events.video.iloc[0]
        figures[video] = timeline_figure(events, stitches, video)
        all_stitches.append(stitches)
        all_blocks.append(block_table(events, stitches))
    stitches, blocks = pd.concat(all_stitches), pd.concat(all_blocks)
    summary = summary_table(stitches)
    stitches.round(2).to_csv(OUT_DIR / "stitches.csv", index=False)
    blocks.round(3).to_csv(OUT_DIR / "blocks.csv", index=False)
    summary.round(2).to_csv(OUT_DIR / "summary.csv", index=False)
    write_markdown(stitches, blocks, summary, figures, overview_figure(stitches))
    print(summary.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
