"""Windows system-tray icon for NetVisual.

Built on **pystray** (pure-Python, only needs Pillow) — it handles the
Windows 10/11 notification-area click-delivery quirks that a raw
``Shell_NotifyIconW`` implementation gets wrong (icon shows, clicks never
arrive). pystray is loaded lazily so the rest of the app stays zero-dep when
running in console mode; tray mode requires it (pip install pystray).

Behaviour:
    • left click (single or double)  → open the dashboard in the browser
    • right click                    → menu:  "Open dashboard"
                                       "Stop NetVisual"
    • "Stop NetVisual"               → ``server_close()`` (frees the port),
                                       then the icon stops and the process
                                       exits via the server's one-shot stop.

Headless-testable: ``load_image()`` works without a message loop.
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser

_WIN = sys.platform.startswith("win")


def is_supported() -> bool:
    """True where the tray icon can actually run (Windows + pystray importable)."""
    if not _WIN:
        return False
    try:
        import pystray  # noqa: F401
    except ImportError:
        return False
    return True


def _load_pystray():
    import pystray
    return pystray


class TrayIcon:
    """A notification-area icon for a running NetVisual server.

    ``icon_path``    — the .ico/.png to display (falls back to Pillow's
                       built-in if missing).
    ``tip``          — tooltip text.
    ``open_url``     — opened on left click / "Open dashboard".
    ``server_close`` — called by "Stop NetVisual" before the icon stops;
                       the server uses this to release the port.
    """

    def __init__(self, icon_path: str, tip: str, open_url: str,
                 server_close):
        self.icon_path = icon_path
        self.tip = tip[:127]
        self.open_url = open_url
        self.server_close = server_close
        self._item = None

    # ------------------------------------------------------------------ #
    # icon (headless-safe)
    # ------------------------------------------------------------------ #
    def load_image(self):
        """Return a PIL image for the tray. Falls back to a generated
        network-node PNG if ``icon_path`` is missing/unreadable.
        """
        from PIL import Image
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                return Image.open(self.icon_path).convert("RGBA")
            except Exception:
                pass
        return self._fallback_image()

    @staticmethod
    def _fallback_image():
        """A small mint 'hub + spokes' image, drawn with Pillow only."""
        from PIL import Image, ImageDraw
        S = 64
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([2, 2, S - 2, S - 2], fill=(11, 20, 34, 255),
                  outline=(34, 211, 238, 255), width=3)
        import math
        cx = cy = S / 2
        for k in range(6):
            a = math.radians(60 * k - 90)
            x2 = cx + 20 * math.cos(a)
            y2 = cy + 20 * math.sin(a)
            d.line([cx, cy, x2, y2], fill=(34, 211, 238, 255), width=3)
            d.ellipse([x2 - 4, y2 - 4, x2 + 4, y2 + 4],
                      fill=(236, 242, 250, 255))
        d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(54, 234, 175, 255))
        return img

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def _open_url(self, *args):
        threading.Thread(target=lambda: webbrowser.open(self.open_url),
                         daemon=True).start()

    def _stop(self, *args):
        # Free the port first (server_close is the one-shot guarded stop),
        # then stop the icon from ANOTHER thread — pystray's stop() posts a
        # quit message to the loop, so calling it from the callback thread
        # that is itself inside the loop would deadlock.
        try:
            self.server_close()
        except Exception:
            pass
        threading.Thread(target=self._stop_item, daemon=True).start()

    def _stop_item(self):
        try:
            if self._item is not None:
                self._item.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # run (blocking; the pystray loop must own its own thread)
    # ------------------------------------------------------------------ #
    def run(self):
        """Show the icon and block until "Stop NetVisual" is chosen.
        Returns after the icon has been removed.

        On Windows, clicking the icon (left or right) opens the menu with
        "Open dashboard" / "Stop NetVisual" — pystray handles all the
        Win10/11 notification-area plumbing.
        """
        pystray = _load_pystray()
        icon = pystray.Icon(
            "netvisual",
            self.load_image(),
            self.tip,
            menu=(
                pystray.MenuItem("Open dashboard", self._open_url, default=True),
                pystray.MenuItem("Stop NetVisual", self._stop),
            ),
        )
        self._item = icon
        # one-time balloon so the user notices it is running
        try:
            icon.notify("Dashboard is live — click me to open it",
                        "NetVisual A+")
        except Exception:
            pass
        stop_after = os.environ.get("NETVISUAL_TRAY_STOP_AFTER")
        if stop_after:
            try:
                sec = float(stop_after)
                if sec > 0:
                    threading.Timer(sec, self._stop).start()
            except ValueError:
                pass
        icon.run()   # blocks until _stop() -> item.stop()
