"""Agent Tools module for NetVisual Cyber AI Copilot.

Provides executable local network actions and live internet search.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any


def search_web(query: str, max_results: int = 4) -> dict[str, Any]:
    """Search the live internet for security advisories, CVEs, ports, or general networking info."""
    clean_query = query.strip()
    if not clean_query:
        return {"error": "Empty search query", "results": []}

    results = []
    # 1. Try DuckDuckGo HTML Lite search
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_query)}"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7'
            }
        )
        with urllib.request.urlopen(req, timeout=7) as response:
            html = response.read().decode('utf-8', errors='ignore')
            snippets = re.findall(r'<a[^>]+class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a[^>]+class="result__url[^>]*>(.*?)</a>', html, re.DOTALL)
            for i in range(min(len(snippets), max_results)):
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
                if snippet:
                    results.append({"url": title, "snippet": snippet})
    except Exception as e:
        pass

    # 2. Fallback to DuckDuckGo Instant Answer API if HTML returned empty
    if not results:
        try:
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(clean_query)}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                abstract = data.get("AbstractText") or data.get("Abstract")
                if abstract:
                    results.append({"url": data.get("AbstractURL", "duckduckgo.com"), "snippet": abstract})
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({"url": topic.get("FirstURL", ""), "snippet": topic.get("Text")})
        except Exception:
            pass

    return {
        "query": clean_query,
        "count": len(results),
        "results": results or [{"url": "web", "snippet": "No direct search snippets found for query."}]
    }


def run_security_audit() -> dict[str, Any]:
    """Execute a real threat and socket vulnerability audit on the local system."""
    try:
        from . import security
        return security.audit_security()
    except Exception as e:
        return {"error": f"Security audit failed: {str(e)}"}


def check_ip(ip: str) -> dict[str, Any]:
    """Look up WHOIS ownership, ASN, and AlienVault Threat Intelligence for an IP."""
    try:
        from . import security
        whois_data = security.query_whois(ip)
        threat_data = security.check_threat_intel(ip)
        return {
            "ip": ip,
            "whois": whois_data,
            "threat_intel": threat_data
        }
    except Exception as e:
        return {"error": f"IP lookup failed: {str(e)}"}


def check_dns_leaks() -> dict[str, Any]:
    """Check DNS servers and potential leakage vectors."""
    try:
        from . import security
        return security.check_dns_leaks()
    except Exception as e:
        return {"error": f"DNS leak check failed: {str(e)}"}


def run_ping(target: str, count: int = 3) -> dict[str, Any]:
    """Ping a host or IP and report packet loss, round-trip time, and OS estimate."""
    try:
        from . import ping
        return ping.ping(target, count=count)
    except Exception as e:
        return {"error": f"Ping failed: {str(e)}"}


def run_traceroute(target: str, maxhops: int = 12) -> dict[str, Any]:
    """Trace route hops to a destination IP or hostname."""
    try:
        from . import traceroute
        hops = traceroute.traceroute(target, maxhops=maxhops)
        return {"target": target, "hops_count": len(hops), "hops": hops}
    except Exception as e:
        return {"error": f"Traceroute failed: {str(e)}"}


def run_port_scan(target: str, ports: list[int] | None = None) -> dict[str, Any]:
    """Scan open ports and risky services on a given target IP."""
    try:
        from . import portscan
        return portscan.portscan(target, ports=ports)
    except Exception as e:
        return {"error": f"Port scan failed: {str(e)}"}


def start_speedtest() -> dict[str, Any]:
    """Trigger the multi-stream bandwidth, latency, and jitter speed test."""
    try:
        from . import speedtest
        started = speedtest.start_speedtest()
        status = speedtest.get_status()
        return {"started": started, "status": status}
    except Exception as e:
        return {"error": f"Speed test failed: {str(e)}"}


def repair_network() -> dict[str, Any]:
    """Flush DNS cache, purge ARP cache, and re-register network stack."""
    try:
        from . import netprofiles
        return netprofiles.repair_network()
    except Exception as e:
        return {"error": f"Network repair failed: {str(e)}"}


def set_dns(preset: str) -> dict[str, Any]:
    """Switch system DNS servers to a preset (cloudflare, google, quad9, adguard, dhcp)."""
    try:
        from . import netprofiles
        return netprofiles.set_dns_preset(preset)
    except Exception as e:
        return {"error": f"DNS switch failed: {str(e)}"}


def get_wifi() -> dict[str, Any]:
    """Retrieve active Wi-Fi connection, SSID, signal strength, and channel metrics."""
    try:
        from . import wifi
        return wifi.get_wifi_details()
    except Exception as e:
        return {"error": f"Wi-Fi details failed: {str(e)}"}


# Registry mapping tool names to functions
TOOL_REGISTRY = {
    "search_web": search_web,
    "run_security_audit": run_security_audit,
    "check_ip": check_ip,
    "check_dns_leaks": check_dns_leaks,
    "run_ping": run_ping,
    "run_traceroute": run_traceroute,
    "run_port_scan": run_port_scan,
    "start_speedtest": start_speedtest,
    "repair_network": repair_network,
    "set_dns": set_dns,
    "get_wifi": get_wifi,
}


def execute_tool_call(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Executes a tool by name with arguments and returns the structured result."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        return {"error": f"Tool '{tool_name}' not found."}
    try:
        return func(**args)
    except TypeError as e:
        try:
            # Fallback to calling without args if args mismatched
            return func()
        except Exception as inner_e:
            return {"error": f"Error executing tool '{tool_name}': {str(inner_e)}"}
    except Exception as e:
        return {"error": f"Tool execution error: {str(e)}"}
