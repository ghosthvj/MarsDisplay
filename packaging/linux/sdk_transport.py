"""Stream curated inputs to the original nonroot SDK owner; recover public outputs."""
import hashlib
from importlib import util
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
_spec = util.spec_from_file_location('transport_assembly', HERE / 'assemble_release.py')
assembly = util.module_from_spec(_spec)
_spec.loader.exec_module(assembly)
_spec = util.spec_from_file_location('transport_payload', HERE.parent / 'payload.py')
payload = util.module_from_spec(_spec)
_spec.loader.exec_module(payload)
SCRIPT = '''tar --no-same-owner -xf -
status=0
python -B source/packaging/linux/build_sdk.py --project /work/source --release-record /work/release.json --output /work/result >&2 || status=$?
if [ "$status" -eq 0 ]; then
    tar -cf - result/onedir result/notices result/build.json
elif [ -f result/build.log ]; then
    tar -cf - result/build.log
else
    tar -cf - --files-from /dev/null
fi
exit "$status"
'''


def extract_sdk(archive_path, destination, expected):
    """Validate the entire namespace, aliases and build record before extraction."""
    if os.path.lexists(destination):
        raise ValueError('extraction destination must not exist')
    with tarfile.open(archive_path) as archive:
        members, folded, spellings = {}, {}, {}
        try:
            for member in archive.getmembers():
                name = member.name.rstrip('/')
                payload._validate({name: b'x'})
                parts = name.split('/')
                for end in range(1, len(parts) + 1):
                    component = '/'.join(parts[:end])
                    if spellings.setdefault(component.casefold(), component) != component:
                        raise ValueError()
                if (name.casefold() in folded or not (member.isdir() or member.isfile() or member.issym())
                        or not (name in {'result', 'result/onedir', 'result/notices', 'result/build.json'}
                                or name.startswith(('result/onedir/', 'result/notices/')))):
                    raise ValueError()
                if name in {'result', 'result/onedir', 'result/notices'} and not member.isdir():
                    raise ValueError()
                members[name], folded[name.casefold()] = member, member
            for name, member in members.items():
                if any(str(parent).casefold() in folded and not folded[str(parent).casefold()].isdir()
                       for parent in PurePosixPath(name).parents):
                    raise ValueError()
                if member.issym():
                    current, seen = name, set()
                    prefix = 'result/onedir/' if name.startswith('result/onedir/') else 'result/notices/'
                    while members[current].issym():
                        if current in seen:
                            raise ValueError()
                        seen.add(current)
                        target = members[current].linkname
                        if not target or target.startswith('/') or '\\' in target:
                            raise ValueError()
                        current = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
                        if not current.startswith(prefix) or current not in members:
                            raise ValueError()
                    if not members[current].isfile():
                        raise ValueError()
            for required in ('result/build.json', 'result/onedir/MarsDisplay/MarsDisplay'):
                if required not in members or not members[required].isfile():
                    raise ValueError()
            if not any(name.startswith('result/notices/') and member.isfile() for name, member in members.items()):
                raise ValueError()
        except (ValueError, KeyError, RuntimeError) as error:
            raise ValueError('unsafe SDK archive') from error
        try:
            record = json.load(archive.extractfile('result/build.json'))
            with archive.extractfile('result/onedir/MarsDisplay/MarsDisplay') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if (record['release'] != expected or record['installed_version'] != expected['version']
                    or record['execution_uid'] != 10001 or record['executable_sha256'] != digest
                    or record['checks'] != ['frozen-worker-smoke', 'native-source-association']):
                raise ValueError()
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError('SDK build record mismatch') from error
        destination.mkdir(mode=0o700)
        archive.extractall(destination, filter='data')
    return destination / 'result'


def run_sdk(source, record_path, image, output, *, sudo=False, runner=subprocess.run):
    """Run once, retaining private tar/log diagnostics on failure; never publish."""
    source, record_path, output = Path(source), Path(record_path), Path(output)
    if os.path.lexists(output):
        raise ValueError('output must not exist')
    payload.read_tree(output.parent, ())
    output = output.resolve()
    if any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output) for p in (source, record_path)):
        raise ValueError('output overlaps input')
    if not isinstance(image, str) or not re.fullmatch(r'[a-z0-9][a-zA-Z0-9._/:@-]*', image):
        raise ValueError('invalid SDK image reference')
    expected = assembly.release_record(record_path)
    files = payload.read_tree(source)
    if 'packaging/linux/build_sdk.py' not in files:
        raise ValueError('missing SDK build script')
    output.mkdir(mode=0o700)
    incoming = output / 'sdk-input.tar'
    with tarfile.open(incoming, 'w') as archive:
        for name, data in [*(('source/' + name, data) for name, data in sorted(files.items())),
                           ('release.json', json.dumps(expected).encode())]:
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(data), 0o644
            archive.addfile(member, io.BytesIO(data))
    command = (['sudo', '-n'] if sudo else []) + ['docker', 'run', '--rm', '-i', '--pull=never',
               '--network=none', '--read-only', '--cap-drop=ALL', '--user', '10001:10001',
               '--tmpfs', '/work:rw,exec,uid=10001,gid=10001,mode=0700',
               '--tmpfs', '/tmp:rw,exec,mode=1777', image, 'bash', '-euc', SCRIPT]
    outgoing = output / 'sdk-output.tar'
    with incoming.open('rb') as stdin, outgoing.open('xb') as stdout, (output / 'docker.log').open('xb') as stderr:
        runner(command, stdin=stdin, stdout=stdout, stderr=stderr, check=True)
    return extract_sdk(outgoing, output / 'extracted', expected)
