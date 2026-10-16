"""Geo-IP resolver and external connection mapper for NetVisual.

Resolves external/public IP addresses to geographic coordinates (city, country,
lat, lon, ISP, organization) with local caching and batch lookup.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
import urllib.request
from typing import Any

from . import probes

# Thread-safe in-memory cache for IP -> Geo details
_lock = threading.Lock()
_geo_cache: dict[str, dict[str, Any]] = {}
_self_geo: dict[str, Any] | None = None
_self_geo_ts: float = 0


def is_public_ip(ip_str: str) -> bool:
    """True if ``ip_str`` is a valid, globally routable public unicast IP."""
    if not ip_str or ip_str.startswith("127.") or ip_str == "0.0.0.0" or ip_str == "::1":
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    except ValueError:
        return False


def _fetch_self_geo() -> dict[str, Any]:
    """Resolve the local machine's external IP and approximate geo location."""
    global _self_geo, _self_geo_ts
    now = time.time()
    if _self_geo and (now - _self_geo_ts < 3600):
        return _self_geo

    # Default fallback (Israel center / Tel Aviv approx)
    default_origin = {
        "ip": "", "city": "Local PC", "country": "Local",
        "country_code": "", "lat": 32.0853, "lon": 34.7818,
        "isp": "Local Network", "org": ""
    }

    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/?fields=status,message,country,countryCode,regionName,city,lat,lon,isp,org,query",
            headers={"User-Agent": "NetVisual-APlus/4.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                _self_geo = {
                    "ip": data.get("query", ""),
                    "city": data.get("city", "Local PC"),
                    "country": data.get("country", "Local"),
                    "country_code": data.get("countryCode", ""),
                    "lat": float(data.get("lat", 32.0853)),
                    "lon": float(data.get("lon", 34.7818)),
                    "isp": data.get("isp", ""),
                    "org": data.get("org", ""),
                }
                _self_geo_ts = now
                return _self_geo
    except Exception:
        pass

    return default_origin


def _batch_resolve_ips(ips: list[str]) -> None:
    """Resolve a batch of public IPs using ip-api.com batch API."""
    needed = [ip for ip in ips if ip not in _geo_cache and is_public_ip(ip)]
    if not needed:
        return

    # Cap at 80 IPs per batch request
    for chunk_start in range(0, len(needed), 80):
        chunk = needed[chunk_start:chunk_start + 80]
        try:
            req_data = json.dumps([{"query": ip} for ip in chunk]).encode("utf-8")
            req = urllib.request.Request(
                "http://ip-api.com/batch?fields=status,message,country,countryCode,regionName,city,lat,lon,isp,org,query",
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "NetVisual-APlus/4.0"}
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                results = json.loads(resp.read().decode())
                with _lock:
                    for item in results:
                        query_ip = item.get("query")
                        if not query_ip:
                            continue
                        if item.get("status") == "success":
                            _geo_cache[query_ip] = {
                                "ip": query_ip,
                                "city": item.get("city") or item.get("regionName") or "Unknown City",
                                "country": item.get("country") or "Unknown Country",
                                "country_code": item.get("countryCode") or "",
                                "lat": float(item.get("lat") or 0.0),
                                "lon": float(item.get("lon") or 0.0),
                                "isp": item.get("isp") or "",
                                "org": item.get("org") or "",
                            }
                        else:
                            _geo_cache[query_ip] = {
                                "ip": query_ip, "city": "Unknown", "country": "Unknown",
                                "country_code": "", "lat": 0.0, "lon": 0.0, "isp": "", "org": ""
                            }
        except Exception:
            with _lock:
                for ip in chunk:
                    if ip not in _geo_cache:
                        _geo_cache[ip] = {
                            "ip": ip, "city": "Unknown", "country": "Unknown",
                            "country_code": "", "lat": 0.0, "lon": 0.0, "isp": "", "org": ""
                        }


def _classify_cloud_and_risk(isp: str, org: str, ports: list[int]) -> dict[str, str]:
    """Classify host into known Cloud/CDN infrastructure and evaluate cybersecurity risk."""
    hay = f"{isp} {org}".lower()
    cloud = ""
    if "cloudflare" in hay or "13335" in hay:
        cloud = "Cloudflare"
    elif "amazon" in hay or "aws" in hay or "16509" in hay or "14618" in hay:
        cloud = "AWS"
    elif "google" in hay or "15169" in hay or "youtube" in hay:
        cloud = "Google Cloud"
    elif "microsoft" in hay or "azure" in hay or "8075" in hay:
        cloud = "Azure"
    elif "akamai" in hay or "20940" in hay:
        cloud = "Akamai"
    elif "fastly" in hay or "54113" in hay:
        cloud = "Fastly"
    elif "digitalocean" in hay or "14061" in hay:
        cloud = "DigitalOcean"
    elif "github" in hay or "36459" in hay:
        cloud = "GitHub"
    elif "oracle" in hay or "31898" in hay:
        cloud = "Oracle Cloud"
    elif "hetzner" in hay or "24940" in hay:
        cloud = "Hetzner"
    elif "ovh" in hay or "16276" in hay:
        cloud = "OVHcloud"
    elif "alibaba" in hay or "aliyun" in hay or "37963" in hay:
        cloud = "Alibaba Cloud"

    # Risk evaluation
    sensitive_ports = {22, 23, 3389, 445, 1433, 3306, 5900, 8080}
    has_sensitive_port = any(p in sensitive_ports for p in ports)

    if cloud in ("Cloudflare", "Google Cloud", "AWS", "Azure", "Akamai", "Fastly", "GitHub"):
        risk = "SAFE_CDN"
        cat = "CDN & Cloud Edge"
    elif has_sensitive_port and not cloud:
        risk = "HIGH_RISK"
        cat = "Sensitive Admin / DB Port"
    elif cloud:
        risk = "CLOUD"
        cat = "Cloud Hosting Infrastructure"
    elif any(term in hay for term in ("telecom", "broadband", "fiber", "mobile", "dynamic", "dsl")):
        risk = "RESIDENTIAL"
        cat = "ISP / Residential Network"
    else:
        risk = "STANDARD"
        cat = "Datacenter / Public Host"

    return {
        "cloud_provider": cloud,
        "risk_level": risk,
        "category": cat
    }


def get_geo_connections() -> dict[str, Any]:
    """Scan active network sockets, group by remote public IP, and attach Geo-IP data."""
    raw_conns = probes.probe_connections().get("connections", [])
    
    # Aggregate by remote IP
    ip_groups: dict[str, dict[str, Any]] = {}
    for c in raw_conns:
        rem = c.get("remote") or ""
        r_ip = c.get("remote_ip")
        r_port = c.get("remote_port")
        if not r_ip and rem and rem != "*:*" and ":" in rem:
            parts = rem.rsplit(":", 1)
            r_ip = parts[0].strip("[]")
            if parts[1].isdigit():
                r_port = int(parts[1])
        
        if not r_ip or not is_public_ip(r_ip):
            continue
        
        entry = ip_groups.setdefault(r_ip, {
            "ip": r_ip,
            "ports": set(),
            "processes": set(),
            "established": 0,
            "total_sockets": 0,
            "protocols": set(),
        })
        
        entry["total_sockets"] += 1
        if c.get("state") == "ESTABLISHED":
            entry["established"] += 1
        if r_port:
            entry["ports"].add(r_port)
        if c.get("process"):
            entry["processes"].add(c["process"])
        if c.get("proto"):
            entry["protocols"].add(c["proto"])

    public_ips = list(ip_groups.keys())
    
    # Resolve any missing IPs in cache
    missing_ips = [ip for ip in public_ips if ip not in _geo_cache]
    if missing_ips:
        _batch_resolve_ips(missing_ips)

    origin = _fetch_self_geo()

    destinations: list[dict[str, Any]] = []
    country_counts: dict[str, int] = {}
    process_counts: dict[str, int] = {}
    cloud_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {"SAFE_CDN": 0, "CLOUD": 0, "STANDARD": 0, "HIGH_RISK": 0, "RESIDENTIAL": 0}

    for ip, g in ip_groups.items():
        geo = _geo_cache.get(ip, {})
        lat = geo.get("lat", 0.0)
        lon = geo.get("lon", 0.0)
        
        country = geo.get("country", "Unknown")
        country_code = geo.get("country_code", "")
        city = geo.get("city", "Unknown")
        isp = geo.get("isp", "")
        org = geo.get("org", "")
        full_isp = isp or org
        
        if country and country != "Unknown":
            country_counts[country] = country_counts.get(country, 0) + 1
            
        procs = sorted(list(g["processes"]))
        for p in procs:
            process_counts[p] = process_counts.get(p, 0) + 1

        sorted_ports = sorted(list(g["ports"]))
        classification = _classify_cloud_and_risk(isp, org, sorted_ports)
        c_provider = classification["cloud_provider"]
        r_level = classification["risk_level"]
        
        if c_provider:
            cloud_counts[c_provider] = cloud_counts.get(c_provider, 0) + 1
        risk_counts[r_level] = risk_counts.get(r_level, 0) + 1

        destinations.append({
            "ip": ip,
            "lat": lat,
            "lon": lon,
            "city": city,
            "country": country,
            "country_code": country_code,
            "isp": full_isp,
            "org": org,
            "ports": sorted_ports,
            "processes": procs,
            "protocols": sorted(list(g["protocols"])),
            "established": g["established"],
            "total_sockets": g["total_sockets"],
            "cloud_provider": c_provider,
            "risk_level": r_level,
            "category": classification["category"],
        })

    # Sort destinations by established connection count desc
    destinations.sort(key=lambda d: (d["established"], d["total_sockets"]), reverse=True)

    top_country = max(country_counts.items(), key=lambda x: x[1])[0] if country_counts else "—"
    top_process = max(process_counts.items(), key=lambda x: x[1])[0] if process_counts else "—"
    top_cloud = max(cloud_counts.items(), key=lambda x: x[1])[0] if cloud_counts else "Direct / Other"

    return {
        "origin": origin,
        "destinations": destinations,
        "stats": {
            "total_destinations": len(destinations),
            "total_sockets": sum(d["total_sockets"] for d in destinations),
            "total_established": sum(d["established"] for d in destinations),
            "countries_count": len(country_counts),
            "top_country": top_country,
            "top_process": top_process,
            "top_cloud": top_cloud,
            "cloud_distribution": cloud_counts,
            "risk_distribution": risk_counts,
        }
    }
