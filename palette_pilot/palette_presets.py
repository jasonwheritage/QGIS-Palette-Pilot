# -*- coding: utf-8 -*-
"""
Named colour lists and helpers for Home-tab preset palettes and swatches.

QgsGradientColorRamp construction is deferred so tests can import ``PRESET_HEX``
without loading the full QGIS runtime.
"""

# Hex lists for “intent” palettes (single-symbol swatches and multi-stop ramps).
PRESET_HEX = {
    "Pastel": [
        "#fbb4c9",
        "#b3cde3",
        "#ccebc5",
        "#decbe4",
        "#fed9a6",
        "#ffffcc",
        "#e5d8bd",
        "#fddaec",
    ],
    "Neon": [
        "#ff00ff",
        "#00ffff",
        "#39ff14",
        "#ffff00",
        "#ff073a",
        "#ff6600",
        "#bf00ff",
        "#00ff88",
    ],
    "Greyscale": [
        "#000000",
        "#2d2d2d",
        "#5a5a5a",
        "#878787",
        "#b4b4b4",
        "#e0e0e0",
        "#ffffff",
    ],
    "High contrast": [
        "#000000",
        "#ffffff",
        "#e41a1c",
        "#377eb8",
        "#4daf4a",
        "#984ea3",
        "#ff7f00",
    ],
    "Earth tones": [
        "#4a3728",
        "#6b4423",
        "#8b6914",
        "#a67c52",
        "#5c7a3a",
        "#3d5c5c",
        "#8b7355",
        "#c2a878",
    ],
    "Warm": [
        "#67001f",
        "#b2182b",
        "#d6604d",
        "#f4a582",
        "#fddbc7",
        "#fee090",
        "#fdae61",
        "#f46d43",
    ],
    "Cool": [
        "#053061",
        "#2166ac",
        "#4393c3",
        "#92c5de",
        "#d1e5f0",
        "#542788",
        "#8073ac",
        "#ce1256",
    ],
}

PRESET_RAMP_DISPLAY_ORDER = [
    "Pastel",
    "Neon",
    "Greyscale",
    "High contrast",
    "Earth tones",
    "Warm",
    "Cool",
]


def preset_qcolors(name):
    """Return ``QColor`` instances for preset *name* (must exist in ``PRESET_HEX``)."""
    from qgis.PyQt.QtGui import QColor

    hexes = PRESET_HEX.get(name)
    if not hexes:
        return []
    out = []
    for h in hexes:
        c = QColor(h)
        if c.isValid():
            out.append(c)
    return out


def sample_ramp_colors(ramp, n=12):
    """
    Sample *n* colours evenly from *ramp*'s ``color(t)`` for ``t`` in ``[0, 1]``.

    Returns a list of valid ``QColor`` (may be shorter than *n* if samples are invalid).
    """
    if ramp is None or n < 1:
        return []
    from qgis.PyQt.QtGui import QColor

    out = []
    if n == 1:
        c = ramp.color(0.0)
        if c.isValid():
            out.append(c)
        return out
    for i in range(n):
        t = i / (n - 1)
        try:
            c = ramp.color(t)
        except Exception:
            continue
        if c.isValid():
            out.append(c)
    return out


def gradient_ramp_from_qcolors(colors):
    """
    Build a ``QgsGradientColorRamp`` with stops at evenly spaced *t* across *colors*.

    Returns ``None`` if QGIS types are unavailable or *colors* is empty.
    """
    if not colors:
        return None
    try:
        from qgis.core import QgsGradientColorRamp, QgsGradientStop
    except Exception:
        return None

    if len(colors) == 1:
        colors = [colors[0], colors[0]]
    stops = []
    for i, c in enumerate(colors):
        t = i / (len(colors) - 1) if len(colors) > 1 else 0.0
        stops.append(QgsGradientStop(t, c))
    ramp = QgsGradientColorRamp()
    try:
        ramp.setStops(stops)
    except Exception:
        return None
    return ramp
