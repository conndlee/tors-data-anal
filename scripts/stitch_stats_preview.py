"""Preview: stitch-level statistics per pig (with a force estimate from the rosbag), as a PDF.

Usage:
    python scripts/stitch_stats_preview.py

Needs results/sutures/stitches.csv (scripts/suture_times.py), results/sync/offsets.csv
and the joint tables in data/derived/<bag>/psm*.parquet (scripts/extract_joints.py).

Per pig: knots tied (stitches with a completed knot), mean stitch time, mean knot tying time,
mean assistant time (knot tightened to cut), and a force estimate per stitch.

Force estimate (preliminary): there is no force sensor. We use the insertion-axis joint effort (N),
which is the same arm hardware for 3 mm and 8 mm. Gravity and friction change slowly, so we subtract a
rolling median (BASELINE_S window) and keep the fast pushes and pulls. Per stitch: the mean and the
95th percentile of |effort - baseline|, taking the larger of the two arms. Videos without a rosbag
(May 29) have no force values.

Excluded: May 29 (no rosbag, incomplete annotation, a 15.5 min cut outlier), from the table and the test overview.

Output, in results/sutures/preview/:
    stitch_stats_preview.pdf   page 1: table; page 2: overview with numbers, without May 29 (a test)
    stitch_stats.csv           the table
    stitch_force.csv           force estimate per stitch
"""

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

import suture_times as st  # noqa: E402
from project import DERIVED_DIR, GRID, MUTED, SYNC_FILE, pig_order, short_name, system_by_video  # noqa: E402

OUT_DIR = Path("results/sutures/preview")
ARMS = ["psm1", "psm2"]
BASELINE_S = 60  # s, rolling-median window for the gravity and friction baseline
BIN_S = 0.1  # s, effort is averaged into bins this long before the rolling median
TEST_EXCLUDED_VIDEO = "pig_may29-2026-05-29_09.34.18"


# ---------- force estimate ----------

def insertion_deviation(bag, arm):
    """|insertion effort - rolling median| in BIN_S bins, indexed by bag time (s)."""
    d = pd.read_parquet(DERIVED_DIR / bag / f"{arm}.parquet", columns=["t", "eff_outer_insertion"]).dropna()
    binned = d.groupby((d.t / BIN_S).astype(int)).eff_outer_insertion.mean()
    window = int(BASELINE_S / BIN_S)
    baseline = binned.rolling(window, center=True, min_periods=window // 4).median()
    deviation = (binned - baseline).abs()
    deviation.index = deviation.index * BIN_S
    return deviation


def stitch_force(stitches):
    """Force estimate per stitch: mean and 95th percentile of the deviation, larger of the two arms."""
    sync = pd.read_csv(SYNC_FILE).set_index("video")
    rows = []
    for video, own in stitches.groupby("video"):
        if video not in sync.index:  # no rosbag (May 29)
            continue
        bag, offset = sync.loc[video, "bag"], sync.loc[video, "offset"]
        deviations = {arm: insertion_deviation(bag, arm) for arm in ARMS}
        rows += [stitch_force_row(s, offset, deviations) for s in own[~own.failed].itertuples()]
    return pd.DataFrame(rows)


def stitch_force_row(s, offset, deviations):
    """Mean and 95th percentile of the deviation over one stitch, larger of the two arms."""
    start, end = s.start_s - offset, s.end_s - offset  # video time -> bag time
    windows = [d[(d.index >= start) & (d.index <= end)] for d in deviations.values()]
    return {"video": s.video, "block": s.block, "number": s.number,
            "force_mean_n": max(w.mean() for w in windows), "force_p95_n": max(w.quantile(0.95) for w in windows)}


# ---------- table ----------

def pig_table(stitches, force):
    systems = system_by_video()
    merged = stitches.merge(force, on=["video", "block", "number"], how="left")
    rows = []
    for video, own in merged.groupby("video"):
        rows.append({"video": video, "system": systems[video],
                     "knots": int(own.knot_s.notna().sum()),
                     "failed": int(own.failed.sum()),
                     "stitch_min": st.minutes(own.stitch_s.mean()),
                     "knot_min": st.minutes(own.knot_s.mean()),
                     "assistant_s": own.assistant_s.mean(),
                     "force_mean_n": own.force_mean_n.mean(),
                     "force_p95_n": own.force_p95_n.mean()})
    table = pd.DataFrame(rows)
    table = table.iloc[sorted(range(len(table)), key=lambda i: pig_order(table.video.iloc[i], systems))]
    means = table.groupby("system").mean(numeric_only=True).reset_index().assign(video=None)
    return table, means


COLUMNS = [("knots", "Knots\ntied", "{:.0f}"), ("failed", "Failed\nattempts", "{:.0f}"), ("stitch_min", "Stitch\n(min)", "{:.1f}"),
           ("knot_min", "Knot tying\n(min)", "{:.1f}"), ("assistant_s", "Assistant\n(s)", "{:.0f}"),
           ("force_mean_n", "Force, mean\n(N, est.)", "{:.2f}"), ("force_p95_n", "Force, peak\n(N, est.)", "{:.2f}")]


FIRST_COLUMN = 0.2  # share of the table width for the pig names


def table_rows(table, means):
    """Rows for the PDF: each system's pigs, then a bold mean row."""
    rows = []
    for system in sorted(table.system.unique()):
        for r in table[table.system == system].itertuples():
            rows.append((f"{short_name(r.video)} · {system.replace('mm', ' mm')}", r._asdict(), False))
        mean = means[means.system == system].iloc[0].to_dict()
        rows.append((f"Mean, {system.replace('mm', ' mm')}", mean, True))
    return rows


def format_value(value, fmt):
    return "–" if value is None or (isinstance(value, float) and np.isnan(value)) else fmt.format(value)


def style_cell(cell, row, col, is_mean):
    """Thin grid lines, a muted taller header row, bold mean rows, a wider left-aligned name column."""
    cell.set_edgecolor(GRID)
    cell.set_linewidth(0.5)
    cell.set_width(FIRST_COLUMN if col == 0 else (1 - FIRST_COLUMN) / len(COLUMNS))
    if row == 0:
        cell.set_height(cell.get_height() * 1.6)
    props = {"color": MUTED} if row == 0 else {"fontweight": "bold"} if is_mean else {}
    cell.set_text_props(ha="left" if col == 0 else "center", **props)


def table_page(pdf, table, means):
    rows = table_rows(table, means)
    fig, ax = plt.subplots(figsize=(st.FIG_WIDTH, 0.3 * len(rows) + 0.9))
    ax.axis("off")
    cell_text = [[label] + [format_value(values.get(k), fmt) for k, _, fmt in COLUMNS] for label, values, _ in rows]
    grid = ax.table(cellText=cell_text, colLabels=["Pig"] + [h for _, h, _ in COLUMNS], loc="upper center",
                    cellLoc="center", colLoc="center")
    grid.auto_set_font_size(False)
    grid.set_fontsize(8)
    grid.scale(1, 1.5)
    for (row, col), cell in grid.get_celld().items():
        style_cell(cell, row, col, is_mean=row > 0 and rows[row - 1][2])
    notes = ("Knots tied: stitches with a completed knot. Stitch: needle first touches tissue to knot tightened. "
             "Knot tying: needle through to knot tightened. Assistant: knot tightened to the assistant's cut. "
             "Force (estimate, preliminary): insertion-axis joint effort minus a 60 s rolling median, mean and 95th "
             "percentile over each stitch, larger of the two arms; no force sensor. May 29 (3 mm) is excluded. "
             "Bold rows: mean of the pigs in each system.")
    fig.text(0.02, -0.02, notes, fontsize=7, color=MUTED, wrap=True, va="top")
    pdf.savefig(fig, bbox_inches="tight")
    fig.savefig(OUT_DIR / "stitch_stats_table.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def overview_page(pdf, stitches):
    """Test: the overview with numbers, without May 29."""
    st.OUT_DIR = OUT_DIR
    st.overview_stats_figure(stitches[stitches.video != TEST_EXCLUDED_VIDEO])
    image = plt.imread(OUT_DIR / "figures" / "overview_stats.png")
    fig, ax = plt.subplots(figsize=(st.FIG_WIDTH, st.FIG_WIDTH * image.shape[0] / image.shape[1]))
    ax.imshow(image)
    ax.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stitches = pd.read_csv(Path("results/sutures/stitches.csv"))
    force = stitch_force(stitches)
    force.round(3).to_csv(OUT_DIR / "stitch_force.csv", index=False)
    table, means = pig_table(stitches[stitches.video != TEST_EXCLUDED_VIDEO], force)
    pd.concat([table, means]).round(3).to_csv(OUT_DIR / "stitch_stats.csv", index=False)
    with PdfPages(OUT_DIR / "stitch_stats_preview.pdf") as pdf:
        table_page(pdf, table, means)
        overview_page(pdf, stitches)
    print(pd.concat([table, means]).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
