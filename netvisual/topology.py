"""Build the network topology graph: this PC → gateway → neighbours.

Neighbours come from the ARP table first (instant, includes MAC + type). With
``sweep=True`` (the manual "Deep Scan"), a live ping-sweep of the primary subnet
is merged in to catch hosts that are not in the ARP cache yet.
"""
from __future__ import annotations

import ipaddress
from concurrent.futures import ThreadPoolExecutor

from . import state
from .cache import TOPO_TTL, get
from .parsers import parse_arp
from .ping import ping
from .oui import lookup_vendor
from .runner import run
from .selfinfo import self_netinfo


def sweep_neighbors(network: str) -> list[str]:
    """Ping-sweep a /prefix to discover live hosts (reports progress to the tracker)."""
    try:
        net = ipaddress.ip_network(network, strict=False)
    except ValueError:
        return []
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 256:
        hosts = hosts[:256]

    def probe(h):
        try:
            r = ping(h, 1)
            res = (h, r.get("os_guess")) if r["reachable"] else None
        except Exception:
            res = None
        finally:
            state.sweep_tick(res[0] if res else None)
        return res

    state.sweep_begin(len(hosts))
    live: list[tuple[str, str|None]] = []
    try:
        with ThreadPoolExecutor(max_workers=32) as ex:
            for res in ex.map(probe, hosts):
                if res:
                    live.append(res)
    finally:
        state.sweep_end()
    return live


def build(sweep: bool = False) -> dict:
    """Return ``{self_ip, gateway, subnet, nodes, edges}``."""
    info = self_netinfo()
    self_ip = info["ip"]
    gateway = info["gateway"]
    network = info["network"]

    try:
        primary_net = ipaddress.ip_network(network, strict=False) if network else None
    except ValueError:
        primary_net = None

    def _ok(ip: str) -> bool:
        """Keep only unicast IPs on the primary subnet."""
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if a.version != 4 or a.is_loopback or a.is_unspecified or a.is_multicast:
            return False
        if a.exploded.split(".")[-1] == "255":
            return False  # subnet broadcast
        if primary_net is not None and a not in primary_net:
            return False
        return True

    neigh: dict[str, dict] = {}

    def add(ip, mac=None, ntype=None, reachable=True, ms=None, os_guess=None):
        if not ip or ip in (self_ip, gateway) or ip.startswith("127.") or not _ok(ip):
            return
        e = neigh.setdefault(ip, {"ip": ip, "mac": None, "type": None,
                                 "reachable": False, "ms": None, "os_guess": None})
        if mac and not e["mac"]:
            e["mac"] = mac
        if ntype and not e["type"]:
            e["type"] = ntype
        e["reachable"] = e["reachable"] or bool(reachable)
        if ms is not None and e["ms"] is None:
            e["ms"] = ms
        if os_guess is not None and e["os_guess"] is None:
            e["os_guess"] = os_guess

    # 1) ARP table (primary, fast)
    for row in parse_arp(run("arp -a", 10)[1]):
        add(row["ip"], row["mac"], row["type"], reachable=True)

    # 2) optional ping sweep to catch hosts not in ARP
    if sweep and network:
        for ip, osg in sweep_neighbors(network):
            add(ip, os_guess=osg)

    nodes = [{
        "id": "self", "kind": "this-pc", "label": "This PC",
        "ip": self_ip, "mac": info.get("mac"),
        "os_guess": "Windows"
    }]
    edges = []

    if gateway:
        gw_mac = None
        for row in parse_arp(run("arp -a", 10)[1]):
            if row["ip"] == gateway:
                gw_mac = row["mac"]
                break
        nodes.append({"id": f"gw-{gateway}", "kind": "gateway", "label": "Gateway",
                      "ip": gateway, "mac": gw_mac,
                      "vendor": lookup_vendor(gw_mac) if gw_mac else ""})
        edges.append({"from": "self", "to": f"gw-{gateway}"})

    def ip_key(ip):
        try:
            return tuple(int(o) for o in ip.split("."))
        except Exception:
            return (999, 999, 999, 999)

    from .aliases import get_alias
    
    for ip in sorted(neigh, key=ip_key):
        n = neigh[ip]
        nid = f"dev-{ip}"
        
        # Simple OS Fingerprint based on TTL from ping or we could do it in ping.py
        # Actually since we don't have TTL in parse_arp, we will just add the alias field
        mac = n["mac"] or ""
        alias = get_alias(mac)
        
        nodes.append({
            "id": nid, "kind": "device", 
            "label": alias if alias else ip, "ip": ip,
            "mac": mac, "type": n["type"],
            "vendor": lookup_vendor(mac) if mac else "",
            "alias": alias,
            "os_guess": n.get("os_guess"),
            "reachable": n["reachable"], "ms": n["ms"],
        })
        edges.append({"from": "self", "to": nid})

    mac_counts = {}
    warnings = []
    for n in nodes:
        m = n.get("mac")
        if m and m != "ff-ff-ff-ff-ff-ff":
            mac_counts[m] = mac_counts.get(m, 0) + 1
    
    for m, count in mac_counts.items():
        if count >= 3:
            warnings.append(f"MAC {m} is shared by {count} devices (potential ARP Proxy or Spoofing)")

    return {
        "self_ip": self_ip,
        "gateway": gateway,
        "subnet": network,
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }


def probe(sweep: bool = False) -> dict:
    """Fast topology (ARP-based) by default; ``sweep=True`` runs a FRESH sweep.

    The sweep path bypasses the cache on purpose so a manual "Deep Scan" always
    re-probes and the progress tracker (``/api/scan-status``) updates live.
    """
    def _record(topo):
        dev_ips = [n["ip"] for n in topo["nodes"] if n.get("kind") == "device"]
        state.record_devices(dev_ips)
        return topo

    if sweep:
        return _record(build(sweep=True))

    def _build():
        return _record(build(sweep=False))
    return get("topo", _build, ttl=TOPO_TTL)
