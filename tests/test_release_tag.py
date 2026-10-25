"""Manual tag and build-only version behavior through the release CLI."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import zipfile
import test_release as legacy

release = legacy.release
TAG = 'v0.3.0rc1'
VERSION = '0.3.0rc1'
STAMP = Path('build/release-version.json')


class ReleaseTagTests(unittest.TestCase):
    make_assets = legacy.ReleaseTests.make_assets
    invoke = legacy.ReleaseTests.invoke

    def setUp(self):
        legacy.ReleaseTests.setUp(self)
        self.original = b'[project]\nversion = "0.2.0rc7"\ndependencies = ["example==1.0"]\n[tool.example]\nversion = "unchanged"\n'
        Path('pyproject.toml').write_bytes(self.original)
        self.refs, self.release_tags, self.git_calls = [], '', []

    def github(self, args, **kwargs):
        if args[0] == 'git':
            self.git_calls.append(args)
            self.assertIn(args[1:], (['rev-parse', 'HEAD'], ['show', 'HEAD:pyproject.toml'], ['show', legacy.SHA + ':pyproject.toml']))
            value = legacy.SHA.encode() if args[1] == 'rev-parse' else self.original
            return subprocess.CompletedProcess(args, 0, value, b'')
        if '/git/matching-refs/tags/' in args[2]:
            self.calls.append((args, None))
            return subprocess.CompletedProcess(args, 0, json.dumps(self.refs), '')
        if '--paginate' in args:
            self.calls.append((args, None))
            return subprocess.CompletedProcess(args, 0, self.release_tags, '')
        return legacy.ReleaseTests.github(self, args, **kwargs)

    def snapshot(self):
        return {str(p): p.read_bytes() for p in Path('.').rglob('*') if p.is_file()}

    def expected_record(self):
        stamped = self.original.replace(b'"0.2.0rc7"', b'"0.3.0rc1"', 1)
        return dict(schema=1, method='project-version-v1', tag=TAG, version=VERSION,
                    source_commit=legacy.SHA, source_version='0.2.0rc7',
                    source_pyproject_sha256=hashlib.sha256(self.original).hexdigest(),
                    build_pyproject_sha256=hashlib.sha256(stamped).hexdigest())

    def prepare(self):
        self.assertEqual(self.invoke('stamp', '--tag', TAG),
                         (0, f'Prepared {TAG} from {legacy.SHA}; no commit created.\n', ''))

    def bundle(self, change=None):
        self.prepare()
        record = json.loads(STAMP.read_text())
        project = Path('pyproject.toml').read_bytes()
        if change == 'metadata':
            record['source_commit'] = 'b' * 40
        if change == 'source':
            project = project.replace(b'example==1.0', b'example==9.0')
        files = {'MarsDisplay.exe': b'fixture', 'source/pyproject.toml': project}
        inventory = dict(source_commit=legacy.SHA, target='Windows-x64', release=record,
                         files={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
        if change == 'missing':
            del inventory['release']
        for p in Path('assets').iterdir():
            p.unlink()
        archive = Path('assets') / f'MarsDisplay-{VERSION}-Windows-x64.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, data in files.items():
                z.writestr('MarsDisplay/' + name, data)
            z.writestr('MarsDisplay/inventory.json', json.dumps(inventory))
        archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        self.assets = {p.name: dict(name=p.name, size=p.stat().st_size, state='uploaded',
                                   digest='sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()) for p in Path('assets').iterdir()}
        Path('pyproject.toml').write_bytes(self.original)  # Separate publisher checkout.
        self.version, self.tag = VERSION, TAG
        self.calls = []

    def test_plan_selects_tag_and_checks_duplicates_without_changing_files(self):
        for tag, kind in ((TAG, 'prerelease'), ('v0.3.0', 'stable')):
            with self.subTest(tag=tag):
                self.calls = []
                before = self.snapshot()
                self.assertEqual(self.invoke('plan', '--tag', tag), (0, f'Release plan: {tag} ({kind})\n', ''))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(len(self.calls), 2)
                self.assertTrue(all('--method' not in args for args, _ in self.calls))

    def test_invalid_tag_never_reads_github_or_changes_source(self):
        for tag in ('0.3.0', 'v0.3.0;echo unsafe', 'v01.3.0', 'v0.3.0rc01', 'v' + '1' * 70):
            with self.subTest(tag=tag):
                before = self.snapshot()
                self.assertEqual(self.invoke('stamp', '--tag', tag),
                                 (1, '', 'Release error: Use a canonical vX.Y.Z or vX.Y.ZrcN tag.\n'))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual((self.calls, self.git_calls), ([], []))

    def test_existing_tag_or_draft_is_rejected_before_build(self):
        for ref, draft in ((True, False), (False, True)):
            with self.subTest(ref=ref, draft=draft):
                self.calls = []
                self.refs = [{'ref': 'refs/tags/' + TAG}] if ref else []
                self.release_tags = TAG + '\n' if draft else ''
                before = self.snapshot()
                self.assertEqual(self.invoke('plan', '--tag', TAG),
                                 (1, '', 'Release error: Tag or release already exists; choose a new version.\n'))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(len(self.calls), 1 if ref else 2)

    def test_stamp_changes_only_project_version_and_records_source(self):
        Path('pyproject.toml').write_bytes(self.original.replace(b'\n', b'\r\n'))
        self.prepare()
        self.assertEqual(Path('pyproject.toml').read_bytes(), self.original.replace(b'"0.2.0rc7"', b'"0.3.0rc1"', 1))
        self.assertEqual(json.loads(STAMP.read_text()), self.expected_record())
        self.assertEqual(self.calls, [])
        with patch.object(release.versioning.subprocess, 'run', self.github):
            self.assertEqual(release.versioning.inspect(Path('.'), legacy.SHA), self.expected_record())

    def test_dirty_source_or_existing_stamp_is_not_overwritten(self):
        Path('pyproject.toml').write_bytes(self.original + b'# local edit\n')
        before = self.snapshot()
        self.assertEqual(self.invoke('stamp', '--tag', TAG),
                         (1, '', 'Release error: Version stamping requires an unchanged project file and no existing stamp.\n'))
        self.assertEqual(self.snapshot(), before)
        Path('pyproject.toml').write_bytes(self.original)
        self.prepare()
        before = self.snapshot()
        self.assertEqual(self.invoke('stamp', '--tag', TAG),
                         (1, '', 'Release error: Version stamping requires an unchanged project file and no existing stamp.\n'))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls, [])

    def test_builder_rejects_changed_stamp_and_keeps_default_path(self):
        calls = []
        self.assertIsNone(release.versioning.inspect(Path('.'), legacy.SHA, lambda: calls.append('installed')))
        self.assertEqual(calls, [])
        self.prepare()
        before = self.snapshot()
        with patch.object(release.versioning.subprocess, 'run', self.github), self.assertRaisesRegex(ValueError, 'Build version provenance does not match source.'):
            release.versioning.inspect(Path('.'), legacy.SHA, lambda: '0.2.0rc7')
        self.assertEqual(self.snapshot(), before)
        Path('pyproject.toml').write_bytes(Path('pyproject.toml').read_bytes() + b'# tampered\n')
        before = self.snapshot()
        with patch.object(release.versioning.subprocess, 'run', self.github), self.assertRaisesRegex(ValueError, 'Build version provenance does not match source.'):
            release.versioning.inspect(Path('.'), legacy.SHA)
        self.assertEqual(self.snapshot(), before)

    def test_publish_uses_requested_version_and_exact_provenance(self):
        self.bundle()
        self.assertEqual(self.invoke('publish', '--tag', TAG, '--artifacts', 'assets'),
                         (0, f'Published https://github.com/test/repo/releases/tag/{TAG}\n', ''))
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(self.calls[0][1], {'ref': 'refs/tags/' + TAG, 'sha': legacy.SHA})

    def test_publisher_binds_canonical_git_blob_not_checkout_line_endings(self):
        self.bundle()
        Path('pyproject.toml').write_bytes(self.original.replace(b'\n', b'\r\n'))
        self.assertEqual(self.invoke('publish', '--tag', TAG, '--artifacts', 'assets'),
                         (0, f'Published https://github.com/test/repo/releases/tag/{TAG}\n', ''))
        self.assertIn(['git', 'show', legacy.SHA + ':pyproject.toml'], self.git_calls)

    def test_publish_rejects_unproven_stamped_source_before_remote_writes(self):
        for change in ('metadata', 'source', 'missing'):
            with self.subTest(change=change):
                if STAMP.exists():
                    STAMP.unlink()
                self.bundle(change)
                before = self.snapshot()
                self.assertEqual(self.invoke('publish', '--tag', TAG, '--artifacts', 'assets'),
                                 (1, '', 'Release error: ' + release.ASSET_ERROR + '\n'))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.calls, [])
