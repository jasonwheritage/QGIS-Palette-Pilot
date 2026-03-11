# -*- coding: utf-8 -*-
"""
Palette Pilot dialog: target active layer, ramp selector, saved styles, saved colours, full layer style save/load.
Stays open until the user clicks Close. Keyboard: Up/Down to change ramp, Enter to Apply, Escape to Close.
"""

import os
import re

from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QKeySequence, QColor, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QShortcut,
    QCheckBox,
    QInputDialog,
)
from qgis.core import (
    QgsStyle,
    QgsSettings,
    QgsMessageLog,
    Qgis,
    QgsSingleSymbolRenderer,
    QgsApplication,
    QgsWkbTypes,
)
from qgis.gui import QgisInterface, QgsColorButton, QgsColorRampButton

# Key for persisting list of ramp names saved via "Save current as…" (plugin-owned; persists between sessions)
_SAVED_STYLES_KEY = "palette_pilot/saved_style_names"
# Key for persisting list of single-symbol colours (hex strings), saved via "Save current" in single-symbol section
_SAVED_SINGLE_COLOURS_KEY = "palette_pilot/saved_single_colours"

# Subfolder under QGIS settings dir for full layer style .qml files; organised by geometry type (point/line/polygon/other)
_FULL_STYLE_SUBDIR = "palette_pilot_full_styles"


def _get_full_style_directory():
    """Return the base directory for full layer styles. Creates it if missing."""
    base = QgsApplication.qgisSettingsDirPath()
    path = os.path.join(base, _FULL_STYLE_SUBDIR)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _geometry_type_folder(layer):
    """Return subfolder name for the layer's geometry type: point, line, polygon, or other."""
    if not layer or layer.type() != layer.VectorLayer:
        return "other"
    try:
        geom_type = layer.geometryType()
    except Exception:
        return "other"
    if geom_type == QgsWkbTypes.PointGeometry:
        return "point"
    if geom_type == QgsWkbTypes.LineGeometry:
        return "line"
    if geom_type == QgsWkbTypes.PolygonGeometry:
        return "polygon"
    return "other"


def _get_full_style_type_directory(layer):
    """Return the type-specific directory (e.g. base/point) for the layer. Creates it if missing."""
    base = _get_full_style_directory()
    folder = _geometry_type_folder(layer)
    path = os.path.join(base, folder)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _list_saved_full_styles(layer):
    """Return list of (display_name, absolute_path) for .qml files in the layer's type folder."""
    directory = _get_full_style_type_directory(layer)
    result = []
    try:
        for name in os.listdir(directory):
            if name.lower().endswith(".qml"):
                base_name = name[:-4]
                result.append((base_name, os.path.join(directory, name)))
    except OSError:
        pass
    result.sort(key=lambda x: x[0].lower())
    return result


def _sanitize_style_filename(name):
    """Return a safe filename (no path, no invalid chars)."""
    name = (name or "").strip() or "style"
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name[:200].strip() or "style"


def _get_builtin_ramp_names():
    """Return list of built-in colour ramp names from default style."""
    style = QgsStyle().defaultStyle()
    return style.colorRampNames() or []


def _get_ramp_by_name(name):
    """Return QgsColorRamp for the given name from default style, or None."""
    if not name:
        return None
    style = QgsStyle().defaultStyle()
    if name not in style.colorRampNames():
        return None
    return style.colorRamp(name)


def _get_saved_style_names():
    """Return list of ramp names saved via the plugin (from QSettings), that still exist in the style DB."""
    settings = QgsSettings()
    raw = settings.value(_SAVED_STYLES_KEY, "", type=str)
    if not raw:
        return []
    names = [n.strip() for n in raw.split("\n") if n.strip()]
    style = QgsStyle().defaultStyle()
    existing = set(style.colorRampNames() or [])
    return [n for n in names if n in existing]


def _add_saved_style_name(name):
    """Append a ramp name to the persisted saved-styles list if not already present."""
    settings = QgsSettings()
    raw = settings.value(_SAVED_STYLES_KEY, "", type=str)
    names = [n.strip() for n in raw.split("\n") if n.strip()]
    if name in names:
        return
    names.append(name)
    settings.setValue(_SAVED_STYLES_KEY, "\n".join(names))


# Saved single colours: one line per entry, "display_name|hex" (pipe separator). Legacy: line with no "|" is hex-only; display name then falls back to hex.
def _get_saved_single_colours():
    """Return list of (display_name, hex_str) saved via the plugin (from QSettings)."""
    settings = QgsSettings()
    raw = settings.value(_SAVED_SINGLE_COLOURS_KEY, "", type=str)
    if not raw:
        return []
    result = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            name, hex_str = line.split("|", 1)
            name, hex_str = name.strip(), hex_str.strip()
        else:
            hex_str = line
            name = hex_str
        if QColor(hex_str).isValid():
            result.append((name, hex_str))
    return result


def _add_saved_single_colour(display_name, hex_str):
    """Prepend a named colour to the persisted list (avoid duplicate hex)."""
    hex_str = hex_str.strip()
    if not QColor(hex_str).isValid():
        return
    display_name = (display_name or hex_str).strip() or hex_str
    entry = f"{display_name}|{hex_str}"
    settings = QgsSettings()
    raw = settings.value(_SAVED_SINGLE_COLOURS_KEY, "", type=str)
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    # Remove any existing entry with same hex
    lines = [ln for ln in lines if ln != hex_str and not ln.endswith("|" + hex_str)]
    lines.insert(0, entry)
    settings.setValue(_SAVED_SINGLE_COLOURS_KEY, "\n".join(lines))


class PaletteToolDialog(QDialog):
    """Dialog: apply a built-in colour ramp to the active layer. Stays open until Close."""

    def __init__(self, iface: QgisInterface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Palette Pilot")
        # Internal state for single-symbol and ramp auto-apply behaviour
        self._last_layer_id = None
        self._last_renderer_single = False
        self._last_full_style_geom_type = None
        self._suppress_ramp_auto_apply = True
        self._suppress_ramp_button_apply = False
        self._suppress_saved_style_apply = True
        self._suppress_saved_colour_apply = True
        self._suppress_full_style_apply = True
        self._build_ui()
        self._populate_ramps()
        self._populate_saved_styles()
        self._populate_saved_colours()
        self._populate_full_styles()
        self.ramp_combo.currentIndexChanged.connect(self._on_ramp_changed)
        self.saved_styles_combo.currentIndexChanged.connect(self._on_saved_style_changed)
        self.saved_colours_combo.currentIndexChanged.connect(self._on_saved_colour_changed)
        self.full_style_combo.currentIndexChanged.connect(self._on_full_style_changed)
        self.ramp_button.colorRampChanged.connect(self._on_ramp_button_changed)
        self._on_ramp_changed()
        self._suppress_ramp_auto_apply = False
        self._suppress_saved_style_apply = False
        self._suppress_saved_colour_apply = False
        self._suppress_full_style_apply = False
        # Refresh target layer label periodically while dialog is open (user may change active layer)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._update_target_label)
        self._refresh_timer.setInterval(1500)
        # Window-level shortcuts: Enter = Apply, Escape = Close (work even when combo has focus;
        # keyPressEvent never sees Enter because the focused combo consumes it)
        self._shortcut_apply_return = QShortcut(QKeySequence(Qt.Key_Return), self)
        self._shortcut_apply_return.activated.connect(self._on_apply)
        self._shortcut_apply_return.setContext(Qt.WindowShortcut)
        self._shortcut_apply_enter = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self._shortcut_apply_enter.activated.connect(self._on_apply)
        self._shortcut_apply_enter.setContext(Qt.WindowShortcut)
        self._shortcut_close = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self._shortcut_close.activated.connect(self.close)
        self._shortcut_close.setContext(Qt.WindowShortcut)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_target_label()
        self._populate_saved_styles()
        self._populate_saved_colours()
        self._populate_full_styles()
        self._refresh_timer.start()
        self.ramp_combo.setFocus(Qt.OtherFocusReason)

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Target layer (active layer only; read-only)
        target_group = QGroupBox("Target layer")
        target_layout = QVBoxLayout(target_group)
        self.target_label = QLabel("—")
        self.target_label.setStyleSheet("font-weight: bold;")
        target_layout.addWidget(self.target_label)
        layout.addWidget(target_group)

        # Colour ramp selection + preview
        ramp_group = QGroupBox("Colour ramp for classes")
        ramp_layout = QVBoxLayout(ramp_group)
        ramp_row = QHBoxLayout()
        self.ramp_combo = QComboBox()
        self.ramp_combo.setMinimumWidth(220)
        self.ramp_combo.setEditable(False)
        ramp_row.addWidget(self.ramp_combo)
        self.ramp_button = QgsColorRampButton()
        self.ramp_button.setMinimumWidth(36)
        ramp_row.addWidget(self.ramp_button)
        ramp_layout.addLayout(ramp_row)
        self.invert_check = QCheckBox("Invert ramp")
        ramp_layout.addWidget(self.invert_check)
        # Changing invert should behave like changing the ramp; for classed layers, auto-apply.
        self.invert_check.toggled.connect(self._on_ramp_changed)
        # Saved styles row (no separate group title; same section as ramp)
        saved_row = QHBoxLayout()
        self.saved_styles_combo = QComboBox()
        self.saved_styles_combo.setMinimumWidth(220)
        self.saved_styles_combo.setEditable(False)
        saved_row.addWidget(self.saved_styles_combo)
        self.save_current_btn = QPushButton("Save current as…")
        self.save_current_btn.clicked.connect(self._on_save_current_as)
        saved_row.addWidget(self.save_current_btn)
        ramp_layout.addLayout(saved_row)
        layout.addWidget(ramp_group)

        # Single symbol colour (only meaningful when renderer is single symbol)
        colour_group = QGroupBox("Single symbol colour")
        colour_layout = QVBoxLayout(colour_group)
        self.colour_button = QgsColorButton()
        self.colour_button.setText("Pick colour…")
        # Auto-apply new colour to single-symbol layers when the user confirms a pick
        self.colour_button.colorChanged.connect(self._on_single_colour_changed)
        colour_layout.addWidget(self.colour_button)
        # Saved colours: list of single-symbol colours saved via "Save current"; persists between sessions
        saved_colours_row = QHBoxLayout()
        self.saved_colours_combo = QComboBox()
        self.saved_colours_combo.setMinimumWidth(180)
        self.saved_colours_combo.setEditable(False)
        saved_colours_row.addWidget(self.saved_colours_combo)
        self.save_current_colour_btn = QPushButton("Save current as…")
        self.save_current_colour_btn.clicked.connect(self._on_save_current_colour_as)
        saved_colours_row.addWidget(self.save_current_colour_btn)
        colour_layout.addLayout(saved_colours_row)
        layout.addWidget(colour_group)
        self._ramp_group = ramp_group
        self._colour_group = colour_group

        # Full layer style: save/load complete style to .qml files in a dedicated directory
        full_style_group = QGroupBox("Full layer style")
        full_style_layout = QVBoxLayout(full_style_group)
        full_row1 = QHBoxLayout()
        self.full_style_combo = QComboBox()
        self.full_style_combo.setMinimumWidth(220)
        self.full_style_combo.setEditable(False)
        full_row1.addWidget(self.full_style_combo)
        self.save_full_style_btn = QPushButton("Save to file…")
        self.save_full_style_btn.clicked.connect(self._on_save_full_style_to_file)
        full_row1.addWidget(self.save_full_style_btn)
        full_style_layout.addLayout(full_row1)
        full_row2 = QHBoxLayout()
        self.copy_style_path_btn = QPushButton("Copy path")
        self.copy_style_path_btn.clicked.connect(self._on_copy_style_path)
        self.open_style_location_btn = QPushButton("Open location")
        self.open_style_location_btn.clicked.connect(self._on_open_style_location)
        full_row2.addWidget(self.copy_style_path_btn)
        full_row2.addWidget(self.open_style_location_btn)
        full_style_layout.addLayout(full_row2)
        layout.addWidget(full_style_group)
        self._full_style_group = full_style_group

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("apply_btn")
        self.apply_btn.clicked.connect(self._on_apply)
        # Obvious focus state: thick blue border and tinted background when focused
        self.apply_btn.setStyleSheet("""
            QPushButton#apply_btn:focus {
                border: 3px solid #0066cc;
                background-color: #cce5ff;
                font-weight: bold;
            }
            QPushButton#apply_btn:hover {
                border: 2px solid #0066cc;
            }
        """)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _populate_ramps(self):
        self.ramp_combo.clear()
        names = _get_builtin_ramp_names()
        self.ramp_combo.addItems(names)
        if names and "Spectral" in names:
            idx = names.index("Spectral")
            self.ramp_combo.setCurrentIndex(idx)

    def _populate_saved_styles(self):
        self.saved_styles_combo.clear()
        self.saved_styles_combo.addItem("—")  # placeholder so selecting the only real item triggers change
        names = _get_saved_style_names()
        self.saved_styles_combo.addItems(names)

    def _populate_saved_colours(self):
        self.saved_colours_combo.clear()
        self.saved_colours_combo.addItem("—")  # placeholder so selecting the only real item triggers change
        for display_name, hex_str in _get_saved_single_colours():
            self.saved_colours_combo.addItem(display_name, hex_str)

    def _populate_full_styles(self):
        self.full_style_combo.clear()
        self.full_style_combo.addItem("—")  # placeholder so selecting the only real item triggers change
        layer = self.iface.activeLayer()
        for display_name, path in _list_saved_full_styles(layer):
            self.full_style_combo.addItem(display_name, path)

    def _current_effective_ramp(self):
        """
        Return the ramp to use (base ramp, optionally inverted and cloned for safety),
        or None if it cannot be loaded.
        """
        name = self.ramp_combo.currentText().strip()
        base = _get_ramp_by_name(name)
        if not base:
            return None
        # Clone so we don't mutate ramps from the global style
        try:
            ramp = base.clone()
        except Exception:
            ramp = base
        if hasattr(self, "invert_check") and self.invert_check.isChecked():
            try:
                ramp.invert()
            except Exception:
                # If invert isn't supported, fall back to the original
                pass
        return ramp

    def _update_target_label(self):
        """Update the 'Target layer' label to the current active layer."""
        layer = self.iface.activeLayer()
        if not layer:
            self.target_label.setText("(No layer selected)")
            self._ramp_group.setEnabled(False)
            self._colour_group.setEnabled(False)
            self._full_style_group.setEnabled(False)
            self._last_layer_id = None
            self._last_renderer_single = False
            self._last_full_style_geom_type = None
            return
        if layer.type() != layer.VectorLayer:
            self.target_label.setText(f"{layer.name()} (not vector)")
            self._ramp_group.setEnabled(False)
            self._colour_group.setEnabled(False)
            self._full_style_group.setEnabled(False)
            self._last_layer_id = layer.id()
            self._last_renderer_single = False
            self._last_full_style_geom_type = None
            return

        # Vector layer: adjust UI based on renderer type
        self.target_label.setText(layer.name())
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            # Single symbol mode: enable colour picker and full style, disable ramp section
            self._colour_group.setEnabled(True)
            self._ramp_group.setEnabled(False)
            self._full_style_group.setEnabled(True)
            # Only sync the colour button from the symbol when entering single mode
            # for this layer (avoid overwriting a colour the user has just picked
            # but not yet applied).
            if not self._last_renderer_single or self._last_layer_id != layer.id():
                try:
                    sym = r.symbol()
                    if sym is not None:
                        self.colour_button.setColor(sym.color())
                except Exception:
                    pass
            self._last_renderer_single = True
            self._last_layer_id = layer.id()
        else:
            # Non-single (graduated/categorized/etc.): use ramp section and full style, disable single-colour picker
            self._ramp_group.setEnabled(True)
            self._colour_group.setEnabled(False)
            self._full_style_group.setEnabled(True)
            self._last_renderer_single = False
            self._last_layer_id = layer.id()

        # Refresh full-style list when geometry type changes so only relevant styles (point/line/polygon) are shown
        geom_type = _geometry_type_folder(layer)
        if geom_type != self._last_full_style_geom_type:
            self._last_full_style_geom_type = geom_type
            self._suppress_full_style_apply = True
            self._populate_full_styles()
            self._suppress_full_style_apply = False

    def _on_ramp_changed(self):
        ramp = self._current_effective_ramp()
        # Keep ramp button in sync with combo (avoid feedback when we apply from button)
        try:
            self._suppress_ramp_button_apply = True
            if ramp is not None:
                self.ramp_button.setColorRamp(ramp)
        except Exception:
            pass
        finally:
            self._suppress_ramp_button_apply = False
        # Auto-apply ramps for graduated/categorized layers when the user
        # cycles ramps, but skip during initialisation or when suppressed.
        if self._suppress_ramp_auto_apply:
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        # Do not auto-apply for single-symbol layers (they use the colour picker)
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            return
        ramp_to_apply = ramp
        if not ramp_to_apply:
            return
        from .palette_pilot import apply_ramp_to_layer

        if apply_ramp_to_layer(layer, ramp_to_apply):
            self._update_target_label()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass

    def _on_saved_style_changed(self):
        """Apply the selected saved style ramp to the active layer (live apply)."""
        if self._suppress_saved_style_apply:
            return
        if self.saved_styles_combo.currentIndex() == 0:
            return  # placeholder "—"
        name = self.saved_styles_combo.currentText().strip()
        if not name:
            return
        ramp = _get_ramp_by_name(name)
        if not ramp:
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            return
        from .palette_pilot import apply_ramp_to_layer

        if apply_ramp_to_layer(layer, ramp):
            self._update_target_label()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass

    def _on_save_current_as(self):
        """Save the current ramp (from ramp button) to the style DB and add to Saved styles list."""
        try:
            ramp = self.ramp_button.colorRamp()
        except Exception:
            ramp = None
        if not ramp:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "No colour ramp to save. Select or edit a ramp above first.",
            )
            return
        name, ok = QInputDialog.getText(
            self,
            "Palette Pilot",
            "Name for this ramp:",
            text="My ramp",
        )
        if not ok or not name or not name.strip():
            return
        name = name.strip()
        style = QgsStyle.defaultStyle()
        try:
            clone = ramp.clone()
        except Exception:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "Could not clone the colour ramp.",
            )
            return
        try:
            style.addColorRamp(name, clone, update=True)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                f"Could not save ramp: {e!s}",
            )
            return
        _add_saved_style_name(name)
        self._populate_ramps()
        self._suppress_saved_style_apply = True
        self._populate_saved_styles()
        self._suppress_saved_style_apply = False
        idx = self.saved_styles_combo.findText(name)
        if idx >= 0:
            self.saved_styles_combo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Saved "{name}" to Saved styles.',
            level=Qgis.Info,
            duration=3,
        )

    def _on_ramp_button_changed(self):
        """Apply ramp chosen from QgsColorRampButton (dropdown or dialog)."""
        if self._suppress_ramp_button_apply:
            return
        try:
            ramp = self.ramp_button.colorRamp()
        except Exception:
            return
        if ramp is None:
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            return
        from .palette_pilot import apply_ramp_to_layer

        if apply_ramp_to_layer(layer, ramp):
            self._update_target_label()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass

    def _on_saved_colour_changed(self):
        """Apply the selected saved colour to the active layer (live apply)."""
        if self._suppress_saved_colour_apply:
            return
        if self.saved_colours_combo.currentIndex() == 0:
            return  # placeholder "—"
        hex_str = self.saved_colours_combo.currentData(Qt.UserRole) or self.saved_colours_combo.currentText()
        if not hex_str or not isinstance(hex_str, str):
            hex_str = str(hex_str).strip() if hex_str else ""
        if not hex_str:
            return
        color = QColor(hex_str)
        if not color.isValid():
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        r = layer.renderer()
        if not isinstance(r, QgsSingleSymbolRenderer):
            return
        try:
            self.colour_button.setColor(color)
            sym = r.symbol().clone()
            sym.setColor(color)
            r.setSymbol(sym)
            layer.setRenderer(r)
            layer.triggerRepaint()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass
        except Exception:
            pass

    def _on_save_current_colour_as(self):
        """Save the current single-symbol colour to the plugin's saved colours list."""
        try:
            color = self.colour_button.color()
        except Exception:
            color = None
        if not color or not color.isValid():
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "No colour to save. Pick a colour first.",
            )
            return
        hex_str = color.name()
        name, ok = QInputDialog.getText(
            self,
            "Palette Pilot",
            "Name for this colour:",
            text=hex_str,
        )
        if not ok:
            return
        display_name = name.strip() if name else hex_str
        _add_saved_single_colour(display_name, hex_str)
        self._suppress_saved_colour_apply = True
        self._populate_saved_colours()
        self._suppress_saved_colour_apply = False
        idx = self.saved_colours_combo.findData(hex_str, Qt.UserRole)
        if idx < 0:
            idx = self.saved_colours_combo.findText(display_name)
        if idx >= 0:
            self.saved_colours_combo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            "Saved colour to Saved colours.",
            level=Qgis.Info,
            duration=3,
        )

    def _on_full_style_changed(self):
        """Load the selected full style (.qml) onto the active layer."""
        if self._suppress_full_style_apply:
            return
        if self.full_style_combo.currentIndex() == 0:
            return  # placeholder "—"
        path = self.full_style_combo.currentData(Qt.UserRole)
        if not path or not isinstance(path, str) or not os.path.isfile(path):
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        try:
            msg, ok = layer.loadNamedStyle(path)
            if not ok:
                self.iface.messageBar().pushMessage(
                    "Palette Pilot",
                    msg or "Could not load style.",
                    level=Qgis.Warning,
                    duration=5,
                )
                return
            layer.triggerRepaint()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                f'Loaded style onto "{layer.name()}".',
                level=Qgis.Info,
                duration=3,
            )
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                str(e),
                level=Qgis.Warning,
                duration=5,
            )

    def _on_save_full_style_to_file(self):
        """Save the current layer's full style to a .qml file via a save-file dialog."""
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "No vector layer selected. Select a layer first.",
            )
            return
        directory = _get_full_style_type_directory(layer)
        default_name = _sanitize_style_filename(layer.name()) + ".qml"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Palette Pilot — Save layer style as",
            os.path.join(directory, default_name),
            "QML style files (*.qml);;All files (*)",
            "QML style files (*.qml)",
        )
        if not path or not path.strip():
            return
        path = path.strip()
        if not path.lower().endswith(".qml"):
            path = path + ".qml"
        try:
            msg, ok = layer.saveNamedStyle(path)
            if not ok:
                QMessageBox.warning(
                    self,
                    "Palette Pilot",
                    msg or "Could not save style to file.",
                )
                return
        except Exception as e:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                f"Could not save style: {e!s}",
            )
            return
        self._suppress_full_style_apply = True
        self._populate_full_styles()
        self._suppress_full_style_apply = False
        idx = self.full_style_combo.findData(path, Qt.UserRole)
        if idx >= 0:
            self.full_style_combo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Saved style to {path}',
            level=Qgis.Info,
            duration=5,
        )

    def _on_copy_style_path(self):
        """Copy the full-style save directory path to the clipboard (type-specific folder when a layer is active)."""
        layer = self.iface.activeLayer()
        directory = _get_full_style_type_directory(layer) if layer and layer.type() == layer.VectorLayer else _get_full_style_directory()
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(directory)
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Path copied to clipboard.",
                level=Qgis.Info,
                duration=2,
            )

    def _on_open_style_location(self):
        """Open the full-style save directory in the system file manager (type-specific folder when a layer is active)."""
        layer = self.iface.activeLayer()
        directory = _get_full_style_type_directory(layer) if layer and layer.type() == layer.VectorLayer else _get_full_style_directory()
        url = QUrl.fromLocalFile(directory)
        if QDesktopServices.openUrl(url):
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Opened save location.",
                level=Qgis.Info,
                duration=2,
            )
        else:
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Could not open location. Use Copy path to open it manually.",
                level=Qgis.Warning,
                duration=4,
            )

    def _on_single_colour_changed(self, color):
        """
        Auto-apply single-symbol colour when the user confirms a pick in the colour dialog.
        This avoids needing a second Enter/Apply after closing the picker.
        """
        layer = self.iface.activeLayer()
        if not layer or layer.type() != layer.VectorLayer:
            return
        r = layer.renderer()
        if not isinstance(r, QgsSingleSymbolRenderer):
            return
        try:
            sym = r.symbol().clone()
            sym.setColor(color)
            r.setSymbol(sym)
            layer.setRenderer(r)
            layer.triggerRepaint()
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                f'Applied single symbol colour to "{layer.name()}".',
                level=Qgis.Info,
                duration=3,
            )
            QgsMessageLog.logMessage(
                f'Applied single symbol colour to "{layer.name()}".',
                "Palette Pilot",
                Qgis.Info,
            )
        except Exception:
            # Fall back silently; user can still click Apply if needed
            return

    def _on_apply(self):
        from .palette_pilot import apply_ramp_to_layer

        # Always use the current active layer
        layer = self.iface.activeLayer()
        if not layer:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "No layer selected. Select a vector layer in the Layers panel, then try again.",
            )
            return

        if layer.type() != layer.VectorLayer:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "The active layer is not a vector layer. Only vector layers with graduated or categorized symbology are supported.",
            )
            return

        # Single symbol: use the colour picker instead of a ramp
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            try:
                color = self.colour_button.color()
                sym = r.symbol().clone()
                sym.setColor(color)
                r.setSymbol(sym)
                layer.setRenderer(r)
                layer.triggerRepaint()
                try:
                    tree = self.iface.layerTreeView()
                    if tree is not None:
                        tree.refreshLayerSymbology(layer.id())
                except Exception:
                    pass
                try:
                    layer.emitStyleChanged()
                except Exception:
                    pass
                self.iface.messageBar().pushMessage(
                    "Palette Pilot",
                    f'Applied single symbol colour to "{layer.name()}".',
                    level=Qgis.Info,
                    duration=3,
                )
                QgsMessageLog.logMessage(
                    f'Applied single symbol colour to "{layer.name()}".',
                    "Palette Pilot",
                    Qgis.Info,
                )
            except Exception:
                QMessageBox.warning(
                    self,
                    "Palette Pilot",
                    "Could not apply single symbol colour.",
                )
            return

        ramp_name = self.ramp_combo.currentText().strip()
        if not ramp_name:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "Please select a colour ramp.",
            )
            return

        ramp = self._current_effective_ramp()
        if not ramp:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                f'Could not load colour ramp "{ramp_name}".',
            )
            return

        if apply_ramp_to_layer(layer, ramp):
            self._update_target_label()
            # Ensure the layer legend/symbology in the Layers panel and the styling panel
            # both reflect the new ramp
            try:
                tree = self.iface.layerTreeView()
                if tree is not None:
                    tree.refreshLayerSymbology(layer.id())
            except Exception:
                pass
            try:
                layer.emitStyleChanged()
            except Exception:
                pass
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                f'Applied "{ramp_name}" to "{layer.name()}".',
                level=Qgis.Info,
                duration=3,
            )
            QgsMessageLog.logMessage(
                f"Applied ramp '{ramp_name}' to \"{layer.name()}\".",
                "Palette Pilot",
                Qgis.Info,
            )
        else:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "The active layer does not use graduated or categorized symbology. "
                "Switch the layer to one of these in Layer Properties → Symbology, then try again.",
            )
        # Dialog stays open; user closes it with Close button
