"""Reveal the Win11 notification-area overflow and report the icons in it.

Steps:
 1. SendInput left-click the overflow chevron (left edge of the tray cluster).
 2. Wait, grab the full physical screen.
 3. Crop the overflow popup region (TopLevelWindowForOverflowXamlIsland rect)
    and the taskbar's right cluster.
 4. Threshold LIGHT pixels (Win11 draws tray icons as white/gray on the dark
    taskbar — NOT their real colour) and report each icon's x-centre + size.
 5. Save 3x zoom crops so the result is inspectable.

Physical screen = virtual x 2.5 (1152x720 virtual -> 2880x1800 physical).
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes as wt
import time
from PIL import ImageGrab

u = ctypes.WinDLL("user32", use_last_error=True)
SC = 2.5  # physical / virtual scale


def _vs():
    return (u.GetSystemMetrics(76), u.GetSystemMetrics(77),
            u.GetSystemMetrics(78), u.GetSystemMetrics(79))


def click(vx, vy):
    _, _, vw, vh = _vs()
    nx = int(vx / vw * 65535)
    ny = int(vy / vh * 65535)

    class MI(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("md", wt.DWORD),
                    ("fl", wt.DWORD), ("tm", wt.DWORD),
                    ("ei", ctypes.POINTER(ctypes.c_ulong))]

    class IN(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MI)]
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    MOVE, LDOWN, LUP = 0x1, 0x2, 0x4

    def ev(fl):
        i = IN(); i.type = 0
        i.u.mi.dx = nx; i.u.mi.dy = ny; i.u.mi.fl = fl
        i.u.mi.ei = ctypes.pointer(ctypes.c_ulong(0))
        return i

    u.SendInput(1, ctypes.byref(ev(MOVE | LDOWN)), ctypes.sizeof(IN))
    u.SendInput(1, ctypes.byref(ev(LUP)), ctypes.sizeof(IN))


def clusters(im, x0, y0, x1, y1, light_thr=110):
    """Return light-pixel clusters (icons) in the region, as (cx, n, w, h)."""
    px = im.convert("RGB").load()
    W, H = im.size
    pts = []
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            r, g, b = px[x, y]
            if r > light_thr and g > light_thr and b > light_thr:
                pts.append((x, y))
    if not pts:
        return []
    # greedy 8-px grid clustering
    grid = {}
    for (x, y) in pts:
        grid.setdefault((x // 10, y // 10), []).append((x, y))
    out = []
    for (gx, gy), cells in grid.items():
        xs = [p[0] for p in cells]
        ys = [p[1] for p in cells]
        out.append((sum(xs) // len(xs), len(cells),
                    max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    out.sort(key=lambda c: c[0])
    return out


def main():
    # overflow chevron: just left of the tray cluster (virtual x ~870, y ~684)
    click(870, 684)
    time.sleep(1.6)

    im = ImageGrab.grab(all_screens=True)
    W, H = im.size
    print(f"screen {W}x{H}  (scale {SC})")

    # overflow popup region (virtual 775,558,1009,672 -> physical)
    ov = (int(775 * SC), int(558 * SC), int(1009 * SC), int(672 * SC))
    # taskbar right cluster (virtual 860,648,1152,720 -> physical)
    tb = (int(860 * SC), int(648 * SC), int(1152 * SC), int(720 * SC))

    for name, (x0, y0, x1, y1) in (("OVERFLOW", ov), ("TASKBAR-right", tb)):
        cl = clusters(im, x0, y0, x1, y1)
        print(f"{name}: {len(cl)} light clusters")
        for (cx, n, w, h) in cl:
            print(f"   x={cx}  n={n}  {w}x{h}")

    # save 3x zooms
    ov_crop = im.crop(ov)
    ov_crop.resize((ov_crop.width * 3, ov_crop.height * 3),
                   ImageGrab.Image.LANCZOS if hasattr(ImageGrab, "Image") else None) \
        .save("overflow_zoom.png")
    from PIL import Image as _I
    ov.crop if False else None
    im.crop(ov).resize(((ov[2] - ov[0]) * 3, (ov[3] - ov[1]) * 3), _I.LANCZOS) \
        .save("overflow_zoom.png")
    im.crop(tb).resize(((tb[2] - tb[0]) * 3, (tb[3] - tb[1]) * 3), _I.LANCZOS) \
        .save("taskbar_zoom.png")
    print("saved overflow_zoom.png + taskbar_zoom.png")


if __name__ == "__main__":
    main()
