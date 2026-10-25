"""Static admission and permission contracts; no live release is created here."""
from importlib import util
from pathlib import Path
import tempfile
import unittest
import shlex
import subprocess
import sys

ROOT = Path(__file__).parents[1]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_corresponding_source_adds_only_release_workflow_and_help(self):
        spec = util.spec_from_file_location('release_source_payload', ROOT / 'packaging/payload.py')
        payload = util.module_from_spec(spec)
        spec.loader.exec_module(payload)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = {'.github/workflows/windows-portable.yml': b'portable'}
            for name, data in expected.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            self.assertEqual(payload.collect_source(root), expected)
            expected.update({'.github/workflows/release.yml': b'release', 'docs/releases.md': b'help'})
            for name, data in expected.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            (root / 'docs/unrelated.md').write_text('not corresponding release source')
            self.assertEqual(payload.collect_source(root), expected)

    def test_manual_main_plan_precedes_read_only_reused_builder(self):
        text = (ROOT / '.github/workflows/release.yml').read_text()
        dispatch = text.split('\non:\n')[1].split('\npermissions:')[0]
        self.assertIn('  workflow_dispatch:\n    inputs:\n      tag:', dispatch)
        self.assertIn('        required: true\n        type: string', dispatch)
        self.assertNotIn('  push:', dispatch)
        self.assertIn('permissions:\n  contents: read', text)
        self.assertIn('cancel-in-progress: false', text)
        self.assertIn('python3 -B packaging/release.py plan', text)
        self.assertIn('    needs: prepare\n    uses: ./.github/workflows/windows-portable.yml', text)
        self.assertNotIn('pull_request', text)

    def test_only_publisher_writes_after_build_success(self):
        text = (ROOT / '.github/workflows/release.yml').read_text()
        before, publisher = text.split('  publish:\n')
        self.assertNotIn('contents: write', before)
        self.assertIn('    needs: build\n', publisher)
        self.assertIn('      contents: write\n      actions: read', publisher)
        self.assertIn('--name MarsDisplay-Windows-x64 --dir release-assets', publisher)
        self.assertIn('python3 -B packaging/release.py publish --artifacts release-assets', publisher)
        self.assertNotIn('always()', publisher)
        self.assertNotIn('--clobber', text)
        self.assertEqual(text.count('          persist-credentials: false'), 2)
        self.assertEqual(text.count('          ref: ${{ github.sha }}'), 2)

    def test_tag_is_data_and_stamping_precedes_sdk_install(self):
        release = (ROOT / '.github/workflows/release.yml').read_text()
        portable = (ROOT / '.github/workflows/windows-portable.yml').read_text()
        self.assertIn('      release_tag: ${{ inputs.tag }}', release)
        self.assertEqual(release.count('          RELEASE_TAG: ${{ inputs.tag }}'), 2)
        self.assertIn('plan --tag "$RELEASE_TAG"', release)
        self.assertIn('publish --artifacts release-assets --tag "$RELEASE_TAG"', release)
        self.assertIn('stamp --tag "$env:RELEASE_TAG"', portable)
        self.assertLess(portable.index('stamp --tag'), portable.index("python -m pip install"))
        self.assertEqual(portable.count('      release_tag:'), 2)
        self.assertIn("if: ${{ inputs.release_tag != '' && !inputs.layout_diagnostics }}", portable)
        for line in (release + portable).splitlines():
            if 'run:' in line:
                self.assertNotIn('${{ inputs.', line)
        builder = (ROOT / 'packaging/build_portable.py').read_text()
        self.assertIn('release_version.inspect(repo, revision,', builder)
        self.assertIn("inventory['release'] = release", builder)

    def test_conflicting_tag_and_diagnostics_fail_before_install(self):
        text = (ROOT / '.github/workflows/windows-portable.yml').read_text()
        step = text.split('      - name: Reject conflicting build options\n')[1].split('      - name:')[0]
        self.assertIn("if: ${{ inputs.release_tag != '' && inputs.layout_diagnostics }}", step)
        command = step.split('        run: ')[1].strip()
        argv = shlex.split(command)
        self.assertEqual(argv[:2], ['python', '-c'])
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'unchanged'
            sentinel.write_bytes(b'fixture')
            result = subprocess.run([sys.executable, *argv[1:]], cwd=folder, capture_output=True, text=True, timeout=10)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (1, '', 'release_tag cannot be combined with layout_diagnostics.\n'))
            self.assertEqual(list(Path(folder).iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b'fixture')
        self.assertLess(text.index('Reject conflicting build options'), text.index('python -m pip install'))

    def test_existing_portable_routes_and_qualification_are_retained(self):
        text = (ROOT / '.github/workflows/windows-portable.yml').read_text()
        self.assertIn('  workflow_call:\n', text)
        self.assertNotIn('  push:', text)
        self.assertIn('  workflow_dispatch:\n', text)
        self.assertIn("      layout_diagnostics:\n        description: 'Capture isolated UI layout diagnostics without packaging'\n        type: boolean\n        default: false", text)
        self.assertIn('r.wasSuccessful() and not r.skipped', text)
        self.assertIn('python packaging/build_portable.py', text)
        self.assertIn('if: ${{ success() && !inputs.layout_diagnostics }}', text)
        self.assertIn('permissions:\n  contents: read', text)
        self.assertNotIn('contents: write', text)
