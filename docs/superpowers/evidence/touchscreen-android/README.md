# Touchscreen Android validation — 2026-10-11

Scope: a separate phone/tablet APK, touch-responsive framework menus, microphone input, consented phone playback capture, and both APKs in CI/release packaging. The core and renderer source are unchanged. Artifact/source SHA256 identities are in [identities.json](identities.json). Local release APKs use the debug signing key and the unchanged 2.3.0 version floor; CI assigns the release version and signs both with the release key.

## Devices and runtime proof

Task-owned API34 ARM64 Pixel 5 emulator (`emulator-5630`), 1080×2340/440dpi, host GPU/HVF, Apple M4 Pro/GLES3.0, 4GB guest RAM. Fingerprint: `Android/sdk_phone64_arm64/emu64a:14/UE1A.230829.036.A1/11228894:userdebug/test-keys`. Host microphone/audio output were disabled; the microphone witness proves AudioRecord startup and reads, not acoustic fidelity. The playback witness generates capturable 44.1kHz mono 440Hz PCM via AudioTrack on the phone and proves it reaches the engine.

- [Touch journey](touch-runtime.txt): slow right/left switching and previous history; vertical/horizontal cancellation; multi-touch suppression; menu tap; persisted main/Advanced/Track values; all panel scrolling; close/back; held-touch auto-hide suspension and release timeout; retained D-pad; stable system-bar-safe bounds.
- [Phone audio](phone-audio-runtime.txt): actual microphone recorder reads, denied/granted Android playback consent, generated local playback RMS 0.343, Home/pause cleanup, fresh consent on resume and restart cleanup.
- [TV journey](tv-runtime.txt): default TV APK main/Advanced/Track D-pad focus scrolling, saved option, Back/Menu, phone audio row hidden and Home/resume rendering. Task-owned API36 ARM64 Android TV emulator (`emulator-5632`), 1080p, host GPU/HVF, 4GB guest RAM. Fingerprint: `google/sdk_google_atv64_arm64/emu64a:16/BT2A.260319.001/15058170:user/dev-keys`.
- The existing `setup_case resolution` journey also passed on that TV emulator: Auto, D-pad fixed 720p, Native wrap/persistence, completed frames and separate Auto history.

The phone screenshot shows the lower main menu after scrolling, including both setting values and touch navigation:

![Scrolled phone menu with visible values and Close menu](phone-menu.png)

## Regression and build checks

- `./gradlew testReleaseUnitTest assembleRelease :app:assembleDebug :app:assembleDebugAndroidTest -PsetupScreenshotTest`: TV APK/core and test APK, 149 JVM tests (75 app, 74 core), zero failures.
- `./gradlew :app:assembleRelease :app:testReleaseUnitTest :app:processProfileMainManifest -PandroidTouchscreen=true`: phone release APK, 75 app JVM tests, and profile manifest. Phone manifests have regular Launcher only, optional Leanback, required touchscreen, and the non-exported mediaProjection service; profile retains `profileable`.
- `python3 -m unittest discover -s .github/scripts/tests -v`: 187 passed, including executing workflow packaging scripts for stable/CI names, two APKs/mappings and exactly one core AAR. New publisher tests initially failed for missing Android assets/alias checks and pass after implementation.
- `bash core/src/test/native/run_native_tests.sh`: 64/64 passed; the transition overlay EGL/GLES test is explicitly skipped on this Mac because pkg-config cannot find EGL/GLES development files.
- Strict MkDocs build passes using `docs/site-requirements.txt`. JDK 21.0.11/Gradle 8.14.2. `git diff --check` passes.
- actionlint 1.7.12 passes the changed workflows when ignoring only its rejection of the existing `concurrency.queue` key; that key predates this change.

[Bounds RED](bounds-red.txt) reproduces the cancelled slide animation leaving a 66px translation and clipping the 935px panel to 902px. A single translation/alpha animation fixes it. Stable phone navigation insets are also included in panel margins; the final screenshot confirms values remain visible.

## Reproduce

Build/install commands and instrumentation entrypoints are in [the development guide](../../../user-guide/development.md#touchscreen-build): use `setup_case touchscreen`, `phone_audio` or `tv_menu` with the matching APK. Dismiss Android's fullscreen tutorial before pointer injection. These tests use the actual framework activity and audio APIs and add no runtime dependency.

No physical-phone acoustic test, third-party player compatibility matrix, API21 runtime coverage, physical-TV performance test or rendering fidelity certification is claimed. Android playback capture needs API29+, fresh consent and an allowed source player; opted-out/protected audio cannot be captured. CI/review results belong to the PR and remain separate from this local evidence.
