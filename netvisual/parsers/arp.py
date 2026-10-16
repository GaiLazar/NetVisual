"""Parse ``arp -a`` into neighbour dicts.

Matches the canonical 3-column row: ``<ip>  <mac>  <static|dynamic>``.
The MAC pattern is numeric so this works regardless of the shell's locale.
"""
from __future__ import annotations

import re

_ROW_RE = re.compile(
    r"\s*([\d.]+)\s+"
    r"([0-9A-Fa-f]{1,2}(?:[-:][0-9A-Fa-f]{1,2}){5})\s+"
    r"(static|dynamic)")


def parse_arp(text: str) -> list[dict]:
    """Return ``[{"ip","mac","type"}, ...]`` for every ARP table row."""
    rows: list[dict] = []
    for line in text.splitlines():
        m = _ROW_RE.match(line)
        if m:
            rows.append({"ip": m.group(1), "mac": m.group(2).upper(),
                         "type": m.group(3)})
    return rows
