"""Aggregate dashboard summary (``GET /api/summary``).

Combines the cached probes into one small dict for the overview cards. Reuses
already-cached results so it adds no extra subprocess work.
"""
from __future__ import annotations

import socket
import time

from . import probes, topology
from .cache import get
from .selfinfo import self_netinfo


def summary() -> dict:
    """Return the one-line network summary for the overview strip."""
    info = get("self", self_netinfo)
    ifaces = probes.probe_interfaces()["interfaces"]
    routes = probes.probe_routes()["routes"]
    conns = probes.probe_connections()["connections"]
    topo = topology.probe()
    neighbors = sum(1 for n in topo["nodes"] if n["kind"] == "device")
    return {
        "hostname": socket.gethostname(),
        "self_ip": info["ip"],
        "gateway": info["gateway"],
        "subnet": info["network"],
        "mac": info["mac"],
        "interfaces": len(ifaces),
        "neighbors": neighbors,
        "routes": len(routes),
        "connections": len(conns),
        "tcp_established": sum(1 for c in conns if c["state"] == "ESTABLISHED"),
        "topo_nodes": len(topo["nodes"]),
        "ts": int(time.time()),
    }
