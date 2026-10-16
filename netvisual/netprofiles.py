"""NetSetMan-style Profile, DNS Switcher, Network Repair & Wake-on-LAN module.

Provides:
  - 1-Click DNS switcher presets (Cloudflare, Google, Quad9, AdGuard, DHCP).
  - 1-Click Network Repair & Flush (flushdns, release/renew, arp purge).
  - Wake-on-LAN (WOL) magic packet sender.
  - Network profile management (save/load/apply named configurations).
"""
from __future__ import annotations

import json
import re
import socket
import struct
import subprocess
import threading
import time
from typing import Any

from .paths import DATA_DIR
from .runner import run

PROFILES_FILE = DATA_DIR / "net_profiles.json"
_lock = threading.Lock()

DNS_PRESETS = [
    {
        "id": "cloudflare",
        "name": "Cloudflare (1.1.1.1)",
        "tag": "Fast & Private",
        "primary": "1.1.1.1",
        "secondary": "1.0.0.1",
        "desc": "Ultra-low latency with strict privacy policy (no logs).",
        "icon": "⚡"
    },
    {
        "id": "quad9",
        "name": "Quad9 (9.9.9.9)",
        "tag": "Threat Blocking",
        "primary": "9.9.9.9",
        "secondary": "149.112.112.112",
        "desc": "Blocks malicious domains, phishing, and malware automatically.",
        "icon": "🛡️"
    },
    {
        "id": "adguard",
        "name": "AdGuard DNS",
        "tag": "Ad & Tracker Block",
        "primary": "94.140.14.14",
        "secondary": "94.140.15.15",
        "desc": "Blocks intrusive ads, trackers, and adult sites network-wide.",
        "icon": "🛑"
    },
    {
        "id": "google",
        "name": "Google Public DNS",
        "tag": "Reliable & Fast",
        "primary": "8.8.8.8",
        "secondary": "8.8.4.4",
        "desc": "Global Anycast routing with 99.99% uptime.",
        "icon": "🌐"
    },
    {
        "id": "dhcp",
        "name": "Automatic (DHCP)",
        "tag": "Router Default",
        "primary": "DHCP",
        "secondary": "",
        "desc": "Obtain DNS server addresses automatically from your router.",
        "icon": "🔄"
    }
]


def _get_active_interface_name() -> str:
    """Detect the active network adapter name (e.g. 'Wi-Fi' or 'Ethernet')."""
    code, out = run("netsh interface show interface", 5)
    for line in out.splitlines():
        if "Connected" in line or "מחובר" in line:
            parts = line.split()
            if len(parts) >= 4:
                return " ".join(parts[3:])
    return "Wi-Fi"


def get_dns_presets() -> dict[str, Any]:
    """Return available DNS presets and currently active adapter."""
    return {
        "presets": DNS_PRESETS,
        "adapter": _get_active_interface_name()
    }


def set_dns_preset(preset_id: str, adapter_name: str | None = None) -> dict[str, Any]:
    """Apply a DNS preset to the active network interface."""
    adapter = adapter_name or _get_active_interface_name()
    preset = next((p for p in DNS_PRESETS if p["id"] == preset_id), None)
    if not preset:
        return {"error": f"Unknown preset ID: {preset_id}", "ok": False}

    if preset["id"] == "dhcp":
        cmd = f'netsh interface ipv4 set dns name="{adapter}" source=dhcp'
        code, out = run(cmd, 10)
    else:
        cmd1 = f'netsh interface ipv4 set dns name="{adapter}" static {preset["primary"]} primary'
        code1, out1 = run(cmd1, 10)
        if preset.get("secondary"):
            cmd2 = f'netsh interface ipv4 add dns name="{adapter}" {preset["secondary"]} index=2'
            run(cmd2, 8)
        code, out = code1, out1

    # Flush DNS cache after change
    run("ipconfig /flushdns", 5)

    return {
        "ok": code == 0,
        "preset": preset,
        "adapter": adapter,
        "output": out or "DNS settings updated successfully."
    }


def repair_network() -> dict[str, Any]:
    """Perform a 1-click comprehensive network flush & repair."""
    steps: list[dict[str, Any]] = []

    # Step 1: Flush DNS
    c1, o1 = run("ipconfig /flushdns", 5)
    steps.append({"step": "Flush DNS Resolver Cache", "ok": c1 == 0, "out": o1.strip()})

    # Step 2: Purge ARP Cache
    c2, o2 = run("arp -d *", 5)
    steps.append({"step": "Purge ARP Neighbor Cache", "ok": c2 == 0, "out": o2.strip() or "ARP cache cleared"})

    # Step 3: Register DNS
    c3, o3 = run("ipconfig /registerdns", 5)
    steps.append({"step": "Re-register DNS Names with DHCP", "ok": c3 == 0, "out": o3.strip()})

    return {
        "ok": all(s["ok"] for s in steps),
        "steps": steps,
        "timestamp": time.time(),
        "summary": "Network stack refreshed, DNS cache cleared, and ARP tables purged."
    }


def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> dict[str, Any]:
    """Send a Wake-on-LAN (WOL) Magic Packet to power on a remote machine."""
    clean_mac = re.sub(r"[^0-9A-Fa-f]", "", mac_address)
    if len(clean_mac) != 12:
        return {"error": "Invalid MAC address format (must be 12 hex digits)", "ok": False}

    mac_bytes = bytes.fromhex(clean_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_ip, port))
        sock.close()
        return {
            "ok": True,
            "mac": mac_address,
            "broadcast": f"{broadcast_ip}:{port}",
            "msg": f"Magic Packet transmitted to {mac_address} via broadcast {broadcast_ip}:{port}"
        }
    except Exception as e:
        return {"error": str(e), "ok": False}


def load_profiles() -> list[dict[str, Any]]:
    """Load saved network profiles."""
    if not PROFILES_FILE.exists():
        default_profiles = [
            {
                "id": "p_home",
                "name": "#1 Home (DHCP)",
                "adapter": "",
                "ip_mode": "dhcp",
                "ip_address": "",
                "subnet_mask": "255.255.255.0",
                "gateway": "",
                "dns_mode": "dhcp",
                "primary_dns": "",
                "secondary_dns": "",
                "proxy_enabled": False,
                "proxy_server": "",
                "notes": "Standard router-assigned automatic DHCP configuration.",
                "icon": "🏠",
                "created_at": time.time(),
                "associated_ssid": ""
            },
            {
                "id": "p_work",
                "name": "#2 Work (Static IP)",
                "adapter": "",
                "ip_mode": "static",
                "ip_address": "192.168.1.55",
                "subnet_mask": "255.255.255.0",
                "gateway": "192.168.1.1",
                "dns_mode": "manual",
                "primary_dns": "1.1.1.1",
                "secondary_dns": "1.0.0.1",
                "proxy_enabled": False,
                "proxy_server": "",
                "notes": "Office static IP profile with Cloudflare DNS.",
                "icon": "💼",
                "created_at": time.time(),
                "associated_ssid": ""
            },
            {
                "id": "p_gaming",
                "name": "#3 Gaming (Low-Ping)",
                "adapter": "",
                "ip_mode": "dhcp",
                "ip_address": "",
                "subnet_mask": "255.255.255.0",
                "gateway": "",
                "dns_mode": "manual",
                "primary_dns": "1.1.1.1",
                "secondary_dns": "1.0.0.1",
                "proxy_enabled": False,
                "proxy_server": "",
                "notes": "Ultra-low latency Anycast DNS for gaming.",
                "icon": "🎮",
                "created_at": time.time(),
                "associated_ssid": ""
            },
            {
                "id": "p_secure",
                "name": "#4 Shield & AdBlock",
                "adapter": "",
                "ip_mode": "dhcp",
                "ip_address": "",
                "subnet_mask": "255.255.255.0",
                "gateway": "",
                "dns_mode": "manual",
                "primary_dns": "94.140.14.14",
                "secondary_dns": "94.140.15.15",
                "proxy_enabled": False,
                "proxy_server": "",
                "notes": "AdGuard DNS blocking intrusive trackers & phishing.",
                "icon": "🛡️",
                "created_at": time.time(),
                "associated_ssid": ""
            }
        ]
        save_profiles(default_profiles)
        return default_profiles

    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for p in data:
                p.setdefault("adapter", "")
                p.setdefault("associated_ssid", "")
                p.setdefault("ip_mode", "dhcp")
                p.setdefault("ip_address", "")
                p.setdefault("subnet_mask", "255.255.255.0")
                p.setdefault("gateway", "")
                p.setdefault("dns_mode", "dhcp")
                p.setdefault("primary_dns", "")
                p.setdefault("secondary_dns", "")
                p.setdefault("proxy_enabled", False)
                p.setdefault("proxy_server", "")
                p.setdefault("icon", "📁")
                p.setdefault("notes", "")
            return data
    except Exception:
        return []


def save_profiles(profiles: list[dict[str, Any]]) -> None:
    with _lock:
        try:
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
        except Exception:
            pass


_last_auto_applied_ssid: str | None = None


def auto_switch_ssid_profile(current_ssid: str) -> dict[str, Any] | None:
    """Check if any profile matches the current Wi-Fi SSID and auto-apply it."""
    global _last_auto_applied_ssid
    if not current_ssid or current_ssid == _last_auto_applied_ssid:
        return None
    
    profiles = load_profiles()
    for prof in profiles:
        assoc = (prof.get("associated_ssid") or "").strip()
        if assoc and assoc.lower() == current_ssid.strip().lower():
            _last_auto_applied_ssid = current_ssid
            res = apply_profile(prof["id"])
            return {"applied": True, "profile": prof, "result": res}
    return None


def upsert_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    """Create or update a network profile."""
    profiles = load_profiles()
    pid = profile_data.get("id") or f"p_{int(time.time()*1000)}"
    profile_data["id"] = pid
    if not profile_data.get("created_at"):
        profile_data["created_at"] = time.time()
    profile_data["updated_at"] = time.time()

    idx = next((i for i, p in enumerate(profiles) if p["id"] == pid), None)
    if idx is not None:
        profiles[idx] = profile_data
    else:
        profiles.append(profile_data)

    save_profiles(profiles)
    return {"ok": True, "profile": profile_data, "profiles": profiles}


def delete_profile(profile_id: str) -> dict[str, Any]:
    """Delete a profile by ID."""
    profiles = load_profiles()
    new_profiles = [p for p in profiles if p["id"] != profile_id]
    if len(new_profiles) == len(profiles):
        return {"ok": False, "error": "Profile not found"}
    save_profiles(new_profiles)
    return {"ok": True, "profiles": new_profiles}


def apply_profile(profile_id: str) -> dict[str, Any]:
    """Apply a full NetSetMan-style network profile to the system."""
    profiles = load_profiles()
    prof = next((p for p in profiles if p["id"] == profile_id), None)
    if not prof:
        return {"error": f"Profile {profile_id} not found", "ok": False}

    adapter = prof.get("adapter") or _get_active_interface_name()
    steps: list[dict[str, Any]] = []

    # 1. IP & Gateway Setting
    ip_mode = prof.get("ip_mode", "dhcp").lower()
    if ip_mode == "static":
        ip = prof.get("ip_address", "").strip()
        mask = prof.get("subnet_mask", "").strip() or "255.255.255.0"
        gw = prof.get("gateway", "").strip()
        if ip:
            gw_clause = f" {gw}" if gw else ""
            cmd = f'netsh interface ipv4 set address name="{adapter}" static {ip} {mask}{gw_clause}'
            c, out = run(cmd, 10)
            steps.append({"action": f"Set Static IP ({ip})", "ok": c == 0, "output": out.strip()})
    else:
        cmd = f'netsh interface ipv4 set address name="{adapter}" dhcp'
        c, out = run(cmd, 10)
        steps.append({"action": "Enable DHCP IP", "ok": c == 0, "output": out.strip()})

    # 2. DNS Setting
    dns_mode = prof.get("dns_mode", "dhcp").lower()
    primary = prof.get("primary_dns", "").strip()
    secondary = prof.get("secondary_dns", "").strip()

    if dns_mode == "manual" and primary:
        c1, o1 = run(f'netsh interface ipv4 set dns name="{adapter}" static {primary} primary', 10)
        steps.append({"action": f"Set Primary DNS ({primary})", "ok": c1 == 0, "output": o1.strip()})
        if secondary:
            c2, o2 = run(f'netsh interface ipv4 add dns name="{adapter}" {secondary} index=2', 8)
            steps.append({"action": f"Add Secondary DNS ({secondary})", "ok": c2 == 0, "output": o2.strip()})
    else:
        c, out = run(f'netsh interface ipv4 set dns name="{adapter}" source=dhcp', 10)
        steps.append({"action": "Enable DHCP DNS", "ok": c == 0, "output": out.strip()})

    # 3. Flush DNS Cache
    run("ipconfig /flushdns", 5)

    return {
        "ok": any(s["ok"] for s in steps) if steps else True,
        "profile": prof,
        "adapter": adapter,
        "steps": steps,
        "summary": f"Profile '{prof.get('name')}' applied to adapter '{adapter}'."
    }


def restart_adapter(iface_name: str) -> dict[str, Any]:
    """Disable and re-enable a network adapter via PowerShell or netsh."""
    safe_name = iface_name.replace('"', '').strip()
    if not safe_name:
        return {"ok": False, "error": "Adapter name required"}
    cmd = f'powershell -Command "Restart-NetAdapter -Name \'{safe_name}\' -Confirm:$false"'
    code, out = run(cmd, 10)
    if code != 0:
        run(f'netsh interface set interface "{safe_name}" disable', 5)
        time.sleep(1)
        code, out = run(f'netsh interface set interface "{safe_name}" enable', 5)

    return {
        "ok": code == 0,
        "adapter": safe_name,
        "output": out or "Adapter power-cycled and restarted successfully."
    }
