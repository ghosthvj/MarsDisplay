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

### S13 — Approved per-test fixture isolation and provenance
Owner authorization, verbatim:
> adelante te autorizo

Accepted proposal, verbatim:
> Necesito tu decisión: ¿autorizás aislar el servidor por prueba y agregar trazas de procedencia, manteniendo las comprobaciones estrictas y sin tocar el capturador?

Acceptance: a distinct loopback server and counters per browser test; handler/session cleanup before fixture disposal; structured case/method/path/peer/time provenance with correlated browser/route-fetch events where relevant; exact request counters include unexpected traffic. Do not modify browser.py, filter away unknown requests, claim the historical root cause is solved, or accept/publish T3 from green reruns alone.

## Tasks

- T1 [S1,S2,S3,S5,S7,S11] route: delegated (context backstop fired); status: done; commit: `b233d6e1f645513c359142c42e21e497b9c4b011` — 358 authored source/test/doc lines plus feature tracking: package skeleton, pinned dependency declarations, validated immutable RGB frames, bounded simulated transport, six public-interface tests and developer documentation; no tray/browser/USB implementation yet.
- T2 [S1,S3,S4,S8,S9] route: delegated (context backstop); status: done (source/offscreen scope; Windows acceptance is T6); commits: T2a `a4c7030df580c71d41fc12f7b2feaab85794260b`, T2b `a0e20b2bad6240b9541b76b0388ed4e233207d54`, T2c `1aebcceb0477864c751fcca04583c837075d2b87` — validated settings, cancellable lifecycle, injectable tray/dialog and single-instance guard. All36 tests plus independent per-unit probes passed. Runnable browser entrypoint is T3, not yet present.
- T3 [S1,S3,S5,S10] route: delegated (context backstop); status: blocked (historical extra root request still unexplained; separately authorized fixture hardening is T7, not capture acceptance); commit: not accepted/uncommitted — actual MARS contract inspected, persistent browser and controlled fixtures under test. Access is HTTP(S) without interactive login.
- T4 [S1,S4,S5,S7] route: inline unless a delegation trigger fires; status: pending; commit: pending — in-memory capture in both orientations, bounded latest-frame pipeline, passive device discovery and simulated-output integration; no USB writes.
- T5 [S1,S2,S3,S6,S7] route: inline unless a delegation trigger fires; status: pending; commit: pending — Windows packaging/workflow source, notices, artifact smoke-test recipe and usage documentation; remote execution is separately authorized.
- T6 [S1,S4,S5,S6] route: local Windows acceptance by owner; status: blocked (requires a packaged prototype and user's Windows 11 environment); commit: evidence pending — tray/LAN/recovery/ZIP and process-tree RAM/CPU measurements. Physical USB validation is deferred, not claimed by these tasks.

- T7 [S13] route: delegated (context backstop); status: done (fixture-only scope); commit: recording — per-test fixture, strict counters, HTTP/Page/Route provenance through later captures, bounded cleanup and corrected listener teardown verified. Helper4, public trace regression1, full51 and targeted independent recheck passed. Standalone helper/trace tests/docs commit independently; unaccepted BrowserSession and its test_browser.py integration remain uncommitted under T3.

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

L19 — T3a writer reported browser RED missing module then10 focused/full46 GREEN tests, but parent's required focused recheck exited1: test_persistent_ready_rgb_portrait_and_landscape(landscape=True) expected Counter({'/display':2}) and observed Counter({'/display':2,'/':1}). Browser unit is NOT accepted or committed. Correct the extra-request/test-isolation cause and pin its regression before independent verification. App assembly remains unimplemented as a separate T3b slice. No automatic retry of the failed command without a code/test correction.

L20 — The one bounded correction attempt added request-header diagnostics and strengthened exact request-count checks after a third capture and browser close (tests/test_browser.py +8 net lines), but did NOT reproduce or explain the extra `/` request and made no justified production fix. Its focused10 and full46 reruns passed (11.922s/12.678s), exit0; these passes do not establish a fix. Worker correctly returned partial. Do not run another acceptance/review/verification cycle or commit T3a. No independent browser verifier was launched because the parent spot-check blocker remains unresolved. App entrypoint/assembly, T4 simulation integration, T5 ZIP/workflow and T6 Windows proof are still pending. Stop as Needs your decision: owner may authorize a newly bounded diagnostic investigation of the request origin, or pause with all verified commits preserved. Preserve unaccepted browser changes for diagnosis, without publishing them.

L21 — Owner authorized investigation: `vale, te autorizo a investigar`. Read-only mapping found class-shared loopback server/counters reset without a handler barrier; a possible misattribution, not demonstrated origin of historical GET /. The investigator's executable probes were unavailable under conflicting scratch rules, not retried. Parent ran one in-memory correlated disabled→portrait→landscape diagnostic, exit0, two selected cases in2.038s: one /disabled/display and two /display requests, no /. No source edits; browser.py SHA256 e68d03a30f38f32b39ef10eb3a0b57b39eda8c4c6ca5ca45dad9ccd08a26ee11 unchanged. Route.fetch forwards request headers, so a browser-looking User-Agent alone does not prove client process identity.

L22 — Owner selected the S13 proposal: `adelante te autorizo`. This authorizes per-test fixture isolation/provenance and necessary tests/docs only; no capture-source fix or acceptance. T7 is a bounded test-only unit. Risk: item4 (fixture server/handler lifecycle and event attribution); independently verify once after the writer's RED/GREEN/focused/full checks. Keep all exact request-count assertions and include injected unexpected / traffic in them. No public delivery or source browser commit is authorized by this adjustment.

L23 — T7 helper RED exited1 (missing browser_fixture), GREEN4 helper tests passed. Initial browser integration run exposed ten teardown TargetClosedErrors; one correction detaches test tracing listeners before closing sessions. Corrected focused10 and full50 passed (11.878s/12.443s), no skips; existing offscreen warnings preserved. Parent reran helper4 successfully (0.058s) and diff-check passed. browser.py SHA256 e68d03a30f38f32b39ef10eb3a0b57b39eda8c4c6ca5ca45dad9ccd08a26ee11 and display.html404b38f3bcea0c06834b042bd809631326d88214d99cd354d92a8af0b4a19e96 unchanged. Standalone helper/helper-tests/test docs total515 lines; no production imports, no suppressing / traffic. Integration changes to existing unaccepted test_browser.py remain separate from that standalone commit. Independent verification will check scope/lifetime of correlated events as well as cleanup and attribution; no historical root-cause or capture acceptance claim.

L24 — Independent T7 verification passed isolation/late attribution, strict unexpected / counts, cleanup, immutable socket provenance and unchanged hashes. Full50 passed, but a deterministic post-goto landscape fetch('/') probe failed: exact socket counts / and /display were correct and an independent Page listener saw the request, while fixture late trace contained only handler.start/end. Cause is proven for this NEW S13 gap: Page listeners are attached only during goto. This is NOT the origin of the historical / failure. One bounded correction must retain Page correlation for later capture/session activity and safely detach before driver teardown. Add the provided public Playwright regression in tests/test_browser_trace.py (no production imports) so the standalone helper slice remains independent of unaccepted BrowserSession code. Then recheck only this blocker; no new broad review sweep. Native ASSESS could not scope unrelated untracked candidate files; its item4 escalation still required the independent verifier, which ran once. Actual native review remains disabled and no review transaction exists.

L25 — Correction worker added the exact public Playwright regression but stopped before changing the helper: its first RED observed two / requests instead of one (display count1), while the mandated full51 run had correct counts and failed on the SAME known missing post-goto Page provenance. Helper4 and existing browser10 still passed, source hashes unchanged. Extra / is the pre-existing investigation pattern and can now occur in a test importing only Playwright and BrowserFixture (no capture implementation); that does not prove identical historical causality. No new root-cause investigation or assertion weakening is authorized. The same S13 Page-lifetime blocker is still deterministically RED, so the specifically permitted final same-blocker correction applies: implement listener lifetime, add full trace to exact-count failure messages, preserve any remaining failures, then targeted recheck only.

L26 — Final same-blocker correction retained Page listeners past goto, cached public request metadata and explicitly detached before owned page/context/browser teardown. Exact-count diagnostics now include full immutable snapshot; no counts relaxed. GREEN regression1 (0.468s), helper4 (0.057s), full51 (13.049s) passed. Parent reran regression1 (0.484s), diff-check and both source hashes matched. Existing independent verifier rechecked ONLY prior late-Page blocker plus affected restoration test: both exit0 (0.544s/0.012s), no remaining S13 blocker, no new full sweep. Historical root request remains unexplained; no T3/Windows/USB acceptance.

L27 — T7 closes as a coherent test-only slice: helper, helper tests, public Playwright trace regression, test guide and tracking. All production files and original fixture HTML unchanged. The source/browser integration test edits remain in the uncommitted T3 candidate because committing them without its unaccepted BrowserSession would create an incomplete work unit. Native ASSESS unassessable/untracked-scope limitation is recorded, independent item4 verification supplied required proof, native review disabled and not started. No push/PR/CI/release. Next consequential choice is whether to resume bounded root-request diagnosis with these traces or leave T3 pending; do not silently accept the unknown cause.
