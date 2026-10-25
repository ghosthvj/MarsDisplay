"""Build-only project version stamping with explicit canonical-source provenance."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

STAMP = Path('build/release-version.json')
PROVENANCE_ERROR = 'Build version provenance does not match source.'
STAMP_ERROR = 'Version stamping requires an unchanged project file and no existing stamp.'


def version(tag):
    number = r'(?:0|[1-9][0-9]*)'
    if not isinstance(tag, str) or len(tag) > 64 or not re.fullmatch(rf'v{number}\.{number}\.{number}(?:rc{number})?', tag):
        raise ValueError('Use a canonical vX.Y.Z or vX.Y.ZrcN tag.')
    return tag[1:]


def render(original, tag):
    """Replace only the scalar in [project].version, preserving other bytes."""
    selected = version(tag)
    text = original.decode('utf-8')
    before = tomllib.loads(text)
    section = re.search(r'(?m)^\[project\][ \t]*\r?\n', text)
    if section is None:
        raise ValueError('Unsupported project version layout.')
    start = section.end()
    end = re.search(r'(?m)^\[', text[start:])
    stop = start + end.start() if end else len(text)
    body, count = re.subn(r'''(?m)^(version[ \t]*=[ \t]*)(["'])([^"'\r\n]*)\2''',
                         lambda match: match[1] + json.dumps(selected), text[start:stop])
    result = text[:start] + body + text[stop:]
    expected = copy.deepcopy(before)
    expected['project']['version'] = selected
    if count != 1 or tomllib.loads(result) != expected:
        raise ValueError('Unsupported project version layout.')
    return result.encode('utf-8')


def provenance(original, tag, sha):
    if not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError(PROVENANCE_ERROR)
    stamped = render(original, tag)
    return dict(schema=1, method='project-version-v1', tag=tag, version=version(tag),
                source_commit=sha, source_version=tomllib.loads(original.decode('utf-8'))['project']['version'],
                source_pyproject_sha256=hashlib.sha256(original).hexdigest(),
                build_pyproject_sha256=hashlib.sha256(stamped).hexdigest())


def git(repo, *args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, timeout=10)
    if result.returncode:
        raise ValueError('Cannot read source revision.')
    return result.stdout


def prepare(repo, tag):
    version(tag)  # Reject untrusted input before even reading Git.
    project, stamp = repo / 'pyproject.toml', repo / STAMP
    if project.is_symlink() or stamp.exists() or stamp.is_symlink() or stamp.parent.is_symlink():
        raise ValueError(STAMP_ERROR)
    sha = git(repo, 'rev-parse', 'HEAD').decode('ascii').strip()
    original = git(repo, 'show', 'HEAD:pyproject.toml')
    if project.read_bytes().replace(b'\r\n', b'\n') != original.replace(b'\r\n', b'\n'):
        raise ValueError(STAMP_ERROR)
    record = provenance(original, tag, sha)
    stamped = render(original, tag)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive marker creation prevents overwriting an earlier stamp. Any I/O
    # failure is terminal; a partial state cannot pass inspect(), never retried.
    with stamp.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
    project.write_bytes(stamped)
    return record


def inspect(repo, sha, installed_version=None):
    stamp = repo / STAMP
    if not stamp.exists() and not stamp.is_symlink():
        return None  # Legacy/default builds do not read extra Git data.
    if stamp.is_symlink() or stamp.parent.is_symlink() or (repo / 'pyproject.toml').is_symlink():
        raise ValueError(PROVENANCE_ERROR)
    record = json.loads(stamp.read_text(encoding='utf-8'))
    original = git(repo, 'show', 'HEAD:pyproject.toml')
    if (not isinstance(record, dict) or 'tag' not in record
            or record != provenance(original, record['tag'], sha)
            or (repo / 'pyproject.toml').read_bytes() != render(original, record['tag'])
            or (installed_version is not None and installed_version() != record['version'])):
        raise ValueError(PROVENANCE_ERROR)
    return record
