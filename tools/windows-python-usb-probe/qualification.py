"""Probe byte facts and a separate, narrow source/terms qualification profile.

The full application's Qt policy must not be adapted by inventing empty Qt
inventory. sdk_origin_facts always remains UNQUALIFIED: SDK residence, RECORD
matches and PE versions alone cannot establish source or license coverage.
qualify composes those facts with actual build inputs and component terms.
"""
import hashlib
import re
from importlib import util
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def _helper(name):
    spec = util.spec_from_file_location(
        'python_usb_probe_' + name, _ROOT / 'packaging' / (name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_payload = _helper('payload')
_native_runtime = _helper('native_runtime')
_spec = util.spec_from_file_location('probe_cpython_material', Path(__file__).with_name('cpython_material.py'))
cpython_material = util.module_from_spec(_spec)
_spec.loader.exec_module(cpython_material)


def _cpython_inputs(repo):
    return cpython_material.read_inputs(repo)


def assert_lean_runtime(runtime):
    """Reject unsafe paths and known forbidden payload families without writes.

    This is a necessary gate, not a complete Analysis import-closure audit:
    Python modules inside PYZ still need inspection by the native builder.
    """
    _payload._validate(runtime)
    _native_runtime.assert_profile(runtime)
    for name in runtime:
        parts = name.casefold().split('/')
        if (any(part in {'pyside6', 'shiboken6', 'pil', 'pillow', 'playwright',
                         'chromium', 'chrome', 'node_modules'} for part in parts)
                or parts[-1] in {'node.exe', 'chrome.exe', 'headless_shell.exe'}
                or parts[-1].startswith(('qt5', 'qt6'))):
            raise ValueError('Forbidden diagnostic dependency')
    if 'PythonUsbProbe.exe' not in runtime:
        raise ValueError('Missing diagnostic executable')
    if any(Path(name).suffix.casefold() == '.exe' and name != 'PythonUsbProbe.exe'
           for name in runtime):
        raise ValueError('Unexpected native executable')


def sdk_origin_facts(runtime, origins, sdk):
    """Bind delivered DLL/PYD bytes to exact core SDK Analysis origins.

    ``origins`` maps delivered relative paths to the actual source paths retained
    by Analysis. The builder must supply those paths, not find an arbitrary
    equal-hash file after the build. Only direct SDK-root and DLLs children are
    admitted, never site-packages, System32 or a sibling SDK. Paths and input
    dictionaries are not modified. Only relative SDK names leave this function.

    This function intentionally has no qualified/publication return state.
    The project-built EXE requires a separate pinned bootloader/build binding;
    embedded SDK components require their own actual versions, sources and terms.
    """
    assert_lean_runtime(runtime)
    native = {name for name in runtime if Path(name).suffix.casefold() in {'.dll', '.pyd'}}
    if set(origins) != native:
        raise ValueError('Native Analysis origins do not match payload')
    sdk = Path(sdk).absolute()
    if any(path.is_symlink() for path in (sdk, *sdk.parents)):
        raise ValueError('Symlink native origin')
    facts = {}
    for name in sorted(native):
        origin = Path(origins[name]).absolute()
        if any(path.is_symlink() for path in (origin, *origin.parents)):
            raise ValueError('Symlink native origin')
        try:
            relative = origin.relative_to(sdk)
        except ValueError:
            raise ValueError('Native origin is outside approved SDK locations') from None
        if relative.parent not in (Path('.'), Path('DLLs')):
            raise ValueError('Native origin is outside approved SDK locations')
        if Path(name).name != origin.name:
            raise ValueError('Native destination differs from SDK basename')
        selected = _payload.read_tree(sdk, (relative.as_posix(),))
        if selected[relative.as_posix()] != runtime[name]:
            raise ValueError('SDK bytes differ from delivered native file')
        facts[name] = {
            'sdk_path': relative.as_posix(),
            'sha256': hashlib.sha256(runtime[name]).hexdigest(),
            'qualification': 'Component source and license coverage required',
        }
    return {
        'status': 'UNQUALIFIED',
        'project_executable': {
            'path': 'PythonUsbProbe.exe',
            'sha256': hashlib.sha256(runtime['PythonUsbProbe.exe']).hexdigest(),
            'qualification': 'PyInstaller build and bootloader evidence required',
        },
        'sdk_files': facts,
    }


def audit_modules(analysis_modules, pyz_modules):
    required = {'mars_display.usb_probe', 'mars_display.usb_probe_process',
                'mars_display.usb_protocol', 'serial'}
    allowed_project = {'mars_display', 'mars_display.frames', 'mars_display.transport',
                       'mars_display.devices', *(required - {'serial'})}
    for modules in (analysis_modules, pyz_modules):
        if not required <= set(modules):
            raise ValueError('Incomplete diagnostic import graph/PYZ')
        for name in modules:
            if (name.split('.')[0].casefold() in {'pil', 'pillow', 'pyside6', 'shiboken6',
                                                'pyqt5', 'pyqt6', 'playwright', 'tkinter'}
                    or (name.startswith('mars_display.') and name not in allowed_project)):
                raise ValueError('Forbidden diagnostic import: ' + name)


def measure_native(runtime, inventory):
    import pefile
    if pefile.__version__ != '2024.8.26':
        raise ValueError('Unexpected PE parser version')
    facts = _helper('native_evidence').collect(runtime, inventory, parser=pefile)
    for name, fact in facts.items():
        pe = pefile.PE(data=runtime[name], fast_load=True)
        try:
            if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
                raise ValueError('Native file is not Windows x64 PE: ' + name)
            fact['machine'] = 'AMD64/PE32+'
        finally:
            pe.close()
        if fact['pe']['status'] not in {'measured', 'absent'}:
            raise ValueError('Unverifiable native PE version: ' + name)
    return facts


_CORE_EXTENSIONS = {
    '_asyncio', '_socket', '_overlapped', 'select', '_queue', '_multiprocessing',
    'unicodedata', '_uuid', '_wmi', '_zoneinfo', '_ctypes', '_hashlib', '_ssl',
    '_decimal', '_elementtree', 'pyexpat', '_bz2', '_lzma', '_msi', 'winsound', 'zlib',
}


def qualify(runtime, origins, sdk, inventory, material, analysis, repo, *, measure=measure_native):
    """Compose actual native facts with a deliberately narrow component policy.

    Missing/unrecognized versions or terms reject publication, retaining facts in
    the caller's metadata-only failure report. No Qt inventory is synthesized.
    """
    origin_facts = sdk_origin_facts(runtime, origins, sdk)
    license_path = 'runtime/Python/LICENSE.txt'
    if not material.get(license_path):
        raise ValueError('Missing Python Windows SDK license')
    build = inventory.get('build', {})
    boot = inventory.get('bootloader', {})
    if (build.get('PyInstaller') != '6.22.3' or build.get('pyserial') != '3.5'
            or not re.fullmatch(r'3\.13\.\d+', build.get('Python', ''))
            or not build.get('sys_version') or not build.get('compiler')
            or not re.fullmatch('[a-f0-9]{64}', boot.get('sha256', ''))
            or boot.get('record_sha256') != boot.get('sha256')
            or not re.fullmatch('[a-f0-9]{64}', boot.get('distribution_metadata_sha256', ''))
            or boot.get('source') != 'https://github.com/pyinstaller/pyinstaller/tree/v6.22.3/bootloader'
            or analysis.get('bootloader_sha256') != boot['sha256']
            or analysis.get('exe_sha256') != hashlib.sha256(runtime['PythonUsbProbe.exe']).hexdigest()):
        raise ValueError('Missing pinned build evidence')
    audit_modules(analysis.get('modules', []), analysis.get('pyz_modules', []))
    if not inventory.get('dependencies') or not inventory.get('build_dependencies'):
        raise ValueError('Missing installed distribution terms')
    for item in inventory['dependencies'] + inventory['build_dependencies']:
        if not item.get('sources') or not item.get('licenses'):
            raise ValueError('Missing installed distribution terms')
        for reference in item['licenses']:
            if not material.get(reference):
                raise ValueError('Missing installed distribution terms')
        for url in item['sources']:
            _payload._source_reference(url)
    if not any(item['name'].casefold() == 'pyserial' and item['version'] == '3.5'
               for item in inventory['dependencies']):
        raise ValueError('Missing pinned pyserial terms')
    installer = [item for item in inventory['build_dependencies']
                 if item['name'].casefold() == 'pyinstaller' and item['version'] == '6.22.3']
    if len(installer) != 1:
        raise ValueError('Missing PyInstaller terms')
    boot_terms = b'\n'.join(material[name] for name in installer[0]['licenses']).lower()
    if b'bootloader' not in boot_terms or b'exception' not in boot_terms:
        raise ValueError('Missing PyInstaller bootloader exception')
    cpython = _cpython_inputs(repo)
    cpython_material.validate_sdk(cpython, build, material[license_path])
    facts = measure(runtime, inventory)
    native = {name for name in runtime if Path(name).suffix.lower() in {'.exe', '.dll', '.pyd'}}
    if set(facts) != native or any(facts[name].get('sha256') != hashlib.sha256(runtime[name]).hexdigest()
                                  or facts[name].get('machine') != 'AMD64/PE32+'
                                  or facts[name].get('pe', {}).get('status') not in {'measured', 'absent'}
                                  for name in native):
        raise ValueError('Native PE/hash evidence mismatch')
    if '_internal/python313.dll' not in native:
        raise ValueError('Missing actual CPython 3.13 runtime DLL')
    components = []
    pending_material = {'cpython-inputs/' + name: raw for name, raw in cpython['files'].items()}
    bundle = None
    for name in sorted(native):
        base = Path(name).name.lower()
        record = {'path': name, 'sha256': facts[name]['sha256'], 'binary_evidence': facts[name]}
        if name == 'PythonUsbProbe.exe':
            record.update(component='project/PyInstaller bootloader', version='1.0.0/6.22.3',
                          sources=[boot['source']], licenses=installer[0]['licenses'],
                          bootloader=boot)
        elif base.startswith(('libcrypto-', 'libssl-')):
            official = cpython_material.associate(cpython, name, facts[name],
                origin_facts['sdk_files'][name], inventory.get('sdk_components', {}))
            record['official_distribution'] = official['official_distribution']
            bundle = bundle or _helper('native_material').read_inputs(repo)
            matches = [item for item in bundle['policy']['supplemental']
                       if item['module'].startswith('openssl-') and item['path'] == name
                       and item['sha256'] == facts[name]['sha256'] and item['pe'] == facts[name]['pe']]
            if len(matches) != 1:
                raise ValueError('Unmapped actual OpenSSL bytes/version: ' + name)
            version = matches[0]['module'].removeprefix('openssl-')
            upstream = bundle['registry']['openssl'][version]
            references = []
            for item in bundle['registry']['files']:
                if item['module'] == matches[0]['module'] and item['kind'] in {'license', 'license-notice'}:
                    reference = 'native-inputs/' + item['path']
                    pending_material[reference] = bundle['files'][item['path']]
                    references.append(reference)
            if not references:
                raise ValueError('Missing verified OpenSSL terms')
            record.update(component='OpenSSL', version=version,
                          sources=[upstream['source_archive']], licenses=references)
        else:
            record.update(cpython_material.associate(cpython, name, facts[name],
                origin_facts['sdk_files'][name], inventory.get('sdk_components', {})))
        components.append(record)
    qualified_names = {Path(item['path']).name.lower(): item['component'] for item in components}
    if '_ctypes.pyd' in qualified_names and 'libffi' not in qualified_names.values():
        raise ValueError('Missing qualified libffi dependency for _ctypes')
    if any(name in qualified_names for name in ('_hashlib.pyd', '_ssl.pyd')):
        if not any(name.startswith('libcrypto-') and component == 'OpenSSL'
                   for name, component in qualified_names.items()):
            raise ValueError('Missing qualified OpenSSL crypto dependency')
    if '_ssl.pyd' in qualified_names and not any(name.startswith('libssl-') and component == 'OpenSSL'
                                                for name, component in qualified_names.items()):
        raise ValueError('Missing qualified OpenSSL SSL dependency')
    material.update(pending_material)  # Commit additions only after all components qualify.
    return {'status': 'QUALIFIED', 'profile': 'python-usb-probe-1', 'components': components,
            'native_evidence': facts, 'origin_facts': origin_facts,
            'qualification': 'Mechanical source/terms binding; no physical rendering acceptance.'}
