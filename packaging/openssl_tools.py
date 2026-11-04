"""Prepare explicit portable tools; never discover tools through ambient PATH."""
import hashlib
import io
from pathlib import Path
import stat
import zipfile

from openssl_inputs import _plain, archive_parts

TOOLS = {
    'nasm': {
        'url': 'https://www.nasm.us/pub/nasm/releasebuilds/2.16.03/win64/nasm-2.16.03-win64.zip',
        'sha256': '3ee4782247bcb874378d02f7eab4e294a84d3d15f3f6ee2de2f47a46aa7226e6',
        'size': 513543,
        'executable': 'nasm-2.16.03/nasm.exe',
        'version': '2.16.03',
        'digest_origin': 'measured official HTTPS archive; no publisher signature claim',
    },
    'perl': {
        'url': 'https://github.com/StrawberryPerl/Perl-Dist-Strawberry/releases/download/'
               'SP_54201_64bit/strawberry-perl-5.42.0.1-64bit-portable.zip',
        'sha256': 'a1cde185656cf307b51670eed69f648b9eff15b5c518cb136e027c628e650b71',
        'size': 302439100,
        'executable': 'perl/bin/perl.exe',
        'version': '5.42.0.1',
        'digest_origin': 'publisher https://strawberryperl.com/releases.json',
    },
}
MAX_ARCHIVE = 400_000_000
MAX_FILES = 50_000
MAX_EXPANDED = 1_200_000_000
MAX_MEMBER = 64 * 1024 * 1024


def _members(archive):
    entries, spellings, total = {}, {}, 0
    members = archive.infolist()
    if len(members) > MAX_FILES:
        raise ValueError('Tool archive exceeds entry limit')
    for member in members:
        if member.orig_filename != member.filename:
            raise ValueError('Tool archive member name was normalized')
        mode = stat.S_IFMT(member.external_attr >> 16)
        allowed = (0, stat.S_IFDIR) if member.is_dir() else (0, stat.S_IFREG)
        if mode not in allowed or member.external_attr & 0x400:
            raise ValueError('Unsupported tool archive entry')
        relative = member.filename.rstrip('/')
        parts = archive_parts(relative)
        for length in range(1, len(parts) + 1):
            spelling = '/'.join(parts[:length])
            key = spelling.casefold()
            if spellings.setdefault(key, spelling) != spelling:
                raise ValueError('Ambiguous tool archive path')
        if relative.casefold() in entries:
            raise ValueError('Duplicate tool archive entry')
        if member.file_size < 0 or member.file_size > MAX_MEMBER:
            raise ValueError('Tool archive member exceeds size limit')
        total += member.file_size
        if total > MAX_EXPANDED:
            raise ValueError('Tool archive exceeds expanded size limit')
        entries[relative.casefold()] = (relative, member)
    for relative, _ in entries.values():
        for parent in Path(relative).parents:
            record = entries.get(parent.as_posix().casefold())
            if record and not record[1].is_dir():
                raise ValueError('Tool archive file shadows a directory')
    return entries


def prepare(name, archive_path, destination):
    """Verify a pinned tool archive before creating a fresh installation tree."""
    if name not in TOOLS:
        raise ValueError('Unknown controlled build tool')
    record = TOOLS[name]
    path = _plain(archive_path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Controlled tool archive must be a regular file')
    if metadata.st_size > MAX_ARCHIVE:
        raise ValueError('Controlled tool archive exceeds size limit')
    if metadata.st_size != record['size']:
        raise ValueError('Controlled tool archive mismatch')
    with path.open('rb') as stream:
        data = stream.read(MAX_ARCHIVE + 1)
    if len(data) != record['size'] or hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError('Controlled tool archive mismatch')
    destination = _plain(destination)
    if destination.exists():
        raise FileExistsError('Controlled tool destination already exists')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = _members(archive)
        executable = entries.get(record['executable'].casefold())
        if not executable or executable[1].is_dir():
            raise ValueError('Controlled executable is missing')
        with archive.open(executable[1]) as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('Controlled executable is not a PE file')
        if archive.testzip() is not None:
            raise ValueError('Tool archive CRC mismatch')
        destination.mkdir()
        for relative, member in entries.values():
            target = destination.joinpath(*relative.split('/'))
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open('xb') as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
    return destination.joinpath(*record['executable'].split('/'))
