"""Native Windows x64 console build; qualify before exclusive publication."""
import argparse
import base64
import hashlib
from importlib import metadata, util
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = '1.0.0'


def load(path):
    spec = util.spec_from_file_location('probe_build_' + path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = load(ROOT / 'packaging/payload.py')
qualification = load(Path(__file__).with_name('qualification.py'))
smoke = load(Path(__file__).with_name('smoke.py'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hashes(files):
    return {name: digest(data) for name, data in sorted(files.items())}


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


SOURCE_PATHS = (
    'LICENSE', 'pyproject.toml', 'requirements.txt', 'requirements-build.txt',
    *('src/mars_display/' + name + '.py' for name in
      ('__init__', 'frames', 'transport', 'devices', 'usb_protocol', 'usb_probe', 'usb_probe_process')),
    *('tools/windows-python-usb-probe/' + name for name in
      ('entrypoint.py', 'PythonUsbProbe.spec', 'build_probe.py', 'qualification.py', 'cpython_material.py', 'smoke.py', 'README.md')),
    *('tools/windows-usb-probe/' + name for name in
      ('pattern.png', 'pattern.rgb565', 'pattern.json', 'pattern.rgb888', 'rgb888-provenance.json')),
    *('tests/' + name + '.py' for name in
      ('test_native_probe_fixture', 'test_usb_protocol', 'test_usb_probe',
       'test_usb_probe_process', 'test_packaging_python_usb_probe')),
    *('packaging/' + name + '.py' for name in
      ('payload', 'notices', 'native_evidence', 'native_runtime', 'native_material', 'build_portable', 'smoke')),
    '.github/workflows/windows-python-usb-probe.yml',
)


def collect_source(repo):
    files = payload.read_tree(repo, SOURCE_PATHS)
    # The app README includes unrelated owner metrics. The source distribution's
    # package readme is the diagnostic guide, not a copy of those observations.
    files['README.md'] = files['tools/windows-python-usb-probe/README.md']
    _, material = payload.collect_license_material(Path(repo) / 'third_party/license-material')
    files.update({'third_party/license-material/' + name: data for name, data in material.items()})
    native = load(ROOT / 'packaging/native_material.py').read_inputs(repo)
    # read_inputs validates immutable raw policy sources; no Qt SDK admission.
    files.update({'third_party/native-material/' + name: data for name, data in native['files'].items()})
    cpython = qualification.cpython_material.read_inputs(repo)
    files.update({qualification.cpython_material.PREFIX + '/' + name: data
                  for name, data in cpython['files'].items()})
    payload._validate(files)
    return files


def assert_source_stable(before, after):
    if before != after:
        raise ValueError('Source changed during build; nothing published')


def zip_bytes(files):
    payload._validate(files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def write_files(root, files):
    payload._validate(files)
    for name, data in sorted(files.items()):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def publish(output, files, expected_hashes):
    """Filesystem publisher only; build() owns mandatory qualification ordering.

    Validate before creating an exclusively owned output directory. Never reuse
    even an empty destination. Roll back only the directory this call created.
    """
    payload._validate(files)
    if hashes(files) != expected_hashes:
        raise ValueError('Publication SHA256 mismatch')
    if any(name.casefold() == 'sha256sums' for name in files):
        raise ValueError('Reserved SHA256SUMS path')
    complete = dict(files)
    complete['SHA256SUMS'] = ''.join(f'{sha}  {name}\n' for name, sha in hashes(files).items()).encode()
    archive_name = f'PythonUsbProbe-{VERSION}-Windows-x64.zip'
    archived = zip_bytes({'PythonUsbProbe/' + name: data for name, data in complete.items()})
    output = Path(output).absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError('Symlink output path')
    output.mkdir()  # Parent must already exist; claim this exact directory only.
    try:
        folder = output / 'PythonUsbProbe'
        folder.mkdir()
        write_files(folder, complete)
        if payload.read_tree(folder) != complete:
            raise ValueError('Published folder readback mismatch')
        archive = output / archive_name
        sidecar = output / (archive_name + '.sha256')
        write_files(output, {archive_name: archived,
                            sidecar.name: (digest(archived) + '  ' + archive_name + '\n').encode()})
        if archive.read_bytes() != archived:
            raise ValueError('Published archive readback mismatch')
        with zipfile.ZipFile(archive) as check:
            extracted = {info.filename: check.read(info) for info in check.infolist()}
        if extracted != {'PythonUsbProbe/' + name: data for name, data in complete.items()}:
            raise ValueError('Published ZIP readback mismatch')
        return archive, sidecar
    except BaseException:
        shutil.rmtree(output)
        raise


def source_revision(repo, source, run=subprocess.run):
    if (repo / '.git').exists():
        status = run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=repo,
                     capture_output=True, text=True, check=True, timeout=10).stdout
        if status:
            raise ValueError('Build requires a clean source checkout')
        commit = run(['git', 'rev-parse', 'HEAD'], cwd=repo, capture_output=True,
                     text=True, check=True, timeout=10).stdout.strip()
    else:
        provenance = json.loads(payload.read_tree(repo, ('SOURCE-PROVENANCE.json',))['SOURCE-PROVENANCE.json'])
        if provenance['files'] != hashes(source):
            raise ValueError('Extracted source provenance mismatch')
        commit = provenance['source_commit']
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Invalid source Git SHA')
    return commit


def installed_environment(sdk):
    import PyInstaller
    if sys.version_info[:3] != (3, 13, 16):
        raise ValueError('Python 3.13.16 is required')
    if metadata.version('PyInstaller') != '6.22.3' or metadata.version('pyserial') != '3.5':
        raise ValueError('Pinned PyInstaller/pyserial SDK required')
    notices = load(ROOT / 'packaging/notices.py')
    dependencies, material = notices.collect_distributions(['pyserial'])
    tools, extra = notices.collect_distributions(['PyInstaller'])
    material.update(extra)
    # Only these two generic helpers are used from the full-app builder.
    generic = load(ROOT / 'packaging/build_portable.py')
    material.update(generic.python_license(sdk))
    relative = 'PyInstaller/bootloader/' + PyInstaller.PLATFORM + '/run.exe'
    distribution = metadata.distribution('PyInstaller')
    matches = [entry for entry in distribution.files or [] if str(entry).replace('\\', '/') == relative]
    if len(matches) != 1 or matches[0].hash is None or matches[0].hash.mode != 'sha256':
        raise ValueError('Missing PyInstaller console bootloader RECORD')
    boot_bytes = payload.read_tree(distribution.locate_file(''), (relative,))[relative]
    recorded = base64.urlsafe_b64decode(matches[0].hash.value + '=' * (-len(matches[0].hash.value) % 4)).hex()
    if digest(boot_bytes) != recorded:
        raise ValueError('Installed bootloader differs from distribution RECORD')
    import zlib
    import pyexpat
    import _decimal
    sdk_components = {}
    for name, module, version in (('zlib', zlib, zlib.ZLIB_RUNTIME_VERSION),
                                  ('expat', pyexpat, pyexpat.EXPAT_VERSION.removeprefix('expat_')),
                                  ('libmpdec', _decimal, _decimal.__libmpdec_version__)):
        origin = Path(module.__file__) if getattr(module, '__file__', None) else sdk / 'python313.dll'
        try:
            relative_origin = origin.relative_to(sdk).as_posix()
        except ValueError:
            raise ValueError('SDK component version provider is outside selected SDK') from None
        raw = payload.read_tree(sdk, (relative_origin,))[relative_origin]
        sdk_components[name] = {'version': version, 'sdk_path': relative_origin, 'sha256': digest(raw)}
    return {'version': VERSION, 'target': 'Windows-x64', 'sdk_components': sdk_components,
            'build': {'Python': platform.python_version(), 'sys_version': sys.version,
                      'compiler': platform.python_compiler(), 'PyInstaller': '6.22.3', 'pyserial': '3.5'},
            'dependencies': dependencies, 'build_dependencies': tools,
            'bootloader': {'path': relative, 'sha256': digest(boot_bytes), 'record_sha256': recorded,
                           'distribution_metadata_sha256': digest(distribution.read_text('METADATA').encode()),
                           'source': 'https://github.com/pyinstaller/pyinstaller/tree/v6.22.3/bootloader'}}, material


def retain_failure(work, phase, inventory, runtime, analysis, material, error):
    # Never export absolute SDK/checkout paths, environment, or arbitrary errors.
    report = {'status': 'UNQUALIFIED', 'phase': phase, 'error_type': type(error).__name__,
              'source_commit': inventory.get('source_commit'),
              'source_files': inventory.get('source_files', {}), 'build': inventory.get('build', {}),
              'sdk_components': inventory.get('sdk_components', {}),
              'bootloader': inventory.get('bootloader', {}), 'native_hashes': hashes({
                  name: data for name, data in runtime.items() if Path(name).suffix.lower() in {'.exe', '.dll', '.pyd'}}),
              'analysis_modules': analysis.get('modules', []), 'pyz_modules': analysis.get('pyz_modules', []),
              'python_sdk_license': {'sha256': digest(material.get('runtime/Python/LICENSE.txt', b'')),
                  'text': material.get('runtime/Python/LICENSE.txt', b'').decode('utf-8', errors='replace')}}
    try:
        report['sdk_origin_facts'] = qualification.sdk_origin_facts(runtime, analysis.get('origins', {}), Path(sys.base_prefix))
    except (OSError, ValueError):
        report['sdk_origin_facts'] = {'status': 'unavailable'}
    try:
        report['native_evidence'] = qualification.measure_native(runtime, inventory)
    except Exception:
        report['native_evidence'] = {'status': 'unavailable'}
    # Sanitized, explicit qualifier messages contain relative names only.
    if isinstance(error, ValueError):
        message = str(error)
        # Known qualifier errors end in a relative payload name, never a host
        # pathname. Suppress other text rather than exporting arbitrary errors.
        if not any(char in message for char in ('\\', '\n')) and not re.search(r'[A-Za-z]:|/(?:Users|home|tmp)/', message):
            report['reason'] = message
    write_files(work, {'unqualified.json': json_bytes(report)})


def build(repo, *, run=subprocess.run):
    generic = load(ROOT / 'packaging/build_portable.py')
    generic.require_host()  # Before SDK inspection, files, directories or children.
    repo = Path(repo).absolute()
    source = collect_source(repo)
    revision = source_revision(repo, source, run)
    parent = repo / 'build'
    if any(path.is_symlink() for path in (parent, *parent.parents)):
        raise ValueError('Symlink build path')
    parent.mkdir(exist_ok=True)
    work = parent / 'python-usb-probe-work'
    output = parent / 'python-usb-probe'
    if output.exists() or output.is_symlink():
        raise FileExistsError('Diagnostic publication output already exists')
    work.mkdir()  # Never accept stale test/native evidence.
    inventory = {'source_commit': revision, 'source_files': hashes(source),
                 'source_file_types': {name: ('python' if name.endswith('.py') else
                     'raw-fixture' if name.endswith(('.rgb888', '.rgb565')) else 'rebuild-material')
                     for name in source}}
    runtime, analysis, material = {}, {}, {}
    phase = 'installed_sdk'
    try:
        sdk = Path(sys.base_prefix)
        installed, material = installed_environment(sdk)
        inventory.update(installed)
        with tempfile.TemporaryDirectory(prefix='native-', dir=work) as temporary:
            stage = Path(temporary)
            phase = 'native_source_tests'
            inventory['source_tests'] = smoke.source_tests(repo, stage / 'test-state', run=run)
            phase = 'analysis_and_compile'
            env = dict(os.environ)
            for name in list(env):
                if name.upper().startswith(('PYTHON', 'QT_', 'QML', 'PLAYWRIGHT_', 'MARS_')):
                    del env[name]
            state = stage / 'compiler-state'
            state.mkdir()
            for name in ('TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
                env[name] = str(state)
            env.update(PYINSTALLER_CONFIG_DIR=str(state / 'pyinstaller'), PYTHONDONTWRITEBYTECODE='1',
                       PROBE_ANALYSIS_REPORT=str(stage / 'analysis.json'))
            run([sys.executable, '-B', '-m', 'PyInstaller', '--distpath', str(stage / 'dist'),
                 '--workpath', str(stage / 'work'), str(repo / 'tools/windows-python-usb-probe/PythonUsbProbe.spec')],
                cwd=repo, env=env, check=True, timeout=600)
            runtime = payload.read_tree(stage / 'dist/PythonUsbProbe')
            analysis = json.loads(payload.read_tree(stage, ('analysis.json',))['analysis.json'])
            phase = 'native_qualification'
            entrypoint = 'tools/windows-python-usb-probe/entrypoint.py'
            if analysis.get('entrypoint') != {'path': entrypoint, 'sha256': digest(source[entrypoint])}:
                raise ValueError('Compiled entrypoint differs from source snapshot')
            inventory['native_profile'] = qualification.qualify(
                runtime, analysis['origins'], sdk, inventory, material, analysis, repo)
            if inventory['native_profile'].get('status') != 'QUALIFIED':
                raise ValueError('Native profile did not qualify publication')
            inventory['analysis'] = {key: analysis[key] for key in
                                     ('modules', 'pyz_modules', 'exe_sha256', 'bootloader_sha256', 'entrypoint')}
            phase = 'extracted_runtime_smoke'
            # Extract a deterministic archive, do not smoke only the build folder.
            extracted = stage / 'extracted'
            extracted.mkdir()
            with zipfile.ZipFile(io.BytesIO(zip_bytes(runtime))) as archive:
                archive.extractall(extracted)  # Names validated by zip_bytes/read_tree.
            if payload.read_tree(extracted) != runtime:
                raise ValueError('Extracted runtime readback mismatch')
            inventory['source_smoke'] = smoke.check_vector(
                [sys.executable, '-B', str(repo / 'tools/windows-python-usb-probe/entrypoint.py')],
                stage / 'source-state', run=run, source=repo)
            inventory['frozen_smoke'] = smoke.check_vector(
                [str(extracted / 'PythonUsbProbe.exe')], stage / 'frozen-state', run=run)
            if inventory['source_smoke'] != inventory['frozen_smoke']:
                raise ValueError('Source/frozen safe-command evidence differs')
            inventory['frozen_lifetime'] = smoke.frozen_lifetime(
                extracted / 'PythonUsbProbe.exe', stage / 'frozen-lifetime-state')
            inventory['parent_death'] = smoke.parent_death(repo, stage / 'parent-death-state')
            phase = 'source_stability'
            if payload.read_tree(extracted) != runtime:
                raise ValueError('Smoke changed extracted runtime files')
            assert_source_stable(source, collect_source(repo))
            if source_revision(repo, source, run) != revision:
                raise ValueError('Source revision changed during build')
            provenance = {'source_commit': revision, 'files': hashes(source)}
            additions = {'source.zip': zip_bytes({**source, 'SOURCE-PROVENANCE.json': json_bytes(provenance)}),
                         'LICENSE': source['LICENSE'], 'README.md': source['tools/windows-python-usb-probe/README.md'],
                         'SOURCE-ACCESS.txt': ('Diagnostic source and rebuild instructions: source.zip and README.md.\n'
                             'Complete corresponding upstream sources (retain equivalent access while distributing):\n'
                             'https://github.com/python/cpython/archive/refs/tags/v' + inventory['build']['Python'] + '.tar.gz\n'
                             'https://github.com/pyserial/pyserial/archive/refs/tags/v3.5.tar.gz\n'
                             'https://github.com/pyinstaller/pyinstaller/archive/refs/tags/v6.22.3.tar.gz\n'
                             'Additional native component sources: native-profile.json; terms: notices/.\n'
                             'Supplementary Qt texts in the registry do not mean Qt is shipped.\n').encode(),
                         'pattern.png': source['tools/windows-usb-probe/pattern.png'],
                         'pattern.json': source['tools/windows-usb-probe/pattern.json'],
                         'source-hashes.json': json_bytes(provenance),
                         'native-profile.json': json_bytes(inventory['native_profile']),
                         'test-evidence.json': json_bytes({key: inventory[key] for key in
                             ('source_tests', 'source_smoke', 'frozen_smoke', 'frozen_lifetime', 'parent_death')}),
                         'inventory.json': json_bytes(inventory)}
            additions.update({'notices/' + name: data for name, data in material.items()})
            if set(runtime) & set(additions):
                raise ValueError('Reserved package path collision')
            files = {**runtime, **additions}
            phase = 'publication'
            return publish(output, files, hashes(files))
    except Exception as error:
        retain_failure(work, phase, inventory, runtime, analysis, material, error)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build PythonUsbProbe 1.0.0 console onedir ZIP on native Windows x64.',
                                     epilog='Requires pinned Python 3.13.16 SDK, clean source, legal/native qualification and USB-free smoke. No downloads or USB transfers. Existing outputs are never replaced.')
    parser.parse_args(argv)
    try:
        archive, sidecar = build(ROOT)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Probe build failed: ' + str(error), file=sys.stderr)
        return 1
    print(str(archive) + '\n' + str(sidecar))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
