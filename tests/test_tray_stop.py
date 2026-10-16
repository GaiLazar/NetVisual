"""End-to-end: the tray "Stop NetVisual" path must terminate the WHOLE
process and release the port — nothing may linger in the background.

Run:  python tests/test_tray_stop.py   (Windows only)

This drives the REAL app in tray mode. The Stop path is exercised via
NETVISUAL_TRAY_STOP_AFTER, which makes the tray post the very same
WM_TRAY_STOP message the menu's "Stop NetVisual" item posts (tray.py:
menu → WM_TRAY_STOP → TrayIcon._stop() → server_close() → PostQuitMessage).
So what is tested is byte-for-byte the menu's shutdown, not a re-implementation.

Asserts:
  1. the app boots, serves HTTP, and registers the tray window
  2. the process EXITS by itself when Stop fires (no lingering background
     process) — with exit code 0
  3. the port is released immediately after
  4. the log shows the deterministic "port released — bye" and no traceback

Exit 0 on all-pass.
"""
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

if os.name != "nt":
    print("skip: tray test is Windows-only")
    sys.exit(0)

from netvisual import tray as tray_mod

PORT = 8743
BASE = f"http://127.0.0.1:{PORT}"
LOG = os.path.join(HERE, "data", "tray_stop_test.log")
STOP_AFTER = 5  # seconds until the tray fires its real Stop path

ok = fail = 0
def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  PASS  {label}")
    else:
        fail += 1; print(f"  FAIL  {label} {extra}")

def wait_http(timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/api/summary", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

# ---- start the real app in tray mode with auto-stop -----------------------
env = dict(os.environ)
env["NETVISUAL_PORT"] = str(PORT)
env["NETVISUAL_TRAY"] = "1"
env["NETVISUAL_TRAY_STOP_AFTER"] = str(STOP_AFTER)
logf = open(LOG, "w", encoding="utf-8")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "netvisual_app.py")],
                        env=env, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT)

try:
    check("server answers in tray mode", wait_http())

    check("tray is supported", tray_mod.is_supported())

    # ---- the real Stop path fires by itself after STOP_AFTER seconds -------
    deadline = time.time() + (STOP_AFTER + 15)
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.3)
    if proc.poll() is None:
        proc.kill(); proc.wait(timeout=5)

    check("process exits on its own when Stop fires (no linger)",
          proc.poll() is not None, f"(rc={proc.returncode})")
    check("exit code 0", proc.returncode == 0, f"(rc={proc.returncode})")

    # ---- port released -------------------------------------------------------
    time.sleep(1)
    free = True
    try:
        with urllib.request.urlopen(BASE + "/api/summary", timeout=2) as r:
            free = r.status != 200
    except Exception:
        free = True
    check("port released after Stop", free)

    # ---- deterministic shutdown, no crash ------------------------------------
    log = open(LOG, encoding="utf-8", errors="replace").read()
    check("log shows 'port released — bye'", "port released" in log)
    check("no traceback in log", "Traceback" not in log)
finally:
    logf.close()
    if proc.poll() is None:
        try:
            proc.kill(); proc.wait(timeout=5)
        except Exception:
            pass
    try:
        os.remove(LOG)
    except Exception:
        pass

print(f"\nRESULT: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
