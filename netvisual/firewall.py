"""Windows Defender Firewall manager for 1-click application blocking/unblocking.

Uses ``netsh advfirewall firewall`` (stdlib runner, no third-party dependencies).
"""
from __future__ import annotations

import os
from typing import Any
from .runner import run

RULE_PREFIX = "NetVisual_Block_"


def list_blocked_programs() -> list[dict[str, Any]]:
    """List all application rules created by NetVisual."""
    code, out = run("netsh advfirewall firewall show rule name=all", timeout=5)
    if code != 0 or not out:
        return []
    
    rules: list[dict[str, Any]] = []
    current_rule: dict[str, Any] = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Rule Name:") or line.startswith("שם כלל:"):
            if current_rule and current_rule.get("name", "").startswith(RULE_PREFIX):
                rules.append(current_rule)
            name = line.split(":", 1)[1].strip()
            current_rule = {"name": name, "blocked": True}
        elif line.startswith("Program:") or line.startswith("תוכנית:"):
            prog = line.split(":", 1)[1].strip()
            current_rule["program"] = prog
        elif line.startswith("Action:") or line.startswith("פעולה:"):
            action = line.split(":", 1)[1].strip()
            current_rule["action"] = action

    if current_rule and current_rule.get("name", "").startswith(RULE_PREFIX):
        rules.append(current_rule)
    return rules


def block_application(program_path: str, rule_name: str | None = None) -> dict[str, Any]:
    """Create an outbound block rule in Windows Defender Firewall."""
    if not program_path:
        return {"ok": False, "error": "Program path required"}
    
    clean_path = program_path.strip().strip('"')
    base_name = os.path.splitext(os.path.basename(clean_path))[0] or "App"
    rname = rule_name or f"{RULE_PREFIX}{base_name}"

    # First delete existing rule with same name to avoid duplicates
    run(f'netsh advfirewall firewall delete rule name="{rname}"', timeout=4)

    # Add outbound block rule
    cmd = f'netsh advfirewall firewall add rule name="{rname}" dir=out action=block program="{clean_path}" enable=yes'
    code, out = run(cmd, timeout=6)
    return {
        "ok": code == 0,
        "rule_name": rname,
        "program": clean_path,
        "output": out or ("Blocked successfully" if code == 0 else "Failed. Run as Administrator."),
        "error": None if code == 0 else (out or "Access Denied. Administrator required.")
    }


def unblock_application(rule_name: str | None = None, program_path: str | None = None) -> dict[str, Any]:
    """Remove a block rule from Windows Defender Firewall."""
    if not rule_name and not program_path:
        return {"ok": False, "error": "Rule name or program path required"}
    
    if rule_name:
        rname = rule_name
    else:
        clean_path = (program_path or "").strip().strip('"')
        base_name = os.path.splitext(os.path.basename(clean_path))[0]
        rname = f"{RULE_PREFIX}{base_name}"
        
    code, out = run(f'netsh advfirewall firewall delete rule name="{rname}"', timeout=6)
    return {
        "ok": code == 0,
        "rule_name": rname,
        "output": out or "Unblocked successfully",
        "error": None if code == 0 else (out or "Failed to remove rule.")
    }
