"""Gateway-latency ring: ping the default gateway on demand and keep history.

The default target is the gateway (re-resolved every 30s in case the default
route changes). The ring feeds ``GET /api/latency`` and the history sampler
(``lat_ms`` / ``gw_up``).
"""
from __future__ import annotations

import threading
import time

from ..ping import ping
from ..safety import safe_ip
from ..selfinfo import self_netinfo

_LATENCY_MAX = 120  # ~6 min at 3s polling

_latency: list[dict] = []
_latency_lock = threading.Lock()
_lat_target = {"ip": None, "t": 0.0}


def _target() -> str | None:
    """Cached gateway IP, re-resolved every 30s."""
    with _latency_lock:
        if _lat_target["ip"] and time.time() - _lat_target["t"] < 30:
            return _lat_target["ip"]
    gw = None
    try:
        gw = self_netinfo().get("gateway")
    except Exception:
        gw = None
    if gw and safe_ip(gw):
        with _latency_lock:
            _lat_target["ip"] = gw
            _lat_target["t"] = time.time()
    return gw


def sample() -> dict:
    """Ping the gateway once, append to the ring, return sample + history."""
    target = _target()
    if target and safe_ip(target):
        r = ping(target, 1)
        point = {"ts": time.time(), "host": target, "ms": r.get("avg_ms"),
                 "reachable": bool(r.get("reachable"))}
    else:
        point = {"ts": time.time(), "host": None, "ms": None, "reachable": False}
    with _latency_lock:
        _latency.append(point)
        if len(_latency) > _LATENCY_MAX:
            _latency[:] = _latency[-_LATENCY_MAX:]
        hist = list(_latency)
    return {"sample": point, "history": hist[-60:]}


def last_reachability() -> tuple[float | None, bool | None]:
    """(last known gateway latency ms, last known up/down) or (None, None)."""
    with _latency_lock:
        for p in reversed(_latency):
            if p.get("ms") is not None:
                return p["ms"], bool(p.get("reachable"))
    return None, None
