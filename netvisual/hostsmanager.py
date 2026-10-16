"""Windows Hosts File & Anti-Telemetry/AdBlock Manager.

Provides read, backup, write, and 1-click curated anti-telemetry & ad blocking
for C:\\Windows\\System32\\drivers\\etc\\hosts.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HOSTS_PATH = Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "drivers" / "etc" / "hosts"

# Curated high-impact telemetry & tracking domains to block
BLOCKLIST_MARKER_START = "# --- NetVisual Anti-Telemetry & Privacy Blocklist (START) ---"
BLOCKLIST_MARKER_END = "# --- NetVisual Anti-Telemetry & Privacy Blocklist (END) ---"

CURATED_BLOCKED_DOMAINS = [
    # Microsoft Windows Telemetry & Diagnostics
    "telemetry.microsoft.com",
    "v10.events.data.microsoft.com",
    "v20.events.data.microsoft.com",
    "settings-win.data.microsoft.com",
    "watson.telemetry.microsoft.com",
    "diagnostics.support.microsoft.com",
    "feedback.microsoft.com",
    "activity.windows.com",
    "cortana.ai",
    # Ad Networks & Trackers
    "adservice.google.com",
    "pagead2.googlesyndication.com",
    "adnxs.com",
    "doubleclick.net",
    "scorecardresearch.com",
    "tracking.taboola.com",
    "analytics.tiktok.com",
]


def read_hosts() -> dict[str, Any]:
    """Read the current hosts file content and detect if blocklist is active."""
    if not HOSTS_PATH.exists():
        return {"content": "", "blocklist_active": False, "lines_count": 0, "path": str(HOSTS_PATH), "writable": False}
    try:
        raw = HOSTS_PATH.read_text(encoding="utf-8", errors="ignore")
        active = BLOCKLIST_MARKER_START in raw
        lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]
        writable = os.access(HOSTS_PATH, os.W_OK)
        return {
            "content": raw,
            "blocklist_active": active,
            "blocked_count": len(CURATED_BLOCKED_DOMAINS) if active else 0,
            "active_rules_count": len(lines),
            "path": str(HOSTS_PATH),
            "writable": writable,
        }
    except Exception as e:
        return {"error": str(e), "content": "", "blocklist_active": False, "path": str(HOSTS_PATH)}


def save_hosts(content: str) -> dict[str, Any]:
    """Save custom content to the hosts file (with automatic backup)."""
    try:
        if HOSTS_PATH.exists():
            backup_path = HOSTS_PATH.with_suffix(".bak")
            backup_path.write_bytes(HOSTS_PATH.read_bytes())
        HOSTS_PATH.write_text(content, encoding="utf-8")
        return {"ok": True, "msg": "Hosts file saved successfully with backup."}
    except PermissionError:
        return {
            "ok": False,
            "error": "Access Denied: Run NetVisual as Administrator to modify C:\\Windows\\System32\\drivers\\etc\\hosts",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def toggle_anti_telemetry(enable: bool) -> dict[str, Any]:
    """1-click enable/disable curated anti-telemetry & adblock rules in hosts."""
    data = read_hosts()
    content = data.get("content", "")
    
    # Remove existing blocklist chunk if present
    if BLOCKLIST_MARKER_START in content and BLOCKLIST_MARKER_END in content:
        before = content.split(BLOCKLIST_MARKER_START)[0]
        after = content.split(BLOCKLIST_MARKER_END)[1]
        content = (before.rstrip() + "\n\n" + after.lstrip()).strip()

    if enable:
        block_lines = [
            f"0.0.0.0 {dom}\n0.0.0.0 www.{dom}" if not dom.startswith("www.") else f"0.0.0.0 {dom}"
            for dom in CURATED_BLOCKED_DOMAINS
        ]
        chunk = (
            f"\n\n{BLOCKLIST_MARKER_START}\n"
            + "\n".join(block_lines)
            + f"\n{BLOCKLIST_MARKER_END}\n"
        )
        content = content + chunk

    return save_hosts(content)
