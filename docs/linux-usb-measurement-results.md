# First authorized Linux USB measurement

**No observed host-side speedup:** pixel writes took **2404.084 ms** on this
Linux KVM guest, compared with **2400.112 ms** for the previous Windows A run.
These are single observations, not a statistical benchmark or panel-latency test.

## Scope and execution

The owner authorized hardware execution and necessary sudo access:
> adelante, puedes usar sudo si es necesario, haz las mediciones que sean necesarias

Exactly one fixed baseline A frame was sent using the verified source command
from `7cf3921` (repository HEAD at execution: `bed444e`). The command revalidated
VID `1a86`, PID `5722`, serial `USB35INCHIPSV2`, currently `/dev/ttyACM0`.
The agent supplied `SEND /dev/ttyACM0` once for this explicitly delegated run;
this is not an unattended confirmation loop or permission for automatic retries.
The stream matched the Windows grouping experiment: portrait 320x480,
122 writes / 307222 bytes, 115200/8N1, RTS-CTS, DTR asserted, separate open/close.
Opening/closing may affect control lines; host completion is not panel ACK.

Sudo launched `/usr/bin/setpriv`, which dropped privileges before the probe:
UID1000, primary GID20 (`dialout`), no supplementary groups. The probe did not
run as root. Device metadata was identical before and after: owner root,
group dialout, mode0660, same inode and device numbers. No ownership, mode,
ACL, group membership, dependency or driver changes were made.

`setfacl`, `getfacl` and `fuser` were unavailable and were not installed. A direct
sudo run-as-group preflight required a password; none was requested or supplied.
The allowed root-launch/privilege-drop route succeeded. No claim of a global
process-occupancy scan is made; serial exclusivity remains cooperative/advisory.

## Recorded host timings

| Stage | Milliseconds |
| --- | ---: |
| Open | 4.416 |
| Fixture loading/encoding | 37.870 |
| Orientation writes | 0.531 |
| Header write | 6.422 |
| Pixel writes | **2404.084** |
| All writes | 2411.052 |
| Host queue drain | 0.047 |
| Close | 4.004 |

Group timings are subsets of all-write time; do not sum overlapping rows.
Exit status was **0**, stderr empty. The command reports success only after
serial close, valid timing output and known owned-child reap. There was no
second frame or retry. Local raw evidence is retained in excluded
`build/linux-usb-measurement/hardware-1/` (stdout/stderr/exit, invocation,
source HEAD and device metadata before/after).

## Interpretation and next gate

The pixel-stage difference versus Windows A is **+3.972 ms (+0.1655%)**.
This first observation did not show that changing the host OS improves transfer.
It does **not** identify the limiting device, firmware, driver, USB scheduling,
virtualization or passthrough behavior. Linux was running in **KVM**, not bare
metal. It does not establish panel FPS or successful application of a new frame.

**Physical image correctness is awaiting owner confirmation.** The public
reference may already have been on the display, so an unchanged image alone
cannot prove that this frame was applied. Before another send, ask whether the
panel currently shows the correct public reference (TOP/up arrow, corner numbers,
RGB bands and border) and whether any corruption was observed. Stop if the image
is wrong or cleanup is uncertain. No production transport change is justified
by this one comparison.

See [measurement procedure and safety limits](linux-usb-measurement.md).
