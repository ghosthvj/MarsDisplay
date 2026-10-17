"""Collect installed provenance verbatim; not an SPDX or compatibility auditor."""
from importlib import metadata, util
from pathlib import Path
import json
import re

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# These standalone recipe modules must not shadow the installed packaging package.
_payload_spec = util.spec_from_file_location('marsdisplay_payload', Path(__file__).with_name('payload.py'))
_payload = util.module_from_spec(_payload_spec)
_payload_spec.loader.exec_module(_payload)
_DEFAULT_MATERIAL_ROOT = Path(__file__).absolute().parents[1] / 'third_party/license-material'


def _license_file(path):
    return bool(re.match(r'(?i)^(license|licence|copying|notice|thirdpartynotices)', path.name)
                or path.name.lower().endswith('.license'))


def collect_distributions(roots, lookup=metadata.distribution, *, material_root=None):
    """Return (runtime inventory, notice bytes) using installed dependency closure.

    Evaluate markers for the current build host with no extras. Run on the actual
    Windows builder for delivery; Linux results are preparation evidence only.
    No direct_url.json, environment dump or editable checkout path is exported.
    Only absent installed license files permit exact-name/version local fallback;
    installed broken/empty files still fail. Binding material is not native audit.
    """
    pending = list(roots)
    seen, inventory, material = set(), [], {}
    fallback = None
    while pending:
        requested = canonicalize_name(pending.pop(0))
        if requested in seen:
            continue
        seen.add(requested)
        dist = lookup(requested)
        meta = dist.metadata
        name, version = meta['Name'], meta['Version']
        if canonicalize_name(name) != requested:
            raise ValueError('Installed distribution name does not match request')
        sources = []
        for value in ([meta.get('Home-page')] + (meta.get_all('Project-URL', []) if hasattr(meta, 'get_all') else [])):
            if value:
                url = value.split(', ', 1)[-1]
                # Only public project references, never credentials/query fragments.
                from urllib.parse import urlsplit
                parsed = urlsplit(url)
                if parsed.scheme in {'https', 'http'} and parsed.hostname and not (parsed.username or parsed.password or parsed.query or parsed.fragment):
                    sources.append(url)
        if not version or not sources:
            raise ValueError(f'Missing version/source project metadata: {name}')
        licenses = []
        for file in dist.files or []:
            if _license_file(Path(file)):
                relative = Path(file).as_posix()
                # Anchor RECORD paths to the installed distribution root. Shared
                # validation rejects traversal and every symlink before reading;
                # invalid installed material must never select the fallback.
                data = _payload.read_tree(dist.locate_file(''), (relative,))[relative]
                key = f'third-party/{requested}/{relative}'
                material[key] = data
                licenses.append(key)
        provenance = {}
        if not licenses:
            if fallback is None:
                fallback = _payload.collect_license_material(
                    _DEFAULT_MATERIAL_ROOT if material_root is None else material_root)
            registry, upstream = fallback
            matched = [record for record in registry['materials']
                       if any(canonicalize_name(package['name']) == requested and package['version'] == version
                              for package in record['packages'])]
            if not matched:
                raise ValueError(f'Missing version-matched license material: {name}=={version}')
            # One shared copy, including supplementary records and qualifications.
            material.update({'upstream/' + path: data for path, data in upstream.items()})
            licenses = ['upstream/' + record['path'] for record in matched]
            provenance = {'license_provenance': matched,
                          'license_registry': 'upstream/provenance.json',
                          'license_qualification': registry['qualification']}
        dependencies = []
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                if requirement.url or requirement.extras:
                    raise ValueError('Runtime URL/extras dependency requires explicit resolution')
                dependencies.append(str(requirement))
                pending.append(requirement.name)
        inventory.append({'name': name, 'version': version, 'license': meta.get('License'),
                          'license_expression': meta.get('License-Expression'),
                          'sources': sorted(set(sources)), 'licenses': licenses,
                          'requires': sorted(dependencies), **provenance})
    return sorted(inventory, key=lambda item: canonicalize_name(item['name'])), material


def collect_vendor(driver):
    """Require Node, Playwright and each installed browser/FFmpeg's raw notices.

    Inspect package-local browsers only. Registry revisions are copied exactly;
    absent browser installations are omitted, but headless Chromium and FFmpeg
    are mandatory for this application's default Playwright launch mode.
    """
    driver = Path(driver)
    required = ('LICENSE', 'package/LICENSE', 'package/NOTICE', 'package/ThirdPartyNotices.txt', 'package/browsers.json')
    material = {}
    for name in required:
        path = driver / name
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing vendor material: {name}')
        material['vendor/' + name] = path.read_bytes()
    # Playwright's ThirdPartyNotices points to these per-bundle inlined licenses.
    for path in sorted((driver / 'package/lib').rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink driver material')
        if path.is_file() and _license_file(path):
            data = path.read_bytes()
            if not data:
                raise ValueError('Empty driver license material')
            material['vendor/' + path.relative_to(driver).as_posix()] = data
    registry = json.loads(material['vendor/package/browsers.json'])
    browsers = driver / 'package/.local-browsers'
    inventory = []
    for item in registry['browsers']:
        name, revision = item['name'], item['revision']
        directory = browsers / (name.replace('-', '_') + '-' + revision)
        if not directory.exists():
            if name in {'chromium-headless-shell', 'ffmpeg'}:
                raise ValueError(f'Missing bundled browser: {name}')
            continue
        if directory.is_symlink():
            raise ValueError('Symlink browser directory')
        licenses = []
        for path in sorted(directory.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink vendor material')
            if path.is_file() and _license_file(path):
                key = 'vendor/' + path.relative_to(driver).as_posix()
                data = path.read_bytes()
                if data:
                    material[key] = data
                    licenses.append(key)
        if not licenses:
            raise ValueError(f'Missing browser license material: {name}')
        inventory.append({'name': name, 'revision': revision,
                          'browser_version': item.get('browserVersion'), 'licenses': licenses,
                          'registry': 'vendor/package/browsers.json'})
    if not {'chromium-headless-shell', 'ffmpeg'} <= {item['name'] for item in inventory}:
        raise ValueError('Missing Chromium/FFmpeg registry entries')
    return inventory, material
