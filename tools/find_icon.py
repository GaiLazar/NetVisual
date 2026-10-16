"""Locate the NetVisual tray icon in a screenshot.

Our icon's mint hub (#36EAAF) and cyan edges (#22D3EE) are distinctive
colours — nothing else on a normal desktop uses them, so any cluster of
them is the icon. Reports the cluster bounds and saves a cropped zoom.
"""
from __future__ import annotations

import sys
from PIL import Image

MINT = (54, 234, 175)
CYAN = (34, 211, 238)
TOL = 45


def near(c, target, tol=TOL):
    return all(abs(c[i] - target[i]) <= tol for i in range(3))


def main(path: str, out: str = "icon_cluster.png"):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    hits = []
    step = max(1, w // 1200)  # keep the scan fast; fine enough for a 16-32px icon
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = px[x, y]
            if near(c, MINT) or near(c, CYAN):
                hits.append((x, y))
    if not hits:
        print(f"{w}x{h}: NO mint/cyan pixels — icon not visible in this shot")
        return
    xs = [p[0] for p in hits]
    ys = [p[1] for p in hits]
    cx, cy = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    pos = []
    pos.append("BOTTOM (taskbar zone)" if cy > h * 0.82 else "upper area")
    pos.append("RIGHT" if cx > w * 0.7 else ("LEFT" if cx < w * 0.3 else "CENTER"))
    print(f"{w}x{h}: {len(hits)} mint/cyan pixels")
    print(f"  cluster: x[{min(xs)}..{max(xs)}] y[{min(ys)}..{max(ys)}] "
          f"center=({cx},{cy}) -> {', '.join(pos)}")
    pad = 28
    box = (max(0, min(xs) - pad), max(0, min(ys) - pad),
           min(w, max(xs) + pad), min(h, max(ys) + pad))
    crop = im.crop(box)
    scale = max(1, 600 // max(crop.width, 1))
    crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS) \
        .save(out)
    print(f"  crop saved -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "icon_cluster.png")
