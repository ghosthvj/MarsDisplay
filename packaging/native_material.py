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


GROUPING_PROFILE = 'usb-grouping-v1'
GROUPING_REQUIRED = frozenset({PREFIX + name for name in (
    'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'QtCore.pyd', 'QtGui.pyd',
    'QtWidgets.pyd', 'pyside6.abi3.dll', 'plugins/platforms/qwindows.dll')} | {
    '_internal/shiboken6/Shiboken.pyd', '_internal/shiboken6/shiboken6.abi3.dll'})
# Stock QtGui/Widgets hook roots; each still needs the exact reviewed policy
# hash, RECORD association and fresh PE evidence. This is not a subset switch.
GROUPING_OPTIONAL = frozenset(PREFIX + name for name in (
    'plugins/platforms/qdirect2d.dll', 'plugins/platforms/qminimal.dll',
    'plugins/platforms/qoffscreen.dll', 'plugins/styles/qmodernwindowsstyle.dll',
    'plugins/imageformats/qgif.dll', 'plugins/imageformats/qicns.dll',
    'plugins/imageformats/qico.dll', 'plugins/imageformats/qjpeg.dll',
    'plugins/imageformats/qtga.dll', 'plugins/imageformats/qtiff.dll',
    'plugins/imageformats/qwbmp.dll', 'plugins/imageformats/qwebp.dll'))
GROUPING_SSL = frozenset({'_internal/libssl-3.dll', '_internal/libcrypto-3.dll'})
# Stock TUIO may retain Network/TLS. Admit only its complete reviewed closure,
# not arbitrary additional Qt modules or one orphaned DLL.
GROUPING_NETWORK = frozenset({PREFIX + name for name in (
    'plugins/generic/qtuiotouchplugin.dll', 'Qt6Network.dll', 'QtNetwork.pyd',
    'plugins/networkinformation/qnetworklistmanager.dll',
    'plugins/tls/qcertonlybackend.dll', 'plugins/tls/qopensslbackend.dll',
    'plugins/tls/qschannelbackend.dll')} | {
    '_internal/libssl-3-x64.dll', '_internal/libcrypto-3-x64.dll'})


def validate_profile(profile):
    if profile not in ('portable', GROUPING_PROFILE):
        raise ValueError('Unknown native profile')


def _profile_policy(policy, runtime, profile):
    validate_profile(profile)
    if profile == 'portable':
        return policy
    scope = {path for path in runtime if (
        path.startswith((PREFIX, '_internal/shiboken6/')) and Path(path).suffix.lower() in {'.dll', '.pyd'})
        or re.fullmatch(r'_internal/(?:libssl|libcrypto)[^/]*\.dll', path, re.I)}
    if (not GROUPING_REQUIRED <= scope
            or not scope <= GROUPING_REQUIRED | GROUPING_OPTIONAL | GROUPING_SSL | GROUPING_NETWORK
            or scope & GROUPING_NETWORK not in (frozenset(), GROUPING_NETWORK)
            or scope & GROUPING_SSL not in (frozenset(), GROUPING_SSL)):
        # Report only fixed allowlist differences, never arbitrary payload/host names.
        differences = dict(
            missing_required=sorted(GROUPING_REQUIRED - scope),
            unexpected_count=len(scope - (GROUPING_REQUIRED | GROUPING_OPTIONAL |
                                          GROUPING_SSL | GROUPING_NETWORK)),
            network_missing=sorted(GROUPING_NETWORK - scope) if scope & GROUPING_NETWORK else [],
            ssl_missing=sorted(GROUPING_SSL - scope) if scope & GROUPING_SSL else [])
        raise ValueError('Unmapped experimental native payload: ' + json.dumps(differences, sort_keys=True))
    known = {item['path'] for item in policy['components'] + policy['supplemental']}
    if not scope <= known:
        raise ValueError('Experimental native payload lacks reviewed policy')
    return dict(policy, **{key: [item for item in policy[key] if item['path'] in scope]
                           for key in ('components', 'supplemental')})


def source_access(bundle, *, profile='portable'):
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
    if profile == GROUPING_PROFILE:
        lines = [line for line in lines if line not in (
            'Other runtime sources and notices: inventory.json and notices/; CPython, Node,',
            'Chromium, FFmpeg, winldd, Python packages and PyInstaller remain separately covered.')]
        lines.extend(['Experimental runtime presence is recorded only in inventory.json and',
                      'supplemental.json; retained full-source notices do not assert bundled features.', ''])
    return '\n'.join(lines).encode('utf-8')


def prepare(repo, runtime, inventory, destination, *, profile='portable'):
    """Materialize only after fresh exact facts match reviewed source policy; own stage only."""
    validate_profile(profile)
    bundle = read_inputs(repo)
    policy, registry = _profile_policy(bundle['policy'], runtime, profile), bundle['registry']
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
    texts.update({'SOURCE-ACCESS.txt': source_access(bundle, profile=profile), 'supplemental.json': _json(dict(
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
