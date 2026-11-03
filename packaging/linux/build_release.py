"""Build four versioned experimental Linux AppImage assets; never publish."""
import argparse
import hashlib
from importlib import util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    spec = util.spec_from_file_location('host_' + path.stem, path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = load(ROOT / 'packaging/payload.py')
versioning = load(ROOT / 'packaging/release_version.py')
source_export = load(ROOT / 'packaging/linux/release_source.py')
transport = load(ROOT / 'packaging/linux/sdk_transport.py')


def write_tree(root, files):
    payload._validate(files)
    spellings = {}
    for name in files:
        parts = name.split('/')
        for end in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:end])
            if spellings.setdefault(prefix.casefold(), prefix) != prefix:
                raise ValueError('content namespace collision')
    root.mkdir()
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)


def instructions(record):
    base = f'MarsDisplay-{record["version"]}-Linux-x86_64'
    image = base + '.AppImage'
    return f'''# MarsDisplay {record['version']} — experimental Linux x86_64

Original source commit: {record['source_commit']}

For Ubuntu 24.04-class systems (glibc 2.39 baseline). This is not a promise of
compatibility with every Linux distribution or desktop.

Check the downloaded image, then run as your ordinary desktop user:

```sh
sha256sum -c {image}.sha256
sha256sum -c {base}-support.zip.sha256
chmod +x {image}
./{image}
```

If FUSE is unavailable: `APPIMAGE_EXTRACT_AND_RUN=1 ./{image}`.
Never run MarsDisplay with sudo. USB permissions are manual: inspect the selected
port's group, arrange membership when needed, then log out and back in. No udev
rule or group membership is installed automatically. No automatic updater or
Linux autostart integration is provided.

The support archive contains stamped source, notices, measured records and recipe
documentation. See source/docs/linux-release-build.md and
source/docs/linux-sdk-transport.md.
The host release command needs the original Git commit; the SDK stage can consume
curated source and the canonical record without Git. Notices/source associations
are not legal clearance or binary-build attestations. Do not publish private
workspaces, downloaded tools, input/output tar diagnostics or build logs.
'''.encode()


def main(argv=None, *, repo=None, runner=None):
    """Repo/runner overrides are Python-only integration-test seams."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True, help='Canonical release tag; builds committed HEAD without creating a tag.')
    parser.add_argument('--output', required=True, type=Path, help='Fresh four-asset directory with an existing unlinked parent.')
    parser.add_argument('--sudo-docker', action='store_true', help='Explicitly wrap only Docker with sudo -n; container stays UID/GID 10001.')
    args = parser.parse_args(argv)
    work = None
    try:
        if runner is None and (sys.platform != 'linux' or platform.machine() != 'x86_64'):
            raise ValueError('Linux x86_64 host required')
        if os.path.lexists(args.output):
            raise ValueError('output must not exist')
        payload.read_tree(args.output.parent, ())
        output = args.output.resolve()
        root = ROOT if repo is None else Path(repo)
        payload.read_tree(root, ())
        root = root.resolve()
        versioning.version(args.tag)
        sha = versioning.git(root, 'rev-parse', 'HEAD').decode().strip()
        work = Path(tempfile.mkdtemp(prefix='.linux-release-', dir=output.parent))
        checkout, context, source = work / 'checkout', work / 'context', work / 'source'
        docker = (['sudo', '-n'] if args.sudo_docker else []) + ['docker']
        engine = subprocess.run if runner is None else runner
        with (work / 'host.log').open('xb') as log:
            def run(command, **kwargs):
                return engine(list(map(str, command)), check=True,
                              **{'stdout': log, 'stderr': log, **kwargs})

            run(['git', 'clone', '--local', '--no-hardlinks', '--no-checkout', root, checkout])
            run(['git', '-C', checkout, 'checkout', '--detach', sha])
            context_files = payload.read_tree(checkout, ('pyproject.toml', 'packaging/linux/Dockerfile',
                                                         'packaging/linux/toolchain.json'))
            write_tree(context, context_files)
            versioning.prepare(checkout, args.tag)
            record = versioning.inspect(checkout, sha)
            marker = checkout / 'build/release-version.json'
            source_files = source_export.collect_source(checkout)
            write_tree(source, source_files)
            inputs = work / 'inputs'
            run([sys.executable, '-B', checkout / 'packaging/linux/fetch_inputs.py', '--output', inputs])
            tools = payload.read_tree(inputs / 'tools')
            pins = json.loads(source_files['packaging/linux/appimage-tools.json'])
            names = {'appimagetool': 'appimagetool-x86_64.AppImage', 'runtime': 'runtime-x86_64'}
            if set(tools) != set(names.values()):
                raise ValueError('unexpected tool inventory')
            for key, name in names.items():
                if hashlib.sha256(tools[name]).hexdigest() != pins[key]['sha256']:
                    raise ValueError('tool SHA256 mismatch')
            tool, runtime = (inputs / 'tools' / names[key] for key in ('appimagetool', 'runtime'))
            tool.chmod(0o755)
            image = 'marsdisplay-linux-sdk:' + work.name.lstrip('.')
            run([*docker, 'build', '--platform', 'linux/amd64', '--tag', image,
                 '--file', context / 'packaging/linux/Dockerfile', context])
            image_id = run([*docker, 'image', 'inspect', '--format', '{{.Id}}', image], stdout=subprocess.PIPE).stdout.decode().strip()
            if not re.fullmatch('sha256:[a-f0-9]{64}', image_id):
                raise ValueError('invalid measured SDK image identity')
            sdk = transport.run_sdk(source, marker, image_id, work / 'sdk', sudo=args.sudo_docker, runner=engine)
            notices = {}
            for tree in (sdk / 'notices', inputs / 'notices'):
                files = payload.read_tree(tree)
                if notices.keys() & files.keys():
                    raise ValueError('notice collision')
                notices.update(files)
            if notices.get('application/build.json') != (sdk / 'build.json').read_bytes():
                raise ValueError('SDK public build record mismatch')
            identity = 'application/sdk-image.json'
            if identity in notices:
                raise ValueError('notice collision')
            notices[identity] = (json.dumps(dict(schema=1, image_id=image_id,
                dockerfile_sha256=hashlib.sha256(context_files['packaging/linux/Dockerfile']).hexdigest(),
                source_pyproject_sha256=record['source_pyproject_sha256'],
                qualification='Measured local image identity and recipe, not rebuild attestation'), indent=2) + '\n').encode()
            write_tree(work / 'notices', notices)
            assembled = work / 'assembled'
            run([sys.executable, '-B', checkout / 'packaging/linux/assemble_release.py',
                 '--onedir', sdk / 'onedir/MarsDisplay', '--tool', tool, '--runtime', runtime,
                 '--output', assembled, '--notices', work / 'notices', '--license', source / 'LICENSE',
                 '--release-record', marker])
            content = {'README.md': instructions(record),
                       'release.json': (assembled / 'MarsDisplay.AppDir/release.json').read_bytes(),
                       **{'source/' + name: data for name, data in source_files.items()},
                       **{'notices/' + name: data for name, data in notices.items()}}
            write_tree(work / 'content', content)
            command = [sys.executable, '-B', checkout / 'packaging/linux/release_assets.py']
            run([*command, 'build', '--image', assembled / 'MarsDisplay.AppImage', '--content', work / 'content',
                 '--output', output, '--tag', args.tag, '--sha', sha], cwd=checkout)
            run([*command, 'check', '--artifacts', output, '--tag', args.tag, '--sha', sha], cwd=checkout)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        message = 'Linux release build failed' if isinstance(error, subprocess.CalledProcessError) else str(error)
        print('error: ' + message, file=sys.stderr)
        if work is not None:
            print('Diagnostics retained: ' + str(work), file=sys.stderr)
        return 2
    print('Prepared Linux release assets: ' + str(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
