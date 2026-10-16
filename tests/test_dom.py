"""Check that every id referenced in app.js exists in index.html.
Run: python test_dom.py"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

ids_in_html = set(re.findall(r'id="([^"]+)"', html))
# every $("#id") and document.getElementById("id") reference
refs = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', js))
refs |= set(re.findall(r'getElementById\("([A-Za-z0-9_-]+)"\)', js))

ok = 0
fail = 0
for r in sorted(refs):
    if r in ids_in_html:
        ok += 1
    else:
        fail += 1
        print(f"  MISSING in HTML: #{r}")

print(f"\n{ok} ids matched, {fail} missing")
import sys
sys.exit(1 if fail else 0)
