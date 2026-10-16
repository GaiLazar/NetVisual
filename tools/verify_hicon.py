"""Prove the tray HICON renders as a real (non-blank) image.

Loads NetVisual.ico exactly the way netvisual/tray.py does (ExtractIconExW),
draws it onto a dark 32x32 bitmap via DrawIconEx, counts opaque pixels, and
saves a 12x zoom.

  - opaque < 20  -> the icon is BLANK (registered but invisible: real bug)
  - opaque >= 20 -> the icon is valid; if it's not on the taskbar it's simply
                    in the Windows 11 overflow area (the "^" chevron), which is
                    normal OS behaviour, not an app bug.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from PIL import Image

u = ctypes.WinDLL("user32", use_last_error=True)
g = ctypes.WinDLL("gdi32", use_last_error=True)
s = ctypes.WinDLL("shell32", use_last_error=True)

# --- prototypes (full, correct signatures) ---
s.ExtractIconExW.argtypes = [ctypes.c_wchar_p, wt.UINT,
                             ctypes.POINTER(wt.HANDLE), ctypes.POINTER(wt.HANDLE),
                             wt.UINT]
s.ExtractIconExW.restype = wt.UINT

u.LoadImageW.argtypes = [wt.HINSTANCE, ctypes.c_wchar_p, wt.UINT,
                         ctypes.c_int, ctypes.c_int, wt.UINT]
u.LoadImageW.restype = wt.HANDLE

g.CreateCompatibleDC.argtypes = [wt.HDC]
g.CreateCompatibleDC.restype = wt.HDC
g.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
g.CreateCompatibleBitmap.restype = wt.HBITMAP
g.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
g.SelectObject.restype = wt.HGDIOBJ
g.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
g.CreateSolidBrush.argtypes = [ctypes.c_uint]
g.CreateSolidBrush.restype = wt.HBRUSH

u.FillRect.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), wt.HBRUSH]
u.FillRect.restype = wt.BOOL

# DrawIconEx(hdc, hIcon, hdcDst, x, y, cx, cy, uStep, crTransparent)
u.DrawIconEx.argtypes = [wt.HDC, wt.HANDLE, wt.HDC, ctypes.c_int, ctypes.c_int,
                         ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                         ctypes.c_uint]
u.DrawIconEx.restype = wt.BOOL

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPels", ctypes.c_long),
                ("biYPels", ctypes.c_long), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 1)]

g.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, ctypes.c_uint, ctypes.c_uint,
                        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO)]
g.GetDIBits.restype = ctypes.c_int

ICON_PATH = r"C:\Users\gaipu\Desktop\NetVisual-A-Plus-v4\NetVisual.ico"
SIZE = 32

# 1. load exactly as tray.py does
small = wt.HANDLE()
n = s.ExtractIconExW(ICON_PATH, 0, None, ctypes.byref(small), 1)
print(f"ExtractIconExW count={n} small={'OK' if small else 'NONE'}")
hicon = small
if not hicon:
    hicon = u.LoadImageW(None, ICON_PATH, 1, 0, 0, 0x10 | 0x8000)
assert hicon, "no icon handle at all"

# 2. render on a dark 32x32
screen = u.GetDC(None)
dc = g.CreateCompatibleDC(screen)
bmp = g.CreateCompatibleBitmap(screen, SIZE, SIZE)
old = g.SelectObject(dc, bmp)
g.SetBkMode(dc, 1)
brush = g.CreateSolidBrush(0x00222222)
rect = wt.RECT(0, 0, SIZE, SIZE)
u.FillRect(dc, ctypes.byref(rect), brush)
ok = u.DrawIconEx(dc, hicon, None, 0, 0, SIZE, SIZE, 0, 0)
print(f"DrawIconEx -> {bool(ok)}")

# 3. read pixels
bi = BITMAPINFO()
bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bi.bmiHeader.biWidth = SIZE
bi.bmiHeader.biHeight = -SIZE
bi.bmiHeader.biPlanes = 1
bi.bmiHeader.biBitCount = 32
bi.bmiHeader.biCompression = 0
buf = (ctypes.c_byte * (SIZE * SIZE * 4))()
got = g.GetDIBits(dc, bmp, 0, SIZE, buf, ctypes.byref(bi))
print(f"GetDIBits rows={got}")

opaque = mint = 0
for i in range(SIZE * SIZE):
    b, gg, r, a = buf[i*4], buf[i*4+1], buf[i*4+2], buf[i*4+3]
    if a > 40:
        opaque += 1
        if abs(r-54) <= 45 and abs(gg-234) <= 45 and abs(b-175) <= 45:
            mint += 1
print(f"opaque={opaque}/{SIZE*SIZE}  mint-ish={mint}")
if opaque < 20:
    print("VERDICT: BLANK icon (real bug in load_icon)")
else:
    print("VERDICT: icon renders fine (any invisibility = Win11 overflow area)")

# 4. 12x zoom (BGRA->RGB)
img = Image.new("RGB", (SIZE, SIZE))
for y in range(SIZE):
    for x in range(SIZE):
        i = (y*SIZE+x)*4
        img.putpixel((x, y), (buf[i+2], buf[i+1], buf[i]))
img.resize((SIZE*12, SIZE*12), Image.NEAREST).save("hicon_zoom.png")
print("saved hicon_zoom.png")

g.SelectObject(dc, old)
g.DeleteObject(bmp)
g.DeleteObject(brush)
g.DeleteDC(dc)
u.DestroyIcon(hicon)
u.ReleaseDC(None, screen)
