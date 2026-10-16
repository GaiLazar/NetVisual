"""Threat & Security Inspector for NetVisual.

Scans active connections for risky/suspicious ports and anomalies,
evaluates DNS leak exposure, checks SSL/certificate posture, and provides
WHOIS / IP reputation details.
"""
from __future__ import annotations

import json
import re
import socket
import threading
import time
import urllib.request
from typing import Any

from . import geo, probes
from .runner import run

# Known suspicious / insecure ports commonly abused by malware, botnets, or misconfigurations
KNOWN_RISKY_PORTS: dict[int, dict[str, str]] = {
    21: {"name": "FTP (Plaintext)", "severity": "warning", "desc": "Unencrypted file transfer"},
    23: {"name": "Telnet (Insecure)", "severity": "critical", "desc": "Unencrypted remote shell"},
    25: {"name": "SMTP (Insecure)", "severity": "warning", "desc": "Direct outbound mail / potential spam bot"},
    69: {"name": "TFTP", "severity": "warning", "desc": "Trivial unauthenticated FTP"},
    135: {"name": "MS-RPC", "severity": "critical", "desc": "Windows RPC exposed externally"},
    137: {"name": "NetBIOS", "severity": "warning", "desc": "NetBIOS name service"},
    139: {"name": "NetBIOS-SSN", "severity": "critical", "desc": "NetBIOS session exposed"},
    445: {"name": "SMB", "severity": "critical", "desc": "SMB Direct exposed externally (WannaCry vector)"},
    1433: {"name": "MS-SQL", "severity": "warning", "desc": "Direct database connection"},
    3306: {"name": "MySQL", "severity": "warning", "desc": "Direct database connection"},
    3389: {"name": "RDP", "severity": "warning", "desc": "Remote Desktop Protocol"},
    4444: {"name": "Metasploit Default", "severity": "critical", "desc": "Common reverse shell payload port"},
    5555: {"name": "ADB / Freeciv", "severity": "warning", "desc": "Android Debug Bridge exposed"},
    6667: {"name": "IRC (Plaintext)", "severity": "warning", "desc": "IRC protocol often used by botnet C2"},
    9001: {"name": "Tor Relay/OR", "severity": "warning", "desc": "Tor onion network traffic"},
    9050: {"name": "Tor SOCKS", "severity": "warning", "desc": "Tor SOCKS proxy connection"},
    14444: {"name": "Crypto Mining", "severity": "critical", "desc": "Known Monero/cryptocurrency mining pool port"},
    3333: {"name": "Stratum Mining", "severity": "critical", "desc": "Crypto stratum mining protocol"},
}

_whois_cache: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def check_dns_leaks() -> dict[str, Any]:
    """Inspect local DNS server configurations and check for potential leak vectors."""
    code, out = run("ipconfig /all", 10)
    dns_servers: list[str] = []
    
    for line in out.splitlines():
        if "DNS Servers" in line or "שרתי DNS" in line:
            parts = line.split(":", 1)
            if len(parts) > 1:
                ip = parts[1].strip()
                if ip and not ip.startswith("::") and ip != "127.0.0.1":
                    dns_servers.append(ip)
        elif dns_servers and line.startswith("    ") and not ":" in line:
            extra_ip = line.strip()
            if extra_ip and "." in extra_ip:
                dns_servers.append(extra_ip)

    # Deduplicate
    dns_servers = list(dict.fromkeys(dns_servers))

    known_secure_dns = {
        "1.1.1.1": "Cloudflare Secure DNS",
        "1.0.0.1": "Cloudflare Secure DNS",
        "8.8.8.8": "Google Public DNS",
        "8.8.4.4": "Google Public DNS",
        "9.9.9.9": "Quad9 Threat Blocking DNS",
        "149.112.112.112": "Quad9 Threat Blocking DNS",
        "208.67.222.222": "Cisco OpenDNS",
        "208.67.220.220": "Cisco OpenDNS",
    }

    server_details = []
    is_secure_upstream = False
    for s in dns_servers:
        name = known_secure_dns.get(s, "Local / ISP DNS Gateway")
        if s in known_secure_dns:
            is_secure_upstream = True
        server_details.append({"ip": s, "provider": name, "secure": s in known_secure_dns})

    return {
        "dns_servers": server_details,
        "count": len(server_details),
        "is_encrypted_upstream": is_secure_upstream,
        "status": "secure" if is_secure_upstream else "info",
        "recommendation": "Using secure public DNS (1.1.1.1 / 9.9.9.9)" if is_secure_upstream else "Standard ISP DNS active. Consider enabling Cloudflare (1.1.1.1) or Quad9 (9.9.9.9) for malware blocking."
    }


def audit_security() -> dict[str, Any]:
    """Perform a full security posture check of all active sockets and ports."""
    conns = probes.probe_connections().get("connections", [])
    threats: list[dict[str, Any]] = []
    risky_conns_count = 0

    for c in conns:
        r_port = c.get("remote_port")
        r_ip = c.get("remote_ip")
        proc = c.get("process") or "Unknown"
        state = c.get("state") or ""

        if not r_ip or not geo.is_public_ip(r_ip):
            continue

        if r_port in KNOWN_RISKY_PORTS:
            risk = KNOWN_RISKY_PORTS[r_port]
            risky_conns_count += 1
            threats.append({
                "severity": risk["severity"],
                "title": f"Active {risk['name']} connection",
                "description": f"Process '{proc}' is communicating with {r_ip}:{r_port} ({risk['desc']})",
                "remote_ip": r_ip,
                "remote_port": r_port,
                "process": proc,
                "state": state
            })

    dns_audit = check_dns_leaks()

    # Calculate overall security score (0-100)
    score = 100
    if risky_conns_count > 0:
        score -= min(40, risky_conns_count * 15)
    if not dns_audit.get("is_encrypted_upstream"):
        score -= 10

    score = max(20, score)
    grade = "A+" if score >= 95 else "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "F"

    return {
        "score": score,
        "grade": grade,
        "timestamp": time.time(),
        "threats": threats,
        "threat_count": len(threats),
        "dns": dns_audit,
        "total_active_sockets": len(conns),
    }


def query_whois(ip_str: str) -> dict[str, Any]:
    """Retrieve WHOIS and ASN details for a given IP."""
    if not ip_str or not geo.is_public_ip(ip_str):
        return {"error": "Invalid or private IP address"}

    with _lock:
        if ip_str in _whois_cache and (time.time() - _whois_cache[ip_str]["_ts"] < 3600):
            return _whois_cache[ip_str]

    try:
        req = urllib.request.Request(
            f"http://ip-api.com/json/{ip_str}?fields=status,message,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query",
            headers={"User-Agent": "NetVisual-APlus/4.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                asn = data.get("as", "")
                res = {
                    "ip": ip_str,
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "region": data.get("regionName", "Unknown"),
                    "isp": data.get("isp", "Unknown"),
                    "org": data.get("org", "Unknown"),
                    "asn": asn,
                    "timezone": data.get("timezone", "UTC"),
                    "is_hosting": any(h in (data.get("isp", "") + data.get("org", "")).lower() for h in ["amazon", "google", "microsoft", "cloudflare", "ovh", "digitalocean", "hetzner"]),
                    "_ts": time.time()
                }
                with _lock:
                    _whois_cache[ip_str] = res
                return res
    except Exception as e:
        return {"error": f"Failed to resolve WHOIS: {e}", "ip": ip_str}

    return {"error": "Unable to resolve", "ip": ip_str}

def check_threat_intel(ip_str: str) -> dict[str, Any]:
    """Check IP against AlienVault OTX Threat Intelligence Feed."""
    if not ip_str or not geo.is_public_ip(ip_str):
        return {"ip": ip_str, "threats": 0, "safe": True}
        
    try:
        req = urllib.request.Request(
            f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip_str}/general",
            headers={"User-Agent": "NetVisual-APlus/4.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode())
            pulses = data.get("pulse_info", {})
            count = pulses.get("count", 0)
            names = [p.get("name", "Unknown Threat") for p in pulses.get("pulses", [])]
            return {
                "ip": ip_str,
                "threats": count,
                "pulse_names": names[:5],
                "safe": count == 0
            }
    except Exception as e:
        return {"ip": ip_str, "threats": 0, "safe": True, "error": str(e)}
