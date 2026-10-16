"""Parsers for the ``netstat`` family of commands.

Two functions:
  - ``parse_netstat``    → ``netstat -ano`` → connection rows
  - ``parse_netstat_e``  → ``netstat -e``  → interface byte/packet counters
"""
from __future__ import annotations


def parse_netstat(text: str) -> list[dict]:
    """Parse ``netstat -ano`` into connection dicts.

    Each row: ``{"proto","local","remote","state","pid"}``.
    UDP rows have ``state == "-"`` and no PID column in some Windows builds;
    we default pid to ``"0"`` in that case so downstream ``int(pid)`` works.
    """
    conns: list[dict] = []
    for line in text.splitlines():
        if not (line.startswith("  TCP") or line.startswith("  UDP")):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        proto, local, remote = parts[0], parts[1], parts[2]
        state = parts[3] if len(parts) >= 4 else "-"
        pid = parts[4] if len(parts) >= 5 else "0"
        conns.append({"proto": proto, "local": local, "remote": remote,
                      "state": state, "pid": pid})
    return conns


def parse_netstat_e(text: str) -> dict:
    """Parse ``netstat -e`` into interface counters.

    Returns ``{"recv_bytes","sent_bytes","recv_pkts","sent_pkts"}``.
    Locale-tolerant: matches the first two numbers on the "Bytes ..." line and
    the first two numbers on the "Unicast packets ..." line.
    """
    stats = {"recv_bytes": 0, "sent_bytes": 0, "recv_pkts": 0, "sent_pkts": 0}
    lines = text.splitlines()
    for ln in lines:
        s = ln.strip().lower()
        if s.startswith("bytes"):
            nums = [x for x in ln.split() if x.isdigit()]
            if len(nums) >= 2:
                stats["recv_bytes"] = int(nums[0])
                stats["sent_bytes"] = int(nums[1])
            break
    for ln in lines:
        if ln.strip().lower().startswith("unicast packets"):
            nums = [x for x in ln.split() if x.isdigit()]
            if len(nums) >= 2:
                stats["recv_pkts"] = int(nums[0])
                stats["sent_pkts"] = int(nums[1])
            break
    return stats
