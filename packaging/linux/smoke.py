"""External no-USB qualification runner; never bundled into production."""
import argparse
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import tempfile
import threading
import time


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def quiet(command, expected, **options):
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    try:
        out, err = child.communicate(timeout=4)
        require((child.returncode, out, err) == (expected, b'', b''), 'Private CLI was not quiet')
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)


def listener():
    channel = socket.socket()
    channel.bind(('127.0.0.1', 0))
    channel.listen(1)
    channel.settimeout(4)
    return channel


def admitted(executable, wrong_identity):
    from mars_display import usb_ipc as ipc
    from mars_display.linux_usb_process import OwnedWorker
    from mars_display.usb_worker import OK, IDENTITY_ERROR

    nonce = secrets.token_hex(32)
    with listener() as server:
        owner = OwnedWorker(server.getsockname()[1], nonce, ipc.Budgets(start=4, reap=2),
            launcher=lambda port, token, fd, parent, deadline: [str(executable),
                '--linux-usb-worker', str(port), token, str(fd), str(parent), str(deadline)])
        try:
            owner.start()
            owner.wait_start(time.monotonic() + 4, threading.Event())
            with server.accept()[0] as channel:
                deadline = time.monotonic() + 4
                require(ipc.receive_packet(channel, deadline) ==
                        (ipc.HELLO, 0, bytes.fromhex(nonce)), 'Missing data HELLO')
                kind, body, status = ((ipc.OPEN, b'not-a-panel', IDENTITY_ERROR) if wrong_identity
                                      else (ipc.CLOSE, b'', OK))
                ipc.send_packet(channel, kind, 1, body, deadline)
                require(ipc.receive_packet(channel, deadline) ==
                        (ipc.REPLY, 1, bytes([status])), 'Unexpected worker reply')
                require(owner.child.wait(timeout=4) == int(wrong_identity), 'Unexpected worker exit')
        finally:
            owner.stop(time.monotonic() + 3)
        require(owner.released and owner.reaped and owner.closed, 'Worker not released/reaped')


def rejected_release(executable, wrong):
    from mars_display import usb_ipc as ipc

    nonce = secrets.token_hex(32)
    control, inherited = socket.socketpair()
    with listener() as server, control, inherited:
        deadline = time.monotonic() + 3
        child = subprocess.Popen([str(executable), '--linux-usb-worker',
            str(server.getsockname()[1]), nonce, str(inherited.fileno()),
            str(os.getpid()), str(deadline)], pass_fds=(inherited.fileno(),),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            inherited.close()
            require(ipc.receive_packet(control, deadline) ==
                    (ipc.HELLO, 0, bytes.fromhex(nonce)), 'Missing control READY')
            if wrong:
                ipc.send_packet(control, ipc.OPEN, 1, b'wrong-release', deadline)
            out, err = child.communicate(timeout=4)
            require((child.returncode, out, err) == (2, b'', b''), 'Release rejection failed')
            server.settimeout(.1)
            try:
                connection, _ = server.accept()
            except socket.timeout:
                pass
            else:
                connection.close()
                raise RuntimeError('Unreleased worker connected to data socket')
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)


def run(executable):
    require(os.name == 'posix' and os.getuid() != 0 and os.geteuid() != 0,
            'Nonroot Linux runner required')
    executable = executable.resolve(strict=True)
    old_env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix='mars-frozen-smoke-') as directory:
        root = Path(directory)
        for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_RUNTIME_DIR'):
            path = root / name
            path.mkdir(mode=0o700)
            os.environ[name] = str(path)
        settings = root / 'XDG_CONFIG_HOME' / 'MarsDisplay'
        settings.mkdir()
        (settings / 'settings.json').write_bytes(b'{"smoke-sentinel":true}\n')
        before = snapshot(root)
        def expired(*_):
            raise TimeoutError('Frozen smoke overall deadline exceeded')
        previous = signal.signal(signal.SIGALRM, expired)
        signal.alarm(40)
        try:
            for args in (['--usb-worker'], ['--linux-usb-worker=bad'],
                         ['ordinary', '--linux-usb-worker'], ['--linux-usb-worker'],
                         ['--linux-usb-worker', '1', 'bad', '99', '1', '0']):
                quiet([str(executable), *args], 2)
            admitted(executable, False)
            admitted(executable, True)
            rejected_release(executable, True)
            rejected_release(executable, False)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
            os.environ.clear()
            os.environ.update(old_env)
            require(snapshot(root) == before, 'Isolated settings changed')
    print('PASS: private CLI, admission, no-USB protocol, rejection and reap')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--appdir', type=Path,
                        help='production onedir directory containing MarsDisplay (not an AppImage AppDir)')
    target.add_argument('--executable', type=Path, help='explicit production frozen executable')
    args = parser.parse_args()
    run(args.executable if args.executable else args.appdir / 'MarsDisplay')


if __name__ == '__main__':
    main()
