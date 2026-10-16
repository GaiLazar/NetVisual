"""Security + correctness self-test for NetVisual A+. Run: python tests/test_security.py"""
import os as _os, sys as _sys
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path: _sys.path.insert(0, _ROOT)
import server as s

ok = 0
fail = 0

def check(label, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}")

print("== safe_ip: injection / malformed must be rejected ==")
bad = [
    "127.0.0.1 " + chr(38) + "x",     # space + ampersand
    "8.8.8.8" + chr(59) + "x",         # semicolon
    "1.1.1.1" + chr(124) + "x",        # pipe
    "999.999.999.999",                 # out of range
    "1.2.3",                           # too few octets
    "",                                # empty
]
for t in bad:
    check(f"reject {t!r}", s.safe_ip(t) is False)

print("== safe_ip: valid IPs must pass ==")
for t in ["192.168.31.1", "8.8.8.8", "10.0.0.5", "0.0.0.0"]:
    check(f"accept {t!r}", s.safe_ip(t) is True)

print("== safe_host: injection rejected, legit accepted ==")
for t in ["evil.com" + chr(38) + "x", "a.com" + chr(59) + "b", "x" + chr(10) + "y"]:
    check(f"reject host {t!r}", s.safe_host(t) is False)
for t in ["google.com", "1.1.1.1", "a-b_c.d.example"]:
    check(f"accept host {t!r}", s.safe_host(t) is True)

print("== ping() on injection returns invalid IP (no subprocess exec) ==")
r = s.ping("1.2.3.4" + chr(38) + "x")
check("ping injection -> invalid IP flag", r.get("error") == "invalid IP" and r["reachable"] is False)

print("== parse_arp handles hyphen MACs ==")
sample = """
Interface: 192.168.1.50 --- 0x8
  Internet Address      Physical Address      Type
  192.168.1.1           9c-9d-7e-49-31-1d     dynamic
  192.168.1.100         aa-bb-cc-dd-ee-ff     dynamic
"""
rows = s.parse_arp(sample)
check("arp row count == 2", len(rows) == 2)
check("arp mac uppercase full", rows[0]["mac"] == "9C-9D-7E-49-31-1D")
check("arp type", rows[0]["type"] == "dynamic")

print("== parse_ipconfig handles 'Wireless LAN adapter' + hyphen MAC ==")
sample2 = """
Wireless LAN adapter WiFi 3:

   Media State . . . . . . . . . . . . . : Media disconnected
   Physical Address. . . . . . . . . : 02-00-00-00-00-02

Wireless LAN adapter WiFi:

   IPv4 Address. . . . . . . . . . . : 192.168.1.50(Preferred)
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
   Physical Address. . . . . . . . . : 00-11-22-33-44-55
"""
ifaces = s.parse_ipconfig(sample2)
check("two adapters found", len(ifaces) == 2)
byname = {i["name"]: i for i in ifaces}
check("WiFi adapter name", "WiFi" in byname)
check("WiFi ip", byname["WiFi"]["ip"] == "192.168.1.50")
check("WiFi gw", byname["WiFi"]["gw"] == "192.168.1.1")
check("WiFi mac full", byname["WiFi"]["mac"] == "00-11-22-33-44-55")
check("WiFi 3 marked down", byname["WiFi 3"]["media_down"] is True)

print("== topology filtering (no multicast/broadcast/other-net) ==")
import ipaddress
# build a fake topology by monkey-parsing
t = s.build_topology()
devs = [n["ip"] for n in t["nodes"] if n["kind"] == "device"]
check("no multicast 224.x", not any(d.startswith("224.") for d in devs))
check("no broadcast .255", not any(d.endswith(".255") for d in devs))
check("all on primary subnet", all(
    ipaddress.ip_address(d) in ipaddress.ip_network("192.168.31.0/24") for d in devs))

print(f"\nRESULT: {ok} passed, {fail} failed")
import sys
sys.exit(1 if fail else 0)
