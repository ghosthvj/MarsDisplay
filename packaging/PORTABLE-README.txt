MarsDisplay portable prototype - Windows 11 x64

Extract the ENTIRE ZIP. Keep README.txt, _internal, LICENSE, notices and source.
Prerequisite: official Microsoft Visual C++ v14 x64 runtime, current 14.51 or newer
(the validated build uses 14.51; older versions are not promised compatible).
If missing, manually download and install it from Microsoft:
https://aka.ms/vc14/vc_redist.x64.exe
MarsDisplay does not download/install prerequisites or redistribute Microsoft DLLs.
Windows 11 provides the OS UCRT/API-set components. No MarsDisplay installer exists.
Open MarsDisplay.exe in an interactive desktop session; capture starts STOPPED.
Output is SIMULATED ONLY; no USB screen is connected or driven by this prototype.
Use the tray Status / Settings to configure; Start/Stop control capture, Exit closes.
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
