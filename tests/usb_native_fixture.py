"""Test-owned child/parent fixtures; never part of the application entrypoint."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time

from mars_display import usb_ipc as ipc, usb_worker as worker
from mars_display.devices import USBSerialDescriptor
from mars_display.usb_process import OwnedWorker, await_admission


def child(port, nonce, mode, report):
    # No socket, file or fake-port effects before the same native startup gate.
    if mode not in ('normal', 'open', 'write', 'drain', 'close') or not await_admission(nonce):
        return 2
    path = Path(report)
    def log(value):
        with path.open('a', encoding='utf-8') as out:
            out.write(json.dumps(value) + '\n')
    class Port:
        def __init__(self):
            self.count, self.digest = 0, hashlib.sha256()
        def block(self, stage):
            if mode == stage:
                threading.Event().wait(60)  # Parent must kill/reap this exact fixture.
                raise RuntimeError('fixture hang escaped containment')
        def open(self):
            log({'op': 'open'}); self.block('open')
        def write(self, data):
            self.count += 1; self.digest.update(data)
            log({'op': 'write', 'n': self.count, 'bytes': len(data)})
            self.block('write')
            return len(data)
        @property
        def out_waiting(self):
            return 1 if mode == 'drain' else 0
        def close(self):
            log({'op': 'close', 'writes': self.count, 'sha256': self.digest.hexdigest()})
            self.block('close')
    def factory(**options):
        log({'op': 'factory', 'options': options})
        return Port()
    device = USBSerialDescriptor('COM5',0x1a86,0x5722,'USB35INCHIPSV2',None,None,None,None,None)
    with socket.socket() as channel:
        channel.settimeout(5); channel.connect(('127.0.0.1', int(port)))
        return worker.run_session(channel, bytes.fromhex(nonce),
            inventory=lambda: (device,), port_factory=factory)


def parent(executable, report):
    """Hold one real windowed child without an OPEN request until parent death."""
    nonce = secrets.token_hex(32)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('PYTHON','QT_','QML'))}
    def launch(port, token):
        return subprocess.Popen([executable, '--usb-worker', str(port), token], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(5)
        owner = OwnedWorker(listener.getsockname()[1], nonce, ipc.Budgets(), launcher=launch)
        try:
            owner.start(); owner.wait_start(time.monotonic()+5, threading.Event())
            with listener.accept()[0] as channel:
                if ipc.receive_packet(channel, time.monotonic()+5) != (ipc.HELLO,0,bytes.fromhex(nonce)):
                    raise RuntimeError('invalid child admission')
                pending=Path(report).with_suffix('.pending')
                with pending.open('x') as out: out.write(str(owner.child.pid))
                pending.rename(report)  # Publish a complete PID, never an empty-file race.
                threading.Event().wait(30)
        finally:
            owner.stop(time.monotonic()+2)
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 5 and args[0] == 'child':
        raise SystemExit(child(*args[1:]))
    if len(args) == 3 and args[0] == 'parent':
        raise SystemExit(parent(*args[1:]))
    raise SystemExit(2)
