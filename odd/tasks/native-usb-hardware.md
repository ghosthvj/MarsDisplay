# P6 owner-run hardware qualification
Qualify the P5 Windows artifact from `56ea091cfae996101e5106cf1acc64898bd52b59`; branch from P5 closure `5f1e1137432f7b6aec592f6af9dad9a43dbf4d91`.
Physical execution belongs to the owner. Record observations without converting host completion or elapsed counter rates into panel acknowledgements or FPS.

## Specs

### S1 — Authorization and scope
> continuamos con P6

Owner readiness choice:
> Listo para probar
> Tengo la pantalla conectada y puedo ejecutar el paquete y compartir resultados.

Accepted P6 scope comes from docs/usb-integration-plan.md, P6 section. Keep P0–P5 artifacts intact and Simulation default. No installer/service/autostart, firmware/reset/brightness/power commands, automatic resend, arbitrary transport fallback, landscape implementation, release or main merge. No local host USB execution by the agent. The prior exact RDD target sha256:975e7d7af3b7fbd5b3206d58109172ddfb3abade61d1c4e9a675e66e9b7be4d6 was declined; that does not grant a decline for different candidates.

### S2 — Physical operation and lifetime
> Owner-run Windows tests cover continuous
> portrait, unplug/replug, COM reassignment, duplicate devices, Stop during transfer/
> retry, restart, Exit, process/resource lifetime and measured latency/capacity.
> Keep the default capture cadence target of one/second with synchronous backpressure and no
> extra queue; do not claim panel FPS from a timer or baud rate.

Native P5 has zero automatic retries; do not introduce retry solely to test it. Ask for reproducible owner evidence, not private endpoint URLs or full user settings. Unavailable physical scenarios stay unqualified, never silently passed.

### S3 — Delivery and separate landscape gate
> Qualify the packaged native helper, clean checkout build, dependency/license
> notices, artifact/source hashes and real Windows delivery independently. Only then
> consider **landscape as a separate gate**: no silent rotation/cropping of unsupported
> native landscape, and no regression to already-supported simulated landscape.

Reuse exact P5 software evidence from docs/usb-runtime.md and its ledger; new hardware observations do not rewrite the qualified ZIP. Artifact12367770679/run39645553766; innerZIP205687478bytes SHA25624d8ce2fff5d9455a08c8fac2251346f0fc9a010653abe13caa0106df910171d. Parent Linux/CI evidence does not prove interactive Windows tray or physical output.

### S4 — Acceptance and rollback
> **Accept:** reproducible owner evidence and measured production deadline budget;
> continuous/reconnect/performance claims limited to observed conditions.
> **Rollback:** select Simulation, preserve configuration and close only owned
> resources. No firmware reset, protocol roulette or automatic transport fallback.

Do not tune production deadlines from a single elapsed counter measurement. Retain source/output/preview distinctions and real cleanup uncertainty. Changes justified by physical findings require reproduction, scoped tests, reviewable units and applicable verification; do not invent them before evidence.

## Tasks

- T0 [S1–S4] route: parent inline; status: in_progress; commit: pending — Pin artifact, reconcile historical documentation and prepare bounded initial owner procedure. Risk: none (documentation).
- T1 [S1–S4] route: owner physical execution + parent evidence review; status: pending; commit: pending — Establish initial portrait continuous output, accepted-frame correspondence and acknowledged Stop from qualified Windows app.
- T2 [S2,S4] route: owner physical execution + parent evidence review; status: pending; commit: pending — Exercise unplug/replug, explicit restart, identity/COM/duplicate admission, in-flight Stop and Exit/resource lifetime without forced unrelated cleanup.
- T3 [S2–S4] route: parent analysis + owner measurement; status: pending; commit: pending — Measure latency/capacity, decide justified production budgets, verify any resulting bounded changes and close only observed hardware conditions. Landscape remains a separate gate.

## Log

L1 — Original request verbatim: `continuamos con P6`.
L2 — Owner selected readiness verbatim `Listo para probar` with description `Tengo la pantalla conectada y puedo ejecutar el paquete y compartir resultados.` No physical P6 execution observed yet.
L3 — Clean P5 closure5f1e113 branched to feat/native-usb-hardware. P5 actual software qualification56ea091/run39645553766/253Windowszero-skips and independent/source/material proof remain valid. Historical plan/screen guide still say P5 unauthorized; reconcile current status without rewriting historical evidence or ZIP. Initial owner procedure is a bounded60second observation, not a production acceptance threshold or panelFPS benchmark.
