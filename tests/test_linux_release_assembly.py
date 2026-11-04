"""Public-main assembly checks without downloads or executable fixture tools."""
from contextlib import redirect_stderr, redirect_stdout
from importlib import util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = util.spec_from_file_location(path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.assembly = load(ROOT / 'packaging/linux/assemble_release.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'onedir'
        self.source.mkdir()
        self.binary = self.source / 'MarsDisplay'
        self.binary.write_text('#!/bin/sh\nprintf "%s\\n" "$MARKER" "$$" "$@"\n')
        self.binary.chmod(0o751)
        self.notices = self.root / 'notices'
        self.notices.mkdir()
        (self.notices / 'NOTICE').write_text('fixture')
        for name in ('tool', 'runtime', 'LICENSE'):
            (self.root / name).write_text(name)
        (self.root / 'tool').chmod(0o700)
        versioning = load(ROOT / 'packaging/release_version.py')
        self.record = versioning.provenance(b'[project]\nversion = "0.1.0"\n', 'v1.2.3rc1', 'a' * 40)
        self.record_path = self.root / 'record.json'
        self.record_path.write_text(json.dumps(self.record))
        self.output = self.root / 'output'
        self.args = []
        for key, path in [('onedir', self.source), ('notices', self.notices),
                          ('tool', self.root / 'tool'), ('runtime', self.root / 'runtime'),
                          ('license', self.root / 'LICENSE'), ('release-record', self.record_path),
                          ('output', self.output)]:
            self.args.extend(['--' + key, str(path)])
        self.pins = {name: {'sha256': self.assembly.legacy.digest(self.root / file)}
                     for name, file in [('appimagetool', 'tool'), ('runtime', 'runtime')]}
        self.calls = []

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():
                (p.lstat().st_mode, os.readlink(p) if p.is_symlink() else
                 p.read_bytes() if p.is_file() else None)
                for p in self.root.rglob('*')}

    def runner(self, command, **kwargs):
        self.calls.append((command, kwargs))
        Path(command[-1]).write_bytes(b'image')

    def invoke(self, runner=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = self.assembly.main(self.args, runner=runner or self.runner, pins=self.pins)
        return code, stdout.getvalue(), stderr.getvalue()

    def reject(self, message):
        before = self.snapshot()
        self.assertEqual(self.invoke(), (2, '', 'error: ' + message + '\n'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls, [])

    def test_success_measures_and_preserves(self):
        before = self.snapshot()
        self.assertEqual(self.invoke(), (0, 'Created release: MarsDisplay.AppImage\n', ''))
        after = self.snapshot()
        self.assertEqual({k: after[k] for k in before}, before)
        appdir = self.output / 'MarsDisplay.AppDir'
        metadata = json.loads((appdir / 'release.json').read_text())
        self.assertEqual(metadata['release'], self.record)
        self.assertEqual(metadata['executable_sha256'], self.assembly.legacy.digest(self.binary))
        self.assertEqual(metadata['tools'], self.pins)
        self.assertNotIn('checks', metadata)
        self.assertFalse((appdir / 'prototype.json').exists())
        for name in ('AppRun', 'MarsDisplay.desktop', 'marsdisplay.svg'):
            self.assertEqual((appdir / name).read_bytes(), (ROOT / 'packaging/linux' / name).read_bytes())
        self.assertEqual((appdir / 'notices/NOTICE').read_text(), 'fixture')
        self.assertEqual((appdir / 'LICENSE').read_text(), 'LICENSE')
        self.assertEqual((self.output / 'MarsDisplay.AppImage').read_bytes(), b'image')
        command, kwargs = self.calls[0]
        self.assertEqual(command, [str(self.root / 'tool'), '--runtime-file',
                                  str(self.root / 'runtime'), str(appdir),
                                  str(self.output / 'MarsDisplay.AppImage')])
        self.assertTrue(kwargs['check'])
        self.assertEqual(kwargs['env']['APPIMAGE_EXTRACT_AND_RUN'], '1')
        self.assertEqual(kwargs['env']['ARCH'], 'x86_64')
        self.assertEqual(kwargs['cwd'], self.output)
        self.calls.clear()
        self.reject('output must not exist')

    def test_help_and_cli_have_no_test_bypass(self):
        before = self.snapshot()
        cli = [sys.executable, '-B', str(ROOT / 'packaging/linux/assemble_release.py')]
        result = subprocess.run(cli + ['--help'], capture_output=True, text=True, timeout=10)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        for option in self.args[::2]:
            self.assertIn(option, result.stdout)
        for option in ('--pins', '--runner'):
            result = subprocess.run(cli + self.args + [option, 'fixture'],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout), (2, ''))
            self.assertIn('unrecognized arguments: ' + option + ' fixture', result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_parent_and_binary(self):
        self.args[-1] = str(self.root / 'missing/output')
        self.reject('output parent must exist')
        self.args[-1] = str(self.output)
        self.args[1] = str(self.notices)
        self.reject('onedir needs executable MarsDisplay')

    def test_record_structure_and_consistency(self):
        for record in [[], {}, {**self.record, 'schema': True},
                       {**self.record, 'version': '9.0.0'}, {**self.record, 'tag': 'v01.2.3'},
                       {**self.record, 'source_commit': 'z' * 40},
                       {**self.record, 'source_pyproject_sha256': 'bad'},
                       {**self.record, 'source_version': ''}, {**self.record, 'extra': 1}]:
            with self.subTest(record=record):
                self.record_path.write_text(json.dumps(record))
                self.reject('invalid release record')

    def test_pins_and_required_material(self):
        for name, file in [('appimagetool', 'tool'), ('runtime', 'runtime')]:
            path = self.root / file
            original = path.read_bytes()
            path.write_bytes(b'wrong')
            self.reject(name + ' SHA256 mismatch')
            path.write_bytes(original)
        (self.root / 'LICENSE').write_bytes(b'')
        self.reject('project LICENSE must not be empty')

    def test_overlap_and_empty_notices(self):
        self.args[-1] = str(self.source / 'output')
        self.reject('output overlaps an input')
        self.args[-1] = str(self.output)
        (self.notices / 'NOTICE').write_bytes(b'')
        self.reject('notices must not be empty')

    def test_failure_retained_without_retry(self):
        def fail(command, **kwargs):
            raise subprocess.CalledProcessError(1, command)
        self.assertEqual(self.invoke(fail), (2, '',
                         'error: appimagetool failed; output retained; see appimagetool.log\n'))
        self.assertTrue((self.output / 'MarsDisplay.AppDir/release.json').is_file())
        self.assertTrue((self.output / 'appimagetool.log').is_file())
        self.reject('output must not exist')

    def test_no_image_is_failure(self):
        self.assertEqual(self.invoke(lambda *a, **k: None),
                         (2, '', 'error: appimagetool produced no image\n'))
        self.assertTrue(self.output.is_dir())


class PosixAssemblyTests(AssemblyTests):
    def test_links_and_launcher(self):
        alias = self.source / 'alias'
        alias.symlink_to('MarsDisplay')
        self.assertEqual(self.invoke()[0], 0)
        appdir = self.output / 'MarsDisplay.AppDir'
        self.assertEqual(os.readlink(appdir / 'usr/lib/marsdisplay/alias'), 'MarsDisplay')
        self.assertEqual((appdir / 'usr/lib/marsdisplay/MarsDisplay').stat().st_mode & 0o777, 0o751)
        process = subprocess.Popen([str(appdir / 'AppRun'), 'a b', '', '--private'],
                                   env={**os.environ, 'MARKER': 'kept', 'APPDIR': '/wrong'},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual((process.returncode, stdout, stderr),
                         (0, f'kept\n{process.pid}\na b\n\n--private\n', ''))

    def test_escaping_links_and_permissions(self):
        for root in (self.source, self.notices):
            link = root / 'bad'
            link.symlink_to('../LICENSE')
            self.reject('unsafe input tree')
            link.unlink()
        (self.root / 'tool').chmod(0o600)
        self.reject('appimagetool must be executable')
        (self.root / 'tool').chmod(0o700)
        self.binary.chmod(0o600)
        self.reject('onedir needs executable MarsDisplay')


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(AssemblyTests)
    if sys.platform == 'linux':
        for name in ('test_links_and_launcher', 'test_escaping_links_and_permissions'):
            suite.addTest(PosixAssemblyTests(name))
    return suite
