# Windows landscape candidate 0.2.0rc5
Build a distinct portable Windows candidate containing the completed native landscape implementation.
Preserve accepted rc4, existing settings and unrelated local work; no physical USB testing or final release.

## Specs
S1 — "adelante preparalo"
S2 — Accepted proposal: "¿preparo el nuevo candidato de Windows para probarlo? El ZIP rc4 sigue sin cambios."

## Tasks
- T1 [S1,S2] Prepare rc5 metadata and validate the candidate source | route: parent inline | status: done | commit: pending.
- T2 [S1,S2] Publish exact candidate and run existing Windows workflow once | route: parent background command | Risk: item 5 (Windows artifact delivery) | status: in_progress | commit: pending.
- T3 [S1,S2] Verify actual new archive and independent artifact proof | route: parent stream verification plus gentle-ai-verify | Risk: item 5 (Windows artifact delivery) | status: pending | commit: pending.
- T4 [S1,S2] Publish verified download instructions and delivery notes | route: parent inline | status: pending | commit: pending.

## Log
L1 — Original request: "adelante preparalo". It accepts the immediately preceding proposal quoted in S2, following the native landscape implementation request.
L2 — Baselineb9cde24b8719c0a79ffbc6c62fc1b81f080787c1; implementationfd201b69d65f1f4deed851343c066a0ceb4ceda2 is software-qualified. Current branchfeat/native-landscape-output, remotehttps://github.com/ghosthvj/MarsDisplay.git. Candidateversion0.2.0rc5; keep rc4 c059526/artifact12560971970 immutable. Existing exact-SHA Windows workflow, pinned SDK and QT_QPA_FONTDIR=C:/Windows/Fonts remain unchanged. No schema migration, hardware probe, release/tag/merge/PR or dependency change.
L3 — Large/resumability: remote build, archive identity and independent verification must survive waits. Forecast under150authoredlines for metadata/notes, single local delivery unit per phase; review boundaryb9cde24, not inherited historical branch. Delivery strategyask-on-risk. Private evidence underbuild/native-landscape-rc5. Stream ZIP verification, never extract or run Windows binaries on Linux. Prior software proof does not substitute for this new artifact. Initial search referenced nonexistent tests/test_packaging.py and exited2; corrected discovery found existing test_packaging_*.py modules, no test/build failed in that lookup.

L4 — T1complete: metadata check proves only projectversion changed frombaseline; SDK pins, build recipe and workflow unchanged. No meaningful RED for a version/documentation-only change; existing fullsuite job164exit0:391tests in48.631s,387passed/4Windows-onlyskips. Job165 confirmed targetghosthvj/MarsDisplay, main, nonarchived andpush/adminpermission. Private build/verification helpers adapted from qualifiedrc4; no runtime extraction. T2starts with exact candidatecommit/nonforcepush/single dispatch; never redispatch on ambiguity or timeout.
