# Windows UI candidate 0.2.0rc3
Prepare the owner-requested Windows portable executable from the accepted source-only UI changes.
Branch `feat/brightness-slider`, baseline `b064bddaf34f229a3b85f9334057ae0c7bd52afc`; existing feature-branch-chain, no PR/merge/final release. Runner: offscreen unittest with `.venv/bin/python -B`, `PYTHONPATH=src:tests`.

## Specs
S1 — User: `ok. compila el EXE para probarlo`. Produce a new qualified Windows portable candidate for testing; keep the complete folder and existing packaging/runtime prerequisites. Assumption: version 0.2.0rc3 distinguishes it from the immutable rc2 artifact.
S2 — User: `este bloque de logs quiero moverlo a una ventana independiente y llamarla con un botón similar a Preview`. Preserve diagnostic semantics and capture ownership.
S3 — User: `escribe Running con la "R" mayuscula, Stoppped con la "S" y así para todos los estados, además agrega delante de cada estado un icono que lo represente Running un rayo, Stopped su icono, y en los cambios Starting/Stopping la rueda de carga`. Keep correct English spelling Stopped and unchanged backend states.
S4 — User: `muestra Enable Brightness SOLO cuando sea necesario y hazlo un boton más estrecho que no ocupe todo el ancho.` / `oculta Restore Settings pero no elimines la funcion, no creo que sea necesario añadir ningun menus de opciones avanzadas por ahora` / `creo que no es necesario mostrar el estado breve del brillo pues la barra se explica sola.` / `la barra del brillo quedaría mejor centrada en la ventana!`. Retain the agreed 320px five-level control and persistence.
S5 — User: `tambien creo que los botones Preview y Logs se pueden mover a la barra inferior donde ya está Save y separarlos un poco más de Save que entre ellos`.
S6 — User: `El campo de configuracion de la URL de MARS está correcto.` / `El desplegable de los dispositivos USB y el boton Refresh USB identities creo que pueden ir en la misma linea ajustando su ancho.` / `Creo que ya no necesitamos los botones de exportar y restaurar el schema-1.` / `Tampoco necesitamos la explicacion del Refresh.` / `La idea es hacer la ventana de configuracion de un alto fijo para que no sea necesario hacer scroll` / `si, confirmo que se configure Native USB`. Save/Start remain explicit; Simulation/export/recovery remain internal capabilities. No automatic migration, device selection or Start.

## Tasks
- T1 [S3] route: inline verified work-unit staging; status: in_progress; commit: pending. Commit capitalized status/vector icons with matching tests/docs; preserve unrelated changes.
- T2 [S2,S4,S5] route: inline verified work-unit staging; status: pending; commit: pending. Commit Logs, compact centered brightness and footer observers with their tests/docs.
- T3 [S6] route: inline verified work-unit staging; status: pending; commit: pending. Commit native-only fixed form, including the observed screen-fit correction and regression tests.
- T4 [S1] route: inline candidate metadata; status: pending; commit: pending. Set rc3 version and update portable instructions without changing dependencies/workflow/packaging recipe.
- T5 [S1] route: existing Windows workflow, exact source binding; status: pending; commit: pending. Nonforce push candidate, dispatch once, retain run ID, await source/native/build/smoke result.
- T6 [S1-S6] route: parent artifact checks plus independent artifact-only verifier for delivery risk item 5; status: pending; commit: pending. Verify exact new ZIP/source/hash/native payload; publish download evidence and deliver for owner testing, not final acceptance.

## Log
L1 — Original build request verbatim: `ok. compila el EXE para probarlo`.
L2 — Source-only changes already independently checked. Logs: 367-test suite/4 Windows-only skips plus independent differential. Status icons: 369/4 plus 42-state differential. Compact brightness: 373/4 plus independent migration/recovery preservation. Footer: 43 focused UI tests. Native-only fixed form: full378/4, initial820px desktop blocker reproduced, corrected height min(760, available desktop height minus48), final58 focused tests and independent3-test screen-fit recheck PASS. Windows physical rendering is not inferred. No new source behavior is requested by compilation.
L3 — Preserve unrelated tracked Linux measurement docs and private untracked screenshots/task files. Only explicitly scoped UI files enter the candidate. Current accumulated UI diff will be staged as three cohesive units with tests/docs, using bounded index snapshots (cap8MiB), not copied build runtimes. Existing branch-chain strategy remains; compilation does not authorize final release/merge.
