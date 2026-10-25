"""Manual release boundary: validate locally, stage assets, then publish once."""
import argparse
import hashlib
from importlib import util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tomllib
import zipfile

_spec = util.spec_from_file_location('release_payload', Path(__file__).with_name('payload.py'))
payload = util.module_from_spec(_spec)
_spec.loader.exec_module(payload)
ASSET_ERROR = 'Release assets do not match the qualified version and commit.'
REMOTE_ERROR = 'GitHub release or tag readback did not match; inspect GitHub before rerunning.'


def plan():
    env = os.environ
    sha, repo = env.get('GITHUB_SHA', ''), env.get('GITHUB_REPOSITORY', '')
    if (env.get('GITHUB_EVENT_NAME') != 'workflow_dispatch' or env.get('GITHUB_REF') != 'refs/heads/main'
            or not re.fullmatch('[a-f0-9]{40}', sha)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repo)):
        raise ValueError('A manual main run with an exact commit and repository is required.')
    version = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if not isinstance(version, str) or len(version) > 64 or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:rc[0-9]+)?', version):
        raise ValueError('Use a numeric X.Y.Z or X.Y.ZrcN project version.')
    return version, sha, repo


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assets(folder, version, sha):
    """Bind the same-run qualified build to the exact caller, without extraction."""
    folder = Path(folder).absolute()
    archive = folder / f'MarsDisplay-{version}-Windows-x64.zip'
    checksum = archive.with_suffix('.zip.sha256')
    try:
        if any(p.is_symlink() for p in (folder, *folder.parents)) or set(folder.iterdir()) != {archive, checksum}:
            raise ValueError()
        if any(p.is_symlink() or not p.is_file() for p in (archive, checksum)):
            raise ValueError()
        archive_hash = digest(archive)
        if checksum.read_text(encoding='utf-8').split() != [archive_hash, archive.name]:
            raise ValueError()
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if len(names) != len(set(n.casefold() for n in names)):
                raise ValueError()
            for item in z.infolist():
                payload.safe_path(item.filename)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError()
            inventory = json.loads(z.read('MarsDisplay/inventory.json'))
            if inventory['source_commit'] != sha or inventory['target'] != 'Windows-x64':
                raise ValueError()
            files = inventory['files']
            if 'MarsDisplay.exe' not in files or set(names) != {'MarsDisplay/' + n for n in files} | {'MarsDisplay/inventory.json'}:
                raise ValueError()
            project = tomllib.loads(z.read('MarsDisplay/source/pyproject.toml').decode('utf-8'))
            if project['project']['version'] != version:
                raise ValueError()
            for name, expected in files.items():
                with z.open('MarsDisplay/' + name) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                        raise ValueError()
        return {p: {'name': p.name, 'size': p.stat().st_size, 'state': 'uploaded',
                    'digest': 'sha256:' + digest(p)} for p in (archive, checksum)}
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
        raise ValueError(ASSET_ERROR) from None


def gh(*args, data=None):
    result = subprocess.run(['gh', *args], input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True, timeout=300)
    if result.returncode:
        raise ValueError('GitHub operation failed: ' + result.stderr.strip())
    return result.stdout


def api(path, data=None, method='POST'):
    args = ('--method', method, '--input', '-') if data is not None else ()
    return json.loads(gh('api', path, *args, data=data))


def check_release(record, release_id, tag, prerelease, expected, *, draft):
    # target_commitish is metadata, not the resolved commit of an existing tag.
    if (record.get('id') != release_id or record.get('tag_name') != tag
            or record.get('draft') is not draft
            or record.get('prerelease') is not prerelease):
        raise ValueError(REMOTE_ERROR)
    actual = record.get('assets', [])
    if len(actual) != len(expected) or {a['name'] for a in actual} != {a['name'] for a in expected.values()}:
        raise ValueError(REMOTE_ERROR)
    for wanted in expected.values():
        found = next(a for a in actual if a['name'] == wanted['name'])
        if any(found.get(key) != value for key, value in wanted.items()):
            raise ValueError(REMOTE_ERROR)


def publish(folder, version, sha, repo):
    expected = assets(folder, version, sha)  # No remote mutation until local checks pass.
    tag, prerelease = 'v' + version, 'rc' in version
    prefix = 'repos/' + repo
    # Exclusive create rejects existing tags, including leftovers from a failed run.
    api(prefix + '/git/refs', {'ref': 'refs/tags/' + tag, 'sha': sha})
    created = api(prefix + '/releases', dict(tag_name=tag, target_commitish=sha,
                  name='MarsDisplay ' + version, draft=True, prerelease=prerelease, generate_release_notes=True))
    release_id = created['id']
    if type(release_id) is not int or release_id <= 0:
        raise ValueError(REMOTE_ERROR)
    endpoint = prefix + '/releases/' + str(release_id)
    # Bind uploads to this newly created draft, never a mutable tag lookup.
    for path in expected:
        gh('api', f'https://uploads.github.com/{prefix}/releases/{release_id}/assets?name={path.name}',
           '--method', 'POST', '--input', str(path), '-H', 'Content-Type: application/octet-stream')
    check_release(api(endpoint), release_id, tag, prerelease, expected, draft=True)
    ref = api(prefix + '/git/ref/tags/' + tag)['object']
    if ref.get('type') != 'commit' or ref.get('sha') != sha:
        raise ValueError(REMOTE_ERROR)
    api(endpoint, {'draft': False}, method='PATCH')
    check_release(api(endpoint), release_id, tag, prerelease, expected, draft=False)
    print(f'Published https://github.com/{repo}/releases/tag/{tag}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'publish'))
    parser.add_argument('--artifacts', default='release-assets', help='Directory containing only the qualified ZIP and SHA256 sidecar.')
    args = parser.parse_args(argv)
    try:
        version, sha, repo = plan()
        if args.command == 'plan':
            print(f'Release plan: v{version} ({"prerelease" if "rc" in version else "stable"})')
        else:
            publish(args.artifacts, version, sha, repo)
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print('Release error: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
