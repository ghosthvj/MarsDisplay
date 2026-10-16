# MarsDisplay foundation

MarsDisplay is a GPL v3 companion foundation for a future Windows 11 x64
MARS display application. **Immutable RGB frames, in-memory simulated output,
local settings persistence, a lifecycle coordinator, and an injectable Qt tray
shell exist today.** There is no application entry point, browser capture, USB
implementation, or Windows executable yet. No screen is needed for these tests.

## Run the source tests

Use Python **3.13.x** (the engineering baseline; currently tested on Linux):

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

The tray tests require the pinned PySide6 dependency and Qt system libraries.
They exercise real widgets using the offscreen Qt platform, without a display
server, browser, network, or USB access. Other modules/tests use the standard
library. Offscreen success does not prove Windows tray integration.

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

## Capture lifecycle boundary (no browser yet)

`mars_display.lifecycle.Coordinator(store, source_factory, transport_factory)`
is an injectable coordinator, not an application entry point. Later application
integration must use `SimulatedTransport` as its transport factory; device identity
is saved only and never selects a protocol or opens USB.

```python
from mars_display.lifecycle import Coordinator

# Implement a synchronous source factory in the later browser integration:
# coordinator = Coordinator(store, source_factory, SimulatedTransport)
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

## Injectable tray shell (not a runnable application yet)

`mars_display.tray.create_shell(app, store, coordinator_factory)` assembles the
tray only after acquiring a per-user `QLockFile` beside `store.path`. It returns
`None` if another instance owns the lock, without invoking the coordinator factory.
The caller should report “MarsDisplay is already running” and exit that launch.
Lock/access and corrupt-configuration errors propagate to the caller for startup
reporting; no silent configuration repair occurs. Retain the returned shell for
its entire event loop.

Future browser-entrypoint assembly (not executable until that adapter exists):

```python
from PySide6.QtWidgets import QApplication
from mars_display.tray import create_shell

# app = QApplication(...)
# shell = create_shell(app, store, lambda: Coordinator(
#     store, actual_browser_session_factory, SimulatedTransport))
# if shell is not None:
#     app.exec()
```

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
extra as well. Only the tray module imports Qt; the core remains GUI-independent.

| Purpose | Selected version |
| --- | --- |
| Future browser rendering | Playwright 1.64.0 |
| Tray/UI | PySide6 6.12.0 |
| Future image handling | Pillow 12.3.0 |
| Optional future executable packaging | PyInstaller 6.22.3 |
| Source build backend | setuptools 84.0.0 |

The backend pin was checked against authoritative
[PyPI JSON metadata](https://pypi.org/pypi/setuptools/84.0.0/json): Python >=3.10
and a `py3-none-any` wheel. The selected stack candidates have published Windows
x64 wheels per the initial dependency investigation; wheel availability is **not**
installation, interoperability, or Windows acceptance evidence. These declarations
are not a complete transitive lock. The pinned editable package and build extra
were installed successfully in a repository-local `.venv` on Linux, producing an
editable wheel. System Python was not modified. Windows executable/ZIP packaging,
Chromium inclusion and packaged runtime compatibility remain unverified.

Linux Qt offscreen availability passed after the explicitly authorized
installation of `libegl1` and its required dependencies. A sandbox-enabled
Chromium local screenshot also passed using the repository-local browser.
These probes establish tooling availability, not Windows tray, real MARS,
packaged-runtime or physical-screen acceptance.

## Deliberately deferred

Later work must assemble the browser entrypoint and implement MARS readiness and
`/display` capture contracts. MARS will continue to own content, order, dwell,
live updates, and orientation. Local rendering must not add server-side work.
Windows packaging must bundle Chromium and retain dependency licenses/notices;
portable ZIP smoke tests and owner-run Windows acceptance remain separate work.

No model-specific driver has been copied. Real protocol selection and physical
USB testing require identified hardware; simulation must never be shown as a
connected screen. There is no installer, service, autostart, or update mechanism.

## License

GPL-3.0-only; see [LICENSE](LICENSE). This foundation contains no copied driver
code. Future integrations must retain their own license and provenance notices.
