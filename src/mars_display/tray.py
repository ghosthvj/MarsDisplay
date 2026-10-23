"""Injectable Qt tray shell. No application entry point, browser, or USB I/O."""
from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QLockFile, QObject, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSlider, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from .lifecycle import Coordinator, LifecycleError
from .presentation import window_stylesheet
from .preview import FramePreviewDialog
from .status_label import StatusLabel
from .settings import (Settings, SettingsError, SettingsStore, SettingsStoreError,
                       NATIVE_IDENTITY, NATIVE_PROFILE, BRIGHTNESS_LEVELS)
from .devices import (enumerate_devices, select_device, DeviceInventoryError,
                      DeviceSelectionError)


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
    must construct an idle Coordinator with this store and an explicit output
    factory; it must not start capture. Retain the shell for the entire event loop.
    """
    guard = SingleInstanceGuard(store)
    if not guard.acquire():
        return None
    try:
        configured = store.load()
        return TrayShell(app, coordinator_factory(), configured, guard, store=store)
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


def _tone(label: QLabel, value: str):
    if label.property("tone") != value:
        label.setProperty("tone", value)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()


class NativeTimingDialog(QDialog):
    """Modeless view of existing timing text, with no capture or device ownership."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("MarsDisplay — Logs")
        self.setObjectName("logsWindow")
        self.setWindowIcon(parent.windowIcon())
        self.resize(650, min(600, max(300, self.screen().availableGeometry().height() - 64)))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("body")
        content = QVBoxLayout(body)
        self.empty = _label("No native timing is available. Start native USB capture to collect samples.")
        content.addWidget(self.empty)
        self.timing = _label()
        self.timing.hide()
        content.addWidget(self.timing)
        content.addStretch()
        self.scroll_area.setWidget(body)
        layout.addWidget(self.scroll_area, 1)
        self.close_action = QPushButton("Close")
        self.close_action.setAutoDefault(False)
        self.close_action.clicked.connect(self.hide)
        layout.addWidget(self.close_action, 0, Qt.AlignmentFlag.AlignRight)


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
        self.runtime = StatusLabel("stopped", "runtimeValue")
        runtime_text = QVBoxLayout()
        runtime_text.addWidget(_label("Capture lifecycle", "muted"))
        runtime_text.addWidget(self.runtime)
        self.capture_row.addLayout(runtime_text, 1)
        self.capture_action = QPushButton("Start capture")
        self.capture_action.setAutoDefault(False)
        self.capture_row.addWidget(self.capture_action)
        self.error_stop_action = QPushButton("Stop capture")
        self.error_stop_action.setAutoDefault(False)
        self.error_stop_action.hide()
        self.capture_row.addWidget(self.error_stop_action)
        column.addWidget(self.runtime_card)
        self.source = StatusLabel("stopped", "sourceBadge")
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
            ("Source metadata", self.metadata), ("Host-accepted frames (lifetime)", self.frames),
        )):
            details.addWidget(_label(title, "muted"), index * 2, 0)
            alignment = Qt.AlignmentFlag.AlignLeft if index == 0 else Qt.AlignmentFlag(0)
            details.addWidget(widget, index * 2, 1, alignment)
            line = QFrame()
            line.setObjectName("separator")
            line.setFixedHeight(1)
            details.addWidget(line, index * 2 + 1, 0, 1, 2)
        column.addLayout(details)
        self.logs_window = NativeTimingDialog(self)
        self.native_timing = self.logs_window.timing
        self.preview_action = QPushButton("Preview")
        self.preview_action.setAutoDefault(False)
        self.preview_action.setAccessibleName("Preview output frame")
        self.logs_action = QPushButton("Logs")
        self.logs_action.setAutoDefault(False)
        self.logs_action.setAccessibleName("Show native timing logs")
        column.addWidget(_label("Native USB brightness", "sectionHeading"))
        brightness_control = QWidget()
        brightness_control.setFixedWidth(320)
        brightness_layout = QVBoxLayout(brightness_control)
        brightness_layout.setContentsMargins(0, 0, 0, 0)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setAccessibleName("Brightness percentage")
        self.brightness.setRange(0, len(BRIGHTNESS_LEVELS) - 1)
        self.brightness.setPageStep(1)
        self.brightness.setTickInterval(1)
        self.brightness.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness.setTracking(False)
        self.brightness.setValue(BRIGHTNESS_LEVELS.index(configured.brightness_percent if configured else 100))
        brightness_layout.addWidget(self.brightness)
        levels = QHBoxLayout()
        for percent in BRIGHTNESS_LEVELS:
            label = _label(f"{percent}%")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            levels.addWidget(label)
            if percent != BRIGHTNESS_LEVELS[-1]:
                levels.addStretch(1)
        brightness_layout.addLayout(levels)
        column.addWidget(brightness_control, 0, Qt.AlignmentFlag.AlignHCenter)
        self.enable_brightness = QPushButton("Enable Brightness")
        self.enable_brightness.setAutoDefault(False)
        column.addWidget(self.enable_brightness, 0, Qt.AlignmentFlag.AlignLeft)
        # Retain the guarded recovery binding without exposing another UI control.
        self.restore_brightness = QPushButton("Restore settings from before brightness…", self)
        self.restore_brightness.setAutoDefault(False)
        self.restore_brightness.hide()
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
        column.addWidget(_label("Output mode (draft until Save)"))
        self.output_mode = QComboBox()
        self.output_mode.setAccessibleName("Output mode")
        self.output_mode.addItem("Simulation", "simulated")
        self.output_mode.addItem("Native USB", "native")
        column.addWidget(self.output_mode)
        column.addWidget(_label(f"Supported native profile: {NATIVE_PROFILE} · 320 × 480 portrait"))
        self.identity = QComboBox()
        self.identity.setAccessibleName("Opaque USB identity")
        column.addWidget(self.identity)
        self.refresh_devices = QPushButton("Refresh USB identities")
        self.export_settings = QPushButton("Export schema-1 settings…")
        self.restore_settings = QPushButton("Restore preserved schema-1 backup…")
        for button in (self.refresh_devices, self.export_settings, self.restore_settings):
            button.setAutoDefault(False)
            column.addWidget(button)
        column.addWidget(_label("Refresh is passive; it does not open a port. Save checks native availability again. "
                                "Drafts never change active output. Export does not change saved settings."))
        self.load_configuration(configured)
        self.message = _label()
        self.message_kind = ""
        self.message.hide()
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
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.logs_action)
        actions.addWidget(self.preview_action)
        actions.addSpacing(12)
        actions.addWidget(self.save)
        footer_row.addLayout(actions)
        outer.addWidget(self.footer)
        self.set_dark_mode(False)

    def load_configuration(self, configured):
        self.url.setText(configured.mars_url if configured else "")
        self.device.setText(configured.device_identity if configured and configured.device_identity
                            else "Not selected (hardware identification pending)")
        native = configured is not None and configured.output_mode == "native"
        self.output_mode.setCurrentIndex(1 if native else 0)
        self.identity.clear()
        self.identity.addItem("Select an explicit USB identity", None)
        # Only an explicit schema-2 native selection may initialize this draft.
        if native:
            self.identity.addItem(configured.device_identity, configured.device_identity)
            self.identity.setCurrentIndex(1)

    def show_message(self, text: str, kind: str = "error"):
        self.message_kind = kind if text else ""
        self.message.setText(text)
        self.message.setVisible(bool(text))
        _tone(self.message, "success" if kind == "saved" else "error")

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
                 configured: Settings | None, guard: SingleInstanceGuard, *,
                 store: SettingsStore | None = None):
        super().__init__()
        self.app = app
        self.coordinator = coordinator
        self.guard = guard
        self.configured = configured
        self.store = store
        self._inventory = None
        app.setQuitOnLastWindowClosed(False)
        self.dialog = SettingsDialog(configured)
        self.preview = None
        self.dialog.preview_action.clicked.connect(self.show_preview)
        self.dialog.logs_action.clicked.connect(self.show_logs)
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
        self.dialog.refresh_devices.clicked.connect(self._refresh_devices)
        self.dialog.export_settings.clicked.connect(self._export)
        self.dialog.restore_settings.clicked.connect(self._restore)
        self.dialog.enable_brightness.clicked.connect(self._enable_brightness)
        self.dialog.restore_brightness.clicked.connect(self._restore_brightness)
        self.dialog.brightness.valueChanged.connect(self._brightness_changed)
        self._capture_intent = None
        self.dialog.capture_action.pressed.connect(self._capture_pressed)
        self.dialog.capture_action.clicked.connect(self._capture_request)
        self.dialog.error_stop_action.clicked.connect(self.stop_action.trigger)
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

    def show_preview(self):
        status = self.coordinator.snapshot()
        if status.exit_requested:
            return
        if self.preview is None:
            self.preview = FramePreviewDialog(self.dialog)
        self.preview.show()
        self.preview.update_snapshot(status)
        self.preview.raise_()
        self.preview.activateWindow()

    def show_logs(self):
        if self.coordinator.snapshot().exit_requested:
            return
        self.refresh()
        self.dialog.logs_window.show()
        self.dialog.logs_window.raise_()
        self.dialog.logs_window.activateWindow()


    def _activate(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings()

    def _capture_pressed(self):
        # Preserve intent across worker state changes between press and release.
        self._capture_intent = (
            self.stop_action if self.dialog.capture_action.property("operation") == "stop"
            else self.start_action)

    def _capture_request(self):
        action, self._capture_intent = self._capture_intent, None
        if action is not None and action.isEnabled():
            action.trigger()

    def _request(self, operation):
        try:
            operation()
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
            self.show_settings()
        self.refresh()

    def _configuration_guard(self):
        status = self.coordinator.snapshot()
        if status.state != "stopped" or status.worker_alive or status.exit_requested:
            raise LifecycleError("Settings can be saved only while stopped.")

    def _confirm(self, title, text):
        box = QMessageBox(self.dialog)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setEscapeButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _refresh_devices(self):
        try:
            self._configuration_guard()
            self._inventory = enumerate_devices()
            self.dialog.identity.clear()
            self.dialog.identity.addItem("Select an explicit USB identity", None)
            for item in self._inventory:
                if item.identity == NATIVE_IDENTITY:
                    self.dialog.identity.addItem(item.identity, item.identity)
            self.dialog.show_message("USB identities refreshed. Select explicitly; Save rechecks availability.", "saved")
        except (LifecycleError, DeviceInventoryError) as error:
            self._inventory = None
            self.dialog.show_message(str(error))
        self.refresh()

    def _export(self):
        try:
            self._configuration_guard()
            destination, _ = QFileDialog.getSaveFileName(
                self.dialog, "Export schema-1 settings (new file only)", "", "JSON files (*.json)")
            if destination:
                self.coordinator.export_schema1_settings(destination)
                self.dialog.show_message("Schema-1 settings exported. Saved settings are unchanged.", "saved")
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
        self.refresh()

    def _restore(self):
        try:
            self._configuration_guard()
            if self._confirm("Restore schema 1", "Replace current settings with the preserved schema-1 backup? "
                             "This restores Simulation and the original URL and identity. Capture will remain stopped."):
                self.coordinator.restore_schema1_settings()
                if self.store is not None:
                    self.configured = self.store.load()
                    self._inventory = None
                    self.dialog.load_configuration(self.configured)
                self.dialog.show_message("Schema-1 backup restored. Capture remains stopped.", "saved")
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
        self.refresh()

    def _enable_brightness(self):
        try:
            self._configuration_guard()
            if self._confirm("Enable saved brightness", "Schema 3 is incompatible with older binaries. "
                             "The saved configuration will be backed up before replacement; unsaved drafts are not included. "
                             "Brightness starts at 100% and is applied only after Start. Enable it?"):
                self.configured = self.coordinator.enable_brightness(acknowledge_legacy_incompatibility=True)
                self.dialog.show_message("Saved brightness enabled. Capture remains stopped.", "saved")
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
        self.refresh()

    def _restore_brightness(self):
        try:
            self._configuration_guard()
            if self._confirm("Restore pre-brightness settings", "Replace current settings with the exact preserved "
                             "configuration from before brightness was enabled? Later settings changes will be lost. "
                             "Capture will remain stopped."):
                self.coordinator.restore_pre_brightness_settings()
                self.configured = self.store.load()
                self._inventory = None
                self.dialog.load_configuration(self.configured)
                self.dialog.show_message("Pre-brightness settings restored. Capture remains stopped.", "saved")
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
        self.refresh()

    def _brightness_changed(self, position):
        try:
            self.configured = self.coordinator.set_brightness(BRIGHTNESS_LEVELS[position])
        except (LifecycleError, SettingsError) as error:
            self.dialog.show_message(str(error))
        self.refresh()

    def _save(self):
        try:
            # Coordinator remains the stopped-only authority even if a stale Qt
            # action was queued just before Start.
            self._configuration_guard()
            settings = (replace(self.configured, mars_url=self.dialog.url.text())
                        if self.configured is not None else Settings(self.dialog.url.text()))
            if self.dialog.output_mode.currentData() == "native":
                identity = self.dialog.identity.currentData()
                if self._inventory is not None or identity is None:
                    select_device(self._inventory or (), identity)
                settings = replace(settings, schema_version=max(2, settings.schema_version), output_mode="native",
                                   device_identity=identity, native_profile=NATIVE_PROFILE)
            else:
                settings = replace(settings, output_mode="simulated", native_profile=None)
            if settings.schema_version == 2 and (self.configured is None or self.configured.schema_version == 1):
                if not self._confirm("Migrate to schema 2", "Schema 2 is incompatible with older binaries. "
                                     "The original schema-1 settings will be preserved as a backup before replacement. "
                                     "Use explicit export or restore for older binaries. Migrate and save?"):
                    return
                self.coordinator.migrate_settings(settings, acknowledge_legacy_incompatibility=True)
            else:
                self.coordinator.save_settings(settings)
        except (SettingsError, LifecycleError, DeviceSelectionError) as error:
            self.dialog.show_message(str(error))
        else:
            self.configured = settings
            self.dialog.device.setText(settings.device_identity or "Not selected (hardware identification pending)")
            self.dialog.show_message("Settings saved. Capture remains stopped.", "saved")
        self.refresh()

    def refresh(self):
        status = self.coordinator.snapshot()
        self.dialog.preview_action.setEnabled(not status.exit_requested)
        self.dialog.logs_action.setEnabled(not status.exit_requested)
        if status.exit_requested:
            self.dialog.logs_window.hide()
        if self.preview is not None:
            if status.exit_requested:
                self.preview.hide()
            elif self.preview.isVisible():
                self.preview.update_snapshot(status)
        self.dialog.runtime.set_state(status.state)
        self.dialog.source.set_state(status.source_state)
        native = status.output_mode == "native"
        self.dialog.output.setText(
            f"Native USB — {status.output_state} (host completion, not panel acknowledgement)" if native
            else f"Simulated — {status.output_state} (no USB output)")
        self.tray.setToolTip(f"MarsDisplay — {'native' if native else 'simulated'} output")
        word = lambda value: "unknown" if value is None else "yes" if value else "no"
        self.dialog.metadata.setText(
            f"Live connected: {word(status.live_connected)}; data stale: {word(status.data_stale)}")
        self.dialog.frames.setText(f"{status.frames_sent:,}")
        report = status.native_timing if native else None
        timing_lines = []
        if report is not None:
            timing_lines.append("Native timing — current/last Start; successful samples only (ms)")
            for title, aggregate in (
                ("Source read (observations)", report.source_read),
                ("Host send (encoding / IPC / helper total)", report.host_send),
                ("Cadence wait (non-cancelled)", report.cadence_wait),
                ("Helper frame decode (ms)", report.decode),
                ("Helper identity resolution (ms)", report.identity),
                ("Helper RGB565 encode (ms)", report.encode),
                ("Helper packet writes (ms)", report.write),
                ("Helper queue drain (ms)", report.drain),
                ("Host IPC body encode (ms)", report.body_encode),
                ("Host exchange (includes helper work) (ms)", report.exchange),
                ("Helper orientation write (ms)", report.orientation),
                ("Helper bitmap-header write (ms)", report.header),
                ("Helper pixel writes (ms)", report.pixels),
            ):
                if title.endswith("(ms)") and not aggregate.count:
                    timing_lines.append(f"{title}: unavailable (count 0)")
                    continue
                values = [f"{value * 1000:.3f}" if aggregate.count else "—"
                          for value in (aggregate.latest, aggregate.minimum,
                                        aggregate.maximum, aggregate.mean)]
                timing_lines.append(
                    f"{title}: count {aggregate.count}; last {values[0]}; min {values[1]}; "
                    f"max {values[2]}; mean {values[3]}")
            timing_lines.append("Write groups are subsets of total packet writes, not additional costs.")
            timing_lines.append("Host send is not isolated serial write/drain or panel rendering. "
                                "Counts are independent, not panel FPS.")
            timing_lines.append("Host exchange includes helper work; do not add exchange and helper stages as separate costs.")
        self.dialog.native_timing.setText("\n".join(timing_lines))
        self.dialog.native_timing.setVisible(report is not None)
        self.dialog.logs_window.empty.setVisible(report is None)
        _tone(self.dialog.source, "success" if status.source_state == "ready" else
              "error" if status.source_state == "error" else
              "warning" if status.source_state == "loading" else "muted")
        _tone(self.dialog.runtime, "active" if status.state == "running" else
              "error" if status.state == "error" else
              "muted" if status.state == "stopped" else "warning")
        idle = not status.worker_alive and not status.exit_requested
        # Only Coordinator knows whether an error permits retry or has a cleanup
        # latch. Let its public Start operation report the actionable rejection.
        self.start_action.setEnabled(idle and status.state in {"stopped", "error"})
        self.stop_action.setEnabled(not status.exit_requested and status.state != "stopping"
                                    and (status.worker_alive or status.state == "error"))
        self.exit_action.setEnabled(not status.exit_requested)
        can_save = idle and status.state == "stopped"
        configured_native = self.configured is not None and self.configured.output_mode == "native"
        brightness_enabled = configured_native and self.configured.schema_version == 3
        self.dialog.brightness.setEnabled(bool(brightness_enabled and not status.exit_requested
            and not status.ownership_uncertain and status.state in {"stopped", "starting", "running"}))
        self.dialog.enable_brightness.setVisible(bool(configured_native and not brightness_enabled))
        self.dialog.enable_brightness.setEnabled(bool(can_save and configured_native and not brightness_enabled))
        self.dialog.restore_brightness.setEnabled(bool(can_save and self.store is not None
            and self.configured is not None and self.configured.schema_version == 3))
        value = self.configured.brightness_percent if self.configured else 100
        if not self.dialog.brightness.isSliderDown():
            self.dialog.brightness.blockSignals(True)
            self.dialog.brightness.setValue(BRIGHTNESS_LEVELS.index(value))
            self.dialog.brightness.blockSignals(False)
        self.dialog.save.setEnabled(can_save)
        self.dialog.url.setReadOnly(not can_save)
        for widget in (self.dialog.output_mode, self.dialog.identity, self.dialog.refresh_devices,
                       self.dialog.export_settings, self.dialog.restore_settings):
            widget.setEnabled(can_save)
        self.dialog.restore_settings.setEnabled(can_save and self.store is not None)
        stopping = status.worker_alive or status.state not in {"stopped", "error"}
        action = self.stop_action if stopping else self.start_action
        self.dialog.capture_action.setProperty("operation", "stop" if stopping else "start")
        self.dialog.capture_action.setText("Stop capture" if stopping else "Start capture")
        self.dialog.capture_action.setEnabled(action.isEnabled())
        # Idle errors offer both deliberate retry and Stop-to-edit, like the tray.
        self.dialog.error_stop_action.setVisible(idle and status.state == "error")
        self.dialog.error_stop_action.setEnabled(self.stop_action.isEnabled())
        if status.exit_requested:
            hint = "Exiting. Waiting for owned resources."
        elif can_save:
            hint = "Capture is stopped. Settings can be saved."
        elif status.state == "stopping":
            hint = "Stopping capture. Waiting for owned resources."
        elif status.state == "error":
            hint = "Capture is in error. Use Stop capture to edit settings."
        else:
            hint = f"Capture is {status.state}. Stop capture to save changes."
        self.dialog.hint.setText(hint)
        if status.error:
            message = status.error
            if status.exit_requested and not status.worker_alive and not status.exit_ready:
                message += (" Exit is blocked: check owned browser/output resources; "
                            "resolve cleanup before restarting MarsDisplay. "
                            "Do not close your normal browser.")
            self.dialog.show_message(message, "runtime")
            if status.exit_requested:
                self.dialog.show()
        elif self.dialog.message_kind == "runtime" or (
                self.dialog.message_kind == "saved" and status.state != "stopped"):
            self.dialog.show_message("")
        if status.exit_ready:
            self.timer.stop()
            self.tray.hide()
            self.dialog.hide()
            self.guard.release()
            self.app.quit()
