"""Public SDK builder checks; external commands run only through test fixtures."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SdkBuildTests(unittest.TestCase):
    def setUp(self):
        self.module = load(ROOT / 'packaging/linux/build_sdk.py')
        versioning = load(ROOT / 'packaging/release_version.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project, self.output = self.root / 'source', self.root / 'result'
        (self.project / 'packaging/linux').mkdir(parents=True)
        (self.project / 'src').mkdir()
        original = b'[project]\nname = "mars-display"\nversion = "0.1.0"\ndependencies = []\n[project.optional-dependencies]\nbuild = ["pyinstaller==6.22.3"]\n'
        self.record = versioning.provenance(original, 'v1.2.3', 'a' * 40)
        (self.project / 'pyproject.toml').write_bytes(versioning.render(original, 'v1.2.3'))
        (self.project / 'LICENSE').write_bytes(b'Application MIT license\n')
        for name in ('Release.spec', 'smoke.py', 'build_evidence.py'):
            (self.project / 'packaging/linux' / name).write_bytes(b'# fixture\n')
        self.record_path = self.root / 'release.json'
        self.record_path.write_text(json.dumps(self.record))
        prefix = self.root / 'sdk/python'
        prefix.mkdir(parents=True)
        archive = prefix.parent / 'Python.tar.xz'
        archive.write_bytes(b'CPython source fixture')
        self.pins = {'python': {'version': '3.13.5', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}
        (self.project / 'packaging/linux/toolchain.json').write_text(json.dumps(self.pins))
        self.sdk = dict(platform='linux', machine='x86_64', uid=1000, python='3.13.5', prefix=prefix)
        self.calls, self.failure = [], None
        self.installed_version = '1.2.3'

    def runner(self, args, **kwargs):
        self.calls.append(args)
        self.assertTrue(kwargs['check'])
        self.assertEqual(kwargs['env']['PLAYWRIGHT_BROWSERS_PATH'], '0')
        self.assertNotIn('--no-sandbox', args)
        kwargs['stdout'].write(b'private command log\n')
        if self.failure and any(str(part).endswith(self.failure) for part in args):
            raise subprocess.CalledProcessError(9, args)
        if 'pip' in args:
            for flag in ('--no-index', '--no-deps', '--no-build-isolation'):
                self.assertIn(flag, args)
            target = Path(args[args.index('--target') + 1]) / 'mars_display-1.2.3.dist-info'
            target.mkdir(parents=True)
            (target / 'METADATA').write_text('Name: mars-display\nVersion: ' + self.installed_version + '\n')
        elif 'PyInstaller' in args:
            self.assertTrue(str(args[-1]).endswith('Release.spec'))
            binary = self.output / 'onedir/MarsDisplay/MarsDisplay'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'\x7fELFbuilt application')
            binary.chmod(0o755)
        elif any(str(part).endswith('build_evidence.py') for part in args):
            notices = Path(args[args.index('--output') + 1]) / 'notices/native'
            notices.mkdir(parents=True)
            (notices / 'inventory.json').write_text('{"fixture": true}\n')

    def collect(self, roots, **kwargs):
        self.assertEqual(roots, ['PyInstaller'])
        return ([dict(name='pyinstaller', version='6.22.3', licenses=['COPYING.txt'])],
                {'COPYING.txt': b'GPL with bootloader exception fixture\n'})

    def invoke(self):
        before = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(['--project', str(self.project), '--release-record', str(self.record_path),
                                     '--output', str(self.output)], runner=self.runner, sdk=self.sdk,
                                    collector=self.collect)
        after = {p.relative_to(self.project): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        return code, stdout.getvalue(), stderr.getvalue()

    def reject(self, message):
        self.assertEqual(self.invoke(), (2, '', 'error: ' + message + '\n'))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_success_installs_stamp_builds_and_exports_only_public_notices(self):
        self.assertEqual(self.invoke(), (0, 'Prepared Linux SDK build.\n', ''))
        self.assertEqual(len(self.calls), 4)
        result = json.loads((self.output / 'build.json').read_text())
        self.assertEqual(result['release'], self.record)
        self.assertEqual(result['installed_version'], '1.2.3')
        self.assertEqual(result['checks'], ['frozen-worker-smoke', 'native-source-association'])
        binary = self.output / 'onedir/MarsDisplay/MarsDisplay'
        self.assertEqual(result['executable_sha256'], hashlib.sha256(binary.read_bytes()).hexdigest())
        public = self.output / 'notices'
        self.assertEqual((public / 'application/LICENSE').read_bytes(), (self.project / 'LICENSE').read_bytes())
        self.assertIn(b'bootloader exception', (public / 'build-tools/COPYING.txt').read_bytes())
        self.assertIn('v6.22.3.tar.gz', (public / 'build-tools/SOURCE-ACCESS.txt').read_text())
        self.assertEqual(json.loads((public / 'application/build.json').read_text()), result)
        self.assertFalse((public / 'acquisition').exists())
        self.assertFalse((public / 'build.log').exists())

    def test_root_rejected_before_commands(self):
        self.sdk['uid'] = 0
        self.reject('nonroot Linux x86_64 SDK required')

    def test_stamp_mismatch_rejected_before_commands(self):
        (self.project / 'pyproject.toml').write_bytes(b'changed')
        self.reject('stamped project does not match release record')

    def test_sdk_archive_mismatch_rejected_before_commands(self):
        (self.sdk['prefix'].parent / 'Python.tar.xz').write_bytes(b'changed')
        self.reject('SDK CPython pin mismatch')

    def test_existing_output_is_untouched(self):
        self.output.mkdir()
        (self.output / 'sentinel').write_bytes(b'keep')
        self.assertEqual(self.invoke(), (2, '', 'error: output must not exist\n'))
        self.assertEqual((self.output / 'sentinel').read_bytes(), b'keep')
        self.assertEqual(self.calls, [])

    def test_wrong_installed_version_stops_before_freezing(self):
        self.installed_version = '9.9.9'
        self.assertEqual(self.invoke(), (2, '', 'error: installed application version mismatch\n'))
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.output / 'notices').exists())
        self.assertFalse((self.output / 'build.json').exists())

    def test_failed_smoke_retains_private_diagnostics_without_public_notices(self):
        self.failure = 'smoke.py'
        self.assertEqual(self.invoke(), (2, '', 'error: SDK command failed; output retained; see build.log\n'))
        self.assertEqual(len(self.calls), 3)
        self.assertTrue((self.output / 'build.log').is_file())
        self.assertFalse((self.output / 'notices').exists())
        self.assertFalse((self.output / 'build.json').exists())
