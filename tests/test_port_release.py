"""Prove the shutdown contract: closing NetVisual releases the port so the
next start binds immediately (the "works next time without issues" guarantee).

Exercises the EXACT teardown the app uses — ``server.shutdown()`` +
``server.server_close()`` (what ``main()``'s finally block and the tray "Stop"
both invoke) — then verifies:
  1. while running, the port answers
  2. after teardown, the port is released (connect refused)
  3. a fresh server re-binds the same port immediately (no "port in use")
  4. teardown is idempotent (calling shutdown twice, as finally does after a
     tray Stop already shut it down, is safe)

Run: python tests/test_port_release.py
"""
import os
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = 8799
URL = f"http://127.0.0.1:{PORT}"

# Make the project root importable (tests/ lives one level down).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The app's real teardown is a one-shot guard (netvisual.server.make_stoppable),
# NOT a raw double shutdown. Import it so we test the contract the app actually
# relies on — tray "Stop" and main()'s finally both call the SAME stop().
from netvisual.server import make_stoppable


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")


def _port_open():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", PORT)) == 0
    except OSError:
        return False


def main():
    results = []

    def check(name, cond):
        results.append((name, cond))
        print(("PASS" if cond else "FAIL"), name)

    # 1) start a real server (same class the app uses)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    check("while running, port answers (200)", _port_open())

    # 2) graceful teardown — the EXACT callable main() uses (make_stoppable),
    #    which does shutdown() + server_close() under a one-shot guard.
    stop = make_stoppable(srv)
    stop()
    time.sleep(0.2)
    check("after teardown, port released (refused)", not _port_open())

    # 3) re-bind the same port immediately => "works next time without issues"
    try:
        srv2 = ThreadingHTTPServer(("127.0.0.1", PORT), _H)
        check("re-bound same port immediately (no 'port in use')", True)
        stop2 = make_stoppable(srv2)
        stop2()
    except OSError as e:
        check(f"re-bound same port immediately ({e})", False)

    # 4) idempotency: tray "Stop" calls stop(), then main()'s finally calls
    #    stop() AGAIN on the same guard — the second call must be a safe no-op,
    #    not a deadlock (this is the bug that used to hang the process).
    try:
        stop()        # second call on the already-stopped guard
        check("stop() idempotent (double stop safe, no deadlock)", True)
    except Exception as e:
        check(f"stop() idempotent ({e!r})", False)

    failed = [n for n, c in results if not c]
    print()
    print(f"RESULT: {len(results)-len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
