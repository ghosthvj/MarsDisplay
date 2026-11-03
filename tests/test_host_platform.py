"""Host admission is a passive policy, not a platform backend."""
import subprocess
import sys
import unittest

from mars_display.host_platform import is_supported_host


class HostPlatformTests(unittest.TestCase):
    def test_windows_x64_admission(self):
        for machine in ("AMD64", "amd64", "x86_64", "X86_64"):
            with self.subTest(machine=machine):
                self.assertTrue(is_supported_host("win32", machine, 8))

    def test_unsupported_hosts(self):
        for host, machine, pointer_size in (
            ("win32", "ARM64", 8),
            ("win32", "AMD64", 4),
            ("win32", "x86_64", 4),
            ("linux", "x86_64", 8),
            ("darwin", "x86_64", 8),
        ):
            with self.subTest(host=host, machine=machine, pointer_size=pointer_size):
                self.assertFalse(is_supported_host(host, machine, pointer_size))

    def test_import_needs_no_runtime_dependencies_or_host_probes(self):
        script = """
import sys
from unittest.mock import patch
sys.modules.update({name: None for name in (
    'PySide6', 'playwright', 'serial', 'mars_display.app',
    'mars_display.settings', 'mars_display.browser', 'mars_display.usb_transport',
)})
with patch('platform.machine', side_effect=AssertionError('host probe')), \
     patch('struct.calcsize', side_effect=AssertionError('pointer probe')):
    import mars_display.host_platform
"""
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
