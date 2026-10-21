"""Native console qualification using only HELLO/CLOSE and malformed IPC.

Never sends OPEN. Parent-death fixture is a build tool, not an executable route.
"""
import ctypes
from ctypes import wintypes
from importlib import util
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

from mars_display import usb_ipc as ipc
from mars_display.usb_grouping_experiment import HELP, INVALID, SELFTEST, worker_command
from mars_display.usb_process import OwnedWorker, WindowsGate


def _load(name):
    spec = util.spec_from_file_location('grouping_smoke_' + name, Path(__file__).with_name(name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = _load('usb_smoke')


def launch(executable, env, arm, port, nonce):
    # Use the production argument validator/vector, replacing only the launcher.
    args = worker_command(arm, 'COM5', port, nonce)[-5:]
    return subprocess.Popen([str(executable), *args], cwd=executable.parent, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)


def exchange(executable, env, arm, malformed=False):
    nonce = secrets.token_hex(32)
    with shared._listener() as listener:
        owner = OwnedWorker(listener.getsockname()[1], nonce, ipc.Budgets(),
            launcher=lambda port, token: launch(executable, env, arm, port, token))
        try:
            owner.start()
            owner.wait_start(time.monotonic() + 5, threading.Event())
            with listener.accept()[0] as channel:
                if ipc.receive_packet(channel, time.monotonic() + 5) != (ipc.HELLO, 0, bytes.fromhex(nonce)):
                    raise RuntimeError('Experimental worker handshake mismatch')
                if malformed:
                    channel.settimeout(2)
                    channel.sendall(ipc.HEADER.pack(b'MUSB', 1, ipc.FRAME, 0, 1, 0xffffffff))
                    if channel.recv(1) != b'' or owner.child.wait(timeout=2) != 1:
                        raise RuntimeError('Experimental malformed IPC rejection mismatch')
                else:
                    ipc.send_packet(channel, ipc.CLOSE, 1, b'', time.monotonic() + 2)
                    if ipc.receive_packet(channel, time.monotonic() + 2) != (ipc.REPLY, 1, b'\x00'):
                        raise RuntimeError('Experimental CLOSE mismatch')
                    if owner.child.wait(timeout=2) != 0:
                        raise RuntimeError('Experimental close exit mismatch')
        finally:
            owner.stop(time.monotonic() + 2)
        if not owner.closed:
            raise RuntimeError('Experimental ownership not released')


def held_gate(executable, env):
    nonce = secrets.token_hex(32)
    gate, child = WindowsGate(nonce), None
    gate.open()
    try:
        with shared._listener() as listener:
            child = launch(executable, env, 'A', listener.getsockname()[1], nonce)
            gate.assign(child)
            listener.settimeout(0.3)
            try:
                listener.accept()
            except TimeoutError:
                pass
            else:
                raise RuntimeError('Experimental worker connected before admission')
            if child.poll() is not None:
                raise RuntimeError('Experimental worker did not await admission')
            gate.close()
            child.wait(timeout=2)
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
            gate.close_process(child)
        gate.close()


def fixture_parent(executable, report):
    """Test-owned parent; no inventory and no device protocol operation."""
    shared.require_host()
    nonce = secrets.token_hex(32)
    with shared._listener() as listener:
        owner = OwnedWorker(listener.getsockname()[1], nonce, ipc.Budgets(),
            launcher=lambda port, token: launch(Path(executable), os.environ.copy(), 'B', port, token))
        try:
            owner.start()
            owner.wait_start(time.monotonic() + 5, threading.Event())
            with listener.accept()[0] as channel:
                if ipc.receive_packet(channel, time.monotonic() + 5) != (ipc.HELLO, 0, bytes.fromhex(nonce)):
                    raise RuntimeError('Parent fixture handshake mismatch')
                pending = Path(report).with_suffix('.pending')
                with pending.open('x') as stream:
                    stream.write(str(owner.child.pid))
                pending.rename(report)
                threading.Event().wait(30)
        finally:
            owner.stop(time.monotonic() + 2)
    return 0


def parent_death(executable, env, scratch):
    report = scratch / 'child.pid'
    parent_env = dict(env, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
    parent = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                               'parent', str(executable), str(report)], env=parent_env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    handle = None
    try:
        deadline = time.monotonic() + 10
        while not report.exists():
            if parent.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Experimental parent fixture admission failed')
            threading.Event().wait(0.01)
        text = report.read_text()
        if not text.isdigit():
            raise RuntimeError('Invalid owned child observation')
        handle = api.OpenProcess(0x100000, False, int(text))
        if not handle or api.WaitForSingleObject(handle, 0) != 0x102:
            raise RuntimeError('Cannot observe live experimental child')
        parent.kill()
        parent.wait(timeout=2)
        if api.WaitForSingleObject(handle, 2000) != 0:
            raise RuntimeError('Experimental child survived parent death')
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=2)
        if handle and not api.CloseHandle(handle):
            raise RuntimeError('Observer handle cleanup failed')


def check(folder, scratch):
    shared.require_host()
    folder, scratch = Path(folder).absolute(), Path(scratch).absolute()
    executable = folder / 'MarsDisplayGroupingExperiment.exe'
    if not executable.is_file() or executable.is_symlink():
        raise ValueError('Missing exact experimental console executable')
    env = shared._environment(scratch)
    cases = [([], 0, HELP), (['--help'], 0, HELP), (['--self-test'], 0, SELFTEST),
             (['--invalid'], 2, INVALID)]
    for args in (['--usb-worker'], ['--usb-worker=bad'], ['--grouping-worker'],
                 ['--grouping-worker=bad'], ['--grouping-worker', 'A', 'COM5', '0', 'a'*64],
                 ['--grouping-worker', 'A', 'COM5', '12345', secrets.token_hex(32)]):
        cases.append((args, 2, None))
    for args, code, text in cases:
        result = subprocess.run([str(executable), *args], cwd=folder, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        expected = b'' if text is None else (text + '\n').replace('\n', '\r\n').encode()
        if (result.returncode, result.stdout, result.stderr) != (code, expected, b''):
            raise RuntimeError('Experimental console streams/exit mismatch')
    for arm in ('A', 'B'):
        exchange(executable, env, arm)
        exchange(executable, env, arm, malformed=True)
    held_gate(executable, env)
    parent_death(executable, env, scratch)
    if any((scratch / name / 'MarsDisplay').exists() for name in ('local', 'roaming')):
        raise RuntimeError('Experimental smoke entered application settings')
    return dict(status='passed', scope='native console; no OPEN/device request',
                public_routes=4, private_rejections=6, hello_close='both arms',
                malformed_ipc='both arms', held_gate='passed', parent_death='passed', owned_reap='passed')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'parent':
        raise SystemExit(fixture_parent(*sys.argv[2:]))
    raise SystemExit(2)
