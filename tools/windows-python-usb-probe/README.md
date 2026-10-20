# Python USB Probe 1.0.0

A standalone, one-image Python/pyserial diagnostic—not the previously tested C# probe and not application integration. Native packaging (S5) and physical Python acceptance (S6) remain pending. No settings are written and no background service is installed.

## Safe first steps

From the repository root with the existing environment:

```text
PYTHONPATH=src python tools/windows-python-usb-probe/entrypoint.py --help
PYTHONPATH=src python tools/windows-python-usb-probe/entrypoint.py --self-test
```

These commands do not enumerate or open USB ports. Help does not read the image or import pyserial. Self-test verifies the canonical raw image and P1 encoder without Pillow. Runtime pyserial must be version 3.5; dependency installation is outside this unit.

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

## T3 build and native qualification contract

- Freeze `entrypoint.py` as a console program. Bundle the raw fixture at `sys._MEIPASS/probe-assets/pattern.rgb888`; include provenance/reference/legal materials in the later audited payload. Do not ship Pillow or Qt.
- Source launch vector: `[sys.executable, '-B', absolute_entrypoint, *public_args]`, with `src` on PYTHONPATH. Frozen launch vector: `[sys.executable, *public_args]`, never frozen Python `-m`.
- `main()` is the production interface. `run()` is the already-isolated core with injected input/output, inventory, serial factory, fixture loader, clock and sleep for tests. Do not wire `run()` directly into the application.
- The parent creates one random 32-hex environment marker, a named manual-reset event, and a Windows kill-on-close job. It starts one child with explicit `stdin=sys.stdin`, `stdout=sys.stdout`, and `stderr=sys.stderr` handles, assigns it to the job, then signals the gate. This preserves redirected parent streams without creating additional pipes. The child consumes its marker, parses the same public arguments and waits at most five seconds for the gate before any device access. The marker is an accidental-entry guard, not local-owner authentication.
- Parent budget is 90 seconds including confirmation, with at most two seconds to reap a timed-out child. Only the owned Popen is killed; no process scanning. Killing the parent closes the job and terminates its assigned child. Assignment/start/gate failures fail closed. No persistent IPC or test-only hang CLI exists.
- Native Windows CI must qualify the actual job/event ABI, source and frozen self-launch, inherited redirected input, timeout/reaping, parent death, and fake-port options. Linux fakes and skipped Windows cases are not native or hardware proof.

Keep the working C# diagnostic and Simulation as rollback. The owner must still run the new source-bound packaged Python executable and supply its console result and matching reference photo before P2 can be accepted.
