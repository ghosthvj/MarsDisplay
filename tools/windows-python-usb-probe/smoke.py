"""Native, USB-free qualification commands; never supplies a SEND confirmation."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def environment(state, system_root, source=None):
    state = Path(state)
    state.mkdir()  # Exclusive; no old settings/caches can affect qualification.
    env = {'SystemRoot': str(system_root), 'WINDIR': str(system_root),
           'PATH': str(Path(system_root) / 'System32'),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
    for key in ('HOME', 'USERPROFILE', 'TEMP', 'TMP', 'TMPDIR', 'APPDATA', 'LOCALAPPDATA',
                'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME'):
        env[key] = str(state)
    if source is not None:
        env['PYTHONPATH'] = os.pathsep.join((str(Path(source) / 'src'), str(Path(source) / 'tests')))
    return env


def check_vector(vector, state, *, run=subprocess.run, system_root=None, source=None):
    # Only build-side imports: never part of the application's Analysis entrypoint.
    from mars_display import usb_probe
    system_root = Path(os.environ['SystemRoot']) if system_root is None else system_root
    env = environment(state, system_root, source)
    expected = [(['--help'], 0, usb_probe.HELP, ''),
                (['--self-test'], 0, usb_probe.SELF_TEST_OK, ''),
                (['--badflag'], 2, '', usb_probe.ERRORS[2] + '\n'),
                (['--port', 'COM0'], 2, '', usb_probe.ERRORS[2] + '\n'),
                (['--worker'], 2, '', usb_probe.ERRORS[2] + '\n'),
                (['--list'], 0, None, ''),
                ([], 0, usb_probe.PORT_PROMPT + usb_probe.CANCELLED, '')]
    evidence = []
    for args, code, out, err in expected:
        result = run([*vector, *args], input='', capture_output=True, text=True,
                     timeout=95, env=env, cwd=state)
        if (result.returncode != code or result.stderr != err
                or (out is not None and result.stdout != out)):
            raise ValueError('Packaged safe-command exit/stdout/stderr mismatch: ' + repr(args))
        if out is None and any(not re.fullmatch(r'\S+ [^\r\n]+', line)
                               for line in result.stdout.splitlines()):
            raise ValueError('Malformed passive descriptor listing')
        evidence.append({'args': args, 'exit': code, 'stdout': result.stdout, 'stderr': result.stderr})
    return {'status': 'passed', 'commands': evidence}


def source_tests(repo, state, *, run=subprocess.run):
    """Run only the selected diagnostic suite; any skip is a native failure."""
    env = environment(state, Path(os.environ['SystemRoot']), repo)
    script = '''import json, unittest
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.discover('tests', pattern=pattern) for pattern in (
 'test_native_probe_fixture.py', 'test_usb_protocol.py', 'test_usb_probe.py',
 'test_usb_probe_process.py', 'test_packaging_python_usb_probe.py'))
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'tests': result.testsRun, 'skips': len(result.skipped),
 'failures': len(result.failures), 'errors': len(result.errors)}))
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
'''
    result = run([sys.executable, '-B', '-c', script], cwd=repo, env=env,
                 capture_output=True, text=True, timeout=180)
    sys.stderr.write(result.stderr)
    if result.returncode:
        raise ValueError('Native source tests failed or skipped')
    report = json.loads(result.stdout)
    if report['tests'] < 25 or any(report[key] for key in ('skips', 'failures', 'errors')):
        raise ValueError('Incomplete native source test evidence')
    return report


def parent_death(repo, state):
    """Test helper only: kill a helper parent, observe its job-owned helper child.

    No application CLI flags or USB operations. Windows process handles, not PID
    scanning, bind observation to the exact child created by this helper.
    """
    import ctypes
    from ctypes import wintypes
    env = environment(state, Path(os.environ['SystemRoot']), repo)
    script = '''import subprocess, sys, time
from mars_display.usb_probe_process import WindowsJobGate
with WindowsJobGate('d'*32) as gate:
 child = subprocess.Popen([sys.executable, '-I', '-B', '-c', 'import time; time.sleep(30)'])
 try:
  gate.assign(child)
  gate.release()
  print(child.pid, flush=True)
  time.sleep(30)
 finally:
  if child.poll() is None:
   child.kill()
  child.wait(timeout=2)
'''
    parent = subprocess.Popen([sys.executable, '-B', '-c', script], env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, cwd=state)
    handle = None
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    api.WaitForSingleObject.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    try:
        # communicate is bounded: helper parent exits on a short timer below,
        # but we must kill it while the job is still open. A reader future gets
        # the single PID line without an unbounded readline on the main thread.
        import queue
        import threading
        lines = queue.Queue()
        reader = threading.Thread(target=lambda: lines.put(parent.stdout.readline()), daemon=True)
        reader.start()
        pid = int(lines.get(timeout=10).strip())
        handle = api.OpenProcess(0x00100000, False, pid)
        if not handle:
            raise ValueError('Cannot observe owned child handle')
        if api.WaitForSingleObject(handle, 0) != 0x102:
            raise ValueError('Owned child exited before parent-death test')
        parent.kill()
        parent.wait(timeout=2)
        if api.WaitForSingleObject(handle, 2000) != 0:
            raise ValueError('Parent death did not terminate owned child')
        reader.join(timeout=2)
        return {'status': 'passed', 'scope': 'owned helper child; no device I/O'}
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=2)
        if handle:
            api.CloseHandle(handle)
        parent.stdout.close()
        parent.stderr.close()


def frozen_lifetime(executable, state):
    """Exercise the actual frozen startup gate and owned termination without USB."""
    from mars_display.usb_probe_process import WindowsJobGate, MARKER, wait_owned
    import secrets
    env = environment(state, Path(os.environ['SystemRoot']))
    results = []
    for release in (True, False):
        marker = secrets.token_hex(16)
        child = None
        try:
            with WindowsJobGate(marker) as gate:
                child = subprocess.Popen([str(executable), '--list'],
                                         env={**env, MARKER: marker}, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=state)
                gate.assign(child)
                try:
                    child.wait(timeout=0.15)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    raise ValueError('Frozen worker did not wait for startup gate')
                if release:
                    gate.release()
                    out, err = child.communicate(timeout=10)
                    if child.returncode != 0 or err:
                        raise ValueError('Frozen worker failed released passive listing')
                    if any(not re.fullmatch(r'\S+ [^\r\n]+', line) for line in out.splitlines()):
                        raise ValueError('Frozen passive list output malformed')
            if not release:
                if wait_owned(child, 2) == 8 or child.poll() is None:
                    raise ValueError('Frozen job close failed to terminate/reap owned worker')
            results.append({'released': release, 'status': 'passed'})
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=2)
                child.stdout.close()
                child.stderr.close()
    return {'status': 'passed', 'cases': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run native USB-free diagnostic source tests; no build or USB transfer.')
    parser.parse_args(argv)
    if os.name != 'nt':
        print('Native Windows qualification required.', file=sys.stderr)
        return 1
    import tempfile
    with tempfile.TemporaryDirectory(prefix='probe-tests-') as temporary:
        print(json.dumps(source_tests(Path(__file__).resolve().parents[2], Path(temporary) / 'state')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
