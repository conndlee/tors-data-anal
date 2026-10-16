"""Train an instrument segmentation model on the hand-labelled frames (visual field work).

Usage:
    python scripts/train_tool_seg.py [label_dir]

Needs labels from tools/mask_labeler.py (data/derived/occlusion/labels/<frame>.png).
Model: torchvision DeepLabV3 (ResNet-50), pretrained, with a 1-class head (instrument).
TEST_SHARE of the labelled frames of each video are held out for testing.

Output:
    data/derived/occlusion/model.pt
    results/occlusion/seg_test.csv   frame, video, system, iou, true_share, predicted_share
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.models.segmentation import DeepLabV3_ResNet50_Weights, deeplabv3_resnet50

OCCLUSION_DIR = Path("data/derived/occlusion")
FRAME_DIR = OCCLUSION_DIR / "frames"
MODEL_FILE = OCCLUSION_DIR / "model.pt"
RESULT_FILE = Path("results/occlusion/seg_test.csv")
SIZE = (520, 480)  # (height, width): half of the 1040 x 960 left eye
TEST_SHARE = 0.2
EPOCHS = 40
BATCH = 4
LEARNING_RATE = 1e-4
SEED = 0
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


# ---------- data ----------

def load_pair(frame, label_dir):
    image = Image.open(FRAME_DIR / frame).convert("RGB").resize(SIZE[::-1], Image.BILINEAR)
    mask = Image.open(label_dir / frame).convert("L").resize(SIZE[::-1], Image.NEAREST)
    image = torch.from_numpy(np.array(image)).permute(2, 0, 1).float() / 255
    mask = torch.from_numpy(np.array(mask) > 127).float()[None]
    return image, mask


def augment(image, mask):
    if torch.rand(1) < 0.5:
        image, mask = image.flip(-1), mask.flip(-1)
    brightness, contrast = 0.8 + 0.4 * torch.rand(2)
    image = ((image - image.mean()) * contrast + image.mean() * brightness).clamp(0, 1)
    return image, mask


def normalise(image):
    return (image - MEAN.to(image.device)) / STD.to(image.device)


def split_frames(label_dir):
    """Labelled frames, split into train and test within each video."""
    frames = pd.read_csv(OCCLUSION_DIR / "frames.csv")
    frames = frames[frames.file.map(lambda f: (label_dir / f).exists())]
    rng = np.random.default_rng(SEED)
    frames["test"] = False
    for _, group in frames.groupby("video"):
        n_test = max(1, round(len(group) * TEST_SHARE))
        frames.loc[rng.choice(group.index, n_test, replace=False), "test"] = True
    return frames[~frames.test], frames[frames.test]


# ---------- model ----------

def make_model():
    model = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT)
    model.classifier[4] = torch.nn.Conv2d(256, 1, kernel_size=1)
    model.aux_classifier = None
    return model.cuda()


def loss_fn(logits, mask):
    """Binary cross-entropy plus Dice, so thin 3 mm tools still count."""
    probability = logits.sigmoid()
    overlap = (probability * mask).sum((1, 2, 3))
    dice = 1 - (2 * overlap + 1) / (probability.sum((1, 2, 3)) + mask.sum((1, 2, 3)) + 1)
    return F.binary_cross_entropy_with_logits(logits, mask) + dice.mean()


def predict(model, image):
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        return model(normalise(image.cuda())[None])["out"][0, 0].float() > 0


# ---------- training and testing ----------

def train(model, pairs):
    optimiser = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    model.train()
    for epoch in range(EPOCHS):
        order = torch.randperm(len(pairs))
        losses = []
        for start in range(0, len(pairs), BATCH):
            batch = [augment(*pairs[i]) for i in order[start:start + BATCH]]
            images = normalise(torch.stack([b[0] for b in batch]).cuda())
            masks = torch.stack([b[1] for b in batch]).cuda()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = loss_fn(model(images)["out"].float(), masks)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            losses.append(loss.item())
        print(f"epoch {epoch + 1}/{EPOCHS}  loss {np.mean(losses):.3f}", flush=True)


def iou(predicted, truth):
    union = (predicted | truth).sum()
    return float((predicted & truth).sum() / union) if union else 1.0


def test(model, frames, label_dir):
    model.eval()
    rows = []
    for row in frames.itertuples():
        image, mask = load_pair(row.file, label_dir)
        predicted, truth = predict(model, image).cpu(), mask[0].bool()
        rows.append({"frame": row.file, "video": row.video, "system": row.system,
                     "iou": round(iou(predicted, truth), 3),
                     "true_share": round(float(truth.float().mean()), 4),
                     "predicted_share": round(float(predicted.float().mean()), 4)})
    return pd.DataFrame(rows)


def main():
    label_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else OCCLUSION_DIR / "labels"
    torch.manual_seed(SEED)
    train_frames, test_frames = split_frames(label_dir)
    print(f"{len(train_frames)} training frames, {len(test_frames)} test frames", flush=True)
    model = make_model()
    train(model, [load_pair(f, label_dir) for f in train_frames.file])
    torch.save(model.state_dict(), MODEL_FILE)
    results = test(model, test_frames, label_dir)
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULT_FILE, index=False)
    print(results.groupby("system")[["iou", "true_share", "predicted_share"]].median().to_string())


if __name__ == "__main__":
    main()
