"""Acquire Linux native associations and source/legal inputs; not legal approval."""
import argparse
import ast
import base64
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import tomllib
from types import SimpleNamespace
from urllib.parse import quote

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_spec = util.spec_from_file_location('linux_association', Path(__file__).with_name('attribution.py'))
attribution = util.module_from_spec(_spec)
_spec.loader.exec_module(attribution)


def toc_entries(path):
    try:
        tree = ast.literal_eval(path.read_text(encoding='utf-8'))
    except (SyntaxError, ValueError):
        raise ValueError('invalid COLLECT TOC') from None
    entries = {}

    def visit(value):
        if not isinstance(value, (tuple, list)):
            return
        if len(value) == 3 and all(isinstance(item, str) for item in value):
            destination, original, kind = value
            if kind in {'BINARY', 'EXTENSION', 'DATA'}:
                attribution.material.safe_path(destination)
                if not Path(original).is_absolute():
                    raise ValueError('TOC original must be absolute')
                entries.setdefault(destination, set()).add(Path(original))
        else:
            for child in value:
                visit(child)
    visit(tree)
    if not entries:
        raise ValueError('COLLECT TOC contains no file entries')
    return entries


def wheel_index(originals, distributions=None):
    """Match installed RECORD paths before checking their recorded hash and size."""
    result = {path: [] for path in originals}
    for dist in metadata.distributions() if distributions is None else distributions:
        for entry in dist.files or ():
            path = Path(dist.locate_file(entry)).resolve()
            if path not in originals:
                continue
            attribution.material.safe_path(str(entry))
            data = originals[path]
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
            if (entry.hash is None or entry.hash.mode != 'sha256'
                    or entry.hash.value != expected or entry.size != len(data)):
                raise ValueError('invalid wheel RECORD: ' + path.name)
            name, version = dist.metadata.get('Name'), dist.metadata.get('Version')
            if not attribution.text(name) or not attribution.text(version):
                raise ValueError('missing wheel identity')
            result[path].append(dict(name=name, version=version, record=str(entry)))
    return result


QUALIFICATION = ('Measured installed-file associations and retained version-specific source/legal '
                 'inputs; not binary build attestations or legal approval')


def sdk_context():
    def run(args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode and not (args[:2] == ['dpkg-query', '--search'] and result.returncode == 1):
            raise ValueError('SDK command failed: ' + args[0])
        return result.stdout
    return SimpleNamespace(root=Path('/'), prefix=Path(sys.base_prefix).resolve(),
                           python_version=platform.python_version(), run=run,
                           distributions=list(metadata.distributions()), lookup=metadata.distribution)


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def owner(kind, name, version, source_name, source_version, reference, licenses, evidence):
    for value in (name, version, source_name, source_version):
        if not attribution.text(value):
            raise ValueError('missing owner/source identity')
    attribution.material._source_reference(reference)
    if not licenses or not evidence:
        raise ValueError('missing legal or ownership material')
    return dict(kind=kind, name=name, version=version,
                source=dict(name=source_name, version=source_version, reference=reference),
                licenses=sorted(set(licenses)), evidence=sorted(set(evidence)))


class Inputs:
    """Acquire facts from installed SDK interfaces, never from caller owner records."""
    def __init__(self, project, sdk):
        self.project, self.sdk = project, sdk
        self.materials, self.python, self.vendor = {}, [], []
        self.shipped_browsers = set()
        self.references = set()
        self.driver = None
        self.python_owner = None
        self.qt_bundle = None

    def put(self, name, data):
        attribution.material._validate({name: data})
        if name in self.materials and self.materials[name] != data:
            raise ValueError('conflicting acquired material: ' + name)
        self.materials[name] = data
        return name

    def distributions(self, roots):
        inventory, texts = attribution.notices.collect_distributions(
            roots, lookup=self.sdk.lookup,
            material_root=self.project / 'third_party/license-material')
        for name, data in texts.items():
            self.put(name, data)
        by_name = {canonicalize_name(item['name']): item for item in self.python}
        by_name.update({canonicalize_name(item['name']): item for item in inventory})
        self.python = list(by_name.values())
        return by_name

    def package(self, original, data):
        relative = original.relative_to(self.sdk.root).as_posix()
        paths = {'/' + relative}
        # Noble's merged-/usr installations can retain pre-merge dpkg paths.
        if relative.startswith(('usr/lib/', 'usr/lib64/', 'usr/bin/', 'usr/sbin/')):
            paths.add('/' + relative[4:])
        matches = set()
        for path in sorted(paths):
            for line in self.sdk.run(['dpkg-query', '--search', path]).splitlines():
                package, separator, registered = line.rpartition(': ')
                if separator and registered in paths:
                    matches.update(package.split(', '))
        if len(matches) != 1:
            raise ValueError('acquire exactly one installed package owner')
        package = matches.pop()
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9-]+)?', package):
            raise ValueError('invalid package identity')
        fields = self.sdk.run(['dpkg-query', '--show',
                              '--showformat=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\t${db:Status-Status}\n',
                              package]).strip('\n').split('\t')
        if len(fields) != 5 or fields[0] != package:
            raise ValueError('package query identity mismatch')
        _, version, source, source_version, status = fields
        if status != 'installed' or not all((version, source, source_version)):
            raise ValueError('missing installed package source identity')
        info = self.sdk.root / 'var/lib/dpkg/info'
        candidates = [info / (package + '.md5sums')]
        if ':' in package:
            candidates.append(info / (package.split(':')[0] + '.md5sums'))
        sums = next((path for path in candidates if path.is_file()), None)
        if sums is None:
            raise ValueError('missing package md5sums')
        hashes = []
        for line in sums.read_text().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and '/' + parts[1].lstrip('./') in paths:
                hashes.append(parts[0])
        if hashes != [hashlib.md5(data).hexdigest()]:
            raise ValueError('package content hash mismatch')
        copyright_path = self.sdk.root / 'usr/share/doc' / package.split(':')[0] / 'copyright'
        target = copyright_path.resolve()
        if (not target.is_relative_to(self.sdk.root / 'usr/share/doc')
                or not target.is_file() or not target.stat().st_size):
            raise ValueError('missing package copyright')
        key = 'packages/' + package.replace(':', '_')
        text = target.read_bytes()
        licenses = [self.put(key + '/copyright', text)]
        for common in sorted(set(re.findall(rb'/usr/share/common-licenses/([A-Za-z0-9.+-]+)', text))):
            name = common.decode().rstrip('.')
            path = self.sdk.root / 'usr/share/common-licenses' / name
            licenses.append(self.put('common-licenses/' + name, path.read_bytes()))
        evidence = self.put(key + '/' + hashlib.sha256(data).hexdigest() + '.json', json_bytes(dict(
            package=package, version=version, source=source, source_version=source_version,
            package_file=relative, md5=hashes[0], sha256=hashlib.sha256(data).hexdigest())))
        reference = 'https://launchpad.net/ubuntu/+source/' + quote(source, safe='') + '/' + quote(source_version, safe='')
        return owner('package', package, version, source, source_version, reference, licenses, [evidence])

    def cpython(self):
        if self.python_owner is not None:
            return self.python_owner
        pin = json.loads((self.project / 'packaging/linux/toolchain.json').read_text())['python']
        if self.sdk.python_version != pin['version']:
            raise ValueError('CPython SDK version differs from toolchain pin')
        archive = self.sdk.prefix.parent / 'Python.tar.xz'
        if attribution.digest(archive) != pin['sha256']:
            raise ValueError('CPython source archive hash mismatch')
        with tarfile.open(archive, 'r:xz') as stream:
            member = stream.getmember('Python-' + pin['version'] + '/LICENSE')
            if not member.isfile():
                raise ValueError('CPython license must be a regular archive member')
            license_data = stream.extractfile(member).read()
        license_path = self.put('cpython/LICENSE', license_data)
        evidence = self.put('cpython/source.json', json_bytes(pin))
        self.python_owner = owner('cpython', 'CPython', pin['version'], 'CPython', pin['version'],
                                  pin['url'], [license_path], [evidence])
        return self.python_owner

    def vendor_inputs(self):
        if self.driver is not None:
            return
        dist = self.sdk.lookup('playwright')
        driver = Path(dist.locate_file('playwright/driver')).resolve()
        selected = {driver / name: (driver / name).read_bytes()
                    for name in ('node', 'package/package.json', 'package/browsers.json')}
        matches = wheel_index(selected, self.sdk.distributions)
        if any(len(items) != 1 or canonicalize_name(items[0]['name']) != 'playwright'
               for items in matches.values()):
            raise ValueError('vendor identity lacks exact Playwright RECORD origin')
        core = json.loads(selected[driver / 'package/package.json'])
        notices = attribution.notices
        if (core.get('name') != 'playwright-core' or core.get('version') != notices._WINLDD_CORE
                or core.get('gitHead', notices._WINLDD_COMMIT) != notices._WINLDD_COMMIT):
            raise ValueError('unmapped Playwright core source identity')
        inventory, texts = notices.collect_vendor(driver, material_root=self.project / 'third_party/license-material')
        for name, data in texts.items():
            self.put(name, data)
        self.distributions(['playwright'])
        self.put('vendor/core-source.json', json_bytes(dict(
            version=core['version'], source_commit=notices._WINLDD_COMMIT,
            reference='https://github.com/microsoft/playwright/archive/' + notices._WINLDD_COMMIT + '.tar.gz')))
        self.references.add('https://github.com/microsoft/playwright/archive/' + notices._WINLDD_COMMIT + '.tar.gz')
        self.vendor, self.driver = inventory, driver

    def vendor_owner(self, original):
        self.vendor_inputs()
        if original == self.driver / 'node':
            version = self.sdk.run([str(original), '--version']).strip()
            if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
                raise ValueError('missing Node runtime version')
            evidence = self.put('vendor/node.json', json_bytes(dict(
                version=version, sha256=attribution.digest(original),
                wheel_records=wheel_index({original: original.read_bytes()}, self.sdk.distributions)[original])))
            return owner('vendor', 'Node.js', version[1:], 'Node.js', version[1:],
                         'https://nodejs.org/dist/' + version + '/node-' + version + '.tar.xz',
                         ['vendor/LICENSE'], [evidence, 'vendor/core-source.json'])
        for item in self.vendor:
            directory = self.driver / 'package/.local-browsers' / (item['name'].replace('-', '_') + '-' + item['revision'])
            if not original.is_relative_to(directory):
                continue
            if item['name'] not in {'chromium', 'chromium-headless-shell'}:
                raise ValueError('unsupported shipped browser source: ' + item['name'])
            version = item.get('browser_version')
            if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version):
                raise ValueError('missing Chromium source version')
            self.shipped_browsers.add(item['name'])
            return owner('vendor', item['name'], item['revision'], 'Chromium', version,
                         'https://chromium.googlesource.com/chromium/src/+/refs/tags/' + version,
                         item['licenses'], [item['registry'], 'vendor/core-source.json'])
        raise ValueError('original is outside registered vendor installations')

    def wheel(self, record):
        name, version = canonicalize_name(record['name']), record['version']
        qt_family = name in {'pyside6', 'pyside6-essentials', 'pyside6-addons',
                             'pyside6-webengine', 'pyside6-pdf', 'shiboken6'}
        if name == 'pillow':
            reference = 'https://github.com/python-pillow/Pillow/archive/refs/tags/' + version + '.tar.gz'
        elif name == 'greenlet':
            reference = 'https://github.com/python-greenlet/greenlet/archive/refs/tags/' + version + '.tar.gz'
        elif qt_family:
            if self.qt_bundle is None:
                spec = util.spec_from_file_location('linux_source_material', Path(__file__).parents[1] / 'native_material.py')
                module = util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.qt_bundle = module.read_inputs(self.project)
            bundle = self.qt_bundle
            modules = bundle['registry']['modules']
            registry, legal = attribution.material.collect_license_material(
                self.project / 'third_party/license-material')
            if not any(canonicalize_name(package['name']) == name and package['version'] == version
                       and entry['upstream_version'] == modules['pyside']['release']
                       for entry in registry['materials'] for package in entry['packages']):
                raise ValueError('unmapped Qt for Python release')
            for path, data in legal.items():
                self.put('upstream/' + path, data)
            self.references.update(item['url'] for item in registry.get('source_archives', [])
                                   if item['component'] == 'QtForPython'
                                   and item['version'] == modules['pyside']['release'])
            for path, data in bundle['files'].items():
                self.put('native-source/' + path, data)
            self.references.update(item['source_archive'] for item in modules.values())
            qt_version = modules['qtbase']['release']
            # Full release route covers modules beyond the reviewed Windows subset;
            # this does not apply the PE byte policy to Linux ELF files.
            self.references.add('https://download.qt.io/official_releases/qt/' + '.'.join(qt_version.split('.')[:2])
                                + '/' + qt_version + '/single/qt-everywhere-src-' + qt_version + '.tar.xz')
            reference = modules['pyside']['source_archive']
        else:
            raise ValueError('missing versioned wheel source: ' + name)
        inventory = self.distributions([name])
        item = inventory[name]
        if item['version'] != version:
            raise ValueError('wheel notice version differs from RECORD owner')
        licenses = list(item['licenses'])
        if qt_family:
            licenses.extend('native-source/' + item['path'] for item in bundle['registry']['files']
                            if item['kind'] in {'license', 'license-notice', 'attribution'})
        evidence = self.put('wheel-records/' + hashlib.sha256(json_bytes(record)).hexdigest() + '.json', json_bytes(record))
        return owner('wheel', record['name'], version, record['name'], version, reference, licenses, [evidence])

    def resolve(self, original, data, wheels):
        if 'playwright' in original.parts and 'driver' in original.parts:
            return self.vendor_owner(original)
        if wheels:
            return self.wheel(wheels[0])
        minor = '.'.join(self.sdk.python_version.split('.')[:2])
        library = self.sdk.prefix / ('lib/libpython' + minor + '.so.1.0')
        extensions = self.sdk.prefix / ('lib/python' + minor + '/lib-dynload')
        if original == library or (original.parent == extensions and original.suffix == '.so'):
            return self.cpython()
        return self.package(original, data)


def acquire(payload, toc, project, output):
    output = output.absolute()
    attribution.no_links(output)
    if output.exists():
        raise ValueError('output must not exist')
    if not output.parent.is_dir():
        raise ValueError('output parent must exist')
    payload, project, toc = payload.resolve(), project.resolve(), toc.resolve()
    if not payload.is_dir() or not project.is_dir() or not toc.is_file():
        raise ValueError('missing payload, project or TOC')
    if (output.is_relative_to(payload) or payload.is_relative_to(output)
            or project.is_relative_to(output) or toc.is_relative_to(output)):
        raise ValueError('output overlaps input')
    entries = toc_entries(toc)
    measured, originals, aliases = {}, {}, {}
    seen = set()
    for path in sorted(payload.rglob('*')):
        name = path.relative_to(payload).as_posix()
        attribution.material.safe_path(name)
        if name.casefold() in seen:
            raise ValueError('duplicate payload path')
        seen.add(name.casefold())
        target = path.resolve()
        if not target.is_relative_to(payload):
            raise ValueError('payload alias escapes root')
        if path.is_symlink():
            if not target.is_file():
                raise ValueError('payload alias must target a regular file')
            aliases[name] = target.relative_to(payload).as_posix()
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('payload must contain regular files')
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        data = path.read_bytes()
        candidates = entries.get(name, entries.get(aliases.get(name), set()))
        matches = set()
        for candidate in candidates:
            if candidate.is_file() and candidate.read_bytes() == data:
                matches.add(candidate.resolve())
        if not matches:
            raise ValueError('missing or changed original: ' + name)
        if len(matches) != 1:
            raise ValueError('ambiguous original: ' + name)
        original = matches.pop()
        originals[original] = data
        measured[name] = (data, original)
    if not measured:
        raise ValueError('payload contains no ELF files')
    sdk = sdk_context()
    wheels = wheel_index(originals, sdk.distributions)
    if any(len(matches) > 1 for matches in wheels.values()):
        raise ValueError('ambiguous wheel RECORD ownership')

    inputs = Inputs(project, sdk)
    configuration = tomllib.loads((project / 'pyproject.toml').read_text())
    roots = [Requirement(item).name for item in configuration['project']['dependencies']]
    inputs.distributions(roots)
    records, files = [], []
    for index, (name, (data, original)) in enumerate(measured.items()):
        owners, reason = [], None
        try:
            acquired = inputs.resolve(original, data, wheels[original])
            inputs.references.add(acquired['source']['reference'])
            owners.append(acquired)
        except (ValueError, OSError, KeyError, tarfile.TarError) as error:
            # File names in acquisition diagnostics are payload-relative, never SDK paths.
            reason = str(error) if isinstance(error, ValueError) else 'missing acquisition input for ' + name
        records.append(dict(file=name, original=f'originals/{index}', owners=owners))
        files.append(dict(file=name, sha256=hashlib.sha256(data).hexdigest(),
                          wheel_records=wheels[original], unresolved=reason))
    diagnostics = dict(schema_version=1, qualification=QUALIFICATION,
                       files=files, aliases=aliases, separate_obligations=[
                           'Generated main application and PyInstaller bootloader: integrating build must qualify',
                           'Outer AppImage runtime: integrating build must qualify independently'])
    output.mkdir()
    build = output / 'evidence'
    (build / 'originals').mkdir(parents=True)
    view = output / 'payload'
    view.mkdir()
    for record, (data, _) in zip(records, measured.values()):
        (build / record['original']).write_bytes(data)
        destination = view / record['file']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    for name, data in inputs.materials.items():
        destination = build / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (build / 'evidence.json').write_bytes(json_bytes(dict(schema_version=1, records=records)))
    (output / 'acquisition.json').write_bytes(json_bytes(diagnostics))
    result = attribution.collect(view, build, output / 'association')
    if result:
        return result
    inventory = json.loads((output / 'association/inventory.json').read_text())
    inventory['qualification'] = QUALIFICATION
    inventory['aliases'] = aliases
    inventory['separate_obligations'] = diagnostics['separate_obligations']
    inputs.put('native/inventory.json', json_bytes(inventory))
    inputs.put('installed.json', json_bytes(dict(python=inputs.python, vendor=inputs.vendor,
                                                shipped_browsers=sorted(inputs.shipped_browsers))))
    directions = [QUALIFICATION, '', 'Full source access (retain alongside the distribution):',
                  *sorted(inputs.references), '',
                  'Chromium: check out the exact source tag, fetch its DEPS with depot_tools, and retain',
                  'Playwright browser_patches at the recorded beta core commit. Registry association',
                  'is not proof of the vendor build inputs or signatures.',
                  'Wheel source references identify distribution releases, not independently attested',
                  'vendored-library build revisions. Raw installed and registered notices are retained.',
                  'Qt/PySide: retain full module sources, build/configuration and vendored code; keep',
                  'equivalent source access available alongside binaries, mirroring if upstream expires.',
                  'Dynamically linked components remain replaceable with compatible modified builds.',
                  'Installed FFmpeg notices do not imply standalone FFmpeg is shipped.',
                  *diagnostics['separate_obligations'], '']
    inputs.put('SOURCE-ACCESS.txt', '\n'.join(directions).encode())
    public = output / 'notices'
    public.mkdir()
    for name, data in inputs.materials.items():
        destination = public / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        'Exit 0: measured source/legal coverage, NOT legal approval; '
        '1: unresolved acquisition, diagnostics retained without notices/; 2: invalid input. '
        'Publish only notices/, never intermediate ELF copies. '
        'See docs/linux-build-evidence.md.'))
    parser.add_argument('--payload', required=True, type=Path, help='shipped _internal directory')
    parser.add_argument('--toc', required=True, type=Path, help='literal PyInstaller COLLECT TOC')
    parser.add_argument('--project', required=True, type=Path, help='project root containing toolchain and reviewed material registries')
    parser.add_argument('--output', required=True, type=Path, help='new diagnostics directory; parent must exist')
    args = parser.parse_args(argv)
    try:
        return acquire(args.payload, args.toc, args.project, args.output)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print('build-evidence: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
