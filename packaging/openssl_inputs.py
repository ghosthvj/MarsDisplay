"""Pinned source extraction and location-independent controlled-tool fingerprints.

These helpers measure inputs; they never qualify DLLs or modify native policy.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

SOURCE_COMMIT = '45e844fa2a14ec92d146bd8f5778ac130b6625fb'
SOURCE_URL = f'https://github.com/openssl/openssl/archive/{SOURCE_COMMIT}.tar.gz'
SOURCE_ROOT = f'openssl-{SOURCE_COMMIT}'
SOURCE_SHA256 = 'f54250b21795bb01240f3f9b42c384868d04460e339e39275aaaf93487f2d903'
VERSION_SHA256 = '6dae52ea88792578bc22594ec2a0a26b2cf675b925ce81ce8792a1ccdf10cdb5'
MAX_ARCHIVE = 100_000_000
MAX_SOURCE_FILE = 32 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
MAX_FILES = 100_000
MAX_TREE = 8 * 1024 * 1024 * 1024
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} | {
    f'{prefix}{number}' for prefix in ('COM', 'LPT') for number in '123456789¹²³'
}


def _plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError('Linked build input is forbidden')
    return path


def _read_archive(path):
    path = _plain(path)
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Build input must be a regular file')
    if metadata.st_size > MAX_ARCHIVE:
        raise ValueError('Input exceeds size limit')
    with path.open('rb') as stream:
        data = stream.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError('Input exceeds size limit')
    return data


def _source_members(archive):
    entries, spellings, total = {}, {}, 0
    members = archive.getmembers()
    if len(members) > MAX_FILES:
        raise ValueError('Source archive exceeds entry limit')
    for member in members:
        if not (member.isfile() or member.isdir()):
            raise ValueError('Source archive contains unsupported entries')
        name = member.name.rstrip('/')
        if name == SOURCE_ROOT and member.isdir():
            continue
        if not name.startswith(SOURCE_ROOT + '/'):
            raise ValueError('Unexpected source archive root')
        relative = name[len(SOURCE_ROOT) + 1:]
        parts = relative.split('/')
        for part in parts:
            if (part in ('', '.', '..') or part.endswith((' ', '.'))
                    or any(ord(c) < 32 or ord(c) == 127 or c in '\\:<>"|?*' for c in part)
                    or part.split('.')[0].upper() in _RESERVED):
                raise ValueError('Unsafe source archive path')
        for length in range(1, len(parts) + 1):
            spelling = '/'.join(parts[:length])
            key = spelling.casefold()
            if spellings.setdefault(key, spelling) != spelling:
                raise ValueError('Ambiguous source archive path')
        if relative.casefold() in entries:
            raise ValueError('Duplicate source archive entry')
        if member.size < 0 or member.size > MAX_SOURCE_FILE:
            raise ValueError('Source archive member exceeds size limit')
        total += member.size
        if total > MAX_EXPANDED:
            raise ValueError('Source archive exceeds expanded size limit')
        entries[relative.casefold()] = (relative, member)
    for relative, _ in entries.values():
        for parent in Path(relative).parents:
            record = entries.get(parent.as_posix().casefold())
            if record and record[1].isfile():
                raise ValueError('Source archive file shadows a directory')
    return entries


def extract_source(archive_path, destination):
    """Extract only the pinned source snapshot into a new, unlinked directory."""
    data = _read_archive(archive_path)
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('OpenSSL source digest mismatch')
    destination = _plain(destination)
    if destination.exists():
        raise FileExistsError('Controlled source destination already exists')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        entries = _source_members(archive)
        version = entries.get('version.dat')
        if not version or not version[1].isfile():
            raise ValueError('OpenSSL version input mismatch')
        with archive.extractfile(version[1]) as stream:
            if hashlib.sha256(stream.read()).hexdigest() != VERSION_SHA256:
                raise ValueError('OpenSSL version input mismatch')
        destination.mkdir()
        for relative, member in entries.values():
            target = destination.joinpath(*relative.split('/'))
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('xb') as output:
                    while block := source.read(1024 * 1024):
                        output.write(block)
    return destination


def fingerprint(directory):
    """Hash a bounded regular-file tree without exporting absolute paths."""
    directory = _plain(directory)
    if not directory.is_dir():
        raise ValueError('Build input directory is missing')
    def fail(error):
        raise error

    result, count, total = hashlib.sha256(), 0, 0
    for parent, dirs, files in os.walk(directory, followlinks=False, onerror=fail):
        dirs.sort()
        for name in dirs:
            _plain(Path(parent) / name)
        for name in sorted(files):
            path = _plain(Path(parent) / name)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('Build input must be a regular file')
            count += 1
            if count > MAX_FILES:
                raise ValueError('Build input tree exceeds entry limit')
            size, digest = 0, hashlib.sha256()
            with path.open('rb') as stream:
                while block := stream.read(1024 * 1024):
                    size += len(block)
                    total += len(block)
                    if total > MAX_TREE:
                        raise ValueError('Build input tree exceeds size limit')
                    digest.update(block)
            record = [path.relative_to(directory).as_posix(), size, digest.hexdigest()]
            result.update(json.dumps(record, separators=(',', ':')).encode('utf-8') + b'\n')
    return {'sha256': result.hexdigest(), 'files': count, 'bytes': total}
