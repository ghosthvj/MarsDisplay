"""Acquire pinned Linux runtime inputs without executing or extracting them."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
RETAINED = {
    "LICENSE", "install-dependencies.sh", "libfuse-LGPL2.txt",
    "libfuse-mount.c.diff", "musl-COPYRIGHT", "squashfuse-LICENSE",
    "zlib-LICENSE", "zstd-LICENSE", "runtime-asset.json", "runtime-run.json",
    "provenance.json",
}
ARCHIVES = {"type2-runtime-fedfad51.tar.gz", "fuse-3.15.0.tar.xz", "musl-1.2.5.tar.gz"}
HOSTS = {"api.github.com", "github.com", "codeload.github.com",
         "release-assets.githubusercontent.com", "objects.githubusercontent.com",
         "distfiles.alpinelinux.org"}


def safe_url(url, *, redirect=False):
    try:
        parts = urlsplit(url)
        path = unquote(parts.path)
        valid = (parts.scheme == "https" and parts.netloc in HOSTS and not parts.fragment
                 and (redirect or not parts.query) and "\\" not in path
                 and not any(p in {".", ".."} for p in path.split("/"))
                 and not any(ord(c) <= 32 or ord(c) == 127 for c in url))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("unsafe download URL")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl, redirect=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url):
    safe_url(url)
    request = Request(url, headers={"Accept": "application/octet-stream", "User-Agent": "MarsDisplay-inputs"})
    with build_opener(SafeRedirect()).open(request, timeout=60) as response:
        safe_url(response.geturl(), redirect=True)
        return response.read()


def regular_bytes(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise OSError("not a regular unlinked file")
    return path.read_bytes()


def checked(data, expected, name):
    if not isinstance(data, bytes) or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("SHA256 mismatch: " + name)
    return data


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def prepare(output, transport, pins_path, registry_path, material_root):
    if output.exists() or output.is_symlink():
        raise ValueError("output must be a new directory")
    if not output.parent.is_dir() or any(p.is_symlink() for p in output.parents) or ".." in output.parts:
        raise ValueError("output parent must be an existing unlinked directory")
    try:
        pins = json.loads(regular_bytes(pins_path))
        jobs = []
        for key, repo, name in (("appimagetool", "appimagetool", "appimagetool-x86_64.AppImage"),
                                ("runtime", "type2-runtime", "runtime-x86_64")):
            pin = pins[key]
            if type(pin["asset_id"]) is not int or pin["asset_id"] <= 0 or not valid_hash(pin["sha256"]):
                raise ValueError()
            url = f"https://api.github.com/repos/AppImage/{repo}/releases/assets/{pin['asset_id']}"
            jobs.append(("tools/" + name, url, pin["sha256"]))
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("invalid tool pins") from None
    try:
        registry_bytes = regular_bytes(registry_path)
        registry = json.loads(registry_bytes)
        archives, retained = registry["downloads"], registry["retained"]
        if (not isinstance(archives, list) or len(archives) != len(ARCHIVES)
                or {a["name"] for a in archives} != ARCHIVES
                or not isinstance(retained, dict) or set(retained) != RETAINED
                or not all(valid_hash(h) for h in retained.values())
                or not all(valid_hash(a["sha256"]) and isinstance(a["url"], str) for a in archives)):
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise ValueError("invalid runtime registry") from None
    for archive in archives:
        safe_url(archive["url"])
        jobs.append(("notices/runtime/" + archive["name"], archive["url"], archive["sha256"]))
    # Stage verified bytes only in memory: rejected inputs leave no output to reuse.
    contents = {"notices/runtime/runtime-inputs.json": registry_bytes}
    for name, sha in retained.items():
        try:
            data = regular_bytes(material_root / name)
        except OSError:
            raise ValueError("retained material unavailable: " + name) from None
        contents["notices/runtime/" + name] = checked(data, sha, name)
    for destination, url, sha in jobs:
        name = destination.rsplit("/", 1)[1]
        try:
            data = transport(url)
        except Exception:
            raise ValueError("download failed: " + name) from None
        contents[destination] = checked(data, sha, name)
    # Exclusive creation protects existing caller data; I/O failures retain partial output.
    output.mkdir()
    (output / "tools").mkdir()
    (output / "notices" / "runtime").mkdir(parents=True)
    for destination, data in contents.items():
        with (output / destination).open("xb") as stream:
            stream.write(data)


def main(argv=None, *, transport=download, pins_path=ROOT / "packaging/linux/appimage-tools.json",
         registry_path=ROOT / "packaging/linux/runtime-inputs.json",
         material_root=ROOT / "third_party/linux-runtime"):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Creates tools/ and notices/runtime/ in a fresh directory with an existing parent. "
        "No execution, extraction, retries or overwrite. Rejections leave no output; "
        "write failures may retain partial output for diagnosis."))
    parser.add_argument("--output", type=Path, required=True, metavar="NEWDIR")
    args = parser.parse_args(argv)
    try:
        prepare(args.output, transport, pins_path, registry_path, material_root)
    except ValueError as error:
        print("fetch_inputs: " + str(error), file=sys.stderr)
        return 1
    except OSError:
        print("fetch_inputs: output I/O failed; any partial output is retained", file=sys.stderr)
        return 1
    print("Prepared pinned Linux inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
