"""Wi-Fi Analyzer and Channel Congestion Optimizer for NetVisual.

Scans local Wi-Fi interfaces and nearby access points using Windows netsh wlan,
calculating channel utilization, signal quality (dBm / %), and channel recommendations.
"""
from __future__ import annotations

import re
from typing import Any

from .runner import run


def _signal_pct_to_dbm(pct: int) -> int:
    """Approximate dBm from Windows signal percentage (0-100%)."""
    # 100% -> -30 dBm, 0% -> -95 dBm
    return int(-95 + (pct * 0.65))


def get_wifi_details() -> dict[str, Any]:
    """Scan the local Wi-Fi interface and neighboring access points."""
    code_if, out_if = run("netsh wlan show interfaces", 8)
    code_net, out_net = run("netsh wlan show networks mode=bssid", 12)

    connected: dict[str, Any] | None = None
    nearby: list[dict[str, Any]] = []

    # Parse current interface
    if "SSID" in out_if or "State" in out_if:
        current_data: dict[str, str] = {}
        for line in out_if.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                current_data[k.strip().lower()] = v.strip()

        ssid = current_data.get("ssid")
        state = current_data.get("state") or current_data.get("מצב", "")

        if ssid and "connected" in state.lower():
            sig_str = current_data.get("signal", "0%").replace("%", "").strip()
            sig_val = int(sig_str) if sig_str.isdigit() else 0
            
            rx_str = current_data.get("receive rate (mbps)", "0").strip()
            tx_str = current_data.get("transmit rate (mbps)", "0").strip()
            
            connected = {
                "ssid": ssid,
                "bssid": current_data.get("bssid", "—"),
                "state": state,
                "radio_type": current_data.get("radio type", "802.11ac"),
                "authentication": current_data.get("authentication", "WPA2-Personal"),
                "channel": int(current_data.get("channel", "1")) if current_data.get("channel", "").isdigit() else 1,
                "signal_pct": sig_val,
                "signal_dbm": _signal_pct_to_dbm(sig_val),
                "rx_rate_mbps": float(rx_str) if rx_str.replace(".", "").isdigit() else 0,
                "tx_rate_mbps": float(tx_str) if tx_str.replace(".", "").isdigit() else 0,
            }

    # Parse nearby networks & BSSIDs
    current_ssid = ""
    current_auth = "WPA2"
    current_bssid_entry: dict[str, Any] = {}

    for line in out_net.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("SSID") and ":" in line_clean:
            parts = line_clean.split(":", 1)
            current_ssid = parts[1].strip() or "<Hidden Network>"
        elif "Authentication" in line_clean or "אימות" in line_clean:
            current_auth = line_clean.split(":", 1)[1].strip()
        elif line_clean.startswith("BSSID") and ":" in line_clean:
            if current_bssid_entry and "bssid" in current_bssid_entry:
                nearby.append(current_bssid_entry)
            bssid_val = line_clean.split(":", 1)[1].strip()
            current_bssid_entry = {
                "ssid": current_ssid,
                "bssid": bssid_val,
                "auth": current_auth,
                "signal_pct": 50,
                "channel": 1,
                "band": "2.4 GHz",
                "radio": "802.11n"
            }
        elif "Signal" in line_clean or "אות" in line_clean:
            sig_match = re.search(r"(\d+)%", line_clean)
            if sig_match and current_bssid_entry:
                current_bssid_entry["signal_pct"] = int(sig_match.group(1))
                current_bssid_entry["signal_dbm"] = _signal_pct_to_dbm(int(sig_match.group(1)))
        elif "Channel" in line_clean or "ערוץ" in line_clean:
            ch_match = re.search(r"(\d+)", line_clean.split(":", 1)[-1])
            if ch_match and current_bssid_entry:
                ch = int(ch_match.group(1))
                current_bssid_entry["channel"] = ch
                current_bssid_entry["band"] = "5 GHz" if ch > 14 else "2.4 GHz"
        elif "Radio type" in line_clean:
            if current_bssid_entry:
                current_bssid_entry["radio"] = line_clean.split(":", 1)[-1].strip()

    if current_bssid_entry and "bssid" in current_bssid_entry:
        nearby.append(current_bssid_entry)

    # Channel congestion map
    channels_24: dict[int, int] = {ch: 0 for ch in range(1, 14)}
    channels_5: dict[int, int] = {ch: 0 for ch in [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 149, 153, 157, 161, 165]}

    for ap in nearby:
        ch = ap.get("channel", 1)
        if ch in channels_24:
            channels_24[ch] += 1
        elif ch in channels_5:
            channels_5[ch] += 1

    # Recommendations
    # Best 2.4 GHz channels are typically 1, 6, 11
    best_24 = min([1, 6, 11], key=lambda c: channels_24.get(c, 0))
    best_5 = min([36, 44, 149, 157], key=lambda c: channels_5.get(c, 0))

    return {
        "has_wifi": connected is not None or len(nearby) > 0,
        "connected": connected,
        "nearby_count": len(nearby),
        "nearby": sorted(nearby, key=lambda x: x.get("signal_pct", 0), reverse=True),
        "channel_congestion_24": [{"channel": k, "count": v} for k, v in channels_24.items() if k in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]],
        "channel_congestion_5": [{"channel": k, "count": v} for k, v in channels_5.items() if v > 0 or k in [36, 40, 44, 48, 149, 153, 157, 161]],
        "recommendation": {
            "best_24_channel": best_24,
            "best_5_channel": best_5,
            "tip": f"For 2.4GHz, Channel {best_24} is least congested. For 5GHz, Channel {best_5} offers clean spectrum."
        }
    }
