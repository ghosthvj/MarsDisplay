"""Bounded OpenSSL collection facts. Installation location is not source approval."""
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import stat
import sys

NAMES = ('libcrypto-3.dll', 'libssl-3.dll', 'libcrypto-3-x64.dll', 'libssl-3-x64.dll')
LOCATIONS = {'cpython-sdk', 'pyside6', 'openssl-install', 'git-install',
             'strawberry-perl', 'msys2-mingw64', 'msys2-ucrt64', 'ruby-toolcache'}
DLL_LIMIT = 32 * 1024 * 1024
REPORT_LIMIT = 4096
STATUSES = {'missing', 'ambiguous', 'unknown_location', 'unavailable'}


def _roots(source):
    roots = {'cpython-sdk': Path(sys.base_prefix) / 'DLLs'}
    try:
        roots['pyside6'] = Path(metadata.distribution('PySide6').locate_file('PySide6'))
    except Exception:
        pass
    if sys.platform == 'win32':
        programs = os.environ.get('ProgramFiles')
        drive = os.environ.get('SystemDrive')
        if programs:
            roots.update({'openssl-install': Path(programs) / 'OpenSSL/bin',
                          'git-install': Path(programs) / 'Git/mingw64/bin'})
        if drive and re.fullmatch(r'[A-Za-z]:', drive):
            root = Path(drive + '/')
            roots.update({'strawberry-perl': root / 'Strawberry/c/bin',
                          'msys2-mingw64': root / 'msys64/mingw64/bin',
                          'msys2-ucrt64': root / 'msys64/ucrt64/bin'})
        cache = os.environ.get('RUNNER_TOOL_CACHE')
        if cache:
            try:
                parts = source.relative_to(Path(cache)).parts
                if (len(parts) == 5 and parts[0].lower() == 'ruby'
                        and re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', parts[1])
                        and parts[2:4] == ('x64', 'bin')):
                    roots['ruby-toolcache'] = source.parent
            except ValueError:
                pass
    return roots


def _read_regular(path, limit):
    # Check from the root down before opening a file through any parent link.
    for part in reversed((path, *path.parents)):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Linked evidence')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('Unbounded evidence')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Unbounded evidence')
    return data


def capture(entries, *, roots=None):
    """Capture only four exact binary destinations, without exporting SDK paths."""
    selected = {name: [] for name in NAMES}
    if not isinstance(entries, (list, tuple)) or len(entries) > 8192:
        return {name: {'status': 'unavailable'} for name in NAMES}
    for entry in entries:
        if (isinstance(entry, (list, tuple)) and len(entry) == 3
                and isinstance(entry[0], str) and entry[0] in selected):
            selected[entry[0]].append(entry)
    result = {}
    for name, candidates in selected.items():
        fact = {'status': 'missing'}
        if len(candidates) > 1:
            fact = {'status': 'ambiguous'}
        elif candidates:
            _, source, kind = candidates[0]
            fact = {'status': 'unavailable'}
            try:
                if (kind != 'BINARY' or not isinstance(source, str) or len(source) > 4096
                        or source.startswith(('\\\\', '//'))):
                    raise ValueError('Invalid selection')
                path = Path(source)
                if not path.is_absolute() or '..' in path.parts or path.name.lower() != name:
                    raise ValueError('Invalid source')
                locations = _roots(path) if roots is None else roots
                matches = [label for label, root in locations.items()
                           if label in LOCATIONS and path.parent == Path(root)]
                if len(matches) != 1:
                    fact = {'status': 'unknown_location'}
                else:
                    data = _read_regular(path, DLL_LIMIT)
                    if not data.startswith(b'MZ'):
                        raise ValueError('Not PE material')
                    fact = {'status': 'selected', 'location': matches[0],
                            'source_sha256': hashlib.sha256(data).hexdigest()}
            except Exception:
                pass  # No raw path, environment, resource string or exception.
        result[name] = fact
    return result


def write(path, entries, *, roots=None):
    """Write once inside the builder-owned stage, never into the shipped payload."""
    report = {'schema': 1, 'files': capture(entries, roots=roots)}
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, sort_keys=True) + '\n')


def read(path, runtime):
    """Export sanitized facts only when their captured bytes match the payload."""
    try:
        report = json.loads(_read_regular(Path(path), REPORT_LIMIT))
        if (not isinstance(report, dict) or report.get('schema') != 1
                or not isinstance(report.get('files'), dict)):
            raise ValueError('Invalid selection report')
        result = {}
        for name in NAMES:
            entry = report['files'].get(name, {'status': 'missing'})
            fact = {'status': 'unavailable'}
            if isinstance(entry, dict):
                status = entry.get('status')
                if isinstance(status, str) and status in STATUSES:
                    fact = {'status': status}
                elif status == 'selected' and entry.get('location') in LOCATIONS:
                    data = runtime.get('_internal/' + name)
                    digest = hashlib.sha256(data).hexdigest() if isinstance(data, bytes) else None
                    if digest is not None and digest == entry.get('source_sha256'):
                        fact = {'status': 'matched', 'location': entry['location'], 'sha256': digest}
                    else:
                        fact = {'status': 'hash_mismatch'}
            result[name] = fact
        return {'status': 'UNQUALIFIED', 'files': result}
    except Exception:
        return {'status': 'unavailable'}
