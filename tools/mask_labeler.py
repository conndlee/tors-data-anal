"""Click-assisted tool mask labelling with SAM 2 (visual field work).

Usage:
    conda run -n tors1 python tools/mask_labeler.py
    then open http://localhost:8765

Frames come from data/derived/occlusion/frames (scripts/sample_label_frames.py).
Each tool is one "object" with its own clicks; the saved mask is the union of all objects.
Only the clicks are sent and stored; the mask is always recomputed from them,
so every label can be reproduced.

Output, per frame, in data/derived/occlusion/labels/:
    <frame>.json   clicks per object
    <frame>.png    mask (255 = instrument, 0 = background)
"""

import base64
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

FRAME_DIR = Path("data/derived/occlusion/frames")
LABEL_DIR = Path("data/derived/occlusion/labels")
PAGE = Path(__file__).with_name("mask_labeler.html")
CHECKPOINT = Path.home() / "src/sam2/checkpoints/sam2.1_hiera_large.pt"
CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
PORT = 8765


class Segmenter:
    """SAM 2 with the image encoding of the last frame cached."""

    def __init__(self):
        self.predictor = SAM2ImagePredictor(build_sam2(CONFIG, str(CHECKPOINT), device="cuda"))
        self.frame = None

    def use_frame(self, name):
        if name != self.frame:
            image = np.array(Image.open(FRAME_DIR / name).convert("RGB"))
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                self.predictor.set_image(image)
            self.frame = name

    def object_mask(self, clicks):
        points = np.array([[c["x"], c["y"]] for c in clicks], dtype=np.float32)
        labels = np.array([1 if c["positive"] else 0 for c in clicks], dtype=np.int32)
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            masks, _, _ = self.predictor.predict(point_coords=points, point_labels=labels, multimask_output=False)
        return masks[0] > 0

    def union_mask(self, name, objects):
        self.use_frame(name)
        height, width = self.predictor._orig_hw[0]
        mask = np.zeros((height, width), bool)
        for clicks in objects:
            if any(c["positive"] for c in clicks):
                mask |= self.object_mask(clicks)
        return mask


def png_bytes(mask):
    buffer = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8) * 255).save(buffer, format="PNG")
    return buffer.getvalue()


def frame_list():
    names = sorted(p.name for p in FRAME_DIR.glob("*.png"))
    return [{"name": n, "done": (LABEL_DIR / f"{Path(n).stem}.json").exists()} for n in names]


def saved_clicks(name):
    path = LABEL_DIR / f"{Path(name).stem}.json"
    return json.loads(path.read_text()) if path.exists() else {"objects": []}


class Handler(BaseHTTPRequestHandler):
    segmenter = None

    def reply(self, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        routes = {
            "/": lambda arg: self.reply(PAGE.read_bytes(), "text/html"),
            "/frames": lambda arg: self.reply(frame_list()),
            "/frame": lambda arg: self.reply((FRAME_DIR / arg).read_bytes(), "image/png"),
            "/clicks": lambda arg: self.reply(saved_clicks(arg)),
        }
        route, _, arg = self.path.partition("?name=")
        routes.get(route, lambda arg: self.send_error(404))(arg)

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        mask = self.segmenter.union_mask(request["name"], request["objects"])
        if self.path == "/save":
            stem = Path(request["name"]).stem
            (LABEL_DIR / f"{stem}.png").write_bytes(png_bytes(mask))
            (LABEL_DIR / f"{stem}.json").write_text(json.dumps({"objects": request["objects"]}))
        self.reply({"mask": base64.b64encode(png_bytes(mask)).decode(), "covered": float(mask.mean())})

    def log_message(self, *args):
        pass


def main():
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    Handler.segmenter = Segmenter()
    print(f"open http://localhost:{PORT}", flush=True)
    HTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
