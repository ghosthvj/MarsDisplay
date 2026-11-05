"""S2/S3/S4/S6/S7: offline recovery-boundary probes."""
import contextlib
import hashlib
import io
import subprocess
import unittest
from unittest.mock import Mock, patch
import test_openssl_prebuilt as fixtures


class RecoveryBoundaryTests(unittest.TestCase):
    setUp = fixtures.PrebuiltOpenSSLTests.setUp
    fixture = fixtures.PrebuiltOpenSSLTests.fixture

    def snapshot(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_http_status_boundaries_and_private_process_errors(self):
        self.fixture()
        m = self.module
        cases = [(m.urllib.error.HTTPError('https://SECRET/path', code, 'SECRET', {}, None),
                  'download', 'HTTPError' + ('; HTTP ' + str(code)
                   if type(code) is int and 100 <= code <= 599 else ''))
                 for code in (99, 100, 403, 599, 600, '403', True)]
        cases += [(subprocess.TimeoutExpired('SECRET', 120, output=b'SECRET', stderr=b'SECRET'),
                   'signatures', 'TimeoutExpired'),
                  (subprocess.CalledProcessError(1, 'SECRET', stderr=b'SECRET'),
                   'signatures', 'CalledProcessError')]
        for error, phase, detail in cases:
            with self.subTest(detail=detail):
                before = self.snapshot()
                out, err = io.StringIO(), io.StringIO()
                with (patch.object(m.sys, 'platform', 'win32'),
                      patch.object(m, 'fetch', side_effect=error if phase == 'download' else None),
                      patch.object(m, 'prepare'),
                      patch.object(m, 'verify_signatures', side_effect=error) as signatures,
                      contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
                    code = m.main(['--output', str(self.destination)])
                self.assertEqual((code, out.getvalue(), err.getvalue()),
                                 (1, '', f'OpenSSL preparation failed ({phase}; {detail}).\n'))
                if phase == 'download':
                    signatures.assert_not_called()
                self.assertEqual(self.snapshot(), before)

    def test_exact_signature_allowlist_and_failure_exit(self):
        self.fixture()
        m = self.module
        m.prepare(self.archive, self.destination)
        before = self.snapshot()
        statuses = ('Valid', 'NotSigned', 'HashMismatch', 'NotTrusted', 'UnknownError',
                    'NotSupportedFileFormat', 'Incompatible', 'UnexpectedSigner')
        verify = m.verify_signatures
        lines = [name + ':' + status for name in m.DLLS for status in statuses]
        private = ['SECRET', 'C:/SECRET/libssl-3-x64.dll:Valid',
                   'libssl-3-x64.dll:Valid SECRET', 'libssl-3-x64.dll:valid',
                   ' libssl-3-x64.dll:Valid', 'libssl-3.dll:Valid']
        out, err = io.StringIO(), io.StringIO()
        with (patch.object(m.sys, 'platform', 'win32'), patch.object(m, 'prepare'),
              patch.object(m, 'verify_signatures', side_effect=lambda directory: verify(self.destination)),
              patch.object(m.subprocess, 'run', return_value=Mock(
                  returncode=1, stdout=('\r\n'.join(lines + private)).encode(),
                  stderr=b'SECRET URL ENV PATH')),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            code = m.main(['--archive', str(self.archive), '--output', str(self.root / 'new')])
        expected = ''.join('OpenSSL signature ' + line + '\n' for line in lines)
        expected += 'OpenSSL preparation failed (signatures; ValueError).\n'
        self.assertEqual((code, out.getvalue(), err.getvalue()), (1, '', expected))
        self.assertEqual(self.snapshot(), before)

    def test_download_overrun_and_same_size_tamper_preserve_inputs(self):
        raw = self.fixture()
        m = self.module
        before = self.snapshot()
        for data in (raw + b'!', raw[:-1] + bytes([raw[-1] ^ 1])):
            stream = Mock(wraps=io.BytesIO(data))
            response = Mock()
            response.__enter__ = Mock(return_value=stream)
            response.__exit__ = Mock(return_value=False)
            opener = Mock()
            opener.open.return_value = response
            with patch.object(m.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaisesRegex(ValueError, '^Pinned OpenSSL archive mismatch$'):
                    m.fetch(self.root / 'download.zip')
            stream.read.assert_called_once_with(len(raw) + 1)
            self.assertFalse((self.root / 'download.zip').exists())
            self.assertEqual(self.snapshot(), before)
