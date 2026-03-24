# -*- coding: utf-8 -*-
"""
Palette Pilot dialog: target active layer, ramp selector, saved styles, saved colours, full layer style save/load.
Stays open until the user clicks Close. Keyboard: Up/Down to change ramp, Enter to Apply, Escape to Close.
"""

import os
import re
from functools import partial

from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QKeySequence, QColor, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QShortcut,
    QCheckBox,
    QInputDialog,
    QTabWidget,
    QWidget,
)
from qgis.core import (
    QgsStyle,
    QgsSettings,
    QgsMessageLog,
    QgsSingleSymbolRenderer,
    QgsApplication,
    QgsProject,
)
from qgis.gui import QgisInterface, QgsColorButton, QgsColorRampButton

from . import qt_compat
from . import palette_presets
from . import theme_engine
from .theme_editor_dialog import ThemeEditorDialog
from .palette_pilot import apply_ramp_to_layer, _clone_ramp

# Key for persisting list of ramp names saved via "Save current as…" (plugin-owned; persists between sessions)
_SAVED_STYLES_KEY = "palette_pilot/saved_style_names"
# Key for persisting list of single-symbol colours (hex strings), saved via "Save current" in single-symbol section
_SAVED_SINGLE_COLOURS_KEY = "palette_pilot/saved_single_colours"

# Subfolder under QGIS settings dir for full layer style .qml files; organised by geometry type (point/line/polygon/other)
_FULL_STYLE_SUBDIR = "palette_pilot_full_styles"

# Theme persistence keys
_THEME_ENABLED_KEY = "palette_pilot/theme_enabled"
_THEME_LAST_KEY = "palette_pilot/last_theme"

# Home tab ramp group: title/tooltip depend on whether the layer is single-symbol
_RAMP_GROUP_TITLE_CLASSES = "Colour ramp for classes"
_RAMP_GROUP_TITLE_PREVIEW = "Colour ramp preview (for swatches)"
_RAMP_GROUP_TIP_CLASSES = (
    "Applies to graduated or categorized layers when you change the ramp or click Apply."
)
_RAMP_GROUP_TIP_PREVIEW = (
    "This layer uses a single symbol. The ramp here only drives the quick swatches "
    "below — it does not change the map. Pick a ramp or edit it to refresh swatches."
)


def _get_theme_enabled():
    """Return True if the theme toggle was last left enabled."""
    settings = QgsSettings()
    return settings.value(_THEME_ENABLED_KEY, False, type=bool)


def _set_theme_enabled(enabled):
    """Persist the theme toggle state."""
    QgsSettings().setValue(_THEME_ENABLED_KEY, enabled)


def _get_last_theme():
    """Return the name of the last-applied theme, or empty string."""
    return QgsSettings().value(_THEME_LAST_KEY, "", type=str)


def _set_last_theme(name):
    """Persist the last-applied theme name."""
    QgsSettings().setValue(_THEME_LAST_KEY, name)


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
    if not layer or layer.type() != qt_compat.VectorLayerType:
        return "other"
    try:
        geom_type = layer.geometryType()
    except Exception:
        return "other"
    if geom_type == qt_compat.PointGeometry:
        return "point"
    if geom_type == qt_compat.LineGeometry:
        return "line"
    if geom_type == qt_compat.PolygonGeometry:
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


def _remove_saved_style_name(name):
    """Remove *name* from the plugin’s saved-ramp list in ``QSettings`` (no ``QgsStyle`` change)."""
    settings = QgsSettings()
    raw = settings.value(_SAVED_STYLES_KEY, "", type=str)
    names = [n.strip() for n in raw.split("\n") if n.strip()]
    if name not in names:
        return
    names = [n for n in names if n != name]
    settings.setValue(_SAVED_STYLES_KEY, "\n".join(names))


def _plugin_saved_ramp_names_set():
    """Set of ramp names recorded under :data:`_SAVED_STYLES_KEY` (may include orphans)."""
    settings = QgsSettings()
    raw = settings.value(_SAVED_STYLES_KEY, "", type=str)
    return {n.strip() for n in raw.split("\n") if n.strip()}


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


def _remove_saved_single_colour_by_hex(hex_str):
    """
    Remove every saved-colour line whose colour matches *hex_str* (normalized via ``QColor``).

    Returns True if at least one line was removed.
    """
    hex_str = (hex_str or "").strip()
    if not hex_str:
        return False
    target = QColor(hex_str)
    if not target.isValid():
        return False
    tnorm = target.name().lower()
    settings = QgsSettings()
    raw = settings.value(_SAVED_SINGLE_COLOURS_KEY, "", type=str)
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    kept = []
    removed = False
    for ln in lines:
        if "|" in ln:
            _, h = ln.split("|", 1)
            h = h.strip()
        else:
            h = ln.strip()
        qc = QColor(h)
        if qc.isValid() and qc.name().lower() == tnorm:
            removed = True
            continue
        kept.append(ln)
    if not removed:
        return False
    settings.setValue(_SAVED_SINGLE_COLOURS_KEY, "\n".join(kept))
    return True


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
        self._suppress_preset_ramp_apply = False
        # Theme state
        self._theme_active_name = _get_last_theme()
        self._theme_signal_connected = False
        self._build_ui()
        self._populate_ramps()
        self._populate_saved_styles()
        self._populate_saved_colours()
        self._populate_full_styles()
        self.ramp_combo.currentIndexChanged.connect(self._on_ramp_changed)
        self.saved_styles_combo.currentIndexChanged.connect(self._on_saved_style_changed)
        self.saved_styles_combo.currentIndexChanged.connect(
            self._update_delete_saved_ramp_enabled
        )
        self.saved_colours_combo.currentIndexChanged.connect(self._on_saved_colour_changed)
        self.saved_colours_combo.currentIndexChanged.connect(
            self._update_delete_saved_colour_enabled
        )
        self.full_style_combo.currentIndexChanged.connect(self._on_full_style_changed)
        self.ramp_button.colorRampChanged.connect(self._on_ramp_button_changed)
        self.theme_combo.currentIndexChanged.connect(
            lambda _: self._update_theme_ui_state()
        )
        self._on_ramp_changed()
        self._update_delete_saved_ramp_enabled()
        self._update_delete_saved_colour_enabled()
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
        self._shortcut_apply_return = QShortcut(QKeySequence(qt_compat.Key_Return), self)
        self._shortcut_apply_return.activated.connect(self._on_apply)
        self._shortcut_apply_return.setContext(qt_compat.WindowShortcut)
        self._shortcut_apply_enter = QShortcut(QKeySequence(qt_compat.Key_Enter), self)
        self._shortcut_apply_enter.activated.connect(self._on_apply)
        self._shortcut_apply_enter.setContext(qt_compat.WindowShortcut)
        self._shortcut_close = QShortcut(QKeySequence(qt_compat.Key_Escape), self)
        self._shortcut_close.activated.connect(self.close)
        self._shortcut_close.setContext(qt_compat.WindowShortcut)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_target_label()
        self._populate_saved_styles()
        self._populate_saved_colours()
        self._populate_full_styles()
        self._populate_themes()
        self._refresh_timer.start()
        self.ramp_combo.setFocus(qt_compat.OtherFocusReason)
        # Re-sync theme auto-apply connection based on toggle state
        self._sync_theme_connection()
        self._rebuild_ramp_derived_swatches()
        self._rebuild_preset_palette_swatches()

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- Tab widget ---
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # === Home tab (existing experience) ===
        home_tab = QWidget()
        home_layout = QVBoxLayout(home_tab)

        # Target layer (active layer only; read-only)
        target_group = QGroupBox("Target layer")
        target_layout = QVBoxLayout(target_group)
        self.target_label = QLabel("—")
        self.target_label.setStyleSheet("font-weight: bold;")
        target_layout.addWidget(self.target_label)
        home_layout.addWidget(target_group)

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
        self.delete_saved_ramp_btn = QPushButton("Delete")
        self.delete_saved_ramp_btn.setToolTip(
            "Remove the selected ramp from QGIS styles and Palette Pilot’s saved list"
        )
        self.delete_saved_ramp_btn.clicked.connect(self._on_delete_saved_ramp)
        saved_row.addWidget(self.delete_saved_ramp_btn)
        ramp_layout.addLayout(saved_row)

        intent_row = QHBoxLayout()
        intent_row.addWidget(QLabel("Intent palette:"))
        self.preset_ramp_for_classes_combo = QComboBox()
        self.preset_ramp_for_classes_combo.setMinimumWidth(180)
        self.preset_ramp_for_classes_combo.addItem("—", "")
        for key in palette_presets.PRESET_RAMP_DISPLAY_ORDER:
            self.preset_ramp_for_classes_combo.addItem(key, key)
        self.preset_ramp_for_classes_combo.setToolTip(
            "Build a gradient from this named palette. For graduated or categorized "
            "layers it applies to the map; for single-symbol layers it only updates "
            "the ramp preview and quick swatches below."
        )
        self.preset_ramp_for_classes_combo.currentIndexChanged.connect(
            self._on_preset_ramp_for_classes_changed
        )
        intent_row.addWidget(self.preset_ramp_for_classes_combo, stretch=1)
        ramp_layout.addLayout(intent_row)

        home_layout.addWidget(ramp_group)

        # Single symbol colour (only meaningful when renderer is single symbol)
        colour_group = QGroupBox("Single symbol colour")
        colour_layout = QVBoxLayout(colour_group)
        self.colour_button = QgsColorButton()
        self.colour_button.setText("Pick colour…")
        # Auto-apply new colour to single-symbol layers when the user confirms a pick
        self.colour_button.colorChanged.connect(self._on_single_colour_changed)
        colour_layout.addWidget(self.colour_button)

        sw_lbl = QLabel("Quick swatches from ramp preview (above)")
        sw_lbl.setWordWrap(True)
        sw_lbl.setStyleSheet("font-size: 11px; color: #555;")
        colour_layout.addWidget(sw_lbl)
        self._ramp_swatch_host = QWidget()
        self._ramp_swatch_grid = QGridLayout(self._ramp_swatch_host)
        self._ramp_swatch_grid.setContentsMargins(0, 0, 0, 0)
        self._ramp_swatch_grid.setSpacing(4)
        colour_layout.addWidget(self._ramp_swatch_host)

        preset_sw_row = QHBoxLayout()
        preset_sw_row.addWidget(QLabel("Preset swatches:"))
        self.preset_swatches_combo = QComboBox()
        self.preset_swatches_combo.setMinimumWidth(160)
        self.preset_swatches_combo.addItem("—", "")
        for key in palette_presets.PRESET_RAMP_DISPLAY_ORDER:
            self.preset_swatches_combo.addItem(key, key)
        self.preset_swatches_combo.setToolTip(
            "Show colours from a named palette as clickable swatches (single-symbol layers)."
        )
        self.preset_swatches_combo.currentIndexChanged.connect(
            self._on_preset_swatches_combo_changed
        )
        preset_sw_row.addWidget(self.preset_swatches_combo, stretch=1)
        colour_layout.addLayout(preset_sw_row)
        self._preset_swatch_host = QWidget()
        self._preset_swatch_grid = QGridLayout(self._preset_swatch_host)
        self._preset_swatch_grid.setContentsMargins(0, 0, 0, 0)
        self._preset_swatch_grid.setSpacing(4)
        colour_layout.addWidget(self._preset_swatch_host)

        # Saved colours: list of single-symbol colours saved via "Save current"; persists between sessions
        saved_colours_row = QHBoxLayout()
        self.saved_colours_combo = QComboBox()
        self.saved_colours_combo.setMinimumWidth(180)
        self.saved_colours_combo.setEditable(False)
        saved_colours_row.addWidget(self.saved_colours_combo)
        self.save_current_colour_btn = QPushButton("Save current as…")
        self.save_current_colour_btn.clicked.connect(self._on_save_current_colour_as)
        saved_colours_row.addWidget(self.save_current_colour_btn)
        self.delete_saved_colour_btn = QPushButton("Delete")
        self.delete_saved_colour_btn.setToolTip(
            "Remove the selected colour from Palette Pilot’s saved colours list"
        )
        self.delete_saved_colour_btn.clicked.connect(self._on_delete_saved_colour)
        saved_colours_row.addWidget(self.delete_saved_colour_btn)
        colour_layout.addLayout(saved_colours_row)
        home_layout.addWidget(colour_group)
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
        home_layout.addWidget(full_style_group)
        self._full_style_group = full_style_group

        home_layout.addStretch()
        self.tab_widget.addTab(home_tab, "Home")

        # === Themes tab ===
        self._build_themes_tab()

        # --- Buttons (always visible, below tabs) ---
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
        self.close_btn.setFocusPolicy(qt_compat.NoFocus)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _build_themes_tab(self):
        """Build the Themes tab content (compact layout — more vertical space for rules context)."""
        themes_tab = QWidget()
        themes_layout = QVBoxLayout(themes_tab)
        themes_layout.setContentsMargins(4, 4, 4, 4)
        themes_layout.setSpacing(4)

        # --- Enable toggle ---
        self.theme_toggle = QCheckBox("Enable theme auto-styling")
        self.theme_toggle.setStyleSheet("font-weight: bold;")
        self.theme_toggle.setChecked(_get_theme_enabled())
        self.theme_toggle.toggled.connect(self._on_theme_toggle_changed)
        themes_layout.addWidget(self.theme_toggle)

        # --- Theme selector, actions, and status in one group (fewer nested boxes) ---
        theme_select_group = QGroupBox("Theme")
        theme_select_layout = QVBoxLayout(theme_select_group)
        theme_select_layout.setSpacing(3)
        theme_select_layout.setContentsMargins(6, 6, 6, 6)

        theme_combo_row = QHBoxLayout()
        theme_combo_row.setSpacing(4)
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(200)
        self.theme_combo.setEditable(False)
        theme_combo_row.addWidget(self.theme_combo, stretch=1)
        theme_select_layout.addLayout(theme_combo_row)

        mgmt_row = QHBoxLayout()
        mgmt_row.setSpacing(4)
        self.new_theme_btn = QPushButton("New…")
        self.new_theme_btn.clicked.connect(self._on_new_theme)
        mgmt_row.addWidget(self.new_theme_btn)
        self.edit_theme_btn = QPushButton("Edit…")
        self.edit_theme_btn.clicked.connect(self._on_edit_theme)
        mgmt_row.addWidget(self.edit_theme_btn)
        self.delete_theme_btn = QPushButton("Delete")
        self.delete_theme_btn.clicked.connect(self._on_delete_theme)
        mgmt_row.addWidget(self.delete_theme_btn)
        mgmt_row.addStretch()
        theme_select_layout.addLayout(mgmt_row)

        self.theme_status_label = QLabel("No theme active.")
        self.theme_status_label.setWordWrap(True)
        self.theme_status_label.setStyleSheet("color: #444; font-size: 11px;")
        theme_select_layout.addWidget(self.theme_status_label)

        themes_layout.addWidget(theme_select_group)
        self._theme_select_group = theme_select_group

        # --- Description ---
        desc = QLabel(
            "When enabled, the selected theme is applied to all project layers "
            "on Apply (or Enter) and automatically to any new layers added while "
            "the toggle is on.  Only one theme is active at a time.\n\n"
            "A theme is a set of rules, each pairing a .qml style file with a "
            "regex pattern that matches layer names."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px; margin-top: 2px;")
        themes_layout.addWidget(desc)

        themes_layout.addStretch()
        self.tab_widget.addTab(themes_tab, "Themes")

        # Initial UI state
        self._update_theme_ui_state()

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------

    def _available_themes(self):
        """Return a list of available theme names from the themes directory."""
        return theme_engine.list_themes()

    def _populate_themes(self):
        """Refresh the theme combo with available themes, preserving selection."""
        self.theme_combo.clear()
        self.theme_combo.addItem("—")
        themes = self._available_themes()
        for name in themes:
            self.theme_combo.addItem(name)
        # Restore last-used theme if still available
        last = _get_last_theme()
        if last:
            idx = self.theme_combo.findText(last)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)

    def _update_theme_ui_state(self):
        """Enable/disable theme controls based on toggle state; update status label."""
        enabled = self.theme_toggle.isChecked()
        self._theme_select_group.setEnabled(enabled)
        has_theme = (
            self.theme_combo.currentIndex() > 0
            and self.theme_combo.currentText().strip() != "—"
        )
        self.edit_theme_btn.setEnabled(has_theme)
        self.delete_theme_btn.setEnabled(has_theme)
        if not enabled:
            self.theme_status_label.setText("Themes disabled.")
        elif self._theme_active_name:
            self.theme_status_label.setText(
                f'Active theme: "{self._theme_active_name}"\n'
                "New layers will be styled automatically."
            )
        else:
            self.theme_status_label.setText("No theme active. Select a theme and click Apply.")

    def _on_theme_toggle_changed(self, checked):
        """Handle the theme enable/disable toggle."""
        _set_theme_enabled(checked)
        self._sync_theme_connection()
        if not checked:
            # Toggling off clears the active theme (but remembers the last name for restore)
            self._theme_active_name = ""
        self._update_theme_ui_state()

    def _sync_theme_connection(self):
        """
        Connect or disconnect the QgsProject.layersAdded signal so new layers
        are auto-styled only while the toggle is on **and** a theme is active.
        """
        should_connect = (
            self.theme_toggle.isChecked() and bool(self._theme_active_name)
        )
        project = QgsProject.instance()
        if should_connect and not self._theme_signal_connected:
            project.layersAdded.connect(self._on_layers_added)
            self._theme_signal_connected = True
        elif not should_connect and self._theme_signal_connected:
            try:
                project.layersAdded.disconnect(self._on_layers_added)
            except (TypeError, RuntimeError):
                pass
            self._theme_signal_connected = False

    def _on_layers_added(self, layers):
        """
        Slot for QgsProject.layersAdded — auto-apply the active theme to
        every newly-added vector layer.
        """
        if not self._theme_active_name or not self.theme_toggle.isChecked():
            return
        for layer in layers:
            if layer.type() != qt_compat.VectorLayerType:
                continue
            self._apply_theme_to_layer(layer, self._theme_active_name)

    def _on_new_theme(self):
        """Open the theme editor to create a new theme."""
        dlg = ThemeEditorDialog(self.iface, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            name = dlg.saved_theme_name()
            self._populate_themes()
            if name:
                idx = self.theme_combo.findText(name)
                if idx >= 0:
                    self.theme_combo.setCurrentIndex(idx)
            self._update_theme_ui_state()

    def _on_edit_theme(self):
        """Open the theme editor for the currently selected theme."""
        name = self.theme_combo.currentText().strip()
        if not name or name == "—":
            return
        data = theme_engine.load_theme(name)
        if not data:
            QMessageBox.warning(
                self, "Palette Pilot",
                f'Could not load theme "{name}".',
            )
            return
        dlg = ThemeEditorDialog(self.iface, parent=self, theme_data=data)
        if dlg.exec_() == QDialog.Accepted:
            new_name = dlg.saved_theme_name()
            self._populate_themes()
            select = new_name or name
            idx = self.theme_combo.findText(select)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            # If the active theme was renamed, update the active name
            if self._theme_active_name == name and new_name and new_name != name:
                self._theme_active_name = new_name
                _set_last_theme(new_name)
            self._update_theme_ui_state()

    def _on_delete_theme(self):
        """Delete the currently selected theme."""
        name = self.theme_combo.currentText().strip()
        if not name or name == "—":
            return
        reply = QMessageBox.question(
            self, "Palette Pilot",
            f'Delete theme "{name}"?  This cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        theme_engine.delete_theme(name)
        if self._theme_active_name == name:
            self._theme_active_name = ""
            _set_last_theme("")
            self._sync_theme_connection()
        self._populate_themes()
        self._update_theme_ui_state()
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Deleted theme "{name}".',
            level=qt_compat.MessageInfo,
            duration=3,
        )

    def _apply_theme_to_layer(self, layer, theme_name):
        """
        Apply *theme_name* to a single vector *layer* using theme_engine.
        Returns True if a rule matched and was applied.
        """
        data = theme_engine.load_theme(theme_name)
        if not data:
            QgsMessageLog.logMessage(
                f'Theme "{theme_name}" not found or invalid.',
                "Palette Pilot",
                qt_compat.MessageWarning,
            )
            return False
        return theme_engine.apply_theme_to_single_layer(data, layer, iface=self.iface)

    def _apply_theme_to_project(self, theme_name):
        """
        Apply *theme_name* to every matching vector layer in the project.
        Returns the number of layers styled.
        """
        data = theme_engine.load_theme(theme_name)
        if not data:
            QgsMessageLog.logMessage(
                f'Theme "{theme_name}" not found or invalid.',
                "Palette Pilot",
                qt_compat.MessageWarning,
            )
            return 0
        styled, warnings = theme_engine.apply_theme(data, iface=self.iface)
        for w in warnings:
            QgsMessageLog.logMessage(
                f'Theme "{theme_name}": {w}',
                "Palette Pilot",
                qt_compat.MessageWarning,
            )
        return styled

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

    def _swatch_source_ramp(self):
        """Ramp shown on the preview button, else built-in combo + invert."""
        try:
            r = self.ramp_button.colorRamp()
            if r is not None:
                return r
        except Exception:
            pass
        return self._current_effective_ramp()

    @staticmethod
    def _clear_swatch_grid(grid_layout):
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _fill_swatch_grid(self, grid_layout, colors, max_cols=6):
        self._clear_swatch_grid(grid_layout)
        if not colors:
            return
        for i, c in enumerate(colors):
            if not c.isValid():
                continue
            row, col = divmod(i, max_cols)
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(c.name())
            lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
            border = "#333" if lum > 160 else "#ccc"
            btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid {border}; "
                "border-radius: 3px;"
            )
            qc = QColor(c)
            btn.clicked.connect(partial(self._apply_single_symbol_color, qc))
            grid_layout.addWidget(btn, row, col)

    def _rebuild_ramp_derived_swatches(self):
        if not hasattr(self, "_ramp_swatch_grid"):
            return
        layer = self.iface.activeLayer()
        if (
            not layer
            or layer.type() != qt_compat.VectorLayerType
            or not isinstance(layer.renderer(), QgsSingleSymbolRenderer)
        ):
            self._clear_swatch_grid(self._ramp_swatch_grid)
            return
        ramp = self._swatch_source_ramp()
        colors = palette_presets.sample_ramp_colors(ramp, 12)
        self._fill_swatch_grid(self._ramp_swatch_grid, colors)

    def _rebuild_preset_palette_swatches(self):
        if not hasattr(self, "_preset_swatch_grid"):
            return
        layer = self.iface.activeLayer()
        if (
            not layer
            or layer.type() != qt_compat.VectorLayerType
            or not isinstance(layer.renderer(), QgsSingleSymbolRenderer)
        ):
            self._clear_swatch_grid(self._preset_swatch_grid)
            return
        if self.preset_swatches_combo.currentIndex() <= 0:
            self._clear_swatch_grid(self._preset_swatch_grid)
            return
        key = self.preset_swatches_combo.currentData()
        colors = palette_presets.preset_qcolors(key)
        self._fill_swatch_grid(self._preset_swatch_grid, colors)

    def _on_preset_swatches_combo_changed(self, _index=None):
        self._rebuild_preset_palette_swatches()

    def _on_preset_ramp_for_classes_changed(self, _index=None):
        if self._suppress_preset_ramp_apply:
            return
        if self.preset_ramp_for_classes_combo.currentIndex() <= 0:
            return
        key = self.preset_ramp_for_classes_combo.currentData()
        colors = palette_presets.preset_qcolors(key)
        ramp = palette_presets.gradient_ramp_from_qcolors(colors)
        if ramp is None:
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != qt_compat.VectorLayerType:
            return
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            btn_ramp = _clone_ramp(ramp)
            if btn_ramp is None:
                return
            self._suppress_ramp_button_apply = True
            try:
                self.ramp_button.setColorRamp(btn_ramp)
            except Exception:
                pass
            finally:
                self._suppress_ramp_button_apply = False
            self._rebuild_ramp_derived_swatches()
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                f'Updated ramp preview for swatches ("{key}").',
                level=qt_compat.MessageInfo,
                duration=3,
            )
            return
        ramp_apply = _clone_ramp(ramp)
        if ramp_apply is None:
            return
        if apply_ramp_to_layer(layer, ramp_apply):
            self._suppress_ramp_button_apply = True
            try:
                btn_ramp = _clone_ramp(ramp)
                if btn_ramp is not None:
                    self.ramp_button.setColorRamp(btn_ramp)
            except Exception:
                pass
            finally:
                self._suppress_ramp_button_apply = False
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
            self._rebuild_ramp_derived_swatches()
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                f'Applied intent palette "{key}" as a gradient ramp.',
                level=qt_compat.MessageInfo,
                duration=3,
            )

    def _apply_single_symbol_color(self, color):
        """Apply *color* to the active layer when it uses single-symbol renderer."""
        if not color or not color.isValid():
            return False
        layer = self.iface.activeLayer()
        if not layer or layer.type() != qt_compat.VectorLayerType:
            return False
        r = layer.renderer()
        if not isinstance(r, QgsSingleSymbolRenderer):
            return False
        try:
            self.colour_button.blockSignals(True)
            try:
                self.colour_button.setColor(color)
            finally:
                self.colour_button.blockSignals(False)
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
            return False
        return True

    def _update_target_label(self):
        """Update the 'Target layer' label to the current active layer."""
        layer = self.iface.activeLayer()
        if not layer:
            self.target_label.setText("(No layer selected)")
            self._ramp_group.setEnabled(False)
            self._ramp_group.setTitle(_RAMP_GROUP_TITLE_CLASSES)
            self._ramp_group.setToolTip("")
            self._colour_group.setEnabled(False)
            self._full_style_group.setEnabled(False)
            self._last_layer_id = None
            self._last_renderer_single = False
            self._last_full_style_geom_type = None
            self._rebuild_ramp_derived_swatches()
            self._rebuild_preset_palette_swatches()
            return
        if layer.type() != qt_compat.VectorLayerType:
            self.target_label.setText(f"{layer.name()} (not vector)")
            self._ramp_group.setEnabled(False)
            self._ramp_group.setTitle(_RAMP_GROUP_TITLE_CLASSES)
            self._ramp_group.setToolTip("")
            self._colour_group.setEnabled(False)
            self._full_style_group.setEnabled(False)
            self._last_layer_id = layer.id()
            self._last_renderer_single = False
            self._last_full_style_geom_type = None
            self._rebuild_ramp_derived_swatches()
            self._rebuild_preset_palette_swatches()
            return

        # Vector layer: adjust UI based on renderer type
        self.target_label.setText(layer.name())
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            # Single symbol: colour section + ramp preview (ramp edits update swatches only)
            self._colour_group.setEnabled(True)
            self._ramp_group.setEnabled(True)
            self._ramp_group.setTitle(_RAMP_GROUP_TITLE_PREVIEW)
            self._ramp_group.setToolTip(_RAMP_GROUP_TIP_PREVIEW)
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
            self._ramp_group.setTitle(_RAMP_GROUP_TITLE_CLASSES)
            self._ramp_group.setToolTip(_RAMP_GROUP_TIP_CLASSES)
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

        self._rebuild_ramp_derived_swatches()
        self._rebuild_preset_palette_swatches()

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
        try:
            # Auto-apply ramps for graduated/categorized layers when the user
            # cycles ramps, but skip during initialisation or when suppressed.
            if self._suppress_ramp_auto_apply:
                return
            layer = self.iface.activeLayer()
            if not layer or layer.type() != qt_compat.VectorLayerType:
                return
            # Do not auto-apply for single-symbol layers (they use the colour picker)
            r = layer.renderer()
            if isinstance(r, QgsSingleSymbolRenderer):
                return
            ramp_to_apply = ramp
            if not ramp_to_apply:
                return

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
        finally:
            self._rebuild_ramp_derived_swatches()

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
        if not layer or layer.type() != qt_compat.VectorLayerType:
            return
        r = layer.renderer()
        if isinstance(r, QgsSingleSymbolRenderer):
            cr = _clone_ramp(ramp)
            if cr is None:
                return
            self._suppress_ramp_button_apply = True
            try:
                self.ramp_button.setColorRamp(cr)
            except Exception:
                pass
            finally:
                self._suppress_ramp_button_apply = False
            self._rebuild_ramp_derived_swatches()
            return

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
            level=qt_compat.MessageInfo,
            duration=3,
        )

    def _update_delete_saved_ramp_enabled(self):
        """Delete is only meaningful when a real saved ramp is selected (not \"—\")."""
        if not hasattr(self, "delete_saved_ramp_btn"):
            return
        self.delete_saved_ramp_btn.setEnabled(self.saved_styles_combo.currentIndex() > 0)

    def _on_delete_saved_ramp(self):
        """Remove the selected ramp from ``QgsStyle`` (if present) and the plugin saved list."""
        idx = self.saved_styles_combo.currentIndex()
        if idx <= 0:
            QMessageBox.information(
                self,
                "Palette Pilot",
                "Select a saved ramp in the list, then click Delete.",
            )
            return
        name = self.saved_styles_combo.currentText().strip()
        if not name:
            return
        if name not in _plugin_saved_ramp_names_set():
            QMessageBox.warning(
                self,
                "Palette Pilot",
                f'"{name}" is not in Palette Pilot’s saved list, so it will not be deleted. '
                "Use QGIS Style Manager to remove other ramps.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Palette Pilot",
            f'Delete colour ramp "{name}" from your QGIS default style and remove it from '
            "Palette Pilot’s saved list?\n\n"
            "Existing layers keep their current colours until symbology is changed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        style = QgsStyle.defaultStyle()
        try:
            style_names = style.colorRampNames() or []
        except Exception:
            style_names = []
        if name in style_names:
            rm = getattr(style, "removeColorRamp", None)
            if rm is None:
                QMessageBox.warning(
                    self,
                    "Palette Pilot",
                    "This QGIS version does not expose removing colour ramps to Python.",
                )
                return
            try:
                result = rm(name)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Palette Pilot",
                    f"Could not remove ramp from style database: {e!s}",
                )
                return
            if result is False:
                QMessageBox.warning(
                    self,
                    "Palette Pilot",
                    f'Could not remove ramp "{name}" from the style database.',
                )
                return

        _remove_saved_style_name(name)
        self._suppress_saved_style_apply = True
        self._populate_saved_styles()
        self.saved_styles_combo.setCurrentIndex(0)
        self._suppress_saved_style_apply = False
        self._update_delete_saved_ramp_enabled()

        in_style = name in style_names
        msg = (
            f'Deleted "{name}" from styles and saved list.'
            if in_style
            else f'Removed "{name}" from saved list (it was not in the style database).'
        )
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            msg,
            level=qt_compat.MessageInfo,
            duration=4,
        )

    def _on_ramp_button_changed(self):
        """Apply ramp chosen from QgsColorRampButton (dropdown or dialog)."""
        if self._suppress_ramp_button_apply:
            return
        try:
            try:
                ramp = self.ramp_button.colorRamp()
            except Exception:
                return
            if ramp is None:
                return
            layer = self.iface.activeLayer()
            if not layer or layer.type() != qt_compat.VectorLayerType:
                return
            r = layer.renderer()
            if isinstance(r, QgsSingleSymbolRenderer):
                return

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
        finally:
            self._rebuild_ramp_derived_swatches()

    def _on_saved_colour_changed(self):
        """Apply the selected saved colour to the active layer (live apply)."""
        if self._suppress_saved_colour_apply:
            return
        if self.saved_colours_combo.currentIndex() == 0:
            return  # placeholder "—"
        hex_str = self.saved_colours_combo.currentData(qt_compat.UserRole) or self.saved_colours_combo.currentText()
        if not hex_str or not isinstance(hex_str, str):
            hex_str = str(hex_str).strip() if hex_str else ""
        if not hex_str:
            return
        color = QColor(hex_str)
        if not color.isValid():
            return
        self._apply_single_symbol_color(color)

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
        idx = self.saved_colours_combo.findData(hex_str, qt_compat.UserRole)
        if idx < 0:
            idx = self.saved_colours_combo.findText(display_name)
        if idx >= 0:
            self.saved_colours_combo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            "Saved colour to Saved colours.",
            level=qt_compat.MessageInfo,
            duration=3,
        )

    def _update_delete_saved_colour_enabled(self):
        """Delete is only meaningful when a real saved colour is selected (not \"—\")."""
        if not hasattr(self, "delete_saved_colour_btn"):
            return
        self.delete_saved_colour_btn.setEnabled(self.saved_colours_combo.currentIndex() > 0)

    def _on_delete_saved_colour(self):
        """Remove the selected colour from the plugin persisted list."""
        idx = self.saved_colours_combo.currentIndex()
        if idx <= 0:
            QMessageBox.information(
                self,
                "Palette Pilot",
                "Select a saved colour in the list, then click Delete.",
            )
            return
        label = self.saved_colours_combo.currentText().strip()
        hex_str = self.saved_colours_combo.currentData(qt_compat.UserRole)
        if not hex_str or not isinstance(hex_str, str):
            hex_str = label
        hex_str = (hex_str or "").strip()
        if not hex_str:
            return
        if not QColor(hex_str).isValid():
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "Could not resolve the colour to remove.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Palette Pilot",
            f'Remove "{label}" from saved colours?\n\n'
            "The map is not changed; only the saved swatch list is updated.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if not _remove_saved_single_colour_by_hex(hex_str):
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "That colour was not found in the saved list.",
            )
            return
        self._suppress_saved_colour_apply = True
        self._populate_saved_colours()
        self.saved_colours_combo.setCurrentIndex(0)
        self._suppress_saved_colour_apply = False
        self._update_delete_saved_colour_enabled()
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Removed "{label}" from saved colours.',
            level=qt_compat.MessageInfo,
            duration=3,
        )

    def _on_full_style_changed(self):
        """Load the selected full style (.qml) onto the active layer."""
        if self._suppress_full_style_apply:
            return
        if self.full_style_combo.currentIndex() == 0:
            return  # placeholder "—"
        path = self.full_style_combo.currentData(qt_compat.UserRole)
        if not path or not isinstance(path, str) or not os.path.isfile(path):
            return
        layer = self.iface.activeLayer()
        if not layer or layer.type() != qt_compat.VectorLayerType:
            return
        try:
            msg, ok = layer.loadNamedStyle(path)
            if not ok:
                self.iface.messageBar().pushMessage(
                    "Palette Pilot",
                    msg or "Could not load style.",
                    level=qt_compat.MessageWarning,
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
                level=qt_compat.MessageInfo,
                duration=3,
            )
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                str(e),
                level=qt_compat.MessageWarning,
                duration=5,
            )

    def _on_save_full_style_to_file(self):
        """Save the current layer's full style to a .qml file via a save-file dialog."""
        layer = self.iface.activeLayer()
        if not layer or layer.type() != qt_compat.VectorLayerType:
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
        idx = self.full_style_combo.findData(path, qt_compat.UserRole)
        if idx >= 0:
            self.full_style_combo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Saved style to {path}',
            level=qt_compat.MessageInfo,
            duration=5,
        )

    def _on_copy_style_path(self):
        """Copy the full-style save directory path to the clipboard (type-specific folder when a layer is active)."""
        layer = self.iface.activeLayer()
        directory = _get_full_style_type_directory(layer) if layer and layer.type() == qt_compat.VectorLayerType else _get_full_style_directory()
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(directory)
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Path copied to clipboard.",
                level=qt_compat.MessageInfo,
                duration=2,
            )

    def _on_open_style_location(self):
        """Open the full-style save directory in the system file manager (type-specific folder when a layer is active)."""
        layer = self.iface.activeLayer()
        directory = _get_full_style_type_directory(layer) if layer and layer.type() == qt_compat.VectorLayerType else _get_full_style_directory()
        url = QUrl.fromLocalFile(directory)
        if QDesktopServices.openUrl(url):
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Opened save location.",
                level=qt_compat.MessageInfo,
                duration=2,
            )
        else:
            self.iface.messageBar().pushMessage(
                "Palette Pilot",
                "Could not open location. Use Copy path to open it manually.",
                level=qt_compat.MessageWarning,
                duration=4,
            )

    def _on_single_colour_changed(self, color):
        """
        Auto-apply single-symbol colour when the user confirms a pick in the colour dialog.
        This avoids needing a second Enter/Apply after closing the picker.
        """
        layer = self.iface.activeLayer()
        if not layer or layer.type() != qt_compat.VectorLayerType:
            return
        if not isinstance(layer.renderer(), QgsSingleSymbolRenderer):
            return
        if not self._apply_single_symbol_color(color):
            return
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Applied single symbol colour to "{layer.name()}".',
            level=qt_compat.MessageInfo,
            duration=3,
        )
        QgsMessageLog.logMessage(
            f'Applied single symbol colour to "{layer.name()}".',
            "Palette Pilot",
            qt_compat.MessageInfo,
        )

    def _on_apply(self):
        # --- Themes tab: apply theme to project ---
        if self.tab_widget.currentIndex() == 1:
            self._on_apply_theme()
            return

        # --- Home tab: existing behaviour ---
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

        if layer.type() != qt_compat.VectorLayerType:
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
                    level=qt_compat.MessageInfo,
                    duration=3,
                )
                QgsMessageLog.logMessage(
                    f'Applied single symbol colour to "{layer.name()}".',
                    "Palette Pilot",
                    qt_compat.MessageInfo,
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
                level=qt_compat.MessageInfo,
                duration=3,
            )
            QgsMessageLog.logMessage(
                f"Applied ramp '{ramp_name}' to \"{layer.name()}\".",
                "Palette Pilot",
                qt_compat.MessageInfo,
            )
        else:
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "The active layer does not use graduated or categorized symbology. "
                "Switch the layer to one of these in Layer Properties → Symbology, then try again.",
            )
        # Dialog stays open; user closes it with Close button

    def _on_apply_theme(self):
        """Apply the selected theme to all project layers (Themes tab Apply handler)."""
        if not self.theme_toggle.isChecked():
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "Themes are disabled. Enable the toggle first.",
            )
            return
        theme_name = self.theme_combo.currentText().strip()
        if not theme_name or theme_name == "—":
            QMessageBox.warning(
                self,
                "Palette Pilot",
                "No theme selected. Choose a theme from the list.",
            )
            return
        # Activate the theme
        self._theme_active_name = theme_name
        _set_last_theme(theme_name)
        self._sync_theme_connection()
        # Apply to all existing layers
        count = self._apply_theme_to_project(theme_name)
        self._update_theme_ui_state()
        self.iface.messageBar().pushMessage(
            "Palette Pilot",
            f'Applied theme "{theme_name}" to {count} layer(s).',
            level=qt_compat.MessageInfo,
            duration=3,
        )
        QgsMessageLog.logMessage(
            f'Applied theme "{theme_name}" to {count} layer(s).',
            "Palette Pilot",
            qt_compat.MessageInfo,
        )
