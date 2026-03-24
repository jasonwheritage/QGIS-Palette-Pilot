# -*- coding: utf-8 -*-
"""
Tests for palette_presets data and ordering (no QGIS runtime required).
"""

import re
import unittest

from palette_pilot.palette_presets import PRESET_HEX, PRESET_RAMP_DISPLAY_ORDER


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TestPalettePresets(unittest.TestCase):
    def test_display_order_matches_preset_keys(self):
        self.assertEqual(set(PRESET_RAMP_DISPLAY_ORDER), set(PRESET_HEX.keys()))

    def test_all_hex_values_valid(self):
        for name, hexes in PRESET_HEX.items():
            self.assertTrue(hexes, f"{name!r} should have at least one colour")
            for h in hexes:
                self.assertIsInstance(h, str, f"{name}: {h!r}")
                self.assertRegex(h, _HEX_RE, f"{name}: invalid hex {h!r}")


if __name__ == "__main__":
    unittest.main()
