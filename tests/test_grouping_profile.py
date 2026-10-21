"""Synthetic profile checks; these do not qualify Windows binaries."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_packaging_payload import load

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'usb-grouping-v1'
REQUIRED = {
    '_internal/PySide6/' + name for name in
    ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'QtCore.pyd',
     'QtGui.pyd', 'QtWidgets.pyd', 'pyside6.abi3.dll',
     'plugins/platforms/qwindows.dll')
} | {'_internal/shiboken6/Shiboken.pyd', '_internal/shiboken6/shiboken6.abi3.dll'}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.builder = load('build_portable')
        self.module = self.builder.native_material
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        # The real registry/policy is read intact; only executable bytes and their
        # evidence are replaced for this expressly synthetic adapter test.
        self.bundle = copy.deepcopy(self.module.read_inputs(ROOT))
        self.runtime, self.facts = {}, {}
        for item in self.bundle['policy']['components'] + self.bundle['policy']['supplemental']:
            data = b'SYNTHETIC NOT EXECUTABLE ' + item['path'].encode()
            self.runtime[item['path']] = data
            item['sha256'] = hashlib.sha256(data).hexdigest()
            if item['owner']:
                item['owner']['sha256'] = item['sha256']
            self.facts[item['path']] = dict(sha256=item['sha256'], pe=item['pe'], origins=dict(
                status='matched' if item['owner'] else 'unknown', record_status='available',
                matches=[item['owner']] if item['owner'] else []))
        self.inventory = {'build': {'Qt': '6.12.0'}}
        self.enterContext(patch.object(self.module, 'read_inputs', return_value=self.bundle))
        self.evidence = SimpleNamespace(collect=Mock(side_effect=lambda data, _: {
            name: self.facts[name] for name in data}))
        self.enterContext(patch.object(self.module, '_load', return_value=self.evidence))

    def prepare(self, runtime, profile=PROFILE, name='material'):
        return self.module.prepare(self.root, runtime, self.inventory, self.root / name, profile=profile)

    def test_minimum_actual_guard_modules_are_qualified_without_browser_or_network_claims(self):
        runtime = {name: self.runtime[name] for name in REQUIRED}
        destination = self.prepare(runtime)
        with patch.object(self.builder, '_load', return_value=self.evidence):
            records, texts = self.builder.collect_native(runtime, self.inventory, destination)
        self.assertEqual({item['path'] for item in records}, {p for p in REQUIRED if '/PySide6/' in p})
        supplemental = json.loads(texts['native/supplemental.json'])['components']
        self.assertEqual({item['path'] for item in supplemental}, REQUIRED - {p for p in REQUIRED if '/PySide6/' in p})
        for record in records + supplemental:
            for reference in record['licenses'] + record['version_evidence']:
                self.assertIn('native/' + reference, texts)
        self.assertNotIn(b'Chromium', texts['native/SOURCE-ACCESS.txt'])
        self.assertEqual(self.evidence.collect.call_count, 2)
        with self.assertRaises(FileExistsError):
            self.prepare(runtime)

    def test_each_missing_required_module_unknown_native_and_changed_bytes_reject_before_output(self):
        base = {name: self.runtime[name] for name in REQUIRED}
        variants = [dict((k, v) for k, v in base.items() if k != missing) for missing in REQUIRED]
        for extra in ('_internal/PySide6/unknown.dll', '_internal/shiboken6/unknown.pyd',
                      '_internal/libssl-unknown.dll', '_internal/PySide6/Qt6Network.dll'):
            variants.append(base | {extra: b'unknown'})
        variants.append(base | {'_internal/PySide6/QtCore.pyd': b'changed'})
        for index, data in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.prepare(data, name=str(index))
            self.assertFalse((self.root / str(index)).exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_normal_profile_still_requires_full_policy_and_rejects_subsets(self):
        destination = self.module.prepare(self.root, self.runtime, self.inventory, self.root / 'normal')
        manifest = json.loads((destination / 'native.json').read_bytes())
        self.assertEqual({item['path'] for item in manifest['components']},
                         {item['path'] for item in self.bundle['policy']['components']})
        with self.assertRaisesRegex(ValueError, 'Unmapped native Qt payload'):
            self.module.prepare(self.root, {k: v for k, v in self.runtime.items() if k in REQUIRED},
                                self.inventory, self.root / 'subset')
        self.assertFalse((self.root / 'subset').exists())

    def test_unknown_profile_and_stale_evidence_fail_before_output(self):
        for profile in ('', 'subset', 'USB-grouping-v1'):
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, 'Unknown native profile'):
                self.prepare(self.runtime, profile=profile)
        key = '_internal/PySide6/QtCore.pyd'
        self.facts[key] = dict(self.facts[key], pe={'status': 'unavailable'})
        with self.assertRaisesRegex(ValueError, 'Native binary evidence'):
            self.prepare({k: v for k, v in self.runtime.items() if k in REQUIRED})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_stock_touch_plugin_requires_complete_reviewed_network_closure(self):
        # QtGui's stock TUIO plugin can pull in QtNetwork even though the Python
        # application imports only Core/Gui/Widgets. Never drop its dependencies.
        destination = self.prepare(self.runtime)
        self.assertTrue(destination.is_dir())
        base = {k: v for k, v in self.runtime.items() if k in REQUIRED}
        touch = '_internal/PySide6/plugins/generic/qtuiotouchplugin.dll'
        with self.assertRaisesRegex(ValueError, 'experimental native'):
            self.prepare(base | {touch: self.runtime[touch]}, name='broken-touch')
        self.assertFalse((self.root / 'broken-touch').exists())

    def test_optional_python_ssl_pair_is_exact_and_never_inferred_from_absent_files(self):
        base = {k: v for k, v in self.runtime.items() if k in REQUIRED}
        ssl = {k: v for k, v in self.runtime.items() if k in ('_internal/libssl-3.dll', '_internal/libcrypto-3.dll')}
        destination = self.prepare(base | ssl)
        records = json.loads((destination / 'supplemental.json').read_bytes())['components']
        self.assertEqual({item['path'] for item in records}, set(ssl) | {p for p in REQUIRED if '/shiboken6/' in p})
        with self.assertRaises(ValueError):
            self.prepare(base | {'_internal/libssl-3.dll': ssl['_internal/libssl-3.dll']}, name='partial')
        self.assertFalse((self.root / 'partial').exists())

    def test_unknown_environment_profile_rejects_before_sdk_or_source_reads(self):
        with patch.object(self.module, 'read_inputs', side_effect=AssertionError('source read')):
            with self.assertRaisesRegex(ValueError, 'Unknown native profile'):
                self.builder.inspect_environment(self.root, profile='subset')
        self.assertEqual(list(self.root.iterdir()), [])


