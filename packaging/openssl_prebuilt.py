"""Prepare pinned FireDaemon OpenSSL DLLs; never compile or search ambient PATH."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

URL = 'https://download.firedaemon.com/FireDaemon-OpenSSL/openssl-3.5.9.zip'
ARCHIVE_SHA256 = '76da391395be029b44794857b9ff380255e02a0960a98314cd3f6a6816d82696'
ARCHIVE_SIZE = 43379394
DLLS = {
    'libcrypto-3-x64.dll': {'sha256': '5268a29c9a5e353770b894f3dbd148ee8c60971aa1620713c54d8e56563d0aca', 'size': 7225016},
    'libssl-3-x64.dll': {'sha256': '00520a8ca63ec624969742aa04e7db2af94ba0d3f5fe204cbd114b4ec1f24752', 'size': 1500856},
}


def _plain(path):
    path = Path(path).absolute()
    if any(item.is_symlink() or item.is_junction() for item in (path, *path.parents)):
        raise ValueError('Linked OpenSSL input or output')
    return path


def _read(path, size):
    path = _plain(path)
    if not path.is_file() or path.stat().st_size != size:
        raise ValueError('Pinned OpenSSL input size mismatch')
    with path.open('rb') as stream:
        return stream.read(size + 1)


def _matches(data, record):
    return len(data) == record['size'] and hashlib.sha256(data).hexdigest() == record['sha256']


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Non-HTTPS OpenSSL redirect')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch(destination):
    """Download only the fixed public archive, verifying bytes before writing."""
    destination = _plain(destination)
    if destination.exists():
        raise FileExistsError('OpenSSL archive output already exists')
    opener = urllib.request.build_opener(HTTPSRedirect())
    request = urllib.request.Request(URL, headers={'User-Agent': 'MarsDisplay-build/1.0'})
    with opener.open(request, timeout=60) as response:
        data = response.read(ARCHIVE_SIZE + 1)
    if not _matches(data, {'size': ARCHIVE_SIZE, 'sha256': ARCHIVE_SHA256}):
        raise ValueError('Pinned OpenSSL archive mismatch')
    with destination.open('xb') as stream:
        stream.write(data)
    return destination


def prepare(archive_path, destination):
    """Verify archive and both selected members before creating a new directory."""
    destination = _plain(destination)
    if destination.exists():
        raise FileExistsError('OpenSSL directory already exists')
    data = _read(archive_path, ARCHIVE_SIZE)
    if not _matches(data, {'size': ARCHIVE_SIZE, 'sha256': ARCHIVE_SHA256}):
        raise ValueError('Pinned OpenSSL archive mismatch')
    selected = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name, record in DLLS.items():
            member_name = 'x64/bin/' + name
            members = [item for item in archive.infolist() if item.orig_filename == member_name]
            if len(members) != 1:
                raise ValueError('Missing or duplicate pinned OpenSSL member')
            member = members[0]
            if (member.filename != member_name or member.file_size != record['size']
                    or member.flag_bits & 1 or member.external_attr & 0x400
                    or stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG)):
                raise ValueError('Invalid pinned OpenSSL member')
            with archive.open(member) as stream:
                value = stream.read(record['size'] + 1)
            if not _matches(value, record) or not value.startswith(b'MZ'):
                raise ValueError('Pinned OpenSSL DLL mismatch')
            selected[name] = value
    destination.mkdir()
    for name, value in selected.items():
        with (destination / name).open('xb') as stream:
            stream.write(value)
    return destination


def collect(directory):
    """Return only the pinned pair for Qt; missing/mismatched inputs never fall back."""
    directory = _plain(directory)
    result = []
    for name, record in DLLS.items():
        try:
            data = _read(directory / name, record['size'])
        except (OSError, ValueError):
            raise ValueError('Pinned OpenSSL DLL mismatch') from None
        if not _matches(data, record):
            raise ValueError('Pinned OpenSSL DLL mismatch')
        result.append((str(directory / name), '.'))
    return result


def verify_signatures(directory):
    """Ask Windows to validate signatures without loading either downloaded DLL."""
    collect(directory)
    script = """$ErrorActionPreference = 'Stop'
foreach ($name in @('libcrypto-3-x64.dll', 'libssl-3-x64.dll')) {
    $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $env:MARSDISPLAY_OPENSSL_VERIFY_ROOT $name)
    Write-Output ($name + ':' + [string]$signature.Status)
    if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate) { exit 1 }
    $signer = $signature.SignerCertificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
    if ($signer -ne 'FireDaemon Technologies Limited') { Write-Output ($name + ':UnexpectedSigner'); exit 1 }
}
"""
    executable = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    # Python inherits PS7 paths; let Windows PowerShell rebuild its own module path.
    env = {key: value for key, value in os.environ.items() if key.upper() != 'PSMODULEPATH'}
    env['MARSDISPLAY_OPENSSL_VERIFY_ROOT'] = str(directory)
    result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-Command', script],
                            env=env,
                            capture_output=True, timeout=120, check=False)
    if result.returncode:
        statuses = ('Valid', 'NotSigned', 'HashMismatch', 'NotTrusted', 'UnknownError',
                    'NotSupportedFileFormat', 'Incompatible', 'UnexpectedSigner')
        allowed = {(name + ':' + status).encode('ascii') for name in DLLS for status in statuses}
        for line in result.stdout.splitlines():
            if line in allowed:
                print('OpenSSL signature ' + line.decode('ascii'), file=sys.stderr)
        raise ValueError('OpenSSL Authenticode verification failed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Use an already downloaded pinned ZIP instead of HTTPS download')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'build/openssl-prebuilt',
                        help='New DLL directory (default: project build/openssl-prebuilt)')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        print('OpenSSL preparation requires Windows.', file=sys.stderr)
        return 1
    phase = 'output'
    try:
        destination = _plain(args.output)
        if destination.exists():
            raise FileExistsError('OpenSSL directory already exists')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if args.archive is None:
            with tempfile.TemporaryDirectory(prefix='openssl-fetch-', dir=destination.parent) as temporary:
                phase = 'download'
                archive = fetch(Path(temporary) / 'openssl.zip')
                phase = 'archive'
                prepare(archive, destination)
        else:
            phase = 'archive'
            prepare(args.archive, destination)
        phase = 'signatures'
        verify_signatures(destination)
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        detail = phase + '; ' + type(error).__name__
        if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
            detail += '; HTTP ' + str(error.code)
        print('OpenSSL preparation failed (' + detail + ').', file=sys.stderr)
        return 1
    print('Prepared verified FireDaemon OpenSSL 3.5.9 (x64).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
