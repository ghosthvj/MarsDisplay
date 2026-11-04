"""Explicit hosted-CI consent exposes only the two selected OpenSSL paths."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from test_packaging_payload import load

ROOT = Path(__file__).resolve().parents[1]


class SourceTraceTests(unittest.TestCase):
    def setUp(self):
        self.module = load('openssl_selection')
        self.env = {'MARSDISPLAY_TRACE_OPENSSL': '1', 'GITHUB_ACTIONS': 'true',
                    'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                    'PATH': 'private-path', 'PRIVATE_SECRET': 'private-secret'}
        self.names = ('libcrypto-3-x64.dll', 'libssl-3-x64.dll')
        self.entries = [(name, 'C:\\Selected SDK\\bin\\' + name, 'BINARY') for name in self.names]

    def invoke(self, entries=None, *, env=None, platform='win32'):
        out, err = StringIO(), StringIO()
        with (patch.dict(self.module.os.environ, self.env if env is None else env, clear=True),
              patch.object(self.module.sys, 'platform', platform),
              patch.object(Path, 'open', side_effect=AssertionError('Trace must not open files')),
              redirect_stdout(out), redirect_stderr(err)):
            result = self.module.trace(self.entries if entries is None else entries)
        self.assertIsNone(result)
        self.assertEqual(err.getvalue(), '')
        return out.getvalue()

    def test_default_and_non_hosted_or_non_manual_calls_are_silent(self):
        for key in ('MARSDISPLAY_TRACE_OPENSSL', 'GITHUB_ACTIONS',
                    'RUNNER_ENVIRONMENT', 'GITHUB_EVENT_NAME'):
            with self.subTest(key=key):
                env = dict(self.env)
                env.pop(key)
                self.assertEqual(self.invoke(env=env), '')
        for key, value in [('MARSDISPLAY_TRACE_OPENSSL', '0'),
                           ('RUNNER_ENVIRONMENT', 'self-hosted'),
                           ('GITHUB_EVENT_NAME', 'push')]:
            with self.subTest(key=key, value=value):
                self.assertEqual(self.invoke(env=self.env | {key: value}), '')
        self.assertEqual(self.invoke(platform='linux'), '')

    def test_opt_in_outputs_exact_two_paths_and_no_other_data(self):
        entries = self.entries + [('libssl-3.dll', 'C:/private/other.dll', 'BINARY'),
                                  ('unrelated.dll', 'C:/private/other.dll', 'BINARY')]
        expected = {'status': 'UNQUALIFIED', 'files': {
            name: {'status': 'selected', 'source_path': source}
            for name, source, _ in self.entries}}
        self.assertEqual(self.invoke(entries),
                         'OpenSSL source trace: ' + json.dumps(expected, sort_keys=True) + '\n')
        self.assertEqual(entries[:2], self.entries)

    def test_ambiguous_invalid_and_oversized_sources_are_redacted(self):
        name = self.names[0]
        cases = [(self.entries + [self.entries[0]], 'ambiguous'),
                 ([(name, '../' + name, 'BINARY')], 'unavailable'),
                 ([(name, '//server/share/' + name, 'BINARY')], 'unavailable'),
                 ([(name, 'C:/secret\n::error::/' + name, 'BINARY')], 'unavailable'),
                 ([(name, 'C:/secret:stream/' + name, 'BINARY')], 'unavailable'),
                 ([(name, 'C:/' + 'x' * 1024 + '/' + name, 'BINARY')], 'unavailable'),
                 ([(name, self.entries[0][1], 'DATA')], 'unavailable')]
        for entries, status in cases:
            with self.subTest(status=status, entries=entries[:1]):
                output = self.invoke(entries)
                value = json.loads(output.removeprefix('OpenSSL source trace: '))
                self.assertEqual(value['files'][name], {'status': status})
                self.assertEqual(len(output.splitlines()), 1)
                self.assertNotIn('secret', output)
        value = json.loads(self.invoke([]).removeprefix('OpenSSL source trace: '))
        self.assertEqual(value['files'], {name: {'status': 'missing'} for name in self.names})
        self.assertEqual(self.invoke(self.entries * 4097),
                         'OpenSSL source trace: {"status": "unavailable"}\n')

    def test_independent_boundaries_and_exact_consent_values(self):
        name, other = self.names
        prefix = 'OpenSSL source trace: '

        def expected(fact):
            return prefix + json.dumps({'status': 'UNQUALIFIED', 'files': {
                name: fact, other: {'status': 'missing'}}}, sort_keys=True) + '\n'

        good = 'C:/' + 'x' * (1024 - len(name) - 4) + '/' + name
        sources = [(good, True), (good.replace('C:', 'D:', 1), True),
                   (good + 'x', False), ('C:/a/../' + name, False),
                   ('\\\\?\\C:\\sdk\\' + name, False), ('\\\\.\\C:\\sdk\\' + name, False),
                   ('C:/sdk/' + name + ':stream', False), ('C:' + name, False),
                   ('', False), (None, False), ('C:/quote"/\u2028/' + name, True)]
        sources += [('C:/a' + chr(c) + '/' + name, False) for c in [*range(32), 127]]
        with patch('builtins.open', side_effect=AssertionError('Unexpected open')):
            for source, valid in sources:
                with self.subTest(source=source):
                    entries = [(name, source, 'BINARY')]
                    before = repr(entries)
                    fact = ({'status': 'selected', 'source_path': source}
                            if valid else {'status': 'unavailable'})
                    self.assertEqual(self.invoke(entries), expected(fact))
                    self.assertEqual(repr(entries), before)
            self.assertEqual(self.invoke([(name,), None, 0]), expected({'status': 'missing'}))
            self.assertEqual(self.invoke([(name, good, 'BINARY')] * 2),
                             expected({'status': 'ambiguous'}))
        for key, values in {'MARSDISPLAY_TRACE_OPENSSL': ['true', '01', '1 '],
                            'GITHUB_ACTIONS': ['True', '1'],
                            'GITHUB_EVENT_NAME': ['workflow_call', 'release']}.items():
            for value in values:
                self.assertEqual(self.invoke(env=self.env | {key: value}), '')

    def test_workflow_opt_in_is_manual_default_off_and_native_build_only(self):
        text = (ROOT / '.github/workflows/windows-portable.yml').read_text()
        dispatch = text.split('  workflow_dispatch:', 1)[1].split('permissions:', 1)[0]
        self.assertIn('      trace_openssl_origins:', dispatch)
        option = dispatch.split('      trace_openssl_origins:', 1)[1]
        self.assertIn('        type: boolean\n        default: false', option)
        build = text.split('      - name: Native build and isolated packaged smoke', 1)[1].split('      - name:', 1)[0]
        self.assertIn("MARSDISPLAY_TRACE_OPENSSL: ${{ github.event_name == 'workflow_dispatch' && inputs.trace_openssl_origins && '1' || '' }}", build)
        self.assertEqual(text.count('MARSDISPLAY_TRACE_OPENSSL:'), 1)
        self.assertNotIn('trace_openssl_origins', (ROOT / '.github/workflows/release.yml').read_text())
        self.assertIn('  contents: read', text)
        self.assertIn('if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }', build)
        self.assertIn('_selection.trace(a.binaries)', (ROOT / 'packaging/MarsDisplay.spec').read_text())


if __name__ == '__main__':
    unittest.main()
