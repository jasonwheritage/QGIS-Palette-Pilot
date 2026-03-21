# -*- coding: utf-8 -*-
"""
Theme engine for Palette Pilot.

A *theme* is a JSON file stored in ``palette_pilot_themes/`` under the QGIS
settings directory.  Each theme contains an ordered list of *rules*.  A rule
pairs a ``.qml`` style file (from ``palette_pilot_full_styles/<geom>/``) with
a Python regex pattern that is matched against layer names.

Schema (``<name>.json``)::

    {
      "name": "My Theme",
      "rules": [
        {
          "geometry_type": "point",
          "style_file": "/absolute/path/to/style.qml",
          "pattern": "(?i)station|stop"
        },
        ...
      ]
    }

Geometry types are ``"point"``, ``"line"``, ``"polygon"``.  A rule only
applies to vector layers whose geometry type matches *and* whose name
matches the regex pattern (``re.search``, case-insensitive by default is
up to the user's pattern).
"""

import json
import os
import re as _re

from qgis.core import QgsApplication, QgsMessageLog, QgsProject

from . import qt_compat

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THEMES_SUBDIR = "palette_pilot_themes"
_FULL_STYLE_SUBDIR = "palette_pilot_full_styles"


def _themes_directory():
    """Return (and create) the directory that holds theme JSON files."""
    base = QgsApplication.qgisSettingsDirPath()
    path = os.path.join(base, _THEMES_SUBDIR)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _full_styles_base():
    """Return the root of the per-geometry-type style directories."""
    base = QgsApplication.qgisSettingsDirPath()
    return os.path.join(base, _FULL_STYLE_SUBDIR)


# ---------------------------------------------------------------------------
# Style discovery
# ---------------------------------------------------------------------------

_GEOM_TYPES = ("point", "line", "polygon")


def list_styles_for_geometry(geom_type):
    """
    Return ``[(display_name, absolute_path), ...]`` of ``.qml`` files in
    ``palette_pilot_full_styles/<geom_type>/``.
    """
    base = _full_styles_base()
    directory = os.path.join(base, geom_type)
    result = []
    try:
        for name in os.listdir(directory):
            if name.lower().endswith(".qml"):
                result.append((name[:-4], os.path.join(directory, name)))
    except OSError:
        pass
    result.sort(key=lambda x: x[0].lower())
    return result


# ---------------------------------------------------------------------------
# Theme CRUD
# ---------------------------------------------------------------------------

def list_themes():
    """Return sorted list of theme names (file stems) from the themes directory."""
    directory = _themes_directory()
    names = []
    try:
        for fname in os.listdir(directory):
            if fname.lower().endswith(".json"):
                names.append(fname[:-5])
    except OSError:
        pass
    names.sort(key=str.lower)
    return names


def load_theme(name):
    """
    Load and return a theme dict, or ``None`` if not found / invalid.

    Returns ``{"name": str, "rules": [{"geometry_type", "style_file", "pattern"}, ...]}``.
    """
    path = os.path.join(_themes_directory(), name + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "rules" not in data:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def save_theme(name, rules):
    """
    Persist a theme.

    *name* – display name (also used as the file stem after sanitising).
    *rules* – list of dicts ``{"geometry_type", "style_file", "pattern"}``.
    """
    safe = _re.sub(r'[<>:"/\\|?*]', "_", name.strip())[:200] or "theme"
    path = os.path.join(_themes_directory(), safe + ".json")
    data = {"name": name, "rules": rules}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def delete_theme(name):
    """Delete the JSON file for *name*.  Silently succeeds if missing."""
    safe = _re.sub(r'[<>:"/\\|?*]', "_", name.strip())[:200] or "theme"
    path = os.path.join(_themes_directory(), safe + ".json")
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Layer helpers
# ---------------------------------------------------------------------------

def _geometry_type_key(layer):
    """Return ``"point"``, ``"line"``, ``"polygon"`` or ``None``."""
    if not layer or layer.type() != qt_compat.VectorLayerType:
        return None
    try:
        g = layer.geometryType()
    except Exception:
        return None
    if g == qt_compat.PointGeometry:
        return "point"
    if g == qt_compat.LineGeometry:
        return "line"
    if g == qt_compat.PolygonGeometry:
        return "polygon"
    return None


def matching_layers_for_rule(rule, project=None):
    """
    Return list of ``QgsVectorLayer`` from the project that match *rule*.

    A layer matches when:
    1. Its geometry type equals ``rule["geometry_type"]``.
    2. Its name matches ``rule["pattern"]`` via ``re.search``.
    """
    if project is None:
        project = QgsProject.instance()
    geom = rule.get("geometry_type", "")
    pattern = rule.get("pattern", "")
    if not pattern:
        return []
    try:
        rx = _re.compile(pattern)
    except _re.error:
        return []
    result = []
    for layer in project.mapLayers().values():
        if layer.type() != qt_compat.VectorLayerType:
            continue
        if _geometry_type_key(layer) != geom:
            continue
        if rx.search(layer.name()):
            result.append(layer)
    return result


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_theme(theme_data, project=None, iface=None):
    """
    Apply *theme_data* to all matching layers in the project.

    Returns ``(styled_count, skipped_messages)`` where *skipped_messages*
    is a list of warning strings for rules that couldn't be applied.
    """
    if project is None:
        project = QgsProject.instance()
    rules = theme_data.get("rules", [])
    styled = 0
    warnings = []
    for rule in rules:
        style_path = rule.get("style_file", "")
        if not style_path or not os.path.isfile(style_path):
            warnings.append(f'Style file not found: {style_path}')
            continue
        layers = matching_layers_for_rule(rule, project)
        for layer in layers:
            try:
                msg, ok = layer.loadNamedStyle(style_path)
                if not ok:
                    warnings.append(f'{layer.name()}: {msg}')
                    continue
                layer.triggerRepaint()
                if iface:
                    try:
                        tree = iface.layerTreeView()
                        if tree is not None:
                            tree.refreshLayerSymbology(layer.id())
                    except Exception:
                        pass
                try:
                    layer.emitStyleChanged()
                except Exception:
                    pass
                styled += 1
            except Exception as exc:
                warnings.append(f'{layer.name()}: {exc}')
    return styled, warnings


def apply_theme_to_single_layer(theme_data, layer, iface=None):
    """
    Apply the first matching rule from *theme_data* to *layer*.

    Returns True if a rule matched and was applied, False otherwise.
    """
    geom = _geometry_type_key(layer)
    if geom is None:
        return False
    for rule in theme_data.get("rules", []):
        if rule.get("geometry_type") != geom:
            continue
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            rx = _re.compile(pattern)
        except _re.error:
            continue
        if not rx.search(layer.name()):
            continue
        style_path = rule.get("style_file", "")
        if not style_path or not os.path.isfile(style_path):
            continue
        try:
            msg, ok = layer.loadNamedStyle(style_path)
            if not ok:
                continue
            layer.triggerRepaint()
            if iface:
                try:
                    tree = iface.layerTreeView()
                    if tree is not None:
                        tree.refreshLayerSymbology(layer.id())
                except Exception:
                    pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass
            return True
        except Exception:
            continue
    return False
