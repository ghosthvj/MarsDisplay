"""Independent S2/S3/S7 trust and source-consumer probes; no DLL execution."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from test_packaging_payload import load


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class IndependentPrebuiltTests(unittest.TestCase):
    def test_selected_member_types_and_same_size_corruption(self):
        m = load('openssl_prebuilt')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = {name: b'MZ independent ' + name.encode() for name in m.DLLS}
            pins = {name: dict(size=len(value), sha256=hashlib.sha256(value).hexdigest())
                    for name, value in data.items()}
            for case in ('valid', 'symlink', 'reparse', 'corrupt'):
                archive, output = root / (case + '.zip'), root / case
                with zipfile.ZipFile(archive, 'w') as z:
                    for index, (name, value) in enumerate(data.items()):
                        info = zipfile.ZipInfo('x64/bin/' + name)
                        info.create_system = 3
                        info.external_attr = (stat.S_IFREG | 0o644) << 16
                        if index == 0 and case == 'symlink':
                            info.external_attr = (stat.S_IFLNK | 0o777) << 16
                        if index == 0 and case == 'reparse':
                            info.external_attr |= 0x400
                        if index == 0 and case == 'corrupt':
                            value = value[:-1] + b'!'
                        z.writestr(info, value)
                    z.writestr('x86/bin/libssl-3.dll', b'never selected')
                before, env = digest(archive), dict(os.environ)
                out, err = io.StringIO(), io.StringIO()
                with (patch.dict(m.DLLS, pins, clear=True),
                      patch.object(m, 'ARCHIVE_SIZE', archive.stat().st_size),
                      patch.object(m, 'ARCHIVE_SHA256', before),
                      contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
                    if case == 'valid':
                        m.prepare(archive, output)
                        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, data)
                        self.assertEqual(len(m.collect(output)), 2)
                    else:
                        message = 'Pinned OpenSSL DLL mismatch' if case == 'corrupt' else 'Invalid pinned OpenSSL member'
                        with self.assertRaisesRegex(ValueError, '^' + message + '$'):
                            m.prepare(archive, output)
                        self.assertFalse(output.exists())
                self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))
                self.assertEqual(digest(archive), before)
                self.assertEqual(dict(os.environ), env)

    def test_bad_pair_never_invokes_signature_process(self):
        m = load('openssl_prebuilt')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, record in m.DLLS.items():
                (root / name).write_bytes(b'X' * record['size'])
            before = {p.name: digest(p) for p in root.iterdir()}
            with patch.object(m.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, '^Pinned OpenSSL DLL mismatch$'):
                    m.verify_signatures(root)
                run.assert_not_called()
            self.assertEqual({p.name: digest(p) for p in root.iterdir()}, before)

    def test_provider_allowlist_and_native_rejection_for_both_consumers(self):
        payload, native = load('payload'), load('native_material')
        names = {'README.md', 'provenance.json', 'LICENSE.txt', 'version.txt',
                 'mkopenssl-35.cmd', '50-win-hybridcrt.conf'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'packaging').mkdir()
            (root / 'packaging/openssl_prebuilt.py').write_bytes(b'# marker')
            provider = root / 'third_party/firedaemon-openssl'
            shutil.copytree('third_party/firedaemon-openssl', provider)
            (provider / 'extra.dll').write_bytes(b'MZ not source')
            selected = payload.collect_source(root)
            prefix = 'third_party/firedaemon-openssl/'
            self.assertEqual({k[len(prefix):] for k in selected if k.startswith(prefix)}, names)
            for name in names:
                self.assertEqual(selected[prefix + name], (provider / name).read_bytes())
            policy = native.read_inputs(Path.cwd())['policy']
            runtime = {r['path']: b'MZ invalid bytes' for r in policy['components'] + policy['supplemental']}
            inventory = {'build': {'Qt': policy['qt_release']}}
            for profile in ('portable', 'usb-grouping-v1'):
                scope = runtime if profile == 'portable' else {k: v for k, v in runtime.items()
                    if k in native.GROUPING_REQUIRED | native.GROUPING_NETWORK | native.GROUPING_SSL}
                before = dict(scope)
                output = root / profile
                with self.assertRaisesRegex(ValueError, '^Native bytes do not match reviewed source policy$'):
                    native.prepare(Path.cwd(), scope, inventory, output, profile=profile)
                self.assertEqual(scope, before)
                self.assertFalse(output.exists())
