"""Public CLI fixtures; no downloads, real AppImage tools or hardware."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'packaging/linux'


class AppImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = self.root / 'recipe'
        shutil.copytree(RECIPE, self.recipe, ignore=shutil.ignore_patterns('__pycache__'))
        self.source = self.root / 'onedir'
        self.source.mkdir()
        binary = self.source / 'MarsDisplay'
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$MARKER" "$$" "$@"\n')
        binary.chmod(0o751)
        (self.source / 'link').symlink_to('MarsDisplay')
        self.notices = self.root / 'notices'
        self.notices.mkdir()
        (self.notices / 'NOTICE').write_text('fixture only')
        self.license = self.root / 'LICENSE'
        self.license.write_text('fixture project license')
        self.tool = self.root / 'tool'
        self.tool.write_text('#!/bin/sh\n[ "$1" = --runtime-file ] || exit 3\n'
                             '[ "$APPIMAGE_EXTRACT_AND_RUN" = 1 ] || exit 4\n'
                             'printf image > "$4"\n')
        self.tool.chmod(0o700)
        self.runtime = self.root / 'runtime'
        self.runtime.write_bytes(b'runtime')
        metadata = json.loads((self.recipe / 'appimage-tools.json').read_text())
        for name, path in [('appimagetool', self.tool), ('runtime', self.runtime)]:
            metadata[name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.recipe / 'appimage-tools.json').write_text(json.dumps(metadata))
        self.output = self.root / 'output'
        self.args = ['--onedir', str(self.source), '--tool', str(self.tool),
                     '--runtime', str(self.runtime), '--output', str(self.output),
                     '--notices', str(self.notices), '--license', str(self.license)]

    def cli(self, args=None):
        return subprocess.run([sys.executable, '-B', str(self.recipe / 'build_appimage.py'),
                               *(self.args if args is None else args)],
                              capture_output=True, text=True, timeout=10)

    def rejected(self, message):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        result = self.cli()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (2, '', f'error: {message}\n'))
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))

    def test_hashes_reject_before_writes(self):
        for path, name in [(self.tool, 'appimagetool'), (self.runtime, 'runtime')]:
            original = path.read_bytes()
            path.write_bytes(b'wrong')
            self.rejected(f'{name} SHA256 mismatch')
            path.write_bytes(original)

    def test_paths_reject_before_writes(self):
        self.output.mkdir()
        self.rejected('output must not exist')

    def test_nested_output_rejected(self):
        self.output = self.source / 'output'
        self.args[self.args.index('--output') + 1] = str(self.output)
        self.rejected('output overlaps an input')

    def test_unsafe_links_rejected(self):
        for target in ['../LICENSE', '/etc/passwd', 'missing', 'unsafe']:
            link = self.source / 'unsafe'
            link.symlink_to(target)
            self.rejected('unsafe input tree')
            link.unlink()

    def test_missing_binary_rejected(self):
        (self.source / 'MarsDisplay').chmod(0o600)
        self.rejected('onedir needs executable MarsDisplay')

    def test_help_is_passive(self):
        result = self.cli(['--help'])
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        for option in ['--onedir', '--tool', '--runtime', '--output', '--notices', '--license']:
            self.assertIn(option, result.stdout)
        self.assertFalse(self.output.exists())

    def test_package_and_launcher_preserve_inputs(self):
        result = self.cli()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, 'Created prototype: MarsDisplay-x86_64.AppImage\n', ''))
        appdir = self.output / 'MarsDisplay.AppDir'
        inner = appdir / 'usr/lib/marsdisplay/MarsDisplay'
        self.assertEqual(inner.stat().st_mode & 0o777, 0o751)
        self.assertEqual(os.readlink(inner.with_name('link')), 'MarsDisplay')
        self.assertEqual((appdir / 'LICENSE').read_bytes(), self.license.read_bytes())
        self.assertEqual((appdir / 'notices/NOTICE').read_text(), 'fixture only')
        process = subprocess.Popen(['/bin/sh', str(appdir / 'AppRun'), 'a b', '', '--private'],
                                   env={**os.environ, 'MARKER': 'kept', 'APPDIR': '/wrong'},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual((process.returncode, stdout, stderr),
                         (0, f'kept\n{process.pid}\na b\n\n--private\n', ''))
        image = self.output / 'MarsDisplay-x86_64.AppImage'
        self.assertEqual((self.output / (image.name + '.sha256')).read_text(),
                         hashlib.sha256(b'image').hexdigest() + '  ' + image.name + '\n')
        self.rejected('output must not exist')


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(AppImageTests) if sys.platform == 'linux' else unittest.TestSuite()
