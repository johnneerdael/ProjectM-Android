# xCrash source provenance

- Upstream: https://github.com/iqiyi/xCrash
- Pinned commit: `86dea4fa0cdbae68b63e9b34436fa20b51244d11` (2025-06-27).
- Latest upstream change affecting `xcrash_lib`: `1e47e97dace52c8662631b0e7b939224635de3ee` (2022-04-25). The 2025 commit changes documentation; it does not demonstrate recent native maintenance.
- Imported paths: `xcrash_lib/src/main/java`, `xcrash_lib/src/main/cpp`, and `LICENSE`. `UPSTREAM-SHA256SUMS` records the exact imported bytes. No upstream samples, documentation, standalone tests, logs, Gradle plugins or prebuilt libraries are imported. `xc_test.c` is part of upstream's runtime JNI library and retained because its test entry point is registered by `xc_jni.c`.
- License: primarily MIT, with the BSD and public-domain component notices reproduced in `LICENSE` and source headers. No upstream documentation is redistributed.

The source is unmodified. `core/src/main/cpp/xcrash/CMakeLists.txt` adapts warning options for NDK 27 while retaining upstream's CMake target definitions, optimizer and signal/unwinding implementation. Java sources compile directly into `:core`; both native outputs are built from source and distributed inside its AAR. No downloads occur during the build.

Upstream explicitly documents Android API 16-30 and ARM32/ARM64. ProjectM enables local native capture alongside Android exit diagnostics, including API 21-30 where the platform does not expose native tombstones to the application. A task-owned API34 ARM64 emulator captured an intentionally delivered SIGSEGV, saved a readable native backtrace, and displayed it after process restart. That test does not qualify Fire TV/PowerVR or every newer Android release; API-level and OEM runtime qualification remain separate from successful source builds.

The dumper is an ELF executable named `libxcrash_dumper.so`, launched from `ApplicationInfo.nativeLibraryDir`. Host APKs (including Milkbeat) must set `android.packagingOptions.jniLibs.useLegacyPackaging = true` and preserve the core AAR manifest's `android:extractNativeLibs="true"`. Packaging both native files without extraction cannot provide the full separate-process dump. Extraction also increases installed disk use for the host's other JNI libraries.

Capture remains in app-private, no-backup storage. Integration disables Java/ANR handlers, logcat, file-descriptor/network listings and other-thread dumps. Native tombstones still include registers, raw stack/near-register memory and device/build metadata. The library does not implement an uploader. Keep reports local, bounded and user-deletable; correlate engine breadcrumbs separately after restart.
