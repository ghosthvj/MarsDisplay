"""Public CLI contracts for the measured acquisition slice."""
import base64
import contextlib
import hashlib
from importlib import util
import io
import json
from pathlib import Path
import shutil
import tempfile
import tarfile
import unittest
from types import SimpleNamespace
from email.message import Message
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'packaging/linux/build_evidence.py'


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        self.payload.mkdir()
        self.original = self.root / 'sdk/module.so'
        self.original.parent.mkdir()
        self.original.write_bytes(b'\x7fELFfixture')
        (self.payload / 'module.so').write_bytes(self.original.read_bytes())
        self.toc = self.root / 'COLLECT-00.toc'
        self.toc.write_text(repr(('output', [('module.so', str(self.original), 'BINARY')])))
        self.output = self.root / 'result'
        (self.root / 'pyproject.toml').write_text('[project]\ndependencies=[]\n')
        self.sdk = SimpleNamespace(root=self.root, prefix=self.root / 'python',
                                   python_version='3.13.5', distributions=[],
                                   lookup=lambda name: None, run=lambda args: '')
        spec = util.spec_from_file_location('build_evidence_test', SCRIPT)
        self.module = util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and not p.is_relative_to(self.output)}

    def invoke(self, distributions=()):
        before = self.snapshot()
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ['--payload', str(self.payload), '--toc', str(self.toc),
                '--project', str(self.root), '--output', str(self.output)]
        self.sdk.distributions = list(distributions)
        with patch.object(self.module.metadata, 'distributions', return_value=distributions), \
                patch.object(self.module, 'sdk_context', return_value=self.sdk, create=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(args)
        self.assertEqual(self.snapshot(), before)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exact_original_remains_unqualified_without_source_legal_proof(self):
        self.assertEqual(self.invoke(), (1, 'measured=1 associated=0 unresolved=1\n', ''))
        data = json.loads((self.output / 'acquisition.json').read_text())
        self.assertEqual(data['files'][0]['file'], 'module.so')
        self.assertEqual(len(data['separate_obligations']), 2)
        self.assertFalse((self.output / 'notices').exists())
        inventory = json.loads((self.output / 'association/inventory.json').read_text())
        self.assertEqual(inventory['files'], [])
        self.assertEqual(len(inventory['unresolved']), 1)

    def test_missing_original_rejected_without_output(self):
        self.toc.write_text(repr(('output', [('module.so', str(self.root / 'absent'), 'BINARY')])))
        self.assertEqual(self.invoke(), (2, '', 'build-evidence: missing or changed original: module.so\n'))
        self.assertFalse(self.output.exists())

    def test_changed_original_rejected(self):
        self.original.write_bytes(b'\x7fELFchanged')
        self.assertEqual(self.invoke(), (2, '', 'build-evidence: missing or changed original: module.so\n'))
        self.assertFalse(self.output.exists())

    def test_ambiguous_original_rejected(self):
        other = self.root / 'other.so'
        other.write_bytes(self.original.read_bytes())
        self.toc.write_text(repr(('output', [('module.so', str(p), 'BINARY')
                                           for p in (self.original, other)])))
        self.assertEqual(self.invoke(), (2, '', 'build-evidence: ambiguous original: module.so\n'))
        self.assertFalse(self.output.exists())

    def distribution(self, digest):
        from importlib.metadata import PackagePath
        from types import SimpleNamespace
        entry = PackagePath('module.so')
        entry.hash = SimpleNamespace(mode='sha256', value=digest)
        entry.size = self.original.stat().st_size
        return SimpleNamespace(files=[entry], metadata={'Name': 'fixture', 'Version': '1'},
                               locate_file=lambda name: self.original.parent / name)

    def test_record_digest_rejected(self):
        self.assertEqual(self.invoke([self.distribution('wrong')]),
                         (2, '', 'build-evidence: invalid wheel RECORD: module.so\n'))
        self.assertFalse(self.output.exists())

    def test_exact_record_is_measured_not_source_approval(self):
        digest = base64.urlsafe_b64encode(hashlib.sha256(self.original.read_bytes()).digest()).decode().rstrip('=')
        self.assertEqual(self.invoke([self.distribution(digest)]),
                         (1, 'measured=1 associated=0 unresolved=1\n', ''))
        item = json.loads((self.output / 'acquisition.json').read_text())['files'][0]
        self.assertEqual(item['wheel_records'], [{'name': 'fixture', 'version': '1', 'record': 'module.so'}])
        self.assertFalse((self.output / 'notices').exists())

    def test_existing_output_preserved(self):
        self.output.mkdir()
        sentinel = self.output / 'sentinel'
        sentinel.write_text('unchanged')
        self.assertEqual(self.invoke(), (2, '', 'build-evidence: output must not exist\n'))
        self.assertEqual(sentinel.read_text(), 'unchanged')

    def test_complete_package_acquisition(self):
        self.package_fixture()
        self.assertEqual(self.invoke(), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        inventory = json.loads((self.output / 'notices/native/inventory.json').read_text())
        owner = inventory['files'][0]['owner']
        self.assertEqual(owner['source'], dict(name='fixture-source', version='2.0-1ubuntu1',
                         reference='https://launchpad.net/ubuntu/+source/fixture-source/2.0-1ubuntu1'))
        self.assertEqual(owner['name'], 'libfixture:amd64')
        self.assertIn(b'fixture copyright', (self.output / 'notices' / owner['licenses'][0]).read_bytes())
        self.assertFalse((self.output / 'notices/originals').exists())
        self.assertNotIn(str(self.root), (self.output / 'notices/native/inventory.json').read_text())

    def package_fixture(self):
        original = self.root / 'usr/lib/libfixture.so.1'
        original.parent.mkdir(parents=True)
        original.write_bytes(self.original.read_bytes())
        self.original = original
        self.toc.write_text(repr(('output', [('module.so', str(original), 'BINARY')])))
        self.md5 = self.root / 'var/lib/dpkg/info/libfixture:amd64.md5sums'
        self.md5.parent.mkdir(parents=True)
        self.md5.write_text(hashlib.md5(original.read_bytes()).hexdigest() + '  usr/lib/libfixture.so.1\n')
        self.copyright = self.root / 'usr/share/doc/libfixture/copyright'
        self.copyright.parent.mkdir(parents=True)
        self.copyright.write_text('fixture copyright\n')
        self.package_fields = 'libfixture:amd64\t1.0-1\tfixture-source\t2.0-1ubuntu1\tinstalled\n'
        self.search_owner = 'libfixture:amd64'
        self.calls = []
        def run(args):
            self.calls.append(args)
            if args[1] == '--search':
                return self.search_owner + ': /usr/lib/libfixture.so.1\n'
            if args[1] == '--show':
                return self.package_fields
            raise AssertionError(args)
        self.sdk.run = run

    def rejection(self, reason, distributions=()):
        self.assertEqual(self.invoke(distributions), (1, 'measured=1 associated=0 unresolved=1\n', ''))
        self.assertFalse((self.output / 'notices').exists())
        data = json.loads((self.output / 'acquisition.json').read_text())
        self.assertEqual(data['files'][0]['unresolved'], reason)

    def test_wrong_package_owner_cannot_qualify(self):
        self.package_fixture()
        self.search_owner = 'wrong:amd64'
        self.rejection('package query identity mismatch')

    def test_package_md5_must_match(self):
        self.package_fixture()
        self.md5.write_text('0' * 32 + '  usr/lib/libfixture.so.1\n')
        self.rejection('package content hash mismatch')

    def test_missing_package_source_cannot_qualify(self):
        self.package_fixture()
        self.package_fields = 'libfixture:amd64\t1.0-1\t\t\tinstalled\n'
        self.rejection('missing installed package source identity')

    def test_missing_package_legal_cannot_qualify(self):
        self.package_fixture()
        self.copyright.write_bytes(b'')
        self.rejection('missing package copyright')

    def python_fixture(self):
        toolchain = json.loads((SCRIPT.parent / 'toolchain.json').read_text())
        version = '3.13.5'
        archive = self.root / 'Python.tar.xz'
        with tarfile.open(archive, 'w:xz') as stream:
            info = tarfile.TarInfo('Python-' + version + '/LICENSE')
            text = b'Python license fixture'
            info.size = len(text)
            stream.addfile(info, io.BytesIO(text))
        toolchain['python']['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        directory = self.root / 'packaging/linux'
        directory.mkdir(parents=True)
        (directory / 'toolchain.json').write_text(json.dumps(toolchain))
        original = self.sdk.prefix / 'lib/libpython3.13.so.1.0'
        original.parent.mkdir(parents=True)
        original.write_bytes(self.original.read_bytes())
        self.toc.write_text(repr(('out', [('module.so', str(original), 'BINARY')])))
        return archive

    def test_cpython_archive_pin_and_license_complete(self):
        self.python_fixture()
        self.assertEqual(self.invoke(), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        data = json.loads((self.output / 'notices/native/inventory.json').read_text())
        self.assertEqual(data['files'][0]['owner']['source']['version'], '3.13.5')
        self.assertEqual((self.output / 'notices/cpython/LICENSE').read_bytes(), b'Python license fixture')

    def test_cpython_pin_mismatch_cannot_qualify(self):
        archive = self.python_fixture()
        archive.write_bytes(b'changed')
        self.rejection('CPython source archive hash mismatch')

    def vendor_fixture(self, browser=False):
        from importlib.metadata import PackagePath
        driver = self.root / 'site/playwright/driver'
        texts = {'LICENSE': b'Node license', 'package/LICENSE': b'Playwright license',
                 'package/NOTICE': b'Playwright notice', 'package/ThirdPartyNotices.txt': b'Vendor notices',
                 'package/package.json': json.dumps(dict(name='playwright-core',
                     version='1.64.0-beta-1791568591000')).encode(),
                 'node': b'\x7fELFfixture'}
        registry = [dict(name='chromium-headless-shell', revision='1248', browserVersion='156.0.8078.4'),
                    dict(name='ffmpeg', revision='1011')]
        texts['package/browsers.json'] = json.dumps(dict(browsers=registry)).encode()
        for directory in ('chromium_headless_shell-1248', 'ffmpeg-1011'):
            texts['package/.local-browsers/' + directory + '/LICENSE'] = b'Browser license'
        chrome = 'package/.local-browsers/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell'
        texts[chrome] = b'\x7fELFfixture'
        for name, data in texts.items():
            path = driver / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        meta = Message()
        meta['Name'], meta['Version'] = 'playwright', '1.64.0'
        meta['Home-page'] = 'https://playwright.dev'
        files = []
        for name, data in texts.items():
            if '.local-browsers' in name:
                continue
            entry = PackagePath('playwright/driver/' + name)
            entry.hash = SimpleNamespace(mode='sha256', value=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('='))
            entry.size = len(data)
            files.append(entry)
        dist = SimpleNamespace(files=files, metadata=meta, requires=[], locate_file=lambda name: self.root / 'site' / name)
        self.sdk.lookup = lambda name: dist
        self.sdk.run = lambda args: 'v24.13.0\n'
        original = driver / (chrome if browser else 'node')
        self.toc.write_text(repr(('out', [('module.so', str(original), 'BINARY')])))
        return dist, driver

    def test_node_verified_record_and_actual_version_complete(self):
        dist, _ = self.vendor_fixture()
        self.assertEqual(self.invoke([dist]), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        data = json.loads((self.output / 'notices/native/inventory.json').read_text())
        self.assertEqual(data['files'][0]['owner']['source']['reference'],
                         'https://nodejs.org/dist/v24.13.0/node-v24.13.0.tar.xz')
        installed = json.loads((self.output / 'notices/installed.json').read_text())
        self.assertEqual(installed['shipped_browsers'], [])
        self.assertIn('ffmpeg', [item['name'] for item in installed['vendor']])

    def test_chromium_registry_identity_complete(self):
        dist, _ = self.vendor_fixture(browser=True)
        self.assertEqual(self.invoke([dist]), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        data = json.loads((self.output / 'notices/native/inventory.json').read_text())
        self.assertEqual(data['files'][0]['owner']['source']['version'], '156.0.8078.4')
        self.assertIn('156.0.8078.4', data['files'][0]['owner']['source']['reference'])
        installed = json.loads((self.output / 'notices/installed.json').read_text())
        self.assertEqual(installed['shipped_browsers'], ['chromium-headless-shell'])

    def test_browser_missing_source_version_cannot_qualify(self):
        dist, driver = self.vendor_fixture(browser=True)
        path = driver / 'package/browsers.json'
        data = json.loads(path.read_text())
        data['browsers'][0].pop('browserVersion')
        path.write_text(json.dumps(data))
        # Update RECORD to isolate the source-identity rule, not RECORD corruption.
        for entry in dist.files:
            content = Path(dist.locate_file(entry)).read_bytes()
            entry.hash.value = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip('=')
            entry.size = len(content)
        self.rejection('missing Chromium source version', [dist])

    def wheel_fixture(self, name='greenlet', version='3.5.6'):
        digest = base64.urlsafe_b64encode(hashlib.sha256(self.original.read_bytes()).digest()).decode().rstrip('=')
        dist = self.distribution(digest)
        meta = Message()
        meta['Name'], meta['Version'] = name, version
        meta['Home-page'] = 'https://example.org/project'
        dist.metadata = meta
        dist.requires = []
        (self.original.parent / 'LICENSE').write_bytes(b'wheel license fixture')
        from importlib.metadata import PackagePath
        dist.files.append(PackagePath('LICENSE'))
        self.sdk.lookup = lambda requested: dist
        return dist

    def test_wheel_source_and_notices_complete(self):
        dist = self.wheel_fixture()
        self.assertEqual(self.invoke([dist]), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        data = json.loads((self.output / 'notices/native/inventory.json').read_text())
        item = data['files'][0]['owner']
        self.assertEqual(item['source']['reference'],
                         'https://github.com/python-greenlet/greenlet/archive/refs/tags/3.5.6.tar.gz')
        self.assertEqual((self.output / 'notices' / item['licenses'][0]).read_bytes(), b'wheel license fixture')

    def test_qt_keeps_reviewed_immutable_and_full_release_routes(self):
        dist = self.wheel_fixture('PySide6_Essentials', '6.12.0')
        for directory in ('native-material', 'license-material'):
            shutil.copytree(SCRIPT.parents[2] / 'third_party' / directory,
                            self.root / 'third_party' / directory)
        self.assertEqual(self.invoke([dist]), (0, 'measured=1 associated=1 unresolved=0\n', ''))
        directions = (self.output / 'notices/SOURCE-ACCESS.txt').read_text()
        self.assertIn('f50facb83fc3dc5f3240c854668c7a6dd93871b2.tar.gz', directions)
        self.assertIn('025bdad181de241e81bf853c8a2d7bf3d19261a9.tar.gz', directions)
        self.assertIn('qt-everywhere-src-6.12.0.tar.xz', directions)
        self.assertTrue((self.output / 'notices/native-source/provenance.json').is_file())

    def test_missing_record_hash_rejected_before_acquisition(self):
        dist = self.distribution('unused')
        dist.files[0].hash = None
        self.assertEqual(self.invoke([dist]), (2, '', 'build-evidence: invalid wheel RECORD: module.so\n'))
        self.assertFalse(self.output.exists())

    def test_missing_vendor_material_cannot_qualify(self):
        dist, driver = self.vendor_fixture()
        (driver / 'package/NOTICE').write_bytes(b'')
        self.rejection('Missing vendor material: package/NOTICE', [dist])

    def test_wrong_node_record_owner_cannot_qualify(self):
        dist, _ = self.vendor_fixture()
        dist.metadata.replace_header('Name', 'wrong-package')
        self.rejection('vendor identity lacks exact Playwright RECORD origin', [dist])

    def test_toc_is_literal_not_executable(self):
        self.toc.write_text('__import__("os").abort()')
        self.assertEqual(self.invoke(), (2, '', 'build-evidence: invalid COLLECT TOC\n'))
        self.assertFalse(self.output.exists())
