"""Bounded native startup check of an unpacked executable, never source main.

No production URL/USB/control endpoint. This does not exercise packaged Exit,
LAN capture or Windows 11 acceptance. Only the owned idle process is terminated.
"""
import argparse
import ctypes
from ctypes import wintypes
from importlib import util
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tempfile
import time


def require_host():
    if sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'} or struct.calcsize('P') != 8:
        raise RuntimeError('Packaged smoke requires native Windows x64')


def environment(root, inherited=None):
    """Allowlist OS essentials, not build-machine Python/Qt/plugin/PATH state."""
    inherited = os.environ if inherited is None else inherited
    allowed = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'SYSTEMDRIVE'}
    env = {key: value for key, value in inherited.items() if key.upper() in allowed}
    windows = next((value for key, value in env.items() if key.upper() == 'SYSTEMROOT'), None)
    if not windows:
        raise RuntimeError('Missing Windows system root')
    env['PATH'] = str(Path(windows) / 'System32')
    for key, directory in (('LOCALAPPDATA', 'local'), ('APPDATA', 'roaming'), ('HOME', 'home'),
                           ('USERPROFILE', 'home'), ('TEMP', 'temp'), ('TMP', 'temp')):
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env['PLAYWRIGHT_BROWSERS_PATH'] = '0'
    return env


def native_ready(process, lock_path):
    """Require owned held lock, an idle GUI queue, and no visible error dialog."""
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    valid, pid, _, _ = lock.getLockInfo()
    if not valid or pid != process.pid:
        return False
    if lock.tryLock(0):
        lock.unlock()
        return False
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.WaitForInputIdle.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    user32.WaitForInputIdle.restype = wintypes.DWORD
    if user32.WaitForInputIdle(int(process._handle), 100) != 0:
        return False
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                          wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                          ctypes.POINTER(ctypes.c_size_t)]
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    visible, owned = [], []
    @callback_type
    def visit(window, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == process.pid:
            owned.append(window)
            if user32.IsWindowVisible(window):
                visible.append(window)
        return True
    if not user32.EnumWindows(visit, 0):
        raise RuntimeError('Cannot inspect owned GUI readiness')
    if visible or not owned:
        return False
    # WaitForInputIdle is a startup signal only. A bounded WM_NULL round trip
    # also proves the owned GUI thread actually dispatches messages now.
    result = ctypes.c_size_t()
    if not all(user32.SendMessageTimeoutW(window, 0, 0, 0, 2, 100, ctypes.byref(result))
               for window in owned):
        return False
    return process.poll() is None


def startup(folder, scratch, *, popen=None, seconds=20):
    require_host()
    if not 0 < seconds <= 60:
        raise ValueError('Startup deadline must be positive and at most 60 seconds')
    env = environment(scratch)
    process = (subprocess.Popen if popen is None else popen)(
        [str(folder / 'MarsDisplay.exe')], cwd=folder, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + seconds
        lock = scratch / 'local/MarsDisplay/marsdisplay.lock'
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Packaged executable exited before readiness')
            if native_ready(process, lock):
                if (scratch / 'local/MarsDisplay/settings.json').exists():
                    raise RuntimeError('Idle startup unexpectedly saved settings')
                return
            time.sleep(0.05)
        raise RuntimeError('Packaged startup readiness unavailable before deadline (tray, lock or GUI)')
    finally:
        if process.poll() is None:
            process.terminate()  # Only this invocation's unconfigured, idle process.
        process.wait(timeout=5)


def check(folder, scratch):
    require_host()
    spec = util.spec_from_file_location('marsdisplay_payload_smoke', Path(__file__).with_name('payload.py'))
    payload = util.module_from_spec(spec)
    spec.loader.exec_module(payload)
    folder = Path(folder).absolute()
    runtime = payload.read_tree(folder)
    payload._layout(runtime)
    import json
    registry = json.loads(runtime['_internal/playwright/driver/package/browsers.json'])
    commands = {'Node': ('_internal/playwright/driver/node.exe', '--version')}
    for name, label, option in (('chromium-headless-shell', 'Chromium', '--version'), ('ffmpeg', 'FFmpeg', '-version')):
        matches = [item for item in registry['browsers'] if item['name'] == name]
        if len(matches) != 1:
            raise ValueError('Missing exact browser registry entry')
        commands[label] = (payload.browser_executable(runtime, name, matches[0]['revision']), option)
    env = environment(scratch)
    measured = {}
    for label, (name, option) in commands.items():
        result = subprocess.run([str(folder / name), option], cwd=folder, env=env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=10)
        lines = (result.stdout + result.stderr).strip().splitlines()
        if not lines or not lines[0].strip():
            raise RuntimeError('Missing packaged ' + label + ' version output')
        measured[label] = lines[0].strip()
        if label == 'Node' and not measured[label].startswith('v'):
            raise RuntimeError('Unexpected packaged Node version output')
        if label == 'Chromium':
            expected = next(item.get('browserVersion') for item in registry['browsers'] if item['name'] == 'chromium-headless-shell')
            if not expected or expected not in measured[label]:
                raise RuntimeError('Packaged Chromium version does not match registry')
        if label == 'FFmpeg' and not measured[label].lower().startswith('ffmpeg version '):
            raise RuntimeError('Unexpected packaged FFmpeg version output')
    startup(folder, scratch)
    return measured


def main(argv=None):
    parser = argparse.ArgumentParser(description='Native Windows x64 smoke of an unpacked MarsDisplay folder; no capture or normal Exit acceptance.')
    parser.add_argument('folder', type=Path, help='Unpacked built folder below repository build/ or dist/')
    args = parser.parse_args(argv)
    try:
        require_host()
        repo = Path(__file__).absolute().parents[1]
        folder = args.folder.absolute()
        if not any(folder.resolve().is_relative_to(repo / directory) for directory in ('build', 'dist')):
            raise ValueError('Smoke input must be below repository build/ or dist/')
        work = repo / 'build'
        if work.is_symlink():
            raise ValueError('Symlink build directory')
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='smoke-', dir=work) as scratch:
            check(folder, Path(scratch))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Packaged smoke failed: ' + str(error), file=sys.stderr)
        return 1
    print('Packaged native startup and binary versions passed; T6 acceptance remains deferred.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
