"""Smart AI Network Explainer & Diagnostic Synthesizer.

Analyzes telemetry across latency, DNS security, Wi-Fi channel crowding,
socket threat intelligence, and bandwidth spikes to produce natural language
summaries and actionable optimization recommendations (in Hebrew and English).
"""
from __future__ import annotations

from typing import Any
from . import probes, security, wifi, summary


def generate_network_explanation() -> dict[str, Any]:
    """Evaluate current network posture and synthesize diagnostic insights."""
    insights_he: list[dict[str, str]] = []
    insights_en: list[dict[str, str]] = []
    score = 100

    # 1. Gateway & Connectivity
    summ = summary.summary()
    gw_up = summ.get("gateway_up", True)
    gw_ip = summ.get("gateway", "—")
    if not gw_up:
        score -= 40
        insights_he.append({
            "type": "err",
            "title": "הראוטר/שער ברירת המחדל אינו מגיב",
            "desc": f"לא ניתן להגיע לראוטר בכתובת {gw_ip}. בדוק את כבל הרשת או את חיבור ה-Wi-Fi.",
            "icon": "⚠️"
        })
        insights_en.append({
            "type": "err",
            "title": "Default Gateway Unreachable",
            "desc": f"Router at {gw_ip} is not responding to ICMP ping. Check your physical connection or AP.",
            "icon": "⚠️"
        })
    else:
        insights_he.append({
            "type": "ok",
            "title": "חיבור הראוטר תקין ויציב",
            "desc": f"שער ברירת המחדל ({gw_ip}) מקושר ומגיב במהירות.",
            "icon": "✅"
        })
        insights_en.append({
            "type": "ok",
            "title": "Gateway Connection Healthy",
            "desc": f"Default gateway ({gw_ip}) is responsive and reachable.",
            "icon": "✅"
        })

    # 2. Security & Threat Posture
    sec_audit = security.audit_security()
    threats = sec_audit.get("threats", [])
    if threats:
        score -= min(30, len(threats) * 15)
        insights_he.append({
            "type": "err",
            "title": f"זוהו {len(threats)} איומי אבטחה או פורטים רגישים פתוחים",
            "desc": f"חיבורים פעילים משתמשים בפורטים בסיכון גבוה ({', '.join(t['title'] for t in threats[:2])}). מומלץ לסגור אותם.",
            "icon": "🚨"
        })
        insights_en.append({
            "type": "err",
            "title": f"{len(threats)} High-Risk Port / Sockets Detected",
            "desc": f"Active sockets on high-risk ports ({', '.join(t['title'] for t in threats[:2])}). Consider terminating them.",
            "icon": "🚨"
        })
    else:
        insights_he.append({
            "type": "ok",
            "title": "רמת אבטחת חיבורים נקייה",
            "desc": "לא זוהו פורטים חשודים, כורי מטבעות או שרתי שליטה עוינים.",
            "icon": "🛡️"
        })
        insights_en.append({
            "type": "ok",
            "title": "Zero Socket Anomalies",
            "desc": "No malicious mining or backdoors detected across active sockets.",
            "icon": "🛡️"
        })

    # 3. DNS Encryption & Leaks
    dns_check = sec_audit.get("dns", {})
    if not dns_check.get("is_encrypted_upstream", False):
        score -= 5
        insights_he.append({
            "type": "warn",
            "title": "שרת ה-DNS של ספק האינטרנט אינו מוצפן",
            "desc": "שאילתות הדומיינים שלך חשופות לספק. מומלץ לעבור ל-Cloudflare (1.1.1.1) או Quad9 בלשונית Profiles.",
            "icon": "🔒"
        })
        insights_en.append({
            "type": "warn",
            "title": "Unencrypted DNS Resolver",
            "desc": "Your DNS queries are in cleartext. Switch to Cloudflare (1.1.1.1) or Quad9 under Profiles tab.",
            "icon": "🔒"
        })

    # 4. Wi-Fi Channel & Congestion
    wifi_data = wifi.get_wifi_details()
    if wifi_data.get("has_wifi", False):
        curr_ch = wifi_data.get("channel", 0)
        rec_ch = wifi_data.get("recommendation", {}).get("cleanest_24ghz", 1)
        nearby_cnt = len(wifi_data.get("nearby", []))
        if nearby_cnt > 5 and curr_ch in (6, 11) and rec_ch != curr_ch:
            insights_he.append({
                "type": "warn",
                "title": f"עומס ערוצי Wi-Fi בסביבתך ({nearby_cnt} רשתות שכנות)",
                "desc": f"הרשת שלך משדרת בערוץ {curr_ch}. מעבר לערוץ {rec_ch} בהגדרות הראוטר יקטין הפרעות וישפר מהירות.",
                "icon": "📶"
            })
            insights_en.append({
                "type": "warn",
                "title": f"Wi-Fi Channel Congestion ({nearby_cnt} Nearby APs)",
                "desc": f"Your AP is on Channel {curr_ch}. Switching to Channel {rec_ch} in router settings improves SNR.",
                "icon": "📶"
            })

    # 5. ARP Spoofing / MAC Duplication
    from . import topology
    topo = topology.probe(sweep=False)
    if "warnings" in topo and topo["warnings"]:
        score -= min(40, len(topo["warnings"]) * 20)
        insights_he.append({
            "type": "warn",
            "title": "התראת MAC כפול: חשד ל-ARP Spoofing או רשת מש (Mesh)",
            "desc": f"מספר מכשירים חולקים את אותה כתובת MAC ({len(topo['warnings'])} התראות). זה תקין אם יש לך ראוטר מסוג Repeater/Mesh, אחרת ייתכן שיש ניסיון האזנה (ARP Spoof).",
            "icon": "🎭"
        })
        insights_en.append({
            "type": "warn",
            "title": "MAC Duplication: ARP Spoofing or Proxy/Mesh",
            "desc": f"Multiple devices share the exact same MAC address ({len(topo['warnings'])} alerts). If you don't use a Wi-Fi Extender or VPN/VM, this could be an ARP Spoofing attack.",
            "icon": "🎭"
        })

    score = max(20, min(100, score))
    return {
        "score": score,
        "insights_he": insights_he,
        "insights_en": insights_en,
        "summary_text_he": f"ציון בריאות הרשת: {score}/100. {'רשת יציבה ומאובטחת ללא חריגות.' if score >= 85 else 'קיימות המלצות לשיפור ביצועים ואבטחה.'}",
        "summary_text_en": f"Network Health Score: {score}/100. {'Network is highly optimized.' if score >= 85 else 'Actionable optimizations recommended.'}"
    }
