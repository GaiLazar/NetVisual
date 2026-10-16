"""Generate high-contrast, vibrant NetVisual.ico for Windows 10/11 taskbar & tray.

Creates dedicated handcrafted renderings for 16, 20, 24, 32, 48, 64, 128, 256
so the icon is ultra-crisp at taskbar scale (16-24px) and gorgeous at 256px.
"""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "NetVisual.ico"
SIZES = [16, 20, 24, 32, 48, 64, 128, 256]


def draw_icon_at_size(s: int) -> Image.Image:
    """Draw a size-tailored network topology badge with transparent background."""
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = (s - 1) / 2.0, (s - 1) / 2.0

    if s <= 24:
        # Small / Tray resolution: bold geometry, thick high-contrast strokes
        # Circular backdrop glow badge for maximum contrast on any taskbar color
        badge_r = (s - 1) / 2.0 - 0.5
        d.ellipse([cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r],
                  fill=(10, 20, 36, 240), outline=(0, 240, 255, 255), width=1)

        # 4 bold satellite nodes connected to center
        r_orbit = s * 0.32
        angles = [-math.pi / 2, 0, math.pi / 2, math.pi]
        pts = [(cx + r_orbit * math.cos(a), cy + r_orbit * math.sin(a)) for a in angles]

        # Connecting lines
        for px, py in pts:
            d.line([(cx, cy), (px, py)], fill=(0, 240, 255, 255), width=2)

        # Center node (Vibrant Mint)
        core_r = max(2.5, s * 0.18)
        d.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r],
                  fill=(0, 255, 163, 255), outline=(255, 255, 255, 255), width=1)

        # Satellites (Crisp White / Cyan)
        sat_r = max(1.5, s * 0.12)
        for px, py in pts:
            d.ellipse([px - sat_r, py - sat_r, px + sat_r, py + sat_r],
                      fill=(255, 255, 255, 255), outline=(0, 240, 255, 255), width=1)

    else:
        # High-res (32px .. 256px): Rich gradient nodes, glowing aura, 6 mesh satellites
        badge_r = (s - 1) / 2.0 - (s * 0.04)

        # Subtle dark glass disc
        d.ellipse([cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r],
                  fill=(10, 18, 32, 230), outline=(0, 220, 255, 220), width=max(1, int(s * 0.025)))

        # Outer energy ring
        orbit_r = s * 0.33
        angles = [math.radians(60 * i - 90) for i in range(6)]
        sats = [(cx + orbit_r * math.cos(a), cy + orbit_r * math.sin(a)) for a in angles]

        line_w = max(2, int(s * 0.035))
        # Hub to satellites
        for sx, sy in sats:
            d.line([(cx, cy), (sx, sy)], fill=(0, 220, 255, 220), width=line_w)

        # Mesh perimeter links
        for i in range(len(sats)):
            p1 = sats[i]
            p2 = sats[(i + 1) % len(sats)]
            d.line([p1, p2], fill=(0, 180, 230, 140), width=max(1, int(line_w * 0.7)))

        # Draw satellites
        sat_r = max(3, int(s * 0.065))
        for sx, sy in sats:
            d.ellipse([sx - sat_r - 2, sy - sat_r - 2, sx + sat_r + 2, sy + sat_r + 2],
                      fill=(0, 220, 255, 60))
            d.ellipse([sx - sat_r, sy - sat_r, sx + sat_r, sy + sat_r],
                      fill=(240, 248, 255, 255), outline=(0, 220, 255, 255), width=max(1, int(s * 0.02)))

        # Center glowing core
        hub_r = max(5, int(s * 0.12))
        d.ellipse([cx - hub_r - 4, cy - hub_r - 4, cx + hub_r + 4, cy + hub_r + 4],
                  fill=(0, 255, 163, 70))
        d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
                  fill=(0, 255, 163, 255), outline=(255, 255, 255, 255), width=max(2, int(s * 0.03)))
        inner_r = max(2, int(hub_r * 0.45))
        d.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                  fill=(255, 255, 255, 255))

    return img


def main():
    images = [draw_icon_at_size(s) for s in SIZES]
    # The largest image saves the .ico containing all custom sizes
    largest = images[-1]
    largest.save(OUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print(f"Successfully generated {OUT} with sizes: {SIZES}")


if __name__ == "__main__":
    main()

