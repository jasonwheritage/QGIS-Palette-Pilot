# -*- coding: utf-8 -*-
"""
Theme editor dialog for Palette Pilot.

Provides a dialog for creating and editing themes.  A theme is a list of
rules, where each rule pairs a ``.qml`` style file (from the
``palette_pilot_full_styles/<geometry>/`` directories) with a regex pattern
that determines which layer names receive that style.
"""

import re as _re

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QScrollArea,
    QWidget,
    QSizePolicy,
    QFrame,
)
from qgis.core import QgsProject

from . import qt_compat
from . import theme_engine


# ---------------------------------------------------------------------------
# Single-rule widget
# ---------------------------------------------------------------------------

class _RuleWidget(QFrame):
    """Widget for editing a single theme rule (geometry type + style + regex)."""

    def __init__(self, parent=None, *, rule=None, rule_number=1):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("QFrame { margin: 2px; padding: 4px; }")
        self._build(rule_number)
        if rule:
            self._load_rule(rule)
        # Wire signals for live match preview
        self.geom_combo.currentIndexChanged.connect(self._on_geom_changed)
        self.pattern_edit.textChanged.connect(self._update_match_preview)

    def _build(self, rule_number):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Header row
        header = QHBoxLayout()
        self._header_label = QLabel(f"<b>Rule {rule_number}</b>")
        header.addWidget(self._header_label)
        header.addStretch()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedWidth(70)
        header.addWidget(self.remove_btn)
        layout.addLayout(header)

        # Geometry type
        form = QFormLayout()
        self.geom_combo = QComboBox()
        self.geom_combo.addItem("Point", "point")
        self.geom_combo.addItem("Line", "line")
        self.geom_combo.addItem("Polygon", "polygon")
        form.addRow("Geometry:", self.geom_combo)

        # Style file
        self.style_combo = QComboBox()
        self.style_combo.setMinimumWidth(200)
        form.addRow("Style:", self.style_combo)

        # Regex pattern
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("e.g. (?i)station|stop")
        form.addRow("Pattern:", self.pattern_edit)

        layout.addLayout(form)

        # Match preview
        self.match_label = QLabel("")
        self.match_label.setWordWrap(True)
        self.match_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.match_label)

        # Populate styles for initial geometry type
        self._refresh_styles()

    def set_rule_number(self, n):
        self._header_label.setText(f"<b>Rule {n}</b>")

    def _on_geom_changed(self):
        """Re-populate style combo when geometry type changes."""
        self._refresh_styles()
        self._update_match_preview()

    def _refresh_styles(self):
        """Populate the style combo for the current geometry type."""
        geom = self.geom_combo.currentData(qt_compat.UserRole)
        self.style_combo.clear()
        self.style_combo.addItem("—", "")
        styles = theme_engine.list_styles_for_geometry(geom or "point")
        for display_name, path in styles:
            self.style_combo.addItem(display_name, path)

    def _update_match_preview(self):
        """Show which current project layers match the rule."""
        pattern = self.pattern_edit.text().strip()
        geom = self.geom_combo.currentData(qt_compat.UserRole) or "point"
        if not pattern:
            self.match_label.setText("")
            return
        try:
            rx = _re.compile(pattern)
        except _re.error as exc:
            self.match_label.setText(f'<span style="color:red;">Invalid regex: {exc}</span>')
            return
        project = QgsProject.instance()
        matched = []
        for layer in project.mapLayers().values():
            if layer.type() != qt_compat.VectorLayerType:
                continue
            if theme_engine._geometry_type_key(layer) != geom:
                continue
            if rx.search(layer.name()):
                matched.append(layer.name())
        if matched:
            names = ", ".join(matched[:15])
            extra = f" (+{len(matched) - 15} more)" if len(matched) > 15 else ""
            self.match_label.setText(
                f'<span style="color:green;">Matches {len(matched)} layer(s): {names}{extra}</span>'
            )
        else:
            self.match_label.setText(
                '<span style="color:orange;">No matching layers in current project.</span>'
            )

    def _load_rule(self, rule):
        """Populate widgets from an existing rule dict."""
        geom = rule.get("geometry_type", "point")
        idx = self.geom_combo.findData(geom, qt_compat.UserRole)
        if idx >= 0:
            self.geom_combo.setCurrentIndex(idx)
        self._refresh_styles()
        style = rule.get("style_file", "")
        if style:
            idx = self.style_combo.findData(style, qt_compat.UserRole)
            if idx >= 0:
                self.style_combo.setCurrentIndex(idx)
        self.pattern_edit.setText(rule.get("pattern", ""))
        self._update_match_preview()

    def to_rule(self):
        """Return a rule dict from the current widget state, or None if incomplete."""
        geom = self.geom_combo.currentData(qt_compat.UserRole) or "point"
        style = self.style_combo.currentData(qt_compat.UserRole) or ""
        pattern = self.pattern_edit.text().strip()
        if not style or not pattern:
            return None
        return {
            "geometry_type": geom,
            "style_file": style,
            "pattern": pattern,
        }


# ---------------------------------------------------------------------------
# Theme editor dialog
# ---------------------------------------------------------------------------

class ThemeEditorDialog(QDialog):
    """Dialog for creating or editing a theme (ordered list of style→regex rules)."""

    def __init__(self, iface, parent=None, *, theme_data=None):
        super().__init__(parent)
        self.iface = iface
        self._rule_widgets = []
        self._editing_name = ""
        self.setWindowTitle("Palette Pilot — Theme Editor")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self._build_ui()
        if theme_data:
            self._load_theme(theme_data)

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Theme name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Theme name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My theme")
        name_row.addWidget(self.name_edit)
        root.addLayout(name_row)

        # Rules area (scrollable)
        rules_group = QGroupBox("Rules")
        rules_outer = QVBoxLayout(rules_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rules_container = QWidget()
        self._rules_layout = QVBoxLayout(self._rules_container)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.addStretch()
        scroll.setWidget(self._rules_container)
        rules_outer.addWidget(scroll)

        add_row = QHBoxLayout()
        add_btn = QPushButton("+ Add rule")
        add_btn.clicked.connect(self._add_empty_rule)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        rules_outer.addLayout(add_row)

        root.addWidget(rules_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        preview_btn = QPushButton("Preview")
        preview_btn.setToolTip("Apply the rules to the project without saving")
        preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(preview_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def _add_rule_widget(self, rule=None):
        """Add a new rule widget (optionally pre-populated from *rule* dict)."""
        n = len(self._rule_widgets) + 1
        w = _RuleWidget(self, rule=rule, rule_number=n)
        w.remove_btn.clicked.connect(lambda _=False, widget=w: self._remove_rule(widget))
        # Insert before the stretch at the end
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, w)
        self._rule_widgets.append(w)
        self._renumber()

    def _add_empty_rule(self):
        self._add_rule_widget()

    def _remove_rule(self, widget):
        if widget in self._rule_widgets:
            self._rule_widgets.remove(widget)
            self._rules_layout.removeWidget(widget)
            widget.deleteLater()
            self._renumber()

    def _renumber(self):
        for i, w in enumerate(self._rule_widgets, 1):
            w.set_rule_number(i)

    # ------------------------------------------------------------------
    # Load / collect
    # ------------------------------------------------------------------

    def _load_theme(self, data):
        self._editing_name = data.get("name", "")
        self.name_edit.setText(self._editing_name)
        for rule in data.get("rules", []):
            self._add_rule_widget(rule)

    def _collect_rules(self):
        """Return list of valid rule dicts from the rule widgets."""
        rules = []
        for w in self._rule_widgets:
            r = w.to_rule()
            if r is not None:
                rules.append(r)
        return rules

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _on_preview(self):
        """Apply current rules to the project without saving the theme file."""
        rules = self._collect_rules()
        if not rules:
            QMessageBox.warning(self, "Palette Pilot", "No complete rules to preview.")
            return
        data = {"name": "__preview__", "rules": rules}
        styled, warnings = theme_engine.apply_theme(data, iface=self.iface)
        msg = f"Preview applied to {styled} layer(s)."
        if warnings:
            msg += "\n\nWarnings:\n" + "\n".join(warnings[:10])
        QMessageBox.information(self, "Palette Pilot", msg)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Palette Pilot", "Please enter a theme name.")
            self.name_edit.setFocus()
            return
        rules = self._collect_rules()
        if not rules:
            QMessageBox.warning(
                self, "Palette Pilot",
                "The theme has no complete rules.\n\n"
                "Each rule needs a style file and a regex pattern.",
            )
            return
        # Check for invalid regex patterns
        for r in rules:
            try:
                _re.compile(r["pattern"])
            except _re.error as exc:
                QMessageBox.warning(
                    self, "Palette Pilot",
                    f'Invalid regex pattern: {r["pattern"]}\n{exc}',
                )
                return
        # Warn if overwriting a different theme
        existing = theme_engine.list_themes()
        if name != self._editing_name and name in existing:
            reply = QMessageBox.question(
                self, "Palette Pilot",
                f'A theme named "{name}" already exists. Overwrite it?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        # If we renamed, delete the old file
        if self._editing_name and self._editing_name != name:
            theme_engine.delete_theme(self._editing_name)
        theme_engine.save_theme(name, rules)
        self.accept()

    # ------------------------------------------------------------------
    # Public result
    # ------------------------------------------------------------------

    def saved_theme_name(self):
        """Return the theme name that was saved (valid after accept)."""
        return self.name_edit.text().strip()
