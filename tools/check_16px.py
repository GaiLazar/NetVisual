"""Decisive test: is the 16x16 tray icon frame non-blank?

The Windows tray renders the *small* (16x16) frame of the .ico. We extract
exactly that frame two independent ways and count non-transparent pixels:

  A. Win32 ExtractIconExW (the EXACT API netvisual/tray.py uses) -> HICON ->
     DrawIconEx onto a 16x16 DIB -> count opaque pixels.
  B. Pillow: load the 16x16 frame straight from the .ico.

If both show a few hundred opaque pixels, the icon is valid and any
"not visible" is Windows 11 parking new icons in the overflow (^) area —
normal OS behaviour, not an app bug. If ~0, the icon is blank (real bug).
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes as wt
from PIL import Image

ICO = r"C:\Users\gaipu\Desktop\NetVisual-A-Plus-v4\NetVisual.ico"

# ---------- A. Win32 path (ground truth: what tray.py does) ----------
u = ctypes.WinDLL("user32", use_last_error=True)
g = ctypes.WinDLL("gdi32", use_last_error=True)
s = ctypes.WinDLL("shell32", use_last_error=True)

s.ExtractIconExW.argtypes = [ctypes.c_wchar_p, wt.UINT,
                             ctypes.POINTER(wt.HANDLE), ctypes.POINTER(wt.HANDLE),
                             wt.UINT]
s.ExtractIconExW.restype = wt.UINT

small = wt.HANDLE()
large = wt.HANDLE()
n = s.ExtractIconExW(ICO, 0, ctypes.byref(large), ctypes.byref(small), 2)
print(f"[A] ExtractIconExW count={n} small={'OK' if small else 'NONE'} "
      f"large={'OK' if large else 'NONE'}")

SIZE = 16
def render(hicon, size):
    if not hicon:
        return 0
    # DrawIconEx(hdc, hIcon, hdcDst, x, y, cxWidth, cyWidth, istepIfAni,
    #            hbrFlash, diFlags)  — 10 args.
    u.DrawIconEx.argtypes = [wt.HDC, wt.HANDLE, wt.HDC, ctypes.c_int, ctypes.c_int,
                             ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                             wt.HBRUSH, wt.UINT]
    u.DrawIconEx.restype = wt.BOOL
    screen = u.GetDC(None)
    dc = g.CreateCompatibleDC(screen)
    bmp = g.CreateCompatibleBitmap(screen, size, size)
    old = g.SelectObject(dc, bmp)
    ok = u.DrawIconEx(dc, hicon, None, 0, 0, size, size, 0, None, 0)
    # read pixels
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXP", ctypes.c_long),
                    ("biYP", ctypes.c_long), ("biCU", wt.DWORD), ("biCI", wt.DWORD)]
    class BI(ctypes.Structure):
        _fields_ = [("h", BIH), ("c", wt.DWORD * 1)]
    bi = BI(); bi.h.biSize = ctypes.sizeof(BIH); bi.h.biWidth = size
    bi.h.biHeight = -size; bi.h.biPlanes = 1; bi.h.biBitCount = 32
    buf = (ctypes.c_byte * (size * size * 4))()
    g.GetDIBits(dc, bmp, 0, size, buf, ctypes.byref(bi))
    opaque = sum(1 for i in range(size * size) if buf[i * 4 + 3] > 40)
    # save zoom
    img = Image.new("RGB", (size, size), (34, 34, 34))
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            if buf[i + 3] > 40:
                img.putpixel((x, y), (buf[i + 2], buf[i + 1], buf[i]))
    img.resize((size * 16, size * 16), Image.NEAREST).save("tray16_zoom.png")
    g.SelectObject(dc, old); g.DeleteObject(bmp); g.DeleteDC(dc)
    u.ReleaseDC(None, screen)
    return opaque, bool(ok)

res = render(small, SIZE)
print(f"[A] 16x16 small icon: opaque={res[0]}/{SIZE*SIZE} DrawIconEx_ok={res[1]}")

# ---------- B. Pillow path ----------
im = Image.open(ICO)
sizes = im.info.get("sizes")
print(f"[B] Pillow sizes in ico: {sorted(sizes)}")
# find a 16x16 frame by iterating
found = None
try:
    idx = 0
    while True:
        im.seek(idx)
        if im.size == (16, 16):
            found = im.copy().convert("RGBA")
            break
        idx += 1
except EOFError:
    pass
if found:
    px = found.load()
    op = sum(1 for y in range(16) for x in range(16) if px[x, y][3] > 40)
    found.resize((16 * 16, 16 * 16), Image.NEAREST).save("tray16_pillow.png")
    print(f"[B] 16x16 pillow frame: opaque={op}/256")
else:
    print("[B] no 16x16 frame found by Pillow (Win32 path is authoritative)")

print("\nsaved tray16_zoom.png (Win32) and/or tray16_pillow.png")
