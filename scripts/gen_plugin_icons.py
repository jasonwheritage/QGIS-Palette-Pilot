#!/usr/bin/env python3
"""
Generate Palette Pilot plugin icons: rainbow gradient at 16, 24, 32, 48, 64 px.
Run from repo root: python scripts/gen_plugin_icons.py
Requires: pip install Pillow
"""
from __future__ import annotations

import colorsys
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Requires Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# Sizes required for QGIS: toolbox 16; toolbar 16, 24, 32, 48, 64
SIZES = (16, 24, 32, 48, 64)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(REPO_ROOT, "palette_pilot", "img")


def rainbow_gradient(size: int) -> Image.Image:
    """Draw a square image with horizontal rainbow gradient (full spectrum left to right)."""
    img = Image.new("RGB", (size, size))
    pix = img.load()
    for x in range(size):
        # Hue 0 = red, 1/6 = yellow, 1/3 = green, 1/2 = cyan, 2/3 = blue, 5/6 = magenta, 1 = red
        h = x / max(size - 1, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        rgb = (int(r * 255), int(g * 255), int(b * 255))
        for y in range(size):
            pix[x, y] = rgb
    return img


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    for s in SIZES:
        img = rainbow_gradient(s)
        path = os.path.join(IMG_DIR, f"icon_{s}.png")
        img.save(path)
        print(f"Wrote {path}")
    # Primary icon.png = 64x64 (metadata and default)
    path64 = os.path.join(IMG_DIR, "icon.png")
    rainbow_gradient(64).save(path64)
    print(f"Wrote {path64}")
    print("Done.")


if __name__ == "__main__":
    main()
