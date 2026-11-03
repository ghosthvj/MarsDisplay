"""Build in the nonroot pinned Linux SDK; Git provenance remains host-owned."""
import argparse
from importlib import metadata, util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

HERE = Path(__file__).resolve().parent


def load(path):
    spec = util.spec_from_file_location('sdk_' + path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assembly = load(HERE / 'assemble_release.py')
notices = load(HERE.parent / 'notices.py')
payload = notices._payload


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def write_tree(root, files):
    payload._validate(files)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def main(argv=None, *, runner=None, sdk=None, collector=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Use an exported source tree and a fresh output with existing parent. '
        'No downloads or SDK-venv writes. Failures retain private output/build.log. '
        'Export only onedir/, notices/ and build.json after exit zero.'))
    parser.add_argument('--project', required=True, type=Path, help='immutable exported stamped source, without .git')
    parser.add_argument('--release-record', required=True, type=Path, help='host-verified canonical release JSON')
    parser.add_argument('--output', required=True, type=Path, help='fresh private build directory')
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise ValueError('output must not exist')
        payload.read_tree(args.output.parent, ())
        output, project = args.output.resolve(), args.project.resolve()
        if output.is_relative_to(project) or project.is_relative_to(output):
            raise ValueError('output overlaps project')
        sdk = (dict(platform=sys.platform, machine=platform.machine(),
                    uid=getattr(os, 'geteuid', lambda: 0)(), python=platform.python_version(),
                    prefix=Path(sys.base_prefix)) if sdk is None else sdk)
        if sdk['platform'] != 'linux' or sdk['machine'] != 'x86_64' or sdk['uid'] == 0:
            raise ValueError('nonroot Linux x86_64 SDK required')
        files = payload.read_tree(args.project)
        record = assembly.release_record(args.release_record)
        import hashlib
        if hashlib.sha256(files['pyproject.toml']).hexdigest() != record['build_pyproject_sha256']:
            raise ValueError('stamped project does not match release record')
        config = tomllib.loads(files['pyproject.toml'].decode())
        if config['project']['version'] != record['version']:
            raise ValueError('stamped project does not match release record')
        pins = json.loads(files['packaging/linux/toolchain.json'])['python']
        if (sdk['python'] != pins['version'] or
                assembly.legacy.digest(sdk['prefix'].parent / 'Python.tar.xz') != pins['sha256']):
            raise ValueError('SDK CPython pin mismatch')
        for name in ('LICENSE', 'packaging/linux/Release.spec', 'packaging/linux/smoke.py',
                     'packaging/linux/build_evidence.py'):
            if name not in files:
                raise ValueError('missing SDK build input: ' + name)
        inventory, legal = (notices.collect_distributions if collector is None else collector)(
            ['PyInstaller'], material_root=project / 'third_party/license-material')
        payload._validate(legal)
        builders = [item for item in inventory if canonicalize_name(item['name']) == 'pyinstaller']
        requirements = [Requirement(item) for item in config['project']['optional-dependencies']['build']]
        requirements = [item for item in requirements if canonicalize_name(item.name) == 'pyinstaller']
        if (len(builders) != 1 or len(requirements) != 1 or
                builders[0]['version'] not in requirements[0].specifier or
                not builders[0]['licenses'] or any(name not in legal for name in builders[0]['licenses'])):
            raise ValueError('PyInstaller identity/legal inputs do not match build requirement')
        output.mkdir(mode=0o700)
        work, target = output / 'project', output / 'application'
        write_tree(work, files)  # pip/setuptools may mutate only this private copy.
        (output / 'home').mkdir()
        env = {**os.environ, 'HOME': str(output / 'home'),
               'XDG_CACHE_HOME': str(output / 'cache'), 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': os.pathsep.join((str(target), str(work / 'src'))),
               'PLAYWRIGHT_BROWSERS_PATH': '0', 'QT_QPA_PLATFORM': 'offscreen',
               'PIP_NO_INDEX': '1', 'PIP_NO_CACHE_DIR': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
        execute = subprocess.run if runner is None else runner
        with (output / 'build.log').open('xb') as log:
            def run(*command):
                execute([sys.executable, '-B', *map(str, command)], cwd=work, env=env,
                        check=True, stdout=log, stderr=subprocess.STDOUT)
            run('-m', 'pip', 'install', '--no-index', '--no-deps', '--no-build-isolation',
                '--no-compile', '--target', target, '.')
            installed = [dist.version for dist in metadata.distributions(path=[str(target)])
                         if canonicalize_name(dist.metadata['Name']) == canonicalize_name(config['project']['name'])]
            if installed != [record['version']]:
                raise ValueError('installed application version mismatch')
            run('-m', 'PyInstaller', '--noconfirm', '--workpath', output / 'work',
                '--distpath', output / 'onedir', work / 'packaging/linux/Release.spec')
            appdir = output / 'onedir/MarsDisplay'
            run(work / 'packaging/linux/smoke.py', '--appdir', appdir)
            acquisition = output / 'acquisition'
            run(work / 'packaging/linux/build_evidence.py', '--payload', appdir / '_internal',
                '--toc', output / 'work/Release/COLLECT-00.toc', '--project', work, '--output', acquisition)
        result = dict(schema=1, release=record, installed_version=installed[0],
                      sdk_python=sdk['python'], execution_uid=sdk['uid'],
                      executable_sha256=assembly.legacy.digest(appdir / 'MarsDisplay'),
                      pyinstaller_version=builders[0]['version'],
                      checks=['frozen-worker-smoke', 'native-source-association'],
                      qualification='Measured outputs and completed checks, not attestation or legal approval')
        public = payload.read_tree(acquisition / 'notices')
        additional = {'application/LICENSE': files['LICENSE'], 'application/build.json': encoded(result),
                      'build-tools/installed.json': encoded(inventory),
                      'build-tools/SOURCE-ACCESS.txt': (
                          'PyInstaller source and bootloader exception: retain the installed legal material.\n'
                          'https://github.com/pyinstaller/pyinstaller/archive/refs/tags/v' +
                          builders[0]['version'] + '.tar.gz\n'
                          'The generated executable combines application and bootloader code; it is not an unchanged wheel file.\n'
                          'Application sources and canonical release provenance are in the companion source snapshot.\n').encode(),
                      **{'build-tools/' + name: data for name, data in legal.items()}}
        if public.keys() & additional.keys():
            raise ValueError('notice namespace collision')
        write_tree(output / 'notices', public | additional)
        with (output / 'build.json').open('xb') as stream:
            stream.write(encoded(result))
    except subprocess.CalledProcessError:
        print('error: SDK command failed; output retained; see build.log', file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2
    print('Prepared Linux SDK build.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
