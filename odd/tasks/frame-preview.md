# MarsDisplay output frame preview
Add a modeless Qt popup for the exact latest frame accepted by simulated output.
Baseline: `3a6c9e383cdf521340ad8a9755218f11e85f2416`; branch `feat/simulated-companion`; existing Windows seven-day test-artifact scope only.

## Specs

### S1 — Preview button and real output frame
> podríamos añadir esto de la vista previa??, un boton que muestre un popup con la captura real que se enviará a la salida, por ahora simulada pero despues será a la pantalla USB

Add a Preview button and one reusable modeless popup. Show the exact immutable RGB888 frame from the existing coordinator snapshot, published only after output.send succeeds, not another capture or a browser view. Preserve portrait320×480/landscape480×320 pixels and orientation; no history, disk export or new dependencies. A preview is not proof of future physical USB reception; hardware remains out of scope.

### S2 — Current proposal accepted by the request
> Lo más útil sería agregar **“Vista previa”**: mostrar ese último frame de 320×480 o 480×320 dentro de MarsDisplay, sin abrir otro Chromium ni guardar archivos. Así podrías comprobar exactamente qué enviaría a la futura pantalla.

Read the existing public snapshot on the UI timer, updating only while visible and converting pixels only for a different frame. Explain the no-frame case without implicit Start; identify latest/retained frame and current lifecycle/live/stale information so a retained picture is not claimed fresh. Stop preserves the last accepted image. Close/Escape hides only the popup, reopening uses current frame, hidden popup releases its rendered image. Honor session theme and existing guarded Start/Stop/Save/Exit; Exit hides/disables preview without bypassing resource cleanup. No lifecycle/browser/retry/settings-format/output/protocol changes.

### S3 — Existing delivery and privacy boundaries
> si, te autorizo, NO me pidas mas autorizaciones simples como estas, no pares a no ser que sea algo importante!

Existing feature-branch push/Windows CI/seven-day artifact authorization continues. Prepare0.1.4 with unchanged dependency/runtime/qualification/workflow. Local test-first, focused/full suite, public-behavior differential, synthetic light/dark/empty/portrait/landscape/small-window previews; one independent Risk3 verification. Run native build only after source proof, then download/verify exact source/version/hashes/notices/profile and document delivery. Owner0.1.3UIconfirmation remains historical; new preview owner Windows11 visual/DPI acceptance is separate. Do not publish private endpoints/images/frame bytes. No main/PR/release/installer/service/autostart/USB.

## Tasks

- P1 [S1,S2] route: inline; status: done; commit: pending cohesive P1/P2 unit — Qt-only preview widget with exact RGB888 ownership, geometry, empty/retained/status/theme and bounded visibility behavior; tests with behavior. Risk: item 3 (shared UI presentation).
- P2 [S1,S2] route: inline after P1; status: done; commit: pending cohesive P1/P2 unit — Bind Preview button to existing snapshot/timer and exit guards, preserve actions/settings/browser/output boundaries; integration tests and usage docs, version0.1.4. Risk: item 3 (shared tray refresh/actions). P1/P2 form one cohesive <400-line source work unit if practical.
- P3 [S1–S3] route: parent checks plus independent Risk3 verifier/native delivery; status: in_progress; commit: pending — Final source/visual/differential proof, native Windows build, downloaded artifact hashes/source/profile, delivery notes. No review while user switch off; no claim owner preview/DPI approval.

## Log

L1 — Owner, verbatim: `podríamos añadir esto de la vista previa??, un boton que muestre un popup con la captura real que se enviará a la salida, por ahora simulada pero despues será a la pantalla USB`.
L2 — Existing code explored before writes: Coordinator publishes latest_frame/frames_sent only after successful synchronous output.send; immutable RGBFrame is packed RGB888320×480/480×320. Qt timer already reads a coherent snapshot every50ms; observer can reuse it without backend edits. Current3a6c9e3workingtree clean;0.1.3ownerUIfeedback documented separately. One dependent feature, parentinline; external native-delivery wait makes resumability tracking necessary. Preview means latest accepted output frame, not future USB acknowledgement. All test/visual data synthetic; no private capture performed.

L3 — Test-first RED7tests/0.260s exit1 (missingpopupmodule/button). P1GREEN2widgettests/0.048sexit0:allRGBbytes/roworientationbothgeometries,stablepixmapcacheonidenticalframe,empty/retained/source/livenesslabels,noUSBreceiptclaim. QImage owns copied pixels,close/hide clears pixmap/reference. Official Qt docs confirm RGB888bytesPerLine/QLabel+QScrollArea; no OpenCV/thread/example dependencies adopted. P1doneforwidgetchecks;P2integrationnext,onecohesivesourcecommitafterall7pass. Onlynewpreviewmodule/theme-selector/tests/ledgerwritten;backendunchanged.

L4 — P2GREEN all7preview+17existingtray=24tests/2.497s exit0. Pixelbytesmatchacceptedframes,updatingportrait→landscape;closedpopupreleasespixmap;reopening/theme/Stopretention work. Loading/rejectedsendkeepoldacceptedframe/count,previewdoesnotreadsource,settingsbytesunchanged;Exitimmediatelyhides/disablespreviewandstillwaitscleanup. Originaltraycasespasswithoutchanges. P1/P2scopedimplementationdone;P3full/differential/syntheticvisual/independent/nativeproofpending. Version-only0.1.3→0.1.4;READMEsourcepreviewsectionandbundledREADME.txtinstructionsupdatedwithoutclaiming0.1.4artifactexists.

L5 — Full159tests/24.963s exit0/no skips on completed source. Differential against3a6c9e3 in fresh in-project mktemp copy:6CLI exit/stdout/stderr identical;original17traytests exactJSONandrawstderr2447B identical;320otherbaselinefiles byte-identical,TOMLversion-only. Synthetic100%/150%light/dark empty/portrait/landscape/retained plus smallpopup/status generated and read:imagesunscaled,scrollwhenviewportsmaller,metadata/note/Close/Saveaccessible,no unintended clipping. Screens underignored build/frame-preview-014-{1,1.5};syntheticRGBonly,no private MARS/frames. NativeglobalRDDoffconfirmed;no reviewstart. Sourceworkunitcommit/independentRisk3verificationnext;Windows build/downloadstillpending.
