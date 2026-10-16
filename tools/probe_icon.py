"""Definitive: inspect the actual HICON the tray uses, via GetIconInfo+GetDIBits.

Loads NetVisual.ico through BOTH loaders netvisual/tray.py uses:
  1. LoadImageW(hInst=NULL, path, IMAGE_ICON, 0,0, LR_LOADFROMFILE|LR_SHARED)
  2. ExtractIconExW(path, 0, &large, &small, 1)  -> large
Then for each HICON: GetIconInfo -> hbmColor -> GetDIBits -> count non-transparent
pixels. This is the real pixel content the shell would draw. A non-zero count
means the icon is visible; zero means blank.

Also prints the HICON's actual width/height (GetIconInfo -> BITMAP.bmWidth/Height
of hbmColor) so we can catch a 0x0 / wrong-size icon.
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes as wt

u = ctypes.WinDLL("user32", use_last_error=True)
g = ctypes.WinDLL("gdi32", use_last_error=True)
s = ctypes.WinDLL("shell32", use_last_error=True)

u.LoadImageW.argtypes = [wt.HINSTANCE, ctypes.c_wchar_p, wt.UINT,
                         ctypes.c_int, ctypes.c_int, wt.UINT]
u.LoadImageW.restype = wt.HANDLE
u.DestroyIcon.argtypes = [wt.HANDLE]
s.ExtractIconExW.argtypes = [ctypes.c_wchar_p, wt.UINT,
                             ctypes.POINTER(wt.HANDLE), ctypes.POINTER(wt.HANDLE),
                             wt.UINT]
s.ExtractIconExW.restype = wt.UINT

class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.UINT), ("yHotspot", wt.UINT),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]
u.GetIconInfo.argtypes = [wt.HANDLE, ctypes.POINTER(ICONINFO)]
u.GetIconInfo.restype = wt.BOOL

class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long),
                ("bmHeight", ctypes.c_long), ("bmWidthBytes", ctypes.c_long),
                ("bmPlanes", wt.WORD), ("bmBitsPixel", wt.WORD), ("bmBits", ctypes.c_void_p)]
g.GetObjectW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.POINTER(BITMAP)]
g.GetObjectW.restype = ctypes.c_int

class BIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXP", ctypes.c_long), ("biYP", ctypes.c_long),
                ("biCU", wt.DWORD), ("biCI", wt.DWORD)]
class BI(ctypes.Structure):
    _fields_ = [("h", BIH), ("c", wt.DWORD * 1)]
g.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, ctypes.c_uint, ctypes.c_uint,
                        ctypes.c_void_p, ctypes.POINTER(BI)]
g.GetDIBits.restype = ctypes.c_int
g.DeleteObject.argtypes = [wt.HANDLE]

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
LR_SHARED = 0x8000

def inspect(hicon, label):
    if not hicon:
        print(f"  [{label}] HICON is NULL — loader FAILED")
        return
    ii = ICONINFO()
    if not u.GetIconInfo(hicon, ctypes.byref(ii)):
        print(f"  [{label}] GetIconInfo failed err={ctypes.get_last_error()}")
        return
    hbm = ii.hbmColor
    if not hbm:
        print(f"  [{label}] hbmColor=NULL (1-bit monochrome icon) — likely renders as 1-bit")
    else:
        bm = BITMAP()
        g.GetObjectW(hbm, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        w, h = bm.bmWidth, abs(bm.bmHeight)
        bits = bm.bmBitsPixel
        hdc = u.GetDC(None)
        bi = BI()
        bi.h.biSize = ctypes.sizeof(BIH)
        bi.h.biWidth = w
        bi.h.biHeight = -h
        bi.h.biPlanes = 1
        bi.h.biBitCount = 32
        n = w * h * 4
        buf = ctypes.create_string_buffer(n)
        got = g.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(bi))
        opaque = 0
        if got == h and n >= w * h * 4:
            for i in range(w * h):
                a = buf[i * 4 + 3]
                if a > 40:
                    opaque += 1
        u.ReleaseDC(None, hdc)
        verdict = "VISIBLE" if opaque > 0 else "BLANK"
        print(f"  [{label}] {w}x{h} {bits}bpp  opaque={opaque}/{w*h}  -> {verdict}")
    if ii.hbmMask:
        g.DeleteObject(ii.hbmMask)
    if ii.hbmColor:
        g.DeleteObject(ii.hbmColor)
    u.DestroyIcon(hicon)

ICO = r"C:\Users\gaipu\Desktop\NetVisual-A-Plus-v4\NetVisual.ico"
print(f"icon file: {ICO}")
h1 = u.LoadImageW(None, ICO, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_SHARED)
inspect(h1, "LoadImageW(LR_LOADFROMFILE)")
large = wt.HANDLE(); small = wt.HANDLE()
n = s.ExtractIconExW(ICO, 0, ctypes.byref(large), ctypes.byref(small), 2)
print(f"ExtractIconExW count={n} large={'OK' if large else 'NONE'} small={'OK' if small else 'NONE'}")
inspect(large, "ExtractIconExW large")
if small:
    inspect(small, "ExtractIconExW small")
