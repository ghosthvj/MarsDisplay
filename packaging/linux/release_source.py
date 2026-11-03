"""Linux source-map extension; the caller supplies a clean stamped Git checkout."""
import importlib.util
import json
from pathlib import Path
import subprocess


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
payload = _load('linux_source_payload', HERE.parent / 'payload.py')
inputs = _load('linux_source_inputs', HERE / 'fetch_inputs.py')
RECIPE = tuple('packaging/linux/' + name for name in (
    'AppRun', 'Dockerfile', 'MarsDisplay.desktop', 'marsdisplay.svg',
    'MarsDisplay.spec', 'Release.spec', 'appimage-tools.json',
    'attribution.py', 'build_appimage.py', 'build_evidence.py', 'entrypoint.py',
    'fetch_inputs.py', 'release_assets.py', 'runtime-inputs.json', 'smoke.py',
    'toolchain.json', 'usb_bootstrap.py',
))
OPTIONAL = tuple('docs/' + name + '.md' for name in (
    'linux-prototype', 'linux-usb-measurement', 'linux-attribution',
    'linux-usb-measurement-results', 'linux-appimage', 'linux-runtime-inputs',
    'linux-build-evidence', 'linux-distribution', 'linux-usb-runtime',
    'linux-release-source', 'linux-release-assembly', 'linux-release-build', 'linux-sdk-transport',
)) + ('.github/workflows/linux-appimage.yml',)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate runtime registry key')
        result[key] = value
    return result


def collect_source(root):
    """Return repository-relative bytes, without writes, downloads or Git proof.

    Git's index selects tracked paths; bytes come from the working tree so the
    canonical release stamp is retained. This does not verify clean/revision/tag
    provenance, which belongs to the integrating host build.
    """
    root = Path(root).absolute()
    payload.read_tree(root, ())  # Reject linked roots/parents before consulting Git.
    try:
        top = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                             check=True, capture_output=True).stdout.decode().strip()
        if Path(top).resolve() != root.resolve():
            raise ValueError('Source root must be the Git checkout root')
        listing = subprocess.run(['git', '-C', str(root), 'ls-files', '--stage', '-z'],
                                 check=True, capture_output=True).stdout
        tracked = {}
        for entry in listing.split(b'\0'):
            if not entry:
                continue
            metadata, name = entry.decode('utf-8').split('\t', 1)
            mode, _, stage = metadata.split()
            if stage != '0' or name in tracked:
                raise ValueError('Unmerged source index')
            tracked[name] = mode
    except (OSError, subprocess.CalledProcessError, UnicodeError) as error:
        raise ValueError('Source requires a readable Git checkout') from error

    def selected(names):
        names = tuple(names)
        if any(tracked.get(name) not in {'100644', '100755'} for name in names):
            raise ValueError('Required source material must be tracked regular files')
        return payload.read_tree(root, names)

    files = selected(RECIPE)
    try:
        registry = json.loads(files['packaging/linux/runtime-inputs.json'], object_pairs_hook=_unique)
        retained, archives = registry['retained'], registry['downloads']
        if (not isinstance(retained, dict) or set(retained) != inputs.RETAINED
                or not all(inputs.valid_hash(h) for h in retained.values())
                or not isinstance(archives, list) or len(archives) != len(inputs.ARCHIVES)
                or {a['name'] for a in archives} != inputs.ARCHIVES
                or not all(inputs.valid_hash(a['sha256']) for a in archives)):
            raise ValueError('Invalid runtime registry')
        for archive in archives:
            inputs.safe_url(archive['url'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid runtime registry') from error
    runtime = selected('third_party/linux-runtime/' + name for name in retained)
    for name, digest in retained.items():
        inputs.checked(runtime['third_party/linux-runtime/' + name], digest, name)
    files.update(runtime)
    files.update(selected(name for name in OPTIONAL if name in tracked))
    # Preserve the shared collector's selection and validation, but never export
    # its untracked workspace neighbors. No shared suffix policy is broadened.
    base = payload.collect_source(root)
    files.update(selected(name for name in base if name in tracked))
    payload._validate(files)
    return files
