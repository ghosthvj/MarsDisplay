MarsDisplay portable candidate - Windows 11 x64

Extract the ENTIRE ZIP. Keep README.txt, _internal, LICENSE, notices and source.
Prerequisite: official Microsoft Visual C++ v14 x64 runtime, current 14.51 or newer
(the validated build uses 14.51; older versions are not promised compatible).
If missing, manually download and install it from Microsoft:
https://aka.ms/vc14/vc_redist.x64.exe
MarsDisplay does not download/install prerequisites or redistribute Microsoft DLLs.
Windows 11 provides the OS UCRT/API-set components. No MarsDisplay installer exists.
Open MarsDisplay.exe in an interactive desktop session; capture starts STOPPED.
Configuration saves Native USB only, after explicit USB selection and Save.
Existing Simulation records are not converted merely by opening the application;
legacy schema migration still requires explicit confirmation and a preserved backup.
Native USB supports the qualified 320x480 portrait profile only, not landscape.
While stopped, Enable Brightness appears only when needed and offers explicit
schema-3 migration with a
preserved pre-brightness settings backup; older binaries cannot read schema 3.
The slider selects only 20%, 40%, 60%, 80%, 100% (initially 100%), never zero/off.
Release it or use arrow keys to save that percentage independently of URL drafts.
Start applies the saved choice; live changes wait for a complete image and reuse
the same connection. Stop/Exit sends no brightness restoration. Host-completed is
not a measured panel value. USB failure has no automatic retry/reconnect.
Brightness and schema-1 recovery/export functions remain implemented internally,
but their buttons remain hidden. No advanced menu was added. Keep the previous
working folder as fallback; existing schema-3 settings need no new migration.
--usb-worker is a reserved owned-child route, not an operator command; do not
invoke it manually. Packaged smoke does not establish physical USB acceptance.
Use the tray Status / Settings to configure; Start/Stop control capture, Exit closes.
After a capture error, the configuration window offers both Start capture (explicit
retry) and Stop capture (same action as tray Stop). Stop enables editing only when
cleanup is known; it cannot bypass uncertain cleanup or Exit ownership.
The fixed-height form uses vertical overflow scrolling only when content cannot
fit; Logs, Preview and Save stay fixed in the footer. USB selection and Refresh
share a row with 12px separation. The selector and its open list follow the current
light/dark theme. The redundant internal profile legend is omitted from the form;
the actual USB profile is unchanged. States use icons; transitions show a loading wheel.
The centered compact brightness slider keeps all five percentages without extra
status/explanation text. Logs and Preview are grouped in the footer, apart from Save.
Logs opens the same live native timing report in an independent modeless window;
it does not start capture or issue USB commands.
Preview opens one modeless view of the latest RGB frame accepted by host output.
It updates while visible without another capture/browser or writing images to disk.
Stop retains the last frame; read the lifecycle/live/stale labels, not just the image.
Close/Escape hides only the preview; tray Exit still waits for owned-resource cleanup.
Preview pixels are unscaled (scroll if needed); Windows DPI can affect physical size.
Light/dark mode follows the status window for this session. This is not USB reception.
Settings persist at %LOCALAPPDATA%\MarsDisplay\settings.json outside this folder.
Missing DLL/startup error: check the official x64 VC++ runtime and full extraction;
do not copy random DLLs, disable security, or assume an unsigned prototype is trusted.
External forced Qt/OpenGL debug graphics are unsupported; Chromium resources stay bundled.
Packaged smoke is not Windows 11/LAN/Exit/resource acceptance or legal qualification.
SOURCE ACCESS: see notices/native/SOURCE-ACCESS.txt for full immutable upstream
module source archives, including build/configuration and vendored code. App and
local build-hook source are in source/. Raw terms/copyrights are in notices/.
Keep these source directions adjacent to the binary; redistributors must maintain
equivalent source access under GPLv3 section 6(d), despite artifact expiry.
Unpacked dynamic DLLs remain replaceable. No extra EULA/DRM restricts GPL/LGPL rights.
