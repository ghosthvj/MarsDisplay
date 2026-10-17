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

> Si, aplica la correccion necesaria pues por lo que se ve el uso de RAM sigue aumentando

Per-frame layout-wait handles must be released without changing readiness, geometry, security or retry behavior. Deliver the authorized corrected 0.1.2 portable ZIP after verification.

Acceptance: persistent isolated browser captures the existing `/display` region in memory; MARS owns selection/order/dwell/live updates/orientation. Nominal frames are 320×480 or 480×320, without stretching. Simulated output retains bounded state and is never reported as a connected USB screen. Establish actual readiness metadata before real MARS integration; HTTP 200 alone is insufficient.

### S6 — Portable-first Windows delivery
> ok, mantengamos la propuesta de desarrollar desde linux y generar el ZIP desde GitHub Actions para hacer las pruebas locales antes de generar un instalador

Acceptance: source tests on Linux; Windows-built portable ZIP with declared runtime/browser/notices and packaged smoke test; local Windows 11 acceptance and resource measurements are separate evidence. Workflow source implementation is in scope; remote execution/publication requires authorization.

Runtime scope selected by the user, verbatim:
> Minimal app-required runtime (recommended)
> Remove only proven-unneeded plugin roots before dependency collection, preserve required DLLs, correct component-version provenance and reverify Windows.

Distribution prerequisite selected by the user, verbatim:
> VC++ oficial como requisito externo — recomendado
> El ZIP incluye Python, Qt y Chromium, pero no redistribuye las DLL de Microsoft. Si falta VC++ x64, el usuario lo instala desde Microsoft. Sin instalador de MarsDisplay.

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
- T3 [S1,S3,S5,S10,S15] route: inline for bounded popup correction, delegated context-backstop for subsequent app assembly; status: done (S5 handle cleanup RED/GREEN/full144/independent14 verified); commits: T3a `5f55f3e6bf720f0f74d578ac21371d9c353dbbc9`, T3b `e951bbb0a4b6f2f4caea07e1a988d69bbc57b272` — actual MARS contract inspected, persistent browser and controlled fixtures under test. Access is HTTP(S) without interactive login.; bootstrap repair: 5d0de48b4f08c38a33c5027195e18841fe2c86d4; handle cleanup: `93b222b77ac07141d561e8735ef6bbb037747315`
- T4 [S1,S4,S5,S7] route: delegated (context backstop); status: done (software preparation/simulated pipeline only; native inventory and physical chooser deferred to identified hardware); commit: `f936dd21a2787e5bb5f67cbaa98478634a9148f3` — both-orientation capture/bounded simulated pipeline proved by T3b; passive USB-serial descriptor inventory and explicit conservative identity-selection APIs/tests without choosing a protocol, auto-selecting a port or writing USB. Runnable output remains simulated; physical GUI chooser/driver qualification waits for identified hardware.
- T5 [S1,S2,S3,S6,S7] route: bounded implementation and independent Risk5 source/policy verification; status: done (0.1.2 CI39065994952 and downloaded ZIP/source/hash/profile verification passed; owner acceptance remains T6); owner acceptance is T6); delivery source commit: `93b222b77ac07141d561e8735ef6bbb037747315`; principal final units: external profile `6e9218ab46f6a92cee4e2f6f3245eb6a21462e69`, native data `dcc7ff6cd526bc7c9843bec151ba120745625965`, policy `97bf8a0ca5d06f61e1feb1d8b5f776bd5fbf4b6d`, provisioner `ff55d90fb348649016b59f610a35d722b00aa868` — source141/independent44 passed; actual Windows run39049628794 compiled, smoked, qualified and uploaded artifact12107551102. Downloaded205549310-byte ZIP verified SHA256f304b389b02b214ee7f090e609e1035256046ddb420ffea50f248d612fffb8fb,1221file/325sourcehashes,69native/27Qt+6supp; no selected Microsoft DLLs or Qt Mesa. VC14.51+x64 external prerequisite acceptedS6. Output remains simulated; T6 separate. Earlier work-unit commits/evidence retained in Log.; 0.1.1 source: 5d0de48b4f08c38a33c5027195e18841fe2c86d4; 0.1.1 source: `5d0de48b4f08c38a33c5027195e18841fe2c86d4`; 0.1.2 candidate: `93b222b77ac07141d561e8735ef6bbb037747315`, CI39065994952 passed; artifact12112754920 verified
- T6 [S1,S4,S5,S6] route: local Windows acceptance by owner; status: blocked (owner Windows screenshots now running/ready with increasing frames; 0.1.1 capture/Start/Stop/restart/normal Exit confirmed by owner; unreachable-source exhaustion/resume and Ethernet-loss/live restoration observed; both Node Stop closure confirmed and preliminary RAM estimate available; awaits owner 0.1.2 sustained Windows benchmark, remaining Chromium/Exit cleanup and Stop-during-retry evidence); commit: evidence pending — actual tray/normal Exit/LAN/recovery and process-tree RAM/CPU measurements. Server2025 CI is not Windows11 acceptance. Physical USB/protocol validation remains deferred.

- T7 [S13] route: delegated (context backstop); status: done (fixture-only scope); commit: `5b34bd34db6acee3a8cd428a5569788abbbae2f0` — per-test fixture, strict counters, HTTP/Page/Route provenance through later captures, bounded cleanup and corrected listener teardown verified. Helper4, public trace regression1, full51 and targeted independent recheck passed. Standalone helper/trace tests/docs commit independently; unaccepted BrowserSession and its test_browser.py integration remain uncommitted under T3.

- T8 [S14] route: delegated (context backstop); status: done (test-only scope); commit: `70ee51f9bdc244820cf6414e15c98797dadd921d` — test-only per-case request identity, exact owned counters, retained foreign/raw observations and deterministic attribution regression tests. Do not modify/accept capture or disable host hook.

## Log

L1 — Original implementation request, verbatim:
> ok, pues empecemos a implementar lo que hemos definido en el plan y teniendo en cuenta que aun no tengo la pantalla

L2 — Owner selected `x64 — Intel o AMD`, `Python + Playwright + PySide6 + PyInstaller`, and `Incluir Chromium en el ZIP`. Repository choice already completed. Additional product decisions in WO5–WO10/WO12–WO14 remain checkpoints before dependent implementation.

L3 — Baseline `e6160e5` contains only LICENSE; working branch created from main. No existing application behavior or CLI to preserve/differentially compare. Initial behavior uses unittest to avoid making test execution depend on GUI/browser packages. The host has Python 3.13.5 but no pip/setuptools in its system interpreter; do not modify system Python or claim packaging success from source tests.

L4 — Primary PyPI confirmed selected Windows-x64 candidate pins; official Playwright/PyInstaller packaging docs inspected. Qt deployment page contained stale2021 limitations, not acceptance. Pins/install/native execution remained distinct evidence.

L5 — Risk: item 5 (dependency declarations and future packaging/environment compatibility); item 4 applies when lifecycle workers are introduced. Independent foundation verification completed with no blockers. Native review mode reads `off (decided by global)` in this clone; do not start native review or change the switch.

L6 — T1 RED missing module → GREEN six tests; parent/independent checks passed. Build probe failed: No module named build; no retry/install. Pins validated, not Windows/packaging proof. See foundation commit and earlier Engram for full output.

L7 — ASSESS item5 requested independent verification but could not scope untracked files. Facade rddLine=on disagreed with clone CLI off globally; no transaction or mode change. Source verification proceeded via the named risk, not fabricated review authority.

L8 — Owner answers, verbatim: `Cadena sobre rama de funcionalidad — recomendado`; `Sí, usar la propuesta conservadora`; `Reintentos limitados — recomendado`; `HTTP o HTTPS sin pantalla de login`. The accepted local-behavior preview and recovery/access descriptions are preserved in S8–S10. Commit the verified foundation as slice 1, then implement settings/lifecycle/tray as the next coherent unit. T1's 358 authored lines plus tracking exceed the heuristic slightly; keep its tests and readable documentation rather than artificially splitting them.

L9 — Foundation committed b233d6e1f645513c359142c42e21e497b9c4b011, no push. T2 split by behavior. Project .venv install started; system Python/MARS unchanged.

L10 — Isolated install succeeded (exit 0): `.venv/bin/python -m pip --disable-pip-version-check install --retries 0 --timeout 30 -e '.[build]'`; an editable Linux wheel was built with the pinned backend and dependencies. This resolves local install availability, not Windows packaging proof. .venv is Git-ignored. Do not add QtWebEngine usage merely because the PySide6 wheel pulls it transitively.

L11 — MARS /display contract verified through gh: #mars-display/version1, loading|ready|empty|error, orientation/geometry/server/live-stale metadata; disabled/config redirects /. Fonts/layout required. Docs blob a4b7c401c3bae187e7158227e4d6ab34b5628afe, Display083d86fa027943ba437ea620bc9c0b9db65f14e4.

L12 — T2a RED missing settings module; GREEN8 and full14 exit0. Parent focused8 and independent14 plus isolated validation/failure/hash probes passed, no blockers. Atomic rejection/replace cleanup preserved; Windows filesystem proof deferred. ASSESS item1/native medium/independent=true, reviewDue=false; no native review.

L13 — Qt availability failed1: `ImportError: libEGL.so.1: cannot open shared object file: No such file or directory`; ldd confirmed only libEGL missing. No retry/install before owner authorization (L14). Settings proof unaffected; README recorded this prerequisite.

L14 — Owner explicitly selected `Autorizo instalar libegl1 y sus dependencias` (token install_libegl1). This unblocks the system prerequisite installation, not GUI acceptance itself. Run the scoped package installation once, then a fresh Qt availability check after the environment change; do not install unrelated system packages.

L15 — Authorized apt install exited0: libegl1 1.7.0-1+b2, libegl-mesa0 and libwayland-client0, no unrelated upgrades. Fresh QApplication offscreen probe then exit0. Linux availability is not Windows acceptance. Coordinator and tray are separate slices; initial internal capture baseline1Hz with synchronous backpressure, not a hardware guarantee/user refresh option.

L16 — Coordinator RED→GREEN13/full27; parent13/independent27 plus3 Event-controlled probes passed. Stop/Exit cleanup, retry policy/uncertainty latch proved. Risk4 verification satisfied; native review off.

L17 — Repository-local Chromium headless shell installed via PLAYWRIGHT_BROWSERS_PATH=0 (Playwright revision1248 plus FFmpeg1013), exit0. A real local HTML screenshot with `chromium_sandbox=True` succeeded, exit0, 3229 PNG bytes. No TLS/sandbox bypass, production URL or USB access. Browser availability is now proven on Linux, not real MARS integration or Windows packaging.

L18 — Tray RED→GREEN9/full36, parent9/independent36 and singleton/queued-save/cleanup probes passed. Lock precedes factory and remains until cleanup; offscreen not Windows proof. Runnable entrypoint was T3.

L19 — T3a initial worker GREEN46 was not accepted: parent landscape expected /display2 but saw additional /1. Required causal/isolation correction; BrowserSession uncommitted. App assembly still pending then.

L20 — First bounded T3a correction added header diagnostics and exact counts after third read/close (+8test lines), but did not explain/fix /. Focused10/full46 exit0 (11.922s/12.678s) were NOT accepted as a fix; worker partial. No browser commit/independent review then; owner diagnosis decision required. Unaccepted code preserved.

L21 — Owner `vale, te autorizo a investigar` authorized read-only diagnosis. Static map found shared-server/counter reset without handler barrier (hypothesis only). Investigator probes unavailable due scratch-rule conflict; not retried. One parent in-memory disabled→portrait→landscape trace exit0/2cases/2.038s: no /. Source unchanged/e68d03a30f38f32b39ef10eb3a0b57b39eda8c4c6ca5ca45dad9ccd08a26ee11. Route.fetch forwards headers, so UA alone proves no process identity.

L22 — Owner selected the S13 proposal: `adelante te autorizo`. This authorizes per-test fixture isolation/provenance and necessary tests/docs only; no capture-source fix or acceptance. T7 is a bounded test-only unit. Risk: item4 (fixture server/handler lifecycle and event attribution); independently verify once after the writer's RED/GREEN/focused/full checks. Keep all exact request-count assertions and include injected unexpected / traffic in them. No public delivery or source browser commit is authorized by this adjustment.

L23 — T7 RED→GREEN4; initial integration10 TargetClosedErrors corrected via detach-before-close; browser10/full50 passed. Source/HTML unchanged; exact unexpected counters retained. Independent finding followedL24.

L24 — IndependentT7 full50 passed but proved post-goto landscape fetch omitted Page events. NewS13 defect, not historical / causality. Required lifetime correction and targeted regression, no source writes then.

L25 — Initialcorrection kept exactregression: RED /2 vs/1 then same missingPageevent. Other / can occur without app imports. Helper4/browser10 retained; finalsame-blocker listener lifetime correction authorized.

L26 — FinalPagefix GREEN1/helper4/full51 exit0/13.049s; parentregression/diff/hashpassed. Targetverifier event/restoration exit0/0.544s,0.012s. Historicalrequestorigin/nativequalificationremainedseparate.

L27 — T7 independent lifecycle/provenance slice; source/browser integration stillT3. Risk4verificationdone, actualRDDoff; no push/CI/release. Rootdiagnosisstillrequiredthen.

L28 — T7 committed5b34bd34db6acee3a8cd428a5569788abbbae2f0,681add/2del. Coherent test lifecycle/provenance slice kept tests/docs; source/browser integration stayed unaccepted/unpublished. No push.

L29 — Owner authorized new read-only diagnosis: `si, retoma el diagnostico`. One no-browser/no-client control server observed unsolicited GET / at127.0.0.1:46187 from peer127.0.0.1:40810, User-Agent Go-http-client/1.1. At handler start, `ss -Htnp 'sport = :40810'` exit0 identified the connected client `moshi-hook`, pid1118, fd10. Control job8 exited0 after19s, zero leftover fixture resources. Independent active portrait→landscape trace exited0 in1.144s with exactly /display2, no / or redirects, unchanged hashes/status. This proves origin of the reproduced control transaction, not retrospective provenance of every old failure. No process/source was modified.

L30 — Owner accepted S14 test-only adjustment: `si, te autorizo`. Keep raw all-socket counts and all traces; add exact case-owned counts plus explicit foreign counts rather than dropping probes or whitelisting User-Agent. All unexpected OWNED / requests must still be visible/fail exact owned assertions. Existing S13 raw-count guarantee remains; browser integration assertions now target emitted case traffic with total=owned+foreign independently pinned. T3 becomes pending behind T8 rather than blocked on a mystery process. Risk: item4 (handler-thread counters and scoped client instrumentation), requiring one independent scoped verifier after own tests. No source-browser commit/acceptance or publishing authority added.

L31 — T8 RED missing identity/routing; GREEN helper5, trace1, full52 exit0/12.829s. Parent helper5/trace1/diff/hash passed. request_headers and immutable owned/foreign counts partition raw counts under lock; scoped forwarding preserves headers; tagged / counted regardless UA, foreign / retained. Helper slice+233/-68; T3 integration uncommitted. No source/process/HTML changes.

L32 — Independentfull52 passed but publicdifferential proved other-case marker overwritten in fallback/fetch/continue, falselyowned2paths. RequiredstrictRED/GREEN/case-insensitive default-onlypreservation, notnewbroadreview.

L33 — S14 marker correction preserved explicit/case-insensitive identities and last override. RED observed; trace2/helper5/full53 exit0 (full13.602s); parent trace2 passed. Existing verifier rechecked only marker regression/casing restoration, exit0 (0.528s/0.012s), no blocker. ASSESS untracked limitation recorded; native switch unchanged/off.

L34 — T8 completedtestscope: raw/owned/foreignretained, strictowned /, calleridentitypreserved. Full53+originalbrowser10passed; standalonecommit only, no production/process/Windows/USBclaim.

L35 — T8 local70ee51f9bdc244820cf6414e15c98797dadd921d,311add/70del, no push. Resume previously deferred original T3a read-only verification after attribution; current no-capture-change constraint still required source findings surfaced before edits. App entry not implemented yet.

L36 — T3a reviewbrowser10+5contractprobes passed exceptsameURLpopup:2pages//display2/foreign0 withoutinstrumentation. Mainpageownershipguardmissing; instrumentationmaskedpopup. PublicRED, no editbeforeauthorization.

L37 — Owner explicitly authorized correction and requested routine-work continuity (S15 quote). The previously external authorization blocker is resolved: T3 in progress. Perform the small main-page navigation guard/popup cleanup correction inline with public regression RED/GREEN, preserve existing browser scenarios and recheck only the source review's single blocker. Continue app assembly after this proof; do not ask permission for routine transitions. Official Playwright docs confirm popup first navigation must be intercepted by BrowserContext.route and Request.frame can be unavailable before a frame exists; fail closed for unknown/non-owned navigation and close extra owned-context pages without touching unrelated browser processes. No installer/USB protocol/publishing scope added.

L38 — Inline popup regression RED exit1 (/display2); owned-main-frame guard/fail-closed unknown-frame routing and extra-page closure yielded focusedGREEN1 exit0/0.521s. README updated. Full suite/targeted recheck still pending then. New BrowserSession had no tracked baseline CLI; existing10 preserved by suite, not Git-history tests.

L39 — Popup full54 exit0/13.726s, old10 preserved. Existing verifier target-rechecked popup+normal source only: one owned GET/page, persistent reads, cleanup; no blocker. New source hash3a90ffcd15dec9d0e747a34bb37f324611875dfa40bd3cc22707fa6adadae358. T3a ready to commit, T3b pending; native mode off/no publication.

L40 — T3a committed5f55f3e6bf720f0f74d578ac21371d9c353dbbc9,562add/16del; no push. App assembly next, no control CLI/HTTP/USB. Windows proof separate.

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

L84 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` ReviewedT5/T6unchanged; readonly46Qt-prefixmap exposedextras/versionmodelgaps. Pinnedhookscollectbroadroots; appCore/Gui/Widgets+raster, notproofDLLremovable. Noqualification.

L85 — 39033278476 EXE/COLLECTcompleted; exacterror `Portable build failed: Missing reviewed native notices: build/native-material/native.json; Windows qualification is pending`. Artifact12101312078/12164archivebytes. Scopechoicebeforebroaderchanges, no bypass.

L86 — Actualbroadreport39033278476 source00108ef UNQUALIFIED/native_qualification; packaged_smokepassed/136nativefiles. JSONSHA256aea9c2af402d2f011e58e4c3a416bb456f2ef847d0afca647b3ad75cd4ac50f8. NotWin11/Exit/legal/ZIP. T5brieflyblockedonscopechoice, resolvedL87; specs/userquotesretained.

L87 — Live owner selected `Minimal app-required runtime (recommended)` / `Remove only proven-unneeded plugin roots before dependency collection, preserve required DLLs, correct component-version provenance and reverify Windows.` (minimal_runtime), in answer to `Which runtime scope should I use to finish native attribution before producing the ZIP?`. S6only amendedwithverbatimscope; T5resumesin_progress/T6blocked. Firstboundedunit targets identifiedoptionalPDF/SVG/virtual-keyboardpluginROOTS viarepo-localQtGuihookbeforeclosure, notblindDLLdeletion; preservebase/Core/Widgets/Network/Mesa/CRT/platform/styles/untargetedplugins. Newinventory/smoke beforeadditionalcuts; provenanceversionmodel/evidence follows. Oldbroadbundlesmokepass doesnotprovefutureminimalcandidate. No main/PR/release/hardwareauthority.

L88 — MinimalQt stage1 SOURCE RED1/0.002→GREEN1/0.002; focused23 exit0/0.360s/full121 exit0/17.990s. RepoQtGuihookfiltersONLYfourfamily/namepluginroots beforeclosure; stocktraversal/validation/hiddenimports/datas/defaultotherhooks+descriptoroverride restoration retained.80protected+482SDKhook/Qt-sourceRECORDhashes unchanged; speconlyhookspath. No minimizedWindowsoutcomeclaimed. IndependentRisk5review/newnativeinventory+smoke pending; component-version/provenance nextunit andqualifiedZIP absent. T5in_progress/T6blocked.

L89 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` ReconciledT5in_progress/T6blocked: stage1SOURCE independent23 exit0/0.433s/no skips/no severe blockers;107workspace/index/status and99othertrackedfiles unchanged. Local121 stand. No minimizedWinprooftransferredfromoldbroadsmoke; version/provenance andqualifiedZIP remainpending. Recordstage1commit thenauthorizednewCI. Routine oldmaterial logs shortenedforfullmirror, specs/userquotes retained. Minimal-plugincommit `081476d42b1c28a9f6787421547ea571ee7095c3`.

L90 — Win39036811563/ad1283785e06b618a8a28a2e703c5be12614a3ab realEXE/COLLECT/source+packagedsmokePASSED; failureonlymissingnativequalification. Artifact12102935472 JSONbuild/ci-39036811563/unqualified-native-ew8cm1mp.json SHA256b4f5da8b7a75aeebfa9cea8fdc31087860a446e505241679bcd8d5c21372d159. Exactdelta:136→123native, Qt46→33; fourtargetplugins+nineQtDLLs(OpenGL/Pdf/Qml/QmlMeta/QmlModels/QmlWorkerScript/Quick/Svg/VirtualKeyboard)removed,noadded. Retain33inclCore/Gui/Network/Widgets/platform/style/otherimageformats/SSL/Mesa/CRT. Nextboundedunitmeasureper-filePEversions/safevendorlabels andexactinstalledRECORD-originhashmatches inUNQUALIFIEDdiagnostic only, beforecorrectingnativeversionmodel. Missingmetadata staysunknown; noqualificationsynthesized/noZIP. T5inprogress/T6blocked.

L91 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` ReviewedT5in_progress/T6blocked, no newtaskdone. NativeevidenceSOURCE RED3errors exit1/0.014→GREEN3 exit0/0.023; focused22/0.296/full125/18.152 all0. Independent22 exit0/0.351/noskips/severeblockers;109workspace/index/status+103othertracked unchanged. LazyPEbyteversions/RECORDhashorigins inUNQUALIFIEDfailureJSONonly; oldqualification/smoke/publisher ASTunchanged. SDK483hashes andCLIbasehelp/guard/invalid exactmatches. Sourcecommit `0e4b571dc5cb38e7963c19898ba5bf78e5f3cbdd`. ActualWinnewcollector unknown, nextCI; versionmodel/materialmappingstillfuture, noZIP.

L92 — RealWin39038363658/29f18f7 compiled/source/smokePASSED; failonlymissingnativequalification. JSONbuild/ci-39038363658/unqualified-native-vjway4kq.json SHA2561e5da4c10089186b8ea855bbe47d4082fbd43e8d406ea88d8a82bb7a641f4290/89273bytes.123facts:101PEmeasured/22absent,46RECORDowners/77unknown, noneunavailable. Qt6.12.0.0 vsPySideCRT14.44.35211.0 vsouterCRT14.51.36247.0; Mesa/bindingsPEabsent butowner6.12known. OuterOpenSSL3.5.5/3.5.9, CPython/APIsystemDLLs unknownRECORDowners. Needseparatepackage/PE/source-releaseversiondimensions; recordownerisNOTMesasourceversion orlicenseproof. Nextreadonlyboundedmapmodel/primarynative-materialsourcesbeforecorrection, no fabricatedmanifest/noZIP. T5inprogress/T6blocked.

L93 — ReadonlyprimarymapconfirmedQtforPythonpinnedwindows_desktop.py supplierpath pyside_qt_deps_684_64_2022.7z/cache forCRT+opengl*.dll, NOarchivehash/Mesasourcerevisionbinding. ExactMesaupstreamsourceversionunproven; notQt6.12inference. NextONEschema-correctionunit: explicitQtstackrelease vsmanualsupportedcomponent/sourceversion vsfreshPE/RECORDownerfacts; evidence/missingstatusneverapproval. Rejectlegacy/diagnosticformats, keepbinary/material/path/sourcechecks,33scopeunchanged/otherSDKfollowupsvisible. Genuineversion-proofmaterialrequired, noactualnative.jsoncreated. Rawvendorinputgapcannotbesolvedbysynthetictests; qualification/ZIPstillblocked. Authenticpinnedqtbase+qtimageformatsattributionleadsnotWindowsbuildfeatureproof.

L94 — User: `Que está pasando?? veo 7 intentos de ejecutar el workflow en github y los 7 fallados!`; then `bueno pues completa T5`. Acknowledged process fault: first4 source/packaging failures corrected, last3 real startup smokes passed then predictably failed missing genuine native inputs. NO additional workflow while inputs missing; never bypass gate for green. V2 model source130/full17.489s and focused27/0.381s passed, independent review still pending/uncommitted. Resume T5 closure: resolve actual inputs, assess whether Mesa is necessary for default raster app before any omission; then qualified candidate CI. T6 still blocked, no ZIP/no new completed task. Routine old evidence shortened; all user quotes/specs kept.

L95 — V2 independentSOURCE27 exit0/0.455s/no skips/severe blockers;110workspace/index/status+105othertracked unchanged; writer130/full17.489s stands. Mesa premise challenge: pinnedQt raster GDI/pixmap/backingstore/tray path doesnotrequestOpenGL, RHI disabledunlessforced/widgetrequires. OmitONLYoptionalcollect_extra_binaries opengl32sw root whiledelegatingbaseguard/Shiboken/ANGLE/ICU/CRT/defaultothers; no environment/app/Chromiumchanges, closuremayretainifindependentlyneeded. ActualMesa-freeWindowsnotyetproven. MicrosoftofficialDOCXterms beingdecoded; genuineQtfullmodule-notices/versioninputsnext, noCIuntilready.

L96 — DecodedofficialMSruntimeEULAs:2022SHAf1e3d56ceb2ad68aae0711b910375009e651ac5530fa0760f0dea6e81e54fae1/2026SHA08651651a7602fc7c0e2763de0fde1ff9f868df2780597cd1775ee9d6441c783 grantinstallation/usebutnotdistributionbythemselves. SeparateVSREDISTpermissionsconditionalonapplicablelicense; projectbasisnotestablished, notallredistributionforbidden. NeedONEownerproductchoice: externalofficialVC++x64prereq(noMicrosoftDLLconveyance) vsautocontainedZIPwithdocumentedapplicableentitlement. Noimplicitacceptance/rightsbypass. T5blockedownerdecision/T6blockedartifact, no newCI. V2sourcecommitb479c22 reviewed130+27; noqualifiedZIP.

L97 — Live owner selected `VC++ oficial como requisito externo — recomendado` / `El ZIP incluye Python, Qt y Chromium, pero no redistribuye las DLL de Microsoft. Si falta VC++ x64, el usuario lo instala desde Microsoft. Sin instalador de MarsDisplay.` (external_microsoft_runtime), to `Para cerrar T5, ¿qué condición de distribución elegís?`. S6 amendedonlywithverbatimplatformprereq. ExternalizeknownVC++runtime/Windows11OSUCRT/APIcontracts explicitlybeforedependencyclosure wherepinnedSDKpermits; notblanketDLLdeletion. KeepQt/Python/Chromium/Pillow/extensions. MesaoptionalrootomissionjustifiedL95. Requireofficialx64VC++versiontestedbybuild(current14.51+)withoutauto-install/download/appinstaller. T5resumesinprogress/T6blocked, no predictable-redCI.

L98 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` Reconciled no newlydone: T5inprogress/T6blocked. ExternalprofileSOURCE RED3 exit1/0.023→GREEN3 exit0/0.033; focused28 exit0/0.459/full134 exit0/17.905, old130 retained.101protected+486SDKrecordhashes unchanged; onlydocumentedCLIhelpepilogdelta. Microsoftroots/deps selectedbeforeclosure, optionalMesaqueryomitted, finalrejectnotpurge; immutableREADME staged. GenuineQtdata/provisioner+independentreview+actualnewWindows stillpending; noCI.

L99 — RepeateduserplanreviewrequestL98: reconciledT5inprogress/T6blocked, no newlydone. Externalprofileindependent28 exit0/0.471/noskips/severeblockers;113nondataworkspace/index/status+101protected unchanged. Commit6e9218ab46f6a92cee4e2f6f3245eb6a21462e69. DATAchild lackedbackgroundnetworktool/noedits; parentjob35performsprimarypinned-sourcecollection (NOT CI). Actualexternalnativeprofile/noticesprovisioner/qualifiedZIPstillpending. Routineownoldobservationsshortenedonly, userquotes/specsretained.

L100 — ParentprimaryretrievalcorrectedQtmetadataJSONviewonly(literaltabs) withoutchangingrawbytes. Job36exit0/32s:233records/204raw/663917bytes/85declaredlicenserefs;Qtbase78/PySide5/imageformats2attrs. RegistrySHA2563543f2d2017e9a05de1fec4a1b580876d45b6db890f8aebd7a3e39bd8124ad06. Gitblob+SHA256/nonempty/safe/case/sourcepins+original56checks passed; passiveinputsno meaningfulRED. DataavailabilityNOTqualification. Nextboundedreader+curated27Qtcomponentpolicy+stageprovisioner, sourceincludesrawinputs, preflightbeforecompiler. OnlythenrealWindowscandidate. No newCI/noZIP/T5inprogress/T6blocked.

L101 — Data commit dcc7ff6cd526bc7c9843bec151ba120745625965:233records/204raw. Initialgitdiffcheckexit2 onoriginalOpenSSLAUTHORS `Authors`/`=======`; raw-onlyconflict-marker-size32preservesunalteredbytes, recheck/commitexit0.14745upstream/generateddatalinesnotauthoredruntimecode. Slice boundaries: externalprofile6e9218(338changed), passivedatadcc7ff6; nextreviewableslicenativeprovisioner+tests/docs, feature-branch-chain/noPRauthority unchanged. Curated27Qtcomponentpolicy mustbindobservedSDKhashes/RECORDownerstoactualpinnedmodule/version-noticeinputs; notgeneratequalificationfromunknowns. NoCIuntilsources/policy/provisionerpreflightready.

L102 — ProvisionerSOURCE RED6exit1/0.089→focused44exit0/1.057/full141exit0/18.730; initialduplicatedeclarationoverstrictness correctedwithoutdroppinggenuineinput. Independent44exit0/1.106/noskips/severeblockers,323workspace/index/status+312protectedunchanged; policysemantics27Qt+6supp reviewedwithrawlicenses/tags. Windowscheckout core.autocrlf=true RED1policy504CRLF/hash986f152→LFattributeGREEN0/a93efb59. Policycommit97bf8a0ca5d06f61e1feb1d8b5f776bd5fbf4b6d; coherentreader/preflight/stageunitff55d90fb348649016b59f610a35d722b00aa868(651authoredincltests/docs,504generatedpolicyseparate). Nativev2gate/publisher unchanged; actualexternalprofile/qualification/ZIPunproved. CandidateCIunderL64nowhasgenuineinputs/no knownmissing-inputfailure; T5inprogress/T6blocked.

L103 — User repeated plan-review instructionL98. ReconciledT5DONEonlyafteractualevidence: nativeCI39049628794/source211645e success; artifact12107551102 downloadedZIP205549310bytes SHA256f304b389b02b214ee7f090e609e1035256046ddb420ffea50f248d612fffb8fb/sidecarmatch;1222members/1221filehashes/325sourcehashes verified,69native,27Qt+6supp, noMSDLL/Mesa. CheckerfirstfailedwrongassumedREADMEpaths; actualREADME.txt→notices/native/SOURCE-ACCESS.txt matchedbuilder, checker-onlycorrectionfullpass. No artifact/codechange. Publicartifactexpires2026-10-24T16:32:46Z; https://github.com/ghosthvj/MarsDisplay/actions/runs/39049628794/artifacts/12107551102 . Docsupdatedwithverifiedproof/prereq/limits. Docs-onlyclosingcommituses[skip ci]toavoidrebuildingunchangedartifact; exactbinarysource211645e retained. T6BLOCKEDownerWin11/LAN/Exit/metrics, notartifact; no hardware/main/PR/release. Ordinarydocsstructuralcheck, no meaningfulRED/fulltestrepeat.

L104 — Owner: `MarsDisplay.exe se ejecuta bien, se queda en la bandeja del sistema, pero al configurarle la URL de MARS y activarlo pues da error`. Screenshots retrying/sourceerror/0frames; personalendpointnotcommitted. Readonlyjob40HTTP200/open0.519/readmetadataerror0.595; Settingspreservesexisting/display. Job41rootCount0afteropen→immediateerror→boundedDOMwaitrootversion1/loading/liveTrue/portrait320x480,total0.616; delayedpublicreadloading succeeds. ProvenSPAbootstraprace,_metadatawraptruthydata:null; notendpointcontractabsence. ReopenonlyaffectedS5/T3; T5followupartifactpending(priorverifiedartifactevidenceretained), T6pendingrepair. Boundedabsence-onlywait+publicdelayed-rootRED, preserveexistinginvalid/duplicate/error/navigation/geometrybehavior; noTLS/sandbox/retrypolicychange orMARSmodification. Realfirstframe+newWindowsZIPstillunproved.

L105 — User: `The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.` ReconciledT3inprogress/T5pending/T6pending, no newlydone. SPAsourceRED1exit1/0.463→GREEN1exit0/0.599; browser13exit0/16.901/full143exit0/23.364(old141retained),318protected unchanged. Actualpublicjob42loading0.628→ready1.106/liveTrue/staleFalse,320x480/460800RGBbytes/3reads/ownedclose; noimages/URLstored. Sourceindependentreviewpending, newWindowsZIPunproved. Artifactversion0.1.1onlypyprojectvaluechanged/depsunchanged. Preservevalidation/navigation/retry/TLS/sandbox/allothercontracts.

L106 — User: `continúa`. Independentmvcnis29-1r-xeqhSOURCEPASS S5/S10/S15:13tests/15.006s/exit0/noskips/stdout0B/stderr2014B18lines.323workspacehashes/status/indexunchanged,317othertrackedbaselineidentical; no severeblocker. T3sourcefixdone143+independent13+actualLinuxframe; T5inprogressnew0.1.1nativeZIP, T6pendingownerWin11acceptance. NativeRDDglobaloffreadagain, noSTART/authority. Risk:item3(sharedmetadatareadiness/validationcontract); independentcheckcomplete. No skippedfunctionalchecks claimedpassed; Windowsnewartifactunproved.

L107 — Verifiedsourcefixcommit5d0de48b4f08c38a33c5027195e18841fe2c86d4(0.1.1) includesbrowser/tests/docs/version/taskstate; cleanfeaturetreeatpush. Job43push+boundnativeCIwatchlaunchedunderexistingfeaturebranch/7dayartifactgrant; no dispatchduplicate/main/PR/release/installer. Windowsresults/ZIPstillpending. Preparedread-only0.1.1checkerboundtosource5d0de48andnewfilename/version; preservesold0.1.0artifactchecker/evidence, validatesallinventory/native/sourcehashesandactualsourcebrowser/versionbytes. No productcode/packaginggatechangesduringCI.

L108 — Planreviewafterlocalwatcherincident: job43pushsucceeded5d0de48butplainpythonabsent,watchernotstartedexit127(notWindowsfailure). Localprobeconfirmed.venv/bin/python3.13.5; job44attachedONLYexisting5d0de48run/nootherpush/dispatch/rebuild. CIoutcome/artifactstillunproven. ReconciledT3done143+independent13+actualLinuxframe;T5inprogresswatch44;T6pendingcorrectedartifactthenownerWin11. No tasknewlymarkedcomplete.

L109 — Corrected0.1.1nativeCI39055573997/source5d0de48b4f08c38a33c5027195e18841fe2c86d4green;Windows143tests49.084s/OK,build/profile/smoke/provisioner/v2/source-stability/uploadpassed. Job45downloadartifact12109691322expires2026-10-24T17:54:50Z. Readonly011checkerexit0/1.9s:ZIP205550469bytes/SHA84769fa48f091323a4d7598fb12358d725c4a2cc6ef6a96fa7f504f75b7a4fc4/1222members/1221hashes/325sourcehashes/69native/27Qt+6supplemental/noMSDLL/Mesa; sourcebrowser/versionbytesmatch5d0de48. NoWindowscodeexecuted/extractedonLinux. Docsupdatedforverifieddelivery/checkedagainstverificationJSON; passiveprogressdocsneednoRED/fullrerun. T5doneinqualifieddeliveryscope;T6notcomplete.

L110 — Owner: `Estas son mis pruebas desde Windows`. Threeimages:running/ready/simulated-open(noUSB),liveyes/staleno,frames98and109. PID30960snapshot0%CPU/36.7MB/0MB/s/0Mbps; no aggregateNode/Chromium/sustainedclaim. ZIPversionnotvisible, donotattributeownercaptureto0.1.1withoutconfirmation; visiblebase/displayURLtextnotproofbothindependentlysaved/restarted. Noimages/personalendpointcopiedtorepo. T6blockedonlyonowneridentity/normalStopExit/ownedcleanup/LANrecovery/wholeprocessresources; noadditionalcodechange/newworkflow/main/PR/release/installer/hardware. Corrected0.1.1linkavailable; laterdocscommitdoesnotrebuild5d0de48binary.

L111 — Owner: `confirmo que he usado el ZIP 0.1.1`. Artifactidentityuncertaintyresolved:priorWindowsrunning/ready/liveyes/staleno/98→109framesbelongtodelivered0.1.1. Captureconfirmedbyowner;T6remainspartial/blockedonnormalStopExit/ownedcleanup/LANrecovery/sustainedaggregateNodeChromiumCPU/RAM. Snapshot36.7MB0%notaggregateproof. No code/build/CI/hardwarechange.

L112 — Owner: `He probado Start, Stop y Exit todo bien!`. FiveWindowsimageswithconfirmed0.1.1:stopped0→runningready1→19→stopped/simulatedclosed30→runningready36/liveyes/staleno. Counterpreservation/restartobserved;normalExitsuccessownerreported,noprocess-treeinstrumentationprovided. FunctionalStartStoprestartExitaccepted;T6stillblockedonlyonnetwork/LANrecoveryandwholeNode/Chromiumresources/ownedprocesscleanupobservation. No code/newbuild/CI/hardwarechange.

L113 — Owner: `despues del Stop el proceso de node desaparece`. Nineimages:validready8; invalid-domainretrying29→RecoveryExhausted/error29; validrestoredready36. Ethernetdisabled/liveNO/staleYES/runningready101→enabled/liveYES/staleNO/ready139. Acceptedobservedfailureexhaustion/restoredcapture/networkflags; noexactretrytiming/countorStop-during-retrycancellationclaim. NodeStopcleanupownerreported. Resourceinstant:NodePID42804=65.8MB/0%,26296=9.3MB/0%(ownershipunbound); Chromium4group74.9MB/0.2%,child14.9+10.3+34.6+15.1alreadyincluded. NeverdoublecountgrouporattributeallNode; olderEXE36.7MBnotsimultaneous. Noaggregate/10minaverage/CPUmodel/OS/ChromeExitcleanupinferredfromcrops. T6remainspartial, no code/build/CI.

L114 — Owner: `desaparecen los dos procesos de Node y el uso de RAM de MarsDisplay.exe oscila entre 33.6MB y 36MB`; correction: `te he pasado las capturas en el mensaje anterior!!`. Allfournewimagesalreadyread:EXEPID50796RAM34.0/34.1/35.1/36.4MB,CPU0.2/0/0.1/0.1%;oneviewready/liveyes/staleno/151frames. BothNodeStopclosureownerconfirmed; no need repeat images/identityquestion. EarlierNode75.1MB+Chrome74.9MB+EXE33.6–36.4 yields preliminary183.6–186.4MB(~185),distincttimesNOTsimultaneousaggregate/average/max/precisephysicalRAM. Remainingprooflimitationsretained, no fullT6done/no code/build/CI.

L115 — Owner: `con el paso del tiempo se ve que aumenta un poco más el uso de RAM de MarsDisplay.exe`. Newimages194557/194608:samePID50796RAM42.7MB/2324frames then42.6MB/2344,CPU0/0.2%,runningready/liveyes/staleno. Comparedwithprior34–36.4MB,growthobserved(~6–9MB),notproofleak/plateau. T6inprogressforboundedread-onlySDK/object-lifetimeexploration; no sourcefix/newWindowsrequests/rebuild/architecturechange. Simulatedoutputretainslatestonly; inspectlayoutwaitresultownershipasahypothesis,notconfirmedcause.

L116 — Planreviewrequested; no newtaskdone. ReadonlySDKmap+ONEpublicfixtureprobeexit0/1.8s:OPENhandles0→10reads10impl+10publicwrappers→20/20→30/30,ownedclose0,afterfixture0. All30exactRGB320x480readyframes;oneowned/displayrequest,raw1=owned1+foreign0. Per-framehandleleakconfirmed:readinesswaitreturnsbooleanJSHandleignored/strongSDKregistries; metadatahandlesdisposed. NotproofofallWindowsMBcause/postfixRSS. Explorerneverstarted(workspaceguard:sessionnonGitparent/nestedindependentrepo); Gitprobeexit128confirmedincident, inlineSDKreads/probe,no consentbypass/agentretry. Proposedfixdisposeunusedsettledhandle; no source/test/SDKwrites,newZIP/CI/commit. T3reopenedblockedonimplementationdecisionafterreadonlydiagnosis,T6pendingT3,T5existing0.1.1deliverydone(notfuture0.1.2). Preservefonts/layout/geometry/navigation/timeout/retry/security.


L117 — User: `Si, aplica la correccion necesaria pues por lo que se ve el uso de RAM sigue aumentando '/my-projects/pantalla/.herdr-web-ui/paste-20261017-200819-4de72b1f.png'`. Image consumed privately: PID50796,45.9MB,0.1%CPU,3671frames,ready/live/nonstale. Authorized bounded handle-disposal fix + regression + corrected0.1.2ZIP. T3inprogress,T5pendingnewdelivery,T6pending. Risk: item 3 (shared BrowserSession.read layout-validation/capture path); independent verification required. No TLS/sandbox/timeout/retry/server/hardware/profile changes.

L118 — Correction: one added settled_handle.dispose() after unchanged real layoutwait; no productionGC/restart/polling change. New publicSDK weakref regression20captures RED1exit1/1.081s(20retained)→GREEN1exit0/1.175s(0retained). Focused14/17.192s and full144/22.596s exit0/no skips; expected offscreenQt warnings retained. Differential base dc977dc isolatedcopy: ready20/landscape/loading/stale/invalid identical publicstdout2724B/stderr0/exit0; six app/buildCLI invocations exactsameexit/stdout/stderr;317 protectedtrackedfilesbyteidentical;TOMLversiononly0.1.1→0.1.2. README/packagingnotes distinguish oldartifact frompending0.1.2 and reconcilebothNodeclosure/roughsnapshotlimits. AssessnativeRiskmedium/escalateditem3→independentverifierrequired/reviewDuefalse; userreviewmodeoffunchanged, facadeonnotauthority. T3stillinprogresspendingindependentverification,T5pendingbuild,T6pendingownerproof.

L119 — Independentmvcu44lb-1s-b6hnPASS:S5sourcecleanup/S6version-onlypreparation;isolated14/16.008sexit0nostdout,stderr2181B19lines,noskips. Weakobserverpass-through/existingcapturecontract/disposalbeforelatererrorbranchesconfirmed;allotherBrowserSessionmethodsASTidentical.323workspacehashes/status/indexunchanged/317othertrackedbaselinefilesidentical. No blockers/advisories. T3doneafterobservedchecks;T5inprogress0.1.2nativebuild/delivery,T6pendingcorrectedownerbenchmarks/processcleanup/retry-cancelproof. NoWindowsRAMboundclaim. Sourceunitcommitpendingbelow;reviewoffunchanged.

L120 — Sourceworkunit `93b222b77ac07141d561e8735ef6bbb037747315` committedonfeaturebranch(6files/100insertions16deletions). Parentpostverifyspotchecknewregression1/1.161sexit0;diffcheckpassed. Job47launchedauthorizedsinglepush+registration+watch(gh--exit-status),nocustomdispatch/rebuild. 0.1.2artifactcheckerpreparedunderignoredbuild/boundtosource93b222b;noartifactdownload/verificationyet. LocalpassivenotesafterthiscommitarenotpartofCIcandidate. T6nowdependsT5portablebeforecorrectedWindowsresourceobservations; existingfunctionalproofretained.

L121 — Job47exit0after4m9s:source93b222bpushandCI39065994952passed,portablejob1174936749923m55s. Windows144tests/50.226sexit0;nativebuild,externalprofile,isolatedpackagedsmoke,genuinematerialqualification/source-stability/uploadpassed. Unqualified-onlyuploadcorrectlyskippedonsuccess. Job48downloadmetadata+artifactactive;nohash/contentverificationyet. Planreview:T5remainsinprogressuntilactualZIPverification,T6pendingT5andownerresource/cleanup/retryStopproof;T3sourcecompletionunchanged. No new source tests/build/reviewrun.

L122 — Job48downloadexit0/46s;artifact12112754920expires2026-10-24T20:20:01Z. Exactapplication`MarsDisplay-0.1.2-Windows-x64.zip`205551083bytes,SHA256`657b71f30f1b73e2340de152cf1719b35a1a6a6739b7e819c075e0959387737e`. Checker012exit0/1.9s:1222members/1221filehashes/325sourcehashes/69native/27Qt+6supplemental/noMicrosoftDLLs/noMesa,source93b222b/version/browser/newregressionbytesmatch. NoWindowscodeextracted/executedonLinux. Wrapper204849246B/digestd356a6a1...isnotapplicationZIP. README/packagingupdatedtoverified0.1.2download/SHA/expiry;sourceunitunchanged. T5doneafteractualproof,T6blockedonownerpostfixRAM/remainingcleanup/retryStop;existing0.1.1functionalproofretained. Docs-onlycommit/pushtoexistingfeaturebranchwith[skipci]next;doesnotrebuildbinary. No main/PR/release/installer/hardwareorflatRAMclaim.
