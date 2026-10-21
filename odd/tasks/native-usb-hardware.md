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

Native P5 has zero automatic retries; do not introduce retry solely to test it. Ask for reproducible owner evidence, not private endpoint URLs or full user settings. Unavailable physical scenarios stay unqualified, never silently passed. Owner subsequently accepted continuing T3 with the stated single-screen/COM5 scope: physical COM reassignment and duplicate-unit rejection are excluded from current physical acceptance and explicitly remain unverified; software coverage is separate.

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

- T0 [S1–S4] route: parent inline; status: done; commit: `2954357aa2511566eedfdd45e47dade1edabbbe6` — Pin artifact, reconcile historical documentation and prepare bounded initial owner procedure. Risk: none (documentation).
- T1 [S1–S4] route: owner physical execution + parent evidence review; status: done; commit: `ee35544` (observations; confirmation in subsequent ledger commit) — Established initial portrait continuous output, accepted-frame correspondence and acknowledged Stop from qualified Windows app.
- T2 [S2,S4] route: owner physical execution + parent evidence review; status: done; commit: `792bff7` through `4d70a05` (evidence) — Unplug/replug, explicit restart, in-flight Stop, Exit/cold startup and physical port relocation observed. Owner accepted single-screen/COM5 scope; physical COM reassignment and duplicates remain unverified, not passed.
- T3 [S2–S4] route: parent analysis + owner measurement; status: blocked; commit: pending — Measure latency/capacity, decide justified production budgets, verify any resulting bounded changes and close only observed hardware conditions. Landscape remains a separate gate.

## Log

L1 — Original request verbatim: `continuamos con P6`.
L2 — Owner selected readiness verbatim `Listo para probar` with description `Tengo la pantalla conectada y puedo ejecutar el paquete y compartir resultados.` No physical P6 execution observed yet.
L3 — Clean P5 closure5f1e113 branched to feat/native-usb-hardware. P5 actual software qualification56ea091/run39645553766/253Windowszero-skips and independent/source/material proof remain valid. Historical plan/screen guide still say P5 unauthorized; reconcile current status without rewriting historical evidence or ZIP. Initial owner procedure is a bounded60second observation, not a production acceptance threshold or panelFPS benchmark.

L4 — T0complete commit2954357: pinned ownerprocedure docs/usb-hardware-qualification.md, historicalplan/diagnosticstatus explicitly superseded,30localdoclinks/diffcheckPASS. Documentation only: no meaningfulRED/runtimechange. ChainedP6delivery boundary starts at5f1e113; this145+/1-docslice is not accumulatedP0–P5featurehistory. T1blocked awaiting firstphysical portrait/Stop evidence from owner; T2/T3orderedpending, no physicalexecution/resultsclaimed. Procedure60s+10s is a bounded firstobservation, not productionbudget or panelFPS. No need to repeat P5 software tests for passive instructions.

L5 — Owner supplied three private local images (2026-10-21 captures); parent inspected all. Evidence: preview320×480RGB888 frame67/running/sourceReady/liveyes/staleno; app native-host-complete/running with78hostacceptedframes and stopped-only configuration disabled; physical panel photo shows legible upright dashboard content. Preview and physicalphoto show different dashboardcards, so exactframe correspondence/rotation needs owner confirmation; do not label mismatch a defect without reproduction. No timestamp-derivedduration/FPS, packagehashconfirmation, acknowledgedStop/countstability or resourceclosure evidenced. T1remainsblocked on ownerobservations. Private endpoint/host/IP values and originalphotos are not copied into tracked docs or distributable artifacts. Next: confirm normalcardrotation and packagehash, obtainStopackelapsed and countafter10s; no unplug/replug yet.

L6 — Owner report verbatim:
> Las tarjetas si rotan, al cambiar de una a otra se nota como un barrido desde arriba hacia abajo como dibujando la nueva tarjeta.
> Se ven las actualizaciones de las tarjetas como cada 1-2 segundos.
> Al pulsar Stop no se demora en pasar a stopped y el contador de frames no aumenta aqui lo puedes ver: '/my-projects/pantalla/MarsDisplay/.herdr-web-ui/paste-20261021-180502-ff7dc881.png'
> No verifiqué el hash, descargué el ZIP que me dijiste y lo ejecuté

L7 — Inspected supplied Stop screenshot: lifecycle/source stopped, native-closed, hostacceptedcount152, configuration reenabled; red diagnostic exactly `Native delivery is uncertain; the previous host-accepted frame is retained. No resend.` Owner confirms no observed delay and stablecount; exact measuredStopduration/10second observation interval not supplied. Cardrotation confirmed, resolving earlier different-card ambiguity, not establishing simultaneouspixelmatch. Visible top-to-bottom redraw and approximate1–2second updates are ownerobservations, not measuredFPS/latencycapacity or proven bufferingcause. Delivery uncertainty differs from retained resourceownership: stopped/nativeclosed can coexist with unconfirmed lastframe after cancellation. Need owner timing of warning (beforeStop vs onlyafter) before classifying physical failure. Local lifecycle.py329–338 confirms typed deliveryuncertainty diagnostic, not evidence of its actual trigger here. Packagehashnotverified byowner; T1blocked on checksum confirmation and warning chronology/stabilitywindow. Do not ask to repeat Start, resend, unplug or changeprotocol yet. Originalimages remain private, no endpoint/IP copied.

L8 — Owner report verbatim:
> El aviso apareció al pulsar en Stop.
> El contador quedó sin avanzar durante todo el tiempo.
> Este es el resultado de la verificacion: '/my-projects/pantalla/MarsDisplay/.herdr-web-ui/paste-20261021-181051-875e9cfe.png'

L9 — Parent inspected SHA256 screenshot: uppercase24D8CE2FFF5D9455A08C8FAC2251346F0FC9A010653ABE13CAA0106DF910171D equals qualified innerZIP hash exactly. T1done for initialowner-observation scope: rotatingportrait physicallyvisible/~1–2sreportedupdates/top-downredraw; stopped/nativeclosed/count152 stablethroughownerobservation; warning beganonStop, compatiblewithinflightcancellation, not proof of a priorrunningerror or panelACK. No measuredStoplatency/FPS/productionbudget/sustainedstress claim. T2blocked awaiting next controlleddisconnect: explicitStart once, observe advancingcount, unplugscreenUSB once, collectstate/message/count+elapsed over atmost30s; no automaticreconnect/restart/forcedcleanup. Thirtyseconds is a bounded observation window, not deadline tuning. If Start itself errors, stopbeforeunplug. T3pending on remainingphysicalscenarios and measurement.

L10 — Owner report verbatim:
> al desconectar el USB se ve así: '/my-projects/pantalla/MarsDisplay/.herdr-web-ui/paste-20261021-181307-c19e7e18.png'
> el error se mostró al momento de desconectar la pantalla, sin demora.

L11 — Parent inspected image: lifecycleerror/sourceStopped/nativeClosed/count291; exactdeliveryuncertain/noresenddiagnostic persists; Startavailable, Save/Refreshdisabled, footer advisestrayStoptoedit. Owner reports immediateerroronunplug; qualitativeobservation only, not measuredlatency. Compatiblewithknownclosedoutputanduncertainlastdelivery; no evidenceofcleanupuncertainty, but actualprocess/resourceexit not yet physicallyverified. T2partial: disconnectederrorseen; stablecount/noautoreconnect/resume stillneed observation. Next reconnectsameunit/sameUSBport, wait10swithoutcontrols and verifycount291/noautomaticrunning; thenoneexplicitStart onlyifstable, verifycountadvances/physicalupdates andcapture. If spontaneousrestart/newerror occurs, stopbeforefurtheractions; no repeatretry/protocolchange. COMreassignment/duplicate/Exitchecks remain pending.

L12 — Owner report verbatim:
> Pantalla reconectada, no vuelve solo a running ni aumentan los frames, se mantienen en 291.
> AL pulsar Start Capture los frames aumentan y se ve correctamente ne la pantalla: '/my-projects/pantalla/MarsDisplay/.herdr-web-ui/paste-20261021-181659-3bca608a.png'

L13 — Inspected screenshot: running/sourceReady/nativeHostComplete/count304/liveyes/staleno, no priorredwarning visible; owner reports correctphysicaloutput. Sameportreconnect kept291/noautoresume, oneexplicitStart restoredcapture. Approve this bounded reconnect/manualrestart scenario, not allT2. Nextownercheck: whilecapturing observe ownMarsDisplay.exe processes in TaskManagerDetails, invoke trayExit (notwindowX), confirmapp/helperprocessesfinish and elapsedtime; noforcekill. Only after confirmedexit, relaunchsameEXE once and confirmstopped/nocaptureuntilStart/settingspreserved. Screenretaininglastimage is not ongoingUSBproof. COMreassignment/duplicatecases and quantitativebudgets remain pending; no hardwarecapability inferred from reconnection alone.

L14 — Owner supplied three private screenshots (181846,182035,182044). Parent observed firstTaskManagergroupMarsDisplay.exe(2) PIDs11208/25580; laterapp running/sourceReady/nativeHostComplete/count11, savednativeidentitypresent but draftselectorplaceholder; lastTaskManagergroupPIDs8252/17100. DifferentPIDs and lowcount are compatiblewithfreshsession, not proof that oldprocessesexited or startupremainedstopped. Neitherimage shows absenceofoldPIDs, initialstoppedstate or measuredExitduration. Do not infer autoStartbug from runningcapturewithout chronology; draftplaceholder alone doesnotinvalidate savedStartcontext. T2stillblocked: owner must confirm oldprocessesdisappearedbeforelaunch/approxelapsed and whether Startwasmanuallypressedafterinitialstopped. No furtherphysicaltestrequesteduntilthisambiguityresolved. Privateendpointnotcopied.

L15 — Owner report verbatim:
> al pulsar Exit los procesos se cerraron completamente de forma instantanea. al iniciar la aplicacion esta se mantuvo en Stopped hasta que yo manualmente le dia Start Capture

L16 — Accept bounded Exit/coldrelaunch scenario from ownerconfirmation plus priorPID/screenshots: previousapp/helperprocesses disappearedbeforefreshlaunch, perceivedinstantaneousExit(noquantifiedlatency), newlaunchstayedStoppeduntilmanualStart. No forcedcleanup or spontaneousresume reported; savednativeconfiguration preserved in priorcapture. T2remaining scope is physicalCOMreassignment/duplicateidentity availability, not repeatingpassedExit/reconnect. Ask whether anotherUSBport andsecondmatchingunit are available; changingports doesnotguaranteeCOMchange and no manualdriver/COM reassignment authorizedhere. No availableduplicate device must remain an explicituntestedboundary, not fakepass. T3productionlatency/capacitybudgetstillpending.

L17 — Owner report verbatim:
> si tengo otro puerto USB disponible, pero no tengo ninguna otra pantalla

L18 — Duplicate-unit physical test unavailable: owner has one screen. Keep duplicate rejection software evidence separate; physicalduplicatecoverage remainsunverified, not passed or silentlyremoved. AnotherUSBport available permits controlledphysicalportmove, but only a measured oldCOM/newCOMdifference proves COMreassignment. Next whileconnected recordcurrentCOMinDeviceManager, Stopandwaitack, movethesameunittootherUSBport, recordnewCOM, verify noautoresume, thenStartoncewithoutchangingsavedidentity/configuration. Observecount/physicalportrait; onerrorstopbeforeanyretry. Do not manuallyassignCOMnumbers/changeWindowsdrivers or attachunrelatedserialdevices. T2blocked on portmoveevidence; T3pending.

L19 — Owner report verbatim:
> puerto inicial: COM5
> puerto al conectar a otro puerto fisico: COM5
> no cambio el nombre del puerto.
> Al iniciar nuevamente la captura funcionó correctamente y se muestra bien en la pantalla sin hacer ningun cambio en la configuracion
> '/my-projects/pantalla/MarsDisplay/.herdr-web-ui/paste-20261021-182937-f50e2ac6.png'

L20 — Inspected screenshotrunning/sourceReady/nativeHostComplete/count29/liveyes/staleno/nativeidentitypreserved/noerror. PhysicalportmoveCOM5→COM5 and manualStartwithoutconfigedit succeeded byownerreport. This passesportrelocationonly, not COMreassignment/oldCOMforeignoccupant orduplicateunitphysicalproof. T2remainspartial: availableportrait/Stop/disconnect/reconnect/Exit/coldstart/portrelocationscenarios observed; nosecondunit and stableCOM prevent remainingphysicalcoverage undercurrentprocedure. Needsownerdecision: proceedT3measurements with explicitlylimited singleunit/COM5qualification and leave missingphysicalscenariosunverified, or pauseuntilrequiredhardware/controlledCOMtestconditions available. No manualCOMreassignment/driverchange or blanketP6acceptance inferred. PendingT3metrics/budget not yet observed; do not tune from1–2svisualestimate.

L21 — Owner report verbatim:
> cambié a varios puertos USB y siempre mantuvo COM5 como nombre del puerto.
> Seguimos con T3

L22 — Owner accepted prior offered limitedscope continuation. T2doneonlyforobserved single-screen/COM5conditions; physicalCOMreassignment/duplicates explicitlyunverified (S2updated), not fulloriginalhardwarecoverage. T3blocked awaiting initial5minute stability sample: no restart/configedit/disconnect duringwindow; C0/C1hostcounts withactualelapsed monotonicstopwatch, screenshots and observedfreeze/redraw/error behavior; StopafterC1andrecordfinalack/countstability separately. Five minutes is a firstmeasurementwindow, not a productionsoak requirement. Compute(C1−C0)/elapsedonlyashostacceptedrate, not panelFPS/maxcapacity/per-operationUSBtiming. Existingframe20s/write3s/drain15s caps remainunchanged/provisional; no productionbudgetclaim fromthissample. Iferrorappearsstopandreportwithoutautomaticretry.

L23 — Owner supplied seven timed screenshots (184102,184153,184311,184412,184514,184610,184624) and reported verbatim:
> Aqui tienes los tiempos cronometrados. Durante la prueba no se vio ningun congelamineto en la pantalla ni errores.
> El barrido es más evidente en la zona del grafico de la tarjeta. Tienes un video en my-projects/pantalla/test_display.mp4

L24 — Parent inspected allsevenimages. Running/sourceReady/nativeHostComplete/liveyes/staleno samples stopwatchseconds→hostcount:3.01→1;61.86→24;141.24→56;203.19→81;267.06→107;322.79→130. Calculated129acceptedframes/319.78s=0.403402frames/s (~2.478915s per acceptedframe). Perintervalrates0.3908,0.4031,0.4036,0.4071,0.4127frames/s. Lastimage stopwatch332.11paused shows stopped/sourceStopped/nativeClosed/count134; no exactStoppress timestamp or laterstablecountsample supplied, so neither9.32sStoplatency nor postStopwrites may be inferred. Owner reportsnofreezes/errors and graph-area sweep visible. No peroperationUSB/source latency/panelFPS/maxcapacity/proddeadline inferred. ffprobe/ffmpeg andPythonav/cv2/imageio absent; existingPlaywrightavailable. Job8 attempts one localvideo decode/sample with existingChromium, noinstall/upload/hardware; resultpending. Originalvideoexplicitly supplied at /my-projects/pantalla/test_display.mp4; privateframes confined ignored build/p6-state/video, not tracked.

L25 — Job8 shell exited0 but produced INVALIDvisualproof: metadata duration22.399646s/videoWidth0/videoHeight0/errornull; allsix extractedJPEGfiles0bytes. Parent readback had noimage; explicit6filevalidation exit1 confirms emptyframes. Do not treat shellsuccess asdecodedvideo or claim visualinspection. No automatic decoder retry/install or externalupload. T3blocked on ownerdecision to enable an actual localdecoder (e.g.FFmpeg) for suppliedvideo; quantitativeperoperationlatency/budgetalso remainsunproven regardlessofvideo. Timedscreenshotrate and ownernofreeze/errorreport remainvalid. Existingcaps unchanged; no fullP6closure.

L26 — Owner authorization verbatim: `si instala un decodificador local para ver el video`. Job9 creates isolated build/p6-video-tools venv and installs pinnedimageio-ffmpeg0.6.0 bundledFFmpeg for local analysis. No system/globalinstallation, projectdependency/lock change, privatevideoupload or sourcebehaviorchange. Currentuntracked.herdr-web-ui is ownerprivateevidence; preserveuntracked/excludecommits. T3decoderworkactive; installationresultnotyetobserved.

L27 — Decoderinstallationjob9exit0: imageio-ffmpeg0.6.0/FFmpeg7.0.2-static isolated. Job10exit0 decoded22nonempty360×640samples (~1/s) from22.4sownervideo; parent inspectedcontactsheet. Job11exit0 decoded20nonemptysamples at~0.1sspacing over9–11s; parent inspectedcontactsheet. Visibleuppercardchangesprecedelowerchartreplacement; intermediatechartcontainsold/newtraces, then completes. Confirms progressive redraw in the sampled transition, not cause or fullvideo/audio review. Sourceanimation/serial/panel/camera contributions not distinguished. Source read lifecycle.py369–391 shows synchronoussource.read→send→hostcount and max(0,1−elapsed)cadencewait: nominal1s target is not guaranteed or an extra1saftereveryframe. No perstage latency measured, so no productionbudget/fix inferred. T3blocked on decision for boundednumeric-only stage instrumentation/ownermeasurement (noURL/images/history), or explicitdeferral of productionbudget/optimization. No applicationcodechange. Planreview:T0/T1done,T2doneonlyacceptedlimitedscope,T3notdone; video blocker resolved, timing proof missing.
