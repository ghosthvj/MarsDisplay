# Experimental Linux build environment and onedir candidate

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

## T5b: production onedir and no-USB smoke (parent-controlled)

`packaging/linux/MarsDisplay.spec` is independent of Windows packaging. The custom
USB runtime hook runs before standard Qt hooks; ordinary launch calls `app.main`.
Standard PyInstaller Qt hooks collect the imported Qt modules/plugins, rather than
all of PySide6. Playwright's standard hook collects its package-local driver and
Chromium tree, preserving the path expected by `BrowserSession`. Default
PyInstaller mode/symlink handling is retained; UPX is disabled.

Run from the project root in Bash, using the already verified T5a builder.
Only tracked Python source and the four named packaging files enter the container;
no host venv, cache, credentials, `.git`, USB or display mounts are involved.
The archive is emitted only after build and smoke succeed (logs go to stderr):

```sh
set -o pipefail
set -C # Refuse to overwrite an existing output archive.
mkdir -p build
{ git ls-files 'src/mars_display/*.py'; printf '%s\n' \
    packaging/linux/MarsDisplay.spec packaging/linux/entrypoint.py \
    packaging/linux/usb_bootstrap.py packaging/linux/smoke.py; } |
  tar -cf - -T - |
  sudo -n docker run --rm -i --network=none --cap-drop=ALL --read-only \
    --tmpfs /work:rw,exec,uid=10001,gid=10001 --tmpfs /tmp:rw,exec,mode=1777 \
    marsdisplay-linux-build:t5a bash -euc '
      tar -xf -
      export PYINSTALLER_CONFIG_DIR=/work/build/pyinstaller-config
      timeout 600 python -m PyInstaller --noconfirm \
        --workpath build/work --distpath build/dist packaging/linux/MarsDisplay.spec >&2
      timeout 50 env PYTHONPATH=src python -B packaging/linux/smoke.py \
        --appdir build/dist/MarsDisplay >&2
      tar -cf - build/dist/MarsDisplay
    ' > build/linux-onedir.tar
```

Here `--appdir` means the **production onedir directory containing `MarsDisplay`**,
not a future AppImage AppDir. Alternatively use `--executable /absolute/path/to/MarsDisplay`.
The runner needs the matching source tree on `PYTHONPATH` for the public ownership
and packet APIs; it is not shipped in the production bundle. `--help` is passive.
Each protocol operation has a 3–4 second deadline, subprocesses are reaped in
`finally`, and a 40-second runner watchdog bounds the scenarios. HOME/XDG paths
are temporary and a settings sentinel must remain unchanged.

The smoke verifies quiet malformed/reserved argument rejection, inherited control
FD READY/release using the real `OwnedWorker`, data HELLO and CLOSE-before-OPEN
with OK/exit 0/reap, wrong-identity OPEN with IDENTITY_ERROR/exit 1, and wrong or
withheld release with exit 2 and no data connection. It never sends a valid panel
identity, so the production protocol rejects before resolver/serial access.
Source tests exercise this runner but do **not** qualify frozen execution.

## T5b2: test-only frozen Qt/browser probe

This optional, nonshipping helper is **not qualified**. Successful frozen
qualification is not a production build or release prerequisite; production
source collection does not require the probe files. No production spec/CLI or
workflow changes are involved. **Never ship SmokeProbe in MarsDisplay or an
AppImage**.

Historical frozen execution reached Qt offscreen, XCB/Wayland dependency loading
and bundled Node, then Chromium failed with `No usable sandbox`. RGB capture was
never reached. The historical independent verifier was unavailable due to
`ENOSPC`; that is not a pass. Source contract tests use fake backends and do not
establish frozen runtime success or production-payload equivalence.

For a separately authorized future attempt, build this separate onedir in the
verified builder. Parent-controlled commands (Bash, repository root; no host
artifact execution):

```sh
set -o pipefail
set -C
mkdir -p build
{ git ls-files 'src/mars_display/*.py'; printf '%s\n' \
    packaging/linux/SmokeProbe.spec packaging/linux/smoke_probe.py; } |
  tar -cf - -T - |
  sudo -n docker run --rm -i --network=none --cap-drop=ALL --read-only \
    --tmpfs /work:rw,exec,uid=10001,gid=10001 --tmpfs /tmp:rw,exec,mode=1777 \
    marsdisplay-linux-build:t5a bash -euc '
      tar -xf -
      export PYINSTALLER_CONFIG_DIR=/work/build/pyinstaller-config
      timeout 600 python -m PyInstaller --noconfirm \
        --workpath build/work --distpath build/dist packaging/linux/SmokeProbe.spec >&2
      tar -cf - build/dist/SmokeProbe
    ' > build/linux-probe.tar
sudo -n docker run --rm -i --network=none --cap-drop=ALL --read-only \
  --tmpfs /work:rw,exec,uid=10001,gid=10001 --tmpfs /tmp:rw,exec,mode=1777 \
  marsdisplay-linux-build:t5a bash -euc '
    tar -xf -
    timeout -k 5 45 build/dist/SmokeProbe/SmokeProbe
  ' < build/linux-probe.tar
```

The image user is nonroot 10001. No mounts, policy overrides, sandbox-disabling
flags, remote dashboards, serial devices or host displays are permitted. A
sandbox/namespace denial is a failure, not a skip or permission to weaken policy.
The 30-second Python watchdog attempts `finally` cleanup; the external timeout
bounds native hangs and container removal is the final containment boundary.
HOME/XDG/tmp are isolated; a settings sentinel must remain unchanged.

`SmokeProbe --help` is passive and prints exactly:

```text
Usage: SmokeProbe [--help]
Test-only Linux nonroot Qt/browser qualification; no devices.
```

Unsupported/root execution returns 2 with stderr `FAIL: Linux nonroot required`.
Success returns 0 with stdout `PASS: Qt offscreen, platform dlopen, Node, sandboxed RGB capture, direct-child cleanup`.
Other failures return 1 with stderr prefixed `FAIL:`. Public Playwright diagnostic
launch errors distinguish permission/sandbox, package/dependencies, and unclassified
failures; their backend detail is retained. Actual BrowserSession then captures
loopback HTML as exactly 320×480 RGB(17,34,51), and closes in `finally`.
Direct-child observations cover this process's threads, not reparented descendants.
XCB/Wayland `dlopen` checks dependency resolution, **not compositor connections**.

Before attributing probe results to production, parent must compare archive member
SHA256 values for shared Qt libraries/plugins, Playwright driver/Node/Chromium and
native dependencies against `build/linux-onedir.tar`; also record source revision
and Python package provenance. Standard hooks alone do not prove byte identity.
No frozen runtime pass or production-payload equivalence is claimed by source
tests. This standalone packaging recipe is risk item 5 for parent verification;
independent verification remains pending. COSMIC, hardware and native Windows
acceptance are outside this helper's qualification. See
[Linux release assembly](linux-release-assembly.md) for the separate production
AppDir/AppImage path; this probe does not gate it.
