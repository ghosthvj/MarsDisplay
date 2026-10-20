# Python USB Probe 1.0.0

A standalone, one-image Python/pyserial diagnostic—not the previously tested C# probe and not application integration. Native packaging (S5) and physical Python acceptance (S6) remain pending. No settings are written and no background service is installed.

## Safe first steps

From the repository root with the existing environment:

```text
PYTHONPATH=src python tools/windows-python-usb-probe/entrypoint.py --help
PYTHONPATH=src python tools/windows-python-usb-probe/entrypoint.py --self-test
```

These commands do not enumerate or open USB ports. Help does not read the image or import pyserial. Self-test verifies the canonical raw image and P1 encoder without Pillow. Runtime pyserial must be version 3.5. The build SDK installation below retains existing pins; the diagnostic itself installs nothing.

On Windows, `--list` lists passive USB descriptors. `--port COM5` requests the current uppercase port; COM5 is only an example. No arguments prompt for a port. Type exactly `SEND COM5` at the confirmation prompt. EOF, an empty port, or any nonmatching confirmation cancels without opening. Unknown options, lowercase ports, combined modes, and private worker flags are rejected.

After a no-argument interactive run finishes, the parent displays `Press Enter to close.` only when stdin is a terminal. This final pause is outside the 90-second child budget; EOF or Ctrl+C preserves the completed exit code. Redirected CI input, help, self-test, listing, explicit `--port`, and the owned child never pause.

The selected port must uniquely resolve `usb:1a86:5722:USB35INCHIPSV2`, with no conflicting COM occupant. Inventory is refreshed after confirmation. Descriptor metadata cannot prove physical ownership or device health; native pyserial observations and actual rendering still require owner qualification.

## Fixed transfer and messages

The only image is `tools/windows-usb-probe/pattern.rgb888` (460800 bytes; SHA256 `19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40`). `encode_portrait(RGBFrame(320, 480, raw, 0))` produces 122 immutable packets. The encoded payload must hash to `8cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d` before inventory or opening. The fixed raw-file read is capped at 460801 bytes (expected size plus one), so oversized files are rejected without an unbounded read.

Settings are 115200 baud, 8N1, RTS/CTS enabled, DSR/DTR flow control disabled, DTR set before open, three-second write timeout, one-second unused read timeout. Each packet is written once; short/None/error returns fail without retry. Queue-empty polling has a 15-second deadline, never `flush()`. Every created serial object receives one close attempt. No reads, HELLO, reset, brightness, power, arbitrary image input, or protocol experiments exist.

| Exit | Exact result/error text |
| --- | --- |
| 0 self-test | `Self-test passed: 122 packets, 307222 bytes; no USB access.` |
| 0 transfer | `Host transfer complete: 122 packets, 307222 bytes; not a rendering ACK.` |
| 0 cancellation | `Cancelled; no device opened.` |
| 2 | `Invalid arguments; use --help.` |
| 3 | `Cannot list USB serial descriptors; no transfer started.` |
| 4 | `Current COM port must uniquely match the known USB identity; no device opened.` |
| 5 | `Fixed image verification failed; no device opened.` |
| 6 | `Transfer failed; delivery uncertain. Do not automatically resend.` |
| 7 | `Worker or Windows isolation failed; delivery uncertain. Do not automatically resend.` |
| 8 | `Worker timed out and was stopped; delivery uncertain. Do not automatically resend.` |

Prompts are `Current uppercase COM port (empty to cancel): ` and `Type SEND COMn to send the fixed image: `. Listing prints one `COMn identity` line per observation, using `(no stable identity)` when absent. Errors go to stderr; normal output and prompts go to stdout. Success means all 307222 bytes were accepted, the output queue became empty, and close succeeded—not a display ACK. Never automatically resend after uncertainty.

## Packaging preparation status

The source build pipeline is implemented, but **no qualified Windows Python EXE or ZIP has been observed yet**. Native CI must run before delivery. Native job/event/frozen-child qualification (S4) and owner physical acceptance (S6) remain pending; passing portable fake-provider tests does not close either gate.

`qualification.py` keeps `sdk_origin_facts(runtime, origins, sdk)` permanently facts-only and `UNQUALIFIED`. A separate profile composes those facts with actual Analysis/PYZ module inventories, x64 PE/hash/version measurements, installed package notices, generated Windows SDK LICENSE, and the console bootloader's actual EXE input, installed RECORD and distribution fingerprint. Only that profile can qualify publication. Unknown native files, mismatched hashes or missing component terms/source-version references fail closed. OpenSSL must match the existing reviewed supplemental hash/version policy; no empty Qt inventory or full-app v2 approval is fabricated. The probe-only `cpython_material.py` validates a pinned offline manifest and every raw SHA256/Git blob in `native-material/`. The original generated SDK LICENSE is retained byte-for-byte; missing notices are supplemented, never inferred from notice wording.

The snapshot covers only CPython **3.13.16**, source commit `cbc944f4bc59639a444dd971c737788ba2283a91`, and eleven independently compared official Windows amd64 embed members. Every new build must match their hashes, Analysis SDK paths and PE facts. Release recipes bind builtin zlib 1.3.1 and Unicode/str to `python313.dll`, external Windows mpdecimal 4.0.0 to `_decimal.pyd`, bzip2 1.0.8 to `_bz2.pyd`, and xz/liblzma 5.2.5 to `_lzma.pyd`. Unicode notices also cover `unicodedata.pyd`. Expat was measured but not shipped; adding it or any unknown member fails closed pending a new reviewed snapshot.

libffi 3.4.4 has no PE version. Its exact official member bytes were independently compared with `python/cpython-bin-deps` commit `94cb9a1c7feb608adf2b9f8fe2dbd6925ffbf90d`, blob `8ebbbe8d5f3be43c2c27a2454e76d809954185fd`; notice text is not version evidence. OpenSSL still requires the unchanged global exact-byte/version/source policy in addition to the official member comparison.

The compact manifest records archive/member comparisons, immutable source commits, and raw-file SHA256/Git blobs. Raw URLs are reconstructed as `https://raw.githubusercontent.com/<repository>/<commit>/<upstream_path>` from its source/file tables. `source.zip` carries the helper and complete verified bundle, including `.gitattributes` (`* -text`) to preserve Windows checkout hashes. Supplementary upstream package notices do not assert that their tools or bindings are shipped. No downloaded DLL, archive or recursive Git API tree is included, and builds perform no evidence downloads. Updating this snapshot requires fresh independent evidence and a reviewed manifest/helper pin change; no SDK fallback is allowed.

The future package must use the same external prerequisite as the application: **official Microsoft Visual C++ v14 x64 runtime, version 14.51 or later**. Installation is manual, from Microsoft; the diagnostic must not install it automatically, copy System32 DLLs, or bypass Windows security controls. Sources and terms for CPython and bundled components, pyserial 3.5, and PyInstaller 6.22.3 (including its bootloader exception) must accompany qualified delivery. Supplementary registry license texts do not imply those packages are installed or shipped.

## Build or rebuild on native Windows x64

Use a fresh clean checkout at the recorded source Git SHA, or extract the delivered `source.zip` into a fresh directory. The source archive includes a hash-bound `SOURCE-PROVENANCE.json`; rebuilds without Git verify that manifest. Its root README is this diagnostic guide, not the application's owner-observation history. Do not edit the source or reuse an old output directory during a build.

With Python 3.13.16 x64 installed, run from that source root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install '.[build]'
.\.venv\Scripts\python.exe -B tools/windows-python-usb-probe/build_probe.py
```

The existing development SDK includes Pillow for fixture tests, plus application dependencies. No Chromium download is needed. The frozen diagnostic imports only its console entrypoint and required CPython/pyserial modules; Pillow, Qt, Playwright, Chromium, Node and build/legal helpers are not runtime dependencies. PyInstaller 6.22.3 and pyserial 3.5 pins are unchanged. `build_probe.py --help` documents the no-option build interface; `smoke.py` separately runs the selected source suites on native Windows.

The builder runs the fixture, encoder, diagnostic, owned-process and packaging suites on the actual SDK, rejecting every skip. It excludes Microsoft runtime DLLs during Analysis, records native origins and actual PYZ contents, compiles `PythonUsbProbe.exe`, qualifies native sources/terms, extracts a trial runtime archive, and compares source/frozen safe commands under isolated HOME/TEMP and system-only PATH. Both redirected EOF and passive listing exercise the inherited child streams. Separate helper-only checks cover frozen gate release/job-close termination and parent-death ownership; no public hang flag or SEND confirmation is used.

Outputs are exclusively owned and never overwritten:

- `build/python-usb-probe/PythonUsbProbe-1.0.0-Windows-x64.zip`
- The adjacent `.zip.sha256` and unpacked `PythonUsbProbe/` folder.
- On failure, only `build/python-usb-probe-work/unqualified.json` is eligible for CI upload. It contains native hashes/PE facts, SDK license text and sanitized failure metadata—not binaries. Use a fresh checkout/output location for another build; stale evidence is rejected.

The qualified ZIP contains the console onedir runtime, `pattern.png`, README, GPL license, dependency/native notices, `source.zip`, source hashes, test evidence, native profile, inventory and `SHA256SUMS`. Diagnostic version **1.0.0** is distinct from application version **0.1.4**; the inventory binds the actual source commit and compiler/SDK facts. ZIP metadata for the source archive is deterministic; this does not claim byte-reproducible compiler output across SDK patches.

The dedicated **Windows Python USB fixed-image probe** workflow uses `windows-2025` and the existing pinned actions. Only successful native qualification and smoke permit the seven-day `PythonUsbProbe-Windows-x64` ZIP/checksum artifact. Failed builds upload metadata only. No binary is ready for the owner until the parent verifies the downloaded archive, source binding, notices and hashes.

## Use a qualified package

1. Obtain the parent-verified ZIP and compare its SHA256 with the adjacent sidecar using `Get-FileHash -Algorithm SHA256`.
2. Extract the entire ZIP into a new directory; retain `_internal`, notices and source material. Never copy only the EXE or mix versions.
3. Run `PythonUsbProbe.exe --help`, then `PythonUsbProbe.exe --self-test`. These are USB-free.
4. Only the owner proceeds with passive `--list`, explicit current-port selection and typed confirmation as described above. Supply the console result and a photo matching `pattern.png`; CI success is not a rendering ACK.

Corresponding upstream source access is listed in `SOURCE-ACCESS.txt`, installed notices and `native-profile.json`. Redistributors must retain equivalent complete source access alongside the binary, including after Actions artifact expiry; keep original copyrights and the PyInstaller bootloader exception. Supplementary license-registry texts do not assert that Qt or browser packages are shipped.

## T3 build and native qualification contract

- Freeze `entrypoint.py` as a console program. Bundle the raw fixture at `sys._MEIPASS/probe-assets/pattern.rgb888`; include provenance/reference/legal materials in the later audited payload. Do not ship Pillow or Qt.
- Source launch vector: `[sys.executable, '-B', absolute_entrypoint, *public_args]`, with `src` on PYTHONPATH. Frozen launch vector: `[sys.executable, *public_args]`, never frozen Python `-m`.
- `main()` is the production interface. `run()` is the already-isolated core with injected input/output, inventory, serial factory, fixture loader, clock and sleep for tests. Do not wire `run()` directly into the application.
- The parent creates one random 32-hex environment marker, a named manual-reset event, and a Windows kill-on-close job. It starts one child with explicit `stdin=sys.stdin`, `stdout=sys.stdout`, and `stderr=sys.stderr` handles, assigns it to the job, then signals the gate. This preserves redirected parent streams without creating additional pipes. The child consumes its marker, parses the same public arguments and waits at most five seconds for the gate before any device access. The marker is an accidental-entry guard, not local-owner authentication.
- Parent budget is 90 seconds including confirmation, with at most two seconds to reap a timed-out child. Only the owned Popen is killed; no process scanning. Killing the parent closes the job and terminates its assigned child. Assignment/start/gate failures fail closed. No persistent IPC or test-only hang CLI exists.
- Native Windows CI must qualify the actual job/event ABI, source and frozen self-launch, inherited redirected input, timeout/reaping, parent death, and fake-port options. Linux fakes and skipped Windows cases are not native or hardware proof.

Keep the working C# diagnostic and Simulation as rollback. The owner must still run the new source-bound packaged Python executable and supply its console result and matching reference photo before P2 can be accepted.
