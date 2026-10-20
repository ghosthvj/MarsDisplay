"""Offline, single-release CPython evidence. No downloads or native execution.

The manifest pin is a review boundary, not a signing key. Updating the SDK
requires a new independently compared snapshot and an explicit source change.
"""
import hashlib
import json
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'tools/windows-python-usb-probe/native-material'
MANIFEST_SHA256 = 'a228c69cc149758e432ef3320f7c8c8388bee485f894d76ed3a01f8fec42317a'
spec = util.spec_from_file_location('probe_material_payload', ROOT / 'packaging/payload.py')
payload = util.module_from_spec(spec)
spec.loader.exec_module(payload)


def read_inputs(repo):
    files = payload.read_tree(Path(repo) / PREFIX)
    manifest = files.get('manifest.json', b'')
    if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Unknown CPython material manifest')
    policy = json.loads(manifest)
    if policy['schema'] != 1 or files.get('.gitattributes') != b'* -text\n':
        raise ValueError('Invalid CPython material schema/attributes')
    expected = {'manifest.json', '.gitattributes'}
    provenance = {}
    for component, path, sha256, blob in policy['files']:
        name = 'raw/' + component + '/' + path
        expected.add(name)
        raw = files.get(name, b'')
        if (hashlib.sha256(raw).hexdigest() != sha256
                or hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != blob):
            raise ValueError('CPython material hash/blob mismatch: ' + name)
        repository, commit, _ = policy['sources'][component]
        url = 'https://raw.githubusercontent.com/' + repository + '/' + commit + '/' + path
        payload._source_reference(url, commit)
        provenance[name] = {'source_url': url, 'source_commit': commit,
                            'sha256': sha256, 'git_blob_sha1': blob}
    if set(files) != expected:
        raise ValueError('Unexpected CPython material file')
    return {'policy': policy, 'files': files, 'provenance': provenance}


def validate_sdk(bundle, build, license_bytes):
    policy = bundle['policy']
    commit = policy['sources']['cpython'][1]
    if (build.get('Python') != policy['python']
            or ('tags/v' + policy['python'] + ':' + commit[:7] + ',') not in build.get('sys_version', '')
            or hashlib.sha256(license_bytes).hexdigest() != policy['sdk_license_sha256']):
        raise ValueError('Unknown CPython SDK release/source/license')


def associate(bundle, name, fact, origin, sdk_components):
    """Bind measured native facts to official members and pinned release recipes.

    The caller independently checks bytes, AMD64 PE format and Analysis origin.
    OpenSSL still needs the existing global exact-byte/source policy afterward.
    Expat is not in this snapshot: shipping it requires new proof, not a marker.
    """
    policy = bundle['policy']
    matches = [row for row in policy['members'] if name == '_internal/' + row[0]]
    if len(matches) != 1:
        raise ValueError('Unknown official CPython native member: ' + name)
    base, sdk_path, sha = matches[0]
    if (fact.get('sha256') != sha or origin.get('sha256') != sha
            or origin.get('sdk_path') != sdk_path):
        raise ValueError('Official CPython member/origin hash mismatch: ' + name)
    pe = fact.get('pe', {})
    if base == 'libffi-8.dll':
        if pe != {'status': 'absent'} or sha != policy['libffi_binary']['sha256']:
            raise ValueError('Independent libffi binary binding mismatch')
    else:
        version = '3.5.9.0' if base == 'libcrypto-3.dll' else '3.13.16150.1013'
        if pe != {'status': 'measured', 'file_version': version, 'product_version': version}:
            raise ValueError('Official CPython member PE mismatch: ' + name)
    source = lambda component: ('https://github.com/' + policy['sources'][component][0]
                               + '/tree/' + policy['sources'][component][1])
    terms = lambda path: 'cpython-inputs/' + path
    record = {'component': 'CPython', 'version': policy['python'],
              'sources': [source('cpython')],
              'licenses': ['runtime/Python/LICENSE.txt', terms('raw/cpython/LICENSE'),
                           terms('raw/cpython/Doc/license.rst')],
              'sdk': origin, 'official_distribution': {**policy['distribution'],
                  'member': base, 'member_sha256': sha},
              'recipe_provenance': terms('manifest.json')}
    embedded = []
    components = {'python313.dll': ['zlib', 'Unicode'], 'unicodedata.pyd': ['Unicode'],
                  '_decimal.pyd': ['mpdecimal'], '_bz2.pyd': ['bzip2'],
                  '_lzma.pyd': ['xz'], 'libffi-8.dll': ['libffi']}.get(base, [])
    recipes = {'zlib': 'pythoncore.vcxproj', 'mpdecimal': '_decimal.vcxproj',
               'bzip2': '_bz2.vcxproj', 'xz': '_lzma.vcxproj', 'libffi': '_ctypes.vcxproj',
               'Unicode': 'pythoncore.vcxproj' if base == 'python313.dll' else 'unicodedata.vcxproj'}
    for component in components:
        if component in {'zlib', 'mpdecimal'}:
            measured = sdk_components.get('libmpdec' if component == 'mpdecimal' else component, {})
            if measured != {'version': policy['sources'][component][2],
                            'sha256': sha, 'sdk_path': sdk_path}:
                raise ValueError('Unbound SDK component version: ' + component)
        licenses = ([terms('raw/cpython/Doc/license.rst')] if component == 'Unicode' else
                    [terms('raw/' + c + '/' + path) for c, path, _, _ in policy['files'] if c == component])
        embedded.append({'component': component,
                         'version': 'CPython ' + policy['python'] + ' Unicode data' if component == 'Unicode'
                                    else policy['sources'][component][2],
                         'sources': [source('cpython' if component == 'Unicode' else component)],
                         'licenses': licenses,
                         'recipe': terms('raw/cpython/PCbuild/' + recipes[component]),
                         'release_properties': terms('raw/cpython/PCbuild/python.props')})
    record['embedded_components'] = embedded
    if base == 'libffi-8.dll':
        record.update(component='libffi', version=policy['sources']['libffi'][2],
                      sources=[source('libffi')], licenses=embedded[0]['licenses'],
                      independent_binary=policy['libffi_binary'])
    return record
