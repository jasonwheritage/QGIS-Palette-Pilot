# -*- coding: utf-8 -*-
"""
Theme editor dialog for Palette Pilot.

Provides a dialog for creating and editing themes.  A theme is a list of
rules, where each rule pairs a ``.qml`` style file (from the
``palette_pilot_full_styles/<geometry>/`` directories) with a regex pattern
that determines which layer names receive that style.
"""

import re as _re

from qgis.PyQt.QtCore import Qt, QMimeData, QEvent
from qgis.PyQt.QtGui import QDrag
from qgis.PyQt.QtWidgets import (
    QApplication,
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
    QFrame,
    QCheckBox,
)
from qgis.core import QgsProject

from . import qt_compat
from . import theme_engine

# MIME type for internal drag-reorder of theme rules (theme editor only).
_RULE_INDEX_MIME = "application/x-palette-pilot-theme-rule-index"


class _ComboBoxWheelOnlyWhenPopupOpen(QComboBox):
    """
    Combo box that ignores the wheel while the drop-down list is closed.

    ``hasFocus()`` is not enough: Tab or a single click can focus the combo
    without opening the list, and the wheel would still change the value.
    Only when the user has opened the list (``view()`` is visible) do we
    forward the wheel; otherwise it is ignored so the parent ``QScrollArea``
    can scroll.
    """

    def wheelEvent(self, event):
        view = self.view()
        if view is not None and view.isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


def _exec_drag(drag):
    """Qt5 ``exec_`` vs Qt6 ``exec`` for QDrag; MoveAction lives under ``Qt`` or ``Qt.DropAction``."""
    try:
        move = Qt.MoveAction
    except AttributeError:
        move = Qt.DropAction.MoveAction
    ex = getattr(drag, "exec", None)
    if callable(ex):
        return ex(move)
    return drag.exec_(move)


# ---------------------------------------------------------------------------
# Rule header: drag handle + drop target for reordering
# ---------------------------------------------------------------------------


class _RuleDragHandle(QLabel):
    """Grip that starts a reorder drag (avoids stealing clicks from fields below)."""

    def __init__(self, rule_widget):
        super().__init__("☰")
        self._rule_widget = rule_widget
        self.setCursor(Qt.SizeVerCursor)
        self.setFixedWidth(22)
        self.setToolTip("Drag to reorder rules (drop on another rule’s header)")
        self.setAlignment(Qt.AlignCenter)
        self._press_pos = None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press_pos = e.pos()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._press_pos = None
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e):
        if self._press_pos is None or not (e.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(e)
        if (e.pos() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(e)
        editor = self._rule_widget._theme_editor
        if editor is None or not hasattr(editor, "_rule_widgets"):
            return super().mouseMoveEvent(e)
        try:
            src = editor._rule_widgets.index(self._rule_widget)
        except ValueError:
            return super().mouseMoveEvent(e)
        mime = QMimeData()
        mime.setData(_RULE_INDEX_MIME, str(src).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        _exec_drag(drag)
        self._press_pos = None


class _RuleHeaderBar(QWidget):
    """
    Header row for a rule: drag handle, title, enabled, reorder buttons, remove.
    Accepts drops so reorder works when releasing over header controls (via event filter).
    """

    def __init__(self, rule_widget, rule_number):
        super().__init__(rule_widget)
        self._rule_widget = rule_widget
        self.setAcceptDrops(True)

        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 0, 0, 0)

        self._drag_handle = _RuleDragHandle(rule_widget)
        hl.addWidget(self._drag_handle)

        self.title_label = QLabel(f"<b>Rule {rule_number}</b>")
        hl.addWidget(self.title_label)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("When off, this rule is skipped when applying the theme.")
        hl.addWidget(self.enabled_check)

        hl.addStretch()

        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(28)
        self.up_btn.setToolTip("Move rule up (earlier rules take precedence)")
        hl.addWidget(self.up_btn)

        self.down_btn = QPushButton("↓")
        self.down_btn.setFixedWidth(28)
        self.down_btn.setToolTip("Move rule down")
        hl.addWidget(self.down_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedWidth(62)
        hl.addWidget(self.remove_btn)

        for w in (
            self._drag_handle,
            self.title_label,
            self.enabled_check,
            self.up_btn,
            self.down_btn,
            self.remove_btn,
        ):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.DragEnter:
            if not event.mimeData().hasFormat(_RULE_INDEX_MIME):
                return False
            self.dragEnterEvent(event)
            return True
        if t == QEvent.DragMove:
            if not event.mimeData().hasFormat(_RULE_INDEX_MIME):
                return False
            self.dragMoveEvent(event)
            return True
        if t == QEvent.Drop:
            if not event.mimeData().hasFormat(_RULE_INDEX_MIME):
                return False
            self.dropEvent(event)
            return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(_RULE_INDEX_MIME):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(_RULE_INDEX_MIME):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if not e.mimeData().hasFormat(_RULE_INDEX_MIME):
            return super().dropEvent(e)
        try:
            raw = e.mimeData().data(_RULE_INDEX_MIME)
            src = int(bytes(raw).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, TypeError):
            return super().dropEvent(e)
        editor = self._rule_widget._theme_editor
        if editor is None or not hasattr(editor, "_reorder_rule_to_index"):
            return super().dropEvent(e)
        try:
            dst = editor._rule_widgets.index(self._rule_widget)
        except ValueError:
            return super().dropEvent(e)
        editor._reorder_rule_to_index(src, dst)
        e.acceptProposedAction()


# ---------------------------------------------------------------------------
# Single-rule widget
# ---------------------------------------------------------------------------

class _RuleWidget(QFrame):
    """Widget for editing a single theme rule (geometry type + style + regex)."""

    def __init__(self, theme_editor, parent=None, *, rule=None, rule_number=1):
        # Layout reparents this widget to the scroll content widget; keep the dialog
        # reference for reorder (parent() is not ThemeEditorDialog after insertWidget).
        self._theme_editor = theme_editor
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("QFrame { margin: 1px; padding: 2px; }")
        self._build(rule_number)
        if rule:
            self._load_rule(rule)
        # Wire signals for live match preview
        self.geom_combo.currentIndexChanged.connect(self._on_geom_changed)
        self.pattern_edit.textChanged.connect(self._update_match_preview)

    def _build(self, rule_number):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)

        self._header_bar = _RuleHeaderBar(self, rule_number)
        self._header_label = self._header_bar.title_label
        self.enabled_check = self._header_bar.enabled_check
        self.enabled_check.toggled.connect(self._update_match_preview)
        self.up_btn = self._header_bar.up_btn
        self.up_btn.setToolTip("Move rule up, or drag ☰ (earlier rules take precedence)")
        self.down_btn = self._header_bar.down_btn
        self.down_btn.setToolTip("Move rule down, or drag ☰ to reorder")
        self.remove_btn = self._header_bar.remove_btn
        layout.addWidget(self._header_bar)

        # Geometry type
        form = QFormLayout()
        form.setSpacing(2)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(6)
        form.setVerticalSpacing(2)
        self.geom_combo = _ComboBoxWheelOnlyWhenPopupOpen()
        self.geom_combo.addItem("Point", "point")
        self.geom_combo.addItem("Line", "line")
        self.geom_combo.addItem("Polygon", "polygon")
        form.addRow("Geometry:", self.geom_combo)

        # Style file
        self.style_combo = _ComboBoxWheelOnlyWhenPopupOpen()
        self.style_combo.setMinimumWidth(160)
        form.addRow("Style:", self.style_combo)

        # Regex pattern
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("e.g. (?i)station|stop")
        form.addRow("Pattern:", self.pattern_edit)

        layout.addLayout(form)

        # Match preview
        self.match_label = QLabel("")
        self.match_label.setWordWrap(True)
        self.match_label.setStyleSheet("color: #555; font-size: 10px;")
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
        disabled_note = ""
        if not self.enabled_check.isChecked():
            disabled_note = ' <span style="color:#888;">(disabled — not applied)</span>'
        if matched:
            names = ", ".join(matched[:15])
            extra = f" (+{len(matched) - 15} more)" if len(matched) > 15 else ""
            self.match_label.setText(
                f'<span style="color:green;">Matches {len(matched)} layer(s): {names}{extra}</span>'
                f"{disabled_note}"
            )
        else:
            self.match_label.setText(
                '<span style="color:orange;">No matching layers in current project.</span>'
                f"{disabled_note}"
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
        self.enabled_check.setChecked(theme_engine._rule_is_enabled(rule))
        self._update_match_preview()

    def to_rule(self):
        """Return a rule dict from the current widget state, or None if incomplete."""
        geom = self.geom_combo.currentData(qt_compat.UserRole) or "point"
        style = self.style_combo.currentData(qt_compat.UserRole) or ""
        pattern = self.pattern_edit.text().strip()
        if not style or not pattern:
            return None
        out = {
            "geometry_type": geom,
            "style_file": style,
            "pattern": pattern,
        }
        if not self.enabled_check.isChecked():
            out["enabled"] = False
        return out


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
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        self._build_ui()
        if theme_data:
            self._load_theme(theme_data)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Theme name
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(QLabel("Theme name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My theme")
        name_row.addWidget(self.name_edit, stretch=1)
        root.addLayout(name_row)

        # Rules area (scrollable)
        rules_group = QGroupBox("Rules")
        rules_outer = QVBoxLayout(rules_group)
        rules_outer.setSpacing(3)
        rules_outer.setContentsMargins(6, 6, 6, 6)

        scroll = QScrollArea()
        try:
            scroll.setFrameShape(QFrame.Shape.NoFrame)
        except AttributeError:
            scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(200)
        self._rules_container = QWidget()
        self._rules_layout = QVBoxLayout(self._rules_container)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.setSpacing(3)
        self._rules_layout.addStretch()
        scroll.setWidget(self._rules_container)
        rules_outer.addWidget(scroll, stretch=1)

        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        add_btn = QPushButton("+ Add rule")
        add_btn.clicked.connect(self._add_empty_rule)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        rules_outer.addLayout(add_row)

        root.addWidget(rules_group, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
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
        w = _RuleWidget(self, parent=self._rules_container, rule=rule, rule_number=n)
        w.remove_btn.clicked.connect(lambda _=False, widget=w: self._remove_rule(widget))
        w.up_btn.clicked.connect(lambda _=False, widget=w: self._move_rule_up(widget))
        w.down_btn.clicked.connect(lambda _=False, widget=w: self._move_rule_down(widget))
        # Insert before the stretch at the end
        self._rules_layout.insertWidget(self._rules_layout.count() - 1, w)
        self._rule_widgets.append(w)
        self._renumber()
        self._update_rule_move_buttons()

    def _add_empty_rule(self):
        self._add_rule_widget()

    def _remove_rule(self, widget):
        if widget in self._rule_widgets:
            self._rule_widgets.remove(widget)
            self._rules_layout.removeWidget(widget)
            widget.deleteLater()
            self._renumber()
            self._update_rule_move_buttons()

    def _rebuild_rules_layout(self):
        """Re-stack rule widgets in ``_rule_widgets`` order above the trailing stretch."""
        for w in self._rule_widgets:
            self._rules_layout.removeWidget(w)
        for w in self._rule_widgets:
            self._rules_layout.insertWidget(self._rules_layout.count() - 1, w)

    def _reorder_rule_to_index(self, source_index, target_index):
        """
        Move the rule at *source_index* so it ends up at *target_index* in the final list.

        *target_index* is the index in the **original** list (same coordinates as
        ``_rule_widgets`` before the move). For a one-step down, that is ``i + 1``;
        ``pop`` then ``insert`` with that index is correct (no extra decrement).
        """
        n = len(self._rule_widgets)
        if (
            source_index == target_index
            or source_index < 0
            or source_index >= n
            or target_index < 0
            or target_index >= n
        ):
            return
        w = self._rule_widgets.pop(source_index)
        self._rule_widgets.insert(target_index, w)
        self._rebuild_rules_layout()
        self._renumber()
        self._update_rule_move_buttons()

    def _move_rule_up(self, widget):
        i = self._rule_widgets.index(widget)
        self._reorder_rule_to_index(i, i - 1)

    def _move_rule_down(self, widget):
        i = self._rule_widgets.index(widget)
        self._reorder_rule_to_index(i, i + 1)

    def _update_rule_move_buttons(self):
        n = len(self._rule_widgets)
        for i, w in enumerate(self._rule_widgets):
            w.up_btn.setEnabled(i > 0)
            w.down_btn.setEnabled(i < n - 1)

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
