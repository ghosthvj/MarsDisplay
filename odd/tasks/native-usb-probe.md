# Native Windows USB fixed-image diagnostic
Prepare a standalone Windows EXE to compare native serial output with the failed browser probe; branch `feat/usb-screen-probe`, baseline `44b0f73`.
Delivery: artifact only for now, no PR/main integration; review strategy `auto-chain`, `chain_strategy=feature-branch-chain` selected by owner (forecast ~750 authored lines, generated fixtures excluded). Runners: existing Python/Playwright and native Windows Framework C# compiler/tests.

## Specs

### S1 — Portable executable
> ok, prepara el .exe

Accepted proposal, verbatim:
> un `.exe` portátil, sin instalar Python ni tocar firmware, para esa prueba

Provide a separate Windows diagnostic executable and a reference image/instructions. Do not change MarsDisplay application behavior or distribute/execute vendor code. Implementation choice: inbox .NET Framework 4.8, with no Python or new runtime installation for the owner. Native Windows compilation, functional tests, downloaded artifact/source/hash verification precede delivery. Windows chooser/WMI and physical rendering remain owner-only acceptance, not CI claims.

### S2 — Controlled native comparison
> el resultado en pantalla es el mismo y este es el mensaje en el navegador: 307222 bytes drained to the serial output; not a rendering ACK. Photograph the screen. Reload only after checking the device.

Accepted diagnostic premise: compare native output with the existing fixed-image probe, not change protocol by guesswork. Freeze its canvas once as embedded RGB565LE and a PNG; record environment/source/hash. Prior owner Windows canvas byte identity is unproven (fonts may differ). Keep portrait 320x480, 16-byte orientation, six-byte header `00 00 04 FD DF C5`, 120 payload writes of 2560 bytes (307222 total), 115200/8N1/RTS-CTS. No HELLO, reset, clear, brightness, power, firmware, automatic retry, or app integration. Drain/close outcomes must not claim panel acknowledgment. Native open/close may change modem control lines.

### S3 — Explicit selection and bounded operation
> ¿Te preparo un `.exe` portátil, sin instalar Python ni tocar firmware, para esa prueba?
> ok, prepara el .exe

Conservative implementation choices: passive inventory, explicit current COM choice plus known VID 1A86/PID 5722/serial USB35INCHIPSV2 metadata verification, reject absent/ambiguous/unhealthy matches; show identity and require typed confirmation. Recheck immediately before open, no first-device fallback. Serial operations have finite write/drain deadlines; supervise only this executable's child process so hidden Framework dispose/flush cannot hang the parent indefinitely. Timeout/failure warns uncertain partial delivery, kills only its own worker, never retries. EOF/cancel/help/self-test never opens a device. WMI failure is actionable without elevation or driver changes; metadata/open hotplug races remain disclosed.

### S4 — Evidence and delivery boundaries
> he descargado la aplicaion que proporcionan en la web www.turzx.com con la aplicacion si funciona correctamente

Vendor rendering is an owner observation, not proof of the native reference. USB-free tests cover exact protocol/options, identity rejection, cancellation, errors, drain/cleanup and owned-worker timeout. Local native RED is unavailable without a C# runner; record this honestly and run actual Windows public-command/compiled harness tests, not string-presence substitutes. Existing Python suite remains a regression gate. Risk: item 4 (owned-worker lifecycle) and item 5 (native build/CI delivery); one independent verifier after source proof. User-owned RDD is currently off; check it, do not start review while off. Use existing origin feature branch for native CI under session delivery permission, no PR/release/tag/main/installer/autostart/global dependencies. Do not publish owner screenshots, hardware metrics, vendor archive or binary copies.

## Tasks

- N0 [S2,S4] route: inline preservation/fixture generation; status: done; commit: `253c8cd3bec7f741bf33f80828af4db85477de9a` (browser slice), fixture commit pending — Preserve verified browser baseline; freeze canonical canvas with PNG/payload/provenance and fixture checks. Risk: none (additive diagnostic fixture).
- N1 [S1–S3] route: delegated writer (runtime context backstop); status: in_progress; commit: pending — Standalone Framework console diagnostic, typed selection, exact image transfer and supervised worker; tests/docs with behavior. Risk: item 4 (own-process lifecycle).
- N2 [S1,S4] route: delegated dependent writer (context backstop), parent CI; status: pending; commit: pending — Isolated pinned Windows workflow/build/USB-free native functional checks and artifact packaging. Risk: item 5 (CI/native delivery); independent check before CI delivery.
- N3 [S1–S4] route: parent + one independent verifier; status: pending; commit: pending — Source checks, existing regression suite, independent verification, native Windows result/download/source/hash validation and owner instructions. Physical image result remains a separate owner check.

## Log

L1 — Owner original request, verbatim: `ok, prepara el .exe`.
L2 — Before writes: current branch feat/usb-screen-probe, HEAD44b0f73, only three historical browser-probe files untracked; existing 165-test suite passed after drain correction. Browser drain correction did not fix hardware. Vendor package static metadata: UsbMonitor2.2.1.0 x64/.NET4.8, referencesSerialPort; not executed here. No exact vendor wire protocol inferred.
L3 — Read-only map mvh33cey-6-n32j: Framework SerialStream.Dispose calls FlushFileBuffers and an unbounded event wait; queue polling alone does not bound close. Same-EXE owned-child supervisor contains application wait. BytesToWrite matches pyserial Windows COMSTAT queue semantics, not panel ACK. Compiler location/runner Framework availability are source evidence only until native CI executes. No local C# compiler/runtime available; no local native RED claim.
L4 — Owner oversized-review choice: `Cadena sobre rama de funcionalidad — recomendado` (`feature-branch-chain`). Cache auto-chain/feature-branch-chain for eventual review; no PR/tracker/main integration created or requested now. Preserve prior browser comparison in one cohesive historical commit (~400 lines), then isolated native work-unit commits. New CI pushes use the existing private/public scope of origin without owner screenshots/vendor assets.
L5 — N0 fixture RED: one test exit1/0.002s missing pattern.json. Generated frozen Linux Chromium156.0.8078.4 canvas from corrected HTML SHA2566a9450539fc60dfe9bd5669392cf52f386b78c275449f03f6f082923733825a8. First check exit1 exposed an extra zero byte in the test's handwritten expected orientation string (not production); corrected to actual16-byte header and Pillow deprecation call. GREEN1/0.057s exit0; all PNG pixels map to307200RGB565LEbytes, palette/geometry/hashes/header/chunk/total checked. PayloadSHA2568cbbb7e39485e211548a4f3f448ca14eeb9358286e5eadf7079a324fdc97ed1d;PNGSHA256d8efdd4339e8c16a8f2b7e1416ec83221403cf6bdc6571ee5ff146113f00cfbc. No USB or browser chooser requested. Canonical fonts differ potentially from owner's original Windows run.
L6 — Preserved historical browser diagnostic as slice1 commit253c8cd3bec7f741bf33f80828af4db85477de9a (428 authored lines, cohesive one tool+tests+guide, modest overage without code shrinking). Existing prior165tests/43.560s remain its evidence; new fixture test added independently. Slice boundary253c8cd; next fixture/native work is a subsequent feature-branch-chain slice. No PR/tracker created.
