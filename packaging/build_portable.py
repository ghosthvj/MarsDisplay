"""Native Windows x64 recipe. Import/help never inspect SDKs or create output."""
import argparse
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile
import tomllib


def _load(name):
    spec = util.spec_from_file_location('marsdisplay_' + name, Path(__file__).with_name(name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = _load('payload')
smoke = _load('smoke')
native_runtime = _load('native_runtime')
native_material = _load('native_material')
release_version = _load('release_version')


def require_host():
    if sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'} or struct.calcsize('P') != 8:
        raise RuntimeError('Portable builds require native Windows x64; no cross-compilation is supported.')


def python_license(sdk):
    return {'runtime/Python/' + name: data for name, data in payload.read_tree(sdk, ('LICENSE.txt',)).items()}


def inspect_environment(repo, *, profile='portable'):
    """Inspect pinned SDK; the explicit experiment excludes unbundled browsers."""
    native_material.validate_profile(profile)
    native_material.read_inputs(repo)  # Genuine material/policy BEFORE any SDK or process work.
    from packaging.requirements import Requirement
    if profile == 'portable':
        import playwright
    from PySide6.QtCore import qVersion
    notices = _load('notices')
    config = tomllib.loads((repo / 'pyproject.toml').read_text(encoding='utf-8'))
    project = config['project']
    if sys.version_info[:2] != (3, 13):
        raise ValueError('Use the selected Python 3.13.x SDK')
    roots = []
    for raw in project['dependencies'] + project['optional-dependencies']['build'] + config['build-system']['requires']:
        requirement = Requirement(raw)
        if not re.fullmatch(r'==[^*,]+', str(requirement.specifier)) or metadata.version(requirement.name) not in requirement.specifier:
            raise ValueError('Installed SDK does not match exact pyproject pins')
        roots.append(requirement.name)
    runtime_roots = (roots[:len(project['dependencies'])] if profile == 'portable'
                     else ['PySide6_Essentials', 'pyserial'])
    dependencies, material = notices.collect_distributions(runtime_roots)
    tools, tool_material = notices.collect_distributions(['PyInstaller'])
    material.update(tool_material)  # Includes COPYING.txt and the bootloader exception.
    material.update(python_license(Path(sys.base_prefix)))
    browsers = []
    if profile == 'portable':
        driver = Path(playwright.__file__).parent / 'driver'
        browsers, vendor = notices.collect_vendor(driver)
        material.update(vendor)
    native_material.preflight(repo, {'build': {'Qt': qVersion()}, 'dependencies': dependencies,
                                     'build_dependencies': tools})
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Missing exact source revision')
    inventory = {'version': project['version'], 'source_commit': revision, 'target': 'Windows-x64',
            'build': {'Python': platform.python_version(), 'PyInstaller': metadata.version('PyInstaller'), 'Qt': qVersion()},
            'build_dependencies': tools, 'dependencies': dependencies, 'browsers': browsers,
            'runtime_components': [{'name': 'CPython', 'version': platform.python_version(),
                                    'sources': ['https://github.com/python/cpython/tree/v' + platform.python_version()],
                                    'licenses': ['runtime/Python/LICENSE.txt']}]}
    release = release_version.inspect(repo, revision, lambda: metadata.version('mars-display'))
    if release is not None:
        inventory['release'] = release
    return inventory, material


def collect_native(runtime, inventory, material_root):
    """Fail closed without a reviewed, exact native Qt file/material mapping.

    The operator supplies real Windows material in build/native-material. This
    check binds that evidence to bytes; it does not certify completeness/legal
    sufficiency. Binding license metadata is deliberately NOT a substitute.
    """
    try:
        raw = payload.read_tree(material_root, ('native.json',))['native.json']
    except (OSError, ValueError):
        raise ValueError('Missing reviewed native notices: build/native-material/native.json; Windows qualification is pending') from None
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or manifest.get('schema') != 'marsdisplay-native-material-v2'
            or set(manifest) != {'schema', 'qt_release', 'qualification', 'components', 'material_sha256'}):
        raise ValueError('Unsupported native material schema; expected marsdisplay-native-material-v2')
    if not isinstance(manifest['qualification'], str) or not manifest['qualification'].strip():
        raise ValueError('Incomplete native qualification')
    if manifest['qt_release'] != inventory['build']['Qt']:
        raise ValueError('Native Qt release does not match build inventory')
    required = {name for name in runtime if name.startswith('_internal/PySide6/') and Path(name).suffix.lower() in {'.dll', '.pyd'}}
    components = manifest['components']
    if (not isinstance(components, list) or not required or len(components) != len(required)
            or any(not isinstance(item, dict) or not isinstance(item.get('path'), str) for item in components)
            or {item['path'] for item in components} != required):
        raise ValueError('Unmapped native Qt payload; binding texts are not native coverage')
    materials = manifest['material_sha256']
    if (not isinstance(materials, dict) or not materials
            or any(not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest) for digest in materials.values())):
        raise ValueError('Native material SHA256 mismatch')
    texts = payload.read_tree(material_root, materials)
    for name, digest in materials.items():
        if hashlib.sha256(texts[name]).hexdigest() != digest:
            raise ValueError('Native material SHA256 mismatch')
    for item in components:
        if (set(item) != {'path', 'sha256', 'component', 'version', 'sources', 'licenses', 'version_evidence', 'binary_evidence'}
                or not isinstance(item['component'], str) or not item['component'].strip()
                or not isinstance(item['version'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_!~-]{0,127}', item['version'])
                or hashlib.sha256(runtime[item['path']]).hexdigest() != item['sha256']
                or not isinstance(item['binary_evidence'], dict)
                or not isinstance(item['sources'], list) or not item['sources']
                or any(not isinstance(url, str) for url in item['sources'])):
            raise ValueError('Incomplete or mismatched native component provenance')
        for field in ('licenses', 'version_evidence'):
            references = item[field]
            if (not isinstance(references, list) or not references
                    or any(not isinstance(name, str) or name not in texts for name in references)):
                raise ValueError('Incomplete or mismatched native component provenance')
        if set(item['licenses']) & set(item['version_evidence']):
            raise ValueError('Incomplete or mismatched native component provenance')
        for url in item['sources']:
            payload._source_reference(url)
    # Admission above binds reviewed source claims to raw material, not PE/owner
    # version inference. Verification below always measures current runtime bytes.
    try:
        fresh = _load('native_evidence').collect({name: runtime[name] for name in sorted(required)}, inventory)
        valid = isinstance(fresh, dict) and set(fresh) == required
        for item in components:
            fact = fresh.get(item['path'], {})
            valid = (valid and fact.get('sha256') == item['sha256']
                     and fact.get('pe', {}).get('status') in {'measured', 'absent'}
                     and fact.get('origins', {}).get('record_status') == 'available'
                     and fact.get('origins', {}).get('status') in {'matched', 'unknown'}
                     and item['binary_evidence'] == fact)
    except Exception:
        valid = False
    if not valid:
        raise ValueError('Native binary evidence does not match verifiable current facts')
    return components, {'native/native.json': raw, **{'native/' + name: data for name, data in texts.items()}}


def retain_diagnostic(work, inventory, runtime, phase, smoke_status):
    """Retain metadata only, never approval evidence or raw failure messages."""
    def version(value):
        return isinstance(value, str) and re.fullmatch(r'v?[0-9][A-Za-z0-9.!+_-]*', value)

    def component(item, keys):
        # Installed metadata may contain URLs/private license statements. Export
        # only package/registry names and version tokens, never whole records.
        result = {}
        for key in keys:
            value = item.get(key)
            if key == 'name':
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', value):
                    result[key] = value
            elif version(value):
                result[key] = value
        return result

    report = {
        'schema': 'marsdisplay-unqualified-native-v1', 'status': 'UNQUALIFIED',
        'failure_phase': phase, 'packaged_smoke': {'status': smoke_status},
        'source_commit': inventory['source_commit'], 'source_files': inventory['source_files'],
        'versions': {
            'build': {key: value for key, value in inventory['build'].items()
                      if key in {'Python', 'PyInstaller', 'Qt', 'Node'} and version(value)},
            'dependencies': [component(item, ('name', 'version')) for item in inventory['dependencies']],
            'build_dependencies': [component(item, ('name', 'version')) for item in inventory.get('build_dependencies', [])],
            'browsers': [component(item, ('name', 'revision', 'browser_version')) for item in inventory['browsers']],
        },
        'native_files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(runtime.items())
                         if Path(name).suffix.lower() in {'.dll', '.pyd', '.exe'}},
    }
    try:
        report['native_evidence'] = _load('native_evidence').collect(
            {name: runtime[name] for name in report['native_files']}, inventory)
    except Exception:
        # Supplemental diagnostics must never replace the original native error.
        report['native_evidence'] = {name: {'sha256': digest, 'status': 'unavailable'}
                                     for name, digest in report['native_files'].items()}
    data = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode('utf-8')
    # mkstemp-backed exclusive creation; never overwrite a prior diagnostic.
    with tempfile.NamedTemporaryFile(prefix='unqualified-native-', suffix='.json', dir=work, delete=False) as stream:
        stream.write(data)
        name = Path(stream.name).name
    print('Unqualified diagnostic: build/' + name, file=sys.stderr)


def build(repo, *, run=None, qualify=None, smoke_check=None):
    """Compile, smoke, qualify, then publish; retain only metadata on failure."""
    require_host()  # Before SDK imports, source reads, directories or processes.
    run = subprocess.run if run is None else run
    automatic_native = qualify is None
    qualify = collect_native if automatic_native else qualify
    smoke_check = smoke.check if smoke_check is None else smoke_check
    repo = Path(repo).absolute()
    if any(path.is_symlink() for path in (repo, *repo.parents)):
        raise ValueError('Symlink repository')
    inventory, material = inspect_environment(repo)
    version = inventory.pop('version')
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*(?:[-a-zA-Z0-9.]*)', version):
        raise ValueError('Invalid artifact version')
    output = repo / 'dist'
    destinations = (output / 'MarsDisplay', output / f'MarsDisplay-{version}-Windows-x64.zip',
                    output / f'MarsDisplay-{version}-Windows-x64.zip.sha256')
    if output.is_symlink() or any(path.exists() or path.is_symlink() for path in destinations):
        raise FileExistsError('Portable output already exists')
    source = payload.collect_source(repo)
    inventory['source_files'] = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(source.items())}
    work = repo / 'build'
    if work.is_symlink():
        raise ValueError('Symlink build directory')
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='portable-', dir=work) as temporary:
        stage = Path(temporary)
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(('QT_', 'QML', 'PYTHON', 'PLAYWRIGHT_'))}
        env['PLAYWRIGHT_BROWSERS_PATH'] = '0'
        temporary_output = stage / 'temp'
        temporary_output.mkdir()
        env.update({name: str(temporary_output) for name in ('TEMP', 'TMP', 'TMPDIR')})
        env['PYINSTALLER_CONFIG_DIR'] = str(stage / 'pyinstaller-cache')
        run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(stage / 'dist'),
             '--workpath', str(stage / 'work'), str(repo / 'packaging/MarsDisplay.spec')],
            cwd=repo, env=env, check=True, timeout=900)
        folder = stage / 'dist/MarsDisplay'
        instructions = source.get('packaging/PORTABLE-README.txt')
        if not instructions:
            raise ValueError('Missing portable prerequisite instructions')
        with (folder / 'README.txt').open('xb') as stream:
            stream.write(instructions)
        runtime = payload.read_tree(folder)
        phase, smoke_status = 'runtime_profile', 'not_run'
        try:
            native_runtime.assert_profile(runtime)
            phase = 'layout_validation'
            payload._layout(runtime)
            phase, smoke_status = 'packaged_smoke', 'failed_or_unavailable'
            measurements = smoke_check(folder, stage / 'smoke')
            inventory['build']['Node'] = measurements['Node']
            inventory['packaged_smoke'] = measurements
            smoke_status = 'passed'
            phase = 'native_qualification'
            material_root = (native_material.prepare(repo, runtime, inventory, stage / 'native-material')
                             if automatic_native else work / 'native-material')
            native, native_texts = qualify(runtime, inventory, material_root)
            inventory['native_components'] = native
            material.update(native_texts)
            phase = 'source_stability'
            if payload.collect_source(repo) != source:
                raise ValueError('Source changed during build; nothing published')
        except Exception:
            retain_diagnostic(work, inventory, runtime, phase, smoke_status)
            raise
        return payload.assemble(output, version, runtime, source, material, inventory)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build a windowed portable ZIP on native Windows x64 (Python 3.13.x). No downloads; requires pinned SDK and package-local Chromium.',
        epilog='External prerequisite: official VC++ v14 x64 14.51+; Microsoft DLLs are not bundled. Requires verified third_party/native-material sources/policy and exact SDK RECORD preflight; stages marsdisplay-native-material-v2 with fresh binary evidence. Missing qualification fails closed. Existing outputs are never replaced.')
    parser.parse_args(argv)
    try:
        _, archive, checksum = build(Path(__file__).absolute().parents[1])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Portable build failed: ' + str(error), file=sys.stderr)
        return 1
    print(archive.name + '\n' + checksum.name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
