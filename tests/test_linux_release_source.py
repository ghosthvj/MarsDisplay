"""Public source-map checks using disposable Git indexes, never project staging."""
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

ROOT = Path(__file__).resolve().parents[1]
RECIPE = (
    'AppRun', 'Dockerfile', 'MarsDisplay.desktop', 'marsdisplay.svg',
    'MarsDisplay.spec', 'Release.spec', 'appimage-tools.json',
    'attribution.py', 'build_appimage.py', 'build_evidence.py', 'entrypoint.py',
    'fetch_inputs.py', 'release_assets.py', 'runtime-inputs.json', 'smoke.py',
    'toolchain.json', 'usb_bootstrap.py',
)
DOCS = (
    'linux-prototype', 'linux-usb-measurement', 'linux-attribution',
    'linux-usb-measurement-results', 'linux-appimage', 'linux-runtime-inputs',
    'linux-build-evidence', 'linux-distribution', 'linux-usb-runtime',
    'linux-release-source', 'linux-release-assembly', 'linux-release-build', 'linux-sdk-transport',
)


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.module = load(ROOT / 'packaging/linux/release_source.py')
        self.payload = load(ROOT / 'packaging/payload.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git('init', '-q')
        self.expected = {}
        for name in RECIPE:
            self.put('packaging/linux/' + name, b'recipe\r\n')
        for name in ('README.md', 'LICENSE', 'pyproject.toml', 'requirements.txt',
                     'requirements-build.txt', '.gitattributes', 'src/app.py',
                     'tests/test_app.py', 'packaging/entrypoint.py',
                     '.github/workflows/windows-portable.yml', 'docs/releases.md'):
            self.put(name, b'base\n')
        self.registry = json.loads((ROOT / 'packaging/linux/runtime-inputs.json').read_bytes())
        for name in self.registry['retained']:
            data = (name + '\r\n').encode()
            self.put('third_party/linux-runtime/' + name, data)
            self.registry['retained'][name] = hashlib.sha256(data).hexdigest()
        self.write_registry()
        self.git('add', '.')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True).stdout

    def put(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.expected[name] = data

    def write_registry(self):
        self.put('packaging/linux/runtime-inputs.json', json.dumps(self.registry).encode())

    def snapshot(self):
        # Include the fixture index and metadata to detect any collector mutation.
        return {p.relative_to(self.root).as_posix():
                ('link', os.readlink(p)) if p.is_symlink() else ('file', p.read_bytes())
                for p in self.root.rglob('*') if p.is_symlink() or p.is_file()}

    def invoke(self, reject=False):
        before = self.snapshot()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if reject:
                with self.assertRaises(ValueError):
                    self.module.collect_source(self.root)
                result = None
            else:
                result = self.module.collect_source(self.root)
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ('', ''))
        self.assertEqual(self.snapshot(), before)
        return result

    def test_exact_mapping_and_unchanged_windows_map(self):
        baseline = self.payload.collect_source(self.root)
        self.assertEqual(self.invoke(), self.expected)
        self.assertEqual(self.payload.collect_source(self.root), baseline)
        self.assertNotIn('packaging/linux/AppRun', baseline)
        self.assertFalse(any(n.startswith('third_party/linux-runtime/') for n in baseline))

    def test_production_tree_without_nonshipping_probes(self):
        for name in ('SmokeProbe.spec', 'smoke_probe.py'):
            self.assertFalse((self.root / 'packaging/linux' / name).exists())
        self.assertEqual(self.invoke(), self.expected)

    def test_tracked_probe_sources_follow_normal_base_selection(self):
        for name in ('SmokeProbe.spec', 'smoke_probe.py'):
            self.put('packaging/linux/' + name, b'optional probe fixture\n')
        self.git('add', 'packaging/linux')
        baseline = self.payload.collect_source(self.root)
        self.assertEqual(self.invoke(), self.expected)
        self.assertEqual(self.payload.collect_source(self.root), baseline)
        for name in ('SmokeProbe.spec', 'smoke_probe.py'):
            self.assertEqual(baseline['packaging/linux/' + name], b'optional probe fixture\n')

    def test_named_optional_docs_and_workflow_only_when_tracked(self):
        names = ['docs/' + n + '.md' for n in DOCS] + ['.github/workflows/linux-appimage.yml']
        for name in names:
            self.put(name, b'named documentation\n')
        before = self.invoke()
        self.assertTrue(set(names).isdisjoint(before))
        self.git('add', 'docs', '.github')
        self.assertEqual(self.invoke(), self.expected)

    def test_neighbors_untracked_sources_and_private_names_not_exported(self):
        expected = dict(self.expected)
        for name in ('packaging/linux/neighbor.sh', 'packaging/linux/neighbor.svg',
                     'third_party/linux-runtime/neighbor.md', 'third_party/other/README.md',
                     'docs/linux-arbitrary.md', 'src/credentials.json', 'src/.env.fixture'):
            self.put(name, b'synthetic excluded fixture')
        self.git('add', '.')
        self.put('src/untracked.py', b'not tracked')
        self.put('packaging/linux/untracked.py', b'not tracked')
        self.assertEqual(self.invoke(), expected)

    def test_required_recipe_and_runtime_must_be_tracked(self):
        self.put('packaging/linux/release_source.py', b'new untracked helper')
        self.assertNotIn('packaging/linux/release_source.py', self.invoke())
        # A separate unborn index contains no recipe entries, though all bytes exist.
        with tempfile.TemporaryDirectory() as temp:
            empty = Path(temp)
            subprocess.run(['git', '-C', str(empty), 'init', '-q'], check=True)
            from unittest.mock import patch
            with patch.dict(os.environ, {'GIT_INDEX_FILE': str(empty / '.git/index')}):
                self.invoke(reject=True)

    def test_missing_or_empty_required_material_rejected(self):
        for name in ('packaging/linux/' + n for n in RECIPE):
            with self.subTest(name=name):
                original = (self.root / name).read_bytes()
                (self.root / name).write_bytes(b'')
                self.invoke(reject=True)
                (self.root / name).write_bytes(original)
        path = self.root / 'third_party/linux-runtime/LICENSE'
        path.rename(path.with_name('absent'))
        self.invoke(reject=True)

    def test_runtime_digest_and_registry_namespace_rejected(self):
        original = dict(self.registry['retained'])
        for name in ('../outside', '/absolute', 'LICENSE/child', 'license', '.env', 'credentials'):
            with self.subTest(name=name):
                self.registry['retained'] = original | {name: 'a' * 64}
                self.write_registry()
                self.invoke(reject=True)
        self.registry['retained'] = dict(original, LICENSE='0' * 64)
        self.write_registry()
        self.invoke(reject=True)
        self.registry['retained'] = {k: v for k, v in original.items() if k != 'LICENSE'}
        self.write_registry()
        self.invoke(reject=True)

    def test_invalid_download_registry_rejected_without_network(self):
        self.registry['downloads'][0]['url'] = 'https://user:password@github.com/source'
        self.write_registry()
        self.invoke(reject=True)

    def check_case_collision_rejected(self):
        self.put('src/APP.py', b'collision')
        self.git('add', 'src/APP.py')
        self.invoke(reject=True)


class LinkTests(SourceTests):
    def test_symlink_recipe_runtime_and_root_rejected(self):
        for name in ('packaging/linux/AppRun', 'third_party/linux-runtime/LICENSE'):
            path = self.root / name
            original = path.read_bytes()
            path.rename(path.with_name(path.name + '.original'))
            path.symlink_to(path.name + '.original')
            self.invoke(reject=True)
            path.unlink()
            path.write_bytes(original)
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.module.collect_source(alias)


def load_tests(loader, tests, pattern):
    suite = loader.loadTestsFromTestCase(SourceTests)
    if os.name != 'nt':
        suite.addTest(SourceTests('check_case_collision_rejected'))
        suite.addTest(LinkTests('test_symlink_recipe_runtime_and_root_rejected'))
    return suite
