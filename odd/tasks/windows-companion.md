# MarsDisplay hardware-independent Windows companion
Objective: implement the approved Windows companion with simulated output before hardware identification. Branch: `feat/simulated-companion`.
Delivery: `auto-chain`, `chain_strategy=feature-branch-chain`; forecast 1,500–2,500 authored lines across work units; local commits per unit, no push, PR, release or CI execution without authorization. Tests: Python standard-library unittest initially; platform checks remain separate.

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

## Tasks

- T1 [S1,S2,S3,S5,S7,S11] route: delegated (context backstop fired); status: done; commit: recording — 358 authored source/test/doc lines plus feature tracking: package skeleton, pinned dependency declarations, validated immutable RGB frames, bounded simulated transport, six public-interface tests and developer documentation; no tray/browser/USB implementation yet.
- T2 [S1,S3,S4,S8,S9] route: delegated (context backstop); status: in_progress; commit: pending — local settings, tray and lifecycle with isolated public-action tests.
- T3 [S1,S3,S5,S10] route: delegated when context backstop applies; status: pending; commit: pending — inspect actual MARS capture contract, persistent browser integration and controlled fixtures. Access is HTTP(S) without interactive login.
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
