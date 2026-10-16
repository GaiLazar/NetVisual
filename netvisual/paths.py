"""Filesystem locations for NetVisual.

Two distinct locations matter:

* **Writable data** (history DB, config, logs) must live in a STABLE place
  — next to the EXE (frozen) or the project root (source) — never in a
  temp dir, which PyInstaller wipes on every exit.
* **Read-only resources** (static/ dashboard, app icon) come from the
  bundled payload in a frozen build (``sys._MEIPASS`` temp dir), or from
  the project root in a source run.

Everything resolves the same from any CWD.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _exe_dir() -> Path | None:
    """The directory of the running .exe, or None in a source (unfrozen) run."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def _resource_root() -> Path:
    """Where read-only resources (static/, NetVisual.ico) live.

    Frozen: the temp bundle dir (``sys._MEIPASS``) — PyInstaller extracts
    the --add-data files there on every start.
    Source: the project root (parent of the netvisual/ package).
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Where writable data (data/, netvisual.json, logs) live.

    Frozen: next to the EXE (created on demand). This is the STABLE home
    for the history DB — a temp dir would be deleted on exit and the 30-day
    history would silently vanish on every restart.
    Source: the project root.
    """
    exe_dir = _exe_dir()
    if exe_dir is not None:
        return exe_dir
    return _resource_root()


ROOT: Path = data_root()          # writable home (data, config, logs)
STATIC: Path = _resource_root() / "static"   # read-only dashboard
DATA_DIR: Path = ROOT / "data"
CONFIG_PATH: Path = Path(os.environ.get(
    "NETVISUAL_CONFIG", str(ROOT / "netvisual.json")))
LOG_PATH: Path = ROOT / "server.log"


def icon_path() -> Path:
    """The app icon (.ico): prefer next to the EXE / project root (so the
    user can swap it), else the bundled copy in the frozen payload."""
    p = ROOT / "NetVisual.ico"
    if p.is_file():
        return p
    return _resource_root() / "NetVisual.ico"
