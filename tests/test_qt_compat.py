# -*- coding: utf-8 -*-
"""
Unit tests for the qt_compat module.

These tests verify that qt_compat resolves Qt enum constants correctly
for both Qt5-style (unscoped) and Qt6-style (scoped) enum access,
and that QGIS 3 / QGIS 4 API compatibility constants are resolved
correctly.

Since the tests run outside QGIS, we mock qgis.PyQt.QtCore.Qt and
qgis.core.Qgis / qgis.core.QgsWkbTypes / qgis.core.QgsMapLayer.
"""

import importlib
import sys
import types
import unittest


def _make_qt5_mock():
    """Create a mock Qt namespace with Qt5-style (unscoped) enums."""
    qt = type("Qt", (), {
        "NoFocus": 0,
        "OtherFocusReason": 7,
        "Key_Return": 0x01000004,
        "Key_Enter": 0x01000005,
        "Key_Escape": 0x01000000,
        "WindowShortcut": 0,
        "UserRole": 0x0100,
    })
    return qt


def _make_qt6_mock():
    """Create a mock Qt namespace with Qt6-style (scoped) enums only."""
    qt = type("Qt", (), {
        "FocusPolicy": type("FocusPolicy", (), {"NoFocus": 0}),
        "FocusReason": type("FocusReason", (), {"OtherFocusReason": 7}),
        "Key": type("Key", (), {
            "Key_Return": 0x01000004,
            "Key_Enter": 0x01000005,
            "Key_Escape": 0x01000000,
        }),
        "ShortcutContext": type("ShortcutContext", (), {"WindowShortcut": 0}),
        "ItemDataRole": type("ItemDataRole", (), {"UserRole": 0x0100}),
    })
    return qt


def _make_qgis3_mock():
    """Create a mock Qgis/QgsWkbTypes/QgsMapLayer with QGIS 3-style (unscoped) enums."""
    qgis_cls = type("Qgis", (), {
        "Info": 0,
        "Warning": 1,
    })
    wkb = type("QgsWkbTypes", (), {
        "PointGeometry": 0,
        "LineGeometry": 1,
        "PolygonGeometry": 2,
    })
    maplayer = type("QgsMapLayer", (), {
        "VectorLayer": 0,
    })
    return qgis_cls, wkb, maplayer


def _make_qgis4_mock():
    """Create a mock Qgis with QGIS 4-style (scoped) enums only."""
    qgis_cls = type("Qgis", (), {
        "MessageLevel": type("MessageLevel", (), {"Info": 0, "Warning": 1}),
        "GeometryType": type("GeometryType", (), {"Point": 0, "Line": 1, "Polygon": 2}),
        "LayerType": type("LayerType", (), {"Vector": 0}),
    })
    return qgis_cls


def _install_qgis_mock(qt_mock, qgis_cls, wkb_types=None, maplayer=None):
    """Install mock qgis.PyQt.QtCore and qgis.core modules into sys.modules."""
    qgis = types.ModuleType("qgis")
    pyqt = types.ModuleType("qgis.PyQt")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qtcore.Qt = qt_mock
    qgis.PyQt = pyqt
    pyqt.QtCore = qtcore

    core = types.ModuleType("qgis.core")
    core.Qgis = qgis_cls
    if wkb_types is not None:
        core.QgsWkbTypes = wkb_types
    if maplayer is not None:
        core.QgsMapLayer = maplayer
    qgis.core = core

    sys.modules["qgis"] = qgis
    sys.modules["qgis.PyQt"] = pyqt
    sys.modules["qgis.PyQt.QtCore"] = qtcore
    sys.modules["qgis.core"] = core


def _cleanup_modules():
    """Remove mock qgis modules and previously-imported qt_compat."""
    for key in list(sys.modules):
        if key.startswith("qgis") or key.endswith("qt_compat"):
            del sys.modules[key]


class TestQtCompatQt5(unittest.TestCase):
    """Verify qt_compat resolves constants on a Qt5-like environment."""

    def setUp(self):
        _cleanup_modules()
        qgis_cls, wkb, maplayer = _make_qgis3_mock()
        _install_qgis_mock(_make_qt5_mock(), qgis_cls, wkb, maplayer)

    def tearDown(self):
        _cleanup_modules()

    def test_qt5_enum_values(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.NoFocus, 0)
        self.assertEqual(qt_compat.OtherFocusReason, 7)
        self.assertEqual(qt_compat.Key_Return, 0x01000004)
        self.assertEqual(qt_compat.Key_Enter, 0x01000005)
        self.assertEqual(qt_compat.Key_Escape, 0x01000000)
        self.assertEqual(qt_compat.WindowShortcut, 0)
        self.assertEqual(qt_compat.UserRole, 0x0100)


class TestQtCompatQt6(unittest.TestCase):
    """Verify qt_compat resolves constants on a Qt6-like environment."""

    def setUp(self):
        _cleanup_modules()
        qgis4 = _make_qgis4_mock()
        _install_qgis_mock(_make_qt6_mock(), qgis4)

    def tearDown(self):
        _cleanup_modules()

    def test_qt6_enum_values(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.NoFocus, 0)
        self.assertEqual(qt_compat.OtherFocusReason, 7)
        self.assertEqual(qt_compat.Key_Return, 0x01000004)
        self.assertEqual(qt_compat.Key_Enter, 0x01000005)
        self.assertEqual(qt_compat.Key_Escape, 0x01000000)
        self.assertEqual(qt_compat.WindowShortcut, 0)
        self.assertEqual(qt_compat.UserRole, 0x0100)


class TestQgisCompatQgis3(unittest.TestCase):
    """Verify qt_compat resolves QGIS 3-style API constants."""

    def setUp(self):
        _cleanup_modules()
        qgis_cls, wkb, maplayer = _make_qgis3_mock()
        _install_qgis_mock(_make_qt5_mock(), qgis_cls, wkb, maplayer)

    def tearDown(self):
        _cleanup_modules()

    def test_geometry_types(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.PointGeometry, 0)
        self.assertEqual(qt_compat.LineGeometry, 1)
        self.assertEqual(qt_compat.PolygonGeometry, 2)

    def test_message_levels(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.MessageInfo, 0)
        self.assertEqual(qt_compat.MessageWarning, 1)

    def test_layer_type(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.VectorLayerType, 0)


class TestQgisCompatQgis4(unittest.TestCase):
    """Verify qt_compat resolves QGIS 4-style API constants."""

    def setUp(self):
        _cleanup_modules()
        qgis4 = _make_qgis4_mock()
        _install_qgis_mock(_make_qt6_mock(), qgis4)

    def tearDown(self):
        _cleanup_modules()

    def test_geometry_types(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.PointGeometry, 0)
        self.assertEqual(qt_compat.LineGeometry, 1)
        self.assertEqual(qt_compat.PolygonGeometry, 2)

    def test_message_levels(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.MessageInfo, 0)
        self.assertEqual(qt_compat.MessageWarning, 1)

    def test_layer_type(self):
        from palette_pilot import qt_compat

        self.assertEqual(qt_compat.VectorLayerType, 0)


if __name__ == "__main__":
    unittest.main()
