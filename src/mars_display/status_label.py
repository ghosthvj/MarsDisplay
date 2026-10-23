"""Presentation-only state labels with font-independent vector icons."""
from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel


class StatusLabel(QLabel):
    """Keep backend state strings untouched; animate only visible loading icons."""

    def __init__(self, state: str, name: str):
        super().__init__()
        self.setObjectName(name)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setContentsMargins(24, 0, 0, 0)
        self._angle = 0
        self._icon = "Empty"
        self._timer = QTimer(self)
        self._timer.setInterval(75)
        self._timer.timeout.connect(self._advance)
        self.set_state(state)

    def set_state(self, state: str):
        title = "Recovering (retrying)" if state == "retrying" else state.capitalize()
        self.setText(title)
        self.setAccessibleName(title)
        self._icon = {
            "running": "Lightning", "stopped": "Stop", "ready": "Check",
            "error": "Warning", "starting": "Loading", "stopping": "Loading",
            "retrying": "Loading", "loading": "Loading",
        }.get(state, "Empty")
        self.setAccessibleDescription(self._icon + " icon")
        self._sync_animation()
        self.update()

    def _sync_animation(self):
        if self._icon == "Loading" and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(3, (self.height() - 18) / 2)
        color = self.palette().color(self.foregroundRole())
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if self._icon == "Lightning":
            bolt = QPainterPath()
            bolt.moveTo(11, 1)
            for x, y in ((3, 10), (8, 10), (6, 17), (15, 7), (10, 7)):
                bolt.lineTo(x, y)
            bolt.closeSubpath()
            painter.fillPath(bolt, color)
        elif self._icon == "Stop":
            painter.fillRect(QRectF(3, 3, 12, 12), color)
        elif self._icon == "Check":
            tick = QPainterPath()
            tick.moveTo(2, 9)
            tick.lineTo(7, 14)
            tick.lineTo(16, 4)
            painter.drawPath(tick)
        elif self._icon == "Warning":
            triangle = QPainterPath()
            triangle.moveTo(9, 1)
            triangle.lineTo(17, 16)
            triangle.lineTo(1, 16)
            triangle.closeSubpath()
            painter.drawPath(triangle)
            painter.drawLine(9, 6, 9, 10)
            painter.drawPoint(9, 13)
        elif self._icon == "Loading":
            painter.drawArc(QRectF(2, 2, 14, 14), -self._angle * 16, 270 * 16)
        else:
            painter.drawEllipse(QRectF(3, 3, 12, 12))
        painter.end()
