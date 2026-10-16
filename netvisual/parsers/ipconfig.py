"""Parse ``ipconfig /all`` into interface dicts.

Locale-agnostic: does NOT rely on Hebrew/English label words for the values.
It anchors each interface block on the ``... adapter <name>:`` line (the
``adapter`` keyword is stable in the English shell we run via ``cmd /c``), then
collects MACs, subnets, IPs, gateways and DNS entries by position.
"""
from __future__ import annotations

import re

_ip_re = re.compile(r"IPv4 Address[^\d]*([\d.]+)")
_gw_re = re.compile(r"Default Gateway[^\d]*([\d.]+)")
_mac_re = re.compile(
    r"Physical Address[^\d]*([0-9A-Fa-f]{1,2}(?:[-:][0-9A-Fa-f]{1,2}){5})")
_dns_re = re.compile(r"DNS Servers?[^\d]*([\d.]+)")
_dhcp_re = re.compile(r"DHCP Server[^\d]*([\d.]+)")
_subnet_re = re.compile(r"Subnet Mask[^\d]*([\d.]+)")
_adapter_re = re.compile(r"^\s*[\w ]+ adapter (.+?):\s*$")


def parse_ipconfig(text: str) -> list[dict]:
    """Return a list of interface dicts, one per ``... adapter`` block.

    Each dict has: name, ip, gw, mac, dns (list), dhcp, subnet, media_down.
    Interfaces with neither an IP nor a MAC are dropped (loopback/disconnected);
    if all are dropped we return the full list so the caller has *something*.
    """
    ifaces: list[dict] = []
    cur: dict | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _adapter_re.match(line)
        if m:
            cur = {"name": m.group(1), "ip": None, "gw": None, "mac": None,
                   "dns": [], "dhcp": None, "subnet": None}
            ifaces.append(cur)
            continue
        if cur is None:
            continue
        if "Media disconnected" in line:
            cur["media_down"] = True
        for field, rx in (("ip", _ip_re), ("gw", _gw_re), ("mac", _mac_re),
                          ("dhcp", _dhcp_re), ("subnet", _subnet_re)):
            mm = rx.search(line)
            if mm:
                cur[field] = mm.group(1)
        mm = _dns_re.search(line)
        if mm:
            cur["dns"].append(mm.group(1))
    up = [i for i in ifaces if i["ip"] or i["mac"]]
    return up or ifaces
