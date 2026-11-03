"""Offline Linux format contract, exercised through the public CLI."""
from contextlib import chdir
import hashlib
from importlib import util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'packaging/linux/release_assets.py'
spec = util.spec_from_file_location('linux_test_version', ROOT / 'packaging/release_version.py')
versioning = util.module_from_spec(spec)
spec.loader.exec_module(versioning)
ERROR = 'Linux artifact error: Invalid Linux artifact format or provenance.\n'


class LinuxReleaseAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.original = b'[project]\nname = "fixture"\nversion = "0.1.0"\n'
        (self.repo / 'pyproject.toml').write_bytes(self.original)

        def git(*args, data=None):
            return subprocess.run(['git', *args], cwd=self.repo, input=data,
                                  capture_output=True, check=True).stdout.strip()

        # Create only fixture objects: no staging, hooks, user identity or checkout
        # history. The validator reads the generated commit directly by its SHA.
        git('init', '--quiet', '--template=', '--object-format=sha1')
        blob = git('hash-object', '-w', '--stdin', data=self.original)
        tree = git('mktree', data=b'100644 blob ' + blob + b'\tpyproject.toml\n')
        identity = b'Fixture <fixture@example.invalid> 1700000000 +0000\n'
        commit = b'tree ' + tree + b'\nauthor ' + identity + b'committer ' + identity + b'\nFixture source\n'
        self.sha = git('hash-object', '-w', '-t', 'commit', '--stdin', data=commit).decode('ascii')
        self.content = self.root / 'content'
        (self.content / 'source').mkdir(parents=True)
        (self.content / 'notices').mkdir()
        (self.content / 'source/pyproject.toml').write_bytes(versioning.render(self.original, 'v1.2.3'))
        (self.content / 'notices/LICENSE.txt').write_text('Fixture, not legal clearance.')
        (self.content / 'README.md').write_text('Fixture instructions.')
        self.image = self.root / 'input.AppImage'
        self.image.write_bytes(b'fixture AppImage bytes')
        self.output = self.root / 'output'
        self.base = 'MarsDisplay-1.2.3-Linux-x86_64'

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def run_cli(self, command, *extra, ok=True):
        before = self.snapshot()
        args = ['--image', str(self.image), '--content', str(self.content), '--output', str(self.output)] if command == 'build' else ['--artifacts', str(self.output)]
        result = subprocess.run([sys.executable, '-B', str(CLI), command, *args,
                                 '--tag', 'v1.2.3', '--sha', self.sha, *extra],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, 'Linux artifact format validated; legal qualification is separate.\n', '') if ok else (1, '', ERROR))
        if not ok or command == 'check':
            self.assertEqual(self.snapshot(), before)
        else:
            self.assertEqual({k: self.snapshot()[k] for k in before}, before)

    def rewrite_zip(self, transform):
        archive = self.output / (self.base + '-support.zip')
        with zipfile.ZipFile(archive) as stream:
            members = [(item, stream.read(item)) for item in stream.infolist()]
        with zipfile.ZipFile(archive, 'w') as stream:
            for item, data in transform(members):
                stream.writestr(item, data)
        archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')

    def test_round_trip_and_upload_api(self):
        self.run_cli('build')
        self.run_cli('check')
        names = {self.base + suffix for suffix in ('.AppImage', '.AppImage.sha256', '-support.zip', '-support.zip.sha256')}
        self.assertEqual({p.name for p in self.output.iterdir()}, names)
        spec = util.spec_from_file_location('linux_assets_test', CLI)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = self.snapshot()
        with chdir(self.repo):
            for tag in ('v1.2.3', None):
                metadata = module.assets(self.output, '1.2.3', self.sha, tag)
                self.assertEqual(metadata, {p: dict(name=p.name, size=p.stat().st_size, state='uploaded',
                                                 digest='sha256:' + hashlib.sha256(p.read_bytes()).hexdigest())
                                            for p in self.output.iterdir()})
        self.assertEqual(self.snapshot(), before)

    def test_build_rejections(self):
        for name in ('source/pyproject.toml', 'notices/LICENSE.txt', 'README.md'):
            with self.subTest(missing_or_invalid=name):
                path = self.content / name
                original = path.read_bytes()
                path.write_bytes(b'')
                self.run_cli('build', ok=False)
                self.assertFalse(self.output.exists())
                path.write_bytes(original)
        for extra in (('--tag', 'v01.2.3'), ('--sha', 'bad'), ('--sha', '0' * 40),
                      ('--output', str(self.content)), ('--output', str(self.content / 'nested'))):
            with self.subTest(extra=extra):
                self.run_cli('build', *extra, ok=False)
        (self.content / 'inventory.json').write_text('{}')
        self.run_cli('build', ok=False)

    def test_build_rejects_casefolded_inventory_file(self):
        (self.content / 'INVENTORY.JSON').write_bytes(b'x')
        self.run_cli('build', ok=False)
        self.assertFalse(self.output.exists())

    def test_build_rejects_inventory_directory(self):
        (self.content / 'inventory.json').mkdir()
        (self.content / 'inventory.json/child').write_bytes(b'x')
        self.run_cli('build', ok=False)
        self.assertFalse(self.output.exists())

    def test_check_rejects_consistently_hashed_component_collisions(self):
        self.run_cli('build')
        archive = self.output / (self.base + '-support.zip')
        original = archive.read_bytes()
        for name in ('inventory.json/child', 'INVENTORY.JSON/child/deeper',
                     'INVENTORY.JSON', 'readme.MD/child'):
            with self.subTest(name=name):
                archive.write_bytes(original)

                def add_collision(members):
                    result = []
                    for item, data in members:
                        if item.filename == 'MarsDisplay/inventory.json':
                            record = json.loads(data)
                            record['files'][name] = hashlib.sha256(b'x').hexdigest()
                            data = json.dumps(record).encode()
                        result.append((item, data))
                    return result + [('MarsDisplay/' + name, b'x')]

                self.rewrite_zip(add_collision)
                self.run_cli('check', ok=False)

    def test_existing_output_is_preserved(self):
        self.run_cli('build')
        self.run_cli('build', ok=False)
        self.run_cli('check')

    def test_checksums_exact_members_and_image_binding(self):
        self.run_cli('build')
        image = self.output / (self.base + '.AppImage')
        image.write_bytes(b'tampered')
        self.run_cli('check', ok=False)
        image.with_suffix('.AppImage.sha256').write_text(hashlib.sha256(image.read_bytes()).hexdigest() + '  ' + image.name + '\n')
        self.run_cli('check', ok=False)

    def test_archive_rejections(self):
        self.run_cli('build')
        archive = self.output / (self.base + '-support.zip')
        saved = archive.read_bytes()
        checksum = archive.with_suffix('.zip.sha256')
        saved_checksum = checksum.read_bytes()

        def inventory_change(members, key, value):
            result = []
            for item, data in members:
                if item.filename == 'MarsDisplay/inventory.json':
                    record = json.loads(data)
                    record[key] = value
                    data = json.dumps(record).encode()
                result.append((item, data))
            return result

        link = zipfile.ZipInfo('MarsDisplay/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        changes = [lambda m: m + [('MarsDisplay/../escape', b'x')],
                   lambda m: m + [('MarsDisplay/README.MD', b'x')],
                   lambda m: m + [(link, b'README.md')],
                   lambda m: m + [('elsewhere/file', b'x')],
                   lambda m: m[:-1],
                   lambda m: [(i, b'changed' if i.filename.endswith('README.md') else d) for i, d in m],
                   lambda m: inventory_change(m, 'release', {}),
                   lambda m: inventory_change(m, 'source_commit', '0' * 40),
                   lambda m: inventory_change(m, 'target', 'Windows-x64'),
                   lambda m: inventory_change(m, 'files', []),
                   lambda m: [(i, self.original if i.filename.endswith('pyproject.toml') else d) for i, d in m]]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                archive.write_bytes(saved)
                checksum.write_bytes(saved_checksum)
                self.rewrite_zip(change)
                self.run_cli('check', ok=False)

    def test_extra_asset_and_wrong_identity(self):
        self.run_cli('build')
        self.run_cli('check', '--tag', 'v1.2.4', ok=False)
        self.run_cli('check', '--sha', '0' * 40, ok=False)
        (self.output / 'extra').write_bytes(b'extra')
        self.run_cli('check', ok=False)
