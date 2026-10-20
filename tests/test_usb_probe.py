import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from dataclasses import replace

from mars_display import usb_probe as probe
from mars_display.devices import USBSerialDescriptor

ROOT = Path(__file__).resolve().parents[1]
DEVICE = USBSerialDescriptor('COM5', 0x1a86, 0x5722, 'USB35INCHIPSV2',
                             None, None, None, None, None)


class Port:
    def __init__(self, **options):
        self.options = options
        self.writes = []
        self.closed = 0
        self.opened = 0
        self.out_waiting = 0
        self.short = False
        self.fail = False
        self.close_fail = False
        self.none = False
        self.open_fail = False

    def open(self):
        self.opened += 1
        if self.open_fail:
            raise OSError('private open detail')
        assert self.dtr is True and self.port == 'COM5'

    def write(self, data):
        self.writes.append(data)
        if self.fail:
            raise OSError('private backend detail')
        return None if self.none else len(data) - 1 if self.short else len(data)

    def close(self):
        self.closed += 1
        if self.close_fail:
            raise OSError('private close detail')


class ProbeTests(unittest.TestCase):
    def run_probe(self, args, answer='SEND COM5\n', inventories=None, port=None, **extra):
        self.out, self.err = io.StringIO(), io.StringIO()
        self.calls = []
        inventories = iter(inventories or [(DEVICE,), (DEVICE,)])
        def inventory():
            self.calls.append('inventory')
            return next(inventories)
        self.port = port or Port()
        def factory(**kwargs):
            self.calls.append('factory')
            self.port.options = kwargs
            return self.port
        code = probe.run(args, stdin=io.StringIO(answer), stdout=self.out,
                         stderr=self.err, inventory=inventory, serial_factory=factory,
                         **extra)
        return code, self.out.getvalue(), self.err.getvalue()

    def test_safe_modes_and_argument_errors(self):
        for args, code, output, error in [
            (['--help'], 0, probe.HELP, ''),
            (['--self-test'], 0, probe.SELF_TEST_OK, ''),
            (['--port', 'com5'], 2, '', probe.ERRORS[2] + '\n'),
            (['--worker', 'a'*32], 2, '', probe.ERRORS[2] + '\n'),
            (['--list', '--port', 'COM5'], 2, '', probe.ERRORS[2] + '\n'),
        ]:
            with self.subTest(args=args):
                self.assertEqual(self.run_probe(args), (code, output, error))
                self.assertEqual(self.calls, [])
                self.assertEqual(self.port.writes, [])

    def test_success_exact_packets_and_settings(self):
        result = self.run_probe(['--port', 'COM5'])
        self.assertEqual(result, (0, probe.confirmation('COM5') + probe.SUCCESS, ''))
        self.assertEqual(self.calls, ['inventory', 'inventory', 'factory'])
        self.assertEqual(tuple(self.port.writes), probe.load_packets())
        self.assertEqual(sum(map(len, self.port.writes)), 307222)
        self.assertEqual(self.port.closed, 1)
        self.assertEqual(self.port.options, dict(port=None, baudrate=115200, bytesize=8,
            parity='N', stopbits=1, rtscts=True, dsrdtr=False, write_timeout=3, timeout=1))

    def test_reject_identity_and_foreign_occupants(self):
        bad = [(), (DEVICE, DEVICE), (replace(DEVICE, serial_number=None),),
               (replace(DEVICE, pid=1),), (replace(DEVICE, device='COM6'),),
               (DEVICE, replace(DEVICE, serial_number='foreign'))]
        for snapshot in bad:
            for refreshed in (False, True):
                with self.subTest(snapshot=snapshot, refreshed=refreshed):
                    inventories = [(DEVICE,), snapshot] if refreshed else [snapshot]
                    result = self.run_probe(['--port', 'COM5'], inventories=inventories)
                    self.assertEqual(result, (4, probe.confirmation('COM5') if refreshed else '',
                                              probe.ERRORS[4] + '\n'))
                    self.assertNotIn('factory', self.calls)
                    self.assertEqual(self.port.writes, [])

    def test_cancel_and_interactive(self):
        for answer in ('', 'no\n', 'SEND COM6\n'):
            self.assertEqual(self.run_probe(['--port', 'COM5'], answer),
                             (0, probe.confirmation('COM5') + probe.CANCELLED, ''))
            self.assertEqual(self.calls, ['inventory'])
        self.assertEqual(self.run_probe([], 'COM5\nSEND COM5\n'),
                         (0, probe.PORT_PROMPT + probe.confirmation('COM5') + probe.SUCCESS, ''))
        self.assertEqual(self.run_probe([], ''), (0, probe.PORT_PROMPT + probe.CANCELLED, ''))

    def test_list_and_inventory_failure(self):
        self.assertEqual(self.run_probe(['--list']),
                         (0, 'COM5 usb:1a86:5722:USB35INCHIPSV2\n', ''))
        def broken():
            raise OSError('secret')
        self.assertEqual(probe.run(['--list'], stdout=io.StringIO(), stderr=io.StringIO(),
                                   inventory=broken), 3)

    def test_corrupt_fixture_before_inventory(self):
        self.assertEqual(self.run_probe(['--port', 'COM5'], raw_loader=lambda: b'bad'),
                         (5, '', probe.ERRORS[5] + '\n'))
        self.assertEqual(self.calls, [])

    def test_transfer_failures_no_retry_and_close(self):
        for mode in ('short', 'none', 'fail', 'open_fail', 'close_fail', 'hang'):
            port = Port()
            setattr(port, mode, True)
            if mode == 'hang':
                port.out_waiting = 1
            ticks = iter(range(100))
            result = self.run_probe(['--port', 'COM5'], port=port,
                                    clock=lambda: next(ticks), sleep=lambda _: None)
            self.assertEqual(result, (6, probe.confirmation('COM5'), probe.ERRORS[6] + '\n'))
            self.assertEqual(port.closed, 1)
            expected = 0 if mode == 'open_fail' else 1 if mode in ('short', 'none', 'fail') else 122
            self.assertEqual(len(port.writes), expected)

    def test_primary_failure_survives_close_failure(self):
        port = Port()
        port.fail = port.close_fail = True
        self.assertEqual(self.run_probe(['--port', 'COM5'], port=port),
                         (6, probe.confirmation('COM5'), probe.ERRORS[6]+'\n'))
        self.assertEqual((len(port.writes), port.closed), (1, 1))

    def test_help_does_not_load_fixture(self):
        with patch.object(probe, 'load_packets', side_effect=AssertionError):
            self.assertEqual(self.run_probe(['--help']), (0, probe.HELP, ''))
        self.assertEqual(self.calls, [])

    def test_import_is_passive(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        script = '''
from unittest.mock import patch
import mars_display.devices as devices
from pathlib import Path
with patch.object(devices, 'enumerate_devices', side_effect=AssertionError), patch.object(Path, 'read_bytes', side_effect=AssertionError):
    import mars_display.usb_probe
    import mars_display.usb_probe_process
import sys
assert 'serial' not in sys.modules
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_main_final_pause_only_interactive_parent(self):
        from mars_display import usb_probe_process as process
        class Input(io.StringIO):
            def __init__(self, terminal, answer):
                super().__init__(answer)
                self.terminal = terminal
                self.reads = 0
            def isatty(self):
                return self.terminal
            def readline(self, *args):
                self.reads += 1
                if self.getvalue() == 'interrupt':
                    raise KeyboardInterrupt
                return super().readline(*args)
        cases = [
            ([], True, False, '\n', True),
            ([], True, False, '', True),
            ([], True, False, 'interrupt', True),
            ([], False, False, '\n', False),
            (['--help'], True, False, '\n', False),
            (['--self-test'], True, False, '\n', False),
            (['--list'], True, False, '\n', False),
            (['--port', 'COM5'], True, False, '\n', False),
            ([], True, True, '\n', False),
        ]
        for args, terminal, worker, answer, pauses in cases:
            with self.subTest(args=args, terminal=terminal, worker=worker, answer=answer):
                stdin, stdout, stderr = Input(terminal, answer), io.StringIO(), io.StringIO()
                environment = {process.MARKER: 'a'*32} if worker else {}
                def completed(_):
                    self.assertEqual(stdin.reads, 0)
                    return 4
                with patch.dict(os.environ, environment, clear=True), \
                     patch('sys.stdin', stdin), patch('sys.stdout', stdout), \
                     patch('sys.stderr', stderr), \
                     patch.object(process, 'supervise', side_effect=completed), \
                     patch.object(process, 'await_gate', return_value=True), \
                     patch.object(probe, 'run', side_effect=completed):
                    code = probe.main(args)
                self.assertEqual(code, 4)
                self.assertEqual(stdout.getvalue(), 'Press Enter to close.' if pauses else '')
                self.assertEqual(stderr.getvalue(), '')
                self.assertEqual(stdin.reads, int(pauses))

    def test_source_safe_cli(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        for args, code, out, err in [(['--help'], 0, probe.HELP, ''),
                                   (['--self-test'], 0, probe.SELF_TEST_OK, ''),
                                   (['--worker', 'bad'], 2, '', probe.ERRORS[2]+'\n')]:
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/windows-python-usb-probe/entrypoint.py'), *args],
                                    capture_output=True, text=True, env=env, timeout=5)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (code, out, err))
