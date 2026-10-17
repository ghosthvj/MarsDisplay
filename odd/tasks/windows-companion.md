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

Runtime scope selected by the user, verbatim:
> Minimal app-required runtime (recommended)
> Remove only proven-unneeded plugin roots before dependency collection, preserve required DLLs, correct component-version provenance and reverify Windows.

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
- T5 [S1,S2,S3,S6,S7] route: delegated (context backstop), inline bounded test-only CI correction; status: in_progress (owner chose minimal app-required runtime; prior T5 CI authority retained); commits: legal data `c0f9d4a2ad930f051a87a91c68b03b02769d919c`, T5a1 `684d6e5a711b76a0e418a5897da908bdd2171d73`, T5a2 `a39fdf163acd982c77b7027fca02f1afefaeeb59`, CI test fix `63db500d1535c57908558be2b59053f45c21b23a`, winldd notices `ba5be6aa1eddee076855f1fc2d6feec657773a91`, runtime DATA `9cf6ee7eab900cdd0294191de48894f0b10969f1`, Qt smoke `fa408d0eece17652ec559550c7e1f9ebe8cf8139` — SOURCE payload/notices/bootstrap/spec/build/smoke/workflow prepared; base source104/independent32 passed; current bounded test-only correction has local106 and independent10 passing; Windows run39026203729 passed source tests; winldd prebuild passed Windows; runtime DATA validated on Windows39032168531; smoke Qt return-contract correction local118/independent6 passed; Windowsrun39033278476 verified packaged smoke passed; native qualification missing. Minimal-runtime choice resolved; stage1 source121/independent23 passed, fresh minimized Windows inventory/smoke and component-version/provenance correction remain. No qualified ZIP. Native Windows EXE/COLLECT assembly proved in39029908479; no execution/smoke/native-qualified ZIP or artifact upload. First authorized Windows run obtains unqualified native inventory; final ZIP requires genuine native mapping and smoke. T5 remains incomplete; do not mark done from Linux/synthetic/source proof.
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

L48 — InitialT5a1 source12focused/full81 exit0/16.375s. Helpersvalidateexclusivepayload/source/hashinventoryandsanitizedNone-streamstartup. Vendorprobe correctlyrefusedmissingQt/pyserialtexts; authenticversionedinputsneeded, notinventedlicenses. Independent/nativeproofthenpending.

L49 — One read-only upstream research pass found authentic versioned license sources: pyserialv3.5 commit0e7634747568547b8a7f9fd0c48ed74f16af4b23 and PyPI sdist SHA2563c77e014170dfffbd816e6ffc205e9842efb10be9f58ec16d3e8675b4925cddb; Qt forPythonv6.12.0 commitf50facb83fc3dc5f3240c854668c7a6dd93871b2 LICENSES directory and source archive SHA256099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751; qtbasev6.12.0 commit025bdad181de241e81bf853c8a2d7bf3d19261a9. Fetch unmodified legal texts with exact version/source/hash provenance into third_party/license-material, then use explicit version-matched collector fallback; unknown/mismatched/missing/altered material must still fail. Binding texts are not blanket coverage of native Qt/WebEngine/Pdf plugins: actual Windows payload inventory/source mapping remains a delivery check. Source/material retrieval is routine authorized work; no legal certification or distribution approval inferred.

L50 — Primaryretrievaljob12 exit0/8s stored47unalteredtexts/sourceURLs/versions/hashes. Pyserialmatchedverifiedsdist+commitfile. Dataavailabilitynotnativecoverage; no runtimeunitdone; fallback/sourceinclusion/Windowsproofthenpending.

L51 — Fiveunalteredcopyright/SPDXsourceheadersadded→52records. Structuralpaths/case/sourceURLs/commit/SHAchecks passed; passivelegaldatahadnomeaningfulRED. Binding/nativecoveragequalificationretained; no nativeclaim.

L52 — Initialgitdiffcachedcheck failed2 onUPSTREAMwhitespace. Scoped.gitattributes preservesraw.txtbytes(-text/-whitespace), registryLF; nolegalnormalization, ordinarycodechecksremain. Neededrecheckbeforedata commit, nottest/RDDbypass.

L53 — Attributecheck/diffrecheckexit0; data/configcommitc0f9d4a2ad930f051a87a91c68b03b02769d919c. Old52rawinputsimmutable; exactfallback/source/tamperrejectionnext. NoWin/CI/artifactthen.

L54 — FallbackRED→focused18/full87 exit0/16.565s(old81retained), parent18+diffpassed. Real12dist/67notices(54shared)/10vendor exit0;41qtbaseentriesnotnativecoverage. Dataunchanged; independenttwo-blockerfindingsL55, T5notdone.

L55 — Independent T5a1 review reproduced two new-helper defects: installed license parent symlink exported external bytes; revision9999 README plus1248exe falsely qualified. PublicRED2; one bounded correction authorized within existing scope, no native/publishing proof.

L56 — T5a1 root-anchored read_tree/exact-exe fix GREEN2/prior18/full89 exit0/16.587s. Real12dist/67notices+10vendor retained; parent2/0.016s and targetverifier2+2/0.019s,0.023s passed. No olddata changes. Coherent support slice retained tests/docs over advisory400; nativebuilder/T5 stillpending.

L57 — T5a2 scope: nativeWinx64 spec/build, realbundledresources, safe windowedstartup, owned isolated lock+GUI-idle smoke (not alive/error dialog). Only own idleprocess cleanup; actualExit/LAN/Win11/metricsT6. Restrictedfeaturepush+manualworkflow/contentsread/no creds/pinnedactions/30min/7days. No remote execution before explicit ownergrant.

L58 — Historical routine evidence was shortened after ~50KB Engram readback truncation. Specs/verbatimuserquotes remain; complete earlierledger throughL57 is in684d6e5. This maintains recoverability, not line-budget code golf.

L59 — Official node24 actionpins/releases verified (exactSHAs inworkflow); runnerwindows-2025 isServer2025/VS2026, notWin11acceptance. T5a1 committed684d6e5; T5a2preparedsource onlythen. Windows tests mustexerciseunsupportedhostbranch deterministically, no accidentalGUIhang.

L60 — T5a2 initialsource12new tests focused29/full101 exit0/16.731s; help0/hostguard1 andimmutable/diff passed. Partial: missingnative-material/native.json stoppedbefore smoke and destroyed neededinventory. No native/CI/ZIP; correct that sourcedata-flow deadend, don'tfabricatemapping.

L61 — Bounded correction retains sanitized unique unqualified native hashes/versions and honest owned-smoke status before qualification failure. Metadata-only failure upload; final ZIP still requires genuine qualification/smoke/stablesource. No approvalreceipt/framework/trueflag; nativeproof requires authorizedWinrun.

L62 — DiagnosticRED2→GREEN2/focused32 exit0/0.393s/full104 exit0/16.272s. IndependentSOURCE32 exit0/0.487s+help0/hostguard1 passed/no writes;101 workspace+55immutable unchanged. ActualWin S3/S6 NOTPROVEN; ASSESS untrackedunassessable/Risk5independent satisfied/globalCLIoff/no transaction.

L63 — Sourcea39fdf163acd982c77b7027fca02f1afefaeeb59 committed. Plan thenT5blocked on ownerpush/WindowsCI, T6blocked onartifact/Win11. NoZIP. Nativeinventory first/qualifiedZIPlater; nomain/PR/release/installer/hardware authority. Subsequent livegrantL64 supersedes that authorization blocker.

L64 — Live owner choice: question `¿Autorizás subir \`feat/simulated-companion\` a \`ghosthvj/MarsDisplay\` y usar CI Windows para cerrar T5?`; selected `Sí: rama, CI y artefacto de prueba`, effect `Autoriza los pushes de T5 y CI: primero inventario JSON; ZIP solo después de completar avisos nativos y pasar smoke. Artefactos por 7 días. Sin main, PR ni release.` (authorize_t5_delivery). T5 returns in_progress for that scoped delivery; no source/native qualification or Windows11 proof invented. T6 remains blocked. Execute feature push and watch exact new-commit run; no manual default-branch change.

L65 — Authorizedfa79218 push/Winrun39024652172/job117373141273 failed1/source tests, setup/SDK/browserinstallpassed. Nativebuild/smoke/uploads skipped; retrieveexactlogbeforerepair. Noartifact.

L66 — FirstWin104/31.099s: portrait4000ms `Application condition was not acknowledged before deadline`, thenlostshell→landscapeNoneType/tempWinError32. Otherbrowser/packagingtests passed. Runtimecauseuncaptured; test-onlyownership/diagnostic/coldbudgetfix, no productiontimeout/retry/sandboxchange.

L67 — ValidcleanupRED1 exit1/0.026s→GREEN2 exit0/0.027s; App10/2.425/full106/16.427s exit0, exactassertionskept/src-materialunchanged. ProbeconstructorrecursionfixedbeforevalidRED. ASSESSmedium/Risk5independent/reviewDuefalse; nativerecheckthenpending.

L68 — IndependenttestSOURCE App10 exit0/2.380s/no blockers,97workspace/index/status+75protected unchanged. OriginalWinruntimecauseunproved, noZIP. Code63db500d1535c57908558be2b59053f45c21b23a; newcommitCIunderL64, notunchangedrerun.

L69 — Authorizeddaf36a9 push/Winrun39026203729/job117377569404 sourcepassed/nativefailed1. Diagnosticstepgreenwasnotartifactproof; actualerror/emptyinventoryL70. Noqualifiedartifact.

L70 — Run39026203729 precompile `Portable build failed: Missing browser license material: winldd`, artifacts[]. Installedtool1007→PrintDeps.exe/core1.64.0-beta-1791568591000; no ownershipassumption. Explorer lackednetwork/hashcapability; parentprimaryjobs19–20 suppliedfacts. No bypass/dependencychange.

L71 — npmcorebeta source1b2924712024804936dbcfe9fabaa655d52325e5 differsstabletag606ecd8b34bac100db32561b6278ffd76e5eb3cd. PrintDeps1–39MITJulien+ApacheMS; BUILD_NUMBER1007/registry andRootlegalbytesmatched. Fourauthenticsupplementary packages[] inputs added, old52raw preserved; noQtqualification.

L72 — WinlddRED2→GREEN2, focused23 exit0/0.303s/full113 exit0/17.789s, old106preserved. Exactcore/tool/source/legalhashes/optionalPrintDeps validation;56raw/58shared, old52records/bytes+attributes unchanged. Linuxvendor1248/1013/10notices, wlddabsent. No product/deps/workflowchanges.

L73 — Independent Winldd SOURCE review PASS:23 tests exit0/0.375s/no skips;102 files/index/status unchanged, original52raw/records plusruntime/workflow/build/spec/deps/.gitattributes unchanged. FournewrawSHA/sizes match, packages[] supplementary. Local113/17.789s stand; no fullrepeat. Exactcore/tool fallback retainsMIT+Apache2, rejectsbadidentity/material/executable, no nativeQtclaims. Commit this unit and newcommit CI underL64. Prior routine supportlogs shortened only for fullmirror recoverability; specs/userquotes intact. SourceWinlddcommit `ba5be6aa1eddee076855f1fc2d6feec657773a91` (388 authored/342 verbatim upstream lines). New native CI remains pending.

L74 — Run39029908479/082047b sourcepass/nativefail/no diagnostic/ZIP. Exactfailedlogretrieved, nativeassembly/runtime causefollowL75; no unchangedretry.

L75 — Exact390299 logs prove WindowsEXE+COLLECT, notexecution. read_tree rejected `Duplicate path or empty/non-byte material`. PinnedSDKhasinstalleremptyflags/.links; scopedpostAnalysisDATAselectionkeepsglobalguards. SourceSDKunchanged, noQt/ZIPclaim.

L76 — Initialselection116passedbutSDKprobeoneempty remained: playwright/py.typed (PEP561). ParentalsofoundPIL/pyeeempty/PySide6-shiboken33byte rootmarkers. Same-blockercorrectiononlysixknownrootDATAmarkers, unknown/deeper/nonDATAretained; no blanketemptyallowance.

L77 — SelectionRED1/0.015→GREEN1/0.013; typingRED1/0.017→GREEN1/0.014. Focused35 exit0/0.439/full117 exit0/17.974; SDK410→404/sixexclusions/remainingempty[]/ninelegal+runtime retained, sourceSDKstats/79protectedunchanged. Nativeproofstillpending then.

L78 — IndependentselectionSOURCE35 exit0/0.549/no skips;104workspace/index/status unchanged,77explicitprotectedbaselineidentical(writer79manifestnotseparatelyavailable). Requireddata/guardsretained; source117notnativeexecution. Commit9cf6ee7eab900cdd0294191de48894f0b10969f1; userquotes/specsunchanged.

L79 — Run39032168531/b65457a sourcepassed/nativefailed1; diagnosticstepgreen/no warningwasNOTproof untilartifactAPI. ZIPskipped; exactartifact/errorconfirmedL80. T5in_progress/T6blocked.

L80 — Verified actual artifact12100766606 downloaded JSONonly tobuild/ci-39032168531/unqualified-native-ktwvwxo1.json (SHA2567acb319ca6e48785345576141abf135f642461121c4d9b11b8224d2cc8ae72fc). UNQUALIFIED/failure_phasepackaged_smoke,136nativefiles/106sourcefiles, Qt6.12/Python3.13.16. Actualerror `not enough values to unpack (expected 4, got 3)` maps smoke.native_ready'sgetLockInfo; installedQtCore.pyi5210 returnsTuple[int,str,str], mockincorrectlyfour. Inline boundedSDK-contractRED then3valuePID/heldlockfix/fakealignment, no app/runtime/gateweakening. NativeQt stillunqualified, T5in_progress/T6blocked.

L81 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` Planreviewed/reconciled: T1-T4/T7-T8 retainverifiedsoftware/preparationscopes; T5in_progress actualWinassembly/resources+UNQUALIFIEDreport verified, smokefailed. QtcontractRED1 exit1/0.045s matchedactualValueError; source3valuefix+realSDK/mockedGUIfocusedGREEN2 exit0/0.054s only. Fullsuite/review/newWinCI pending; Qtattribution/qualifiedZIPunproved. T6blockedartifact/Win11. No newlydone task; routineevidencecondensedforfullmirror.

L82 — Qtcontractsource smoke6 exit0/0.165/full118 exit0/17.685; old117retained/protecteddataunchanged. Fourbase-vs-currentbuild/smokeCLIhelp+Linuxguard outputs/exits match; differential0. RealSDKRED/GREENnotWinGUIproof. Risk5independentthenpending.

L83 — IndependentQtSOURCE6 exit0/0.173/no skips;104workspace/index/status/99othertrackedfiles unchanged. Full118/CLIdiff supplied, no rerun/nativeclaim. Commitfa408d0eece17652ec559550c7e1f9ebe8cf8139.136-fileUNQUALIFIEDreport permitsreadonlyattributionmap, notapproval.

L84 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` Reviewed: T5in_progress/T6blocked, no newlydone. CI39033278476/00108ef sourcepassed/nativefailed, exactlog/artifact job28pending. Readonlymap:46Qt-prefixnativefiles includesPdf/Qml/Quick/VirtualKeyboard/Svg/plugins andsixnonQt-candidates;90outsideprefix. Collectorwronglyforcesallversion=Qt; generictexts notcompleteattribution. Pinnedhooks collectbroadpluginfamilies; targetedQtGui-wrapperproposal BEFOREnativeclosure, notsupportedhookconfig norblindDLLdeletion. AppusesWidgets/raster; removerequirements/nativeedges notyetproven, retainNetwork/Mesa/CRT pendingevidence. No mapping/qualification/codechanges.

L85 — Exact39033278476 log: nativeEXE/COLLECT complete; `Portable build failed: Missing reviewed native notices: build/native-material/native.json; Windows qualification is pending`. Actualunqualifiedartifact12101312078 exists12,164bytes; reportdownloadjob29 verifyingexplicitphase/smokestatus. Nativequalification remainsabsent, noZIP. Beforebroaderplugin/provenancemodelchanges, presentconsequentialruntime-scope choice (minimalrequestedGUI vsretainbroadSDK/source-onlypause), notlicenseapproval or guardbypass. Nothing newlymarkedcomplete.

L86 — Actualreport39033278476 downloadedJSONonly: build/ci-39033278476/unqualified-native-jlx0yvx6.json SHA256aea9c2af402d2f011e58e4c3a416bb456f2ef847d0afca647b3ad75cd4ac50f8/31,691bytes. UNQUALIFIED, source00108ef, failure_phasenative_qualification, packaged_smoke.status=passed,136nativefiles/Nodev24.21/Qt6.12/Python3.13.16. Native frozenstartup/binarysmoke VERIFIED, notnormalExit/Win11/legalqualification/ZIP. T5BLOCKEDonconsequentialminimal-vs-broad runtime/provenance scope choice beforeexpansion; T6stillblockedartifact/Win11. Recommendminimizeprovenunneededpluginroots, preserveunknownrequiredMesa/CRT, correctcomponentversions/evidence, no bypass. No new taskmarkedcomplete. Prior routineobserverlogs shortenedforfullmirror, userquotes/specs unchanged.

L87 — Live owner selected `Minimal app-required runtime (recommended)` / `Remove only proven-unneeded plugin roots before dependency collection, preserve required DLLs, correct component-version provenance and reverify Windows.` (minimal_runtime), in answer to `Which runtime scope should I use to finish native attribution before producing the ZIP?`. S6only amendedwithverbatimscope; T5resumesin_progress/T6blocked. Firstboundedunit targets identifiedoptionalPDF/SVG/virtual-keyboardpluginROOTS viarepo-localQtGuihookbeforeclosure, notblindDLLdeletion; preservebase/Core/Widgets/Network/Mesa/CRT/platform/styles/untargetedplugins. Newinventory/smoke beforeadditionalcuts; provenanceversionmodel/evidence follows. Oldbroadbundlesmokepass doesnotprovefutureminimalcandidate. No main/PR/release/hardwareauthority.

L88 — MinimalQt stage1 SOURCE RED1/0.002→GREEN1/0.002; focused23 exit0/0.360s/full121 exit0/17.990s. RepoQtGuihookfiltersONLYfourfamily/namepluginroots beforeclosure; stocktraversal/validation/hiddenimports/datas/defaultotherhooks+descriptoroverride restoration retained.80protected+482SDKhook/Qt-sourceRECORDhashes unchanged; speconlyhookspath. No minimizedWindowsoutcomeclaimed. IndependentRisk5review/newnativeinventory+smoke pending; component-version/provenance nextunit andqualifiedZIP absent. T5in_progress/T6blocked.

L89 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` ReconciledT5in_progress/T6blocked: stage1SOURCE independent23 exit0/0.433s/no skips/no severe blockers;107workspace/index/status and99othertrackedfiles unchanged. Local121 stand. No minimizedWinprooftransferredfromoldbroadsmoke; version/provenance andqualifiedZIP remainpending. Recordstage1commit thenauthorizednewCI. Routine oldmaterial logs shortenedforfullmirror, specs/userquotes retained. Minimal-plugincommit recording.
