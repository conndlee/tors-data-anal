#!/usr/bin/env bash
# Progress bar for scripts/occlusion.py.
# occlusion.py saves one check image every 300 s of video, so we count those
# against what each video's length predicts.
#
# Usage (from the repo folder):  bash tools/watch_occlusion.sh   (Ctrl+C to stop watching)

CHECK_EVERY=300
CHECK_DIR=results/occlusion/check
DONE_DIR=data/derived/occlusion/video

expected=0
for video in $(python3 -c "import csv; print(' '.join(r['video'] for r in csv.DictReader(open('results/sync/offsets.csv'))))"); do
  duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "data/video/$video.mp4")
  expected=$((expected + ${duration%.*} / CHECK_EVERY + 1))
done

while true; do
  done_images=$(ls "$CHECK_DIR" 2>/dev/null | wc -l)
  done_videos=$(ls "$DONE_DIR" 2>/dev/null | wc -l)
  percent=$((100 * done_images / expected))
  filled=$((percent / 2))
  bar=$(printf '%*s' "$filled" '' | tr ' ' '#')$(printf '%*s' "$((50 - filled))" '' | tr ' ' '.')
  printf '\r[%s] %3d%%   videos done: %d / 6 ' "$bar" "$percent" "$done_videos"
  if ! pgrep -f "python -u scripts/occlusion.py" > /dev/null; then
    printf '\nocclusion.py is not running (finished or stopped).\n'
    break
  fi
  sleep 5
done
