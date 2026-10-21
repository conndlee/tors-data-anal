"""Instrument occlusion over time in each video (visual field work).

Usage:
    python scripts/occlusion.py [video ...]

Runs the segmentation model (scripts/train_tool_seg.py) on the left eye at FPS
frames per second and records the share of the image covered by instruments.
Every CHECK_EVERY seconds it also saves the frame with the mask drawn on, for checking by eye.

Videos without a rosbag (the May pilots) get t_bag = NaN.

Output:
    data/derived/occlusion/video/<video>.parquet   t_video, t_bag, occlusion (0-1), brightness (0-255)
        brightness lets black frames (recorder left running) be dropped later
    results/occlusion/check/<video>_<t>.jpg        overlays for checking
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

from project import LEFT_EYE, SYNC_FILE, VIDEO_DIR
from train_tool_seg import MODEL_FILE, SIZE, make_model, normalise

OUT_DIR = Path("data/derived/occlusion/video")
CHECK_DIR = Path("results/occlusion/check")
FPS = 1
BATCH = 32
CHECK_EVERY = 300  # s


def read_frames(video):
    """Yield batches of left-eye frames, shape (n, H, W, 3), uint8."""
    height, width = SIZE
    filters = f"fps={FPS},{LEFT_EYE},scale={width}:{height}"
    command = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", filters, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    frame_size = height * width * 3
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        while raw := process.stdout.read(frame_size * BATCH):
            usable = len(raw) - len(raw) % frame_size
            yield np.frombuffer(raw[:usable], np.uint8).reshape(-1, height, width, 3)


def predict_masks(model, frames):
    images = torch.from_numpy(frames).cuda().permute(0, 3, 1, 2).float() / 255
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        return (model(normalise(images))["out"][:, 0].float() > 0).cpu().numpy()


def save_check(frame, mask, path):
    overlay = frame.copy()
    overlay[mask] = (0.5 * overlay[mask] + [0, 127, 0]).astype(np.uint8)
    Image.fromarray(np.hstack([frame, overlay])).save(path, quality=85)


def video_occlusion(model, video):
    shares, brightness, index = [], [], 0
    for frames in read_frames(video):
        masks = predict_masks(model, frames)
        for frame, mask in zip(frames, masks):
            t = index / FPS
            if t % CHECK_EVERY == 0:
                save_check(frame, mask, CHECK_DIR / f"{video.stem}_{int(t):05d}.jpg")
            shares.append(mask.mean())
            brightness.append(frame.mean())
            index += 1
    return np.array(shares), np.array(brightness)


def videos_to_run(args):
    """(video, offset) for every video; offset is NaN when the video has no rosbag."""
    offsets = pd.read_csv(SYNC_FILE).set_index("video").offset
    videos = [Path(a) for a in args] or sorted(VIDEO_DIR.glob("*.mp4"))
    return [(video.stem, offsets.get(video.stem, np.nan)) for video in videos]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    model = make_model()
    model.load_state_dict(torch.load(MODEL_FILE))
    model.eval()
    for video, offset in videos_to_run(sys.argv[1:]):
        shares, brightness = video_occlusion(model, VIDEO_DIR / f"{video}.mp4")
        t_video = np.arange(len(shares)) / FPS
        table = pd.DataFrame({"t_video": t_video, "t_bag": t_video - offset,
                              "occlusion": shares, "brightness": brightness})
        table.to_parquet(OUT_DIR / f"{video}.parquet", index=False)
        print(f"{video}: {len(table)} frames, median occlusion {np.median(shares):.1%}", flush=True)


if __name__ == "__main__":
    main()
