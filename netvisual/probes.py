"""Cached data providers — the "probes".

Each ``probe_*`` wraps a (possibly expensive) subprocess + parse behind the
TTL :mod:`netvisual.cache`, so repeated UI polls are cheap. This module is the
composition layer over :mod:`netvisual.parsers`, :mod:`netvisual.runner`,
:mod:`netvisual.selfinfo`, and the live state modules.
"""
from __future__ import annotations

import os
from typing import Any

from . import state
from .cache import get
from .parsers import (
    parse_ipconfig, parse_arp, parse_netstat, parse_routes,
    parse_tasklist_csv,
)
from .runner import run
from .selfinfo import self_netinfo


# --------------------------------------------------------------------------- #
# Interfaces
# --------------------------------------------------------------------------- #
def probe_interfaces() -> dict:
    """Interface list. If ipconfig parsing yields nothing (unusual locale),
    fall back to the socket/route-derived ``self_netinfo()`` for a Primary row."""
    data = get("ifaces", lambda: {"interfaces": parse_ipconfig(run("ipconfig /all", 15)[1])})
    if not data["interfaces"]:
        i = self_netinfo()
        if i["ip"]:
            data["interfaces"] = [{
                "name": "Primary", "ip": i["ip"], "gw": i["gateway"],
                "mac": i["mac"], "subnet": i["subnet"],
                "prefix": i["prefix"], "network": i["network"],
                "dns": [], "dhcp": None,
            }]
    return data


# --------------------------------------------------------------------------- #
# Neighbours (ARP)
# --------------------------------------------------------------------------- #
def probe_arp() -> dict:
    return get("arp", lambda: {"neighbors": parse_arp(run("arp -a", 10)[1])})


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def probe_routes() -> dict:
    return get("routes", lambda: {"routes": parse_routes(run("route print", 10)[1])})


# --------------------------------------------------------------------------- #
# Connections + process names
# --------------------------------------------------------------------------- #
def process_names() -> dict[int, str]:
    """Map pid → process name. Cached 60s (tasklist is a bit heavy)."""
    data = get("procs", lambda: {"map": parse_tasklist_csv(run("tasklist /fo csv /nh", 15)[1])},
               ttl=60)
    return data["map"]


def probe_connections() -> dict:
    """``netstat -ano`` rows, enriched with process names + listening-port events."""
    def _build() -> dict:
        conns = parse_netstat(run("netstat -ano", 15)[1])
        names = process_names()
        for c in conns:
            try:
                c["process"] = names.get(int(c["pid"]), "")
            except (ValueError, TypeError):
                c["process"] = ""
        listen_ports = []
        for c in conns:
            if c["state"] == "LISTENING":
                lp = c["local"].rsplit(":", 1)[-1]
                if lp.isdigit():
                    listen_ports.append(int(lp))
        state.record_listening(listen_ports)
        return {"connections": conns}
    return get("conn", _build)


# --------------------------------------------------------------------------- #
# Live bandwidth
# --------------------------------------------------------------------------- #
def probe_traffic() -> dict:
    """Live bandwidth sample + recent history + window stats (peak/avg)."""
    sample = state.traffic_sample()
    hist = state.traffic_history()[-60:]
    rx = [p.get("rx_bps", 0) for p in hist]
    tx = [p.get("tx_bps", 0) for p in hist]
    stats = {
        "rx_peak": max(rx) if rx else 0,
        "tx_peak": max(tx) if tx else 0,
        "rx_avg": round(sum(rx) / len(rx)) if rx else 0,
        "tx_avg": round(sum(tx) / len(tx)) if tx else 0,
        "samples": len(hist),
    }
    # Feed the activity feed on big spikes.
    if sample.get("rx_bps", 0) > 5_000_000:
        state.activity_add("traffic", f"high RX rate {sample['rx_bps']/1e6:.1f} MB/s")
    if sample.get("tx_bps", 0) > 5_000_000:
        state.activity_add("traffic", f"high TX rate {sample['tx_bps']/1e6:.1f} MB/s")
    return {"sample": sample, "history": hist, "stats": stats}


# --------------------------------------------------------------------------- #
# Process Bandwidth Ranking (GlassWire Style)
# --------------------------------------------------------------------------- #
_proc_path_cache: dict[str, str] = {}


def get_process_path(proc_name: str) -> str:
    """Resolve full executable path for a process name."""
    if not proc_name or proc_name in ("System", "Idle", "Registry"):
        return ""
    if proc_name in _proc_path_cache:
        return _proc_path_cache[proc_name]
    
    code, out = run(f'powershell -NoProfile -Command "(Get-Process -Name \'{os.path.splitext(proc_name)[0]}\' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Path)"', timeout=3)
    path = out.strip() if (code == 0 and out) else ""
    if path:
        _proc_path_cache[proc_name] = path
    return path


def probe_process_bandwidth() -> dict:
    """Aggregate active sockets and network bandwidth distribution by process."""
    conns_data = probe_connections()
    conns = conns_data.get("connections", [])
    sample = state.traffic_sample()
    total_rx_bps = sample.get("rx_bps", 0)
    total_tx_bps = sample.get("tx_bps", 0)
    
    # Group connections by process name
    proc_map: dict[str, dict[str, Any]] = {}
    active_est_conns = 0

    for c in conns:
        pname = c.get("process") or (f"PID {c.get('pid')}" if c.get("pid") else "Unknown")
        state_val = c.get("state", "")
        if state_val in ("ESTABLISHED", "LISTENING", "TIME_WAIT", "CLOSE_WAIT"):
            active_est_conns += 1
            if pname not in proc_map:
                proc_map[pname] = {
                    "process": pname,
                    "pid": c.get("pid", 0),
                    "path": get_process_path(pname),
                    "established": 0,
                    "listening": 0,
                    "total_conns": 0,
                    "remote_hosts": set(),
                    "ports": set(),
                }
            if state_val == "ESTABLISHED":
                proc_map[pname]["established"] += 1
                rem = c.get("remote", "")
                if rem and not rem.startswith("0.0.0.0") and not rem.startswith("127.0.0.1"):
                    host_ip = rem.rsplit(":", 1)[0]
                    proc_map[pname]["remote_hosts"].add(host_ip)
            elif state_val == "LISTENING":
                proc_map[pname]["listening"] += 1
            proc_map[pname]["total_conns"] += 1

    proc_list = []
    total_weights = sum(p["established"] * 3 + p["total_conns"] for p in proc_map.values()) or 1
    
    for pname, data in proc_map.items():
        weight = data["established"] * 3 + data["total_conns"]
        ratio = weight / total_weights
        est_rx = int(total_rx_bps * ratio)
        est_tx = int(total_tx_bps * ratio)
        proc_list.append({
            "process": pname,
            "pid": data["pid"],
            "path": data["path"],
            "established": data["established"],
            "listening": data["listening"],
            "total_conns": data["total_conns"],
            "remote_hosts_count": len(data["remote_hosts"]),
            "rx_bps": est_rx,
            "tx_bps": est_tx,
            "total_bps": est_rx + est_tx,
            "pct": round(ratio * 100, 1)
        })

    proc_list.sort(key=lambda x: (x["rx_bps"] + x["tx_bps"], x["total_conns"]), reverse=True)
    return {
        "processes": proc_list[:25],
        "total_rx_bps": total_rx_bps,
        "total_tx_bps": total_tx_bps,
        "total_active_conns": len(conns)
    }

