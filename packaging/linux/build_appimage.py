"""Offline Linux prototype assembly from a trusted, immutable production onedir."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IMAGE = 'MarsDisplay-x86_64.AppImage'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree(root):
    """Allow relocatable contained links, never devices, dangling links or loops."""
    if not root.is_dir():
        raise ValueError('unsafe input tree')
    try:
        for path in root.rglob('*'):
            mode = path.lstat().st_mode
            if path.is_symlink():
                if (os.path.isabs(os.readlink(path)) or
                        not path.resolve(strict=True).is_relative_to(root)):
                    raise ValueError('unsafe input tree')
            elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError('unsafe input tree')
    except (OSError, RuntimeError):
        raise ValueError('unsafe input tree') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name, help_text in [
        ('onedir', 'verified production directory matching --source-ref (not a tar or probe)'),
        ('tool', 'original pinned appimagetool AppImage, not extracted AppRun'),
        ('runtime', 'independently pinned local type2 runtime'),
        ('output', 'new output directory; parent must exist; failures retained'),
        ('notices', 'collected attribution tree; presence is NOT legal clearance'),
        ('license', 'project LICENSE file'),
    ]:
        parser.add_argument('--' + name, required=True, type=Path, help=help_text)
    parser.add_argument('--source-ref', default='42feea4',
                        help='caller-verified source revision for manifest (default: 42feea4)')
    args = parser.parse_args(argv)
    try:
        if sys.platform != 'linux' or platform.machine() != 'x86_64':
            raise ValueError('Linux x86_64 builder required')
        if os.path.lexists(args.output):
            raise ValueError('output must not exist')
        output = args.output.resolve()
        inputs = [args.onedir, args.tool, args.runtime, args.notices, args.license, HERE]
        if any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output)
               for p in inputs):
            raise ValueError('output overlaps an input')
        if not output.parent.is_dir():
            raise ValueError('output parent must exist')
        source, notices = args.onedir.resolve(), args.notices.resolve()
        binary = source / 'MarsDisplay'
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('onedir needs executable MarsDisplay')
        tree(source)
        tree(notices)
        if not any(p.is_file() and p.stat().st_size for p in notices.rglob('*')):
            raise ValueError('notices must not be empty')
        if not args.license.is_file() or not args.license.stat().st_size:
            raise ValueError('project LICENSE must not be empty')
        pins = json.loads((HERE / 'appimage-tools.json').read_text())
        for name, path in [('appimagetool', args.tool), ('runtime', args.runtime)]:
            if digest(path) != pins[name]['sha256']:
                raise ValueError(f'{name} SHA256 mismatch')
        if not os.access(args.tool, os.X_OK):
            raise ValueError('appimagetool must be executable')
        assets = {name: (HERE / name).read_bytes() for name in
                  ('AppRun', 'MarsDisplay.desktop', 'marsdisplay.svg')}
        # Inputs must remain immutable during assembly. No downloads or cleanup.
        output.mkdir()
        appdir = output / 'MarsDisplay.AppDir'
        shutil.copytree(source, appdir / 'usr/lib/marsdisplay', symlinks=True)
        shutil.copytree(notices, appdir / 'notices', symlinks=True)
        shutil.copy2(args.license, appdir / 'LICENSE')
        for name, data in assets.items():
            with (appdir / name).open('xb') as stream:
                stream.write(data)
        (appdir / 'AppRun').chmod(0o755)
        manifest = {
            'source': args.source_ref, 'builder': 'Ubuntu Noble / Python 3.13.5 / glibc 2.39',
            'input_contract': 'Caller supplies verified immutable production onedir',
            'tools': pins, 'qualification': 'Experimental; not redistribution clearance',
            'checks': ['Parent reports production frozen worker smoke PASS'],
            'limitations': ['Browser sandbox denied in container; capture not proven',
                            'COSMIC, physical panel and native Windows not qualified',
                            'Native/runtime attribution and corresponding source pending'],
        }
        with (appdir / 'prototype.json').open('x') as stream:
            json.dump(manifest, stream, indent=2)
            stream.write('\n')
        # Only the build tool gets extract-and-run; AppRun never changes worker env.
        with (output / 'appimagetool.log').open('xb') as log:
            subprocess.run([str(args.tool.resolve()), '--runtime-file', str(args.runtime.resolve()),
                            str(appdir), str(output / IMAGE)], cwd=output, check=True,
                           env={**os.environ, 'ARCH': 'x86_64', 'APPIMAGE_EXTRACT_AND_RUN': '1'},
                           stdout=log, stderr=subprocess.STDOUT)
        if not (output / IMAGE).is_file() or not (output / IMAGE).stat().st_size:
            raise ValueError('appimagetool produced no image')
        with (output / (IMAGE + '.sha256')).open('x') as stream:
            stream.write(digest(output / IMAGE) + '  ' + IMAGE + '\n')
    except subprocess.CalledProcessError:
        print('error: appimagetool failed; output retained; see appimagetool.log', file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2
    print('Created prototype: ' + IMAGE)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
