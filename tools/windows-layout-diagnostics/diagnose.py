"""Capture the existing failing fixture, not the user's settings or hardware.

Run from the repository root with PYTHONPATH=src:tests (src;tests on Windows)
and QT_QPA_PLATFORM=offscreen. Exit status preserves the seven UI test results.
The JSON/PNG are diagnostic evidence, never executable qualification.
"""
import json
import os
from pathlib import Path
import sys
import unittest

from PySide6.QtCore import QPoint, QRect, qVersion
from PySide6.QtGui import QFontInfo

import test_fixed_native_settings_ui as cases
import test_tray as fixture
from mars_display.settings import Settings

OUTPUT = Path('build/windows-layout-diagnostics')
TARGET = 'test_small_desktop_scrolls_content_without_moving_footer'


def margins(layout):
    value = layout.contentsMargins()
    return value.left(), value.top(), value.right(), value.bottom()


def layout_tree(layout, path='body'):
    """Use public layout metrics, including each minimum-width contribution."""
    records = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        name = f'{path}/{index}'
        widget = item.widget()
        child = item.layout()
        record = {
            'path': name, 'kind': type(widget or child).__name__,
            'minimum': item.minimumSize().toTuple(),
            'size_hint': item.sizeHint().toTuple(),
            'geometry': item.geometry().getRect(),
        }
        if widget is not None:
            font = QFontInfo(widget.font())
            metrics = widget.fontMetrics()
            record.update(
                object_name=widget.objectName(), visible=widget.isVisible(),
                text=widget.text() if hasattr(widget, 'text') else '',
                minimum_hint=widget.minimumSizeHint().toTuple(),
                explicit_minimum=widget.minimumSize().toTuple(),
                font_family=font.family(), font_pixels=font.pixelSize(),
                font_average_width=metrics.averageCharWidth(),
                font_maximum_width=metrics.maxWidth(),
                height_for_width=widget.heightForWidth(widget.width()),
            )
            child = widget.layout()
        if child is not None:
            record.update(margins=margins(child), spacing=child.spacing())
        records.append(record)
        if child is not None:
            records.extend(layout_tree(child, name))
    return records


class DiagnosticCase(cases.FixedNativeSettingsTests):
    def tearDown(self):
        try:
            if self._testMethodName == TARGET and self.shell is not None:
                self.capture_layout()
        finally:
            super().tearDown()

    def capture_layout(self):
        dialog = self.shell.dialog
        area = dialog.scroll_area
        snapshot = self.shell.coordinator.snapshot()
        safety = {
            'settings_unchanged': self.store.load() == Settings('https://mars.example', 'opaque-device'),
            'capture_not_opened': not self.session.opened.is_set(),
            'worker_not_alive': not snapshot.worker_alive,
            'coordinator_stopped': snapshot.state == 'stopped',
        }
        assert all(safety.values()), safety
        rows = layout_tree(dialog.body.layout())
        assert len(rows) <= 400, 'Unexpected diagnostic scope'
        report = {
            'diagnostic_only': True, 'source_commit': os.environ.get('GITHUB_SHA'),
            'python': sys.version, 'platform': sys.platform, 'qt': qVersion(),
            'qt_platform': fixture.APP.platformName(), 'style': fixture.APP.style().objectName(),
            'fixture': TARGET, 'safety': safety,
            'body': dialog.body.size().toTuple(),
            'body_minimum': dialog.body.minimumSizeHint().toTuple(),
            'body_margins': margins(dialog.body.layout()),
            'viewport': area.viewport().size().toTuple(),
            'horizontal_range': area.horizontalScrollBar().maximum(),
            'vertical_range': area.verticalScrollBar().maximum(),
            'frame': dialog.frameGeometry().getRect(),
            'footer': QRect(dialog.footer.mapToGlobal(QPoint()), dialog.footer.size()).getRect(),
            'rows': rows,
        }
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'layout.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert dialog.grab().save(str(OUTPUT / 'layout.png')), 'Screenshot was not saved'
        print(json.dumps({key: report[key] for key in ('body', 'body_minimum', 'viewport',
                                                       'horizontal_range', 'safety')}), flush=True)
        for row in sorted(rows, key=lambda row: row['minimum'][0], reverse=True)[:12]:
            print(json.dumps(row), flush=True)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticCase))
    code = 0 if result.wasSuccessful() and not result.skipped else 1
    summary = dict(diagnostic_only=True, tests_run=result.testsRun, test_exit_code=code,
                   failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))
    (OUTPUT / 'test-result.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
