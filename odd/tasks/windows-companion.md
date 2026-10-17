# MarsDisplay hardware-independent Windows companion
Objective: implement the approved Windows companion with simulated output before hardware identification. Branch: `feat/simulated-companion`.
Delivery: `auto-chain`, `chain_strategy=feature-branch-chain`; revised forecast 4,500–6,500 authored lines across work units (including deterministic lifecycle/UI/browser tests); local commits per unit, no push, PR, release or CI execution without authorization. Tests: Python standard-library unittest initially; platform checks remain separate.

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

### S14 — Approved test-owned traffic attribution
Owner authorization, verbatim:
> si, te autorizo

Accepted proposal, verbatim:
> No modifiqué código. Recomiendo separar el tráfico propio de cada prueba del tráfico ajeno, **conservando ambos en las trazas y manteniendo estrictos los recuentos propios**.
> ¿Autorizás ese ajuste únicamente en las pruebas, sin tocar el capturador ni detener `moshi-hook`?

Acceptance: per-run/case request identity for test-controlled clients; exact owned counts include unexpected owned paths; foreign/missing/wrong-identity traffic stays in raw totals and separately attributable traces. Preserve existing raw Snapshot.counts semantics and make the owned/foreign partition explicit. No path/User-Agent allowlist, no dropped requests, no hook/process changes and no production-source/HTML changes. The identity is a test attribution mechanism, not authentication or proof of process ownership. Preserve existing helper/route/header/lifecycle behavior while adding ownership observations.

### S15 — Single-page correction and routine-work continuity
Owner authorization and preference, verbatim:
> si, te autorizo, NO me pidas mas autorizaciones simples como estas, no pares a no ser que sea algo importante!

Acceptance: correct the proven same-URL popup defect with regression proof, retain one owned display page/client, and continue routine implementation/verification under the original plan without repeated low-consequence approval stops. Consequential scope/product decisions, publishing/destructive actions, mandated consent and genuinely unavailable/exhausted proof remain human-controlled.

## Tasks

- T1 [S1,S2,S3,S5,S7,S11] route: delegated (context backstop fired); status: done; commit: `b233d6e1f645513c359142c42e21e497b9c4b011` — 358 authored source/test/doc lines plus feature tracking: package skeleton, pinned dependency declarations, validated immutable RGB frames, bounded simulated transport, six public-interface tests and developer documentation; no tray/browser/USB implementation yet.
- T2 [S1,S3,S4,S8,S9] route: delegated (context backstop); status: done (source/offscreen scope; Windows acceptance is T6); commits: T2a `a4c7030df580c71d41fc12f7b2feaab85794260b`, T2b `a0e20b2bad6240b9541b76b0388ed4e233207d54`, T2c `1aebcceb0477864c751fcca04583c837075d2b87` — validated settings, cancellable lifecycle, injectable tray/dialog and single-instance guard. All36 tests plus independent per-unit probes passed. Runnable browser entrypoint delivered under T3.
- T3 [S1,S3,S5,S10,S15] route: inline for bounded popup correction, delegated context-backstop for subsequent app assembly; status: done (source/offscreen integration scope; native Windows acceptance is T6); commits: T3a `5f55f3e6bf720f0f74d578ac21371d9c353dbbc9`, T3b `e951bbb0a4b6f2f4caea07e1a988d69bbc57b272` — actual MARS contract inspected, persistent browser and controlled fixtures under test. Access is HTTP(S) without interactive login.
- T4 [S1,S4,S5,S7] route: delegated (context backstop); status: done (software preparation/simulated pipeline only; native inventory and physical chooser deferred to identified hardware); commit: `f936dd21a2787e5bb5f67cbaa98478634a9148f3` — both-orientation capture/bounded simulated pipeline proved by T3b; passive USB-serial descriptor inventory and explicit conservative identity-selection APIs/tests without choosing a protocol, auto-selecting a port or writing USB. Runnable output remains simulated; physical GUI chooser/driver qualification waits for identified hardware.
- T5 [S1,S2,S3,S6,S7] route: delegated (context backstop); status: blocked (explicit public push/Windows CI authorization required); commits: legal data `c0f9d4a2ad930f051a87a91c68b03b02769d919c`, T5a1 `684d6e5a711b76a0e418a5897da908bdd2171d73`, T5a2 `a39fdf163acd982c77b7027fca02f1afefaeeb59` — SOURCE payload/notices/bootstrap/spec/build/smoke/workflow prepared; full104 writer tests and independent32/source CLI checks pass. No actual Windows build/native qualification/ZIP or CI upload. First authorized Windows run obtains unqualified native inventory; final ZIP requires genuine native mapping and smoke. T5 remains incomplete; do not mark done from Linux/synthetic/source proof.
- T6 [S1,S4,S5,S6] route: local Windows acceptance by owner; status: blocked (requires a packaged prototype and user's Windows 11 environment); commit: evidence pending — tray/LAN/recovery/ZIP and process-tree RAM/CPU measurements. Physical USB validation is deferred, not claimed by these tasks.

- T7 [S13] route: delegated (context backstop); status: done (fixture-only scope); commit: `5b34bd34db6acee3a8cd428a5569788abbbae2f0` — per-test fixture, strict counters, HTTP/Page/Route provenance through later captures, bounded cleanup and corrected listener teardown verified. Helper4, public trace regression1, full51 and targeted independent recheck passed. Standalone helper/trace tests/docs commit independently; unaccepted BrowserSession and its test_browser.py integration remain uncommitted under T3.

- T8 [S14] route: delegated (context backstop); status: done (test-only scope); commit: `70ee51f9bdc244820cf6414e15c98797dadd921d` — test-only per-case request identity, exact owned counters, retained foreign/raw observations and deterministic attribution regression tests. Do not modify/accept capture or disable host hook.

## Log

L1 — Original implementation request, verbatim:
> ok, pues empecemos a implementar lo que hemos definido en el plan y teniendo en cuenta que aun no tengo la pantalla

L2 — Owner selected `x64 — Intel o AMD`, `Python + Playwright + PySide6 + PyInstaller`, and `Incluir Chromium en el ZIP`. Repository choice already completed. Additional product decisions in WO5–WO10/WO12–WO14 remain checkpoints before dependent implementation.

L3 — Baseline `e6160e5` contains only LICENSE; working branch created from main. No existing application behavior or CLI to preserve/differentially compare. Initial behavior uses unittest to avoid making test execution depend on GUI/browser packages. The host has Python 3.13.5 but no pip/setuptools in its system interpreter; do not modify system Python or claim packaging success from source tests.

L4 — Research: PyPI reports Windows x64 wheels for Playwright 1.64.0 (Python >=3.10), PySide6 6.12.0 (>=3.10,<3.16), Pillow 12.3.0 (>=3.10), PyInstaller 6.22.3 (>=3.8,<3.16). These are candidate exact pins, not installed proof. Official Playwright packaging docs use PLAYWRIGHT_BROWSERS_PATH=0 and install chromium before PyInstaller. Context7's Qt deployment page contains obsolete March 2021 limitations; use current PyInstaller support and actual Windows smoke tests rather than trusting that stale section. Sources: https://pypi.org/ ; https://playwright.dev/python/docs/library ; https://pyinstaller.org/en/stable/ .

L5 — Risk: item 5 (dependency declarations and future packaging/environment compatibility); item 4 applies when lifecycle workers are introduced. Independent foundation verification completed with no blockers. Native review mode reads `off (decided by global)` in this clone; do not start native review or change the switch.

L6 — T1 RED: unittest exited 1 for missing mars_display package before implementation. GREEN: six tests passed, exit 0; parent reran the suite with the same result. Independent verifier also ran all six tests, README example, two additional isolated public-interface probes, metadata checks and unchanged-license hashing: all passed. `git diff --check` exited 0. No base command/option exists to differentially compare. Runtime/backend pins are Playwright 1.64.0, PySide6 6.12.0, Pillow 12.3.0, PyInstaller 6.22.3, setuptools 84.0.0 (authoritative metadata checked). Build probe `python3 -m build --no-isolation` exited 1: `No module named build`; no retry or install attempted. Installation/transitive resolution, Windows/EXE/Chromium/USB proof are not established and remain separate stages.

L7 — ASSESS item5 requested independent verification but could not scope untracked files. Facade rddLine=on disagreed with clone CLI off globally; no transaction or mode change. Source verification proceeded via the named risk, not fabricated review authority.

L8 — Owner answers, verbatim: `Cadena sobre rama de funcionalidad — recomendado`; `Sí, usar la propuesta conservadora`; `Reintentos limitados — recomendado`; `HTTP o HTTPS sin pantalla de login`. The accepted local-behavior preview and recovery/access descriptions are preserved in S8–S10. Commit the verified foundation as slice 1, then implement settings/lifecycle/tray as the next coherent unit. T1's 358 authored lines plus tracking exceed the heuristic slightly; keep its tests and readable documentation rather than artificially splitting them.

L9 — Slice 1 committed locally as `b233d6e1f645513c359142c42e21e497b9c4b011`, 456 authored additions including 98 tracking lines. No push. T2 is split into cohesive settings-persistence and lifecycle/tray work units, not file-type slices. A repository-local .venv install is running using python3 -m venv and pinned editable package extras; system Python is unchanged. Real MARS documentation/source was read through gh API, without re-creating its removed clone.

L10 — Isolated install succeeded (exit 0): `.venv/bin/python -m pip --disable-pip-version-check install --retries 0 --timeout 30 -e '.[build]'`; an editable Linux wheel was built with the pinned backend and dependencies. This resolves local install availability, not Windows packaging proof. .venv is Git-ignored. Do not add QtWebEngine usage merely because the PySide6 wheel pulls it transitively.

L11 — Actual MARS contract verified through gh API: #mars-display/version1; states loading|ready|empty|error; orientation, width/height, ready server ID and live/stale flags. Disabled/config failure redirects to /. Docs blob a4b7c401c3bae187e7158227e4d6ab34b5628afe; Display blob083d86fa027943ba437ea620bc9c0b9db65f14e4. Wait fonts/layout; SSE freshness is not server health.

L12 — T2a RED missing settings module; GREEN8 and full14 exit0. Parent focused8 and independent14 plus isolated validation/failure/hash probes passed, no blockers. Atomic rejection/replace cleanup preserved; Windows filesystem proof deferred. ASSESS item1/native medium/independent=true, reviewDue=false; no native review.

L13 — Qt availability failed1: `ImportError: libEGL.so.1: cannot open shared object file: No such file or directory`; ldd confirmed only libEGL missing. No retry/install before owner authorization (L14). Settings proof unaffected; README recorded this prerequisite.

L14 — Owner explicitly selected `Autorizo instalar libegl1 y sus dependencias` (token install_libegl1). This unblocks the system prerequisite installation, not GUI acceptance itself. Run the scoped package installation once, then a fresh Qt availability check after the environment change; do not install unrelated system packages.

L15 — Authorized apt install exited0: libegl1 1.7.0-1+b2, libegl-mesa0 and libwayland-client0, no unrelated upgrades. Fresh QApplication offscreen probe then exit0. Linux availability is not Windows acceptance. Coordinator and tray are separate slices; initial internal capture baseline1Hz with synchronous backpressure, not a hardware guarantee/user refresh option.

L16 — T2b RED missing lifecycle; GREEN13/full27 exit0. Parent13 and independent27 plus three Event-controlled concurrency probes passed. Stop/Exit wait cleanup+thread completion, exact retry delays/exhaustion and uncertainty latch proven. ASSESS item4/native medium/independent=true, reviewDue=false. Larger coherent lifecycle/test/doc slice retained without golfing; GUI/Windows deferred.

L17 — Repository-local Chromium headless shell installed via PLAYWRIGHT_BROWSERS_PATH=0 (Playwright revision1248 plus FFmpeg1013), exit0. A real local HTML screenshot with `chromium_sandbox=True` succeeded, exit0, 3229 PNG bytes. No TLS/sandbox bypass, production URL or USB access. Browser availability is now proven on Linux, not real MARS integration or Windows packaging.

L18 — T2c RED missing tray; GREEN9/full36 no skips. Parent9 and independent36 plus live cross-process admission, queued-save hash and cleanup-lock probes passed. Offscreen warnings retained, not Windows tray proof. create_shell locks before factory; Exit retains ownership until cleanup. ASSESS item4 asked verification; actual native mode off, no review. T3 supplies runnable browser assembly.

L19 — T3a writer reported browser RED missing module then10 focused/full46 GREEN tests, but parent's required focused recheck exited1: test_persistent_ready_rgb_portrait_and_landscape(landscape=True) expected Counter({'/display':2}) and observed Counter({'/display':2,'/':1}). Browser unit is NOT accepted or committed. Correct the extra-request/test-isolation cause and pin its regression before independent verification. App assembly remains unimplemented as a separate T3b slice. No automatic retry of the failed command without a code/test correction.

L20 — First bounded T3a correction added header diagnostics and exact counts after third read/close (+8test lines), but did not explain/fix /. Focused10/full46 exit0 (11.922s/12.678s) were NOT accepted as a fix; worker partial. No browser commit/independent review then; owner diagnosis decision required. Unaccepted code preserved.

L21 — Owner `vale, te autorizo a investigar` authorized read-only diagnosis. Static map found shared-server/counter reset without handler barrier (hypothesis only). Investigator probes unavailable due scratch-rule conflict; not retried. One parent in-memory disabled→portrait→landscape trace exit0/2cases/2.038s: no /. Source unchanged/e68d03a30f38f32b39ef10eb3a0b57b39eda8c4c6ca5ca45dad9ccd08a26ee11. Route.fetch forwards headers, so UA alone proves no process identity.

L22 — Owner selected the S13 proposal: `adelante te autorizo`. This authorizes per-test fixture isolation/provenance and necessary tests/docs only; no capture-source fix or acceptance. T7 is a bounded test-only unit. Risk: item4 (fixture server/handler lifecycle and event attribution); independently verify once after the writer's RED/GREEN/focused/full checks. Keep all exact request-count assertions and include injected unexpected / traffic in them. No public delivery or source browser commit is authorized by this adjustment.

L23 — T7 RED missing helper, GREEN4. Browser integration initially failed10 TargetClosedErrors; detach-before-close correction then browser10/full50 exit0. Parent helper4/diff-check/hashes passed. Helper/tests/docs515 lines independent of unaccepted BrowserSession. Source/HTML unchanged; exact unexpected / counts retained. Independent review pending at this point.

L24 — Independent T7 passed isolation/cleanup/raw counts/hash preservation, full50, but proved post-goto landscape fetch('/') missing Page events despite exact socket counts and an independent listener. Cause: listeners scoped only to goto. This NEW S13 defect is not historical / origin. Add public standalone regression, retain listeners through capture and detach safely; target-recheck only. ASSESS untracked scope unavailable; native mode off.

L25 — Correction worker added exact standalone regression but did not edit helper: first RED saw /2 instead of /1; full51 then had correct counts but the SAME missing Page event. Extra / can occur without app imports, not proof of historical causality. Helper4/browser10 preserved. Final permitted same-blocker correction: listener lifetime and full trace in strict-count failures; no root investigation or weakened assertions.

L26 — Final Page correction retained listeners, cached request metadata and detached before owned teardown. GREEN1/helper4/full51 exit0 (full13.049s); parent regression1/diff/hash passed. Existing verifier target-rechecked event+restoration only, both exit0 (0.544s/0.012s), no blocker. Historical / and native platform qualification remained separate.

L27 — T7 coherent test-only slice: helper, helper tests, public trace regression, guide, tracking. Production/HTML unchanged; test_browser integration remained with unaccepted T3. ASSESS untracked scope unavailable, item4 independent proof completed, native review off. No push/CI/release; root diagnosis still required.

L28 — Standalone T7 unit committed locally as `5b34bd34db6acee3a8cd428a5569788abbbae2f0`:681 additions/2 deletions across helper, helper/trace tests, test guide and tracking. This coherent lifecycle/provenance unit exceeds the advisory400-line heuristic to keep its deterministic proof/docs together; no minification or extra slicing loop. Source/browser integration candidate and root README remain uncommitted and unpublished. Actual commit identity is recorded after creation for continuity.

L29 — Owner authorized new read-only diagnosis: `si, retoma el diagnostico`. One no-browser/no-client control server observed unsolicited GET / at127.0.0.1:46187 from peer127.0.0.1:40810, User-Agent Go-http-client/1.1. At handler start, `ss -Htnp 'sport = :40810'` exit0 identified the connected client `moshi-hook`, pid1118, fd10. Control job8 exited0 after19s, zero leftover fixture resources. Independent active portrait→landscape trace exited0 in1.144s with exactly /display2, no / or redirects, unchanged hashes/status. This proves origin of the reproduced control transaction, not retrospective provenance of every old failure. No process/source was modified.

L30 — Owner accepted S14 test-only adjustment: `si, te autorizo`. Keep raw all-socket counts and all traces; add exact case-owned counts plus explicit foreign counts rather than dropping probes or whitelisting User-Agent. All unexpected OWNED / requests must still be visible/fail exact owned assertions. Existing S13 raw-count guarantee remains; browser integration assertions now target emitted case traffic with total=owned+foreign independently pinned. T3 becomes pending behind T8 rather than blocked on a mystery process. Risk: item4 (handler-thread counters and scoped client instrumentation), requiring one independent scoped verifier after own tests. No source-browser commit/acceptance or publishing authority added.

L31 — T8 RED missing identity/routing; GREEN helper5, trace1, full52 exit0/12.829s. Parent helper5/trace1/diff/hash passed. request_headers and immutable owned/foreign counts partition raw counts under lock; scoped forwarding preserves headers; tagged / counted regardless UA, foreign / retained. Helper slice+233/-68; T3 integration uncommitted. No source/process/HTML changes.

L32 — Independent full52 passed but candidate-vs-baseline public probe proved explicit other-case marker overwritten during fallback/fetch/continue (helper272,313–316), turning two foreign paths into owned. Other S14 rules passed. One correction: exact regression RED/GREEN, case-insensitive default-only merge/caller preservation; targeted recheck, not new sweep.

L33 — S14 marker correction preserved explicit/case-insensitive identities and last override. RED observed; trace2/helper5/full53 exit0 (full13.602s); parent trace2 passed. Existing verifier rechecked only marker regression/casing restoration, exit0 (0.528s/0.012s), no blocker. ASSESS untracked limitation recorded; native switch unchanged/off.

L34 — T8 complete: raw/owned/foreign retained, strict owned /, no UA/path filter, explicit foreign identities preserved. Full53 and ten original browser scenarios pass. Commit standalone helper/tests/guide/tracking; T3 integration/source remain separate. No process/production changes or Windows/ZIP/USB acceptance.

L35 — T8 local70ee51f9bdc244820cf6414e15c98797dadd921d,311add/70del, no push. Resume previously deferred original T3a read-only verification after attribution; current no-capture-change constraint still required source findings surfaced before edits. App entry not implemented yet.

L36 — Independent first T3a review: browser10 plus five contract probes passed. S5 blocker proven without fixture.instrument: same-URL window.open('/display') yielded2 pages and owned/raw /display2, foreign0; regression exit1. Guard admitted URL without page ownership. Instrumentation masked popup, so regression tags context directly. No source edits then; owner correction authorization required. Windows/real MARS/USB deferred.

L37 — Owner explicitly authorized correction and requested routine-work continuity (S15 quote). The previously external authorization blocker is resolved: T3 in progress. Perform the small main-page navigation guard/popup cleanup correction inline with public regression RED/GREEN, preserve existing browser scenarios and recheck only the source review's single blocker. Continue app assembly after this proof; do not ask permission for routine transitions. Official Playwright docs confirm popup first navigation must be intercepted by BrowserContext.route and Request.frame can be unavailable before a frame exists; fail closed for unknown/non-owned navigation and close extra owned-context pages without touching unrelated browser processes. No installer/USB protocol/publishing scope added.

L38 — Inline popup regression RED exit1 (/display2); owned-main-frame guard/fail-closed unknown-frame routing and extra-page closure yielded focusedGREEN1 exit0/0.521s. README updated. Full suite/targeted recheck still pending then. New BrowserSession had no tracked baseline CLI; existing10 preserved by suite, not Git-history tests.

L39 — Popup full54 exit0/13.726s, old10 preserved. Existing verifier target-rechecked popup+normal source only: one owned GET/page, persistent reads, cleanup; no blocker. New source hash3a90ffcd15dec9d0e747a34bb37f324611875dfa40bd3cc22707fa6adadae358. T3a ready to commit, T3b pending; native mode off/no publication.

L40 — T3a local5f55f3e6bf720f0f74d578ac21371d9c353dbbc9,562add/16del; coherent capture/tests/docs over advisory400, no golfing/push. Next ordinary GUI module composition, idle startup/existing singleton/cancellation; no test-only CLI/control server or USB. Native Windows proof remainsT6.

L41 — T3b app.py/__main__/build_shell RED missing module, GREEN8/full62 exit0/17.025s (old54 intact); parent8/diff passed. Real browser→coordinator→simulation/tray tests proved both RGB geometries, exact owned traffic, stop/exit and unchanged settings. Fake Windows only branch proof. ASSESS item4/native medium/verify=true, reviewDue=false. Native no-console visibility isT5; passive discovery not implemented yet, T6 external.

L42 — Independent T3b PASS, no blockers/advisories: focused8, exact unsupported exit1/no Qt/config writes, admission/duplicate/config hashes/guard passed. Real QApplication.exec reentry proved responsive cleanup, guard held for live worker, then exit_ready/worker close/release and exact error exit1. Existing18 files unchanged, no full62 repeat. T3 software scope done; T4/T5 and nativeT6 outstanding.

L43 — T3b locale951bbb0a4b6f2f4caea07e1a988d69bbc57b272,388add/27del, no push. T4 remaining: passive descriptor inventory/explicit identity API, never Serial/open/probe/write or VID/PID protocol inference; missing/duplicate identities cannot fall back toCOM. UI saved ID remains read-only pending hardware; sole backend simulated. Synthetic tests only, no native compatibility claim; pyserial3.5 added only to projectvenv.

L44 — T4 RED missing devices, GREEN7/full69 exit0/16.607s and pipcheck. Parent7/diff passed. No real enumeration/Serial/USB, app/tray changes or chooser claim; frozen stable identities reject ambiguity and follow COM reassignment. Independent review then pending; resultL45.

L45 — Independent T4 PASS S1/S4/S7/S15, no blockers/advisories: focused7, pipcheck, two synthetic identity/lazy-failure/settings-hash probes, version/license metadata and21 unchanged source/test hashes. No full69 repeat/device access. Universalwheel not Windows proof. T4 preparation done; runtime simulated, physical chooser/driver deferred.

L46 — T5 delivery-source only: native Windows-x64 one-folder, exact libraries/browser, windowed safe errors, notices/source/build inventory. Pin actions/least privilege/no secrets; bootstrap restricted feature-branch push then manual trigger after registration. No push/run without permission. Packaged startup smoke uses real exe/isolated state+lock and browser executable, not source-only; T6 owns real Exit/LAN/metrics. Linux fixtures are not Windows build proof.

L47 — T4 localf936dd21a2787e5bb5f67cbaa98478634a9148f3,298add/5del, no push. Local editable metadata refreshed with --no-deps --no-build-isolation (exit0/no downloads). Official GH docs require default file for workflow_dispatch; restricted feature push avoids silently updating main. T5a payload/windowed support precedes native recipe/smoke/workflow; source-only until approved push/CI, no synthetic.exe acceptance.

L48 — T5a1 worker wrote payload/notices/windowed entry support and12 focused tests; full81 passed16.375s. Payload validates source/runtime tree, refuses overwrite, writes inventory/source/checksum; windowed bootstrap captures trusted sanitized app errors and uses native temporary reporting with None streams. Installed vendor probe found real Playwright/Node/inlined sidecars and Chromium/FFmpeg registry/notices. It also correctly REFUSED missing installed license texts for Qt/pyserial; parent metadata file inspection confirmed none in their RECORDs. This material gap must be resolved from version-matched authentic upstream sources, not by changing expected tests or inventing licenses. Native builder/spec/workflow and real Windows build remain pending. Independent T5a1 delivery/privacy verification not yet run; T5 stays in_progress.

L49 — One read-only upstream research pass found authentic versioned license sources: pyserialv3.5 commit0e7634747568547b8a7f9fd0c48ed74f16af4b23 and PyPI sdist SHA2563c77e014170dfffbd816e6ffc205e9842efb10be9f58ec16d3e8675b4925cddb; Qt forPythonv6.12.0 commitf50facb83fc3dc5f3240c854668c7a6dd93871b2 LICENSES directory and source archive SHA256099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751; qtbasev6.12.0 commit025bdad181de241e81bf853c8a2d7bf3d19261a9. Fetch unmodified legal texts with exact version/source/hash provenance into third_party/license-material, then use explicit version-matched collector fallback; unknown/mismatched/missing/altered material must still fail. Binding texts are not blanket coverage of native Qt/WebEngine/Pdf plugins: actual Windows payload inventory/source mapping remains a delivery check. Source/material retrieval is routine authorized work; no legal certification or distribution approval inferred.

L50 — Official material retrieval job12 exited0 after8s:47 unchanged legal texts (pyserial LICENSE,8 Qt-forPython licenses,38 qtbase licenses) stored under third_party/license-material with source commit/URL/version/content SHA256 and explicit coverage qualifications. Pyserial text matched BOTH verified PyPI sdist archive hash and commit-pinned GitHub file. Data availability is not native binary coverage; no package/unit marked done from it. Next integrate explicit exact-version/hash fallback and corresponding-source inclusion, then independent T5a1 verification. Native recipe/workflow still not written; actual Windows ZIP/build/smoke and user acceptance remain unproved. Plan status reviewed: only T5 in_progress, T6 blocked on external Windows proof; source T1–T4/T7–T8 completion evidence preserved.

L51 — Added five unchanged leading copyright/SPDX headers from pinned PySide/shiboken/Qtbase source files, bringing material registry to52. Parent structural integrity check validated every path, case uniqueness, source commit/HTTPS reference and file SHA256, with no runtime/build/native tests claimed for passive legal data (no meaningful RED). Preserve unmodified upstream bytes; registry/README state binding/native qualification limits and exact source archive provenance. Commit data separately from packaging behavior for review; legal/vendor original lines are not authored application code. Next fallback integration must keep unknown/version-mismatched/altered material fail-closed.

L52 — Source data commit initially stopped at git diff --cached --check (exit2): upstream legal texts/headers contain original trailing spaces/blank EOF lines. Do not normalize legal bytes and invalidate provenance. Added narrowly scoped .gitattributes: upstream .txt files -text/-whitespace (also preserves exact hashes on Windows checkout), provenance JSON LF. Application/code whitespace checks remain active. Recheck required before commit; this is not bypassing native review/tests. Plan reviewed again: T5 remains in_progress;52 materials structurally verified but fallback integration/independent review/native recipe/workflow/Windows build still pending. No artifact or source helper completion inferred from data retrieval.

L53 — Scoped attribute correction verified: check-attr confirms legal .txt text/whitespace unset, registry JSON LF; subsequent diff-check exit0. Authentic data/config committed separately as `c0f9d4a2ad930f051a87a91c68b03b02769d919c` (upstream/vendor texts+generated registry, not authored runtime code). T5 still in_progress. The fallback now must integrate this immutable registry, preserve source inclusion and reject tampering/unmapped versions. No further basic authorization needed, no Windows build/CI or artifact upload.

L54 — T5a1 continuation integrated exact-name/version/hash fallback and legal source inclusion after RED missing support; GREEN18 focused tests and full87 passed16.565s (old81 preserved). Actual installed-runtime/vendor probe exit0:12 distributions,67 notice files including54 shared upstream inputs,10 vendor files. No remaining LICENSE-INPUT mapping gaps;41 supplementary Qtbase records remain explicitly unassigned as package/native coverage. Immutable parent legal data/attributes unchanged. Parent reran18 and diff-check passed. Native builder/spec/workflow not created; no Windows executable, real ZIP/smoke/legal qualification/hardware proof. Independent delivery/privacy review found two T5a1 blockers (L55); T5 remains in_progress.

L55 — Independent support-unit verification passed18 existing tests but reproduced two new-helper defects: collect_distributions followed an installed legal/LICENSE through a parent directory symlink to external bytes; assemble accepted Chromium revision9999 based on a README directory prefix while actual executable was1248. Two public regressions exited1 (ValueError not raised). Source/input status unchanged, no nativebuild/CI. Correct both in ONE scoped batch with observedRED/GREEN: anchor installed material to distribution root and reject parent symlink/escape before reading; require actual declared revision executable(s), not any prefix file. Preserve prior artifact bytes/rollback and original legal data, exact version fallback and safe no-console reporting. Then existing verifier rechecks only these blockers, no broad new sweep. T5a2 recipe/workflow and actual Windows still pending; no approval questions for these routine fixes.

L56 — Both T5a1 regressions observedRED, corrected root-anchored read_tree and exact declared executable validation then GREEN2/prior18/full89 passed16.587s; actual12-distribution67-notice+10-vendor collection still succeeds. Parent regression2 passed0.016s and immutabledata diff empty. Existing independent verifier target-rechecked ONLY the two blockers and directly affected valid-license/payload cases: all exit0 (0.019s/0.023s), no remaining support blocker. Source/helper unit now verified; commit it, not T5 completion. Native builder/spec/smoke/workflow and realWindowsartifact still pending. This coherent support unit is larger than400 advisory lines to retain privacy/provenance tests/docs; no code golf or extra slicing loop, raw upstream texts already separate.

L57 — Next unit T5a2 builds only on native Windows x64, includes actual bundled browser/driver/Qt platform resources, visible safe windowed errors and owned startup smoke with isolated LOCALAPPDATA/held-instance-lock readiness; an alive error dialog alone must not pass smoke. Stop only the owned idle smoke process, not global/user browsers; actual packaged Exit/Windows11/LAN/resource proof remains T6. Prepare restricted feature-branch push plus manual workflow, contents:read/no persisted checkout credentials, pinned official action SHAs, bounded job/7day artifact retention and no production endpoints. Do NOT execute/push/CI until explicit delivery authorization. Unit tests/spec structure are not native build evidence; T5 remainsin_progress.

L58 — Routine historical evidence above was condensed for recoverability after mem_get_observation truncated its ~50KB response before L57. Specs/tasks and verbatim user quotes remain unchanged; test outcomes, blockers, authorization boundaries and commit references retained. Full prior ledger through L57 remains in commit684d6e5a711b76a0e418a5897da908bdd2171d73; current evidence L48–L57 stays detailed. This is memory/readback maintenance, not line-budget code golf or a changed product requirement.

L59 — T5a1 source support committed 684d6e5a711b76a0e418a5897da908bdd2171d73; T5a2 uses verified helpers. Official action release SHAs and action.yml inputs checked: checkoutv7.0.1 3d3c42e5aac5ba805825da76410c181273ba90b1; setup-pythonv7.0.0 5fda3b95a4ea91299a34e894583c3862153e4b97; upload-artifactv7.0.2 cf430e030ddbb5b0abf93d22962f4752f3646cd9. All node24. Runner table supports windows-2025 (Server2025/VS2026), not Windows11 acceptance. Prepare/test source only; no push/CI execution yet. Windows-compatible unit tests must exercise unsupported-host branch deterministically rather than start native idle GUI. T5 remains in_progress until actual Windows artifact/smoke proof.

L60 — T5a2 initial SOURCE implemented builder/spec/smoke/workflow and12 new tests. Focused29/full101 exit0 (16.731s), help0/unsupported nativeguards1, immutabledata/diffcheck passed; no nativebuild or publication. Worker partial: collect_native requires unproduced build/native-material/native.json and runs before packaged smoke; current CI can only fail, without useful native inventory. This is a source data-flow dead end plus genuine target qualification gap, not a reason to fabricate mapping.

L61 — One bounded correction: compile/inspect owned stage, record actual native-file relative paths/hashes and measured versions/source metadata plus honest smoke result BEFORE missing qualification abort. Retain fail-closed final ZIP and prior output bytes. Workflow may upload only sanitized unqualified inventory metadata on failure; binary ZIP upload still only after successful qualification/smoke. No new approval receipt/lifecycle or invented qualification boolean. This diagnostic route makes a future explicitly authorized Windows CI run useful; it is not distribution/legal clearance, native proof or T5 completion.

L62 — Diagnostic correction RED2→GREEN2; focused32 exit0/0.393s/full104 exit0/16.272s, prior101 preserved. Independent SOURCE review PASS/no severe blockers: focused32 exit0/0.487s plus exact public help0/nativeguard1, no output writes;101 workspace hashes/index/status and55 immutable files unchanged. Actual Windows S3/S6 NOTPROVEN, no compiler/nativeAPI/Win11/ZIP qualification. ASSESS unassessable untracked scope, namedRisk5 independent satisfied; CLIglobal RDDoff/no transaction. Source unit is ready only for explicitly authorized diagnostic CI; native qualification still fails closed. Record local code commit then block T5 pending owner push/Windows-CI decision; T6 still waits real artifact/Win11 acceptance.

L63 — Source unit committed locally `a39fdf163acd982c77b7027fca02f1afefaeeb59` (coherent pipeline/tests/docs, no code golf; exceeds advisory400). Task plan reconciled: T1-T4/T7-T8 done only for stated software/preparation scopes; T5 BLOCKED on important public push/Windows-CI authorization, not done; T6 BLOCKED on actual artifact/user Win11 acceptance. No push/CI/ZIP yet. Next decision: public feature-branch CI/test artifacts7days, native inventory first and ZIP only after missing native notices plus smoke pass; no main/PR/release/installer/hardware authority.
