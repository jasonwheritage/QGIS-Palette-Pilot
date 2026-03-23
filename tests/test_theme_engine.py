# -*- coding: utf-8 -*-
"""
Unit tests for the theme_engine module.

These tests verify theme CRUD (save / load / list / delete), regex matching
logic, and style discovery helpers.  They run **outside** QGIS by mocking
the QGIS/Qt dependencies that theme_engine imports.
"""

import importlib
import json
import os
import sys
import tempfile
import types
import unittest


# ---------------------------------------------------------------------------
# Mock scaffolding (must be set up before importing theme_engine)
# ---------------------------------------------------------------------------

def _install_mocks(tmp_settings_dir):
    """
    Install minimal mocks for qgis.* and palette_pilot.qt_compat so that
    theme_engine can be imported and exercised outside QGIS.
    """
    # qgis.PyQt.QtCore.Qt (only UserRole needed by theme_editor_dialog, but
    # theme_engine itself doesn't use Qt directly)
    qt_mod = types.ModuleType("qgis.PyQt.QtCore")
    qt_cls = type("Qt", (), {"UserRole": 0x0100})
    qt_mod.Qt = qt_cls

    pyqt_mod = types.ModuleType("qgis.PyQt")
    pyqt_mod.QtCore = qt_mod

    qgis_pkg = types.ModuleType("qgis")
    qgis_pkg.PyQt = pyqt_mod

    # qgis.core with QgsApplication, QgsMessageLog, QgsProject
    core_mod = types.ModuleType("qgis.core")

    class _QgsApplication:
        _settings_dir = tmp_settings_dir

        @staticmethod
        def qgisSettingsDirPath():
            return _QgsApplication._settings_dir

    class _QgsMessageLog:
        messages = []

        @staticmethod
        def logMessage(msg, tag="", level=0):
            _QgsMessageLog.messages.append((msg, tag, level))

    # Fake project with configurable layers
    class _QgsProject:
        _instance = None
        _layers = {}

        @classmethod
        def instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def mapLayers(self):
            return dict(self._layers)

    core_mod.QgsApplication = _QgsApplication
    core_mod.QgsMessageLog = _QgsMessageLog
    core_mod.QgsProject = _QgsProject

    # Minimal Qgis namespace for qt_compat
    class _Qgis:
        Info = 0
        Warning = 1

    class _QgsWkbTypes:
        PointGeometry = 0
        LineGeometry = 1
        PolygonGeometry = 2

    class _QgsMapLayer:
        VectorLayer = 0

    core_mod.Qgis = _Qgis
    core_mod.QgsWkbTypes = _QgsWkbTypes
    core_mod.QgsMapLayer = _QgsMapLayer

    # Register in sys.modules
    sys.modules["qgis"] = qgis_pkg
    sys.modules["qgis.PyQt"] = pyqt_mod
    sys.modules["qgis.PyQt.QtCore"] = qt_mod
    sys.modules["qgis.core"] = core_mod

    # palette_pilot.qt_compat — provide the constants theme_engine needs
    pp_pkg = types.ModuleType("palette_pilot")
    pp_pkg.__path__ = [os.path.join(os.path.dirname(os.path.dirname(__file__)), "palette_pilot")]

    qt_compat = types.ModuleType("palette_pilot.qt_compat")
    qt_compat.VectorLayerType = 0
    qt_compat.PointGeometry = 0
    qt_compat.LineGeometry = 1
    qt_compat.PolygonGeometry = 2
    qt_compat.MessageInfo = 0
    qt_compat.MessageWarning = 1

    sys.modules["palette_pilot"] = pp_pkg
    sys.modules["palette_pilot.qt_compat"] = qt_compat

    return _QgsProject, _QgsApplication


# ---------------------------------------------------------------------------
# Fake layer used in matching tests
# ---------------------------------------------------------------------------

class _FakeLayer:
    """Minimal stand-in for QgsVectorLayer."""

    def __init__(self, name, geom_type_val, layer_type=0):
        self._name = name
        self._geom = geom_type_val
        self._type = layer_type
        self._loaded_style = None

    def name(self):
        return self._name

    def type(self):
        return self._type

    def geometryType(self):
        return self._geom

    def id(self):
        return f"layer_{self._name}"

    def loadNamedStyle(self, path):
        self._loaded_style = path
        return ("", True)

    def triggerRepaint(self):
        pass

    def emitStyleChanged(self):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestThemeEngine(unittest.TestCase):
    """Test theme_engine CRUD and matching outside QGIS."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="pp_test_")
        cls._QgsProject, cls._QgsApp = _install_mocks(cls._tmp)
        # Import theme_engine *after* mocks are installed
        import palette_pilot.theme_engine as te
        importlib.reload(te)
        cls.te = te

    def setUp(self):
        """Reset project layers + clean themes and styles dirs before each test."""
        self._QgsProject._layers = {}
        for subdir in ("palette_pilot_themes", "palette_pilot_full_styles"):
            d = os.path.join(self._tmp, subdir)
            if os.path.isdir(d):
                import shutil
                shutil.rmtree(d)

    # --- CRUD ---

    def test_save_and_load_theme(self):
        rules = [
            {"geometry_type": "point", "style_file": "/tmp/s.qml", "pattern": "stop"},
        ]
        self.te.save_theme("Test Theme", rules)
        data = self.te.load_theme("Test Theme")
        self.assertIsNotNone(data)
        self.assertEqual(data["name"], "Test Theme")
        self.assertEqual(len(data["rules"]), 1)
        self.assertEqual(data["rules"][0]["pattern"], "stop")

    def test_list_themes(self):
        self.te.save_theme("Alpha", [])
        self.te.save_theme("bravo", [])
        names = self.te.list_themes()
        self.assertEqual(names, ["Alpha", "bravo"])

    def test_delete_theme(self):
        self.te.save_theme("ToDelete", [{"geometry_type": "line", "style_file": "/x.qml", "pattern": "r"}])
        self.assertIn("ToDelete", self.te.list_themes())
        self.te.delete_theme("ToDelete")
        self.assertNotIn("ToDelete", self.te.list_themes())

    def test_load_nonexistent(self):
        self.assertIsNone(self.te.load_theme("NoSuchTheme"))

    # --- Style discovery ---

    def test_list_styles_for_geometry_empty(self):
        """When no .qml files exist, returns empty list."""
        styles = self.te.list_styles_for_geometry("point")
        self.assertEqual(styles, [])

    def test_list_styles_for_geometry(self):
        """Discovers .qml files in the right subdirectory."""
        point_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "point")
        os.makedirs(point_dir, exist_ok=True)
        open(os.path.join(point_dir, "Stations.qml"), "w").close()
        open(os.path.join(point_dir, "Stops.qml"), "w").close()
        open(os.path.join(point_dir, "readme.txt"), "w").close()  # not .qml
        styles = self.te.list_styles_for_geometry("point")
        names = [s[0] for s in styles]
        self.assertEqual(names, ["Stations", "Stops"])

    # --- Matching ---

    def test_matching_layers_for_rule(self):
        project = self._QgsProject.instance()
        project._layers = {
            "a": _FakeLayer("Bus Stops", 0),       # point
            "b": _FakeLayer("Rail Stations", 0),    # point
            "c": _FakeLayer("Rail Lines", 1),       # line
            "d": _FakeLayer("Boundaries", 2),       # polygon
        }
        rule = {"geometry_type": "point", "pattern": "(?i)station|stop", "style_file": "/s.qml"}
        matched = self.te.matching_layers_for_rule(rule, project)
        names = sorted(l.name() for l in matched)
        self.assertEqual(names, ["Bus Stops", "Rail Stations"])

    def test_matching_layers_invalid_regex(self):
        project = self._QgsProject.instance()
        project._layers = {"a": _FakeLayer("Test", 0)}
        rule = {"geometry_type": "point", "pattern": "[invalid", "style_file": "/s.qml"}
        matched = self.te.matching_layers_for_rule(rule, project)
        self.assertEqual(matched, [])

    def test_geometry_type_enforcement(self):
        """A line rule should not match a point layer, even if the name matches."""
        project = self._QgsProject.instance()
        project._layers = {"a": _FakeLayer("Roads", 0)}  # point
        rule = {"geometry_type": "line", "pattern": "Roads", "style_file": "/r.qml"}
        matched = self.te.matching_layers_for_rule(rule, project)
        self.assertEqual(matched, [])

    # --- Apply ---

    def test_apply_theme_to_single_layer(self):
        """apply_theme_to_single_layer applies the first matching rule."""
        # Create a real .qml file so the file-exists check passes
        point_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "point")
        os.makedirs(point_dir, exist_ok=True)
        qml_path = os.path.join(point_dir, "stops.qml")
        with open(qml_path, "w") as f:
            f.write("<qgis></qgis>")

        data = {
            "name": "test",
            "rules": [
                {"geometry_type": "point", "style_file": qml_path, "pattern": "(?i)stop"},
            ],
        }
        layer = _FakeLayer("Bus Stops", 0)
        result = self.te.apply_theme_to_single_layer(data, layer)
        self.assertTrue(result)
        self.assertEqual(layer._loaded_style, qml_path)

    def test_apply_theme_to_single_layer_no_match(self):
        data = {
            "name": "test",
            "rules": [
                {"geometry_type": "point", "style_file": "/missing.qml", "pattern": "nomatch"},
            ],
        }
        layer = _FakeLayer("Something Else", 0)
        result = self.te.apply_theme_to_single_layer(data, layer)
        self.assertFalse(result)

    def test_apply_theme_bulk(self):
        """apply_theme applies to all matching layers across rules."""
        point_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "point")
        os.makedirs(point_dir, exist_ok=True)
        qml = os.path.join(point_dir, "s.qml")
        with open(qml, "w") as f:
            f.write("<qgis></qgis>")

        line_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "line")
        os.makedirs(line_dir, exist_ok=True)
        qml2 = os.path.join(line_dir, "r.qml")
        with open(qml2, "w") as f:
            f.write("<qgis></qgis>")

        project = self._QgsProject.instance()
        project._layers = {
            "a": _FakeLayer("Stops", 0),
            "b": _FakeLayer("Routes", 1),
            "c": _FakeLayer("Zones", 2),
        }
        data = {
            "name": "multi",
            "rules": [
                {"geometry_type": "point", "style_file": qml, "pattern": "Stop"},
                {"geometry_type": "line", "style_file": qml2, "pattern": "Route"},
            ],
        }
        styled, warnings = self.te.apply_theme(data, project)
        self.assertEqual(styled, 2)
        self.assertEqual(warnings, [])

    def test_apply_theme_skips_disabled_rules(self):
        point_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "point")
        os.makedirs(point_dir, exist_ok=True)
        qml = os.path.join(point_dir, "a.qml")
        with open(qml, "w") as f:
            f.write("<qgis></qgis>")

        project = self._QgsProject.instance()
        project._layers = {"a": _FakeLayer("Stops", 0)}
        data = {
            "name": "t",
            "rules": [
                {
                    "geometry_type": "point",
                    "style_file": qml,
                    "pattern": "Stop",
                    "enabled": False,
                },
            ],
        }
        styled, warnings = self.te.apply_theme(data, project)
        self.assertEqual(styled, 0)
        self.assertEqual(warnings, [])

    def test_apply_theme_to_single_layer_skips_disabled_rule(self):
        point_dir = os.path.join(self._tmp, "palette_pilot_full_styles", "point")
        os.makedirs(point_dir, exist_ok=True)
        qml_path = os.path.join(point_dir, "stops.qml")
        with open(qml_path, "w") as f:
            f.write("<qgis></qgis>")

        data = {
            "name": "test",
            "rules": [
                {
                    "geometry_type": "point",
                    "style_file": qml_path,
                    "pattern": "(?i)stop",
                    "enabled": False,
                },
            ],
        }
        layer = _FakeLayer("Bus Stops", 0)
        result = self.te.apply_theme_to_single_layer(data, layer)
        self.assertFalse(result)
        self.assertIsNone(layer._loaded_style)


if __name__ == "__main__":
    unittest.main()
