"""External Microsoft-runtime profile; selection, never SDK deletion or installation."""
from contextlib import contextmanager
import re


def _basename(path):
    return str(path).replace('\\', '/').rsplit('/', 1)[-1].casefold()


def is_external(path):
    name = _basename(path)
    return (name in {'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
                     'vcruntime140.dll', 'vcruntime140_1.dll', 'ucrtbase.dll'}
            or re.fullmatch(r'api-ms-win-(?:core|crt)-[a-z0-9-]+\.dll', name) is not None)


def select_roots(entries):
    return [entry for entry in entries if not is_external(entry[0]) and not is_external(entry[1])]


@contextmanager
def external_dependencies():
    # Pinned 6.22.3 Analysis retains its input list, then extends it with the
    # finder result. Selecting only the result would leave direct SDK roots.
    from PyInstaller.building import build_main
    from PyInstaller.depend import dylib
    original_find, original_include = build_main.find_binary_dependencies, dylib.include_library
    def find(binaries, import_packages, symlink_suppression_patterns):
        binaries[:] = select_roots(binaries)  # Analysis-owned list; tuples unchanged.
        return original_find(binaries, import_packages, symlink_suppression_patterns)
    def include(path):
        return False if is_external(path) else original_include(path)
    try:
        build_main.find_binary_dependencies, dylib.include_library = find, include
        yield
    finally:
        build_main.find_binary_dependencies, dylib.include_library = original_find, original_include


@contextmanager
def omit_optional_mesa(info):
    missing = object()
    previous = info.__dict__.get('_collect_all_or_none', missing)
    original = info._collect_all_or_none
    def collect(mandatory_dll_patterns, *args, **kwargs):
        if mandatory_dll_patterns == ['opengl32sw.dll'] and not args and not kwargs:
            return []
        return original(mandatory_dll_patterns, *args, **kwargs)
    try:
        info._collect_all_or_none = collect
        yield
    finally:
        if previous is missing:
            del info._collect_all_or_none
        else:
            info._collect_all_or_none = previous


def assert_profile(runtime):
    if any(is_external(name) or _basename(name) == 'opengl32sw.dll' for name in runtime):
        raise ValueError('External-runtime profile contains a Microsoft DLL or optional Mesa; nothing published')
