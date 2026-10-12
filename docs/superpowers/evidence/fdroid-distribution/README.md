# F-Droid distribution qualification

The four-edition change keeps full assets in GitHub APKs and the canonical
Native AAR, with 20 starters and explicit collection download in F-Droid APKs.
This evidence qualifies the bounded starter and pack journeys below. It does
not certify physical-TV performance, API21 runtime behavior, Windows pixel
equivalence or every preset in the full collection.

## Starter runtime

Task-owned emulators, host GPU/HVF and Apple M4 Pro GLES translation:

| Device | Serial | Fingerprint | Native surface |
|---|---|---|---|
| Phone, Android14 | emulator-5630 | `Android/sdk_phone64_arm64/emu64a:14/UE1A.230829.036.A1/11228894:userdebug/test-keys` | 1560×720 |
| TV, Android16 | emulator-5632 | `google/sdk_google_atv64_arm64/emu64a:16/BT2A.260319.001/15058170:user/dev-keys` | 1280×720 |

Each device rendered all 20 original, hash-identified preset files for at least
90 completed frames per selection, with pulsed synthetic unsigned mono PCM,
received audio peak above 0.1 and visible centre-region output. The prescribed
signal has 110 Hz kicks and 1760 Hz accents with repeating amplitude envelopes.
The minimum recorded audio peak was 0.29879 on TV and 0.28345 on phone.
`tv/starter-runtime.json` and `phone/starter-runtime.json` name every capture.
`sha256.json` binds the checked-in evidence files.

APK/test APK identities for these rendering runs:

| | Setup APK SHA256 | Test APK SHA256 |
|---|---|---|
| TV | `9f9179d6495867050669ad9310e2a12c95cd618018a6fcdc54f0a194294855e5` | `2a92f205dec42984f08cb5b7d7ba79bc816d77e120a69707a5609f2f695dae5c` |
| Phone | `a0a5e9bbbf7a231cc132bfa5876403d9f12d54bb870a1875438321065cc97bae` | `5c41d6f44619b58f05243a0887719c9194a7aeae47123a8ef4ce8c08c149f734` |

The first steady-tone phone probe left Geiss Spiral Artifact black. Its source
sets `wave_a=beat_level`; the qualified run uses beat-rich input and passes on
both devices without changing equations. The initial candidate requiring
`rose.jpg` was replaced by that texture-free preset from the same pinned
Butterchurn curation source. The final 15 minimal / 5 nonMinimal selection retains
20 All, 7 Chill, 10 Normal and 2 Intense memberships and has no external textures.
Selection provenance, file hashes and the replacement reason live in
`tools/preset-distribution/starter-presets.json`. This is a curated starter set.

## Pack and input journeys

Both devices pass explicit consent/decline, full 9,606-preset installation,
separate two-preset Custom coexistence (All 9,608), cold restart and removal
(All 22, Custom 2), including retaining native-leased files and reclaiming them
after retirement. The tests also verify that rendering advances during import
and no partial download ZIP remains after completion.

Network delivery is deliberately a file-backed HTTPS response adapter in the
test APK. It supplies the real 40,615,848-byte archive with SHA256
`8200aad345c5dbbc011809c93d4e1267fbc2a3c1ae62d31073d111848a9a96b0`;
platform parsing, SHA/CRC/size validation, extraction, UI consent and actual
native publication are production paths. Public GitHub HTTPS delivery is a
post-publication check, not established by this adapter.

The original phone pointer helper used dialog-window coordinates. Its first
install attempt never started a transfer. Screen-coordinate injection fixes
the harness; the successful phone pack/restart/removal test APK is
`6c037b9ec9dacb5a36b8a5c47196d7457fbd46ae5a10daf20550986c9d9f2043`.
TV uses D-pad focus. Initial long dialog labels clipped the starter action on
Android16; shorter equal-access choices pass the visibility/focus checks and
are shown in `tv/fdroid-consent.jpg`.

Existing phone audio instrumentation passes real microphone recorder samples,
denied/granted playback consent, local 440 Hz capturable audio (peak RMS 0.34306),
Home/pause cleanup, fresh consent after resume and restarted-service cleanup.
Existing touch navigation and TV menu/focus/scrolling/Home-resume cases pass.
These are emulator/API-specific checks, not a guarantee every player permits
playback capture.

Host regressions cover archive rejection, retained previous pointers,
insufficient storage, extraction cancellation, network cancellation/disconnect,
missing/changed installed files and final-status publication after cleanup.

## Reproducibility and consumer

`task6-local-reproducibility.json` binds source a562f72a, local nonpublishing
version 2.3.39/code 88, fdroidserver 2.4.5, JDK 21 and both independent source builds.
Actual F-Droid scanning/build/signature-transfer verification passes against
regular-checkout debug-signed references. Initial worktree references differed
only in AGP's VCS metadata (`NO_VALID_GIT_FOUND` versus the real commit).
Official-release signing-key verification and GitLab pipeline results are
separate post-publication requirements.

Milkbeat source `f970d7fb` builds its GitHub debug APK and passes 23 focused
visualizer/preference/audio-tap tests against the exact new full AAR, SHA256
`902a2752e78de903170686ca16f48df6d209db87af83c2ef72ea919543012d6f`.
The AAR retains 9,606 presets and 74 textures. It adds official-slot Java/JNI
methods while retaining existing host APIs and Native rendering behavior.

Live token check 38183829261 confirms an active `api` token, Owner 50 on the fork,
and successful scratch-branch creation/deletion; expiry 2027-10-11. No submission
was modified by the check. Live synchronization activates after publication.

## Final packaging checks

Controlled local release identity 2.3.39/code 88, JDK 21:

| Edition | APK bytes | Presets | Textures |
|---|---:|---:|---:|
| GitHub TV | 43,656,205 | 9,606 | 74 |
| GitHub phone | 43,660,800 | 9,606 | 74 |
| F-Droid TV | 2,091,767 | 20 | 0 |
| F-Droid phone | 2,096,647 | 20 | 0 |

All four packaged IDs, version identities, launchers and audio permissions
pass checks. F-Droid APKs contain no install permission/provider or APK-update
implementation. Starter source hashes, indexes/moods and qualification marker
pass; the staged full AAR retains all source assets. These local artifacts are
not official signed/public release claims.
