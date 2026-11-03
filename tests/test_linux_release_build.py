"""Host orchestration through its public CLI, real Git and real asset validation."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

from test_linux_release_source import ROOT, SourceTests, load


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SourceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.fixture.put('pyproject.toml', b'[project]\nname = "mars-display"\nversion = "0.1.0"\n')
        self.fixture.put('packaging/linux/build_sdk.py', b'# SDK fixture\n')
        self.tools = {'appimagetool-x86_64.AppImage': b'tool', 'runtime-x86_64': b'runtime'}
        self.pins = {key: {'sha256': hashlib.sha256(self.tools[name]).hexdigest()}
                     for key, name in [('appimagetool', 'appimagetool-x86_64.AppImage'), ('runtime', 'runtime-x86_64')]}
        self.fixture.put('packaging/linux/appimage-tools.json', json.dumps(self.pins).encode())
        self.fixture.git('add', '.')
        self.fixture.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-qm', 'fixture')
        self.sha = self.fixture.git('rev-parse', 'HEAD').decode().strip()
        self.fixture.put('staged.txt', b'preserve me')
        self.fixture.git('add', 'staged.txt')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'assets'
        self.module = load(ROOT / 'packaging/linux/build_release.py')
        self.calls, self.fail_stage, self.work = [], False, None
        self.bad_public_record = False

    def runner(self, args, **kwargs):
        args = list(map(str, args))
        self.calls.append(args)
        if args[0] == 'git':
            return subprocess.run(args, **kwargs)
        if 'docker' in args:
            if 'build' in args:
                self.work = Path(args[-1]).parent
                if self.fail_stage:
                    raise subprocess.CalledProcessError(1, args)
            elif 'inspect' in args:
                return subprocess.CompletedProcess(args, 0, stdout=b'sha256:' + b'b' * 64 + b'\n')
            else:
                with tarfile.open(fileobj=kwargs['stdin']) as incoming:
                    record = json.load(incoming.extractfile('release.json'))
                binary = b'\x7fELFfixture'
                manifest = dict(release=record, installed_version='1.2.3', execution_uid=10001,
                                executable_sha256=hashlib.sha256(binary).hexdigest(),
                                checks=['frozen-worker-smoke', 'native-source-association'])
                with tarfile.open(fileobj=kwargs['stdout'], mode='w') as archive:
                    for name, data in [('result/build.json', json.dumps(manifest).encode()),
                                       ('result/onedir/MarsDisplay/MarsDisplay', binary),
                                       ('result/notices/native/LICENSE', b'license'),
                                       ('result/notices/application/build.json', b'{}' if self.bad_public_record else json.dumps(manifest).encode())]:
                        member = tarfile.TarInfo(name)
                        member.size, member.mode = len(data), 0o755
                        archive.addfile(member, io.BytesIO(data))
            return subprocess.CompletedProcess(args, 0)
        script = Path(args[2]).name
        if script == 'fetch_inputs.py':
            target = Path(args[args.index('--output') + 1])
            (target / 'tools').mkdir(parents=True)
            for name, data in self.tools.items():
                (target / 'tools' / name).write_bytes(data)
            (target / 'notices/runtime').mkdir(parents=True)
            (target / 'notices/runtime/LICENSE').write_bytes(b'runtime legal material')
        elif script == 'assemble_release.py':
            target = Path(args[args.index('--output') + 1])
            (target / 'MarsDisplay.AppDir').mkdir(parents=True)
            record = json.loads(Path(args[args.index('--release-record') + 1]).read_text())
            (target / 'MarsDisplay.AppDir/release.json').write_text(json.dumps({'release': record}))
            (target / 'MarsDisplay.AppImage').write_bytes(b'\x7fELFappimage fixture')
        else:
            self.assertEqual(script, 'release_assets.py')
            return subprocess.run([args[0], args[1], str(ROOT / 'packaging/linux/release_assets.py'), *args[3:]], **kwargs)
        return subprocess.CompletedProcess(args, 0)

    def invoke(self, extra=()):
        before = self.fixture.snapshot()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(['--tag', 'v1.2.3', '--output', str(self.output), *extra],
                                    repo=self.root, runner=self.runner)
        self.assertEqual(self.fixture.snapshot(), before)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_four_assets_bind_committed_source_without_mutating_original_index(self):
        self.assertEqual(self.invoke(), (0, f'Prepared Linux release assets: {self.output}\n', ''))
        names = {p.name for p in self.output.iterdir()}
        base = 'MarsDisplay-1.2.3-Linux-x86_64'
        self.assertEqual(names, {base + suffix for suffix in ('.AppImage', '.AppImage.sha256', '-support.zip', '-support.zip.sha256')})
        with zipfile.ZipFile(self.output / (base + '-support.zip')) as archive:
            self.assertIn(b'version = "1.2.3"', archive.read('MarsDisplay/source/pyproject.toml'))
            self.assertEqual(json.loads(archive.read('MarsDisplay/inventory.json'))['source_commit'], self.sha)
            self.assertNotIn('MarsDisplay/source/staged.txt', archive.namelist())
            self.assertIn('MarsDisplay/notices/application/sdk-image.json', archive.namelist())
            self.assertFalse(any('/tools/' in name or name.endswith('.log') for name in archive.namelist()))
        self.assertTrue(all(args[0] == 'docker' for args in self.calls if 'docker' in args))

    def test_public_sdk_record_matches_the_checked_sidecar(self):
        self.bad_public_record = True
        result = self.invoke()
        self.assertEqual(result, (2, '', f'error: SDK public build record mismatch\nDiagnostics retained: {self.work}\n'))
        self.assertFalse(self.output.exists())

    def test_explicit_sudo_is_forwarded_to_build_inspect_and_transport(self):
        self.assertEqual(self.invoke(['--sudo-docker']), (0, f'Prepared Linux release assets: {self.output}\n', ''))
        self.assertTrue(all(args[:3] == ['sudo', '-n', 'docker'] for args in self.calls if 'docker' in args))

    def test_existing_output_rejects_before_any_command(self):
        self.output.mkdir()
        (self.output / 'sentinel').write_bytes(b'keep')
        self.assertEqual(self.invoke(), (2, '', 'error: output must not exist\n'))
        self.assertEqual(self.calls, [])
        self.assertEqual((self.output / 'sentinel').read_bytes(), b'keep')

    def test_failed_stage_retains_diagnostics_without_final_assets(self):
        self.fail_stage = True
        result = self.invoke()
        self.assertEqual(result, (2, '', f'error: Linux release build failed\nDiagnostics retained: {self.work}\n'))
        self.assertFalse(self.output.exists())
        self.assertTrue((self.work / 'host.log').is_file())


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(BuildTests)
