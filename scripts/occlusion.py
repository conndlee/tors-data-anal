"""Instrument occlusion over time in each video (visual field work).

Usage:
    python scripts/occlusion.py [video ...]

Runs the segmentation model (scripts/train_tool_seg.py) on the left eye at FPS
frames per second and records the share of the image covered by instruments.
Every CHECK_EVERY seconds it also saves the frame with the mask drawn on, for checking by eye.

Output:
    data/derived/occlusion/video/<video>.parquet   t_video, t_bag, occlusion (0-1)
    results/occlusion/check/<video>_<t>.jpg        overlays for checking
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

from bagio import SYSTEM_BY_BAG
from train_tool_seg import MODEL_FILE, SIZE, make_model, normalise

VIDEO_DIR = Path("data/video")
OUT_DIR = Path("data/derived/occlusion/video")
CHECK_DIR = Path("results/occlusion/check")
SYNC_FILE = Path("results/sync/offsets.csv")
FPS = 1
BATCH = 32
CHECK_EVERY = 300  # s
LEFT_EYE = "crop=960:1040:0:40"


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
    shares, index = [], 0
    for frames in read_frames(video):
        masks = predict_masks(model, frames)
        for frame, mask in zip(frames, masks):
            t = index / FPS
            if t % CHECK_EVERY == 0:
                save_check(frame, mask, CHECK_DIR / f"{video.stem}_{int(t):05d}.jpg")
            shares.append(mask.mean())
            index += 1
    return np.array(shares)


def videos_to_run(args):
    sync = pd.read_csv(SYNC_FILE)
    wanted = {Path(a).stem for a in args}
    return [row for row in sync.itertuples() if not wanted or row.video in wanted]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    model = make_model()
    model.load_state_dict(torch.load(MODEL_FILE))
    model.eval()
    for row in videos_to_run(sys.argv[1:]):
        shares = video_occlusion(model, VIDEO_DIR / f"{row.video}.mp4")
        t_video = np.arange(len(shares)) / FPS
        table = pd.DataFrame({"t_video": t_video, "t_bag": t_video - row.offset, "occlusion": shares})
        table.to_parquet(OUT_DIR / f"{row.video}.parquet", index=False)
        print(f"{row.video} ({SYSTEM_BY_BAG[row.bag]}): {len(table)} frames, "
              f"median occlusion {np.median(shares):.1%}", flush=True)


if __name__ == "__main__":
    main()
