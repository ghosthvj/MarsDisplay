"""Offline, pinned source policy binding. Not an automatic legal approver."""
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import posixpath
import re

REGISTRY_SHA256 = '3543f2d2017e9a05de1fec4a1b580876d45b6db890f8aebd7a3e39bd8124ad06'
POLICY_SHA256 = 'a93efb59277880545494b5c8cee9b544df4b641f8f86be1de050055ec561f15a'
PREFIX = '_internal/PySide6/'


def _load(name):
    spec = util.spec_from_file_location('marsdisplay_material_' + name, Path(__file__).with_name(name + '.py'))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload = _load('payload')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _modules(registry):
    return registry['modules'] | {'openssl-' + version: dict(item, repository='openssl/openssl', release=version)
                                  for version, item in registry['openssl'].items()}


def read_inputs(repo):
    """Return only registered, unmodified raw inputs and reviewed policy. No SDK/I/O side effects."""
    root = Path(repo) / 'third_party/native-material'
    if not root.exists() and not root.is_symlink():
        raise ValueError('Missing verified native sources: third_party/native-material; Windows qualification is pending')
    try:
        files = payload.read_tree(root, ('provenance.json', 'policy.json', 'README.md'))
        if _sha(files['provenance.json']) != REGISTRY_SHA256 or _sha(files['policy.json']) != POLICY_SHA256:
            raise ValueError()
        registry, policy = [json.loads(files[name]) for name in ('provenance.json', 'policy.json')]
        if (registry['schema'] != 'marsdisplay-native-source-material-v1'
                or policy['schema'] != 'marsdisplay-native-source-policy-v1'
                or policy['registry_sha256'] != REGISTRY_SHA256):
            raise ValueError()
        modules = _modules(registry)
        files.update(payload.read_tree(root, dict.fromkeys(item['path'] for item in registry['files'])))
        by_source, release_records = {}, {}
        for item in registry['files']:
            module = modules[item['module']]
            data = files[item['path']]
            key = (item['module'], payload.safe_path(item['source_path']))
            if (key in by_source or item['source_commit'] != module['commit']
                    or _sha(data) != item['sha256'] or item['path'] != 'raw/' + item['sha256'] + '.txt'
                    or item['kind'] not in {'release-reference', 'source-metadata', 'license', 'license-notice', 'attribution'}):
                raise ValueError()
            payload._source_reference(item['source_url'])
            if item['kind'] == 'release-reference':
                tag = json.loads(data)
                expected_tag = ('openssl-' if item['module'].startswith('openssl-') else 'v') + module['release']
                expected_url = 'https://api.github.com/repos/' + module['repository'] + '/git/tags/' + tag['sha']
                if (tag['object'] != dict(sha=module['commit'], type='commit', url=tag['object'].get('url'))
                        and tag['object'] != dict(sha=module['commit'], type='commit')):
                    raise ValueError()
                if (tag['tag'] != expected_tag or item['source_url'] != expected_url
                        or tag['url'] != expected_url or item['path'] != module['release_reference']
                        or item['module'] in release_records or not re.fullmatch('[a-f0-9]{40}', tag['sha'])):
                    raise ValueError()
                release_records[item['module']] = item
            else:
                blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                url = 'https://raw.githubusercontent.com/' + module['repository'] + '/' + module['commit'] + '/' + item['source_path']
                if item['git_blob_sha1'] != blob or item['source_url'] != url:
                    raise ValueError()
                payload._source_reference(url, module['commit'])
            by_source[key] = item
        if set(release_records) != set(modules):
            raise ValueError()
        for module in modules.values():
            expected = 'https://github.com/' + module['repository'] + '/archive/' + module['commit'] + '.tar.gz'
            if module['source_archive'] != expected:
                raise ValueError()
            payload._source_reference(expected, module['commit'] + '.tar.gz')
        declared = set()
        for item in registry['declared_license_files']:
            attribute = by_source[(item['module'], item['attribution'])]
            license_record = by_source[(item['module'], item['license_file'])]
            if attribute['kind'] != 'attribution' or license_record['kind'] not in {'license', 'license-notice'}:
                raise ValueError()
            declared.add((item['module'], item['attribution'], item['license_file']))
        actual = set()
        for (module, name), item in by_source.items():
            if item['kind'] != 'attribution':
                continue
            # Some primary Qt metadata contains literal tabs. Retained bytes NEVER change.
            attributes = json.loads(files[item['path']], strict=False)
            for attribute in attributes if isinstance(attributes, list) else [attributes]:
                names = attribute.get('LicenseFiles', []) + ([attribute['LicenseFile']] if 'LicenseFile' in attribute else [])
                for relative in names:
                    target = payload.safe_path(posixpath.normpath(posixpath.join(posixpath.dirname(name), relative)))
                    actual.add((module, name, target))
        # Repeated upstream declarations are retained verbatim, not normalized away.
        if actual != declared:
            raise ValueError()
        payload._validate(files)
        return dict(registry=registry, policy=policy, files=files)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ValueError('Invalid verified native sources or policy') from None


def preflight(repo, inventory):
    """Admit exact selected SDK RECORD associations before compiler/process creation."""
    bundle = read_inputs(repo)
    policy = bundle['policy']
    if inventory['build']['Qt'] != policy['qt_release']:
        raise ValueError('Native source policy does not match selected Qt SDK')
    items = policy['components'] + policy['supplemental']
    index, status = _load('native_evidence')._record_index(inventory, {item['sha256'] for item in items}, metadata.distribution)
    for item in items:
        owner = item['owner']
        if status != 'available' or (owner and index.get(item['sha256']) != {(owner['name'], owner['version'], owner['record_path'])}):
            raise ValueError('Native source policy does not match selected SDK RECORD')
    return bundle


def source_access(bundle):
    lines = ['SOURCE ACCESS — MarsDisplay portable prototype', '',
             'The application and local build hooks/configuration are included in source/.',
             'For complete pinned upstream module sources, including build/configuration and',
             'vendored code, copy these full immutable archives (not just notice extracts):']
    for name, item in sorted(_modules(bundle['registry']).items()):
        lines.extend([name + ' ' + item['release'] + ' / ' + item['commit'], item['source_archive']])
    lines.extend(['', 'Raw copyrights, licenses, conditional QtUsage/version attributions and tag proofs:',
                  'notices/native/inputs/ (also source/third_party/native-material/).',
                  'Qt/PySide source association is the reviewed policy, NOT inferred from owner/PE versions.',
                  'Full-module notices are conservative: not every optional feature is compiled.',
                  'Supplemental Shiboken/OpenSSL inventory: notices/native/supplemental.json.',
                  'Other runtime sources and notices: inventory.json and notices/; CPython, Node,',
                  'Chromium, FFmpeg, winldd, Python packages and PyInstaller remain separately covered.',
                  'Redistributors: provide equivalent source access alongside the binary under GPLv3',
                  'section 6(d); keep these directions adjacent, maintain access as long as required,',
                  'and mirror the exact complete sources if upstream access ceases. Artifact expiry',
                  'is not an exemption. No extra EULA/DRM overrides the applicable GPL/LGPL rights.',
                  'Unpacked dynamically linked DLLs remain replaceable with compatible modified builds.',
                  'Microsoft VC++ is an official external prerequisite, not redistributed here.', ''])
    return '\n'.join(lines).encode('utf-8')


def prepare(repo, runtime, inventory, destination):
    """Materialize only after fresh exact facts match reviewed source policy; own stage only."""
    bundle = read_inputs(repo)
    policy, registry = bundle['policy'], bundle['registry']
    required = {path for path in runtime if path.startswith(PREFIX) and Path(path).suffix.lower() in {'.dll', '.pyd'}}
    if required != {item['path'] for item in policy['components']} or inventory['build']['Qt'] != policy['qt_release']:
        raise ValueError('Unmapped native Qt payload for reviewed source policy')
    supplemental_scope = {path for path in runtime if (
        path.startswith('_internal/shiboken6/') and Path(path).suffix.lower() in {'.dll', '.pyd'})
        or re.fullmatch(r'_internal/(?:libssl|libcrypto)[^/]*\.dll', path, re.I)}
    if supplemental_scope != {item['path'] for item in policy['supplemental']}:
        raise ValueError('Unmapped supplemental native payload for reviewed source policy')
    items = policy['components'] + policy['supplemental']
    selected = {item['path']: runtime[item['path']] for item in items if item['path'] in runtime}
    if len(selected) != len(items) or any(_sha(selected[item['path']]) != item['sha256'] for item in items):
        raise ValueError('Native bytes do not match reviewed source policy')
    fresh = _load('native_evidence').collect(selected, inventory)
    for item in items:
        owner = item['owner']
        expected = dict(sha256=item['sha256'], pe=item['pe'], origins=dict(
            status='matched' if owner else 'unknown', record_status='available', matches=[owner] if owner else []))
        if fresh.get(item['path']) != expected:
            raise ValueError('Native binary evidence does not match reviewed source policy')
    modules = _modules(registry)
    components, supplemental = [], []
    for item in items:
        module = modules[item['module']]
        licenses = sorted({'inputs/' + record['path'] for record in registry['files']
                           if record['module'] == item['module'] and record['kind'] in {'license', 'license-notice', 'attribution'}})
        record = dict(path=item['path'], sha256=item['sha256'], component=item['module'], version=module['release'],
                      sources=[module['source_archive']], licenses=licenses,
                      version_evidence=['inputs/' + module['release_reference']], binary_evidence=fresh[item['path']])
        (components if item in policy['components'] else supplemental).append(record)
    texts = {'inputs/' + name: data for name, data in bundle['files'].items()}
    texts.update({'SOURCE-ACCESS.txt': source_access(bundle), 'supplemental.json': _json(dict(
        schema='marsdisplay-native-supplemental-v1', components=supplemental))})
    manifest = dict(schema='marsdisplay-native-material-v2', qt_release=policy['qt_release'],
                    qualification=policy['qualification'], components=components,
                    material_sha256={name: _sha(data) for name, data in sorted(texts.items())})
    texts['native.json'] = _json(manifest)
    payload._validate(texts)
    destination = Path(destination).absolute()
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('Symlink native material stage')
    destination.mkdir()  # Exclusive; never use the old manually populated build/native-material.
    for name, data in texts.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    return destination
