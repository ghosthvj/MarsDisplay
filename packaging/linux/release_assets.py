"""Offline Linux artifact format; not a builder or legal qualification gate."""
import argparse
import hashlib
from importlib import util
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile


def _load(name):
    spec = util.spec_from_file_location('linux_format_' + name, Path(__file__).resolve().parents[1] / (name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = _load('payload')
versioning = _load('release_version')
ERROR = 'Invalid Linux artifact format or provenance.'
SUCCESS = 'Linux artifact format validated; legal qualification is separate.'
FAILURES = (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError,
            zipfile.BadZipFile, subprocess.TimeoutExpired)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(ERROR)
    return path


def _identity(version, sha, tag):
    tag = 'v' + version if tag is None else tag
    if versioning.version(tag) != version or not re.fullmatch('[a-f0-9]{40}', sha):
        raise ValueError(ERROR)
    original = versioning.git(Path.cwd(), 'show', sha + ':pyproject.toml')
    return versioning.provenance(original, tag, sha), versioning.render(original, tag)


def _names(version):
    base = f'MarsDisplay-{version}-Linux-x86_64'
    return base + '.AppImage', base + '-support.zip'


def _content(files, stamped):
    payload._validate(files)
    if (files.get('source/pyproject.toml') != stamped or not files.get('README.md')
            or not any(name.startswith('notices/') for name in files)
            or any(name.split('/')[0].casefold() == 'inventory.json' for name in files)):
        raise ValueError(ERROR)


def _sidecar(name, data):
    return (_hash(data) + '  ' + name + '\n').encode('ascii')


def build(image, content, output, tag, sha):
    """Assemble prepared bytes exclusively; never modify inputs or stamp source."""
    try:
        version = versioning.version(tag)
        release, stamped = _identity(version, sha, tag)
        image, content, output = map(_path, (image, content, output))
        if (output.exists() or not output.parent.is_dir() or not content.is_dir()
                or output.resolve().is_relative_to(content.resolve()) or not image.is_file()):
            raise ValueError(ERROR)
        for path in content.rglob('*'):
            _path(path)
            if not (path.is_file() or path.is_dir()):
                raise ValueError(ERROR)
        files = payload.read_tree(content)
        _content(files, stamped)
        image_data = image.read_bytes()
        if not image_data:
            raise ValueError(ERROR)
        image_name, archive_name = _names(version)
        inventory = dict(target='Linux-x86_64', source_commit=sha, release=release,
                         appimage=dict(name=image_name, size=len(image_data), sha256=_hash(image_data)),
                         files={name: _hash(data) for name, data in sorted(files.items())})
        files['inventory.json'] = (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                archive.writestr('MarsDisplay/' + name, data)
        # All semantic checks precede exclusive output creation. I/O failures may
        # leave a partial new output; never remove or overwrite it on a retry.
        output.mkdir()
        for name, data in ((image_name, image_data), (archive_name, buffer.getvalue())):
            for filename, material in ((name, data), (name + '.sha256', _sidecar(name, data))):
                with (output / filename).open('xb') as stream:
                    stream.write(material)
    except FAILURES:
        raise ValueError(ERROR) from None


def assets(folder, version, sha, tag=None):
    """Return Windows-compatible upload metadata after read-only validation.

    Omitting tag derives its canonical spelling from version, never bypassing
    provenance. Original pyproject.toml is read at sha in the current Git repo.
    """
    try:
        release, stamped = _identity(version, sha, tag)
        folder = _path(folder)
        image_name, archive_name = _names(version)
        names = (image_name, image_name + '.sha256', archive_name, archive_name + '.sha256')
        if {p.name for p in folder.iterdir()} != set(names):
            raise ValueError(ERROR)
        data = {}
        for name in names:
            path = _path(folder / name)
            if not path.is_file():
                raise ValueError(ERROR)
            data[name] = path.read_bytes()
        for name in (image_name, archive_name):
            if not data[name] or data[name + '.sha256'] != _sidecar(name, data[name]):
                raise ValueError(ERROR)
        files = {}
        with zipfile.ZipFile(io.BytesIO(data[archive_name])) as archive:
            seen = set()
            for item in archive.infolist():
                name = payload.safe_path(item.filename)
                mode = stat.S_IFMT(item.external_attr >> 16)
                if (not name.startswith('MarsDisplay/') or name.casefold() in seen
                        or mode not in (0, stat.S_IFREG) or item.is_dir()):
                    raise ValueError(ERROR)
                seen.add(name.casefold())
                files[name[len('MarsDisplay/'):]] = archive.read(item)
        # Validate the complete namespace before removing the generated member:
        # inventory.json must never double as a directory, even under case folding.
        payload._validate(files)
        inventory = json.loads(files.pop('inventory.json'))
        _content(files, stamped)
        if (inventory['target'] != 'Linux-x86_64' or inventory['source_commit'] != sha
                or inventory['release'] != release
                or inventory['appimage'] != dict(name=image_name, size=len(data[image_name]), sha256=_hash(data[image_name]))
                or inventory['files'] != {name: _hash(material) for name, material in files.items()}):
            raise ValueError(ERROR)
        return {folder / name: dict(name=name, size=len(data[name]), state='uploaded',
                                    digest='sha256:' + _hash(data[name])) for name in names}
    except FAILURES:
        raise ValueError(ERROR) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    assembler = commands.add_parser('build', help='Package prepared source, notices and README.md; no legal certification.')
    assembler.add_argument('--image', required=True, help='Existing AppImage; read only, not executed.')
    assembler.add_argument('--content', required=True, help='Prepared tree with stamped source/pyproject.toml, notices/ and README.md.')
    assembler.add_argument('--output', required=True, help='New directory outside content, with an existing parent; never overwritten.')
    checker = commands.add_parser('check', help='Read-only format, hash and canonical source provenance validation.')
    checker.add_argument('--artifacts', required=True, help='Directory containing exactly the four versioned assets.')
    for command in (assembler, checker):
        command.add_argument('--tag', required=True, help='Canonical vX.Y.Z or vX.Y.ZrcN; no tag is created.')
        command.add_argument('--sha', required=True, help='Original 40-character lowercase commit SHA in the current Git repository.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            build(args.image, args.content, args.output, args.tag, args.sha)
        else:
            assets(args.artifacts, versioning.version(args.tag), args.sha, args.tag)
        print(SUCCESS)
        return 0
    except FAILURES:
        print('Linux artifact error: ' + ERROR, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
