#!/usr/bin/env python3
"""Render the home-screen icons.

iOS ignores SVG for apple-touch-icon and applies its own squircle mask, so these are
full-bleed PNGs with no transparency and no rounding of their own. Drawn at 4x and
downsampled so the arc and the tines stay clean at 60 px on a phone.

    python3 tools/make_icons.py
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "icons"
S = 4                                   # supersample

INK_TOP = (26, 41, 56)                  # slightly lifted navy, top
INK_BOT = (16, 26, 37)                  # deeper navy, bottom
TRACK   = (42, 58, 74)                  # unfilled part of the ring
AMBER   = (229, 167, 90)                # the app's accent
WHITE   = (247, 250, 252)

FILLED = 0.72                           # how much of the ring is drawn


def draw(px):
    n = px * S
    img = Image.new("RGB", (n, n), INK_BOT)
    d = ImageDraw.Draw(img)

    # vertical gradient ground
    for y in range(n):
        t = y / max(n - 1, 1)
        d.line([(0, y), (n, y)],
               fill=tuple(round(a + (b - a) * t) for a, b in zip(INK_TOP, INK_BOT)))

    cx = cy = n / 2
    r = n * 0.355                        # ring radius (centre line)
    w = n * 0.075                        # ring thickness
    box = [cx - r, cy - r, cx + r, cy + r]

    # full track, then the filled arc over it, starting at 12 o'clock
    d.arc(box, 0, 360, fill=TRACK, width=int(w))
    d.arc(box, -90, -90 + 360 * FILLED, fill=AMBER, width=int(w))

    # rounded cap where the arc starts, so it reads as a gauge not a broken circle
    cap = w / 2
    d.ellipse([cx - cap, cy - r - cap, cx + cap, cy - r + cap], fill=AMBER)

    # fork, centred inside the ring
    tine_w, tine_h = n * 0.030, n * 0.150
    gap = n * 0.052
    top = cy - n * 0.185
    for i in (-1, 0, 1):
        x = cx + i * gap
        d.rounded_rectangle([x - tine_w / 2, top, x + tine_w / 2, top + tine_h],
                            radius=tine_w / 2, fill=WHITE)
    # head joining the tines
    head_w = gap * 2 + tine_w
    d.rounded_rectangle([cx - head_w / 2, top + tine_h - n * 0.012,
                         cx + head_w / 2, top + tine_h + n * 0.055],
                        radius=n * 0.022, fill=WHITE)
    # handle
    hw = n * 0.042
    d.rounded_rectangle([cx - hw / 2, top + tine_h + n * 0.040,
                         cx + hw / 2, cy + n * 0.205],
                        radius=hw / 2, fill=WHITE)

    return img.resize((px, px), Image.LANCZOS)


def main():
    OUT.mkdir(exist_ok=True)
    for px, name in [(180, "apple-touch-icon.png"), (192, "icon-192.png"),
                     (512, "icon-512.png"), (32, "favicon-32.png")]:
        p = OUT / name
        draw(px).save(p, optimize=True)
        print(f"  {name:22} {px}x{px}  {p.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
