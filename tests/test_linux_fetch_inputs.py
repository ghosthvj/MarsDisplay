"""Portable public-main checks; no network or executable inputs are used."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RETAINED = (
    "LICENSE", "install-dependencies.sh", "libfuse-LGPL2.txt",
    "libfuse-mount.c.diff", "musl-COPYRIGHT", "squashfuse-LICENSE",
    "zlib-LICENSE", "zstd-LICENSE", "runtime-asset.json", "runtime-run.json",
    "provenance.json",
)
ARCHIVES = ("type2-runtime-fedfad51.tar.gz", "fuse-3.15.0.tar.xz", "musl-1.2.5.tar.gz")


def digest(data):
    return hashlib.sha256(data).hexdigest()


class FetchTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("fetch_inputs", ROOT / "packaging/linux/fetch_inputs.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.material = self.root / "material"
        self.material.mkdir()
        self.output = self.root / "result"
        self.calls = []
        self.responses = {}
        self.pins = {}
        for key, repo in (("appimagetool", "appimagetool"), ("runtime", "type2-runtime")):
            url = f"https://api.github.com/repos/AppImage/{repo}/releases/assets/123"
            self.responses[url] = key.encode()
            self.pins[key] = {"asset_id": 123, "sha256": digest(key.encode())}
        self.registry = {"downloads": [], "retained": {}}
        for name in ARCHIVES:
            url = "https://github.com/source/archive/" + name
            self.responses[url] = name.encode()
            self.registry["downloads"].append({"name": name, "url": url, "sha256": digest(name.encode())})
        for name in RETAINED:
            data = (name + "\r\n").encode()
            (self.material / name).write_bytes(data)
            self.registry["retained"][name] = digest(data)
        self.pins_path = self.root / "pins.json"
        self.registry_path = self.root / "registry.json"
        (self.root / "caller-data").write_bytes(b"untouched")

    def invoke(self, message=None, calls=0):
        self.pins_path.write_text(json.dumps(self.pins), encoding="utf-8")
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        output_existed = self.output.exists()
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        stdout, stderr = io.StringIO(), io.StringIO()

        def transport(url):
            self.calls.append(url)
            response = self.responses[url]
            if isinstance(response, Exception):
                raise response
            return response

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(["--output", str(self.output)], transport=transport,
                                    pins_path=self.pins_path, registry_path=self.registry_path,
                                    material_root=self.material)
        self.assertEqual((code, stdout.getvalue(), stderr.getvalue()),
                         (0, "Prepared pinned Linux inputs.\n", "") if message is None
                         else (1, "", f"fetch_inputs: {message}\n"))
        self.assertEqual(len(self.calls), calls)
        for path, data in before.items():
            self.assertEqual((self.root / path).read_bytes(), data)
        if message and not output_existed:
            self.assertFalse(self.output.exists())

    def test_success_layout_and_verbatim_material(self):
        self.invoke(calls=5)
        expected = {"tools/appimagetool-x86_64.AppImage": b"appimagetool", "tools/runtime-x86_64": b"runtime"}
        expected.update({"notices/runtime/" + n: n.encode() for n in ARCHIVES})
        expected.update({"notices/runtime/" + n: (n + "\r\n").encode() for n in RETAINED})
        expected["notices/runtime/runtime-inputs.json"] = self.registry_path.read_bytes()
        actual = {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected)

    def test_existing_output_is_untouched(self):
        self.output.mkdir()
        (self.output / "sentinel").write_bytes(b"keep")
        self.invoke("output must be a new directory")

    def test_missing_material_rejected_before_transport(self):
        self.material = self.root / "missing"
        self.invoke("retained material unavailable: LICENSE")

    def test_changed_material_rejected_before_transport(self):
        (self.material / "LICENSE").write_bytes(b"changed")
        self.invoke("SHA256 mismatch: LICENSE")

    def test_each_download_digest_is_mandatory(self):
        for index, url in enumerate(self.responses):
            with self.subTest(url=url):
                original = self.responses[url]
                self.responses[url] = b"corrupt"
                names = ("appimagetool-x86_64.AppImage", "runtime-x86_64") + ARCHIVES
                self.invoke("SHA256 mismatch: " + names[index], calls=index + 1)
                self.responses[url] = original
                self.calls.clear()

    def test_transport_failure_has_no_output_or_retry(self):
        url = list(self.responses)[2]
        self.responses[url] = OSError("private host details")
        self.invoke("download failed: " + ARCHIVES[0], calls=3)

    def test_unsafe_urls_rejected_before_transport(self):
        for url in ("http://github.com/a", "file:///etc/passwd", "https://user@github.com/a",
                    "https://localhost/a", "https://github.com/../a", "https://github.com/%2e%2e/a",
                    "https://github.com/a#fragment", "https://github.com/a?token=secret"):
            with self.subTest(url=url):
                self.registry["downloads"][0]["url"] = url
                self.invoke("unsafe download URL")

    def test_unsafe_or_incomplete_registry_rejected(self):
        for name in ("../escape", "/absolute", "C:\\escape", "x/y", "LICENSE", ARCHIVES[1]):
            with self.subTest(name=name):
                self.registry["downloads"][0]["name"] = name
                self.invoke("invalid runtime registry")
        self.registry["downloads"][0]["name"] = ARCHIVES[0]
        self.registry["retained"].pop("zlib-LICENSE")
        self.invoke("invalid runtime registry")

    def test_missing_output_parent_rejected_without_transport(self):
        self.output = self.root / "absent" / "result"
        self.invoke("output parent must be an existing unlinked directory")

    def test_write_failure_retains_diagnostic_output(self):
        original = Path.open

        def fail_output(path, mode="r", *args, **kwargs):
            if mode == "xb":
                raise OSError("private filesystem details")
            return original(path, mode, *args, **kwargs)

        # Existing sentinel outside output stays intact; output is retained on write errors.
        self.pins_path.write_text(json.dumps(self.pins), encoding="utf-8")
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(Path, "open", fail_output), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(["--output", str(self.output)], transport=self.responses.__getitem__,
                                    pins_path=self.pins_path, registry_path=self.registry_path,
                                    material_root=self.material)
        self.assertEqual((code, stdout.getvalue(), stderr.getvalue()),
                         (1, "", "fetch_inputs: output I/O failed; any partial output is retained\n"))
        self.assertTrue((self.output / "notices/runtime").is_dir())
        self.assertFalse(any(p.is_file() for p in self.output.rglob("*")))
        self.assertEqual((self.root / "caller-data").read_bytes(), b"untouched")
        self.invoke("output must be a new directory")

    def test_repository_registry_passes_local_checks_before_fetch(self):
        stdout, stderr, calls = io.StringIO(), io.StringIO(), []

        def stop(url):
            calls.append(url)
            raise OSError("fixture stop; no network")

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module.main(["--output", str(self.output)], transport=stop)
        self.assertEqual((code, stdout.getvalue(), stderr.getvalue()),
                         (1, "", "fetch_inputs: download failed: appimagetool-x86_64.AppImage\n"))
        self.assertEqual(calls, ["https://api.github.com/repos/AppImage/appimagetool/releases/assets/699466557"])
        self.assertFalse(self.output.exists())
        registry = json.loads((ROOT / "packaging/linux/runtime-inputs.json").read_bytes())
        asset = json.loads((ROOT / "third_party/linux-runtime/runtime-asset.json").read_bytes())
        pins = json.loads((ROOT / "packaging/linux/appimage-tools.json").read_bytes())
        self.assertEqual(asset["digest"], "sha256:" + pins["runtime"]["sha256"])
        self.assertEqual(set(registry["retained"]), set(RETAINED))
        self.assertIn("not exact Alpine APK build source", (ROOT / "third_party/linux-runtime/provenance.json").read_text())

    def test_invalid_pin_rejected_before_transport(self):
        self.pins["runtime"]["sha256"] = "not-a-hash"
        self.invoke("invalid tool pins")

    def test_invalid_registry_digest_rejected_before_transport(self):
        self.registry["downloads"][0]["sha256"] = ""
        self.invoke("invalid runtime registry")


if __name__ == "__main__":
    unittest.main()
