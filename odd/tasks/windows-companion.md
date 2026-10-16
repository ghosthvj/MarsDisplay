# MarsDisplay hardware-independent Windows companion
Objective: implement the approved Windows companion with simulated output before hardware identification. Branch: `feat/simulated-companion`.
Delivery: `auto-chain`, `chain_strategy=feature-branch-chain`; revised forecast 3,500–5,000 authored lines across work units (including deterministic lifecycle/UI/browser tests); local commits per unit, no push, PR, release or CI execution without authorization. Tests: Python standard-library unittest initially; platform checks remain separate.

## Specs

### S1 — Implementation authorization and hardware boundary
> ok, pues empecemos a implementar lo que hemos definido en el plan y teniendo en cuenta que aun no tengo la pantalla

Reference plan: `/my-projects/pantalla/docs/windows-companion-implementation-plan.md`, confirmed requirements WS1–WS14 and acceptance matrix. Hardware-independent work only; protocol selection and physical acceptance remain deferred. No installer, service, autostart or automatic updates.

### S2 — Repository and license
> ok, crea un repo separado llamado MarsDisplay usando las credenciales actuales de gh, el repo hazlo publico y con licencia GPL v3

Repository: `https://github.com/ghosthvj/MarsDisplay`; GPL v3 LICENSE already present.

### S3 — Selected platform and stack
Exact selections from the implementation questionnaire:
> x64 — Intel o AMD
> Python + Playwright + PySide6 + PyInstaller
> Incluir Chromium en el ZIP

Target Windows 11 x64. Use the selected stack; bundle Chromium rather than require an installed browser. Pin selected versions after checking compatibility. Linux tests are not Windows acceptance.

### S4 — Tray and controls
> me parece perfecta la recomendacion de la aplicacion para Windows, aplicacion en segundo plano con icono en la bandeja del sistema con la posibilidad de consultar el estado de conexion con MARS y la pantalla, configurar la URL de MARS y seleccionar el dispositivo USB y poder iniciar, detener o cerrarlo.
> Ahora hablame de como sería eso de que necesitaría archivos auxiliares o un instalador??

Acceptance: independent source/device states and responsive public Start/Stop/Exit actions. Stop must prevent later writes/retries. Real device selection must not silently select a protocol or send probe commands.

### S5 — Local rendering and MARS ownership
> ok, mantengamos el renderizado usando un el navegador, hasta no tener pruebas de consumo reales sería lo mejor, además no quiero añadir más carga a MARS en el servidor ni complegizar su codígo

Acceptance: persistent isolated browser captures the existing `/display` region in memory; MARS owns selection/order/dwell/live updates/orientation. Nominal frames are 320×480 or 480×320, without stretching. Simulated output retains bounded state and is never reported as a connected USB screen. Establish actual readiness metadata before real MARS integration; HTTP 200 alone is insufficient.

### S6 — Portable-first Windows delivery
> ok, mantengamos la propuesta de desarrollar desde linux y generar el ZIP desde GitHub Actions para hacer las pruebas locales antes de generar un instalador

Acceptance: source tests on Linux; Windows-built portable ZIP with declared runtime/browser/notices and packaged smoke test; local Windows 11 acceptance and resource measurements are separate evidence. Workflow source implementation is in scope; remote execution/publication requires authorization.

### S7 — Provenance and protocol gate
> ok. la licencia es GPL3.0 así que podríamos reutilizar su codigo en la capa de comunicacion una vez que tengamos identificada la pantalla y así no tener que desarrollarlo desde cero
> si, no tengo problemas en respetar las condiciones de la licencia y de momento el uso es personal

Acceptance: retain licenses/provenance. Do not copy a model-specific driver before identification. Public simulation tests validate frame geometry, ordered delivery, errors and unchanged frame/counters on rejected input through public interfaces.

### S8 — Approved local behavior
Exact selection: `Sí, usar la propuesta conservadora`. Accepted preview, verbatim:
> - Configuración: `%LOCALAPPDATA%\MarsDisplay\settings.json`, con versión de formato.
> - Guardar cambios solo estando detenido; un error no sobrescribe la configuración válida.
> - Abrir la aplicación no inicia la captura automáticamente.
> - Detener cierra el navegador propio y no envía órdenes de borrado o apagado a la pantalla.
> - El menú de bandeja abre Estado/Configuración; un segundo lanzamiento no crea otro capturador.
> - En esta etapa la salida es simulada, sin escrituras USB.

### S9 — Approved recovery policy
Exact selection: `Reintentos limitados — recomendado`. Accepted description:
> Hasta 5 intentos, con esperas de 1, 2, 4, 8 y 16 segundos; después queda en error y requiere Iniciar. Detener cancela todo.

### S10 — Approved MARS access
Exact selection:
> HTTP o HTTPS sin pantalla de login
Accepted description:
> Acceso directo o proxy que ya gestiona el backend, sin autenticación interactiva en el navegador.

### S11 — Approved delivery shape
Exact selection:
> Cadena sobre rama de funcionalidad — recomendado

Use `chain_strategy=feature-branch-chain`. This organizes local work-unit boundaries and eventual review only; no publishing authority.

### S12 — Authorized Qt system prerequisite
Exact owner selection:
> Autorizo instalar libegl1 y sus dependencias

Scope is the required system package and necessary dependencies only; no unrelated upgrades, MARS changes or blanket system authorization.

## Tasks

- T1 [S1,S2,S3,S5,S7,S11] route: delegated (context backstop fired); status: done; commit: `b233d6e1f645513c359142c42e21e497b9c4b011` — 358 authored source/test/doc lines plus feature tracking: package skeleton, pinned dependency declarations, validated immutable RGB frames, bounded simulated transport, six public-interface tests and developer documentation; no tray/browser/USB implementation yet.
- T2 [S1,S3,S4,S8,S9] route: delegated (context backstop); status: done (source/offscreen scope; Windows acceptance is T6); commits: T2a `a4c7030df580c71d41fc12f7b2feaab85794260b`, T2b `a0e20b2bad6240b9541b76b0388ed4e233207d54`, T2c recording — validated settings, cancellable lifecycle, injectable tray/dialog and single-instance guard. All36 tests plus independent per-unit probes passed. Runnable browser entrypoint is T3, not yet present.
- T3 [S1,S3,S5,S10] route: delegated (context backstop); status: in_progress; commit: pending — inspect actual MARS capture contract, persistent browser integration and controlled fixtures. Access is HTTP(S) without interactive login.
- T4 [S1,S4,S5,S7] route: inline unless a delegation trigger fires; status: pending; commit: pending — in-memory capture in both orientations, bounded latest-frame pipeline, passive device discovery and simulated-output integration; no USB writes.
- T5 [S1,S2,S3,S6,S7] route: inline unless a delegation trigger fires; status: pending; commit: pending — Windows packaging/workflow source, notices, artifact smoke-test recipe and usage documentation; remote execution is separately authorized.
- T6 [S1,S4,S5,S6] route: local Windows acceptance by owner; status: blocked (requires a packaged prototype and user's Windows 11 environment); commit: evidence pending — tray/LAN/recovery/ZIP and process-tree RAM/CPU measurements. Physical USB validation is deferred, not claimed by these tasks.

## Log

L1 — Original implementation request, verbatim:
> ok, pues empecemos a implementar lo que hemos definido en el plan y teniendo en cuenta que aun no tengo la pantalla

L2 — Owner selected `x64 — Intel o AMD`, `Python + Playwright + PySide6 + PyInstaller`, and `Incluir Chromium en el ZIP`. Repository choice already completed. Additional product decisions in WO5–WO10/WO12–WO14 remain checkpoints before dependent implementation.

L3 — Baseline `e6160e5` contains only LICENSE; working branch created from main. No existing application behavior or CLI to preserve/differentially compare. Initial behavior uses unittest to avoid making test execution depend on GUI/browser packages. The host has Python 3.13.5 but no pip/setuptools in its system interpreter; do not modify system Python or claim packaging success from source tests.

L4 — Research: PyPI reports Windows x64 wheels for Playwright 1.64.0 (Python >=3.10), PySide6 6.12.0 (>=3.10,<3.16), Pillow 12.3.0 (>=3.10), PyInstaller 6.22.3 (>=3.8,<3.16). These are candidate exact pins, not installed proof. Official Playwright packaging docs use PLAYWRIGHT_BROWSERS_PATH=0 and install chromium before PyInstaller. Context7's Qt deployment page contains obsolete March 2021 limitations; use current PyInstaller support and actual Windows smoke tests rather than trusting that stale section. Sources: https://pypi.org/ ; https://playwright.dev/python/docs/library ; https://pyinstaller.org/en/stable/ .

L5 — Risk: item 5 (dependency declarations and future packaging/environment compatibility); item 4 applies when lifecycle workers are introduced. Independent foundation verification completed with no blockers. Native review mode reads `off (decided by global)` in this clone; do not start native review or change the switch.

L6 — T1 RED: unittest exited 1 for missing mars_display package before implementation. GREEN: six tests passed, exit 0; parent reran the suite with the same result. Independent verifier also ran all six tests, README example, two additional isolated public-interface probes, metadata checks and unchanged-license hashing: all passed. `git diff --check` exited 0. No base command/option exists to differentially compare. Runtime/backend pins are Playwright 1.64.0, PySide6 6.12.0, Pillow 12.3.0, PyInstaller 6.22.3, setuptools 84.0.0 (authoritative metadata checked). Build probe `python3 -m build --no-isolation` exited 1: `No module named build`; no retry or install attempted. Installation/transitive resolution, Windows/EXE/Chromium/USB proof are not established and remain separate stages.

L7 — Native read-only ASSESS with item 5 escalation returned independentVerifier=true and nativeRisk=unassessable because untracked files have no explicit scope declaration. Its reported rddLine=on disagrees with the direct clone-scoped mode status (off globally); no review transaction was started and no mode changed. The independent verifier ran once as required by the named environment risk. T1 is source-complete; owner subsequently selected the chain strategy in L8. Publication remains unauthorized.

L8 — Owner answers, verbatim: `Cadena sobre rama de funcionalidad — recomendado`; `Sí, usar la propuesta conservadora`; `Reintentos limitados — recomendado`; `HTTP o HTTPS sin pantalla de login`. The accepted local-behavior preview and recovery/access descriptions are preserved in S8–S10. Commit the verified foundation as slice 1, then implement settings/lifecycle/tray as the next coherent unit. T1's 358 authored lines plus tracking exceed the heuristic slightly; keep its tests and readable documentation rather than artificially splitting them.

L9 — Slice 1 committed locally as `b233d6e1f645513c359142c42e21e497b9c4b011`, 456 authored additions including 98 tracking lines. No push. T2 is split into cohesive settings-persistence and lifecycle/tray work units, not file-type slices. A repository-local .venv install is running using python3 -m venv and pinned editable package extras; system Python is unchanged. Real MARS documentation/source was read through gh API, without re-creating its removed clone.

L10 — Isolated install succeeded (exit 0): `.venv/bin/python -m pip --disable-pip-version-check install --retries 0 --timeout 30 -e '.[build]'`; an editable Linux wheel was built with the pinned backend and dependencies. This resolves local install availability, not Windows packaging proof. .venv is Git-ignored. Do not add QtWebEngine usage merely because the PySide6 wheel pulls it transitively.

L11 — Actual MARS capture boundary found in remote docs/external-display.md (blob a4b7c401c3bae187e7158227e4d6ab34b5628afe) and frontend/src/pages/Display.tsx (083d86fa027943ba437ea620bc9c0b9db65f14e4): `#mars-display`, `data-display-version=1`, `data-display-state=loading|ready|empty|error`, `data-orientation`, `data-width`, `data-height`, `data-server-id` when ready, `data-live-connected`, `data-data-stale`. Nominal geometry follows orientation. Disabled/config failure redirects to `/`; missing root or navigation is not ready. Wait `document.fonts.ready` plus settled layout. Source/SSE freshness is not a replacement server health evaluator. This is implementation evidence, not a new requested feature.

L12 — T2a RED: focused unittest exited 1 for missing settings module; GREEN: eight settings tests passed. Worker full suite and independent full suite passed all 14 tests; parent reran eight focused tests with exit 0. Independent isolated probes verified strict URL/schema rejection, unchanged bytes on bad input, atomic replacement and cleanup through read/write/fsync/replace failures. No blockers. Existing six frame/transport tests preserved; no command/option differential applies. ASSESS item1 escalation returned nativeRisk=medium and independentVerifier=true; reviewDue=false, no native review started. Windows filesystem acceptance remains pending.

L13 — One Qt availability probe failed, exit 1: `ImportError: libEGL.so.1: cannot open shared object file: No such file or directory`. Diagnostic ldd on the installed PySide6 QtWidgets extension confirms only `libEGL.so.1 => not found`. No retry, workaround, system install or GUI success claim. T2b waits for owner authorization to install Debian/Ubuntu libegl1 (system paths outside repository), or an explicit alternative for obtaining Windows GUI proof. Settings is source-verified independently of this unrelated GUI prerequisite. README now records successful Linux editable install and this specific missing GUI dependency.

L14 — Owner explicitly selected `Autorizo instalar libegl1 y sus dependencias` (token install_libegl1). This unblocks the system prerequisite installation, not GUI acceptance itself. Run the scoped package installation once, then a fresh Qt availability check after the environment change; do not install unrelated system packages.

L15 — Authorized apt installation exited 0: libegl1 1.7.0-1+b2 and required libegl-mesa0/libwayland-client0 installed; no unrelated upgrades. After this explicit environment change, a fresh offscreen QApplication probe exited 0: `Qt offscreen application available`. The earlier missing-library blocker is resolved. Offscreen Linux Qt availability is not Windows tray acceptance. Next slices are the cancellable coordinator (T2b) and its tray binding (T2c), with their own tests/docs. Internal capture scheduling starts conservatively at 1 Hz with synchronous backpressure; it is an engineering baseline, not a hardware throughput claim or user refresh setting.

L16 — T2b coordinator RED exited 1 for missing lifecycle module; GREEN13 focused tests and full27 passed. Parent reran13; independent verifier ran all27 plus three isolated concurrency probes with bounded handshakes, all exit0. Tests prove sole worker ownership, stopped-only save, cancellation, cleanup-before-stop acknowledgement, exact retry delays/exhaustion and restart, and cleanup-failure latch; no blockers. ASSESS escalated item4, returned independentVerifier=true, nativeRisk=medium, reviewDue=false. No old CLI differential applies. Coherent slice is ~780 lines including concurrency tests/docs; keep the lifecycle state machine with its proof rather than file-type splitting. GUI and Windows behavior remain separate.

L17 — Repository-local Chromium headless shell installed via PLAYWRIGHT_BROWSERS_PATH=0 (Playwright revision1248 plus FFmpeg1013), exit0. A real local HTML screenshot with `chromium_sandbox=True` succeeded, exit0, 3229 PNG bytes. No TLS/sandbox bypass, production URL or USB access. Browser availability is now proven on Linux, not real MARS integration or Windows packaging.

L18 — T2c tray RED exited1 for missing tray module; GREEN9 Qt-widget/guard tests and full36 passed with no skips. Parent reran9; independent verifier ran36 plus isolated live cross-process admission, blocked-start Stop/Exit, queued-save byte preservation and cleanup-error lock-retention probes; no blockers. Expected offscreen platform warnings (no native tray window/raise support) were preserved and are not Windows acceptance. ASSESS item4 escalation requested independent verify and reviewDue=true, but actual clone review mode remains globally off; no native review started and no switch changed. create_shell(app, store, coordinator_factory) admits its lock before factory; SingleInstanceGuard exposes acquire/release. Commit this source/UI unit separately; T3 supplies the actual browser factory and entrypoint. Revised total forecast reflects the tests needed for concurrency and UI; chain strategy stays unchanged, no publication.
