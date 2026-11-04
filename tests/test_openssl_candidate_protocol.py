"""S2/S3/S5: mocked orchestration, not Windows build proof."""
import hashlib
import io
import subprocess
import unittest
import urllib.request
from unittest.mock import Mock, patch
import test_openssl_candidate as fixtures


class CandidateProtocolTests(unittest.TestCase):
    setUp = fixtures.OpenSSLCandidateTests.setUp
    layout = fixtures.OpenSSLCandidateTests.layout

    def test_build_sequence_failure_and_source_drift(self):
        m = self.module
        for failure in (None, 0, 1, 2, "drift"):
            with self.subTest(failure=failure):
                calls = []
                def run(command, **kw):
                    calls.append((command, kw))
                    if failure == len(calls) - 1:
                        raise subprocess.CalledProcessError(7, command)
                with (patch.object(m.inputs, 'extract_source', return_value=self.root / 'source'),
                      patch.object(m.inputs, 'fingerprint', side_effect=[{}, {'drift': 1} if failure == 'drift' else {}]),
                      patch.object(m.subprocess, 'run', side_effect=run),
                      patch.object(m, 'digest', return_value={'sha256': 'a'*64, 'size': 2}) as digest):
                    args = (str(failure), self.root, self.root, self.layout())
                    if failure is None:
                        self.assertEqual(m.build_once(*args)['upstream_tests'], 'passed')
                        self.assertEqual(digest.call_count, 2)
                    else:
                        error = ValueError if failure == 'drift' else subprocess.CalledProcessError
                        with self.assertRaises(error) as caught:
                            m.build_once(*args)
                        if failure == 'drift':
                            self.assertEqual(str(caught.exception), 'OpenSSL source changed during compilation')
                        else:
                            self.assertEqual(caught.exception.returncode, 7)
                        digest.assert_not_called()
                self.assertEqual(len(calls), 3 if failure in (None, 'drift') else failure + 1)
                self.assertEqual(calls[0][0][1:], ['../src/Configure', *m.CONFIGURE])
                if len(calls) > 1:
                    self.assertEqual(calls[1][0][1:], ['/nologo'])
                if len(calls) > 2:
                    self.assertEqual(calls[2][0][1:], ['/nologo', 'test'])
                for _, kw in calls:
                    self.assertTrue(kw['check'])
                    self.assertEqual(kw['cwd'], self.root / str(failure) / 'build')

    def test_download_bounds_pins_and_existing_input_preservation(self):
        m = self.module
        record = {'url': 'https://example.invalid/fixed', 'filename': 'fixed',
                  'size': 2, 'sha256': hashlib.sha256(b'ok').hexdigest()}
        for data, message in ((b'ok', None), (b'bad', 'Downloaded input exceeds pinned size'),
                              (b'no', 'Downloaded input does not match its pin'),
                              (b'', 'Downloaded input does not match its pin')):
            directory = self.root / ('case' + str(len(data)) + data.hex())
            opener = Mock()
            opener.open.return_value = io.BytesIO(data)
            with (patch.dict(m.ARCHIVES, {'fixture': record}, clear=True),
                  patch.object(m.urllib.request, 'build_opener', return_value=opener),
                  patch.object(m.subprocess, 'run') as execute):
                if message:
                    with self.assertRaises(ValueError) as caught:
                        m.fetch(directory)
                    self.assertEqual(str(caught.exception), message)
                else:
                    m.fetch(directory)
                before = hashlib.sha256((directory / 'fixed').read_bytes()).digest()
                opener.reset_mock()
                with self.assertRaises(FileExistsError):
                    m.fetch(directory)
                opener.open.assert_not_called()
                execute.assert_not_called()
                self.assertEqual(hashlib.sha256((directory / 'fixed').read_bytes()).digest(), before)

    def test_redirect_downgrade_rejected(self):
        handler = self.module.HTTPSRedirect()
        request = urllib.request.Request('https://example.invalid/source')
        for url in ('http://example.invalid/file', 'file:///private', 'ftp://example.invalid/file'):
            with self.subTest(url=url), self.assertRaises(ValueError) as caught:
                handler.redirect_request(request, None, 302, 'Found', {}, url)
            self.assertEqual(str(caught.exception), 'Non-HTTPS input redirect is forbidden')
        redirected = handler.redirect_request(request, None, 302, 'Found', {}, 'https://example.invalid/asset')
        self.assertEqual(redirected.full_url, 'https://example.invalid/asset')
