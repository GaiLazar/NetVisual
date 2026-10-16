"""MAC → vendor lookup (OUI).

A small built-in table covers the common home/office device vendors (VMs,
Raspberry Pi, Apple, etc.). Users can extend it at runtime by dropping a
``data/oui.json`` file shaped as ``{"AA:BB:CC": "Vendor", ...}`` (keyed on the
first three octets, colon-separated).
"""
from __future__ import annotations

import json

from .paths import DATA_DIR

# First three hex octets (colon-separated) → vendor.
_BUILTIN: dict[str, str] = {
    "00:15:5D": "Microsoft Virtual",
    "3C:5A:B4": "Microsoft Virtual",
    "52:54:00": "QEMU Virtual",
    "00:0C:29": "VMware",
    "08:00:27": "VirtualBox",
    "9C:9D:7E": "Apple",
    "10:D5:61": "Raspberry Pi",
    "32:D1:27": "Raspberry Pi / Silex",
    "DC:A6:32": "Apple",
    "F0:18:98": "VMware",
    "00:16:3E": "Xensource",
    "00:50:56": "VMware",
    "00:03:FF": "3Com",
    "00:17:F2": "VMware",
    "00:50:0F": "VMware",
    "00:0C:76": "VMware",
    "00:1C:14": "VMware",
    "00:1C:42": "VMware",
    "00:1E:C2": "VMware",
    "00:0C:41": "VMware",
    "00:15:59": "Microsoft Hyper-V",
}


def _load_extra() -> dict[str, str]:
    """Load user-provided OUI overrides from ``data/oui.json`` (if present)."""
    p = DATA_DIR / "oui.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # missing / malformed / not-yet-created
        return {}


import threading
import urllib.request
import time

_EXTRA: dict[str, str] = _load_extra()
_FETCHING: set[str] = set()
_LOCK = threading.Lock()

def _fetch_online(mac_prefix: str) -> None:
    with _LOCK:
        if mac_prefix in _FETCHING:
            return
        _FETCHING.add(mac_prefix)

    def do_fetch():
        time.sleep(0.5)
        try:
            req = urllib.request.Request(f"https://api.macvendors.com/{mac_prefix}", headers={'User-Agent': 'NetVisual'})
            with urllib.request.urlopen(req, timeout=3) as res:
                vendor = res.read().decode('utf-8').strip()
                if vendor and "error" not in vendor.lower():
                    with _LOCK:
                        _EXTRA[mac_prefix] = vendor
                        p = DATA_DIR / "oui.json"
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(json.dumps(_EXTRA, indent=2), encoding="utf-8")
        except Exception:
            pass
        finally:
            with _LOCK:
                _FETCHING.discard(mac_prefix)

    threading.Thread(target=do_fetch, daemon=True).start()

def lookup_vendor(mac: str) -> str:
    """Return the vendor name for ``mac`` (any separator), or ``''`` if unknown."""
    if not mac:
        return ""
    # Normalise to colon-separated uppercase, take the first three octets.
    norm = mac.upper().replace("-", ":").replace(".", ":")
    key = ":".join(norm.split(":")[:3])
    
    val = _BUILTIN.get(key) or _EXTRA.get(key)
    if val:
        return val
        
    _fetch_online(key)
    return ""
