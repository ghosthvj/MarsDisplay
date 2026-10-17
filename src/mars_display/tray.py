"""Injectable Qt tray shell. No application entry point, browser, or USB I/O."""
from collections.abc import Callable

from PySide6.QtCore import QLockFile, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from .lifecycle import Coordinator, LifecycleError
from .presentation import window_stylesheet
from .settings import Settings, SettingsError, SettingsStore, SettingsStoreError


class SingleInstanceGuard:
    """Nonblocking per-settings-directory admission; retain until clean exit.

    Qt may recover a verifiably dead process lock. Age alone never makes a lock
    stale, and this class never forcibly removes a live owner's lock.
    """

    def __init__(self, store: SettingsStore):
        self.directory = store.path.parent
        self._lock = QLockFile(str(self.directory / "marsdisplay.lock"))
        self._lock.setStaleLockTime(0)
        self._held = False

    def acquire(self) -> bool:
        if self._held:
            return True
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise SettingsStoreError("Cannot create instance lock; check settings directory access.") from None
        self._held = self._lock.tryLock(0)
        if not self._held and self._lock.error() != QLockFile.LockError.LockFailedError:
            raise SettingsStoreError("Cannot acquire instance lock; check settings directory access.")
        return self._held

    def release(self) -> None:
        if self._held:
            self._lock.unlock()
            self._held = False


def create_shell(app: QApplication, store: SettingsStore,
                 coordinator_factory: Callable[[], Coordinator]) -> "TrayShell | None":
    """Acquire before invoking factory; None means already running (no worker).

    The caller owns reporting startup errors/already-running and entering exec().
    Invalid settings propagate unchanged, before coordinator creation. The factory
    must construct an idle Coordinator with this store and SimulatedTransport;
    it must not start capture. Retain the returned shell for the entire event loop.
    """
    guard = SingleInstanceGuard(store)
    if not guard.acquire():
        return None
    try:
        configured = store.load()
        return TrayShell(app, coordinator_factory(), configured, guard)
    except Exception:
        guard.release()
        raise


def _icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#218a9b"), 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(3, 4, 26, 18, 3, 3)
    painter.drawLine(16, 23, 16, 27)
    painter.drawLine(10, 28, 22, 28)
    painter.drawLine(8, 15, 13, 15)
    painter.drawLine(13, 15, 16, 10)
    painter.drawLine(16, 10, 19, 17)
    painter.drawLine(19, 17, 24, 17)
    painter.end()
    return QIcon(pixmap)


def _label(text: str = "", name: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setObjectName(name)
    return label


class SettingsDialog(QDialog):
    """Native window with a scrollable status body and an always-visible footer."""

    def __init__(self, configured: Settings | None):
        super().__init__()
        self.setWindowTitle("MarsDisplay — Status / Settings")
        self.setWindowIcon(_icon())
        self.setObjectName("statusWindow")
        self.setMinimumWidth(480)
        self.resize(650, min(870, max(400, self.screen().availableGeometry().height() - 48)))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("body")
        column = QVBoxLayout(body)
        column.setContentsMargins(30, 24, 30, 24)
        column.setSpacing(14)
        toolbar = QHBoxLayout()
        logo = _label()
        logo.setPixmap(self.windowIcon().pixmap(24, 24))
        logo.setFixedSize(24, 24)
        toolbar.addWidget(logo)
        toolbar.addWidget(_label("MarsDisplay", "sectionHeading"))
        toolbar.addStretch()
        self.theme_switch = QPushButton("Dark mode")
        self.theme_switch.setObjectName("themeSwitch")
        self.theme_switch.setCheckable(True)
        self.theme_switch.setAutoDefault(False)
        self.theme_switch.toggled.connect(self.set_dark_mode)
        toolbar.addWidget(self.theme_switch)
        column.addLayout(toolbar)
        self.window_heading = _label("Status / Settings", "windowHeading")
        column.addWidget(self.window_heading)
        column.addWidget(_label("Monitor your connection and configure MARS.", "muted"))
        self.runtime_card = QFrame()
        self.runtime_card.setObjectName("lifecycleCard")
        self.capture_row = QHBoxLayout(self.runtime_card)
        self.capture_row.setContentsMargins(20, 16, 20, 16)
        self.runtime = _label("stopped", "runtimeValue")
        runtime_text = QVBoxLayout()
        runtime_text.addWidget(_label("Capture lifecycle", "muted"))
        runtime_text.addWidget(self.runtime)
        self.capture_row.addLayout(runtime_text)
        self.capture_row.addStretch()
        column.addWidget(self.runtime_card)
        self.source = _label("stopped", "sourceBadge")
        self.source.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.output = _label("Simulated — simulated-closed (no USB output)")
        self.metadata = _label()
        self.frames = _label("0", "frames")
        details = QGridLayout()
        details.setColumnStretch(0, 2)
        details.setColumnStretch(1, 3)
        details.setHorizontalSpacing(20)
        details.setVerticalSpacing(12)
        for index, (title, widget) in enumerate((
            ("MARS source state", self.source), ("Output", self.output),
            ("Source metadata", self.metadata), ("Frames sent (lifetime)", self.frames),
        )):
            details.addWidget(_label(title, "muted"), index * 2, 0)
            details.addWidget(widget, index * 2, 1)
            line = QFrame()
            line.setObjectName("separator")
            line.setFixedHeight(1)
            details.addWidget(line, index * 2 + 1, 0, 1, 2)
        column.addLayout(details)
        column.addWidget(_label("Configuration", "sectionHeading"))
        column.addWidget(_label("MARS URL"))
        self.url = QLineEdit(configured.mars_url if configured else "")
        self.url.setAccessibleName("MARS URL")
        column.addWidget(self.url)
        device_card = QFrame()
        device_card.setObjectName("deviceCard")
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(18, 14, 18, 14)
        device_layout.addWidget(_label("Saved device identity · Read-only", "muted"))
        self.device = _label(configured.device_identity if configured and configured.device_identity
                             else "Not selected (hardware identification pending)")
        device_layout.addWidget(self.device)
        column.addWidget(device_card)
        self.message = _label()
        column.addWidget(self.message)
        column.addStretch()
        self.scroll_area.setWidget(body)
        outer.addWidget(self.scroll_area, 1)
        self.footer = QFrame()
        self.footer.setObjectName("footer")
        footer_row = QHBoxLayout(self.footer)
        footer_row.setContentsMargins(24, 16, 24, 16)
        self.hint = _label("Settings can be saved only while capture is stopped.", "hint")
        footer_row.addWidget(self.hint, 1)
        self.save = QPushButton("Save")
        footer_row.addWidget(self.save)
        outer.addWidget(self.footer)
        self.set_dark_mode(False)

    def set_dark_mode(self, dark: bool):
        self.setProperty("theme", "dark" if dark else "light")
        self.setStyleSheet(window_stylesheet(dark))
        self.theme_switch.setText("Light mode" if dark else "Dark mode")
        self.theme_switch.setAccessibleName(self.theme_switch.text())


class TrayShell(QObject):
    """UI-thread binding using only coordinator public operations and snapshots.

    Prefer create_shell() for lock-before-coordinator assembly. No join, browser
    call, output call, or implicit Start occurs here. Backend timeouts remain the
    source adapter's responsibility. Exit keeps the lock until exit_ready.
    """

    def __init__(self, app: QApplication, coordinator: Coordinator,
                 configured: Settings | None, guard: SingleInstanceGuard):
        super().__init__()
        self.app = app
        self.coordinator = coordinator
        self.guard = guard
        self.configured = configured
        app.setQuitOnLastWindowClosed(False)
        self.dialog = SettingsDialog(configured)
        self.menu = QMenu()
        self.settings_action = self.menu.addAction("Status / Settings")
        self.start_action = self.menu.addAction("Start")
        self.stop_action = self.menu.addAction("Stop")
        self.exit_action = self.menu.addAction("Exit")
        self.settings_action.triggered.connect(self.show_settings)
        self.start_action.triggered.connect(lambda: self._request(coordinator.start))
        self.stop_action.triggered.connect(lambda: self._request(coordinator.stop))
        self.exit_action.triggered.connect(lambda: self._request(coordinator.request_exit))
        self.dialog.save.clicked.connect(self._save)
        self.tray = QSystemTrayIcon(_icon(), self)
        self.tray.setToolTip("MarsDisplay — simulated output")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activate)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.refresh)
        self.refresh()
        self.tray.show()
        self.timer.start()

    def show_settings(self):
        self.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _activate(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings()

    def _request(self, operation):
        try:
            operation()
        except (LifecycleError, SettingsError) as error:
            self.dialog.message.setText(str(error))
            self.show_settings()
        self.refresh()

    def _save(self):
        try:
            # Coordinator remains the stopped-only authority even if a stale Qt
            # action was queued just before Start.
            settings = Settings(self.dialog.url.text(),
                                self.configured.device_identity if self.configured else None)
            self.coordinator.save_settings(settings)
        except (SettingsError, LifecycleError) as error:
            self.dialog.message.setText(str(error))
        else:
            self.configured = settings
            self.dialog.message.setText("Settings saved. Capture remains stopped.")
        self.refresh()

    def refresh(self):
        status = self.coordinator.snapshot()
        self.dialog.runtime.setText("recovering (retrying)" if status.state == "retrying" else status.state)
        self.dialog.source.setText(status.source_state)
        self.dialog.output.setText(f"Simulated — {status.output_state} (no USB output)")
        word = lambda value: "unknown" if value is None else "yes" if value else "no"
        self.dialog.metadata.setText(
            f"Live connected: {word(status.live_connected)}; data stale: {word(status.data_stale)}")
        self.dialog.frames.setText(str(status.frames_sent))
        idle = not status.worker_alive and not status.exit_requested
        # Only Coordinator knows whether an error permits retry or has a cleanup
        # latch. Let its public Start operation report the actionable rejection.
        self.start_action.setEnabled(idle and status.state in {"stopped", "error"})
        self.stop_action.setEnabled(not status.exit_requested and status.state != "stopping"
                                    and (status.worker_alive or status.state == "error"))
        self.exit_action.setEnabled(not status.exit_requested)
        self.dialog.save.setEnabled(idle and status.state == "stopped")
        if status.error:
            message = status.error
            if status.exit_requested and not status.worker_alive and not status.exit_ready:
                message += (" Exit is blocked: check owned browser/output resources; "
                            "resolve cleanup before restarting MarsDisplay. "
                            "Do not close your normal browser.")
            self.dialog.message.setText(message)
            if status.exit_requested:
                self.dialog.show()
        if status.exit_ready:
            self.timer.stop()
            self.tray.hide()
            self.dialog.hide()
            self.guard.release()
            self.app.quit()
