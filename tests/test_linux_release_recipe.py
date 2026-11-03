"""Execute the distribution recipe with isolated PyInstaller collection seams."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class LinuxReleaseRecipeTests(unittest.TestCase):
    def recipe(self, filename):
        prefix = 'playwright/driver/package/.local-browsers/'
        entries = [(prefix + name, '/sdk/' + name, kind) for name, kind in (
            ('ffmpeg-1013/ffmpeg-linux', 'BINARY'),
            ('ffmpeg-1013/COPYING.LGPLv2.1', 'DATA'),
            ('chromium_headless_shell-1248/chrome-linux/headless_shell', 'BINARY'),
            ('chromium-1248/chrome-linux/libffmpeg.so', 'BINARY'),
            ('ffmpeg-1013.extra/file', 'DATA'),
            ('ffmpeg-not-a-revision/file', 'DATA'))]
        entries.extend([('playwright/driver/node', '/sdk/node', 'BINARY'),
                        ('playwright/driver/package/browsers.json', '/sdk/browsers.json', 'DATA')])
        captured = {}

        def analysis(*args, **kwargs):
            captured['analysis'] = (args, kwargs)
            return SimpleNamespace(pure=[], scripts=[], binaries=list(entries), datas=list(entries))

        def exe(*args, **kwargs):
            captured['exe'] = (args, kwargs)
            return 'fixture executable'

        def collect(*args, **kwargs):
            captured['collect'] = (args, kwargs)

        with mock.patch('sys.platform', 'linux'), mock.patch('platform.machine', return_value='x86_64'):
            runpy.run_path(str(ROOT / 'packaging/linux' / filename), init_globals={
                'SPECPATH': str(ROOT / 'packaging/linux'), 'Analysis': analysis,
                'PYZ': lambda value: value, 'EXE': exe, 'COLLECT': collect})
        return entries, captured

    def test_distribution_excludes_only_standalone_video_recorder(self):
        entries, release = self.recipe('Release.spec')
        _, baseline = self.recipe('MarsDisplay.spec')
        self.assertEqual(release['analysis'], baseline['analysis'])
        self.assertEqual(release['exe'], baseline['exe'])
        args, options = release['collect']
        expected = entries[2:]
        self.assertEqual(args, ('fixture executable', expected, expected))
        self.assertEqual(options, baseline['collect'][1])
        for actual, original in zip(args[1], expected):
            self.assertIs(actual, original)
        self.assertEqual(baseline['collect'][0], ('fixture executable', entries, entries))

    def test_distribution_retains_linux_only_guard(self):
        with mock.patch('sys.platform', 'win32'), self.assertRaises(SystemExit) as stopped:
            runpy.run_path(str(ROOT / 'packaging/linux/Release.spec'))
        self.assertEqual(str(stopped.exception), 'Linux x86_64 builder required')
