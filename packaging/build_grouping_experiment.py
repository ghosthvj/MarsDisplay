"""Native-only, separately named console build. No SDK work on import/help."""
import argparse
from importlib import util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def _load(name):
    spec = util.spec_from_file_location('grouping_build_' + name, Path(__file__).with_name(name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load('build_portable')
payload = _load('grouping_payload')


def build(repo, *, run=None, smoke_check=None):
    base.require_host()  # Before SDK imports, paths, fixture reads or processes.
    repo = Path(repo).absolute()
    if any(path.is_symlink() for path in (repo, *repo.parents)):
        raise ValueError('Symlink repository')
    inventory, material = base.inspect_environment(repo, profile='usb-grouping-v1')
    version = inventory.pop('version')
    payload.destinations(repo / 'dist', version)
    source = payload.collect_source(repo)
    inventory.update(schema='marsdisplay-grouping-v1', profile='usb-grouping-v1',
                     source_files=payload.hashes(source))
    work = repo / 'build'
    if work.is_symlink():
        raise ValueError('Symlink build directory')
    work.mkdir(exist_ok=True)
    run = subprocess.run if run is None else run
    smoke_check = _load('grouping_smoke').check if smoke_check is None else smoke_check
    with tempfile.TemporaryDirectory(prefix='grouping-', dir=work) as temporary:
        stage = Path(temporary)
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(('QT_', 'QML', 'PYTHON', 'PLAYWRIGHT_'))}
        temp = stage / 'temp'
        temp.mkdir()
        env.update({key: str(temp) for key in ('TMP', 'TEMP', 'TMPDIR')})
        env['PYINSTALLER_CONFIG_DIR'] = str(stage / 'cache')
        run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(stage / 'dist'),
             '--workpath', str(stage / 'work'), str(repo / 'packaging/MarsDisplayGroupingExperiment.spec')],
            cwd=repo, env=env, check=True, timeout=900)
        folder = stage / 'dist' / payload.NAME
        with (folder / 'README.txt').open('xb') as stream:
            stream.write(source['packaging/GROUPING-README.txt'])
        runtime = base.payload.read_tree(folder)
        payload.layout(runtime)
        inventory['packaged_smoke'] = smoke_check(folder, stage / 'smoke')
        destination = base.native_material.prepare(repo, runtime, inventory, stage / 'native-material',
                                                   profile='usb-grouping-v1')
        components, texts = base.collect_native(runtime, inventory, destination)
        supplemental = json.loads(texts['native/supplemental.json'])['components']
        inventory['native_components'] = [dict(item, **{
            field: ['native/' + name for name in item[field]] for field in ('licenses', 'version_evidence')})
            for item in components + supplemental]
        material.update(texts)
        if payload.collect_source(repo) != source:
            raise ValueError('Source changed during build; nothing published')
        return payload.assemble(repo / 'dist', version, runtime, source, material, inventory)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build the isolated console experiment on native Windows x64; no downloads.',
        epilog='Requires pinned Python 3.13 SDK and official VC++ v14 x64 14.51+. No hardware test; qualification fails closed. Existing outputs are never replaced.')
    parser.parse_args(argv)
    try:
        _, archive, checksum = build(Path(__file__).absolute().parents[1])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Experimental build failed: ' + str(error), file=sys.stderr)
        return 1
    print(archive.name + '\n' + checksum.name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
