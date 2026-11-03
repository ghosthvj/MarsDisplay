"""Measure native original/RECORD associations; source/legal inputs remain required."""
import argparse
import ast
import base64
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import subprocess
import sys
from types import SimpleNamespace


_spec = util.spec_from_file_location('linux_association', Path(__file__).with_name('attribution.py'))
attribution = util.module_from_spec(_spec)
_spec.loader.exec_module(attribution)


def toc_entries(path):
    try:
        tree = ast.literal_eval(path.read_text(encoding='utf-8'))
    except (SyntaxError, ValueError):
        raise ValueError('invalid COLLECT TOC') from None
    entries = {}

    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if len(value) == 3 and all(isinstance(item, str) for item in value):
            destination, original, kind = value
            if kind in {'BINARY', 'EXTENSION', 'DATA'}:
                attribution.material.safe_path(destination)
                if not Path(original).is_absolute():
                    raise ValueError('TOC original must be absolute')
                entries.setdefault(destination, set()).add(Path(original))
        else:
            for child in value:
                visit(child)
    visit(tree)
    if not entries:
        raise ValueError('COLLECT TOC contains no file entries')
    return entries


def wheel_index(originals, distributions=None):
    """Match installed RECORD paths before checking their recorded hash and size."""
    result = {path: [] for path in originals}
    for dist in metadata.distributions() if distributions is None else distributions:
        for entry in dist.files or ():
            path = Path(dist.locate_file(entry)).resolve()
            if path not in originals:
                continue
            attribution.material.safe_path(str(entry))
            data = originals[path]
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
            if (entry.hash is None or entry.hash.mode != 'sha256'
                    or entry.hash.value != expected or entry.size != len(data)):
                raise ValueError('invalid wheel RECORD: ' + path.name)
            name, version = dist.metadata.get('Name'), dist.metadata.get('Version')
            if not attribution.text(name) or not attribution.text(version):
                raise ValueError('missing wheel identity')
            result[path].append(dict(name=name, version=version, record=str(entry)))
    return result


QUALIFICATION = 'Measured original and RECORD associations only; source/legal acquisition required'


def sdk_context():
    def run(args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode and not (args[:2] == ['dpkg-query', '--search'] and result.returncode == 1):
            raise ValueError('SDK command failed: ' + args[0])
        return result.stdout
    return SimpleNamespace(root=Path('/'), prefix=Path(sys.base_prefix).resolve(),
                           python_version=platform.python_version(), run=run,
                           distributions=list(metadata.distributions()), lookup=metadata.distribution)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def acquire(payload, toc, project, output):
    output = output.absolute()
    attribution.no_links(output)
    if output.exists():
        raise ValueError('output must not exist')
    if not output.parent.is_dir():
        raise ValueError('output parent must exist')
    payload, project, toc = payload.resolve(), project.resolve(), toc.resolve()
    if not payload.is_dir() or not project.is_dir() or not toc.is_file():
        raise ValueError('missing payload, project or TOC')
    if (output.is_relative_to(payload) or payload.is_relative_to(output)
            or project.is_relative_to(output) or toc.is_relative_to(output)):
        raise ValueError('output overlaps input')
    entries = toc_entries(toc)
    measured, originals, aliases = {}, {}, {}
    seen = set()
    for path in sorted(payload.rglob('*')):
        name = path.relative_to(payload).as_posix()
        attribution.material.safe_path(name)
        if name.casefold() in seen:
            raise ValueError('duplicate payload path')
        seen.add(name.casefold())
        target = path.resolve()
        if not target.is_relative_to(payload):
            raise ValueError('payload alias escapes root')
        if path.is_symlink():
            if not target.is_file():
                raise ValueError('payload alias must target a regular file')
            aliases[name] = target.relative_to(payload).as_posix()
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('payload must contain regular files')
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        data = path.read_bytes()
        candidates = entries.get(name, entries.get(aliases.get(name), set()))
        matches = set()
        for candidate in candidates:
            if candidate.is_file() and candidate.read_bytes() == data:
                matches.add(candidate.resolve())
        if not matches:
            raise ValueError('missing or changed original: ' + name)
        if len(matches) != 1:
            raise ValueError('ambiguous original: ' + name)
        original = matches.pop()
        originals[original] = data
        measured[name] = (data, original)
    if not measured:
        raise ValueError('payload contains no ELF files')
    sdk = sdk_context()
    wheels = wheel_index(originals, sdk.distributions)
    if any(len(matches) > 1 for matches in wheels.values()):
        raise ValueError('ambiguous wheel RECORD ownership')

    records, files = [], []
    for index, (name, (data, original)) in enumerate(measured.items()):
        records.append(dict(file=name, original=f'originals/{index}', owners=[]))
        files.append(dict(file=name, sha256=hashlib.sha256(data).hexdigest(),
                          wheel_records=wheels[original],
                          unresolved='source/legal acquisition required'))
    diagnostics = dict(schema_version=1, qualification=QUALIFICATION,
                       files=files, aliases=aliases, separate_obligations=[
                           'Generated main application and PyInstaller bootloader: integrating build must qualify',
                           'Outer AppImage runtime: integrating build must qualify independently'])
    output.mkdir()
    build = output / 'evidence'
    (build / 'originals').mkdir(parents=True)
    view = output / 'payload'
    view.mkdir()
    for record, (data, _) in zip(records, measured.values()):
        (build / record['original']).write_bytes(data)
        destination = view / record['file']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (build / 'evidence.json').write_bytes(json_bytes(dict(schema_version=1, records=records)))
    (output / 'acquisition.json').write_bytes(json_bytes(diagnostics))
    return attribution.collect(view, build, output / 'association')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Measurement only; no qualified notices are produced. '
        'Exit 1: source/legal acquisition required; 2: invalid input. '
        'Publish only notices/, never intermediate ELF copies. '
        'See docs/linux-build-evidence.md.'))
    parser.add_argument('--payload', required=True, type=Path, help='shipped _internal directory')
    parser.add_argument('--toc', required=True, type=Path, help='literal PyInstaller COLLECT TOC')
    parser.add_argument('--project', required=True, type=Path, help='project root containing toolchain and reviewed material registries')
    parser.add_argument('--output', required=True, type=Path, help='new diagnostics directory; parent must exist')
    args = parser.parse_args(argv)
    try:
        return acquire(args.payload, args.toc, args.project, args.output)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print('build-evidence: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
