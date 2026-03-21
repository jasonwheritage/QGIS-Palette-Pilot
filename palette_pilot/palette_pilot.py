# -*- coding: utf-8 -*-
"""
Palette Pilot — style vector layers in a snap: ramps, saved colours, full layer styles.
Supports graduated, categorized, and single-symbol symbology.
"""

import os

from qgis.PyQt.QtCore import QCoreApplication, QSize
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsStyle
from qgis.gui import QgisInterface

from . import qt_compat

# Default ramp name for the M2 stub (must exist in QgsStyle default ramps)
_DEFAULT_RAMP_NAME = "Spectral"


def _get_default_ramp():
    """Return (ramp, ramp_name) from the default style, or (None, None) if none available."""
    style = QgsStyle().defaultStyle()
    names = style.colorRampNames()
    if _DEFAULT_RAMP_NAME in names:
        return style.colorRamp(_DEFAULT_RAMP_NAME), _DEFAULT_RAMP_NAME
    if names:
        name = names[0]
        return style.colorRamp(name), name
    return None, None


def _clone_ramp(ramp):
    """Return a clone of the ramp so the renderer owns its copy (avoids crashes with shared style ramps)."""
    if ramp is None:
        return None
    try:
        return ramp.clone()
    except Exception:
        return ramp


def _apply_ramp_to_categorized(renderer, ramp, layer) -> bool:
    """
    Apply ramp to categorized renderer by updating each category symbol color from the ramp.
    Uses new symbols + updateCategorySymbol() to avoid crashes from modifying shared
    category symbols or from updateColorRamp() on existing categorized layers.
    """
    from qgis.core import QgsSymbol

    categories = renderer.categories()
    n = len(categories)
    if n == 0:
        return False

    ramp_clone = _clone_ramp(ramp)
    if ramp_clone is None:
        return False

    for i in range(n):
        # Sample ramp at position i / (n-1) for n>1, else 0
        t = i / (n - 1) if n > 1 else 0.0
        color = ramp_clone.color(t)
        if not color.isValid():
            continue
        # Create a new symbol (do not use category's symbol() - modifying it can crash QGIS)
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        if symbol is None:
            continue
        symbol.setColor(color)
        renderer.updateCategorySymbol(i, symbol)
    return True


def apply_ramp_to_layer(layer, ramp) -> bool:
    """
    Apply a QgsColorRamp to the current layer's renderer if it is graduated or categorized.
    Returns True if applied, False otherwise (wrong layer type or renderer).
    """
    if not layer or not ramp:
        return False
    if layer.type() != qt_compat.VectorLayerType:
        return False

    renderer = layer.renderer()
    if renderer is None:
        return False

    from qgis.core import (
        QgsGraduatedSymbolRenderer,
        QgsCategorizedSymbolRenderer,
    )

    if isinstance(renderer, QgsGraduatedSymbolRenderer):
        ramp_clone = _clone_ramp(ramp)
        if ramp_clone is None:
            return False
        renderer.setSourceColorRamp(ramp_clone)
        renderer.updateColorRamp(ramp_clone)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True

    if isinstance(renderer, QgsCategorizedSymbolRenderer):
        # Apply by updating each category symbol from the ramp (avoids crash from
        # setSourceColorRamp/updateColorRamp on existing categorized layers)
        if _apply_ramp_to_categorized(renderer, ramp, layer):
            layer.setRenderer(renderer)
            layer.triggerRepaint()
            return True
        return False

    return False


class ColourPaletteToolPlugin:
    """QGIS plugin: dialog to select layers and a built-in colour ramp, then apply."""

    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(
            QCoreApplication.translate("ColourPaletteToolPlugin", "Palette Pilot"),
            self.iface.mainWindow(),
        )
        self.action.setObjectName("colourPaletteToolOpen")
        plugin_dir = os.path.dirname(__file__)
        img_dir = os.path.join(plugin_dir, "img")
        # Use multi-size icon so QGIS toolbar/toolbox get the right resolution (16–64 px)
        icon = QIcon()
        for size in (16, 24, 32, 48, 64):
            path = os.path.join(img_dir, f"icon_{size}.png")
            if os.path.isfile(path):
                icon.addFile(path, QSize(size, size))
        if icon.isNull():
            path = os.path.join(img_dir, "icon.png")
            if os.path.isfile(path):
                icon.addFile(path)
        if not icon.isNull():
            self.action.setIcon(icon)
        self.action.setWhatsThis(
            QCoreApplication.translate(
                "ColourPaletteToolPlugin",
                "Open Palette Pilot to apply colour ramps, saved colours, or full layer styles to the active vector layer.",
            )
        )
        self.action.setStatusTip(
            QCoreApplication.translate("ColourPaletteToolPlugin", "Open Palette Pilot")
        )
        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        menu_text = QCoreApplication.translate("ColourPaletteToolPlugin", "&Palette Pilot")
        self.iface.addPluginToMenu(menu_text, self.action)

    def unload(self):
        menu_text = QCoreApplication.translate("ColourPaletteToolPlugin", "&Palette Pilot")
        self.iface.removePluginMenu(menu_text, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dialog:
            self.dialog.close()

    def run(self):
        from .palette_dialog import PaletteToolDialog

        if self.dialog is None:
            self.dialog = PaletteToolDialog(self.iface, self.iface.mainWindow())
        self.dialog._update_target_label()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
