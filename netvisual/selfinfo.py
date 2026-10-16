"""Derive this machine's own network identity WITHOUT parsing ipconfig text.

Locale-proof strategy (the core of why NetVisual works on Hebrew/English/any
Windows locale):
  1. Own outbound IP  → UDP socket trick (no locale involved at all).
  2. Gateway + subnet → the numeric ``route print`` table (default route = GW,
     the on-link route that contains our IP = subnet/prefix).
  3. MAC             → ``ipconfig /all`` (first up adapter with a MAC).

Only step 3 touches locale-sensitive text, and only to pull a MAC address — a
pure numeric string — so a failed label match is tolerable.
"""
from __future__ import annotations

import ipaddress
import socket

from .parsers import parse_ipconfig, parse_routes
from .runner import run


def own_ip() -> str:
    """This machine's primary outbound IPv4 (``0.0.0.0`` on failure)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packet is actually sent
        return s.getsockname()[0]
    except Exception:
        return "0.0.0.0"
    finally:
        s.close()


def self_netinfo() -> dict:
    """Return ``{ip, gateway, subnet, prefix, mac, network}`` for this host."""
    ip = own_ip()
    gateway = None
    subnet = None
    prefix = 24

    routes = parse_routes(run("route print", 10)[1])
    # Default route → gateway.
    for r in routes:
        if r["dest"] == "0.0.0.0" and r["gateway"] not in ("0.0.0.0", "On-link", None):
            gateway = r["gateway"]
            break
    # On-link route containing our IP → subnet + prefix (from the netmask col).
    if ip:
        try:
            self_addr = ipaddress.ip_address(ip)
        except ValueError:
            self_addr = None
        for r in routes:
            if r["gateway"] in ("On-link", None):
                try:
                    net = ipaddress.ip_network(f"{r['dest']}/{r['netmask']}",
                                               strict=False)
                    if net.version == 4 and self_addr in net:
                        prefix = net.prefixlen
                        subnet = net.netmask.compressed
                        break
                except ValueError:
                    continue

    # MAC: prefer the primary adapter (has IPv4, not media-down, has MAC).
    mac = None
    ifaces = parse_ipconfig(run("ipconfig /all", 12)[1])
    for i in ifaces:
        if i.get("ip") and not i.get("media_down") and i.get("mac"):
            mac = i["mac"]
            break
    if not mac:
        for i in ifaces:
            if i.get("mac"):
                mac = i["mac"]
                break

    # Network address (e.g. 192.168.31.0/24), not the host IP.
    net_addr = None
    if ip:
        try:
            net_addr = str(ipaddress.ip_network(f"{ip}/{prefix}",
                                                strict=False).network_address)
        except ValueError:
            pass

    return {
        "ip": ip,
        "gateway": gateway,
        "subnet": subnet,
        "prefix": prefix,
        "mac": mac,
        "network": (f"{net_addr}/{prefix}" if net_addr else f"{ip}/{prefix}"),
    }
