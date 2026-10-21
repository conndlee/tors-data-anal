"""Shared paths, pig names and plot style for the analysis scripts.

Kept free of heavy imports, so any script can use it.
"""

from pathlib import Path

import pandas as pd

VIDEO_DIR = Path("data/video")
DERIVED_DIR = Path("data/derived")
SYNC_FILE = Path("results/sync/offsets.csv")  # video time = bag time + offset (scripts/sync_video.py)
SEGMENTS_FILE = Path("results/occlusion/segments.csv")  # which system each video used, and which are main trials
LEFT_EYE = "crop=960:1040:0:40"  # ffmpeg crop: x 0-960 is the left window; the top 40 px is its title bar

# Plot text colours (primary, muted, gridlines).
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
FONTS = ["Arial", "Liberation Sans", "DejaVu Sans"]  # first installed one wins; Liberation Sans has Arial's metrics
MONTHS = {"may": "May", "jun": "Jun", "aug": "Aug", "oct": "Oct"}


# ---------- pigs ----------

def pig_tag(video):
    """'pig_oct08-2026-10-08_13.19.52' -> 'oct08'."""
    return video.split("_")[1][:5]


def short_name(video):
    """'pig_oct08-2026-10-08_13.19.52' -> 'Oct 8'."""
    tag = pig_tag(video)
    return f"{MONTHS.get(tag[:3], tag[:3])} {int(tag[3:])}"


def system_by_video():
    """{video: '3mm' or '8mm'} for the main trials (pilots are left out)."""
    if not SEGMENTS_FILE.exists():
        return {}
    segments = pd.read_csv(SEGMENTS_FILE).query("trial == 'main'")
    return dict(zip(segments.video, segments.system))


def pig_order(video, systems):
    """Sort key: system (3 mm first), then recording date ('pig_may29-2026-05-29_...' -> '2026-05-29...')."""
    return systems.get(video, "?"), video.split("-", 1)[1]


# ---------- plot style ----------

def use_journal_font():
    """Set matplotlib to the first installed Arial-style font."""
    import matplotlib.font_manager
    import matplotlib.pyplot as plt

    installed = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    plt.rcParams["font.family"] = next(f for f in FONTS if f in installed)
