"""Check that badge/panel classes used in app.js exist in style.css.
Run: python test_css.py"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
layout_p = ROOT / "static" / "layout.css"
theme_p = ROOT / "static" / "theme.css"
style_p = ROOT / "static" / "style.css"
css_parts = []
if layout_p.exists(): css_parts.append(layout_p.read_text(encoding="utf-8"))
if theme_p.exists(): css_parts.append(theme_p.read_text(encoding="utf-8"))
if style_p.exists(): css_parts.append(style_p.read_text(encoding="utf-8"))
css = "\n".join(css_parts)

# badge classes emitted in JS
badge_classes = set(re.findall(r'badge\([^,]+,\s*"([a-z0-9-]+)"', js))
badge_classes |= set(re.findall(r'"(b-[a-z]+)"', js))

ok = fail = 0
for c in sorted(badge_classes):
    # a class is "styled" if .c appears in css
    if re.search(r'\.' + re.escape(c) + r'[\s{,:.]', css):
        ok += 1
    else:
        fail += 1
        print(f"  UNSTYLED class: .{c}")

print(f"\n{ok} classes styled, {fail} unstyled")
import sys
sys.exit(1 if fail else 0)
