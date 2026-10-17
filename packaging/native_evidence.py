"""Unqualified byte/RECORD facts only. No binary loading, execution or vendor inference."""
import base64
import hashlib
from importlib import import_module, metadata, util
from pathlib import Path
import re

from packaging.utils import canonicalize_name

_spec = util.spec_from_file_location('marsdisplay_evidence_payload', Path(__file__).with_name('payload.py'))
_payload = util.module_from_spec(_spec)
_spec.loader.exec_module(_payload)


def _pe_versions(data, parser):
    if parser is None or getattr(parser, '__version__', None) != '2024.8.26':
        return {'status': 'unavailable'}
    pe, result = None, {'status': 'unknown'}
    try:
        pe = parser.PE(data=data, fast_load=True)
        pe.parse_data_directories(directories=[parser.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        fixed = getattr(pe, 'VS_FIXEDFILEINFO', None)
        if fixed is None or fixed == []:
            result = {'status': 'absent'}
        elif isinstance(fixed, (list, tuple)) and len(fixed) == 1:
            info = fixed[0]
            words = [getattr(info, field) for field in
                     ('FileVersionMS', 'FileVersionLS', 'ProductVersionMS', 'ProductVersionLS')]
            if info.Signature == 0xFEEF04BD and all(type(word) is int and 0 <= word <= 0xffffffff for word in words):
                def dotted(ms, ls):
                    return f'{ms >> 16}.{ms & 65535}.{ls >> 16}.{ls & 65535}'
                result = {'status': 'measured', 'file_version': dotted(*words[:2]),
                          'product_version': dotted(*words[2:])}
    except Exception:
        pass  # Fixed unknown status, never a raw parser exception or resource string.
    finally:
        if pe is not None:
            try:
                pe.close()
            except Exception:
                result = {'status': 'unknown'}
    return result


def _identity(name, version):
    return (isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name)
            and isinstance(version, str) and re.fullmatch(r'[0-9][A-Za-z0-9.!+_-]{0,127}', version))


def _record_index(inventory, digests, lookup):
    declared = set()
    for item in inventory.get('dependencies', []) + inventory.get('build_dependencies', []):
        name, version = item.get('name'), item.get('version')
        if _identity(name, version):
            declared.add((canonicalize_name(name), version))
    matches, unavailable = {}, False
    for requested, version in sorted(declared):
        try:
            dist = lookup(requested)
            name, actual_version, files = dist.metadata['Name'], dist.version, dist.files
            if (not _identity(name, actual_version) or canonicalize_name(name) != requested
                    or actual_version != version or files is None):
                unavailable = True
                continue
            for entry in files:
                path, recorded = str(entry), getattr(entry, 'hash', None)
                try:
                    if len(path) > 512:
                        continue
                    _payload.safe_path(path)
                    if (recorded is None or recorded.mode != 'sha256'
                            or not isinstance(recorded.value, str)
                            or not re.fullmatch(r'[A-Za-z0-9_-]{43}=?', recorded.value)):
                        continue
                    digest = base64.b64decode(recorded.value + '=' * (-len(recorded.value) % 4),
                                              altchars=b'-_', validate=True)
                    if len(digest) != 32 or digest.hex() not in digests:
                        continue
                    if base64.urlsafe_b64encode(digest).decode().rstrip('=') != recorded.value.rstrip('='):
                        continue
                except (ValueError, TypeError):
                    continue
                # No locate_file/stat/open/resolve: RECORD paths are metadata,
                # so neither SDK binaries nor symlink targets can be traversed.
                matches.setdefault(digest.hex(), set()).add((name, version, path))
        except Exception:
            unavailable = True
    return matches, 'unavailable' if unavailable else 'available'


def collect(runtime, inventory, *, parser=None, lookup=None):
    """Return per-native-path hash-bound facts; provider seams are test-only.

    Origins are installed RECORD associations, not vendor/license/source proof.
    pefile is lazy and fixed to the inspected 2024.8.26 public resource API.
    """
    hashes = {}
    for name, data in runtime.items():
        _payload.safe_path(name)
        if Path(name).suffix.lower() in {'.dll', '.pyd', '.exe'}:
            hashes[name] = hashlib.sha256(data).hexdigest()
    if parser is None:
        try:
            parser = import_module('pefile')
        except Exception:
            parser = None
    index, record_status = _record_index(inventory, set(hashes.values()), metadata.distribution if lookup is None else lookup)
    result = {}
    for name, digest in sorted(hashes.items()):
        owners = [{'name': owner, 'version': version, 'record_path': path, 'sha256': digest}
                  for owner, version, path in sorted(index.get(digest, ()))]
        result[name] = {'sha256': digest, 'pe': _pe_versions(runtime[name], parser),
                        'origins': {'status': 'matched' if owners else 'unknown',
                                    'record_status': record_status, 'matches': owners}}
    return result
