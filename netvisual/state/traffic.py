"""Live bandwidth ring: bytes/sec computed between successive ``netstat -e`` reads.

Pure rate computation — it does not touch the activity feed (the probe layer
decides what's "notable"). Kept in its own module so the ring, its lock, and
the delta logic are all inspectable together.
"""
from __future__ import annotations

import threading
import time

from ..parsers import parse_netstat_e
from ..runner import run

_TRAFFIC_MAX = 120  # ~2 min at 1s sampling

_traffic: list[dict] = []
_traffic_lock = threading.Lock()


def sample() -> dict:
    """Compute bytes/sec since the last call; append to the ring; return it.

    Point shape: ``{"ts","rx_bps","tx_bps","recv_total","sent_total"}``.
    """
    s = parse_netstat_e(run("netstat -e", 8)[1])
    ts = time.time()
    with _traffic_lock:
        prev = _traffic[-1] if _traffic else None
        if prev:
            dt = max(ts - prev["ts"], 1.0)
            rx_bps = max(0.0, (s["recv_bytes"] - prev["recv_total"]) / dt)
            tx_bps = max(0.0, (s["sent_bytes"] - prev["sent_total"]) / dt)
        else:
            rx_bps = tx_bps = 0.0
        point = {
            "ts": ts, "rx_bps": round(rx_bps, 1), "tx_bps": round(tx_bps, 1),
            "recv_total": s["recv_bytes"], "sent_total": s["sent_bytes"],
        }
        _traffic.append(point)
        if len(_traffic) > _TRAFFIC_MAX:
            _traffic[:] = _traffic[-_TRAFFIC_MAX:]
    return point


def history() -> list[dict]:
    """A copy of the full bandwidth ring (oldest first)."""
    with _traffic_lock:
        return list(_traffic)
