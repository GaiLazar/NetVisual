"""The ``history_snapshot`` provider for the background sampler.

Cheap: reuses the already-cached summary + the live traffic/latency rings, so
the sampler thread adds no extra subprocess work. Returns the dict shape the
history store's ``record()`` expects (ts, rx_bps, tx_bps, recv/sent totals,
devices, connections, tcp_est, lat_ms, gw_up, ips).
"""
from __future__ import annotations

import time

from .. import notifier, state, summary
from .. import topology as topo


def history_snapshot() -> dict:
    """Current snapshot for the persistent history store."""
    s = summary.summary()
    # last bandwidth sample from the traffic ring
    hist = state.traffic_history()
    last = hist[-1] if hist else {}
    # gateway latency: last non-null sample (or None)
    lat, gw_up = state.last_reachability()
    # current set of discovered device IPs → enables appear/disappear tracking
    t_data = topo.probe()
    nodes = t_data.get("nodes", [])
    ips = [{"ip": n["ip"], "kind": n.get("kind", "device")}
           for n in nodes if n.get("kind") == "device" and n.get("ip")]

    # Evaluate notification alerts (new device, gateway down)
    notifier.evaluate_events(nodes, gw_up)
    return {
        "ts": int(time.time()),
        "rx_bps": last.get("rx_bps", 0),
        "tx_bps": last.get("tx_bps", 0),
        "recv_total": last.get("recv_total", 0),
        "sent_total": last.get("sent_total", 0),
        "devices": s.get("neighbors", 0),
        "connections": s.get("connections", 0),
        "tcp_est": s.get("tcp_established", 0),
        "lat_ms": lat,
        "gw_up": gw_up,
        "ips": ips,
    }
