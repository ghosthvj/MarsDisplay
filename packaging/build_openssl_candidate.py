"""Build two UNQUALIFIED OpenSSL candidates; never rewrite admission policy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

import openssl_inputs as inputs
import openssl_tools as tools

DLLS = ('libcrypto-3-x64.dll', 'libssl-3-x64.dll')
VS_ROOT = Path('C:/Program Files/Microsoft Visual Studio/18/Enterprise')
SDK_ROOT = Path('C:/Program Files (x86)/Windows Kits/10')
SDK_VERSION = '10.0.26100.0'
EPOCH = str(int(datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp()))
CONFIGURE = ('VC-WIN64A', 'shared', '--prefix=C:/Program Files/MarsDisplay/OpenSSL',
             '--openssldir=C:/Program Files/MarsDisplay/OpenSSL/ssl')
ARCHIVES = {'openssl': {'url': inputs.SOURCE_URL, 'sha256': inputs.SOURCE_SHA256,
                        'size': 53468565, 'filename': 'openssl.tar.gz'},
            **{name: {**record, 'filename': name + '.zip'} for name, record in tools.TOOLS.items()}}


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Non-HTTPS input redirect is forbidden')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def digest(path, limit=400_000_000):
    path = inputs._plain(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Invalid candidate input file')
    result, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            if size > limit:
                raise ValueError('Candidate input exceeds size limit')
            result.update(block)
    return {'sha256': result.hexdigest(), 'size': size}


def fetch(directory):
    directory = inputs._plain(directory)
    directory.mkdir(parents=True)  # Never overwrite an existing input directory.
    opener = urllib.request.build_opener(HTTPSRedirect())
    for record in ARCHIVES.values():
        path = directory / record['filename']
        size = 0
        with opener.open(record['url'], timeout=60) as response, path.open('xb') as output:
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > record['size']:
                    raise ValueError('Downloaded input exceeds pinned size')
                output.write(block)
        if digest(path) != {key: record[key] for key in ('sha256', 'size')}:
            raise ValueError('Downloaded input does not match its pin')


def compiler(vs_root, sdk_root):
    root = inputs._plain(vs_root) / 'VC/Tools/MSVC'
    versions = [path for path in root.iterdir()
                if re.fullmatch(r'14\.44\.\d+', path.name) and path.is_dir()]
    if len(versions) != 1:
        raise ValueError('Exactly one MSVC 14.44 toolset is required')
    vc = inputs._plain(versions[0])
    sdk = inputs._plain(sdk_root)
    if not (sdk / 'bin' / SDK_VERSION / 'x64').is_dir():
        raise ValueError('Pinned Windows SDK directory is missing')
    return {'vc': vc, 'sdk': sdk}


def environment(layout, work):
    vc, sdk, perl, nasm = (layout[key] for key in ('vc', 'sdk', 'perl', 'nasm'))
    system = Path('C:/Windows')
    path = [vc / 'bin/Hostx64/x64', sdk / 'bin' / SDK_VERSION / 'x64', nasm,
            perl / 'perl/bin', perl / 'c/bin', system / 'System32']
    includes = [vc / 'include', *[sdk / 'Include' / SDK_VERSION / name
                                  for name in ('ucrt', 'shared', 'um', 'winrt')]]
    libraries = [vc / 'lib/x64', *[sdk / 'Lib' / SDK_VERSION / name / 'x64'
                                   for name in ('ucrt', 'um')]]
    # _CL_ appends to upstream flags. Keep path-dependent flags out of buildinf.h;
    # the recipe records the normalization template, not an ambient environment.
    flags = ['/Z7', '/Brepro', '/experimental:deterministic',
             f'/pathmap:{work}=C:\\openssl-build']
    return {'SystemRoot': str(system), 'COMSPEC': str(system / 'System32/cmd.exe'),
            'PATH': ';'.join(map(str, path)), 'PATHEXT': '.COM;.EXE;.BAT;.CMD',
            'INCLUDE': ';'.join(map(str, includes)), 'LIB': ';'.join(map(str, libraries)),
            'TEMP': str(work / 'tmp'), 'TMP': str(work / 'tmp'),
            'PERL5LIB': ';'.join(str(perl / 'perl' / name) for name in ('lib', 'vendor/lib', 'site/lib')),
            'SOURCE_DATE_EPOCH': EPOCH, 'VSLANG': '1033', 'TZ': 'UTC',
            'OS': 'Windows_NT', 'PROCESSOR_ARCHITECTURE': 'AMD64',
            '_CL_': subprocess.list2cmdline(flags), 'ASFLAGS': '-g --reproducible',
            'LDFLAGS': '/nologo /debug /Brepro /INCREMENTAL:NO /PDBALTPATH:openssl.pdb'}


def inventory(layout):
    vc, sdk = layout['vc'], layout['sdk']
    roots = {'vc_bin': vc / 'bin/Hostx64/x64', 'vc_include': vc / 'include',
             'vc_lib': vc / 'lib/x64', 'sdk_bin': sdk / 'bin' / SDK_VERSION / 'x64',
             'sdk_include': sdk / 'Include' / SDK_VERSION,
             'sdk_ucrt': sdk / 'Lib' / SDK_VERSION / 'ucrt/x64',
             'sdk_um': sdk / 'Lib' / SDK_VERSION / 'um/x64',
             'perl': layout['perl'], 'nasm': layout['nasm']}
    return {name: inputs.fingerprint(root) for name, root in roots.items()}


def capture(command, env, codes=(0,)):
    result = subprocess.run(list(map(str, command)), env=env, capture_output=True,
                            text=True, errors='replace', check=False)
    text = result.stdout + result.stderr
    if result.returncode not in codes or len(text) > 65536:
        raise ValueError('Build tool identification failed')
    return text.strip()


def identify(layout, env):
    vc = layout['vc'] / 'bin/Hostx64/x64'
    for name in ('cl.exe', 'link.exe', 'lib.exe', 'nmake.exe'):
        digest(vc / name)
    perl = capture([layout['perl'] / 'perl/bin/perl.exe', '-MConfig', '-e',
                    'print "$^V|$Config{archname}"'], env)
    nasm = capture([layout['nasm'] / 'nasm.exe', '--version'], env)
    cl = capture([vc / 'cl.exe'], env, codes=(0, 2))
    version = re.search(r'Compiler Version (19\.44\.\d+(?:\.\d+)?) for x64', cl)
    if perl != 'v5.42.0|MSWin32-x64-multi-thread' or not nasm.startswith('NASM version 2.16.03 '):
        raise ValueError('Portable tool version or architecture mismatch')
    if not version:
        raise ValueError('MSVC compiler identity mismatch')
    return {'msvc_directory': layout['vc'].name, 'compiler_version': version.group(1),
            'sdk_directory': SDK_VERSION, 'perl': perl, 'nasm': '2.16.03'}


def build_once(label, input_directory, output, layout):
    root = output / label
    root.mkdir()
    source = inputs.extract_source(input_directory / ARCHIVES['openssl']['filename'], root / 'src')
    before = inputs.fingerprint(source)
    build = root / 'build'
    build.mkdir()
    (root / 'tmp').mkdir()
    env = environment(layout, root)
    perl = layout['perl'] / 'perl/bin/perl.exe'
    make = layout['vc'] / 'bin/Hostx64/x64/nmake.exe'
    commands = ([perl, '../src/Configure', *CONFIGURE], [make, '/nologo'],
                [make, '/nologo', 'test'])
    for command in commands:
        subprocess.run(list(map(str, command)), cwd=build, env=env, check=True)
    if inputs.fingerprint(source) != before:
        raise ValueError('OpenSSL source changed during compilation')
    return {'id': label, 'upstream_tests': 'passed',
            'files': {name: digest(build / name, limit=32 * 1024 * 1024) for name in DLLS}}


def require_equal(builds):
    if (len(builds) != 2 or any(set(build['files']) != set(DLLS) for build in builds)
            or builds[0]['files'] != builds[1]['files']):
        raise ValueError('Controlled OpenSSL builds differ')


def candidate(input_directory, output):
    input_directory, output = inputs._plain(input_directory), inputs._plain(output)
    if output.exists():
        raise FileExistsError('Candidate output already exists')
    for record in ARCHIVES.values():
        if digest(input_directory / record['filename']) != {key: record[key] for key in ('sha256', 'size')}:
            raise ValueError('Candidate input archive mismatch')
    layout = compiler(VS_ROOT, SDK_ROOT)
    output.mkdir(parents=True)
    report = {'schema': 1, 'status': 'UNQUALIFIED', 'completed': False, 'phase': 'portable_tools',
              'source_commit': inputs.SOURCE_COMMIT, 'archives': ARCHIVES, 'patches': [],
              'configure': list(CONFIGURE), 'source_date_epoch': EPOCH, 'builds': []}
    for variable, field, pattern in (('ImageVersion', 'runner_image', r'\d{8}\.\d+\.\d+'),
                                     ('GITHUB_SHA', 'project_commit', r'[0-9a-f]{40,64}')):
        value = os.environ.get(variable, '')
        report[field] = value if re.fullmatch(pattern, value) else None
    try:
        tool_root = output / 'tools'
        tool_root.mkdir()
        for name in ('nasm', 'perl'):
            executable = tools.prepare(name, input_directory / ARCHIVES[name]['filename'], tool_root / name)
            layout[name] = executable.parent if name == 'nasm' else tool_root / name
        report['phase'] = 'toolchain'
        before = inventory(layout)
        report['tool_inputs'] = before
        probe = output / 'probe'
        (probe / 'tmp').mkdir(parents=True)
        report['tool_versions'] = identify(layout, environment(layout, probe))
        report['flags'] = {'compiler': ['/Z7', '/Brepro', '/experimental:deterministic',
                                        '/pathmap:<build-root>=C:\\openssl-build'],
                           'assembler': '-g --reproducible',
                           'linker': environment(layout, probe)['LDFLAGS']}
        recipe = hashlib.sha256()
        for name in ('build_openssl_candidate.py', 'openssl_inputs.py', 'openssl_tools.py'):
            recipe.update(name.encode() + b'\0' + Path(__file__).with_name(name).read_bytes().replace(b'\r\n', b'\n'))
        report['recipe_lf_sha256'] = recipe.hexdigest()
        for label in ('build-a', 'different-build-b'):
            report['phase'] = label
            report['builds'].append(build_once(label, input_directory, output, layout))
        report['phase'] = 'reproducibility'
        require_equal(report['builds'])
        if inventory(layout) != before:
            raise ValueError('Tool inputs changed during compilation')
        report.update(completed=True, phase='measured', reproducible=True)
    except Exception as error:
        # Never serialize exception text, arbitrary paths, or inherited environment.
        report['error_type'] = type(error).__name__
    with (output / 'candidate.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    print('OpenSSL controlled candidate: ' + json.dumps(report, sort_keys=True))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True, help='Directory containing the three pinned archives')
    parser.add_argument('--output', type=Path, required=True, help='New owned candidate directory; never a release output')
    parser.add_argument('--download', action='store_true', help='Fetch pinned archives into a new inputs directory')
    args = parser.parse_args(argv)
    if sys.platform != 'win32':
        print('Controlled OpenSSL candidate requires Windows.', file=sys.stderr)
        return 1
    try:
        if inputs._plain(args.output).exists():
            raise FileExistsError('Candidate output already exists')
        if args.download:
            fetch(args.inputs)
        report = candidate(args.inputs, args.output)
        if report['completed']:
            return 0
    except Exception:
        pass
    print('Controlled OpenSSL candidate failed; no DLLs are approved.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
