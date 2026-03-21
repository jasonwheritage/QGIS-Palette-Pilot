# -*- coding: utf-8 -*-
"""
Qt5 / Qt6 and QGIS 3 / QGIS 4 compatibility shim for Palette Pilot.

PyQt6 (used by QGIS 3.44+ Qt6 builds and QGIS 4.0) moved all enum
members into scoped enums.  For example ``Qt.NoFocus`` became
``Qt.FocusPolicy.NoFocus``.  QGIS 4 also moved several core enums
(``QgsWkbTypes``, ``Qgis.Info``, ``QgsMapLayer.VectorLayer``, …) into
scoped ``Qgis.*`` namespaces and removed the old names.

This module resolves the correct constant at import time so the rest of
the plugin works on both Qt5/Qt6 and QGIS 3/4 without littering the
code with try/except blocks.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import Qgis

# ---------------------------------------------------------------------------
# Qt enum compatibility
# ---------------------------------------------------------------------------

# -- Focus -------------------------------------------------------------------
try:
    NoFocus = Qt.FocusPolicy.NoFocus
except AttributeError:
    NoFocus = Qt.NoFocus

# -- Focus reason -------------------------------------------------------------
try:
    OtherFocusReason = Qt.FocusReason.OtherFocusReason
except AttributeError:
    OtherFocusReason = Qt.OtherFocusReason

# -- Keys ---------------------------------------------------------------------
try:
    Key_Return = Qt.Key.Key_Return
except AttributeError:
    Key_Return = Qt.Key_Return

try:
    Key_Enter = Qt.Key.Key_Enter
except AttributeError:
    Key_Enter = Qt.Key_Enter

try:
    Key_Escape = Qt.Key.Key_Escape
except AttributeError:
    Key_Escape = Qt.Key_Escape

# -- Shortcut context ---------------------------------------------------------
try:
    WindowShortcut = Qt.ShortcutContext.WindowShortcut
except AttributeError:
    WindowShortcut = Qt.WindowShortcut

# -- Item data role ------------------------------------------------------------
try:
    UserRole = Qt.ItemDataRole.UserRole
except AttributeError:
    UserRole = Qt.UserRole

# ---------------------------------------------------------------------------
# QGIS API compatibility (QGIS 3 → 4)
# ---------------------------------------------------------------------------

# -- Geometry types (QgsWkbTypes removed in QGIS 4) --------------------------
try:
    PointGeometry = Qgis.GeometryType.Point
    LineGeometry = Qgis.GeometryType.Line
    PolygonGeometry = Qgis.GeometryType.Polygon
except AttributeError:
    from qgis.core import QgsWkbTypes
    PointGeometry = QgsWkbTypes.PointGeometry
    LineGeometry = QgsWkbTypes.LineGeometry
    PolygonGeometry = QgsWkbTypes.PolygonGeometry

# -- Message levels (Qgis.Info → Qgis.MessageLevel.Info in QGIS 4) -----------
try:
    MessageInfo = Qgis.MessageLevel.Info
    MessageWarning = Qgis.MessageLevel.Warning
except AttributeError:
    MessageInfo = Qgis.Info
    MessageWarning = Qgis.Warning

# -- Layer type (QgsMapLayer.VectorLayer → Qgis.LayerType.Vector in QGIS 4) --
try:
    VectorLayerType = Qgis.LayerType.Vector
except AttributeError:
    from qgis.core import QgsMapLayer
    VectorLayerType = QgsMapLayer.VectorLayer
