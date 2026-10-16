# Build and test

ProjectM TV is an Android app (`:app`) and an engine library (`:core`). The engine builds projectM from the pinned submodule and applies the [patch series](engine/patches.md) at configure time.

## Build the app

Requirements: JDK 21, Android SDK platform 34, NDK 27.3.13750724, CMake 3.22.1, and a `local.properties` file with `sdk.dir`.

```sh
git clone --recursive https://github.com/johnneerdael/ProjectM-Android.git
cd ProjectM-Android
./gradlew assembleDebug          # debug APK
./gradlew assembleRelease        # release APK + core AAR
./gradlew assembleProfile        # release build that profilers can attach to
```

In an existing clone, run `git submodule update --init --recursive`. Never commit edits inside `third_party/projectm`: engine changes are new patch files in `tools/projectm-patches/`.

## Touchscreen build

The default build is for Android TV. Add `-PandroidTouchscreen=true` to build the phone/tablet APK, which has app ID `nl.neerdael.projectm`, a regular Launcher entry, optional Leanback and a required touchscreen. Both builds use the same source and core. Their outputs occupy the same paths, so copy each APK and mapping before building the other platform. CI does this for reviewed PR validation and for releases, publishing `projectM-TV-<version>.apk` and `projectM-Android-<version>.apk` plus one Native core AAR.

```sh
./gradlew :app:assembleRelease :app:testReleaseUnitTest -PandroidTouchscreen=true
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PandroidTouchscreen=true -PsetupScreenshotTest
adb -s SERIAL install -r app/build/outputs/apk/debug/app-debug.apk
adb -s SERIAL install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s SERIAL shell pm grant nl.neerdael.projectm.setuptest android.permission.RECORD_AUDIO
adb -s SERIAL shell am instrument -w -e setup_case touchscreen nl.neerdael.projectm.setuptest.test/com.example.projectm.visualizer.MusicCategoryInstrumentation
```

Use a task-owned phone emulator or device. The framework instrumentation checks actual tap/swipe input, preset history, scroll isolation, persisted settings, touch navigation and retained D-pad controls, and writes `touch-menu.png` to the target's external cache. Profile and test suffixes also apply to the touchscreen app ID.

For phone audio, run the same instrumentation with `-e setup_case phone_audio` on Android 10+. It checks microphone recorder reads, denied/granted playback consent, synthetic local playback reaching the engine, and pause cleanup. Dismiss Android's first-launch fullscreen tutorial before pointer tests.

## F-Droid builds

The default GitHub build is unflavored and bundles all 9,606 presets and 74 textures. `-PprojectmDistribution=fdroid` selects one named flavor for the requested device, with generated 20-preset assets and the app updater excluded from compilation:

```sh
./gradlew :app:assembleFdroidTvRelease :app:testFdroidTvReleaseUnitTest -PprojectmDistribution=fdroid
./gradlew :app:assembleFdroidAndroidRelease :app:testFdroidAndroidReleaseUnitTest -PprojectmDistribution=fdroid -PandroidTouchscreen=true
```

F-Droid listings live under `src/fdroidTv/fastlane/` and `src/fdroidAndroid/fastlane/`, and the pinned importer selects the recipe's flavor. The listing used to sit at the root; it was moved after an importer check showed TV screenshots leaking into the phone listing.

For isolated runtime checks, use the matching `assembleFdroidTvDebug` / `assembleFdroidTvDebugAndroidTest` tasks, or the `fdroidAndroid` equivalents with `-PandroidTouchscreen=true`, and add `-PsetupScreenshotTest`. The cases `fdroid_starters`, `fdroid_pack`, `fdroid_pack_restart` and `fdroid_pack_removed` check consent, actual GL output/audio, installation, independent custom packs, restart and removal. The pack case reads a host-pushed `official-test.zip` from external files through a test-only response adapter. Public HTTPS delivery is checked separately after publication.

Use `-PprojectmReleaseVersion=VERSION -PprojectmReleaseVersionCode=CODE` for a controlled build identity. Release CI derives both values from the same source and writes them into `gradle.properties` in the tagged release source, where F-Droid's tag-based update check reads them. The GitLab secret, validation and recovery workflow are documented in [Recipe/sync setup](https://github.com/johnneerdael/ProjectM-Android/blob/main/tools/fdroid/README.md).

## Run the tests

| Command | Covers |
|---|---|
| `./gradlew testDebugUnitTest` | App and core JVM tests: settings, automatic quality, custom-pack import, upload server |
| `core/src/test/native/run_native_tests.sh` | Native engine tests and patched-projectM regression controls under ASan/UBSan, with real GL (macOS OpenGL or Linux EGL/GLES) |
| `tools/projectm-host-tests.sh` | projectM's own GoogleTest suite with the patches applied |
| `tools/check-patch-series.sh` | The patch series applies cleanly to the pinned commit |
| `tools/check-presets.py`, `tools/gen-preset-index.py --check` | Bundled presets react to audio, reference only bundled textures, and match the index |
| `python -m pytest tools/preset-lab/tests` | Preset Lab |
| `.venv-fdroid/bin/python -m unittest discover -s .github/scripts/tests -v` | Release tooling and pinned F-Droid generation/import/discovery/synchronization; install `tools/fdroid/requirements.txt` in that environment first |

[Validation and evidence](engine/validation.md) describes what the native controls check, including the legacy compatibility controls for `fShader` shading and mode-1 waveforms ([BrainStain investigation](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/superpowers/evidence/brainstain-dark-output/README.md)). Negative-power controls also verify CPU-defined nested exponents, attribute 9 uploads, unchanged equation parameters, nonfinite preservation, resize and prepared replay ([power-domain evidence](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/superpowers/evidence/tulip-negative-zoom-power/README.md)). Sampling in the invalid fractional domain still depends on the backend, so its appearance cannot be established portably from source alone.

## Test on a TV without replacing the release

A debug build cannot update a production installation because it has a different signing key. These test builds install side by side with it:

| Gradle property | Package | Use |
|---|---|---|
| `-PpresetLabDeviceTest` | `nl.neerdael.projectmtv.presettest` | Mood/category instrumentation and live-audio checks |
| `-PsetupScreenshotTest` | `nl.neerdael.projectmtv.setuptest` | Setup journeys: resolution, Native trails, custom-pack upload and restart |

```sh
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PsetupScreenshotTest
adb -s SERIAL shell pm grant --user USER nl.neerdael.projectmtv.setuptest android.permission.RECORD_AUDIO
adb -s SERIAL shell am instrument --user USER -w -e setup_case resolution \
  nl.neerdael.projectmtv.setuptest.test/com.example.projectm.visualizer.MusicCategoryInstrumentation
```

The other cases are `tv_menu`, which checks D-pad focus/scrolling across all shared panels and Home/resume, `native_trails`, `custom_pack` followed by a cold `custom_pack_restart`, and `custom_pack_qr`. Find `USER` with `adb shell am get-current-user`. These cases check settings, navigation, uploads and completed frames. They do not check preset appearance or performance.

### Profiling and diagnostics

- Pin one preset for measurements: `adb shell setprop debug.projectmtv.preset '<filename prefix>'`, and clear it afterwards.
- `tools/tv-diagnostics.sh <tv-ip>:5555 --no-install --duration 180` collects logs and frame statistics ([DIAGNOSTICS.md](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/DIAGNOSTICS.md)).
- CPU profiling with the profile build and simpleperf: [PROFILING.md](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/PROFILING.md).

## Use the engine in another app

Every release publishes the engine as an Android library, `projectM-TV-core-<version>.aar`, plus a stable alias `projectM-TV-core.aar`. [Milkbeat](https://github.com/johnneerdael/Milkbeat) uses it this way and is rebuilt automatically when a new core is released.

The public API lives in `nl.neerdael.projectm.core`:

| Class | Role |
|---|---|
| `ProjectMCore.init(context)` | Call once from `Application.onCreate`: indexes presets and copies textures |
| `VisualizerView` + `VisualizerRenderer` | The GL surface and its renderer |
| `ProjectMJNI` | Audio input (`addWaveform`), preset navigation, settings such as transitions and `setNativeTrails` |
| `QualityController` | Automatic resolution from frame rate and live memory headroom; `setResolutionMode` for fixed or Native sizes |
| `DeviceProfile`, `DisplayInfo` | Device tier and physical panel detection |
| `NativeCrashReports` | Capture status and bounded saved native reports; read or clear on a background thread |

The AAR includes source-built xCrash and its native dumper. Set `android.packagingOptions.jniLibs.useLegacyPackaging = true` in the consuming app and keep the merged `android:extractNativeLibs="true"` attribute. The dumper must exist as an executable file under `ApplicationInfo.nativeLibraryDir`; packaging it only inside the APK prevents the full dump. `ProjectMCore.init(context)` starts local capture once per process. `NativeCrashReports.recent(context)` returns up to five reports with `fileName`, `timestampMs` and readable `details`; `status()` reports initialization failure and `clear(context)` removes native reports only. Nothing uploads automatically.

To verify capture in an isolated setup build, run the two instrumentation cases `native_crash_capture` then `native_crash_report`. The first deliberately sends SIGSEGV to the test app and must end with `Process crashed`; the second starts a new process and checks the saved signal/backtrace in Recent exits. The report screenshot is `native-crash-report.png` in the test app's external cache. Do not run the fault case against a production app session.

Some engine defaults differ from the app's. For example, blank-preset skipping is off in the core and switched on by the app. `ProjectMJNI.getVersion()` reports the upstream numeric projectM version (`4.2.0`), not the release version. Releasing and publishing are described in [RELEASING.md](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/RELEASING.md).

## Offline preset tools

- [Preset Lab](https://github.com/johnneerdael/ProjectM-Android/tree/main/tools/preset-lab): offline rendering, static audio tracing and bass-response screening with a private desktop build of the engine.
- [milk-analyzer](https://github.com/johnneerdael/ProjectM-Android/tree/main/tools/milk-analyzer): source parsing, equation-domain proofs, shader lowering and the mood scorer.

See [Test and predict presets](authoring/testing.md) for what each tool can tell you.

## This documentation site

The site uses MkDocs with the Material theme. Its source is `docs/user-guide/`; GitHub Pages serves the static build.

```sh
python3 -m venv build/docs-env
build/docs-env/bin/pip install -r docs/site-requirements.txt
build/docs-env/bin/mkdocs serve          # preview at http://127.0.0.1:8000
build/docs-env/bin/mkdocs build --strict
```

Reviewed pull requests build the site, and every merge to `main` publishes it after the full test suite passes. Screenshots on these pages come from the released app on an Android TV emulator, playing music through Milkbeat.

## Contributing

Changes go through a pull request to `main`. Claude and Codex review the initial ready PR; for follow-up commits, choose one reviewer by posting exactly `@claude review` or `@codex review`. A PR runs the full build only after a clean signoff for its latest full commit SHA, with every review thread resolved and no outstanding review requests or changes requested. See the [review gate and reviewer setup](https://github.com/johnneerdael/ProjectM-Android/blob/main/docs/RELEASING.md#review-gate) for permissions, completion signals and manual triggers. Every PR needs a `## Release notes` section written for people using the app (see the PR template). Each successfully tested merge automatically publishes a new versioned APK and core library.
