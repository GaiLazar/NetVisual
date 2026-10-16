"""Regenerate NetVisual.ico as a CLASSIC BMP-compressed ICO.

Why: Pillow's default ICO writer emits PNG-compressed frames. The Windows
notification-area icon path (ExtractIconExW -> HICON -> Shell_NotifyIconW)
cannot decode those PNG frames, so the tray icon shows up BLANK even though it
is registered. A classic ICO with uncompressed 32bpp BITMAPINFOHEADER (DIB)
frames decodes correctly on every Windows version and the icon actually shows.

This builds the ICO by hand: ICONDIR + one ICONDIRENTRY per size + a 32bpp
BITMAPINFOHEADER DIB (height doubled for the AND mask) per frame.

Requires Pillow (only to draw the source art). Output: NetVisual.ico.
"""
from __future__ import annotations
import os
import struct
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "NetVisual.ico")
SIZES = (16, 24, 32, 48, 64, 128, 256)

# --- palette (network-node motif) ---
NAVY = (11, 20, 34)
NAVY2 = (19, 31, 51)
MINT = (54, 234, 175)
CYAN = (34, 211, 238)
WHITE = (236, 242, 250)


def draw(size: int) -> Image.Image:
    """Draw the network-node motif at `size` (RGBA, transparent corners)."""
    S = 16
    img = Image.new("RGBA", (S * S, S * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def u(v):
        return v / S

    # rounded dark tile
    r = u(3.2)
    d.rounded_rectangle([0, 0, S * S - 1, S * S - 1], radius=r,
                        fill=NAVY + (255,), outline=CYAN + (255,),
                        width=max(1, int(u(0.7))))

    # inner subtle border
    d.rounded_rectangle([u(1.2), u(1.2), u(S) - u(1.2), u(S) - u(1.2)],
                        radius=u(2.4), outline=NAVY2 + (255,),
                        width=max(1, int(u(0.4))))

    cx, cy = u(S / 2), u(S / 2)
    hub = u(2.4)
    sat = u(1.5)
    ring = u(5.6)

    # spokes (drawn first, under the nodes)
    import math
    for k in range(6):
        a = math.radians(60 * k - 90)
        sx = cx + ring * math.cos(a)
        sy = cy + ring * math.sin(a)
        d.line([cx, cy, sx, sy], fill=CYAN + (255,), width=max(1, int(u(0.9))))

    # satellite nodes
    for k in range(6):
        a = math.radians(60 * k - 90)
        sx = cx + ring * math.cos(a)
        sy = cy + ring * math.sin(a)
        d.ellipse([sx - sat, sy - sat, sx + sat, sy + sat], fill=WHITE + (255,))

    # hub (mint, on top)
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=MINT + (255,))
    d.ellipse([cx - u(0.9), cy - u(0.9), cx + u(0.9), cy + u(0.9)],
              fill=NAVY + (255,))

    return img.resize((size, size), Image.LANCZOS)


def to_dib(img: Image.Image) -> bytes:
    """Encode an RGBA image as a 32bpp BITMAPINFOHEADER DIB (ICO frame body)."""
    size = img.size[0]
    img = img.convert("RGBA")
    # top-down BGRA (biHeight negative = top-down)
    raw = b""
    for y in range(size):
        for x in range(size):
            r, g, b, a = img.getpixel((x, y))
            raw += struct.pack("<BBBB", b, g, r, a)  # BGRA
    # AND mask: all zero (fully opaque where alpha>0); ICO requires it.
    # For a 32bpp icon the AND mask is typically all-zero rows, 1 byte/px.
    and_row = (size + 31) // 32 * 4  # padded to 32 bits
    and_mask = b"\x00" * (and_row * size)

    bih = struct.pack(
        "<IiiHHIIiiII",
        40,            # biSize
        size,          # biWidth
        size * 2,      # biHeight (XOR + AND)
        1,             # biPlanes
        32,            # biBitCount
        0,             # biCompression BI_RGB
        len(raw) + len(and_mask),  # biSizeImage
        0, 0, 0, 0,
    )
    return bih + raw + and_mask


def main():
    frames = []
    for s in SIZES:
        dib = to_dib(draw(s))
        frames.append((s, dib))

    # ICONDIR
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    data = b""
    offset = 6 + 16 * len(frames)
    for s, dib in frames:
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(dib), offset)
        data += dib
        offset += len(dib)

    with open(OUT, "wb") as f:
        f.write(header + entries + data)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)} bytes, "
          f"{len(frames)} BMP frames: {SIZES})")

    # quick self-check: frame 0 should now be a 16x16 BMP DIB, not PNG
    d0 = frames[0][1]
    is_png = d0[:4] == b"\x89PNG"
    print(f"frame 0 (16x16) is {'PNG (BAD)' if is_png else 'BMP DIB (GOOD)'}")


if __name__ == "__main__":
    sys.exit(main())
