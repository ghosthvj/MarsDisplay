"""Combined publication uses both validators before any GitHub mutation."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import unittest
from unittest import mock

import test_release as windows

release = windows.release


class CombinedReleaseTests(unittest.TestCase):
    setUp = windows.ReleaseTests.setUp
    make_assets = windows.ReleaseTests.make_assets
    github = windows.ReleaseTests.github
    invoke_windows = windows.ReleaseTests.invoke

    def prepare_linux(self):
        folder = Path('linux-assets')
        folder.mkdir()
        names = ('MarsDisplay-0.2.0rc7-Linux-x86_64.AppImage',
                 'MarsDisplay-0.2.0rc7-Linux-x86_64-support.zip')
        for name in names:
            (folder / name).write_bytes(b'isolated validator-boundary fixture')
            (folder / (name + '.sha256')).write_text('validator-boundary fixture')
        self.linux_metadata = {
            p.absolute(): dict(name=p.name, size=p.stat().st_size, state='uploaded',
                               digest='sha256:' + hashlib.sha256(p.read_bytes()).hexdigest())
            for p in folder.iterdir()}
        self.assets.update({v['name']: v for v in self.linux_metadata.values()})

    def invoke(self, *args):
        before = {p: p.read_bytes() for p in Path('linux-assets').glob('*')}
        result = self.invoke_windows(*args)
        self.assertEqual(before, {p: p.read_bytes() for p in Path('linux-assets').glob('*')})
        return result

    def test_combined_publish_validates_then_uploads_all_six_assets(self):
        self.prepare_linux()
        with mock.patch.object(release, 'linux_assets', return_value=self.linux_metadata, create=True) as validate:
            self.assertEqual(self.invoke('publish', '--artifacts', 'assets', '--linux-artifacts', 'linux-assets'),
                             (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0rc7\n', ''))
        validate.assert_called_once_with('linux-assets', self.version, windows.SHA, None)
        uploads = [args for args, _ in self.calls if args[2].startswith('https://uploads.github.com/')]
        self.assertEqual(len(uploads), 6)
        self.assertEqual({a[2].split('?name=')[1] for a in uploads}, set(self.assets))
        self.assertEqual(self.calls[-2][1], {'draft': False})

    def test_rejected_linux_assets_prevent_every_remote_call(self):
        self.prepare_linux()
        with mock.patch.object(release, 'linux_assets', side_effect=ValueError('Invalid Linux artifact format or provenance.'), create=True):
            self.assertEqual(self.invoke('publish', '--artifacts', 'assets', '--linux-artifacts', 'linux-assets'),
                             (1, '', 'Release error: Invalid Linux artifact format or provenance.\n'))
        self.assertEqual(self.calls, [])

    def test_real_linux_validator_composes_with_windows_and_publish(self):
        # Generate provenance locally; never consult the checkout's Git history.
        subprocess.run(['git', 'init', '-q'], check=True, capture_output=True)
        subprocess.run(['git', 'add', 'pyproject.toml'], check=True, capture_output=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'],
                       check=True, capture_output=True)
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        original = subprocess.check_output(['git', 'show', sha + ':pyproject.toml'])
        stamped = release.versioning.render(original, self.tag)
        archive = next(Path('assets').glob('*.zip'))
        with zipfile.ZipFile(archive) as z:
            files = {name: z.read(name) for name in z.namelist()}
        inventory = json.loads(files['MarsDisplay/inventory.json'])
        files['MarsDisplay/source/pyproject.toml'] = stamped
        inventory['files']['source/pyproject.toml'] = hashlib.sha256(stamped).hexdigest()
        inventory.update(source_commit=sha,
                         release=release.versioning.provenance(original, self.tag, sha))
        files['MarsDisplay/inventory.json'] = json.dumps(inventory).encode()
        with zipfile.ZipFile(archive, 'w') as z:
            for name, data in files.items():
                z.writestr(name, data)
        archive.with_suffix('.zip.sha256').write_text(
            hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        content = Path('content')
        (content / 'source').mkdir(parents=True)
        (content / 'notices').mkdir()
        (content / 'source/pyproject.toml').write_bytes(stamped)
        (content / 'README.md').write_text('Isolated format fixture.')
        (content / 'notices/LICENSE').write_text('Fixture, not legal qualification.')
        Path('input.AppImage').write_bytes(b'format fixture only')
        cli = Path(release.__file__).parent / 'linux/release_assets.py'
        built = subprocess.run([sys.executable, '-B', str(cli), 'build', '--image',
                                'input.AppImage', '--content', 'content', '--output',
                                'linux-assets', '--tag', self.tag, '--sha', sha],
                               capture_output=True, text=True)
        self.assertEqual((built.returncode, built.stdout, built.stderr),
                         (0, 'Linux artifact format validated; legal qualification is separate.\n', ''))
        self.assets = {p.name: dict(name=p.name, size=p.stat().st_size, state='uploaded',
                                   digest='sha256:' + hashlib.sha256(p.read_bytes()).hexdigest())
                       for folder in ('assets', 'linux-assets') for p in Path(folder).iterdir()}
        self.env['GITHUB_SHA'] = sha
        # Real Git and Python children still need executable lookup on Windows;
        # retain no GitHub credentials in the isolated publication environment.
        for key in ('PATH', 'SYSTEMROOT'):
            if key in os.environ:
                self.env[key] = os.environ[key]
        before = {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()}
        out, err = io.StringIO(), io.StringIO()

        def fake_gh(*args, data=None):
            return self.github(['gh', *args], input=json.dumps(data) if data else None).stdout

        with (mock.patch.dict(os.environ, self.env, clear=True),
              mock.patch.object(windows, 'SHA', sha), mock.patch.object(release, 'gh', fake_gh),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            code = release.main(['publish', '--artifacts', 'assets', '--linux-artifacts',
                                 'linux-assets', '--tag', self.tag])
        self.assertEqual((code, out.getvalue(), err.getvalue()),
                         (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0rc7\n', ''))
        self.assertEqual(before, {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()})
        self.assertEqual(len(self.calls), 12)

    def test_other_commands_keep_exact_unknown_option_rejection(self):
        for command in ('plan', 'stamp'):
            before = {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()}
            out, err = io.StringIO(), io.StringIO()
            with (self.subTest(command=command), mock.patch('sys.argv', ['release.py']),
                  contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
                  self.assertRaises(SystemExit) as stopped):
                release.main([command, '--linux-artifacts', 'linux-assets'])
            self.assertEqual((stopped.exception.code, out.getvalue(), err.getvalue()),
                             (2, '', 'usage: release.py [-h] [--tag TAG] [--artifacts ARTIFACTS]\n'
                              '                  {plan,stamp,publish}\n'
                              'release.py: error: unrecognized arguments: --linux-artifacts linux-assets\n'))
            self.assertEqual(before, {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()})
            self.assertEqual(self.calls, [])

    def test_missing_linux_value_keeps_nonpublish_rejection(self):
        for command in ('plan', 'stamp'):
            before = {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()}
            out, err = io.StringIO(), io.StringIO()
            with (self.subTest(command=command), mock.patch('sys.argv', ['release.py']),
                  contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
                  self.assertRaises(SystemExit) as stopped):
                release.main([command, '--linux-artifacts'])
            self.assertEqual((stopped.exception.code, out.getvalue(), err.getvalue()),
                             (2, '', 'usage: release.py [-h] [--tag TAG] [--artifacts ARTIFACTS]\n'
                              '                  {plan,stamp,publish}\n'
                              'release.py: error: unrecognized arguments: --linux-artifacts\n'))
            self.assertEqual(before, {p: p.read_bytes() for p in Path('.').rglob('*') if p.is_file()})
            self.assertEqual(self.calls, [])

    def test_windows_only_publish_keeps_original_contract(self):
        with mock.patch.object(release, 'linux_assets', create=True) as validate:
            self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                             (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0rc7\n', ''))
        validate.assert_not_called()
        self.assertEqual(len(self.calls), 8)
