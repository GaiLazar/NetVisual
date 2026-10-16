"""Grouping helpers: "who is talking to me" + "what's using my bandwidth".

  - ``top_talkers``   — connections grouped per process, ranked.
  - ``remote_peers``  — connections grouped per remote host, ranked, flagged
                        LAN/external, with this machine's own IP filtered out.

Both are pure functions over the connection list (testable without a server).
"""
from __future__ import annotations

import ipaddress

from . import probes
from .selfinfo import self_netinfo


# --------------------------------------------------------------------------- #
# Top talkers (by process)
# --------------------------------------------------------------------------- #
def top_talkers(limit: int = 8) -> list[dict]:
    """Group connections by process, ranked by established count then total."""
    data = probes.probe_connections()["connections"]
    by: dict[str, dict] = {}
    for c in data:
        p = c.get("process") or c.get("pid") or "unknown"
        e = by.setdefault(p, {"process": p, "connections": 0, "established": 0,
                              "remote_ips": 0})
        e["connections"] += 1
        if c.get("state") == "ESTABLISHED":
            e["established"] += 1
        if c.get("remote") and c["remote"] not in ("0.0.0.0:0", "[::]:0", "-"):
            e["remote_ips"] += 1
    ranked = sorted(by.values(), key=lambda x: (x["established"], x["connections"]),
                    reverse=True)
    return ranked[:limit]


# --------------------------------------------------------------------------- #
# Remote peers (by remote host)
# --------------------------------------------------------------------------- #
def _remote_host(remote: str) -> str | None:
    """Host part (no port) of a netstat remote address, or None for non-peers."""
    r = (remote or "").strip()
    if (not r or r in ("-", "0.0.0.0:0", "[::]:0", "*:*")
            or r.rsplit(":", 1)[0] in ("", ":", "::", "::1", "127.0.0.1", "0.0.0.0")):
        return None
    host = r.rsplit(":", 1)[0]
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if not host or host in ("0.0.0.0", "::", "127.0.0.1", "::1"):
        return None
    return host


def group_remote_peers(conns: list[dict]) -> list[dict]:
    """Group connections by remote host (pure function)."""
    by: dict[str, dict] = {}
    for c in conns:
        host = _remote_host(c.get("remote", ""))
        if not host:
            continue
        port = c.get("remote", "").rsplit(":", 1)[-1]
        e = by.setdefault(host, {"ip": host, "connections": 0, "established": 0,
                                 "ports": set(), "processes": set(), "protos": set()})
        e["connections"] += 1
        if c.get("state") == "ESTABLISHED":
            e["established"] += 1
        if port.isdigit():
            e["ports"].add(int(port))
        if c.get("process"):
            e["processes"].add(c["process"])
        if c.get("proto"):
            e["protos"].add(c["proto"])
    out = []
    for e in by.values():
        out.append({
            "ip": e["ip"],
            "connections": e["connections"],
            "established": e["established"],
            "ports": sorted(e["ports"]),
            "processes": sorted(e["processes"]),
            "proto": "/".join(sorted(e["protos"])),
        })
    out.sort(key=lambda x: (-x["established"], -x["connections"], x["ip"]))
    return out


def remote_peers(limit: int = 10) -> list[dict]:
    """Top remote peers ranked by established connections, flagged LAN/external.

    Filters out this machine's own IP (self-connections via the LAN IP are noise).
    """
    own_ip = None
    try:
        own_ip = self_netinfo().get("ip")
    except Exception:
        pass
    try:
        net = ipaddress.ip_network(
            (self_netinfo().get("network") if own_ip else None) or "0.0.0.0/0",
            strict=False)
    except ValueError:
        net = ipaddress.ip_network("0.0.0.0/0")
    peers = [p for p in group_remote_peers(probes.probe_connections()["connections"])
             if own_ip is None or p["ip"] != own_ip]
    for p in peers:
        try:
            p["local"] = ipaddress.ip_address(p["ip"]) in net
        except ValueError:
            p["local"] = False
    return peers[:limit]
