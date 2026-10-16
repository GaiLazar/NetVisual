"""TCP port scan via parallel ``socket.create_connection`` (stdlib, no shell).

Read-only by design: it only completes TCP handshakes. Classification:
  - ``open``      → handshake completed
  - ``closed``    → RST (connection refused)
  - ``filtered``  → no answer within timeout (firewalled / dropped)
"""
from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor

from .safety import safe_ip

#: Ports most home/office devices expose. Used when the caller passes none.
COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995,
    1433, 3306, 3389, 5432, 5900, 8080, 8443, 11211, 27017, 9200,
]


PORT_SERVICES: dict[int, dict[str, str]] = {
    21: {"service": "FTP", "risk": "HIGH", "desc": "File Transfer Protocol (Cleartext)"},
    22: {"service": "SSH", "risk": "SAFE", "desc": "Secure Shell Remote Access"},
    23: {"service": "Telnet", "risk": "CRITICAL", "desc": "Unencrypted Telnet Terminal (Severe Risk)"},
    25: {"service": "SMTP", "risk": "MEDIUM", "desc": "Simple Mail Transfer Protocol"},
    53: {"service": "DNS", "risk": "SAFE", "desc": "Domain Name System"},
    80: {"service": "HTTP", "risk": "MEDIUM", "desc": "Hypertext Transfer Protocol (Cleartext)"},
    110: {"service": "POP3", "risk": "MEDIUM", "desc": "Post Office Protocol v3"},
    135: {"service": "MS-RPC", "risk": "HIGH", "desc": "Microsoft Remote Procedure Call"},
    139: {"service": "NetBIOS", "risk": "HIGH", "desc": "NetBIOS Session Service"},
    143: {"service": "IMAP", "risk": "MEDIUM", "desc": "Internet Message Access Protocol"},
    443: {"service": "HTTPS", "risk": "SAFE", "desc": "Secure Hypertext Transfer (TLS)"},
    445: {"service": "SMB", "risk": "CRITICAL", "desc": "Server Message Block (WannaCry / EternalBlue vector)"},
    993: {"service": "IMAPS", "risk": "SAFE", "desc": "Secure IMAP over TLS"},
    995: {"service": "POP3S", "risk": "SAFE", "desc": "Secure POP3 over TLS"},
    1433: {"service": "MS-SQL", "risk": "HIGH", "desc": "Microsoft SQL Database Server"},
    3306: {"service": "MySQL", "risk": "HIGH", "desc": "MySQL Database Server"},
    3389: {"service": "RDP", "risk": "HIGH", "desc": "Remote Desktop Protocol"},
    5432: {"service": "PostgreSQL", "risk": "HIGH", "desc": "PostgreSQL Database Server"},
    5900: {"service": "VNC", "risk": "HIGH", "desc": "Virtual Network Computing Remote Desktop"},
    8080: {"service": "HTTP-Proxy", "risk": "MEDIUM", "desc": "Alternative Web / Proxy Server"},
    8443: {"service": "HTTPS-Alt", "risk": "SAFE", "desc": "Alternative Secure Web Server"},
    11211: {"service": "Memcached", "risk": "CRITICAL", "desc": "Memcached (DDoS amplification risk)"},
    27017: {"service": "MongoDB", "risk": "HIGH", "desc": "MongoDB Database Instance"},
    9200: {"service": "Elasticsearch", "risk": "HIGH", "desc": "Elasticsearch REST API"},
}


def portscan(ip: str, ports: list[int] | None = None,
             timeout: float = 0.6) -> dict:
    """Scan ``ip`` for open TCP ports with service and risk evaluation."""
    if not safe_ip(ip):
        return {"ip": ip, "error": "invalid IP", "ports": [],
                "open_ports": [], "open_count": 0, "total": 0, "risk_summary": "SAFE"}
    ip = ip.strip()
    if not ports:
        ports = COMMON_PORTS
    ports = sorted({max(1, min(65535, int(p)))
                    for p in ports
                    if str(p).strip().lstrip("-").isdigit()})
    if not ports:
        return {"ip": ip, "error": "no valid ports", "ports": [],
                "open_ports": [], "open_count": 0, "total": 0, "risk_summary": "SAFE"}
    timeout = max(0.1, min(5.0, float(timeout or 0.6)))

    def probe(port: int) -> dict:
        t0 = time.time()
        meta = PORT_SERVICES.get(port, {"service": f"TCP/{port}", "risk": "MEDIUM", "desc": "Custom TCP Service"})
        try:
            with socket.create_connection((ip, port), timeout=timeout) as s:
                ms = round((time.time() - t0) * 1000, 1)
                banner = ""
                try:
                    s.settimeout(0.3)
                    banner_bytes = s.recv(128)
                    if banner_bytes:
                        banner = banner_bytes.decode("utf-8", errors="replace").strip()[:64]
                except Exception:
                    pass
                return {
                    "port": port,
                    "service": meta["service"],
                    "risk": meta["risk"],
                    "desc": meta["desc"],
                    "open": True,
                    "ms": ms,
                    "state": "open",
                    "banner": banner
                }
        except ConnectionRefusedError:
            return {
                "port": port,
                "service": meta["service"],
                "risk": meta["risk"],
                "desc": meta["desc"],
                "open": False,
                "ms": round((time.time() - t0) * 1000, 1),
                "state": "closed",
                "banner": ""
            }
        except (socket.timeout, TimeoutError, OSError):
            return {
                "port": port,
                "service": meta["service"],
                "risk": meta["risk"],
                "desc": meta["desc"],
                "open": False,
                "ms": None,
                "state": "filtered",
                "banner": ""
            }

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=24) as ex:
        results = list(ex.map(probe, ports))
    results.sort(key=lambda r: r["port"])
    open_entries = [r for r in results if r["open"]]
    
    # Assess overall risk level
    has_critical = any(r["risk"] == "CRITICAL" for r in open_entries)
    has_high = any(r["risk"] == "HIGH" for r in open_entries)
    has_medium = any(r["risk"] == "MEDIUM" for r in open_entries)
    risk_summary = "CRITICAL" if has_critical else ("HIGH" if has_high else ("MEDIUM" if has_medium else "SAFE"))

    return {
        "ip": ip,
        "ports": results,
        "open_ports": [r["port"] for r in open_entries],
        "open_entries": open_entries,
        "open_count": len(open_entries),
        "total": len(results),
        "risk_summary": risk_summary
    }
