"""Windows Desktop Toast Notifications & Alert Watcher for NetVisual.

Sends native notification alerts to the user when:
  - A new device connects to the LAN
  - Internet/Gateway connection is lost or restored
  - Critical network alerts are triggered
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from .paths import DATA_DIR

CONFIG_FILE = DATA_DIR / "notifications.json"

_settings: dict[str, Any] = {
    "enabled": True,
    "notify_new_devices": True,
    "notify_gateway_drop": True,
    "notify_high_bandwidth": False,
}

_known_ips: set[str] = set()
_last_gw_up: bool | None = None
_tray_instance = None
_lock = threading.Lock()


def set_tray_icon(icon_instance) -> None:
    global _tray_instance
    with _lock:
        _tray_instance = icon_instance


def load_settings() -> dict[str, Any]:
    global _settings
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                _settings.update(json.load(f))
        except Exception:
            pass
    return _settings


def save_settings(new_conf: dict[str, Any]) -> dict[str, Any]:
    global _settings
    with _lock:
        _settings.update(new_conf)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(_settings, f, indent=2)
        except Exception:
            pass
    return _settings


def send_notification(title: str, message: str) -> None:
    """Send a desktop notification via pystray or PowerShell Windows toast."""
    load_settings()
    if not _settings.get("enabled", True):
        return

    # Try pystray tray notification if available
    with _lock:
        ti = _tray_instance

    if ti and hasattr(ti, "notify"):
        try:
            ti.notify(message, title)
            return
        except Exception:
            pass

    # Windows PowerShell Toast fallback
    def _ps_toast():
        ps_code = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("NetVisual A+")
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($toast)
        """
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_ps_toast, daemon=True).start()


def evaluate_events(devices: list[dict[str, Any]], gw_up: bool | None) -> None:
    """Evaluate changes and send notifications if enabled."""
    global _known_ips, _last_gw_up
    load_settings()
    if not _settings.get("enabled", True):
        return

    # 1. Check Gateway drop / recovery
    if _settings.get("notify_gateway_drop", True) and gw_up is not None:
        if _last_gw_up is True and gw_up is False:
            send_notification("⚠️ Internet / Gateway Disconnected", "Your default gateway stopped responding to pings.")
        elif _last_gw_up is False and gw_up is True:
            send_notification("✅ Internet Restored", "Connection to default gateway has recovered.")
        _last_gw_up = gw_up

    # 2. Check New Devices
    if _settings.get("notify_new_devices", True) and devices:
        current_ips = {d.get("ip") for d in devices if d.get("ip")}
        if _known_ips:
            new_ips = current_ips - _known_ips
            if new_ips:
                if len(new_ips) == 1:
                    ip = list(new_ips)[0]
                    dev = next((d for d in devices if d.get("ip") == ip), {})
                    vendor = dev.get("vendor", "")
                    vendor_str = f" ({vendor})" if vendor and vendor != "Unknown" else ""
                    send_notification("🖥️ New Device on Network", f"Host {ip}{vendor_str} just connected to your subnet.")
                else:
                    lines = []
                    for ip in new_ips:
                        dev = next((d for d in devices if d.get("ip") == ip), {})
                        vendor = dev.get("vendor", "")
                        vendor_str = f" ({vendor})" if vendor and vendor != "Unknown" else ""
                        lines.append(f"{ip}{vendor_str}")
                    if len(lines) > 3:
                        msg = ", ".join(lines[:3]) + f" and {len(lines)-3} more devices connected."
                    else:
                        msg = ", ".join(lines) + " connected to your subnet."
                    send_notification(f"🖥️ {len(new_ips)} New Devices on Network", msg)
        _known_ips = current_ips
