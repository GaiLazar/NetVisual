"""NetVisual A+ v4 — root launcher.

Thin entry point so the app can be started from the project root without the
``-m`` flag:

    python netvisual_app.py            # start on port 8730
    NETVISUAL_PORT=9000 python netvisual_app.py

Equivalent to ``python -m netvisual.server``.
"""
from __future__ import annotations

from netvisual.server import main

if __name__ == "__main__":
    main()
