"""Measure native byte associations; supplied owner claims are not legal approval."""
import argparse
import hashlib
from importlib import util
import json
from pathlib import Path
import stat
import sys

_spec = util.spec_from_file_location('linux_notices', Path(__file__).parents[1] / 'notices.py')
notices = util.module_from_spec(_spec)
_spec.loader.exec_module(notices)
# Reuse the existing notice collector's safe material/source policies unchanged.
material = notices._payload
QUALIFICATION = 'Measured byte association; supplied ownership claims, not legal approval'
REQUIRED = 'acquire owner name/version, source name/version/reference, legal and ownership inputs'


def text(value):
    return isinstance(value, str) and bool(value.strip()) and all(ord(c) >= 32 for c in value)


def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink material or parent')


def selected(root, name):
    if not isinstance(name, str):
        raise ValueError('invalid material path')
    material.safe_path(name)
    path = root / name
    no_links(path)
    if not path.exists():
        raise ValueError('Missing selected material')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('material must be a regular file')
    return path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def mappings(build):
    data = json.loads(selected(build, 'evidence.json').read_text(encoding='utf-8'),
                      object_pairs_hook=unique_object)
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'records'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['records'], list)):
        raise ValueError('unsupported evidence schema')
    records = {}
    for record in data['records']:
        if not isinstance(record, dict) or set(record) != {'file', 'original', 'owners'}:
            raise ValueError('invalid mapping record')
        for key in ('file', 'original'):
            if not isinstance(record[key], str):
                raise ValueError('invalid material path')
            material.safe_path(record[key])
        if record['file'].casefold() in {name.casefold() for name in records}:
            raise ValueError('duplicate payload mapping')
        if not isinstance(record['owners'], list):
            raise ValueError('owners must be a list')
        # Reject unsafe selections even if another missing field would be unresolved.
        for owner in record['owners']:
            if not isinstance(owner, dict):
                raise ValueError('invalid owner record')
            for key in ('licenses', 'evidence'):
                paths = owner.get(key)
                if isinstance(paths, list):
                    for name in paths:
                        if not isinstance(name, str):
                            raise ValueError('invalid material path')
                        material.safe_path(name)
                        no_links(build / name)
        no_links(build / record['original'])
        records[record['file']] = record
    return records


def associate(build, record, sha256):
    if record is None:
        raise ValueError('acquire exact original-file mapping')
    if digest(selected(build, record['original'])) != sha256:
        raise ValueError('original SHA256 differs from payload')
    if len(record['owners']) != 1:
        raise ValueError('acquire exactly one owner')
    owner = record['owners'][0]
    if owner.get('kind') not in ('wheel', 'package', 'vendor', 'cpython'):
        raise ValueError('unsupported owner kind')
    source = owner.get('source')
    if (set(owner) != {'kind', 'name', 'version', 'source', 'licenses', 'evidence'}
            or not all(text(owner.get(k)) for k in ('name', 'version'))
            or not isinstance(source, dict) or set(source) != {'name', 'version', 'reference'}
            or not all(text(source[k]) for k in source)
            or any(not isinstance(owner.get(k), list) or not owner[k]
                   for k in ('licenses', 'evidence'))):
        raise ValueError(REQUIRED)
    material._source_reference(source['reference'])
    paths = owner['licenses'] + owner['evidence']
    if len(set(paths)) != len(paths):
        raise ValueError('duplicate owner material')
    for name in paths:
        selected(build, name)
    inputs = material.read_tree(build, paths)
    return {'file': record['file'], 'original': record['original'], 'owner': owner,
            'sha256': sha256,
            'materials': {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}}


def collect(payload, build, output):
    roots = [p.absolute() for p in (payload, build, output)]
    for path in roots:
        no_links(path)
    payload, build, output = (p.resolve() for p in roots)
    if output.exists():
        raise ValueError('output must not exist')
    for root in (payload, build):
        if output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError('output overlaps input')
        if not root.is_dir():
            raise ValueError('input root must be a directory')
    if not output.parent.is_dir():
        raise ValueError('output parent must exist')
    records = mappings(build)
    measured = {}
    seen = set()
    for path in sorted(payload.rglob('*')):
        name = path.relative_to(payload).as_posix()
        material.safe_path(name)
        no_links(path)
        if name.casefold() in seen:
            raise ValueError('duplicate payload path')
        seen.add(name.casefold())
        if path.is_dir():
            continue
        selected(payload, name)
        with path.open('rb') as stream:
            if stream.read(4) == b'\x7fELF':
                measured[name] = digest(path)
    if not measured:
        raise ValueError('payload contains no ELF files')
    if set(records) - measured.keys():
        raise ValueError('mapping does not name a measured ELF')
    files, unresolved = [], []
    for name, sha256 in measured.items():
        try:
            files.append(associate(build, records.get(name), sha256))
        except ValueError as error:
            unresolved.append({'file': name, 'reason': str(error)})
    inventory = {'schema_version': 1, 'qualification': QUALIFICATION,
                 'evidence_sha256': digest(build / 'evidence.json'),
                 'measured': measured, 'files': files, 'unresolved': unresolved}
    output.mkdir()
    with (output / 'inventory.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
    print(f'measured={len(measured)} associated={len(files)} unresolved={len(unresolved)}')
    return int(bool(unresolved))


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Exit 0: measured coverage with supplied records, NOT legal approval; '
        '1: unresolved (inventory retained); 2: invalid input. No network or discovery. '
        'See docs/linux-attribution.md for evidence.json schema.'))
    parser.add_argument('--payload', required=True, type=Path, help='ELF payload root; no symlinks')
    parser.add_argument('--build', required=True, type=Path, help='evidence.json and original/legal input root')
    parser.add_argument('--output', required=True, type=Path, help='new diagnostic directory; parent must exist')
    args = parser.parse_args()
    try:
        return collect(args.payload, args.build, args.output)
    except (ValueError, OSError) as error:
        print(f'attribution: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
