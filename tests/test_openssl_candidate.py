"""Candidate construction never substitutes measurement for native admission."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_packaging_payload import load


class OpenSSLCandidateTests(unittest.TestCase):
    def setUp(self):
        inputs = load('openssl_inputs')
        with patch.dict(sys.modules, {'openssl_inputs': inputs}):
            tools = load('openssl_tools')
            with patch.dict(sys.modules, {'openssl_tools': tools}):
                self.module = load('build_openssl_candidate')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def layout(self):
        return {key: self.root / key for key in ('vc', 'sdk', 'perl', 'nasm')}

    def test_environment_does_not_inherit_flags_paths_or_openssl_overrides(self):
        with patch.dict(os.environ, {'PATH': 'untrusted', 'CL': '/evil', '_CL_': '/evil',
                                     'OPENSSL_CONF': 'private', 'PERL5LIB': 'private'}, clear=True):
            env = self.module.environment(self.layout(), self.root / 'build-a')
        self.assertNotIn('untrusted', str(env))
        self.assertNotIn('private', str(env))
        self.assertNotIn('/evil', str(env))
        self.assertNotIn('CL', env)
        self.assertNotIn('OPENSSL_CONF', env)
        self.assertEqual(env['SOURCE_DATE_EPOCH'], '1790640000')
        self.assertIn('/Brepro', env['_CL_'])
        self.assertIn('/Z7', env['_CL_'])
        self.assertIn('/experimental:deterministic', env['_CL_'])
        self.assertIn('/PDBALTPATH:openssl.pdb', env['LDFLAGS'])
        self.assertIn('--reproducible', env['ASFLAGS'])

    def test_compiler_selection_never_chooses_latest_or_ambiguous_family(self):
        versions = self.root / 'vs/VC/Tools/MSVC'
        versions.mkdir(parents=True)
        sdk = self.root / 'sdk'
        (sdk / 'bin/10.0.26100.0/x64').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, '^Exactly one MSVC 14.44 toolset is required$'):
            self.module.compiler(self.root / 'vs', sdk)
        (versions / '14.50.12345').mkdir()
        chosen = versions / '14.44.35207'
        chosen.mkdir()
        self.assertEqual(self.module.compiler(self.root / 'vs', sdk)['vc'], chosen)
        (versions / '14.44.35208').mkdir()
        with self.assertRaisesRegex(ValueError, '^Exactly one MSVC 14.44 toolset is required$'):
            self.module.compiler(self.root / 'vs', sdk)

    def test_two_matching_builds_are_required_without_creating_policy(self):
        files = {name: {'sha256': 'a' * 64, 'size': 100} for name in self.module.DLLS}
        builds = [{'id': 'a', 'files': files}, {'id': 'b', 'files': dict(files)}]
        self.module.require_equal(builds)
        self.assertEqual(list(self.root.iterdir()), [])
        for invalid in (builds[:1], [builds[0], {'id': 'b', 'files': {}}],
                        [builds[0], {'id': 'b', 'files': {name: {'sha256': 'b' * 64, 'size': 100}
                                                       for name in self.module.DLLS}}]):
            with self.assertRaisesRegex(ValueError, '^Controlled OpenSSL builds differ$'):
                self.module.require_equal(invalid)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_nonwindows_cli_preserves_existing_data_and_returns_failure(self):
        output = self.root / 'output'
        output.mkdir()
        marker = output / 'human'
        marker.write_bytes(b'keep')
        stdout, stderr = io.StringIO(), io.StringIO()
        with (patch.object(self.module.sys, 'platform', 'linux'),
              contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr)):
            code = self.module.main(['--inputs', str(self.root), '--output', str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), 'Controlled OpenSSL candidate requires Windows.\n')
        self.assertEqual(marker.read_bytes(), b'keep')
        self.assertFalse((output / 'candidate.json').exists())

    def test_windows_cli_rejects_existing_output_or_missing_inputs_without_execution(self):
        marker = self.root / 'human'
        marker.write_bytes(b'keep')
        for mode in ('existing', 'missing-inputs'):
            output = self.root / mode
            if mode == 'existing':
                output.mkdir()
            stdout, stderr = io.StringIO(), io.StringIO()
            with (self.subTest(mode=mode), patch.object(self.module.sys, 'platform', 'win32'),
                  patch.object(self.module, 'fetch') as fetch,
                  patch.object(self.module.subprocess, 'run') as execute,
                  contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr)):
                args = ['--inputs', str(self.root / 'absent'), '--output', str(output)]
                code = self.module.main(args + (['--download'] if mode == 'existing' else []))
                self.assertEqual(code, 1)
                self.assertEqual(stdout.getvalue(), '')
                self.assertEqual(stderr.getvalue(), 'Controlled OpenSSL candidate failed; no DLLs are approved.\n')
                fetch.assert_not_called()
                execute.assert_not_called()
                self.assertEqual(marker.read_bytes(), b'keep')
                self.assertFalse((output / 'candidate.json').exists())
                self.assertEqual(output.exists(), mode == 'existing')

    def test_candidate_cli_records_failures_without_admitting_or_leaking_data(self):
        archives = {}
        input_dir = self.root / 'inputs'
        input_dir.mkdir()
        for name in ('openssl', 'nasm', 'perl'):
            (input_dir / name).write_bytes(b'fixture')
            archives[name] = {'filename': name, 'size': 7,
                              'sha256': hashlib.sha256(b'fixture').hexdigest()}
        marker = self.root / 'existing-policy.json'
        marker.write_bytes(b'unchanged policy')
        same = {name: {'sha256': 'a' * 64, 'size': 100} for name in self.module.DLLS}
        for mode in ('success', 'build_error', 'unequal', 'tool_changed'):
            output = self.root / mode
            stdout, stderr = io.StringIO(), io.StringIO()

            def build(label, *args):
                if mode == 'build_error':
                    raise RuntimeError('private-secret')
                files = {} if mode == 'unequal' and label != 'build-a' else same
                return {'id': label, 'upstream_tests': 'passed', 'files': files}

            with (self.subTest(mode=mode), patch.object(self.module.sys, 'platform', 'win32'),
                  patch.dict(self.module.ARCHIVES, archives, clear=True),
                  patch.object(self.module, 'compiler', return_value=self.layout()),
                  patch.object(self.module.tools, 'prepare', side_effect=lambda n, a, d: d / 'tool.exe'),
                  patch.object(self.module, 'inventory', side_effect=[{}, {'changed': True} if mode == 'tool_changed' else {}]),
                  patch.object(self.module, 'identify', return_value={'compiler': 'fixture'}),
                  patch.object(self.module, 'build_once', side_effect=build) as built,
                  contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr)):
                code = self.module.main(['--inputs', str(input_dir), '--output', str(output)])
                report = json.loads((output / 'candidate.json').read_text())
                self.assertEqual(code, 0 if mode == 'success' else 1)
                self.assertEqual(report['completed'], mode == 'success')
                self.assertEqual(report['status'], 'UNQUALIFIED')
                self.assertIn('/experimental:deterministic', report['flags']['compiler'])
                self.assertEqual(built.call_count, 1 if mode == 'build_error' else 2)
                self.assertEqual(stdout.getvalue(), 'OpenSSL controlled candidate: ' +
                                 json.dumps(report, sort_keys=True) + '\n')
                self.assertEqual(stderr.getvalue(), '' if mode == 'success' else
                                 'Controlled OpenSSL candidate failed; no DLLs are approved.\n')
                self.assertNotIn('private-secret', stdout.getvalue())
                self.assertNotIn(str(self.root), stdout.getvalue())
                self.assertEqual(marker.read_bytes(), b'unchanged policy')

    def test_workflow_is_manual_readonly_and_uploads_only_metadata(self):
        text = Path('.github/workflows/windows-portable.yml').read_text()
        self.assertIn('workflow_dispatch:', text)
        self.assertNotIn('openssl_candidate:', text.split('workflow_dispatch:', 1)[0])
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.openssl_candidate", text)
        self.assertIn('!inputs.layout_diagnostics && !inputs.openssl_candidate', text)
        self.assertIn('release_tag cannot be combined with layout_diagnostics.', text)
        self.assertIn('contents: read', text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('path: build/openssl-candidate/candidate.json', text)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('release.yml', text)
        self.assertNotIn('gh release', text)
