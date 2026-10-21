"""Separate experimental payload. Never relax the normal portable layout."""
import hashlib
from importlib import util
import json
from pathlib import Path
import re
import zipfile


def _load(name):
    spec = util.spec_from_file_location('grouping_' + name, Path(__file__).with_name(name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = _load('payload')
native = _load('native_material')
NAME = 'MarsDisplayGroupingExperiment'
FIXTURE = 'tools/windows-usb-probe/pattern.rgb888'
FIXTURE_HASH = '19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40'
EXTRA_SOURCE = frozenset({'.github/workflows/windows-usb-grouping.yml',
    'docs/usb-grouping-experiment.md', 'docs/usb-grouping-protocol.md'})
REQUIRED_SOURCE = EXTRA_SOURCE | payload._ROOT_SOURCE | frozenset({
    FIXTURE, 'src/mars_display/usb_grouping_experiment.py',
    'src/mars_display/usb_grouping_worker.py', 'src/mars_display/usb_grouping_profile.py',
    'packaging/grouping_entrypoint.py', 'packaging/grouping_bootstrap.py',
    'packaging/grouping_smoke.py', 'packaging/grouping_payload.py',
    'packaging/build_grouping_experiment.py', 'packaging/MarsDisplayGroupingExperiment.spec',
    'packaging/GROUPING-README.txt', 'tests/test_grouping_packaging.py', 'tests/test_grouping_smoke.py'})


def hashes(files):
    return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}


def collect_source(repo):
    files = payload.collect_source(repo)
    files.update(payload.read_tree(repo, EXTRA_SOURCE))
    payload._validate(files)
    if not REQUIRED_SOURCE <= files.keys():
        raise ValueError('Missing experiment corresponding source')
    return files


def destinations(output, version):
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*(?:[-a-zA-Z0-9.]*)', version):
        raise ValueError('Invalid artifact version')
    output = Path(output).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Symlink output directory')
    folder = output / NAME
    archive = output / f'{NAME}-{version}-Windows-x64.zip'
    checksum = archive.with_suffix('.zip.sha256')
    if any(p.exists() or p.is_symlink() for p in (folder, archive, checksum)):
        raise FileExistsError('Experimental output already exists')
    return folder, archive, checksum


def layout(runtime):
    payload._validate(runtime)
    _load('native_runtime').assert_profile(runtime)
    required = native.GROUPING_REQUIRED | {NAME + '.exe', '_internal/python313.dll',
                                           '_internal/grouping-pattern.rgb888', 'README.txt'}
    if not required <= runtime.keys():
        raise ValueError('Missing experimental executable, fixture or guard runtime')
    if any(name == 'MarsDisplay.exe' or name.startswith('_internal/playwright/') for name in runtime):
        raise ValueError('Unexpected normal application or browser runtime')
    fixture = runtime['_internal/grouping-pattern.rgb888']
    if len(fixture) != 460800 or hashlib.sha256(fixture).hexdigest() != FIXTURE_HASH:
        raise ValueError('Invalid fixed experiment fixture')


def _records(records, notices):
    if not isinstance(records, list) or not records:
        raise ValueError('Missing component inventory')
    for item in records:
        if (not isinstance(item, dict) or not item.get('version') or not item.get('sources')
                or not item.get('licenses') or any(name not in notices for name in item['licenses'])):
            raise ValueError('Missing exact component source/license material')
        for url in item['sources']:
            payload._source_reference(url)


def assemble(output, version, runtime, source, notices, inventory):
    """Validate before exclusive publication. Any failure leaves outputs unqualified."""
    folder, archive, checksum = destinations(output, version)
    for files in (runtime, source, notices):
        payload._validate(files)
    layout(runtime)
    if (not REQUIRED_SOURCE <= source.keys() or not notices
            or inventory.get('schema') != 'marsdisplay-grouping-v1'
            or inventory.get('profile') != native.GROUPING_PROFILE
            or inventory.get('target') != 'Windows-x64'
            or not re.fullmatch('[a-f0-9]{40}', inventory.get('source_commit', ''))
            or inventory.get('source_files') != hashes(source)
            or inventory.get('browsers') != []
            or inventory.get('packaged_smoke', {}).get('status') != 'passed'
            or any(not inventory.get('build', {}).get(key) for key in ('Python', 'PyInstaller', 'Qt'))):
        raise ValueError('Missing experimental source/hash/build/smoke inventory')
    if source[FIXTURE] != runtime['_internal/grouping-pattern.rgb888']:
        raise ValueError('Source fixture mismatch')
    for field in ('dependencies', 'build_dependencies', 'runtime_components', 'native_components'):
        _records(inventory.get(field), notices)
    dependencies = {item.get('name', '').lower().replace('-', '_') for item in inventory['dependencies']}
    if dependencies != {'pyside6_essentials', 'shiboken6', 'pyserial'}:
        raise ValueError('Unexpected experimental dependency closure')
    scope = {name for name in runtime if (name.startswith(('_internal/PySide6/', '_internal/shiboken6/'))
             and Path(name).suffix.lower() in {'.dll', '.pyd'})
             or re.fullmatch(r'_internal/(?:libssl|libcrypto)[^/]*\.dll', name, re.I)}
    records = inventory['native_components']
    if (len(records) != len(scope) or {item.get('path') for item in records} != scope
            or any(item.get('sha256') != hashlib.sha256(runtime[item['path']]).hexdigest() for item in records)):
        raise ValueError('Native inventory does not bind actual runtime')
    files = dict(runtime)
    additions = {'LICENSE': source['LICENSE'], **{'source/' + k: v for k, v in source.items()},
                 **{'notices/' + k: v for k, v in notices.items()}}
    if set(files) & (set(additions) | {'inventory.json'}):
        raise ValueError('Reserved experimental payload path')
    files.update(additions)
    payload._validate(files)
    files['inventory.json'] = (json.dumps(dict(inventory, files=hashes(files)), indent=2, sort_keys=True) + '\n').encode()
    # Exclusive creation at every boundary, including races. A failed publisher
    # never uploads; a partial experimental destination must be investigated,
    # not overwritten. Normal destinations are never opened.
    folder.parent.mkdir(parents=True, exist_ok=True)
    folder.mkdir()
    for name, data in sorted(files.items()):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(files.items()):
            zipped.writestr(NAME + '/' + name, data)
    with checksum.open('x', encoding='ascii') as stream:
        stream.write(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    return folder, archive, checksum
