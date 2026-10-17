# MarsDisplay themed status window
Implement the approved light/dark reference in Qt Widgets with native window controls.
Baseline: `916a9be08e51d7ea25a4d3fb9d4623754494f5f9`; branch `feat/simulated-companion`; retain accepted 0.1.2 as the testing baseline until a verified 0.1.3 portable is available.

## Specs

### S1 — Authorization
> ok, me parece bien,  podemos implementarlo

Implement the previously discussed reference UI, not a new capture stack or product control API.

### S2 — Reference appearance and controls
> que te parece este diseño, es posible replicarlo para MarsDisplay.exe

References: private owner images `paste-20261017-223052-b2f69189.png` and `paste-20261017-223350-0241bb24.png`, already viewed; never publish their bytes or embedded private URL. Reproduce the light/dark teal palette, status heading, lifecycle card, labeled status rows, configuration/device card and explanatory Save footer closely, not pixel-identically across OS/DPI. Keep the native Windows titlebar. Offer a per-session light/dark selector, initially light; do not change the settings schema or write theme preferences. Use existing Qt Widgets and painted icons only, no new dependencies/webview/fonts. Preserve simulated/no-USB and read-only device indications.

### S3 — Preserve application boundaries
> si, te autorizo, NO me pidas mas autorizaciones simples como estas, no pares a no ser que sea algo importante!

Existing companion specs S1,S4,S8–S10,S15 remain binding: startup stopped; close/Escape hides the dialog and keeps the tray; one instance; existing tray Start/Stop/Exit remain authoritative. The new capture button delegates to those same operations and enablement, including starting/running/retrying/stopping/error/exit. User URL editing and saving only while stopped; invalid/rejected saves preserve stored bytes and counters. Distinguish current status hints, runtime errors and successful-save feedback; do not show stale success text claiming capture remains stopped while running. Retain all source/output/live/stale/retained-frame semantics. No browser, retry, protocol, MARS, settings-format or hardware changes.

### S4 — Verified portable delivery
> ok, mantengamos la propuesta de desarrollar desde linux y generar el ZIP desde GitHub Actions para hacer las pruebas locales antes de generar un instalador

Existing feature-branch push/Windows CI/seven-day test-artifact authorization continues. Prepare 0.1.3 without changing dependency pins/runtime profile/qualification/workflow. Run deterministic test-first rules, existing tray/app checks, offscreen visual inspection in both themes/states and a small-window check; compare existing shared public behavior against the baseline. Independently verify named Risk3 UI/coordinator seams once at feature end. One Windows build after local proof; download and validate source/version/hashes/notices/profile. Linux previews and Server CI are not owner Windows11 visual/DPI acceptance. No main/PR/release/installer/USB scope.

## Tasks

- U1 [S1,S2,S3] route: inline; status: done; commits: theme `3001de1e227fef6d1e4174daefaebe3179c3dffe`, layout `cc889541b7e308d82497a5e0bc4cef16f6ed15d8` — Reference layout and light/dark themes, preserving existing tray interactions. Risk: item 3 (shared status/settings widgets). Tests/docs with behavior; target <=400 authored diff lines.
- U2 [S1,S2,S3] route: inline after U1; status: done; commit: pending — Bind capture button, state badges, readonly/save hints and transient feedback to existing public lifecycle actions; test requested rules and old action paths. Risk: item 3 (shared UI/coordinator boundaries).
- U3 [S1–S4] route: parent checks plus one independent Risk3 verifier, native Windows CI and artifact checks; status: in_progress; commit: pending — Full suite/differential/visual proof, 0.1.3 delivery and docs. Preserve accepted 0.1.2 evidence; no native review while user-owned switch is off.

## Log

L1 — Owner, verbatim: `ok, me parece bien,  podemos implementarlo`.
L2 — Both light/dark references were consumed in the previous discussion. Owner accepted the native-titlebar recommendation and adaptations for stopped/retrying/error states. Current UI is QtWidgets QDialog/QFormLayout; settings JSON admits exactly three existing keys, so theme remains per-session. Source/UI contracts explored before writes. Official Qt for Python Context7 docs confirm QScrollArea widgetResizable, scoped stylesheet selectors and dynamic-property recomputation. Work is large by external Windows delivery/continuity, not file count. One dependent UI feature: no independent writer units; parent inline. Two cohesive source commits protect review size; no pushes between them, one final CI candidate. No private screenshot assets or URLs in source/previews.

L3 — Test-first RED: both new theme/layout rules failed as expected (2tests/0.016s, exit1: no theme property/window icon). Honest review slicing refined before implementation: U1 uses two cohesive source units, per-session theming first, then reference layout; U2 binds controls afterward. Temporarily keep only the theme regression in the first unit so no failing layout test is committed; the exact observed layout regression is retained for the next unit. All source commits stay local until the final single Windows candidate.

L4 — Theme unit GREEN:10traytests/0.656s exit0, including new real-palette light/dark roundtrip/hide-reopen/new-dialog-default, unchanged settings bytes/zero frames/no source start. Existing nine tray/lifecycle/guard/error/save tests pass; offscreen tray warnings remain environmental. README documents per-session theme and old portable boundary. U1 remains in progress for reference layout. No full-suite repeat or remote push at this intermediate unit; final independent/source/app/visual checks remain U3.

L5 — Theme unit committed `3001de1e227fef6d1e4174daefaebe3179c3dffe` (177add/2delete). Exact retained layout regression rerun RED1/0.011s exit1 (missing native window icon), then layout GREEN11traytests/0.686s exit0. Native titlebar/painted monitor icon/plain-text fields, scrollable body/fixed footer and small-window accessibility checks passed; prior nine lifecycle/guard/tray cases preserved. U1 done for its scoped layout/theme checks; U2 in progress, independent/full/app/visual/Windows proof remains U3. Layout source commit below; no push yet. Todo display positions are not stable task IDs: current actual IDs9/10/11 resolved with list after a harmless invalid note update to#1.

L6 — Layout unit committed `cc889541b7e308d82497a5e0bc4cef16f6ed15d8` (137add/34delete). U2 five-rule RED5/0.199s exit1 (capture button absent, URL not readonly, unformatted7045); GREEN16traytests/1.198s. Final focused tray+real-browser app integration26/3.596s exit0: native Escape hides, saved feedback clears on capture, runtime error clears after Stop, error footer explicitly points to tray Stop for editing, capture button preserves start/stop/retry/exit guards and counters/settings. Displayed operation determines click intent, so queued Stop never becomes Start. Ready/error text and color remain distinct; state tone repolishes only when changed, themes only on toggle. Version-only0.1.2→0.1.3; no dependency or backend changes. U2 done for scoped checks; U3 in progress for full/differential/visual/independent/Windows proof. No remote push yet.
