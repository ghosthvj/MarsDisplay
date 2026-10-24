# MarsDisplay

## 0.2.0rc4: USB selector polish candidate

The candidate fixes light/dark contrast for the USB selector and its open
list, separates Refresh by 12 logical pixels, and removes the redundant profile
legend from the configuration heading. The internal USB profile, explicit
selection/Save/Start, settings and brightness are unchanged.

**[Download 0.2.0rc4 for Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/40096247259/artifacts/12560971970)**
from [verified run 40096247259](https://github.com/ghosthvj/MarsDisplay/actions/runs/40096247259).
Available until **2026-10-31 13:03 UTC**; GitHub sign-in may be required. Extract
the Actions download, then the whole `MarsDisplay-0.2.0rc4-Windows-x64.zip`
(**205,798,234 bytes**) into a new folder. Inner ZIP SHA256:

```text
ab85da542fa40e53098f4d692a2a785d1b4ea48400250d608a883efcd673e58d
```

**Verified:** 378 Windows tests with zero skips, native build and packaged smoke;
parent and independent checks verified 1,280 payload hashes, 384 source hashes
and 69 AMD64 binaries against `c059526fd55eccdac1d4646a08ab4449a9e68845`.
This remains a test candidate, not physical owner acceptance or a final release.
Packaged worker smoke makes no OPEN/device request.

Exit the previous instance and keep its complete folder as fallback. Existing
schema-3 settings and brightness need no migration. Windows 11 x64 still requires
the official Microsoft Visual C++ v14 x64 runtime 14.51 or newer. These delivery
notes supersede pending wording in the immutable bundled source; no rebuild is
implied. See [verification details](packaging/README.md#ui-follow-up-candidate--020rc4).
The rc3 artifact below is historical and does not contain these follow-up changes.

## 0.2.0rc3: compact native configuration candidate

The new candidate combines the requested UI changes:

- Capitalized status labels and vector icons, with animated transition wheels.
- Independent live **Logs**, grouped with **Preview** in the footer apart from Save.
- Centered 320px brightness slider; compact **Enable Brightness** only when needed.
- Native-USB-only configuration, explicit device selection, Save and Start.
- USB selector and Refresh in one row; legacy recovery/export controls hidden,
  with their guarded functions retained internally and no new advanced menu.
- Fixed-height form bounded by desktop space, with vertical overflow scrolling
  only when needed and a fixed footer; cleanup errors remain readable.
  Simulation remains a backend capability, not a UI mode selector.

Existing rc2 schema-3 settings and brightness carry over without another migration.
Extract the full new portable ZIP into a separate folder after exiting rc2; retain
that folder as fallback. No dependencies, USB transport or packaging recipe changed.
**[Download 0.2.0rc3 for Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/40042896444/artifacts/12540281670)**
from [verified run 40042896444](https://github.com/ghosthvj/MarsDisplay/actions/runs/40042896444).
Available until **2026-10-31 00:06 UTC**; GitHub sign-in may be required. Extract
the Actions download, then the entire `MarsDisplay-0.2.0rc3-Windows-x64.zip`
(**205,795,065 bytes**). Inner ZIP SHA256:

```text
012206d539bc8988bf655f0a4d59371d43975517035046be9a63f991c72a0c8b
```

**Verified:** 376 Windows tests with zero skips, native build and isolated packaged
smoke. Parent and independent checks matched all 1,280 payload hashes, 384 source
hashes and 69 AMD64 binaries to source `0a19dd32db14e0d9e0e40f3dc543ce2fb538869d`.
Offscreen layout checks also passed with valid system fonts and zero horizontal
overflow. This is a test candidate, not owner acceptance of rc3 or a final release;
packaged worker smoke sends no OPEN/device request. Windows 11 x64 still requires
the official Microsoft Visual C++ v14 x64 runtime **14.51 or newer**.

These delivery notes supersede pending-qualification wording bundled in the
immutable source archive; they do not rebuild the candidate. See
[verification details](packaging/README.md#ui-candidate--020rc3) and
[current controls](docs/usb-runtime.md). The rc2 download below is the previously
accepted fallback, not a package containing the new UI.

## Previously delivered 0.2.0rc2: brightness and configuration Stop

The rc2 source adds **Stop capture** beside **Start capture** after an idle capture
error. Stop uses the same tray action; explicit Start retry remains available.
It never clears uncertain cleanup or bypasses Exit. The verified rc2 Windows
artifact below includes this fix and keeps existing schema-3 settings unchanged.

MarsDisplay is a Windows 11 x64 tray companion that renders MARS with bundled
Chromium. The current candidate supports Simulation and explicitly selected native
USB output for the qualified 320×480 portrait profile. Native landscape is not
supported; the accepted progressive image repaint is unchanged.

### Brightness

1. Extract the entire portable ZIP, launch `MarsDisplay.exe`, and keep the
   previous working folder as a fallback. Capture always starts stopped.
2. In **Status / Settings**, save the MARS URL and explicit **Native USB** device.
3. While stopped, choose **Enable saved brightness…**. Review the schema-3
   compatibility warning: a backup preserves the previous settings for recovery.
4. Move the slider to **20%, 40%, 60%, 80% or 100%**. Releasing it or using arrow keys
   saves the percentage; **Start** applies it. Live changes wait for the current
   image and reuse the same connection. There is no zero/off setting.
5. **Stop** ends capture; tray **Exit** waits for owned cleanup. Neither restores
   an unknown prior brightness. The next Start uses the saved percentage.

The slider changes only brightness, never unsaved URL/device drafts. Host completion
is not panel readback. On uncertain USB failure there is no automatic resend or
reconnect: resolve the cause and use Start explicitly. Legacy settings are not
silently migrated; use **Restore settings from before brightness…** while stopped
if returning to the prior configuration/binary (later settings edits are lost).

### Historical rc2 download

[Download MarsDisplay 0.2.0rc2 Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/40023603045/artifacts/12531318437)
from [verified Windows run 40023603045](https://github.com/ghosthvj/MarsDisplay/actions/runs/40023603045).
Artifact retention ends **2026-10-30 21:04 UTC**; GitHub sign-in may be required.
Extract the Actions download, then the complete application ZIP into a new folder.
The inner `MarsDisplay-0.2.0rc2-Windows-x64.zip` is **205,781,620 bytes**; SHA256:

```text
c00fb9d50e86845e9ff96f56a738fb4cfc704e358670dfe4f30a12238482f9d2
```

**Verified:** 360 Windows tests with zero skips, native build and isolated packaged
smoke. Parent and independent checks verified 1,277 payload hashes, 381 source
hashes and 69 AMD64 native binaries against source
`2b973d9a8786191dbf686b0881ac872936e48916`.
**The owner confirmed brightness changes and retention of the selected percentage
across closing and reopening 0.2.0rc1.** The rc2 package corrects the reported
configuration Stop omission after Start errors. **The owner confirmed that rc2
Stop returns to `stopped` and permits configuration editing.** The requested
brightness/persistence and error-Stop behavior are accepted. Unchanged Exit was
not separately requalified physically on rc2; its regression coverage is retained.
This is an accepted release candidate, not a published final release.
Later documentation commits do not rebuild this immutable artifact.

Keep the previous folder as a fallback. Updating rc1 to rc2 needs no settings
migration. Returning to a pre-schema-3 binary requires
stopped **Restore settings from before brightness…** if schema 3 was enabled;
that restores the old configuration and discards later settings edits. This remains
a full portable folder, not a standalone EXE or installer; official VC++ v14 x64
runtime 14.51+ is an external prerequisite. Do not disable Windows security protections.

See [runtime and brightness controls](docs/usb-runtime.md),
[settings and recovery](docs/usb-settings.md), and
[Windows packaging](packaging/README.md). Run source checks with Python 3.13:

```sh
QT_QPA_PLATFORM=offscreen PLAYWRIGHT_BROWSERS_PATH=0 PYTHONPATH=src:tests .venv/bin/python -B -m unittest discover -s tests -v
```

<details>
<summary>Historical prototype documentation and immutable artifact evidence</summary>

The statements below describe earlier prototype stages, not the current candidate.


MarsDisplay is a GPL v3 Windows 11 x64 tray companion that renders MARS locally
with bundled Chromium. Output is **simulated only**: this prototype does not
drive a physical USB screen.

## Download the output preview prototype — 0.1.4

[Download MarsDisplay 0.1.4 Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/39084595234/artifacts/12120556248)
from the [successful native build](https://github.com/ghosthvj/MarsDisplay/actions/runs/39084595234).
Retention ends **2026-10-25 00:59 UTC**; GitHub sign-in may be required.

**Preview** in Status / Settings opens one modeless popup with the exact latest
RGB888 frame accepted by simulated output, not a separate browser capture.
Portrait320×480 and landscape480×320 remain unscaled; scroll if the window is small.
It updates while visible, identifies current lifecycle/live/stale state and retains
the last accepted image after Stop or an output failure. With no frame, it explains
that capture must be started. Close/Escape hides only the popup; reopening shows
the current frame. Hidden previews release their rendered image. Session theme and
existing capture/Save/Exit guards remain unchanged. No image files/history, extra
Chromium, new setting, USB communication or proof of physical reception is added.
Exit the previous instance through the tray, extract the **entire application ZIP**
into a separate folder, open `MarsDisplay.exe`, then use **Status / Settings → Preview**.
Your saved settings remain in place. Keep the owner-tested 0.1.3 folder as a fallback.
The official Microsoft VC++ v14 x64 **14.51+** prerequisite is unchanged:
https://aka.ms/vc14/vc_redist.x64.exe . No installer or automatic prerequisite download.

**Verified:** 159 Windows source tests (61.547s), native build, isolated packaged
smoke, external-runtime profile, genuine-material qualification and source stability.
The downloaded ZIP is **205,571,620 bytes**; all **1,224 file hashes** and **328 source
hashes** passed, with 69 native files and the unchanged minimal runtime profile.
Application ZIP SHA256 (not the Actions wrapper digest):

```text
4252eeae642b9e7c878c618c7aca5ae0dc13c16ec14629af25a5e8c658064e54
```

Exact binary source: `2b87ace0967f720820fa800b93a21541715012df`.
All 159 local tests, 34 independent tray/preview/real-browser app checks and the
parent spot check passed. Existing public behavior matched the previous source;
synthetic light/dark, portrait/landscape, empty/retained, small-window and 150% views
were inspected. **Owner Windows 11 preview/DPI acceptance remains pending.** The
prior owner confirmation of 0.1.3 themes below does not cover this new popup or
physical USB reception. Later documentation commits do not rebuild this artifact.

<details>
<summary>Previous owner-tested 0.1.3 UI and accepted 0.1.2 baseline</summary>

### Owner-tested themed UI — 0.1.3

[Download MarsDisplay 0.1.3 Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/39078344950/artifacts/12117643947)
from the [successful native build](https://github.com/ghosthvj/MarsDisplay/actions/runs/39078344950).
Includes the approved light/dark Qt status window, capture control and contextual
Save footer, retaining the earlier browser-readiness and handle-disposal fixes.
The artifact contains the application ZIP and SHA256 sidecar; retention ends
**2026-10-24 23:19 UTC**. GitHub sign-in may be required.

1. Exit the previous instance through the tray. Keep your saved settings.
2. Extract the entire application ZIP into a separate folder; do not mix versions
   or copy only the EXE. Keep the accepted 0.1.2 folder as a fallback.
3. Open `MarsDisplay.exe`, check the saved URL, then use **Start capture**.
   **Dark mode / Light mode** switches the window theme for this session only.
   Closing the window or Escape hides it; tray **Exit** closes the application.

Python, Qt and Chromium are bundled. Official **Microsoft VC++ v14 x64 14.51+**
is still an external prerequisite if missing: https://aka.ms/vc14/vc_redist.x64.exe .
The prototype is unsigned, not an installer: do not disable security or copy
random DLLs to bypass an error. Output remains simulated; no USB screen is driven.

**Verified delivery:** Windows CI passed 152 source tests (45.267s), native build,
external-runtime profile, isolated startup/binary smoke, genuine-material
qualification and source stability. The downloaded **205,561,440-byte** ZIP,
all **1,222 file hashes** and **326 source hashes** were verified. SHA256:

```text
d7c2c461cc21e0b857fa87eae20a63cf9af86a099a4ac5fefe55e0178661e3ff
```

Exact artifact source: `e497e165bcfa4d69aafd8715b8d6cf302b6c6097`.
Local tests, independent verification and synthetic 100%/150%/small-window views
passed. The first Windows test run exposed premature layout measurement; the
corrected test retains the same geometry requirement and bounded Qt event loop.
No production timeout, threshold, runtime profile or qualification was relaxed.
**The owner confirmed the 0.1.3 UI working in both light and dark modes on
Windows.** Supplied screenshots show running/ready, live connected, non-stale
capture and increasing frames (34 to 59), with no obvious clipping at that setup.
Other DPI configurations and sustained aggregate resource use were not established
by these two snapshots. Keep **0.1.2** as a fallback; this is not production or
physical-hardware qualification. Later documentation commits do not rebuild
this artifact.

<details>
<summary>Accepted 0.1.2 baseline and historical acceptance evidence</summary>

### Accepted 0.1.2 testing baseline and earlier evidence

[Download MarsDisplay 0.1.2 Windows x64](https://github.com/ghosthvj/MarsDisplay/actions/runs/39065994952/artifacts/12112754920)
from the [successful native build](https://github.com/ghosthvj/MarsDisplay/actions/runs/39065994952).
This releases the temporary Playwright layout-wait handle after every capture;
0.1.1 retained one per frame until Stop. The earlier bounded SPA readiness fix
is preserved. The artifact contains the application ZIP and SHA256 sidecar;
retention ends **2026-10-24 20:20 UTC**. GitHub sign-in may be required.

1. Exit the previous MarsDisplay instance. Keep existing user settings.
2. If missing, manually install official **Microsoft VC++ v14 x64, 14.51+**:
   https://aka.ms/vc14/vc_redist.x64.exe .
3. Extract the entire new application ZIP into a separate folder; do not mix
   versions or copy only the EXE. Keep all auxiliary files.
4. Open `MarsDisplay.exe`. It starts **stopped**. Use tray **Status / Settings**
   to check the saved MARS URL, then **Start**. Use tray **Exit** to close.

Python, Qt and Chromium are bundled; selected Microsoft runtime DLLs and Qt Mesa
are not. There is no MarsDisplay installer or automatic prerequisite download.
The prototype is unsigned: do not disable security or copy random DLLs to bypass
an error. Follow the included root `README.txt`.

**T5 is complete for 0.1.2:** native CI passed all 144 source tests, assembly,
external-runtime profile, startup/binary smoke, native-material qualification,
source stability and publication. The downloaded **205,551,083-byte** ZIP,
all **1,221 file hashes** and **325 source hashes** were verified. SHA256:

```text
657b71f30f1b73e2340de152cf1719b35a1a6a6739b7e819c075e0959387737e
```

Exact artifact source: `93b222b77ac07141d561e8735ef6bbb037747315`.
The memory regression failed with 20 retained handles before correction and
passed with none afterward; all 144 local tests and 14 independent capture and
security tests passed. A real MARS capture passed with the earlier SPA-corrected
source on Linux; no new private endpoint capture was required for this fix. Owner Windows
screenshots show running/ready, live connected, non-stale data and increasing
frame counts; the owner confirmed these tests used the delivered 0.1.1 ZIP.
The owner also confirmed Start, Stop, restart and normal Exit. Screenshots show
the lifetime frame count retained across Stop/restart (30 to 36).
Later owner screenshots show unreachable-source retry exhaustion with unchanged
frames, capture resumed after URL restoration, and Ethernet-loss/live restoration
with appropriate stale flags. The owner confirmed both observed Node processes
disappear after Stop. Separate snapshots suggest an initial combined 184–186 MB,
not a simultaneous total or sustained benchmark. The same EXE PID later grew
from 34–36.4 MB to 42.6–42.7 MB and then 45.9 MB at 3,671 frames.
A local isolated reproduction confirmed one retained layout-wait handle per
capture; source 0.1.2 corrects that retention without changing rendering policy.
**T6 is closed by owner acceptance of 0.1.2 as a testing baseline.** Eight
subsequent same-PID EXE samples ranged from 34.2 to 38.6 MB through 2,303 frames,
ending at 36.4 MB: compatible with stabilization in that run, not an indefinite
memory bound. Aggregate Node/Chromium measurements, remaining Chromium/Exit
cleanup and Stop-during-retry observations are deferred, not passed. This is not
production or physical-screen qualification.
Windows Server CI is not Windows 11 acceptance or hardware support. Later
documentation-only commits do not rebuild this artifact.

</details>

</details>

## Run the application (Windows source)

With the pinned runtime and package-local Chromium available, run from an
interactive Windows x64 user session:

```sh
python -m mars_display
```

There are no product test/control flags or HTTP service. First launch stays
stopped and unconfigured. Use the tray's **Status / Settings** to save an HTTP(S)
MARS URL with direct access (no interactive login), then **Start**. **Stop** closes
only the owned browser; **Exit** waits for acknowledged cleanup before releasing
the single-instance lock. Output is always explicitly simulated, never connected
USB. No browser launches until Start, including when settings already exist.

| Launch outcome | Exit / stderr (stdout is empty) |
| --- | --- |
| Unsupported OS/architecture | 1: `MarsDisplay requires Windows x64; use Windows 11 x64.` |
| No session tray | 1: `A system tray is required; run MarsDisplay in an interactive Windows session.` |
| Duplicate instance | 0: `MarsDisplay is already running.` No second coordinator is created. |
| Other startup failure | 1: `Cannot start MarsDisplay; check the interactive system tray and settings directory access.` |
| Unexpected event-loop return | 1 after cleanup: `Application event loop ended unexpectedly; waiting for owned cleanup.` |

Settings and lock errors use the actionable, non-secret messages described below;
invalid files are not repaired or overwritten. Browser startup failures appear in
the tray as `Capture or output failed; retrying.`; Stop cancels recovery. Resolve
bundled-browser/direct-access issues before Start. Missing Qt/runtime libraries
are startup failures, not an invitation to install system dependencies silently.
Unsupported hosts are rejected before importing Qt or accessing user settings.
The host admission check recognizes Windows x64; Windows 11 is the acceptance
target, not a new version-detection framework. Fake-platform tests are branch
proof only. Source invocation may have a console. The [native build and delivery guide](packaging/README.md) records the verified
artifact, pinned provenance and remaining acceptance limits.

## Run the source tests

Use Python **3.13.x** (the engineering baseline; currently tested on Linux):

```sh
QT_QPA_PLATFORM=offscreen PLAYWRIGHT_BROWSERS_PATH=0 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

The tray tests require the pinned PySide6 dependency and Qt system libraries.
They exercise real widgets using the offscreen Qt platform, without a display
server or USB access. Browser tests require the pinned Playwright/Pillow packages
and the package-local Chromium headless shell; they run real sandboxed Chromium
against a loopback HTTP fixture only. No external MARS access is performed.
Offscreen/Linux success does not prove Windows tray or packaged-browser acceptance.
Application tests compose the real browser, coordinator and simulated output in
both orientations through public tray Start/Stop/Exit, using isolated settings
and test-owned loopback traffic; foreign/raw fixture traces remain intact.
Each orientation releases its owned shell in `finally`, including assertion
failures. First/restarted-frame waits allow a bounded 15-second cold-start
budget and report selected state/counters on timeout, never frame bytes or
URLs. This changes test orchestration, not production timeouts or retries.

## Public interface

With `src` on the Python import path:

```python
from mars_display import RGBFrame, SimulatedTransport, Transport

output: Transport = SimulatedTransport()
output.open()
output.send(RGBFrame(320, 480, bytes(320 * 480 * 3), 0.0))
output.close()
```

| Contract | Behavior |
| --- | --- |
| Frame | Frozen value with integer width/height, immutable `bytes` RGB888, and capture timestamp. |
| Geometry | Only portrait 320×480 or landscape 480×320; no stretching or padding. |
| RGB layout | Top-to-bottom rows, left-to-right RGB triplets; exactly `width * height * 3` bytes. |
| Timestamp | Caller-supplied finite, non-negative monotonic seconds (`int` or `float`, not `bool`); no wall-clock reads or timestamp sorting. |
| Transport | Synchronous `open()`, `send(frame)`, `close()`; no workers, retries, or discovery. |
| Simulation | Initially closed; `status` is `simulated-closed` or `simulated-open`, never physical connectivity. |
| Observation | Read-only `is_open`, `latest_frame` (initially `None`), and `accepted_frames` (initially zero). |
| Accepted send | Replaces the sole retained frame and increments the lifetime counter, including repeated sends of the same frame. Delivery follows call order. |
| Open/close | Idempotent; preserve latest frame and counter, including across reopen. |
| Rejection | Closed sends raise `RuntimeError` before validation; open sends of non-frames raise `TypeError`. Frames are validated before acceptance. All rejected sends leave state unchanged. |

Construction rejects invalid field types with `TypeError` and invalid geometry,
byte lengths, or timestamp values with `ValueError`. Mutable byte buffers are not
silently copied. Simulation retains no history and writes no files. This is a
single-threaded boundary, not a streaming scheduler or a real adapter.

## Passive USB-serial preparation (API only)

`mars_display.devices.enumerate_devices(provider=None)` returns a tuple of frozen
`USBSerialDescriptor` observations. Import does nothing. Only an explicit call
without a provider lazily calls `serial.tools.list_ports.comports(include_links=False)`;
it never opens, probes, handshakes, resets or writes a port. Tests replace that
backend or inject a zero-argument provider of synthetic descriptor objects; no
actual host inventory was enumerated for qualification.

Observations retain `device`, integer `vid`/`pid`, and optional `serial_number`,
`description`, `location`, `manufacturer`, `product`, and `interface`. Non-USB,
missing/invalid VID/PID (outside 0–65535, including booleans), or invalid port-name
records are omitted. Missing, blank, non-string or non-printable optional text
becomes `None`. Metadata is sorted deterministically by all fields; duplicates
remain visible. Inventory failure raises sanitized `DeviceInventoryError` with
`Cannot list USB serial descriptors; check system device access and retry.`
No partial inventory is returned.

A descriptor's `identity` is `None` without a usable USB serial. Otherwise it is
an opaque persistable identity combining VID/PID and percent-escaped,
case-preserved USB serial, e.g. `usb:1234:00ab:Screen%2FA%25%3A%C3%A9` for
serial `Screen/A%:é`. Treat the entire identity as opaque, not as a protocol or
compatibility claim. A COM name alone is never stable identity.

`select_device(inventory, identity)` returns the exact existing observation only
when exactly one matches; it never chooses even a sole device automatically.
COM reassignment follows the unique USB identity, not an unrelated old COM
occupant. Rejections raise `DeviceSelectionError`, leave the inventory unchanged,
and use these exact messages without echoing supplied values:

| Condition | Message |
| --- | --- |
| No selection (`None` or blank) | `Select an explicit stable USB identity; no device was selected.` |
| Unknown identity (including COM-only or legacy opaque values) | `Selected USB identity was not found; refresh inventory and select again.` |
| Multiple matching observations | `Selected USB identity is ambiguous; disconnect duplicates or identify the hardware before selecting.` |

Neither API saves configuration. Existing opaque `Settings.device_identity`
values remain valid and unmigrated; the tray field remains read-only. These APIs
are not wired into startup or Start: runnable output remains `SimulatedTransport`.
Native Windows enumeration, driver compatibility, a physical GUI chooser and
hardware/protocol qualification await identified hardware. VID/PID never selects
a protocol, and no model-specific upstream driver has been copied.

## Local settings (no capture or automatic launch)

```python
from mars_display.settings import Settings, SettingsStore

store = SettingsStore()  # Windows: %LOCALAPPDATA%\MarsDisplay\settings.json
configured = store.load()  # None on first run; does not create a file/directory
# Only an explicit user Save action should call:
# store.save(Settings("https://mars.example/proxy", device_identity=None))
# configured.capture_url would be https://mars.example/proxy/display
```

`Settings(mars_url, device_identity=None, schema_version=1)` is immutable. The
optional device identity is an opaque string, not a COM selection or protocol.
Output remains simulated; there are no preview-product settings. Importing,
constructing, or loading settings never starts capture or discovers devices.

| Contract | Behavior |
| --- | --- |
| Location | Default is exactly `%LOCALAPPDATA%\MarsDisplay\settings.json`; no executable-directory fallback. Missing/relative `LOCALAPPDATA` raises `SettingsStoreError`. |
| Test injection | `SettingsStore(path)` accepts an explicit path; tests use isolated system temporary directories, never real user configuration. |
| Format | JSON object containing exactly `schema_version` (integer 1, not boolean), `mars_url` (string), and `device_identity` (null or non-blank string without control characters). Duplicate/unknown/missing keys are rejected. |
| URL | HTTP(S) with valid host/port; no credentials, query (even empty), fragment (even empty), raw whitespace, control characters (including percent-encoded), or backslashes. No authentication support or TLS bypass. |
| Capture URL | `Settings.capture_url` normalizes scheme/host and trailing slashes, preserves a reverse-proxy prefix, and appends `/display` only if not already present. The original `mars_url` is stored unchanged. |
| Failure | `SettingsError` reports invalid schema/version/URL; `SettingsStoreError` (a subclass) reports access/write failures with actionable messages, never supplied values. No logging. |
| Recovery | Missing file returns `None` (unconfigured). Malformed/unsupported files raise instead of being repaired or overwritten on load. Only explicit `save(settings)` can replace them. |
| Save | Validate before writing; flush and sync a same-directory temporary file, close it, then atomically replace. Rejection or replacement failure preserves old bytes; failed temporary writes are cleaned up. Cleanup denial is reported explicitly. |

For example, `https://mars.example/proxy/` and
`https://mars.example/proxy/display/` both capture
`https://mars.example/proxy/display`. This layer has no runtime-state knowledge:
the lifecycle coordinator below enforces saving only while stopped and keeps
startup stopped/unconfigured rather than choosing a URL/device. Windows filesystem
and application acceptance remain separate from Linux tests.

## Capture lifecycle boundary

`mars_display.lifecycle.Coordinator(store, source_factory, transport_factory)`
is an injectable coordinator, not an application entry point. Application
assembly uses `SimulatedTransport` as its transport factory; device identity
is saved only and never selects a protocol or opens USB.

```python
from mars_display.lifecycle import Coordinator

from mars_display.browser import BrowserSession

# coordinator = Coordinator(store, BrowserSession, SimulatedTransport)
# coordinator.start()         # explicit user action only
# status = coordinator.snapshot()
# coordinator.stop()          # nonblocking request, not an acknowledgement
# coordinator.request_exit()  # nonblocking; poll snapshot().exit_ready
```

| Public operation | Contract |
| --- | --- |
| Construction | Does not load settings, start a worker, or create source/output resources. Initial state is `stopped`. |
| `start()` | Loads saved settings; returns `True` on launch, `False` if a worker already exists (including while stopping). Missing settings raises `LifecycleError("Configure a MARS URL before starting.")`. No implicit resume. |
| `stop()` | Cancels delays and requests cleanup. A currently blocking capture/write must return before cleanup; adapters must use bounded backend timeouts. An in-flight write may finish, but no writes/retries occur after acknowledgement. |
| `request_exit()` | Also prevents future Start. Exit is safe only when `snapshot().exit_ready` is true. Never kills external processes. |
| `snapshot()` | Immutable, thread-safe view; observes actual worker completion before acknowledging stopped/exit. Runtime states: `stopped`, `starting`, `running`, `retrying`, `stopping`, `error`. |
| `save_settings(settings)` | Uses atomic `SettingsStore.save`, only in `stopped` with no live worker. Otherwise raises `LifecycleError("Settings can be saved only while stopped.")`; rejection leaves saved bytes unchanged. |
| `wait_stopped(timeout)` | Bounded join helper for tests/non-GUI callers, not the UI thread. Returns whether the worker finished; inspect snapshot for cleanup errors. |

**Source integration:** `source_factory(settings)` returns a synchronous session
with `open()`, `read() -> SourceSample`, and `close()`. Both factories and every
source/output call run on the same single worker, without a coordinator lock held
across those calls. `close()` must tolerate partial `open()` failure. A factory
that raises before returning must clean its own allocations because the coordinator
cannot own an object it never receives.

`SourceSample(state, frame=None, live_connected=None, data_stale=None)` reports
`loading`, `ready`, `empty`, or `error`; only `ready` permits an `RGBFrame`.
Ready without a frame is also valid. Metadata is independently boolean or unknown
(`None`), not a server-health assessment. A reported error observation does not
itself request reconnect; adapters raise exceptions for recoverable failures.
Snapshots separate `source_state` from `output_state` (`simulated-open`,
`simulated-closed`, or `error`), and expose the metadata, `latest_frame`, lifetime
`frames_sent`, `failures`, `retries`, sanitized `error`, and worker/exit flags.
Simulation is never reported as physical connectivity.

The internal baseline is at most 1 capture/second, with synchronous backpressure
and no frame queue. Empty/loading/error observations retain the last accepted
frame and counter. Snapshots retain that frame even when retry replaces a closed
output instance; there is no automatic resend, clear, reset, or power command.
Setup/capture/write exceptions close all returned resources before retry, with
**five additional attempts after the initial failure**, waiting exactly 1, 2, 4,
8, 16 seconds via cancellable `Event.wait`. A successful observation/delivery
resets the consecutive failure budget. Exhaustion remains `error` until explicit
Start or Stop. Cleanup failure attempts both closes, latches `error`, blocks
restart/save and withholds exit readiness; restart the application after resolving
the owned-resource failure. Backend exception text and private URLs are never
included in status. The tray tests exercise responsiveness with controlled
sessions; actual browser behavior and Windows acceptance remain separate proof.

## Persistent browser capture

`mars_display.browser.BrowserSession(settings)` implements the worker-owned
`SourceSession`: synchronous `open()`, `read() -> SourceSample`, and `close()`.
Construct it on the coordinator worker. Construction starts nothing; repeated
open/close calls are safe. One isolated Chromium browser/context/page survives
across reads, with no per-frame navigation, extra API polling, or disk images.
MARS still owns content, selection, order, dwell, SSE and orientation.

| Boundary | Behavior |
| --- | --- |
| Browser ownership | Forces `PLAYWRIGHT_BROWSERS_PATH=0` before starting the driver. Uses only Playwright's bundled headless Chromium, with sandbox enabled, default TLS validation and device scale factor 1. No persistent profile, user-browser attachment, copied credentials, executable fallback or TLS bypass. |
| Navigation | Only the owned main frame may issue requests; extra pages are closed and popup/subframe requests are rejected before forwarding, even at the same URL. Only the configured capture URL is admitted for document navigation. The initial document response is fetched once with redirects disabled, then fulfilled into the page; redirects and unsuccessful HTTP responses fail without following login paths. Main-frame subresources remain the frontend's responsibility. |
| Readiness | Exactly one `#mars-display`, version 1, valid state/orientation/nominal width and height, boolean live flag and optional boolean stale flag; ready also requires a nonblank server ID. HTTP 200 or a login page alone is never ready. |
| Capture | Loading/empty return no frame. Ready waits for loaded fonts and three matching animation-frame layout observations, releases the temporary wait handle, aligns the viewport, verifies root geometry and captures only that region as PNG in memory. Pillow decodes immutable RGB bytes through `RGBFrame` validation, with a monotonic timestamp. No resizing. |
| Transitions | Metadata and geometry are read again after capture. A state/server/orientation/geometry/freshness transition discards the frame. The next read reevaluates orientation; it never delivers a mismatched frame. |
| Errors | `BrowserError` messages contain no URL/backend exception. Display errors and malformed/missing metadata raise for coordinator recovery. Live-disconnected/stale flags remain independent observations, never claims of server health/unreachability. |
| Stop/cleanup | Navigation, metadata, font/layout and screenshot operations have explicit 1,500 ms timeouts per operation, not a whole-read deadline. Close releases only the owned browser and Playwright driver, including partial setup failures. Backend close has no Playwright timeout option; cleanup failure is reported rather than silently acknowledged. |

A SPA may mount `#mars-display` after DOMContentLoaded. Reads now wait only while
no root exists, within the existing 1,500 ms metadata budget; existing invalid or
duplicate roots are rejected without waiting for repair. Permanent absence keeps
the same metadata error. Path ownership is checked again after the wait. This
source fix changes no retry policy or readiness/geometry requirements.

The loopback tests cover both nominal geometries and exact RGB pixels, repeated
captures without reload, metadata rejections, fonts/layout readiness, transitions,
independent freshness, redirect blocking and partial-setup/capture cleanup. Real
MARS, Windows process ownership, performance and packaged-browser acceptance
remain separate evidence.

## Status window appearance

The 0.1.3 UI offers **Dark mode / Light mode** without another framework.
Theme selection is local to the current dialog/session, initially light; it
survives hiding the window but is not saved in `settings.json`. A new session
starts light. The accepted 0.1.2 portable predates this UI; keep it as a testing fallback.

The window groups capture status, MARS/output observations and configuration,
with a painted monitor icon and a fixed Save footer. Its body scrolls on smaller
windows. Values remain plain text, including saved device identity.
The lifecycle card's **Start capture / Stop capture** button delegates to the
same guarded tray actions. Its intent is fixed when pressed, so a Stop cannot
become an unintended restart if recovery finishes before mouse release.
During capture/recovery/cleanup the URL is read-only
and Save is disabled. In terminal error the primary button can restart capture;
use tray Stop to return to editable settings. The footer explains the current
restriction; obsolete runtime errors and saved-while-stopped feedback are cleared.
Ready/loading/error badges use text as well as color. Lifetime frame counts use
digit grouping only in the view, without changing counters or delivered frames.
The native titlebar, tray actions, stopped-only settings authority and simulated
output remain unchanged. Closing the window or pressing Escape does not exit.

## Application composition and injectable tray shell

`mars_display.tray.create_shell(app, store, coordinator_factory)` assembles the
tray only after acquiring a per-user `QLockFile` beside `store.path`. It returns
`None` if another instance owns the lock, without invoking the coordinator factory.
The entrypoint reports `MarsDisplay is already running.` and exits that launch.
Lock/access and corrupt-configuration errors propagate to the caller for startup
reporting; no silent configuration repair occurs. Retain the returned shell for
its entire event loop.

`mars_display.app.build_shell(app, store)` is the public composition helper for
packaging and isolated tests. It checks session tray availability, then calls
`create_shell` with an idle `Coordinator(store, BrowserSession, SimulatedTransport)`
factory. Tests may supply an isolated `SettingsStore(path)` and patch the native
tray availability boundary for offscreen Qt; production never installs a fake
source or bypasses tray admission. `main()` creates QApplication and the default
per-user store, retaining the shell for the event loop. Unexpected event-loop
return requests owned cleanup and reuses the existing shell polling until its
acknowledgement; cleanup uncertainty keeps ownership instead of forcing a kill.

The factory must construct an idle coordinator using the same store; it must not
start capture or allocate a browser. No fake session is installed in production.
`SingleInstanceGuard(store).acquire()` / `.release()` is also available for future
startup composition; acquire is nonblocking, repeatable for the owning guard,
and never force-removes another live lock. Keep ownership until cleanup succeeds.

| Tray action | Behavior |
| --- | --- |
| Status / Settings (or icon click) | Opens a temporary dialog with separate MARS source, source metadata, explicitly simulated output, lifecycle state, and lifetime frame count. Closing hides it, not the application. |
| Save (stopped only) | Validates the MARS URL through `Settings` and saves through `Coordinator.save_settings`; invalid/active saves preserve previous settings. Saved device identity is opaque/read-only pending hardware identification, not an editable COM port or connected-device claim. |
| Start / Stop | Explicit nonblocking coordinator requests; first launch remains stopped/unconfigured and does not automatically open the dialog. Starting/running/recovering/stopping/error reflect snapshots; no UI-thread joins or backend calls. |
| Exit | Requests cleanup and polls `exit_ready` before releasing the lock and quitting. Uncertain cleanup keeps the app alive and displays an actionable error; it never terminates the user's normal browser. |

The shell sets `QApplication.setQuitOnLastWindowClosed(False)`, generates its icon
in code, and owns a 50 ms snapshot timer. It has no permanent normal window or
console facility, no preview/refresh/server-selection controls, and no local
slideshow or orientation settings. The eventual packaged Windows entrypoint must
select windowed/no-console packaging. Actual Windows lock contention, tray menu,
process lifetime, and no-console behavior still require Windows acceptance.

## Dependencies and current verification

`pyproject.toml` is the single source of direct pins. `requirements.txt` selects
the local editable runtime package; `requirements-build.txt` selects its `build`
extra as well. Tray/application assembly imports Qt; the core remains GUI-independent.

| Purpose | Selected version |
| --- | --- |
| Browser rendering | Playwright 1.64.0 |
| Tray/UI | PySide6 6.12.0 |
| Image decoding | Pillow 12.3.0 |
| Passive serial descriptor metadata only | pyserial 3.5 |
| Native executable recipe (native CI verified; owner acceptance is T6) | PyInstaller 6.22.3 |
| Source build backend | setuptools 84.0.0 |

The backend pin was checked against authoritative
[PyPI JSON metadata](https://pypi.org/pypi/setuptools/84.0.0/json): Python >=3.10
and a `py3-none-any` wheel. The selected stack candidates have published Windows
x64 wheels per the initial dependency investigation; wheel availability is **not**
installation, interoperability, or Windows acceptance evidence. These declarations
are not a complete transitive lock. The pinned editable package and build extra
were installed successfully in a repository-local `.venv` on Linux, producing an
editable wheel. System Python was not modified. Windows EXE/one-folder assembly
and the broad bundle's native startup/binary smoke have since succeeded in CI.
The minimal external-runtime profile, fresh native inventory/smoke, qualification
and downloaded 0.1.2 ZIP are now verified. The owner accepted this testing
baseline and closed T6; unperformed observations remain explicitly deferred.

Linux Qt offscreen availability passed after the explicitly authorized
installation of `libegl1` and its required dependencies. A sandbox-enabled
Chromium local screenshot also passed using the repository-local browser.
These probes establish tooling availability, not Windows tray, real MARS,
packaged-runtime or physical-screen acceptance.

The direct `pyserial==3.5` pin comes from the upstream
[pySerial project](https://pypi.org/project/pyserial/3.5/), under its BSD license;
retain that license and provenance in future bundled dependency notices. The
passive API follows the official
[list_ports documentation](https://github.com/pyserial/pyserial/blob/master/documentation/tools.rst).
The package is installed in the local `.venv`; its universal wheel and empty
`Requires-Python` metadata do not establish Python/Windows compatibility. Synthetic
API tests do not qualify native enumeration or any physical driver.

## Deliberately deferred

The GUI composes the browser and simulated transport. The version 1 `/display`
contract has now produced a real MARS frame with corrected source; owner Windows
screenshots also show ongoing capture, confirmed by the owner as the 0.1.1 ZIP.
MARS continues to own content, selection, order, dwell, live updates and orientation.
No server-side rendering, extra product control endpoint or protocol was added.

Native assembly, smoke, fresh source/notice bindings and portable delivery are
verified for 0.1.1. The [packaging guide](packaging/README.md) records the selected
minimal external-runtime profile, immutable upstream source inputs, strict v2
qualification and complete extraction instructions. Those mechanical checks and
independent source/policy reviews are not legal certification. Original notices,
corresponding source, Chromium resources and validation gates remain included.
No driver, DLL or source-version identity was inferred from a filename.

Owner-run Windows 11 acceptance is still T6: normal Stop/Exit, owned-browser
cleanup, LAN/recovery and aggregate sustained resource measurements. Keep all
auxiliary files; settings persist per user outside the extracted folder. The
unsigned prototype needs no MarsDisplay installer, but the separate official
VC++ prerequisite may require administrator installation.

No model-specific driver has been copied. Real protocol selection and physical
USB testing require identified hardware; simulation must never be shown as a
connected screen. There is no installer, service, autostart, or update mechanism.

## License

GPL-3.0-only; see [LICENSE](LICENSE). This foundation contains no copied driver
code. Future integrations must retain their own license and provenance notices.

</details>
