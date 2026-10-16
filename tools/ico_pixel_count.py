"""Ground-truth: count non-transparent pixels in a .ico frame, straight from
the file (no Win32 rendering, no flaky prototypes).

Parses the classic ICO directory, picks the frame matching `size`, decodes its
32bpp BITMAPINFOHEADER DIB (BGRA, top-down), and counts pixels with alpha>40.
This is exactly the pixels the Windows tray would draw, so:
  - count == 0  -> the icon is BLANK (the 'registered but invisible' bug)
  - count > 0   -> the icon has real pixels and will be visible in the tray
"""
from __future__ import annotations
import os
import struct
import sys

ICO = r"C:\Users\gaipu\Desktop\NetVisual-A-Plus-v4\NetVisual.ico"
WANT = int(sys.argv[1]) if len(sys.argv) > 1 else 16


def parse(ico: str):
    data = open(ico, "rb").read()
    _, _, count = struct.unpack_from("<HHH", data, 0)
    frames = {}
    off = 6
    for _ in range(count):
        w, h, cc, resv, planes, bpp, size, offset = struct.unpack_from(
            "<BBBBHHII", data, off)
        off += 16
        w = 256 if w == 0 else w
        h = 256 if h == 0 else h
        frames[w] = (data[offset:offset + size], h, bpp)
    return frames


def count_opaque(dib: bytes, h: int, bpp: int):
    if len(dib) < 40:
        return -1, "not a DIB (PNG or too short)"
    bih = struct.unpack_from("<IiiHHIIiiII", dib, 0)
    biSize, biWidth, biHeight, biPlanes, biBitCount = bih[:5]
    compression = bih[5]
    if compression != 0:
        return -1, f"compressed={compression} (not BI_RGB)"
    if biBitCount != 32:
        return -1, f"bitcount={biBitCount} (expected 32)"
    # In an ICO the DIB biHeight is 2x the real height (XOR + AND masks);
    # the colour (XOR) bitmap is the top `height` rows, top-down.
    height = abs(biHeight) // 2
    rowbytes = ((32 * biWidth + 31) // 32) * 4
    xor_size = rowbytes * height
    px = dib[40:40 + xor_size]
    opaque = 0
    for y in range(height):
        for x in range(biWidth):
            i = y * rowbytes + x * 4
            a = px[i + 3]  # BGRA
            if a > 40:
                opaque += 1
    return opaque, f"{biWidth}x{height} BI_RGB 32bpp"


def main():
    frames = parse(ICO)
    print(f"frames present: {sorted(frames)}")
    if WANT not in frames:
        print(f"frame {WANT} not present")
        return
    dib, h, bpp = frames[WANT]
    is_png = dib[:4] == b"\x89PNG"
    if is_png:
        print(f"frame {WANT}: PNG-compressed (classic tray path CANNOT decode -> BLANK)")
        return
    opaque, info = count_opaque(dib, h, bpp)
    print(f"frame {WANT}: {info}, opaque pixels = {opaque}/{WANT*WANT}")
    if opaque == 0:
        print("VERDICT: BLANK icon (real bug)")
    else:
        print("VERDICT: icon has real pixels -> will be VISIBLE in the tray")


if __name__ == "__main__":
    main()
