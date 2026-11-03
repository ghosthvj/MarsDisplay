"""Test-only child. Report/control socket is independent of admission/data IPC.

Never imports serial, enumerates devices, or executes another program once armed.
"""
import ctypes
import os
import socket
import subprocess
import sys
import threading
import time

from mars_display import linux_usb_admission as admission


def child(fd, nonce, parent, deadline, report_port):
    with socket.create_connection(('127.0.0.1', report_port), timeout=3) as report:
        report.settimeout(5)  # Independent watchdog for every test barrier.
        stream = report.makefile('rwb', buffering=0)
        stream.write(f'START {os.getpid()}\n'.encode())
        if stream.readline() != b'ARM\n':
            return 2
        original = admission.arm_parent_death

        def arm(expected):
            original(expected)
            stream.write(b'ARMED\n')
            if stream.readline() != b'READY\n':
                raise RuntimeError('test barrier rejected')

        admission.arm_parent_death = arm
        try:
            admission.await_admission(fd, nonce, parent, deadline)
        except Exception:
            stream.write(b'REJECTED\n')
            return 3
        stream.write(b'ADMITTED\n')
        for line in stream:
            if line == b'PING\n':
                stream.write(b'PONG\n')
            elif line == b'EXIT\n':
                return 0
        return 0


def creator(report_port):
    """A creator thread may die while its process (and PPID) stays alive."""
    children = []

    def run():
        parent, endpoint = socket.socketpair()
        try:
            fd = endpoint.fileno()
            children.append(subprocess.Popen([sys.executable, '-B', __file__, str(fd),
                'ab' * 32, str(os.getpid()), str(time.monotonic() + 3), str(report_port)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, pass_fds=(fd,)))
            endpoint.close()
            print('CREATED', flush=True)
            if sys.stdin.readline() == 'PROCESS\n':
                os._exit(0)  # Test-only abrupt whole-parent death.
        finally:
            endpoint.close()
            parent.close()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join()
    print('CREATOR_EXITED', flush=True)
    try:
        print(f'REAPED {children[0].wait(timeout=5)}', flush=True)
    finally:
        if children and children[0].poll() is None:
            children[0].kill()
            children[0].wait(timeout=2)


def death_watch(report_port):
    """Subreaping is confined to this test fixture, never the test runner."""
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise RuntimeError('test subreaper failed')
    inner = subprocess.Popen([sys.executable, '-B', __file__, 'creator', str(report_port)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        print(inner.stdout.readline().strip(), flush=True)
        command = sys.stdin.readline()
        output, _ = inner.communicate(command, timeout=7)
        print(output, end='', flush=True)
        _, status = os.waitpid(-1, 0)  # Adopted child retains its own watchdog.
        print(f'ADOPTED {os.waitstatus_to_exitcode(status)}', flush=True)
    finally:
        if inner.poll() is None:
            inner.kill()
            inner.wait(timeout=2)
        inner.stdin.close()
        inner.stdout.close()


if __name__ == '__main__':
    if sys.argv[1] == 'creator':
        creator(int(sys.argv[2]))
    elif sys.argv[1] == 'death-watch':
        death_watch(int(sys.argv[2]))
    else:
        raise SystemExit(child(int(sys.argv[1]), sys.argv[2], int(sys.argv[3]),
                              float(sys.argv[4]), int(sys.argv[5])))
