# Native macOS GLES understanding checkpoint

The user allowed native library-code execution as an alternative to the blocked
Android emulator. The Mac cannot load an Android ELF `.so` directly despite
matching ARM64 CPUs. An isolated build of the **pinned patched source34 engine**
uses software SwiftShader GLES3 on macOS; it is not stock upstream projectM.
No authored presets, engine source, AAR bytes or production devices are modified.

The initial accelerated CGL check fails before preset loading (invalid CoreGraphics
connection). The native software GLES control succeeds with exact expected
RGBA[51,102,153,255] readback and no GL error. The actual engine then renders
Zylot Spiral for300 frames at480×270/30fps with explicit SetFrameTime and the
frozen synthetic audio quantized to U8 as the existing Java runner does.
Native trails are explicitly disabled, line reference is480×270, and the whole
engine renders directly to the pbuffer. Every frame checks readback GL errors.
FFprobe verifies a10.000-second MP4 with300 H.264 frames and AAC audio.

**Matched:** centred multi-turn coloured spiral, clipped outer coils, retained
layers and evolving local colour/band pattern. **Miss:** the illustration
underestimated broad dense feedback bands. The original v5 prediction remains
unchanged. Source-math work now links fresh inward locus motion with outward
retained-feature motion and inter-turn pitch. Do not diagnose a library defect
or fit a special-case label from this visual discrepancy.

The screenshot/clip are real patched-engine render captures, unlike the generated
illustration. They remain **native macOS/source GLES comparison evidence**, not
published Android AAR/JNI/GPU certification. No calibrated visual score is assigned.
Driver, platform ABI, API binding, line-reference configuration and clock are
recorded separately. Source-only grouping never consumes these rendered frames.

Local artifacts:
- `build/preset-corpus/native-macos-checkpoint-2026-10-11/frame-149.png`
- `build/preset-corpus/native-macos-checkpoint-2026-10-11/spiral-10s.mp4`
- `build/preset-corpus/preset-understanding-checkpoint-2026-10-11/prediction-image-v5.png`

Full source/reader/AAR/audio/illustration/dylib identities and raw output digests
are preserved beside this report. The driver uses the existing production source
and APIs; rebuild with its saved CMakeLists and explicit PROJECTM_SOURCE and
JSON_INCLUDE paths. The initial failed build diagnostics concerned only the
harness include path and an absent EGL enum spelling, both corrected; no native
engine fix was required. Downloads remains outside the permitted write roots.
