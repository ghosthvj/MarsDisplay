# Experimental Linux source runtime

The source application admits non-root Linux x64 and composes the Linux USB
backend, XDG settings and tray presentation at the application boundary.
This is **not AppImage, desktop or hardware qualification**. Windows defaults
and packaging are unchanged. See the [source-run requirements](../README.md#experimental-linux-source-run)
for manual launch, system tray and existing serial-permission prerequisites.

Real or effective UID 0, unavailable credentials, and unsupported hosts are
rejected before Qt or settings construction. Unsupported hosts report
`MarsDisplay requires Windows or Linux x64.` Credential rejection reports
`MarsDisplay requires a non-root Linux user; cannot verify safe user credentials.`
A missing Linux tray reports
`A system tray is required; run MarsDisplay in an interactive Linux session.`
There is no simulation or window fallback. Windows login controls are hidden on
Linux; capture-on-launch is independent, opt-in and not OS-login registration.

## Ownership and admission

`linux_usb_transport.create_transport` composes the existing `UsbTransport`
with the Linux supervisor. Only the supervisor launches the worker, using an
explicit argv list without a shell. Source launch retains
`sys.executable -m mars_display.linux_usb_worker`; frozen launch uses the same
`sys.executable` directly with the private vector. Its inherited connected
control socket, nonce, expected parent PID and finite absolute startup deadline
are private prerequisites, not user configuration. There is no tty argument,
public test switch, environment token, or manual admission bypass.

The worker rejects malformed/manual invocation quietly with exit code 2 before
inventory, serial or data-channel effects. It requires non-root Linux, excludes
GUI/settings imports, arms parent-death protection and awaits supervisor release
before connecting to owned loopback IPC. Session success/failure uses the existing
fixed replies and exit codes; private arguments and backend errors are not logged.
The frozen flag grants no admission and bypasses none of these checks.

The persistent creating supervisor must survive through confirmed child reap.
Cancellation registered before release prevents admission; release winning that
race can permit effects before termination. Timeouts bound caller waits, not
kernel scheduling or kill/reap latency. Uncertain cleanup retains ownership and
blocks reopening; it is not treated as success. No frames are automatically retried.

The application enables graceful Stop for admitted frame/brightness commands on
both Linux and Windows: finish within the original command deadline, then close.
Startup cancellation remains immediate, and explicit transport close can still abort
an in-flight command. Direct transport callers retain immediate cancellation unless
they explicitly opt in. No device reset, serial-option change or panel acknowledgment
is introduced; physical Stop/restart behavior still requires hardware qualification.

## Early frozen dispatch contract (not yet qualified)

`packaging/linux/usb_bootstrap.py` implements the Linux-private runtime hook.
A future Linux packaging recipe must register it **before Qt/default GUI runtime
hooks**. The hook passes the exact six-argument private vector to the existing
guarded `linux_usb_worker.main`:

```text
--linux-usb-worker PORT NONCE CONTROL_FD PARENT_PID ABSOLUTE_DEADLINE
```

These are supervisor-owned values, not a manual-launch interface. The hook exits
with the worker result; worker/import failures exit quietly with code 2, even
without stdout/stderr. Any argument starting with `--linux-usb-worker` or the
Windows route `--usb-worker` reserves the launch: malformed prefixes, misplaced
routes, extra/missing arguments and mixed routes never fall through to the GUI.
Value validation and inherited admission remain owned by the worker. Ordinary
arguments pass through without application, Qt or settings imports or startup.
No public help option or admission bypass is added.

Source tests execute the hook and simulate `sys.frozen` in callable worker tests.
They do **not** prove PyInstaller runtime-hook ordering or inherited descriptor
survival. T5 must qualify both in an actual frozen build; no Linux spec, AppDir or
AppImage recipe is provided here. Source GUI admission does not qualify frozen launch.

## Serial scope and limits

Only the existing exact `usb:1a86:5722:USB35INCHIPSV2` identity is accepted, uniquely
observed on `/dev/ttyACM[0-9]+` with no duplicate observed occupancy. There is no
first-tty, COM, ttyUSB or user-selected path fallback. The lazy pyserial adapter
preserves the shared serial options and forces `exclusive=True`. It rechecks
identity after open and closes on mismatch or failed open; shared fresh checks
remain before frame, timed/grouped frame and brightness writes.

Exclusivity is advisory, not protection against non-cooperating processes.
Inventory snapshots and post-open checks cannot eliminate hotplug races or prove
that the open descriptor still represents the observed physical panel. Host write
completion does not prove display output or brightness. No root execution, chmod,
udev installation or automatic permission changes are provided.

## Evidence boundary

Deterministic tests use fake inventory/serial, including real admitted child
processes and blocked native-operation simulations. They do not access a panel.
Independent verification of admission and concurrency remains required. Native
Windows regression, Pop!_OS desktop acceptance, real hardware checks
and AppImage packaging/clean-machine validation remain separate pending work.
Offscreen GUI composition tests do not establish a usable native tray or confirm
the target desktop/session.
