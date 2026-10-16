# MarsDisplay foundation

MarsDisplay is a GPL v3 companion foundation for a future Windows 11 x64
MARS display application. **Immutable RGB frames, in-memory simulated output,
and local settings persistence exist today.** There is no application CLI, tray, browser capture, USB
implementation, or Windows executable yet. No screen is needed for these tests.

## Run the source tests

Use Python **3.13.x** (the engineering baseline; currently tested on Linux):

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The tests and public imports use only the standard library. They do not require
installed GUI/browser dependencies, a display server, network, or USB access.

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
**the later lifecycle controller must enforce saving only while stopped** and
keep application startup stopped/unconfigured rather than choosing a URL/device.
Windows filesystem and application acceptance remain separate from Linux tests.

## Dependencies and current verification

`pyproject.toml` is the single source of direct pins. `requirements.txt` selects
the local editable runtime package; `requirements-build.txt` selects its `build`
extra as well. No third-party packages are imported by the foundation itself.

| Purpose | Selected version |
| --- | --- |
| Future browser rendering | Playwright 1.64.0 |
| Future tray/UI | PySide6 6.12.0 |
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

A Linux Qt availability probe currently fails on missing system library
`libEGL.so.1` (`libegl1` on Debian/Ubuntu). GUI tests require that dependency;
standard-library frame, transport and settings tests do not. No system package
was installed automatically.

## Deliberately deferred

Later work must implement the tray/lifecycle and inspect MARS readiness and
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
