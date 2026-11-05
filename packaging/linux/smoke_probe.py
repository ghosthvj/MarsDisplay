"""Test-only frozen qualification. Never imported by the production entrypoint."""
import contextlib
import ctypes
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

HELP = 'Usage: SmokeProbe [--help]\nTest-only Linux nonroot Qt/browser qualification; no devices.\n'
PASS = 'PASS: Qt offscreen, platform dlopen, Node, sandboxed RGB capture, direct-child cleanup\n'
HTML = b'''<!doctype html><style>body{margin:0}#mars-display{width:320px;height:480px;background:rgb(17,34,51)}</style>
<div id="mars-display" data-display-version="1" data-display-state="ready"
 data-orientation="portrait" data-width="320" data-height="480"
 data-server-id="probe" data-live-connected="true" data-data-stale="false"></div>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML if self.path == '/display' else b''
        self.send_response(200 if body else 404)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

    def setup(self):
        self.request.settimeout(2)
        super().setup()


def capture(factory):
    from mars_display.settings import Settings
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    session = None
    try:
        thread.start()
        session = factory(Settings(f'http://127.0.0.1:{server.server_port}'))
        session.open()
        sample = session.read()
        frame = sample.frame
        if (sample.state != 'ready' or frame is None or
                (frame.width, frame.height) != (320, 480) or
                frame.rgb != bytes((17, 34, 51)) * (320 * 480)):
            raise RuntimeError('RGB frame mismatch')
    finally:
        try:
            if session is not None:
                session.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            if thread.is_alive():
                raise RuntimeError('HTTP thread cleanup failed')


def launch_failure(text):
    text = text.lower()
    if any(word in text for word in ('operation not permitted', 'permission denied', 'sandbox', 'namespace')):
        return 'browser permission/sandbox'
    if any(word in text for word in ('shared object', 'missing dependencies', "executable doesn't exist")):
        return 'browser package/dependencies'
    return 'browser launch unclassified'


def children():
    # Only this process's direct children across all threads; never host enumeration.
    return {pid for task in Path('/proc/self/task').iterdir()
            for pid in (task / 'children').read_text().split()}


def qualify():
    from PySide6.QtCore import QLibraryInfo
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    import playwright
    from playwright.sync_api import sync_playwright
    from mars_display.browser import BrowserSession

    baseline = children()
    app = QApplication([])
    try:
        if QGuiApplication.platformName() != 'offscreen':
            raise RuntimeError('Qt offscreen platform mismatch')
        platforms = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / 'platforms'
        for name in ('libqxcb.so', 'libqwayland.so'):
            try:
                ctypes.CDLL(str(platforms / name))
            except OSError as error:
                raise RuntimeError(f'Qt platform dependency: {name}: {error}') from None
        node = Path(playwright.__file__).parent / 'driver/node'
        result = subprocess.run([str(node), '--version'], capture_output=True, timeout=5)
        if result.returncode or not result.stdout.startswith(b'v'):
            raise RuntimeError('bundled Node execution failed')
        # Public diagnostic launch preserves sandboxing. BrowserSession deliberately
        # sanitizes launch errors, so it cannot distinguish policy from packaging.
        with sync_playwright() as driver:
            try:
                browser = driver.chromium.launch(headless=True, chromium_sandbox=True, timeout=5000)
            except Exception as error:
                raise RuntimeError(f'{launch_failure(str(error))}: {error}') from None
            browser.close()
        capture(BrowserSession)
    finally:
        app.quit()
        deadline = time.monotonic() + 3
        while children() - baseline and time.monotonic() < deadline:
            time.sleep(0.05)
        if children() - baseline:
            raise RuntimeError('direct-child cleanup failed')


@contextlib.contextmanager
def watchdog():
    def expired(*args):
        raise RuntimeError('probe watchdog expired')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(30)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args == ['--help']:
        print(HELP, end='')
        return 0
    if args:
        print(HELP, end='', file=sys.stderr)
        return 2
    if (sys.platform != 'linux' or not hasattr(os, 'getuid') or
            os.getuid() == 0 or os.geteuid() == 0):
        print('FAIL: Linux nonroot required', file=sys.stderr)
        return 2
    original = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory(prefix='mars-probe-') as directory, watchdog():
            root = Path(directory)
            for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_RUNTIME_DIR', 'TMPDIR'):
                path = root / key
                path.mkdir(mode=0o700)
                os.environ[key] = str(path)
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'PLAYWRIGHT_NODEJS_PATH'):
                os.environ.pop(key, None)
            os.environ.update(QT_QPA_PLATFORM='offscreen', PLAYWRIGHT_BROWSERS_PATH='0')
            sentinel = Path(os.environ['HOME']) / 'settings.json'
            sentinel.write_bytes(b'sentinel')
            try:
                qualify()
            finally:
                if sentinel.read_bytes() != b'sentinel':
                    raise RuntimeError('settings sentinel changed')
    except Exception as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1
    finally:
        os.environ.clear()
        os.environ.update(original)
    print(PASS, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
