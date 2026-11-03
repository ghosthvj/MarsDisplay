"""Offline release assembly; caller owns source, build and legal qualification."""
import argparse
from importlib import util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IMAGE = 'MarsDisplay.AppImage'


def _load(path):
    spec = util.spec_from_file_location('assembly_' + path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = _load(HERE / 'build_appimage.py')
versioning = _load(HERE.parent / 'release_version.py')


def release_record(path):
    """Validate the canonical shape, not its association with Git or built bytes."""
    record = json.loads(path.read_text(encoding='utf-8'))
    fields = {'schema', 'method', 'tag', 'version', 'source_commit', 'source_version',
              'source_pyproject_sha256', 'build_pyproject_sha256'}
    try:
        if (not isinstance(record, dict) or set(record) != fields
                or type(record['schema']) is not int or record['schema'] != 1
                or record['method'] != 'project-version-v1'
                or any(not isinstance(record[key], str) or not record[key]
                       for key in fields - {'schema'})
                or versioning.version(record['tag']) != record['version']
                or not re.fullmatch('[a-f0-9]{40}', record['source_commit'])
                or any(not re.fullmatch('[a-f0-9]{64}', record[key]) for key in
                       ('source_pyproject_sha256', 'build_pyproject_sha256'))):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError('invalid release record') from None
    return record


def main(argv=None, *, runner=None, pins=None):
    """Runner/pins injection is Python-only for offline portable tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name, help_text in [
        ('onedir', 'immutable production directory containing executable MarsDisplay'),
        ('tool', 'original pinned executable appimagetool AppImage'),
        ('runtime', 'independently pinned type2 runtime'),
        ('output', 'fresh directory with existing parent; failed output retained'),
        ('notices', 'merged attribution tree, separate from downloaded tools'),
        ('license', 'nonempty project LICENSE'),
        ('release-record', 'JSON returned by host release_version.inspect after stamping'),
    ]:
        parser.add_argument('--' + name, required=True, type=Path, help=help_text)
    args = parser.parse_args(argv)
    try:
        if runner is None and (sys.platform != 'linux' or platform.machine() != 'x86_64'):
            raise ValueError('Linux x86_64 builder required')
        if os.path.lexists(args.output):
            raise ValueError('output must not exist')
        output = args.output.resolve()
        inputs = [args.onedir, args.tool, args.runtime, args.notices,
                  args.license, args.release_record, HERE]
        if any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output)
               for p in inputs):
            raise ValueError('output overlaps an input')
        if not output.parent.is_dir():
            raise ValueError('output parent must exist')
        source, notices = args.onedir.resolve(), args.notices.resolve()
        legacy.tree(source)
        legacy.tree(notices)
        binary = source / 'MarsDisplay'
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('onedir needs executable MarsDisplay')
        if not any(p.is_file() and p.stat().st_size for p in notices.rglob('*')):
            raise ValueError('notices must not be empty')
        if not args.license.is_file() or not args.license.stat().st_size:
            raise ValueError('project LICENSE must not be empty')
        record = release_record(args.release_record)
        pins = json.loads((HERE / 'appimage-tools.json').read_text()) if pins is None else pins
        measured = {}
        for name, path in [('appimagetool', args.tool), ('runtime', args.runtime)]:
            measured[name] = {'sha256': legacy.digest(path)}
            if measured[name]['sha256'] != pins[name]['sha256']:
                raise ValueError(f'{name} SHA256 mismatch')
        if not os.access(args.tool, os.X_OK):
            raise ValueError('appimagetool must be executable')
        assets = {name: (HERE / name).read_bytes() for name in
                  ('AppRun', 'MarsDisplay.desktop', 'marsdisplay.svg')}
        metadata = {'schema': 1, 'release': record, 'tools': measured,
                    'executable_sha256': legacy.digest(binary),
                    'qualification': 'Experimental; record consistency is not source/build verification'}
        # All inputs validated before the first write. Caller keeps them immutable.
        output.mkdir()
        appdir = output / 'MarsDisplay.AppDir'
        shutil.copytree(source, appdir / 'usr/lib/marsdisplay', symlinks=True)
        shutil.copytree(notices, appdir / 'notices', symlinks=True)
        shutil.copy2(args.license, appdir / 'LICENSE')
        for name, data in assets.items():
            with (appdir / name).open('xb') as stream:
                stream.write(data)
        (appdir / 'AppRun').chmod(0o755)
        with (appdir / 'release.json').open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(metadata, indent=2) + '\n')
        # Extraction applies only to the tool, never to the application launcher.
        with (output / 'appimagetool.log').open('xb') as log:
            (subprocess.run if runner is None else runner)(
                [str(args.tool.resolve()), '--runtime-file', str(args.runtime.resolve()),
                 str(appdir), str(output / IMAGE)], cwd=output, check=True,
                env={**os.environ, 'ARCH': 'x86_64', 'APPIMAGE_EXTRACT_AND_RUN': '1'},
                stdout=log, stderr=subprocess.STDOUT)
        image = output / IMAGE
        if image.is_symlink() or not image.is_file() or not image.stat().st_size:
            raise ValueError('appimagetool produced no image')
    except subprocess.CalledProcessError:
        print('error: appimagetool failed; output retained; see appimagetool.log', file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2
    print('Created release: ' + IMAGE)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
