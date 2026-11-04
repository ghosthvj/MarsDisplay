"""Public transport checks with a simulated Docker command and real tar parsing."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.module = load(ROOT / 'packaging/linux/sdk_transport.py')
        versioning = load(ROOT / 'packaging/release_version.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source, self.output = self.root / 'source', self.root / 'output'
        (self.source / 'packaging/linux').mkdir(parents=True)
        (self.source / 'packaging/linux/build_sdk.py').write_bytes(b'# SDK fixture\n')
        original = b'[project]\nversion = "0.1.0"\n'
        self.record = versioning.provenance(original, 'v1.2.3', 'a' * 40)
        self.record_path = self.root / 'record.json'
        self.record_path.write_text(json.dumps(self.record))
        self.binary = b'\x7fELFfixture'
        self.manifest = dict(release=self.record, installed_version='1.2.3', execution_uid=10001,
                             executable_sha256=hashlib.sha256(self.binary).hexdigest(),
                             checks=['frozen-worker-smoke', 'native-source-association'])
        self.extra, self.calls, self.fail_command = [], [], False

    def runner(self, args, **kwargs):
        self.calls.append(args)
        self.assertTrue(kwargs['check'])
        self.assertIn('--pull=never', args)
        self.assertEqual(args[args.index('--user') + 1], '10001:10001')
        self.assertIn('--network=none', args)
        self.assertIn('--read-only', args)
        self.assertIn('--cap-drop=ALL', args)
        self.assertNotIn('--mount', args)
        self.assertNotIn('--privileged', args)
        with tarfile.open(fileobj=kwargs['stdin']) as incoming:
            self.assertEqual(incoming.getnames(), ['source/packaging/linux/build_sdk.py', 'release.json'])
            self.assertEqual(json.load(incoming.extractfile('release.json')), self.record)
        if self.fail_command:
            kwargs['stderr'].write(b'container failed\n')
            raise subprocess.CalledProcessError(2, args)
        with tarfile.open(fileobj=kwargs['stdout'], mode='w') as archive:
            for name, data in [('result/onedir/MarsDisplay/MarsDisplay', self.binary),
                               ('result/notices/LICENSE', b'license'),
                               ('result/build.json', json.dumps(self.manifest).encode())]:
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o755
                archive.addfile(member, io.BytesIO(data))
            for member, data in self.extra:
                archive.addfile(member, io.BytesIO(data) if data is not None else None)

    def invoke(self, **kwargs):
        before = {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        record = self.record_path.read_bytes()
        try:
            return self.module.run_sdk(self.source, self.record_path, 'sdk:fixture', self.output,
                                       runner=self.runner, **kwargs)
        finally:
            self.assertEqual(before, {p: p.read_bytes() for p in self.source.rglob('*') if p.is_file()})
            self.assertEqual(record, self.record_path.read_bytes())

    def test_streams_to_original_nonroot_owner_and_validates_exports(self):
        result = self.invoke()
        self.assertEqual(result, self.output / 'extracted/result')
        self.assertEqual((result / 'onedir/MarsDisplay/MarsDisplay').read_bytes(), self.binary)
        self.assertEqual(json.loads((result / 'build.json').read_text()), self.manifest)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], 'docker')

    def test_existing_output_unchanged_without_commands(self):
        self.output.mkdir()
        (self.output / 'sentinel').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, '^output must not exist$'):
            self.invoke()
        self.assertEqual((self.output / 'sentinel').read_bytes(), b'keep')
        self.assertEqual(self.calls, [])

    def test_explicit_sudo_only_wraps_docker_client(self):
        self.invoke(sudo=True)
        self.assertEqual(self.calls[0][:3], ['sudo', '-n', 'docker'])

    def test_failed_command_retains_private_log_without_extraction(self):
        self.fail_command = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.invoke()
        self.assertEqual((self.output / 'docker.log').read_bytes(), b'container failed\n')
        self.assertFalse((self.output / 'extracted').exists())

    def test_wrong_build_record_rejected_before_extraction(self):
        self.manifest['installed_version'] = '9.9.9'
        with self.assertRaisesRegex(ValueError, '^SDK build record mismatch$'):
            self.invoke()
        self.assertFalse((self.output / 'extracted').exists())

    def test_private_or_traversing_archive_member_rejected_before_extraction(self):
        for name in ('../outside', 'result/acquisition/private', 'result/onedir/MarsDisplay/MarsDisplay'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=self.root) as out:
                self.output = Path(out) / 'result'
                member = tarfile.TarInfo(name)
                member.size = 1
                self.extra = [(member, b'x')]
                with self.assertRaisesRegex(ValueError, '^unsafe SDK archive$'):
                    self.invoke()
                self.assertFalse((self.output / 'extracted').exists())
        self.assertFalse((self.root / 'outside').exists())

    def test_case_conflicting_implicit_directories_rejected(self):
        for name in ('Data/a', 'data/b'):
            member = tarfile.TarInfo('result/onedir/MarsDisplay/' + name)
            member.size = 1
            self.extra.append((member, b'x'))
        with self.assertRaisesRegex(ValueError, '^unsafe SDK archive$'):
            self.invoke()
        self.assertFalse((self.output / 'extracted').exists())

    def check_contained_alias_chain_preserved(self):
        for name, target in (('alias', 'MarsDisplay'), ('alias2', 'alias')):
            member = tarfile.TarInfo('result/onedir/MarsDisplay/' + name)
            member.type, member.linkname = tarfile.SYMTYPE, target
            self.extra.append((member, None))
        result = self.invoke()
        alias = result / 'onedir/MarsDisplay/alias2'
        self.assertTrue(alias.is_symlink())
        self.assertEqual(os.readlink(alias), 'alias')
        self.assertEqual(alias.read_bytes(), self.binary)

    def test_escaping_archive_alias_rejected_before_extraction(self):
        member = tarfile.TarInfo('result/onedir/MarsDisplay/alias')
        member.type, member.linkname = tarfile.SYMTYPE, '../../../../outside'
        self.extra = [(member, None)]
        with self.assertRaisesRegex(ValueError, '^unsafe SDK archive$'):
            self.invoke()
        self.assertFalse((self.output / 'extracted').exists())


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(TransportTests)
    if os.name != "nt":
        suite.addTest(TransportTests("check_contained_alias_chain_preserved"))
    return suite
