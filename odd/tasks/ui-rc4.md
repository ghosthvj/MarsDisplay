# Windows UI follow-up candidate 0.2.0rc4
Remove the redundant profile legend and deliver the approved USB selector polish in a new portable candidate.
Branch `feat/brightness-slider`; baseline `118d17f3dc1a76484eb2690cc18fdc3b9e7b6b91`. Preserve unrelated Linux measurement edits/private files; no release, merge or PR.

## Specs
S1 — User: `si, quita ese texto y cuando termines manda a crear el EXE`. Remove only the visible `Native USB · tus35-portrait-v1 · 320 × 480 portrait` legend; preserve the internal profile, explicit selection/Save/Start, saved brightness and recovery safeguards. Build a distinct 0.2.0rc4 candidate through the existing Windows workflow and verify the complete portable ZIP.
S2 — Earlier user: `Cuando pongo el modo Oscuro, el desplegable para seleccionar los dispositivos USB se ve blanco y el texto también` and `además el desplegable y el boton Refresh USB identities están muy pegados, dale algo de separacion.` Include the already authorized selector/open-list theme correction and 12px spacing, without capture/settings behavior changes.

## Tasks
- T1 [S1,S2] route: inline focused UI correction and tests; status: done — focused63UItests4.713sPASS; commit: pending candidate. Remove legend, retain tested selector contrast/spacing, verify saved profile and all existing controls.
- T2 [S1] route: inline version/instructions; status: done — metadata/dependency/recipe checks and full suite passed; commit: pending candidate. Prepare rc4 metadata and docs; preserve dependencies, build recipe and font-corrected offscreen CI configuration.
- T3 [S1] route: existing exact-SHA Windows workflow; status: in_progress — commit verified source then dispatch once; commit: pending. Commit/push the verified candidate, dispatch once, preserve source tests/build/smoke/upload results; do not retry blindly.
- T4 [S1,S2] route: parent stream verification plus independent artifact verifier (risk item5); status: pending; commit: pending. Validate the new ZIP/source/hash/native profile, publish passive delivery notes and provide the testing link.

## Log
L1 — Original request verbatim: `si, quita ese texto y cuando termines manda a crear el EXE`.
L2 — Prior selector correction is uncommitted and belongs in this candidate: explicit QComboBox/popup theme colors and 12px row gap; 9focused tests and full383Linux tests38.615sPASS/4Windows-only skips, plus light/dark render inspection. Initial RED reproduced light field in dark mode and4px gap; a subsequent out-of-viewport pixel sample was corrected to inspect the visible row. Native profile legend remained pending the owner's explicit decision, now granted inS1.
L3 — rc3 remains immutable: candidate0a19dd3/run40042896444/artifact12540281670. Use rc4 to distinguish this new executable. Existing schema3settings need no migration; retain the previous working folder. Offscreen Windows tests must keep QT_QPA_FONTDIR=C:/Windows/Fonts; never shrink UI to compensate for missing fonts. No private screenshot is committed or packaged. Complete archive verification streams in place; no runtime extraction/copies, physical USB action or hardware acceptance claim.

L4 — Meaningful legend RED observed after correcting the fixture to use explicit public schema2migration (ordinarySave correctly rejects version changes). GREEN63UItests4.713s; full384Linux tests38.922sPASS/4Windows-only skips(job74exit0). New regression proves visible legend absent while saved internal profile/identity/settingsbytes/backup/snapshot remain unchanged and capture never starts. rc4version checked; dependency/build-system blocks, packaging scripts, workflow andsettings/lifecycle/USBbackend diff unchanged against118d17f. Light/dark form and popup images inspected; no legend, readable selector,12pxgap. Native mode globaloff; assessunassessableuntracked with explicitrisk5 requires independent artifact verification afterbuild. T1/T2done; T3in_progress, T4pending. No Windows rc4 or download yet.
