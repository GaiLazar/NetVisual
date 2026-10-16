"""Ping-sweep progress tracker.

The UI polls ``GET /api/scan-status`` while a deep scan runs; this ring keeps
the live counters (total/done/found/percent) so the progress gauge can update
without re-running the sweep.
"""
from __future__ import annotations

import threading
import time

_state = {
    "running": False, "total": 0, "done": 0, "found": 0, "found_ips": [],
    "started_at": None, "finished_at": None,
}
_lock = threading.Lock()


def begin(total: int) -> None:
    with _lock:
        _state.update(running=True, total=total, done=0, found=0,
                      found_ips=[], started_at=time.time(), finished_at=None)


def tick(ip: str | None) -> None:
    """Advance the counter once per host (thread-safe)."""
    if ip:
        _state["found"] += 1
        if len(_state["found_ips"]) < 200:
            _state["found_ips"].append(ip)
    _state["done"] += 1


def end() -> None:
    with _lock:
        _state["running"] = False
        _state["done"] = _state["total"]
        _state["finished_at"] = time.time()


def status() -> dict:
    with _lock:
        st = dict(_state)
    st["percent"] = round(100 * st["done"] / st["total"]) if st["total"] else 0
    return st
