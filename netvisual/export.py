"""CSV & Report Exporter for Devices, Connections, and Sniffer Packets.
"""
from __future__ import annotations

import csv
import io
import time
from typing import Any


def export_devices_csv(devices: list[dict[str, Any]]) -> str:
    """Generate a clean CSV string of all discovered network devices."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["IP Address", "MAC Address", "Vendor / OUI", "Hostname", "Kind", "Latency (ms)", "Status", "Is New"])
    
    for d in devices:
        writer.writerow([
            d.get("ip", ""),
            d.get("mac", ""),
            d.get("vendor", "") or "Unknown",
            d.get("name", "") or d.get("ptr", "") or "",
            d.get("kind", "peer"),
            d.get("ms", "") or "",
            "Active" if d.get("up", True) else "Inactive",
            "Yes" if d.get("is_new") else "No"
        ])
    return output.getvalue()


def export_connections_csv(connections: list[dict[str, Any]]) -> str:
    """Generate a CSV string of all active TCP/UDP sockets."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Protocol", "Local Address", "Remote Address", "State", "PID", "Process Name"])
    
    for c in connections:
        writer.writerow([
            c.get("proto", ""),
            c.get("local", ""),
            c.get("remote", ""),
            c.get("state", ""),
            c.get("pid", ""),
            c.get("process", "") or ""
        ])
    return output.getvalue()


def export_packets_csv(packets: list[dict[str, Any]]) -> str:
    """Generate a CSV string of captured sniffer packets."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Packet #", "Timestamp", "Source", "Destination", "Protocol", "Length (Bytes)", "TCP Flags", "Summary"])
    
    for p in packets:
        writer.writerow([
            p.get("id", ""),
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.get("ts", time.time()))),
            f"{p.get('src_ip', '')}:{p.get('src_port', '')}" if p.get("src_port") else p.get("src_ip", ""),
            f"{p.get('dst_ip', '')}:{p.get('dst_port', '')}" if p.get("dst_port") else p.get("dst_ip", ""),
            p.get("proto", ""),
            p.get("length", ""),
            p.get("flags", "") or "",
            p.get("summary", "") or ""
        ])
    return output.getvalue()
