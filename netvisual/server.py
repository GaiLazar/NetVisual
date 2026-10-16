"""NetVisual A+ v4 — entry point.

Boots the modular package: loads config, initialises the history store,
launches the background sampler, and serves the REST API + static dashboard.

    python -m netvisual.server          # console mode (Ctrl+C to stop)
    python -m netvisual.server --tray   # system-tray mode (icon in taskbar)
    pythonw netvisual_app.py --tray     # desktop mode (no console, tray icon)

Shutdown semantics (both modes): the listening socket is ALWAYS closed
deterministically — ``server.shutdown()`` + ``server.server_close()`` run in a
``finally`` block, so the port is freed on every exit path (tray "Stop",
Ctrl+C, or the console window closing). The next start binds immediately.

Single-instance: if a NetVisual server already answers on the port, this start
just opens the existing dashboard instead of failing on the busy port.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

from . import config, history, paths, tray as tray_mod
from .api import Handler, history_snapshot

PORT = int(os.environ.get("NETVISUAL_PORT", "8730"))


def _log(msg: str) -> None:
    """Print, but survive pythonw mode (where sys.stdout is None)."""
    try:
        if sys.stdout:
            print(msg)
    except Exception:
        pass


def _want_tray() -> bool:
    """Tray mode: enabled by default on Windows when pystray is supported.
    Can be explicitly disabled with --no-tray, --console, or NETVISUAL_TRAY=0.
    """
    if not tray_mod.is_supported():
        return False
    if os.environ.get("NETVISUAL_TRAY", "").lower() in ("0", "false", "no", "off"):
        return False
    if "--no-tray" in sys.argv[1:] or "--console" in sys.argv[1:]:
        return False
    return True


def make_stoppable(srv, serve_thread=None):
    """Return a **one-shot** stop callable that safely tears down ``srv``.

    ``ThreadingHTTPServer.shutdown()`` is dangerous in two ways:
      1. called a **second** time it blocks forever (the internal
         "shut down" event is already consumed), and
      2. called **before** ``serve_forever`` ever ran it also blocks forever
         (nothing will ever set that event) — e.g. if tray creation raises
         between server creation and the serve loop.

    The tray "Stop" and ``main()``'s ``finally`` both want to stop the server,
    and the exit path must **never hang**, so the teardown:
      • runs exactly once (one-shot guard), and
      • runs ``shutdown()`` in a daemon thread with a 3s join, so even a
        never-started / already-stopped server can't wedge the process, and
      • if ``serve_thread`` (the thread running ``serve_forever``) is given,
        waits for that loop to exit BEFORE closing the socket. Closing first
        makes the loop's ``select()`` fail with WinError 10038 and CPython
        prints a spurious "Exception in thread http-server" at shutdown.

    Either way ``server_close()`` frees the listening socket, so the port is
    released deterministically on every exit path.
    """
    lock = threading.Lock()
    state = {"stopped": False}

    def stop():
        with lock:
            if state["stopped"]:
                return
            state["stopped"] = True
        try:
            # NOTE: _BaseServer__is_shut_down is a threading.Event, not a bool.
            # Checking its truthiness (as `if not <event>`) is always False —
            # so it must be .is_set(), or shutdown() is silently skipped and
            # server_close() kills the serve loop mid-select (WinError 10038).
            shut = getattr(srv, "_BaseServer__is_shut_down", None)
            if shut is None or not shut.is_set():
                t = threading.Thread(target=srv.shutdown, daemon=True,
                                     name="http-shutdown")
                t.start()
                t.join(timeout=3)  # never let the exit path hang
        except Exception:
            pass
        try:
            if (serve_thread is not None
                    and serve_thread is not threading.current_thread()
                    and serve_thread.is_alive()):
                serve_thread.join(timeout=3)  # let select() exit cleanly
        except Exception:
            pass
        try:
            srv.server_close()   # close the listening socket -> frees the port
        except Exception:
            pass

    return stop


def _port_live(port: int) -> bool:
    """True if something is already accepting connections on 127.0.0.1:port.

    TIME_WAIT sockets do NOT count — connect_ex only succeeds on a live listener.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def _winbox(title: str, msg: str) -> None:
    """Native Windows message box (used in tray/desktop mode where no console)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, title, 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


def main():
    cfg = config.load()
    config_path = config.write_defaults()
    history.init()
    interval = cfg["history"]["interval_seconds"]
    if int(os.environ.get("NETVISUAL_HISTORY_INTERVAL", interval)) > 0:
        history.start_sampl(history_snapshot)

    from . import __version__
    url = f"http://127.0.0.1:{PORT}"
    use_tray = _want_tray()

    # Single-instance: an existing server → just open its dashboard.
    if _port_live(PORT):
        _log(f"NetVisual already running at {url} — opening the dashboard.")
        if use_tray:
            _winbox("NetVisual A+",
                    "NetVisual is already running.\nOpening the existing dashboard.")
        webbrowser.open(url)
        return

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)

    _log(f"NetVisual A+ v{__version__} running  →  {url}")
    _log(f"History store: {history.DB_PATH} (every {history.SAMPLE_INTERVAL}s, "
         f"{history.RETENTION_DAYS}d retention)")
    _log(f"Config: {config_path} (alerts: {len(cfg['alerts'])} thresholds)")
    _log("Probing: ipconfig, arp, route, netstat, ping, nslookup, tracert")
    _log("Stop: 'Stop NetVisual' in the tray menu" if use_tray
         else "Stop: Ctrl+C")

    # ONE stop callable shared by the tray and the finally-block. Calling
    # ThreadingHTTPServer.shutdown() twice deadlocks, so the guard is essential.
    # The serve thread (tray mode) is created first so stop() can join it
    # before closing the socket — otherwise the loop's select() dies on a
    # closed socket and CPython prints a spurious exception at shutdown.
    srv_thread = None
    if use_tray:
        srv_thread = threading.Thread(target=srv.serve_forever,
                                      name="http-server", daemon=True)
    stop = make_stoppable(srv, srv_thread)
    Handler.SHUTDOWN_CALLBACK = stop
    try:
        if use_tray:
            # Server in a daemon thread; the Win32 message loop must live on
            # the main thread. Tray "Stop" calls stop() to end it.
            srv_thread.start()
            # Open the dashboard in browser on initial launch
            threading.Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)),
                             daemon=True).start()
            tr = tray_mod.TrayIcon(str(paths.icon_path()),
                                   f"NetVisual A+ · {url}", url,
                                   server_close=stop)
            tr.run()
        else:
            srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Deterministic port release on EVERY exit path (tray Stop, Ctrl+C,
        # console closed): next start binds immediately, no "port in use".
        stop()
        _log("port released — bye")


if __name__ == "__main__":
    main()
