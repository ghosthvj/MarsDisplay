"""Public release CLI checks with an isolated, non-network GitHub boundary."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location('release_cli', Path(__file__).parents[1] / 'packaging/release.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
SHA = 'a' * 40


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        previous = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, previous)
        self.env = dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REF='refs/heads/main',
                        GITHUB_SHA=SHA, GITHUB_REPOSITORY='test/repo')
        self.calls = []
        self.fail_at = None
        self.bad_assets = False
        self.drift = False
        self.remote_mismatch = None
        self.bad_final = False
        self.commitish = SHA
        self.make_assets()

    def make_assets(self, version='0.2.0rc7', commit=SHA, artifact_version=None, target='Windows-x64', bad_hash=False):
        Path('pyproject.toml').write_text(f'[project]\nversion = "{version}"\n')
        self.version = version
        self.tag = 'v' + version
        folder = Path('assets')
        folder.mkdir(exist_ok=True)
        for p in folder.iterdir():
            p.unlink()
        files = {'MarsDisplay.exe': b'fixture executable',
                 'source/pyproject.toml': f'[project]\nversion = "{artifact_version or version}"\n'.encode()}
        inventory = dict(source_commit=commit, target=target,
                         files={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
        if bad_hash:
            inventory['files']['MarsDisplay.exe'] = '0' * 64
        archive = folder / f'MarsDisplay-{version}-Windows-x64.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, data in files.items():
                z.writestr('MarsDisplay/' + name, data)
            z.writestr('MarsDisplay/inventory.json', json.dumps(inventory))
        archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        self.assets = {p.name: dict(name=p.name, size=p.stat().st_size, state='uploaded',
                                   digest='sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()) for p in folder.iterdir()}

    def github(self, args, **kwargs):
        data = json.loads(kwargs['input']) if kwargs.get('input') else None
        self.calls.append((args, data))
        if len(self.calls) == self.fail_at:
            return subprocess.CompletedProcess(args, 1, '', 'simulated failure')
        reply = {}
        if args[1:3] == ['api', 'repos/test/repo/releases']:
            reply = dict(id=7)
        elif args[1:3] == ['api', 'repos/test/repo/git/ref/tags/' + self.tag]:
            reply = dict(object=dict(type='commit', sha='b' * 40 if self.drift else SHA))
        elif args[1:3] == ['api', 'repos/test/repo/releases/7']:
            assets = [dict(a) for a in self.assets.values()] if not self.bad_assets else []
            if self.remote_mismatch and assets:
                assets[0][self.remote_mismatch] = 'wrong'
            published = any(payload == {'draft': False} for _, payload in self.calls)
            if self.bad_final and published:
                assets = []
            reply = dict(id=7, tag_name=self.tag, target_commitish=self.commitish, draft=not published,
                         prerelease='rc' in self.version, assets=assets)
        return subprocess.CompletedProcess(args, 0, json.dumps(reply), '')

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        before = {p.name: p.read_bytes() for p in Path('assets').iterdir()}
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(release.subprocess, 'run', self.github), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = release.main(list(args))
        self.assertEqual(before, {p.name: p.read_bytes() for p in Path('assets').iterdir()})
        return result, out.getvalue(), err.getvalue()

    def test_plan_uses_project_version_without_remote_writes(self):
        self.assertEqual(self.invoke('plan'), (0, 'Release plan: v0.2.0rc7 (prerelease)\n', ''))
        self.assertEqual(self.calls, [])

    def test_publish_stages_uploads_checks_then_makes_public(self):
        self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                         (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0rc7\n', ''))
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(self.calls[0][1], {'ref': 'refs/tags/v0.2.0rc7', 'sha': SHA})
        self.assertEqual(self.calls[1][1], dict(tag_name=self.tag, target_commitish=SHA,
                         name='MarsDisplay ' + self.version, draft=True, prerelease=True, generate_release_notes=True))
        for call in self.calls[2:4]:
            self.assertTrue(call[0][2].startswith('https://uploads.github.com/repos/test/repo/releases/7/assets?name='))
            self.assertNotIn('--clobber', call[0])
        self.assertEqual(self.calls[6][1], {'draft': False})

    def test_stable_version_is_not_prerelease(self):
        self.make_assets('0.2.0')
        self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                         (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0\n', ''))
        self.assertFalse(self.calls[1][1]['prerelease'])

    def test_wrong_event_branch_commit_or_repository_never_writes(self):
        for key, value in [('GITHUB_EVENT_NAME', 'push'), ('GITHUB_REF', 'refs/heads/other'),
                           ('GITHUB_SHA', 'main'), ('GITHUB_REPOSITORY', '../other')]:
            with self.subTest(key=key), mock.patch.dict(self.env, {key: value}):
                self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                                 (1, '', 'Release error: A manual main run with an exact commit and repository is required.\n'))
                self.assertEqual(self.calls, [])

    def test_tag_sha_not_target_commitish_metadata_binds_the_release(self):
        self.commitish = 'main'  # API documents this as unused for an existing tag.
        self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                         (0, 'Published https://github.com/test/repo/releases/tag/v0.2.0rc7\n', ''))
        self.assertEqual(self.calls[5][0][2], 'repos/test/repo/git/ref/tags/' + self.tag)

    def test_invalid_version_never_writes(self):
        Path('pyproject.toml').write_text('[project]\nversion = "0.2.0; unsafe"\n')
        self.assertEqual(self.invoke('plan'), (1, '', 'Release error: Use a numeric X.Y.Z or X.Y.ZrcN project version.\n'))
        self.assertEqual(self.calls, [])

    def test_bad_checksum_or_wrong_source_never_writes(self):
        for mismatch in ('checksum', 'source', 'extra', 'version', 'target', 'payload'):
            with self.subTest(mismatch=mismatch):
                self.make_assets(commit='b' * 40 if mismatch == 'source' else SHA,
                                 artifact_version='0.1.0' if mismatch == 'version' else None,
                                 target='wrong' if mismatch == 'target' else 'Windows-x64',
                                 bad_hash=mismatch == 'payload')
                if mismatch == 'checksum':
                    next(Path('assets').glob('*.sha256')).write_text('invalid')
                if mismatch == 'extra':
                    Path('assets/extra.txt').write_text('unexpected')
                self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                                 (1, '', 'Release error: Release assets do not match the qualified version and commit.\n'))
                self.assertEqual(self.calls, [])

    def test_existing_tag_or_upload_failure_stops_without_retry_or_publish(self):
        for fail_at in (1, 3, 4):
            with self.subTest(fail_at=fail_at):
                self.calls = []
                self.fail_at = fail_at
                self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                                 (1, '', 'Release error: GitHub operation failed: simulated failure\n'))
                self.assertEqual(len(self.calls), fail_at)
                self.assertFalse(any(data == {'draft': False} for _, data in self.calls))

    def test_missing_uploaded_assets_or_tag_drift_never_publishes(self):
        for bad_assets, drift, count in [(True, False, 5), (False, True, 6)]:
            with self.subTest(bad_assets=bad_assets, drift=drift):
                self.calls = []
                self.bad_assets, self.drift = bad_assets, drift
                self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                                 (1, '', 'Release error: GitHub release or tag readback did not match; inspect GitHub before rerunning.\n'))
                self.assertEqual(len(self.calls), count)
                self.assertFalse(any(data == {'draft': False} for _, data in self.calls))

    def test_remote_asset_fields_must_match_before_publish(self):
        for field in ('name', 'size', 'state', 'digest'):
            with self.subTest(field=field):
                self.calls = []
                self.remote_mismatch = field
                self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                                 (1, '', 'Release error: GitHub release or tag readback did not match; inspect GitHub before rerunning.\n'))
                self.assertEqual(len(self.calls), 5)

    def test_failed_final_readback_is_not_reported_as_success_or_retried(self):
        self.bad_final = True
        self.assertEqual(self.invoke('publish', '--artifacts', 'assets'),
                         (1, '', 'Release error: GitHub release or tag readback did not match; inspect GitHub before rerunning.\n'))
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(sum(data == {'draft': False} for _, data in self.calls), 1)
