# MarsDisplay foundation

MarsDisplay is a GPL v3 companion foundation for a future Windows 11 x64
MARS display application. **Only immutable RGB frames and in-memory simulated
output exist today.** There is no application CLI, tray, browser capture, USB
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

## Dependency declarations, not installation proof

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
are not a complete transitive lock. Package installation/build proof is pending;
the source-test interpreter has no pip/setuptools and was not modified.

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
