"""Portable payload file assembly only: no compiler, downloader or product CLI."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile
from urllib.parse import parse_qsl, urlsplit

_PRIVATE = {'.git', '.venv', '.cache', '__pycache__', 'settings.json', 'profile',
            'profiles', 'user data', 'cookies', 'local state', 'credentials', '.config',
            '.ssh', 'id_rsa', 'id_ed25519', 'user settings', 'preferences'}
_ROOT_SOURCE = {'README.md', 'LICENSE', 'pyproject.toml', 'requirements.txt', 'requirements-build.txt'}
_SOURCE_SUFFIXES = {'.py', '.spec', '.toml', '.txt', '.md', '.html', '.json', '.yml', '.yaml'}


def safe_path(name):
    """Reject paths unsafe on Windows or likely to carry private runtime state."""
    parts = name.split('/')
    if (not name or '\\' in name or ':' in name or PurePosixPath(name).is_absolute()
            or any(not p or p in {'.', '..'} or p.endswith((' ', '.'))
                   or any(ord(c) < 32 or c in '<>"|?*' for c in p)
                   or p.lower() in _PRIVATE or p.lower().startswith('.env')
                   or any(word in p.lower() for word in ('cookie', 'token', 'credential'))
                   or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', p, re.I)
                   for p in parts)):
        raise ValueError('Unsafe payload path')
    return name


def _validate(files):
    seen = set()
    for name, data in files.items():
        safe_path(name)
        folded = name.casefold()
        if folded in seen or not isinstance(data, bytes) or not data:
            raise ValueError('Duplicate path or empty/non-byte material')
        seen.add(folded)
    # A file must not also be a directory, including under Windows case folding.
    for name in seen:
        if any('/'.join(name.split('/')[:i]) in seen for i in range(1, len(name.split('/')))):
            raise ValueError('File/directory collision')


def read_tree(root, paths=None):
    """Read a tree or exact relative file selection, rejecting links/private paths."""
    root = Path(root).absolute()
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('Symlink root or parent')
    selected = paths is not None
    names = paths if selected else (path.relative_to(root).as_posix() for path in sorted(root.rglob('*')))
    files = {}
    for name in names:
        safe_path(name)
        path = root / name
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Symlink material or parent')
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Material escapes root')
        if path.is_file():
            files[name] = path.read_bytes()
        elif selected:
            raise ValueError('Missing selected material')
    _validate(files)
    return files


def _source_reference(url, commit=None):
    """Require public HTTPS provenance; permit only Qt's commit-id query."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment
            or (parsed.query and (commit is None or parse_qsl(parsed.query) != [('id', commit)]))
            or (commit is not None and commit not in parsed.path.split('/')
                and parse_qsl(parsed.query) != [('id', commit)])):
        raise ValueError('Missing public commit-pinned source provenance')


def collect_license_material(root):
    """Read only registry-listed legal inputs, verifying bytes and provenance.

    Returns (registry, files). Empty package mappings remain supplementary source
    material, never evidence of native binary coverage. No network I/O occurs.
    """
    files = read_tree(root, ('provenance.json', 'README.md'))
    registry = json.loads(files['provenance.json'])
    if (registry.get('schema_version') != 1 or not registry.get('qualification')
            or not isinstance(registry.get('materials'), list) or not registry['materials']
            or set(registry) - {'schema_version', 'qualification', 'materials', 'source_archives'}):
        raise ValueError('Unsupported legal material registry')
    declared = dict.fromkeys(files, b'validation')
    required = {'path', 'sha256', 'source_url', 'source_commit', 'upstream_version', 'packages', 'coverage'}
    for record in registry['materials']:
        if (not required <= record.keys() or set(record) - required - {'source_file_sha256', 'source_excerpt'}
                or not record['upstream_version'] or not record['coverage']
                or not re.fullmatch('[a-f0-9]{64}', record['sha256'])
                or not re.fullmatch('[a-f0-9]{40}', record['source_commit'])
                or not isinstance(record['packages'], list)):
            raise ValueError('Incomplete legal material provenance')
        for package in record['packages']:
            if (set(package) != {'name', 'version'} or not package['version']
                    or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]*', package['name'])):
                raise ValueError('Invalid exact package/version mapping')
        if 'source_file_sha256' in record and not re.fullmatch('[a-f0-9]{64}', record['source_file_sha256']):
            raise ValueError('Invalid source excerpt provenance')
        _source_reference(record['source_url'], record['source_commit'])
        if record['path'] in declared:
            raise ValueError('Duplicate legal material path')
        declared[record['path']] = b'validation'
    _validate(declared)
    for archive in registry.get('source_archives', []):
        if (set(archive) != {'component', 'version', 'url', 'sha256'} or not archive['component']
                or not archive['version'] or not re.fullmatch('[a-f0-9]{64}', archive['sha256'])):
            raise ValueError('Invalid source archive provenance')
        _source_reference(archive['url'])
    files.update(read_tree(root, (item['path'] for item in registry['materials'])))
    for record in registry['materials']:
        if hashlib.sha256(files[record['path']]).hexdigest() != record['sha256']:
            raise ValueError('Legal material SHA256 mismatch')
    return registry, files


def collect_source(root):
    """Explicit build/test source allowlist; never archive a whole workspace."""
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Symlink source root')
    files = {}
    for directory in ('src', 'packaging', 'tests'):
        base = root / directory
        if base.is_symlink():
            raise ValueError('Symlink source directory')
        for path in sorted(base.rglob('*')):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ValueError('Symlink source material')
            try:
                safe_path(relative)
            except ValueError:
                continue
            if path.is_file() and path.suffix in _SOURCE_SUFFIXES:
                files[relative] = path.read_bytes()
    for name in sorted(_ROOT_SOURCE | {'.gitattributes'}):
        path = root / name
        if path.is_symlink():
            raise ValueError('Symlink source material')
        if path.is_file():
            files.update(read_tree(root, (name,)))
    legal = root / 'third_party/license-material'
    if legal.exists() or legal.is_symlink():
        _, material = collect_license_material(legal)
        files.update({'third_party/license-material/' + name: data for name, data in material.items()})
    native = root / 'third_party/native-material'
    if native.exists() or native.is_symlink():
        # Lazy standalone load avoids import recursion; never archive third_party wholesale.
        from importlib import util
        spec = util.spec_from_file_location('marsdisplay_source_material', Path(__file__).with_name('native_material.py'))
        reader = util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        material = reader.read_inputs(root)['files']
        files.update({'third_party/native-material/' + name: data for name, data in material.items()})
    if (root / 'src/mars_display/usb_worker.py').is_file():
        # Only the known P3 rebuild/test assets, never tools/ or a workspace glob.
        fixtures = ['tools/windows-usb-probe/' + name for name in
                    ('pattern.png', 'pattern.rgb565', 'pattern.rgb888', 'pattern.json',
                     'rgb888-provenance.json')]
        files.update(read_tree(root, (*fixtures, 'docs/usb-helper.md', 'docs/usb-runtime.md')))
    for name in ('.github/workflows/windows-portable.yml', '.github/workflows/release.yml', 'docs/releases.md'):
        if (root / name).exists() or (root / name).is_symlink():
            files.update(read_tree(root, (name,)))
    _validate(files)
    return files


def browser_executable(runtime, name, revision):
    """Resolve only pinned known Windows registry paths, never an arbitrary EXE."""
    if not re.fullmatch('[0-9]+', revision):
        raise ValueError('Missing exact bundled browser revision')
    prefix = '_internal/playwright/driver/package/.local-browsers/' + name.replace('-', '_') + '-' + revision + '/'
    executables = {'chromium-headless-shell': ('chrome-headless-shell-win64/chrome-headless-shell.exe',
                                             'chrome-headless-shell-win64/headless_shell.exe'),
                   'ffmpeg': ('ffmpeg-win64.exe',),
                   'winldd': ('PrintDeps.exe',)}[name]
    for executable in executables:
        if prefix + executable in runtime:
            return prefix + executable
    raise ValueError('Browser inventory does not match required Windows executable')


def _layout(runtime):
    required = ('MarsDisplay.exe', '_internal/playwright/driver/node.exe',
                '_internal/playwright/driver/package/browsers.json')
    if any(name not in runtime for name in required):
        raise ValueError('Missing executable, Qt platform or Playwright driver material')
    if not any(name in runtime for name in ('_internal/PySide6/plugins/platforms/qwindows.dll',
                                            '_internal/PySide6/Qt/plugins/platforms/qwindows.dll')):
        raise ValueError('Missing Qt Windows platform resource')
    if not any(re.fullmatch(r'_internal/playwright/driver/package/\.local-browsers/chromium_headless_shell-[0-9]+/chrome-headless-shell-win64/(?:chrome-headless-shell|headless_shell)\.exe', name) for name in runtime):
        raise ValueError('Missing bundled Windows Chromium headless shell')
    if not any(re.fullmatch(r'_internal/playwright/driver/package/\.local-browsers/ffmpeg-[0-9]+/ffmpeg-win64.exe', name) for name in runtime):
        raise ValueError('Missing bundled Windows FFmpeg')


def assemble(output, version, runtime, source, notices, inventory):
    """Validate bytes first; publish a folder, versioned ZIP and SHA256 exclusively.

    Caller supplies actual native build output and installed metadata/material.
    This validates layout, NOT executable functionality or legal completeness.
    Returns (folder, zip, checksum) Paths. Existing outputs are never replaced.
    Native builder should use repository dist/build; tests use system temp roots.
    """
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*(?:[-a-zA-Z0-9.]*)', version):
        raise ValueError('Invalid artifact version')
    for files in (runtime, source, notices):
        _validate(files)
    _layout(runtime)
    if (not _ROOT_SOURCE <= source.keys() or not notices
            or any(not any(name.startswith(prefix + '/') and name.endswith('.py') for name in source)
                   for prefix in ('src', 'packaging', 'tests'))
            or not re.fullmatch('[a-fA-F0-9]{40}', inventory.get('source_commit', ''))
            or inventory.get('target') != 'Windows-x64'
            or any(not inventory.get(key) for key in ('build', 'dependencies', 'browsers'))):
        raise ValueError('Missing corresponding source, notices, commit or exact inventory')
    if any(not inventory['build'].get(key) for key in ('Python', 'PyInstaller', 'Node')):
        raise ValueError('Missing exact build/runtime tool versions')
    if any(not item.get('name') or not item.get('version') or not item.get('sources')
           for item in inventory['dependencies']):
        raise ValueError('Missing dependency version/source inventory')
    optional_winldd = ('winldd',) if any(item.get('name') == 'winldd' for item in inventory['browsers']) else ()
    for name in ('chromium-headless-shell', 'ffmpeg') + optional_winldd:
        matches = [item for item in inventory['browsers'] if item.get('name') == name]
        if len(matches) != 1 or not re.fullmatch('[0-9]+', matches[0].get('revision', '')):
            raise ValueError('Missing exact bundled browser revision')
        browser_executable(runtime, name, matches[0]['revision'])
    files = dict(runtime)
    additions = {'LICENSE': source['LICENSE']}
    additions.update({'source/' + k: v for k, v in source.items()})
    additions.update({'notices/' + k: v for k, v in notices.items()})
    if set(files) & set(additions):
        raise ValueError('Reserved payload path')
    files.update(additions)
    _validate(files)
    if 'inventory.json' in files:
        raise ValueError('Reserved inventory path')
    inventory = dict(inventory, files={name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())})
    files['inventory.json'] = (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode()
    _validate(files)
    output = Path(output)
    folder = output / 'MarsDisplay'
    archive = output / f'MarsDisplay-{version}-Windows-x64.zip'
    checksum = archive.with_suffix('.zip.sha256')
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Symlink output directory')
    if any(p.exists() or p.is_symlink() for p in (folder, archive, checksum)):
        raise FileExistsError('Portable output already exists')
    output.mkdir(parents=True, exist_ok=True)
    published = []
    with tempfile.TemporaryDirectory(prefix='.marsdisplay-payload-', dir=output) as scratch:
        staging = Path(scratch)
        staged_zip = staging / archive.name
        with zipfile.ZipFile(staged_zip, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for name, data in sorted(files.items()):
                zipped.writestr('MarsDisplay/' + name, data)
        digest = hashlib.sha256(staged_zip.read_bytes()).hexdigest()
        staged_checksum = staging / checksum.name
        staged_checksum.write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
        # Publish with exclusive creation; never replace a competing writer.
        # Hard links need a same-filesystem scratch directory for ZIP/sidecar.
        with tempfile.TemporaryDirectory(prefix='.marsdisplay-', dir=output) as local:
            try:
                for staged, destination in ((staged_zip, archive), (staged_checksum, checksum)):
                    local_file = Path(local) / destination.name
                    local_file.write_bytes(staged.read_bytes())
                    os.link(local_file, destination)
                    published.append(destination)
                folder.mkdir()
                published.append(folder)
                for name, data in files.items():
                    path = folder / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('xb') as stream:
                        stream.write(data)
            except BaseException:
                # Roll back only paths created by this invocation, never prior bytes.
                import shutil
                for path in reversed(published):
                    if path == folder:
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                raise
    return folder, archive, checksum
