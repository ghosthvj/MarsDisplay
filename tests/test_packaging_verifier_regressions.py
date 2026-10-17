import hashlib
from pathlib import Path
import tempfile
import unittest
import test_packaging_payload as fixtures


class PackagingVerifierRegressions(unittest.TestCase):
    def test_installed_license_parent_symlink_rejected(self):
        notices = fixtures.load('notices')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / 'external'; outside.mkdir()
            license_file = outside / 'LICENSE'; license_file.write_bytes(b'external private material')
            installed = root / 'installed'; installed.mkdir()
            (installed / 'legal').symlink_to(outside, target_is_directory=True)
            dist = fixtures.NoticeTests().missing_wheel()
            dist.files = [Path('legal/LICENSE')]
            dist.locate_file.side_effect = lambda name: installed / name
            digest = hashlib.sha256(license_file.read_bytes()).digest()
            try:
                with self.assertRaises(ValueError):
                    notices.collect_distributions(['pyserial'], lambda _: dist, material_root=root / 'absent')
            finally:
                self.assertEqual(hashlib.sha256(license_file.read_bytes()).digest(), digest)

    def test_stale_browser_revision_with_nonexecuting_file_rejected(self):
        fixture = fixtures.PayloadTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        runtime = fixture.fixture()
        runtime['_internal/playwright/driver/package/.local-browsers/chromium_headless_shell-9999/README.txt'] = b'old extracted directory'
        inventory = fixture.inventory(); inventory['browsers'][0]['revision'] = '9999'
        output = fixture.root / 'dist'; output.mkdir()
        prior = output / 'previous.zip'; prior.write_bytes(b'previous release bytes')
        digest = hashlib.sha256(prior.read_bytes()).digest()
        try:
            with self.assertRaises(ValueError):
                fixture.payload.assemble(output, '1', runtime, fixture.source(), {'LICENSE': b'notice'}, inventory)
        finally:
            self.assertEqual(hashlib.sha256(prior.read_bytes()).digest(), digest)
        self.assertEqual(list(output.iterdir()), [prior])
