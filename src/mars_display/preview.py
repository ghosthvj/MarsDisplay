"""UI-thread observer of accepted output frames; no capture, files or device I/O."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QScrollArea, QVBoxLayout

from .lifecycle import Snapshot


class FramePreviewDialog(QDialog):
    """One modeless, unscaled RGB view; retain no image history or hidden pixmap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MarsDisplay — Output preview")
        self.setObjectName("previewWindow")
        if parent is not None:
            self.setWindowIcon(parent.windowIcon())
        self.resize(540, min(700, max(300, self.screen().availableGeometry().height() - 64)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.image = QLabel()
        self.image.setTextFormat(Qt.TextFormat.PlainText)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setScaledContents(False)
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image)
        layout.addWidget(self.scroll_area, 1)
        note = QLabel("Latest frame accepted by simulated output, not USB reception.\n"
                      "Retained when no new frame arrives; no image history is saved.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        # Keep the output/retention boundary visible alongside current status.
        self.note = note
        close = QPushButton("Close")
        close.setAutoDefault(False)
        close.clicked.connect(self.hide)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self._frame = None
        self.update_snapshot(Snapshot())

    def update_snapshot(self, status: Snapshot):
        frame = status.latest_frame
        if frame is None:
            self._frame = None
            self.image.setText("No frame has been delivered yet.\nStart capture to see the output preview.")
            self.image.setFixedSize(300, 100)
        elif frame is not self._frame:
            # Own the Qt bytes; never lend a temporary Python buffer to painting.
            image = QImage(frame.rgb, frame.width, frame.height, frame.width * 3,
                           QImage.Format.Format_RGB888).copy()
            self.image.setPixmap(QPixmap.fromImage(image))
            self.image.setFixedSize(frame.width, frame.height)
            self._frame = frame
        geometry = f"{frame.width} × {frame.height} · RGB888" if frame else "No accepted frame"
        word = lambda value: "unknown" if value is None else "yes" if value else "no"
        self.details.setText(
            f"{geometry} · Frame {status.frames_sent:,}\n"
            f"Capture: {status.state}; Source: {status.source_state}\n"
            f"Live connected: {word(status.live_connected)}; data stale: {word(status.data_stale)}")

    def hideEvent(self, event):
        self._frame = None
        self.image.clear()
        super().hideEvent(event)
