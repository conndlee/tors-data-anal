"""Shared paths, pig names and plot style for the analysis scripts.

Kept free of heavy imports, so any script can use it.
"""

from pathlib import Path

import pandas as pd

VIDEO_DIR = Path("data/video")
DERIVED_DIR = Path("data/derived")
SYNC_FILE = Path("results/sync/offsets.csv")  # video time = bag time + offset (scripts/sync_video.py)
SEGMENTS_FILE = Path("results/occlusion/segments.csv")  # which system each video used, and which are main trials
CASE_FILE = Path("data/case_labels.csv")  # manuscript case IDs (P01-P07, Pilot) per recording key
LEFT_EYE = "crop=960:1040:0:40"  # ffmpeg crop: x 0-960 is the left window; the top 40 px is its title bar

# Plot text colours (primary, muted, gridlines).
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
# System colours, shared by the 3 mm vs 8 mm figures: 3 mm in the suture-figure purple, 8 mm in teal.
SYSTEM_COLORS = {"3mm": "#842996", "8mm": "#2a9d8f"}
SYSTEM_NAMES = {"3mm": "3 mm", "8mm": "8 mm"}
MONTHS = {"may": "May", "jun": "Jun", "aug": "Aug", "oct": "Oct"}


# ---------- pigs ----------

def pig_tag(video):
    """'pig_oct08-2026-10-08_13.19.52' -> 'oct08'."""
    return video.split("_")[1][:5]


def case_labels():
    """{recording key: case ID}, the manuscript's fixed crosswalk ('pig_oct08-2026-10-08_13.19.52' -> 'P07')."""
    table = pd.read_csv(CASE_FILE)
    return dict(zip(table.recording_key, table.case_id))


def case_id(video):
    """Case ID shown in figures, tables and captions. Raises KeyError for a recording not in the crosswalk."""
    return case_labels()[video]


def short_name(video):
    """'pig_oct08-2026-10-08_13.19.52' -> 'Oct 8'. Only for working tools (knot clips), not for reporting."""
    tag = pig_tag(video)
    return f"{MONTHS.get(tag[:3], tag[:3])} {int(tag[3:])}"


def system_by_video():
    """{video: '3mm' or '8mm'} for the main trials (pilots are left out)."""
    if not SEGMENTS_FILE.exists():
        return {}
    segments = pd.read_csv(SEGMENTS_FILE).query("trial == 'main'")
    return dict(zip(segments.video, segments.system))


def pig_order(video, systems):
    """Sort key: system (3 mm first), then case ID (P01-P07 are in recording order)."""
    return systems.get(video, "?"), case_id(video)


# ---------- plot style ----------

def use_figure_font():
    """Set matplotlib to Computer Modern (cmr10, shipped with matplotlib) for all figure text.

    Matplotlib ships the bold face as a separate family (cmb10); it is registered as cmr10 bold,
    so fontweight="bold" works.
    """
    import dataclasses

    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    bold = next(f for f in fm.fontManager.ttflist if f.name == "cmb10")
    fm.fontManager.ttflist.append(dataclasses.replace(bold, name="cmr10", weight=700))

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["cmr10"],
        "mathtext.fontset": "cm",
        "axes.formatter.use_mathtext": True,  # cmr10 has no minus sign; mathtext draws it
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,  # embed TrueType, so the PDFs keep the font when placed elsewhere
    })
