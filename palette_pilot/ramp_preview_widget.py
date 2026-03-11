# -*- coding: utf-8 -*-
"""
Widget that draws a horizontal preview of a QgsColorRamp.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPainter, QLinearGradient
from qgis.PyQt.QtWidgets import QWidget

# Number of steps to sample the ramp for a smooth gradient
_PREVIEW_STEPS = 64


class RampPreviewWidget(QWidget):
    """Paints a horizontal strip showing the current colour ramp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ramp = None
        self.setMinimumHeight(24)
        self.setMaximumHeight(40)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )

    def set_ramp(self, ramp):
        """Set the ramp to display (QgsColorRamp or None). Triggers repaint."""
        self._ramp = ramp
        self.update()

    def paintEvent(self, event):
        if not self._ramp:
            return
        painter = QPainter(self)
        r = self.rect()
        if r.width() <= 0 or r.height() <= 0:
            painter.end()
            return
        gradient = QLinearGradient(r.left(), 0, r.right(), 0)
        for i in range(_PREVIEW_STEPS + 1):
            t = i / _PREVIEW_STEPS
            color = self._ramp.color(t)
            if color.isValid():
                gradient.setColorAt(t, color)
        painter.fillRect(r, gradient)
        painter.end()
