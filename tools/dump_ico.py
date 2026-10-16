"""Dump the raw structure of NetVisual.ico — how many frames, BMP or PNG, sizes.

This is the ground truth for whether the .ico has a decodable 16x16 BMP frame
for the tray (classic ExtractIconExW / Shell_NotifyIcon path).
"""
from __future__ import annotations
import struct

ICO = r"C:\Users\gaipu\Desktop\NetVisual-A-Plus-v4\NetVisual.ico"
data = open(ICO, "rb").read()
print(f"file size: {len(data)} bytes")

# ICONDIR: uReserved(2)=0, uType(2)=1, uCount(2)
res, typ, count = struct.unpack_from("<HHH", data, 0)
print(f"reserved={res} type={typ} image_count={count}")

off = 6
for i in range(count):
    w, h, colors, resv, planes, bpp, size, offset = struct.unpack_from(
        "<BBBBHHII", data, off)
    off += 16
    w = 256 if w == 0 else w
    h = 256 if h == 0 else h
    # PNG frame? PNG magic is 89 50 4E 47
    is_png = data[offset:offset + 4] == b"\x89PNG"
    fmt = "PNG" if is_png else f"BMP({bpp}bpp)"
    print(f"  frame {i}: {w}x{h}  {fmt}  bytes={size}  @offset={offset}")
    off = offset + size
