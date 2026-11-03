# Experimental Linux build environment (T5a)

This recipe prepares an **x86_64 Ubuntu 24.04 build image**, not an AppImage or a
supported Linux release. Windows packaging and dependency pins are unchanged.
The target is a separate Pop!_OS Ubuntu 24.04-based machine running COSMIC/Wayland.

## Build and inspect (parent-controlled)

From the repository root, an operator already authorized to use Docker can run:

```sh
# Bash: send only the three required files to the Docker daemon.
set -o pipefail
tar -cf - packaging/linux/Dockerfile packaging/linux/toolchain.json pyproject.toml |
  docker build --platform=linux/amd64 -f packaging/linux/Dockerfile -t marsdisplay-linux-build:t5a -
docker run --rm --network=none marsdisplay-linux-build:t5a python --version
```

The current parent has authorization to prefix **Docker only** with `sudo` if
required by its daemon. This is not permission to change host groups, socket
permissions, device permissions, or to run the application as root.

The build needs network access to Ubuntu repositories, python.org, PyPI and
Playwright's browser distribution. The explicit tar context sends only the
Dockerfile and two public metadata files to the daemon. Explicit `COPY` alone
limits image contents, not which files a repository-wide context could transmit.
No application, host venv, host binaries, private records or `.git` are sent or
installed. These commands require no host mounts.
The final user is `builder` (UID 10001); only OS dependency provisioning uses root.
CPython compilation, pip and Chromium installation run as that nonroot user.

## What is pinned and recorded

| Input | Contract |
| --- | --- |
| Ubuntu | `24.04`, immutable digest in `toolchain.json`, explicit `linux/amd64` |
| CPython | 3.13.5 official `.tar.xz`; SHA256 checked before extraction |
| Python requirements | Read current project dependencies, build extra and build-system pins directly from `pyproject.toml`; no upgrades |
| Browser | Chromium installed package-locally by that pinned Playwright (`PLAYWRIGHT_BROWSERS_PATH=0`) |
| Provenance | `/opt/provenance`: input manifest/metadata, apt versions/architectures, Python packages, compiler/glibc, PyInstaller and browser identities |

CPython archive SHA256:
`93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640`.
The parent established the published checksum from the CPython package entry in
[PSF's source SBOM](https://www.python.org/ftp/python/3.13.5/Python-3.13.5.tar.xz.spdx.json),
linked by the [official release](https://www.python.org/downloads/release/python-3135/).
The [archive](https://www.python.org/ftp/python/3.13.5/Python-3.13.5.tar.xz)
was not independently downloaded/verified by the implementation worker.
The recipe verifies downloaded bytes during construction; no signature
verification is claimed. Apt repositories and transitive wheels remain unlocked:
base/source pins and recorded identities do **not** imply full reproducibility.

Ubuntu 24.04 supplies the target glibc 2.39 baseline. The development host uses
newer glibc 2.41, so copying its Python, venv or frozen binaries would not establish
target compatibility. Building here avoids that known baseline mismatch; actual
ELF dependency/version checks and execution on the target are still required.
Headers support shared CPython and its standard extensions; binutils/file/patchelf
support later PyInstaller inspection. XCB/Wayland/EGL, fonts and Chromium libraries
support later desktop/browser testing. Xvfb is for isolated tests, not proof of
COSMIC/Wayland acceptance.

## Safety and remaining acceptance

Keep Chromium sandboxing enabled when later tests launch it. Do not add
sandbox-disabling flags, privileged mode, security-policy overrides, host IPC,
USB/display/home mounts, or root app/test execution. Nonroot installation alone
does not prove a working sandbox: if the daemon blocks required namespaces,
report that environment limitation rather than weakening isolation.

- T5a: parent must actually build the image and inspect the recorded identities.
- T5b: implement Linux-only onedir/entrypoint and verify frozen worker admission,
  Qt loading, sandboxed Chromium and cleanup using fake-only tests.
- T5c: separately pin AppImage tooling/runtime and establish artifact/license
  provenance, packaging and transfer instructions. No such tools are fetched here.
- Remote acceptance: real COSMIC/Wayland tray/GUI, panel brightness/capture,
  disconnect/cleanup and current native Windows regression remain pending.

Portable `tests/test_linux_packaging.py` checks metadata/recipe constraints and
executes dependency argument construction with installation intercepted. It does
not build Docker, launch a browser, or qualify a frozen artifact.
