"""Parse ``tasklist /fo csv /nh`` into ``{pid: process_name}``.

Used to enrich ``netstat -ano`` rows (which only carry a PID) with a human
readable process name.
"""
from __future__ import annotations

import csv
import io


def parse_tasklist_csv(text: str) -> dict[int, str]:
    """Return ``{pid: process_name}`` for every row in a CSV tasklist dump.

    Rows are shaped like ``"System","4","Services","0","1 K"`` — the first two
    columns are ``ImageName`` and ``PID``.
    """
    out: dict[int, str] = {}
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) >= 2 and row[0].strip() and row[1].strip().isdigit():
            name = row[0].strip().strip('"')
            pid = int(row[1].strip().strip('"'))
            out[pid] = name
    return out
