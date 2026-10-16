"""Open the Win11 tray overflow (chevron) and locate the NetVisual icon.

1. SendInput left-click on the chevron (physical coords via normalized virtual
   screen) to reveal the overflow popup.
2. Screenshot the full screen.
3. Scan for a DENSE cluster of the icon's mint hub colour (wallpaper is
   scattered; an icon is a tight blob). Report location + save a zoom.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from PIL import Image, ImageGrab

u = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _virtual_screen():
    # single-monitor virtual screen == desktop resolution
    x = u.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    y = u.GetSystemMetrics(77)
    w = u.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
    h = u.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
    return x, y, w, h


def click(vx: int, vy: int):
    """Physical-screen click at virtual coords (vx,vy)."""
    _, _, vw, vh = _virtual_screen()
    nx = int((vx - 0) / vw * 65535)
    ny = int((vy - 0) / vh * 65535)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    def ev(flags):
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.u.mi.dx = nx
        inp.u.mi.dy = ny
        inp.u.mi.dwFlags = flags
        inp.u.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
        return inp

    u.SendInput(1, ctypes.byref(ev(MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN)),
                ctypes.sizeof(INPUT))
    u.SendInput(1, ctypes.byref(ev(MOUSEEVENTF_LEFTUP)),
                ctypes.sizeof(INPUT))


def main():
    # chevron: left edge of the notification area. TrayNotifyWnd top-left in
    # virtual coords is (876,648); chevron sits ~8px in, ~middle of the bar.
    click(884, 684)
    time.sleep(1.2)

    im = ImageGrab.grab(all_screens=True).convert("RGB")
    w, h = im.size
    px = im.load()
    print(f"screenshot {w}x{h}")

    MINT = (54, 234, 175)

    def near(c, tol=26):
        return (abs(c[0] - MINT[0]) <= tol and abs(c[1] - MINT[1]) <= tol
                and abs(c[2] - MINT[2]) <= tol)

    hits = []
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if near(px[x, y]):
                hits.append((x, y))
    if not hits:
        print("no mint pixels anywhere — icon not rendered")
        return
    # keep only dense clusters: count neighbours within 24px
    from collections import defaultdict
    grid = defaultdict(int)
    for (x, y) in hits:
        grid[(x // 24, y // 24)] += 1
    dense = [(x, y) for (x, y) in hits if grid[(x // 24, y // 24)] >= 4]
    print(f"mint pixels total={len(hits)} dense-cluster={len(dense)}")
    if dense:
        xs = [p[0] for p in dense]
        ys = [p[1] for p in dense]
        cx, cy = sum(xs) // len(xs), sum(ys) // len(ys)
        print(f"DENSE ICON CLUSTER center=({cx},{cy}) "
              f"x[{min(xs)}..{max(xs)}] y[{min(ys)}..{max(ys)}]")
        pad = 48
        im.crop((cx - pad, cy - pad, cx + pad, cy + pad)) \
          .resize((pad * 8, pad * 8), Image.LANCZOS).save("icon_visible.png")
        print("saved icon_visible.png (8x zoom)")


if __name__ == "__main__":
    main()
