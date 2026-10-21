# Fixed USB grouping protocol and private worker

This experimental core does not change normal MarsDisplay behavior. It is not a
standalone operator interface or permission to execute against hardware. The
agent does not run real USB tests; physical panel correctness remains unverified.

## Fixed public frame

`mars_display.usb_grouping_profile` is Qt-free and contains only the fixed fixture
loader and trusted encoders. There is no arbitrary chunk size or saved profile.

| Arm | Orientation | Header | Payload writes | Total |
| --- | --- | --- | --- | --- |
| A | 16 bytes | 6 bytes | 120 × 2560 bytes | 122 writes; 307222 bytes |
| B | 16 bytes | 6 bytes | 60 × 5120 bytes | 62 writes; 307222 bytes |

B concatenates adjacent baseline payload packets. The full streams are identical.
The baseline encoder remains unchanged. Neither arm changes baud/CTS, firmware,
brightness, power, orientation mode, or drivers.

- Source fixture: `tools/windows-usb-probe/pattern.rgb888`.
- Frozen resource: `sys._MEIPASS/grouping-pattern.rgb888` (no fallback/search).
- Required size: 460800 bytes. SHA-256:
  `19edb4162586afb859c062b82a4c26b54d7329dc3303205628ad61ab1558ef40`.
- Shared seam: keyword-only trusted Python `usb_worker.run_session(...,
  encoder=encode_portrait)`. The default is unchanged; no normal CLI, environment,
  or settings selector was added.

## Private bootstrap and ownership

`mars_display.usb_grouping_worker.main` handles exactly
`--grouping-worker A|B COMn loopback-port 64-lowercase-hex-nonce`.
These arguments alone grant no admission. Invalid arguments and Qt/settings
preimports are rejected before admission, socket access or device enumeration.
Private rejection is silent (exit 2). The normal worker CLI cannot select the
experiment. After admission the child independently validates the public fixture
before socket/device access. It imports the profile, not an operator console.

The owning caller uses `UsbTransport` launcher injection, `OwnedWorker`, Windows
admission/job ownership, strict IPC, identity checks, short-write rejection and
existing safety budgets. The child revalidates the confirmed COM at OPEN and
again before sending: a move or competing occupant is rejected, not followed.

## Frozen-delivery qualification boundary

A separate frozen executable must dispatch the private route **before any
Qt/settings import**; do not modify normal application dispatch. Source tests use
test-owned fake ports, real framing, and an injected Python-only launcher/admission
fixture. They **do not prove native Windows job assignment, frozen bootstrap
behavior, or physical panel correctness**. T2/T3 must qualify separate console
packaging, licenses, source manifest/hash, help/self-test/private rejection,
admission and owned-reap on Windows.

## Native qualification profile

The explicit `usb-grouping-v1` inventory/material profile admits only the fixed
Core/Gui/Widgets guard runtime and complete reviewed optional dependency closures.
Unknown or incomplete native closures fail closed. Existing `portable` defaults
still require the full original policy; experiment qualification does not weaken
normal package checks or claim absent browser components are bundled.

A rejected experimental native closure reports bounded JSON differences after
`Unmapped experimental native payload:`: `missing_required`, `network_missing`,
`ssl_missing` contain only fixed expected paths, and `unexpected_count` counts
unrecognized components without disclosing their names. This is failure evidence,
not permission to omit dependencies or bypass source/hash/license qualification.

The experimental recipe explicitly collects Python's standard-library `ssl` module
to include the complete reviewed Python OpenSSL pair (`libssl-3.dll` and
`libcrypto-3.dll`). Hashing alone can collect only the crypto library. This is a
packaging dependency, not a network operation or a relaxation of native checks.
