# Windows layout diagnostics

Capture the existing small-desktop regression's layout tree and screenshot using
isolated test settings. This does not open USB, capture a browser, package the
application, or qualify an executable. Do not use real user settings.

## Run on Windows Actions

Dispatch `windows-portable.yml` on an explicitly selected, pushed source commit's
branch with `layout_diagnostics=true`. Bind the resulting run to that exact SHA.
The default is `false`: ordinary portable builds keep their existing steps.

Diagnostic mode installs the same pinned SDK, then runs only the fixed-form
UI tests. It skips Chromium installation, the full source suite, native packaging,
and portable upload. The named `MarsDisplay-UI-layout-diagnostics` artifact contains
only `layout.json`, `layout.png`, and `test-result.json`, retained for seven days.
The test exit code is preserved: a red run can contain useful failure diagnostics.
A diagnostic artifact is never a portable release or a successful UI qualification.

## Font prerequisite

Windows `offscreen` uses Qt's FreeType database, which scans `QT_QPA_FONTDIR`
instead of the native Windows font registry. Both offscreen CI steps point it at
`C:/Windows/Fonts`. Without fonts, replacement boxes can inflate layout minimums;
the font regression rejects an unresolved family or missing printable glyphs.
Fonts are loaded from the runner OS, not copied, installed, or shipped. Native
packaging still clears `QT_*` variables before its existing build and smoke steps.

## Run locally

From the repository root, set `QT_QPA_PLATFORM=offscreen`,
`PLAYWRIGHT_BROWSERS_PATH=0`, and `PYTHONPATH=src:tests` (`src;tests` on Windows),
On Windows, also set `QT_QPA_FONTDIR=C:/Windows/Fonts` before starting Python,
then run `python -B tools/windows-layout-diagnostics/diagnose.py`.
Files go to `build/windows-layout-diagnostics/`. Use a fresh diagnostic directory
for each run; compare the root body minimum with the recorded row/child minimums,
resolved font metrics, and viewport dimensions. The screenshot contains synthetic
fixture values only. The failing test's assertions are not suppressed or changed.
