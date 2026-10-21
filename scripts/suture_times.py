"""Stitch timing from annotator exports: tables, a timeline figure and a markdown summary.

Usage:
    python scripts/suture_times.py [annotation.csv ...]

Defaults to every results/annotations/*_events.csv (Export CSV from tools/annotator.html).

Per stitch (x ... x), with its needle_through (n) and the assistant's cut (u):
    bite       start -> needle through (the last n inside the stitch, i.e. the final pass)
    knot tying needle through -> end (last throw tightened)
    assistant  end -> cut (the cut paired with the stitch that most recently ended before it)
    gap        end -> start of the next completed stitch
Each stitch belongs to the block (muscle_repair, soft_palate, hard_palate) containing its start.
A stitch span with no needle_through and no cut is a failed attempt (from a mistake or a tear):
it is left out of all stitch times and counts, its duration is kept as attempt_s, and it is drawn
grey and marked x. The time it took falls inside the gap between completed stitches.

Output, in results/sutures/:
    stitches.csv, blocks.csv, summary.csv
    figures/timeline_<video>.png and .pdf   one detailed timeline per pig
    figures/overview.png and .pdf           all pigs stacked, 3 mm then 8 mm, aligned at the first stitch
    figures/overview_stats.png and .pdf     the same, with per-pig numbers and a mean row per system
    figures/procedure.png and .pdf          all pigs, phases and stitches from the start of dissection
    procedures.csv  total procedure time per pig: dissection start to the last stitch's cut
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
PHASE_LABELS = {"bite": "bite", "knot": "knot tying", "assistant": "assistant"}  # names shown to readers
# One-hue purple ramp around #842996 (the knot colour), dark -> light, so the three stages of a stitch
# read as one family and still separate in greyscale. Contrast on white: 12.5, 7.7 and 2.8 to 1.
PHASE_COLORS = {"bite": "#531a5e", "knot": "#842996", "assistant": "#cc7ddb"}
FAILED_COLOR = "#b8b6af"  # failed attempts: neutral grey, so they read as "not a stitch"
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
    for s in stitches.itertuples():
        inside = needles[(needles >= s.start_s) & (needles <= s.end_s)]
        needle = inside.max() if len(inside) else np.nan
        cut = paired_cut(s.end_s, stitches, cuts)
        rows.append({
            "video": s.video, "block": block_of(s.start_s, blocks), "start_s": s.start_s, "end_s": s.end_s,
            "stitch_s": s.end_s - s.start_s, "bite_s": needle - s.start_s, "knot_s": s.end_s - needle,
            "assistant_s": cut - s.end_s, "needle_marks": len(inside), "cut_s": cut, "note": s.note,
        })
    return mark_failed(pd.DataFrame(rows))


def mark_failed(table):
    """Failed attempts (no needle_through, no cut) leave the stitch times; number and gaps use completed stitches."""
    table["failed"] = (table.needle_marks == 0) & table.cut_s.isna()
    table["attempt_s"] = np.where(table.failed, table.stitch_s, np.nan)
    table.loc[table.failed, "stitch_s"] = np.nan
    done = table[~table.failed]
    table["number"] = 0  # 0 = failed attempt
    table.loc[done.index, "number"] = done.groupby("block").cumcount() + 1
    table["gap_s"] = np.nan
    table.loc[done.index, "gap_s"] = done.start_s.shift(-1) - done.end_s
    columns = ["video", "block", "number"] + [c for c in table.columns if c not in ("video", "block", "number")]
    return table[columns]


def block_table(events, stitches):
    rows = []
    for b in events[events.event.isin(BLOCKS)].itertuples():
        own = stitches[stitches.block == b.event]
        rows.append({"video": b.video, "block": b.event, "start_s": b.start_s, "end_s": b.end_s,
                     "duration_s": b.end_s - b.start_s, "stitches": int((~own.failed).sum()),
                     "failed": int(own.failed.sum()),
                     "stitching_pct": 100 * own.stitch_s.sum() / (b.end_s - b.start_s)})
    return pd.DataFrame(rows)


def summary_table(stitches):
    rows = []
    order = [b for b in BLOCKS if b in set(stitches.block)]
    groups = [("all blocks", stitches)] + [(name, stitches[stitches.block == name]) for name in order]
    for name, group in groups:
        for measure in ["stitch_s", "bite_s", "knot_s", "assistant_s", "gap_s"]:
            values = group[measure].dropna()
            short = measure.replace("_s", "")
            rows.append({"block": name, "measure": PHASE_LABELS.get(short, short), "n": len(values),
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
    """Bite, knot and (if cut) assistant segments of one stitch, in minutes from origin (seconds).
    A failed attempt is one grey segment."""
    if s.failed:
        return [(minutes(s.start_s - origin), minutes(s.end_s - origin), FAILED_COLOR)]
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


def add_legend(ax, show_failed=False):
    handles = [matplotlib.patches.Patch(color=PHASE_COLORS[p], label=PHASE_LABELS[p]) for p in PHASES]
    if show_failed:
        handles.append(matplotlib.patches.Patch(color=FAILED_COLOR, label="failed attempt"))
    ax.legend(handles=handles, frameon=False, fontsize=8, ncol=len(handles), loc="upper right", bbox_to_anchor=(1, -0.18),
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
        label = "×" if s.failed else str(s.number)
        draw_bracket(ax, minutes(s.start_s), minutes(whole_stitch_end), lane - STITCH_HEIGHT / 2 - 0.06, label, 1, 7)
    for e in events[events.event.isin(PHASE_EVENTS)].itertuples():
        label = e.event.replace("_", " ")
        draw_bracket(ax, minutes(e.start_s), minutes(e.end_s), lane + STITCH_HEIGHT / 2 + 0.12, label, -1, 8.5)
    times = events[events.event.isin(PHASE_EVENTS + ["stitch", "cut"])]
    ax.set_xlim(minutes(times.start_s.min()) - 1, minutes(times.end_s.max()) + 1)
    ax.set_ylim(0.6, 1.5)
    ax.set_yticks([])
    style_axes(ax, "Video time (min)")
    add_legend(ax, stitches.failed.any())
    return save_figure(fig, f"timeline_{video}")


def system_by_video():
    if not SEGMENTS_FILE.exists():
        return {}
    segments = pd.read_csv(SEGMENTS_FILE).query("trial == 'main'")
    return dict(zip(segments.video, segments.system))


def pig_order(video, systems):
    """Sort key: system (3 mm first), then recording date ('pig_may29-2026-05-29_...' -> '2026-05-29...')."""
    return systems.get(video, "?"), video.split("-", 1)[1]


def overview_figure(stitches):
    """All pigs stacked, 3 mm then 8 mm, each aligned at its first stitch."""
    systems = system_by_video()
    videos = sorted(stitches.video.unique(), key=lambda v: pig_order(v, systems))
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
    add_legend(ax, stitches.failed.any())
    return save_figure(fig, "overview")


# ---------- overview with numbers ----------

STAT_COLUMNS = [("stitches", "Stitches", "{:.0f}"), ("failed", "Failed", "{:.0f}"), ("stitch_min", "Stitch\n(min)", "{:.1f}"),
                ("gap_min", "Gap\n(min)", "{:.1f}"), ("span_min", "Span\n(min)", "{:.0f}")]


def pig_stats(own):
    """Numbers for one pig's stitches."""
    end = own.cut_s.fillna(own.end_s).max()
    return {"stitches": int((~own.failed).sum()), "failed": int(own.failed.sum()),
            "stitch_min": minutes(own.stitch_s.mean()), "gap_min": minutes(own.gap_s.mean()),
            "span_min": minutes(end - own.start_s.min())}


def stats_rows(stitches, systems):
    """Rows top to bottom: each system's pigs, then that system's mean row."""
    rows = []
    videos = sorted(stitches.video.unique(), key=lambda v: pig_order(v, systems))
    for system in sorted({systems.get(v, "?") for v in videos}):
        own_videos = [v for v in videos if systems.get(v, "?") == system]
        pig_rows = [{"kind": "pig", "video": v, "system": system, **pig_stats(stitches[stitches.video == v])}
                    for v in own_videos]
        mean = {k: np.mean([r[k] for r in pig_rows]) for k, _, _ in STAT_COLUMNS}
        rows += pig_rows + [{"kind": "mean", "video": None, "system": system, **mean}]
    return rows


def row_label(row):
    system = row["system"].replace("mm", " mm")
    return f"Mean, {system}" if row["kind"] == "mean" else f"{short_name(row['video'])} · {system}"


def draw_stats_table(ax, rows, ys):
    ax.set_xlim(0, len(STAT_COLUMNS))
    ax.axis("off")
    for i, (_, header, _) in enumerate(STAT_COLUMNS):
        ax.text(i + 0.5, max(ys) + 0.75, header, ha="center", va="bottom", fontsize=8, color=MUTED)
    for row, y in zip(rows, ys):
        weight = "bold" if row["kind"] == "mean" else "normal"
        for i, (key, _, fmt) in enumerate(STAT_COLUMNS):
            ax.text(i + 0.5, y, fmt.format(row[key]), ha="center", va="center", fontsize=8.5, color=TEXT,
                    fontweight=weight)


def overview_stats_figure(stitches):
    """The stitch overview with each pig's numbers beside it and a mean row per system."""
    systems = system_by_video()
    rows = stats_rows(stitches, systems)
    ys = list(range(len(rows) - 1, -1, -1))  # first row at the top
    fig = plt.figure(figsize=(FIG_WIDTH, 0.36 * len(rows) + 1.1))
    grid = fig.add_gridspec(1, 2, width_ratios=[3.0, 1.15], wspace=0.02)
    ax, table_ax = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    for row, y in zip(rows, ys):
        if row["kind"] == "pig":
            own = stitches[stitches.video == row["video"]]
            for s in own.itertuples():
                draw_segments(ax, stitch_segments(s, own.start_s.min()), y, 0.5)
        else:  # a light line above each mean row, across both panels
            for a in (ax, table_ax):
                a.axhline(y + 0.5, color=GRID, linewidth=1)
    ax.set_yticks(ys, [row_label(r) for r in rows])
    for label, row in zip(ax.get_yticklabels(), rows):
        label.set_fontweight("bold" if row["kind"] == "mean" else "normal")
    for a in (ax, table_ax):
        a.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(-0.5, max(r["span_min"] for r in rows if r["kind"] == "pig") + 0.5)
    style_axes(ax, "Minutes from the first stitch")
    draw_stats_table(table_ax, rows, ys)
    add_legend(ax, stitches.failed.any())
    return save_figure(fig, "overview_stats")


# ---------- procedure time ----------

# Cool, pale tints (grey, teal, blue, mint) that sit with the purple and teal of the other figures;
# the purple stitches sit on top.
PHASE_TINTS = {"dissection": "#eff1f2", "incision": "#eff1f2", "muscle_repair": "#b8e1da",
               "soft_palate": "#d4e3f5", "hard_palate": "#cfeedd"}


def procedure_row(events, stitches):
    """Total procedure time: start of dissection to the cut of the last stitch (its knot if it has no cut)."""
    dissection = events[events.event == "dissection"]
    blocks = events[events.event.isin(BLOCKS)]
    start = dissection.start_s.min() if len(dissection) else blocks.start_s.min()
    end = stitches.cut_s.fillna(stitches.end_s).max()
    return {"video": events.video.iloc[0], "start_s": start, "end_s": end,
            "total_min": minutes(end - start), "dissection_min": minutes((dissection.end_s - dissection.start_s).sum()),
            "suturing_min": minutes(end - stitches.start_s.min()), "stitches": int((~stitches.failed).sum()),
            "failed": int(stitches.failed.sum()),
            "dissection_marked": len(dissection) > 0}


def draw_procedure_row(ax, events, stitches, row, origin):
    for e in events[events.event.isin(PHASE_EVENTS)].itertuples():
        draw_segments(ax, [(minutes(e.start_s - origin), minutes(e.end_s - origin), PHASE_TINTS[e.event])], row, 0.6)
    for s in stitches.itertuples():
        end = s.end_s if np.isnan(s.cut_s) else s.cut_s
        draw_segments(ax, [(minutes(s.start_s - origin), minutes(end - origin), PHASE_COLORS["knot"])], row, 0.26)


def procedure_figure(events_by_video, stitches, procedures):
    """All pigs stacked (3 mm then 8 mm), phases and stitches from the start of dissection, total time at the end."""
    systems = system_by_video()
    videos = sorted(procedures.video, key=lambda v: pig_order(v, systems))
    rows = list(reversed(videos))
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, 0.42 * len(rows) + 0.9))
    for row, video in enumerate(rows):
        p = procedures.set_index("video").loc[video]
        draw_procedure_row(ax, events_by_video[video], stitches[stitches.video == video], row, p.start_s)
        ax.text(p.total_min + 1, row, f"{p.total_min:.0f} min", va="center", fontsize=8, color=TEXT)
    ax.set_yticks(range(len(rows)), [f"{short_name(v)} · {systems.get(v, '?').replace('mm', ' mm')}" for v in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(-1, procedures.total_min.max() + 12)
    for row in range(1, len(rows)):  # a thin line between the 3 mm and 8 mm groups
        if systems.get(rows[row]) != systems.get(rows[row - 1]):
            ax.axhline(row - 0.5, color=GRID, linewidth=1)
    style_axes(ax, "Minutes from the start of dissection")
    names = {"dissection": "dissection", "muscle_repair": "muscle repair", "soft_palate": "soft palate",
             "hard_palate": "hard palate"}
    handles = [matplotlib.patches.Patch(color=PHASE_TINTS[k], label=v) for k, v in names.items()]
    handles.append(matplotlib.patches.Patch(color=PHASE_COLORS["knot"], label="stitch (to cut)"))
    ax.legend(handles=handles, frameon=False, fontsize=8, ncol=5, loc="upper right", bbox_to_anchor=(1, -0.18),
              labelcolor=MUTED, handlelength=1.2, handleheight=0.9, columnspacing=1.0)
    return save_figure(fig, "procedure")


def procedure_lines(procedures, figure):
    systems = system_by_video()
    table = procedures.assign(pig=procedures.video.map(short_name),
                              system=procedures.video.map(lambda v: systems.get(v, "?").replace("mm", " mm")))
    table = table.iloc[sorted(range(len(table)), key=lambda i: pig_order(table.video.iloc[i], systems))]
    per_system = table.groupby("system")[["total_min", "dissection_min", "suturing_min", "stitches"]].median().reset_index()
    lines = ["## Procedure time", "", f"![Procedure time]({figure})", "",
             "**Total procedure time.** One row per pig, from the start of dissection (0) to the cut of the last "
             "stitch; the number is the total in minutes. Shaded bars: annotated phases. Purple bars: stitches, "
             "from the needle first touching tissue to the assistant's cut.", ""]
    lines += markdown_table(table, ["pig", "system", "total_min", "dissection_min", "suturing_min", "stitches"],
                            {"total_min": "total (min)", "dissection_min": "dissection (min)",
                             "suturing_min": "first stitch to last cut (min)"})
    lines += ["", "Median per system:", ""]
    lines += markdown_table(per_system, ["system", "total_min", "dissection_min", "suturing_min", "stitches"],
                            {"total_min": "total (min)", "dissection_min": "dissection (min)",
                             "suturing_min": "first stitch to last cut (min)"})
    missing = table[~table.dissection_marked]
    lines += [""] + [f"- {r.pig}: no dissection marked; total starts at the first block." for r in missing.itertuples()]
    return lines + [""]


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
    for s in stitches[stitches.failed].itertuples():
        lines.append(f"- {short_name(s.video)}, {s.block.replace('_', ' ')}: failed attempt at {s.start_s:.0f} s "
                     f"({s.attempt_s:.0f} s; no needle through, no cut). Left out of stitch times.")
    for s in stitches[~stitches.failed].itertuples():
        where = f"{short_name(s.video)}, {s.block.replace('_', ' ')} stitch {s.number}"
        if s.needle_marks != 1:
            lines.append(f"- {where}: {s.needle_marks} needle_through marks; the last one is used.")
        if np.isnan(s.cut_s):
            lines.append(f"- {where}: no cut.")
        if s.assistant_s > LONG_ASSISTANT:
            lines.append(f"- {where}: {s.assistant_s / 60:.1f} min from knot to cut; check the cut mark.")
    for b in blocks[blocks.stitches == 0].itertuples():
        lines.append(f"- {short_name(b.video)}, {b.block.replace('_', ' ')}: block has no stitches marked.")
    return lines or ["- None."]


LONG_ASSISTANT = 300  # s; a longer knot-to-cut time is flagged for checking
STITCH_KEY = ("bite (dark purple, needle first touches tissue to needle through), knot tying (purple, needle through to "
              "last throw tightened) and assistant (light purple, tightened to the assistant's cut)")


def write_markdown(stitches, blocks, summary, figures, overview, overview_stats, procedure):
    lines = ["# Suture timing (draft)", "",
             "Written by `scripts/suture_times.py` from `results/annotations/`; re-run it after new annotations.", ""]
    lines += procedure
    lines += ["## All pigs", "", f"![Overview]({overview})", "",
             f"**Stitch timelines, 3 mm vs 8 mm.** One row per pig, aligned at its first stitch. Each bar is one "
             f"stitch, split into {STITCH_KEY}.", "",
             "## All pigs, with numbers", "", f"![Overview with numbers]({overview_stats})", "",
             "**Stitch timelines with per-pig numbers.** Left: as above. Right: Stitches, number of stitches; "
             "Stitch, mean stitch time (needle first touches tissue to knot tightened); Gap, mean time from the end "
             "of one stitch (knot tightened) to the start of the next; Span, first stitch to last cut. "
             "Bold rows: mean of the pigs in each system.", ""]
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
                            {"stitch_s": "stitch", "bite_s": "bite", "knot_s": "knot tying", "assistant_s": "assistant",
                             "gap_s": "gap to next"})
    lines += ["", "## Annotation checks", ""] + check_lines(stitches, blocks) + [""]
    (OUT_DIR / "sutures.md").write_text("\n".join(lines))


def main():
    paths = [Path(a) for a in sys.argv[1:]] or sorted(ANNOTATION_DIR.glob("*_events.csv"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_stitches, all_blocks, figures, events_by_video, procedure_rows = [], [], {}, {}, []
    main_trials = system_by_video()
    for path in paths:
        events = load_events(path)
        video = events.video.iloc[0]
        if video not in main_trials:
            print(f"skipped {path.name}: not a main trial (see {SEGMENTS_FILE})")
            continue
        if not (events.event == "stitch").any():
            print(f"skipped {path.name}: no stitches marked yet")
            continue
        stitches = stitch_table(events)
        figures[video] = timeline_figure(events, stitches, video)
        all_stitches.append(stitches)
        all_blocks.append(block_table(events, stitches))
        events_by_video[video] = events
        procedure_rows.append(procedure_row(events, stitches))
    stitches, blocks = pd.concat(all_stitches), pd.concat(all_blocks)
    procedures = pd.DataFrame(procedure_rows)
    procedures.round(2).to_csv(OUT_DIR / "procedures.csv", index=False)
    procedure = procedure_lines(procedures, procedure_figure(events_by_video, stitches, procedures))
    summary = summary_table(stitches)
    stitches.round(2).to_csv(OUT_DIR / "stitches.csv", index=False)
    blocks.round(3).to_csv(OUT_DIR / "blocks.csv", index=False)
    summary.round(2).to_csv(OUT_DIR / "summary.csv", index=False)
    write_markdown(stitches, blocks, summary, figures, overview_figure(stitches), overview_stats_figure(stitches),
                   procedure)
    print(summary.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
