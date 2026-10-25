"""Static admission and permission contracts; no live release is created here."""
from importlib import util
from pathlib import Path
import tempfile
import unittest

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
        self.assertEqual(text.split('\non:\n')[1].split('\npermissions:')[0], '  workflow_dispatch:\n')
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

    def test_existing_portable_routes_and_qualification_are_retained(self):
        text = (ROOT / '.github/workflows/windows-portable.yml').read_text()
        self.assertIn('  workflow_call:\n', text)
        self.assertIn('  push:\n    branches: [feat/simulated-companion, feat/native-usb-helper]', text)
        self.assertIn("      layout_diagnostics:\n        description: 'Capture isolated UI layout diagnostics without packaging'\n        type: boolean\n        default: false", text)
        self.assertIn('r.wasSuccessful() and not r.skipped', text)
        self.assertIn('python packaging/build_portable.py', text)
        self.assertIn('if: ${{ success() && !inputs.layout_diagnostics }}', text)
        self.assertIn('permissions:\n  contents: read', text)
        self.assertNotIn('contents: write', text)
