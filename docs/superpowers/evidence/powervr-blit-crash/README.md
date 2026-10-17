# PowerVR framebuffer blit crash

## Report and source binding

The reporter supplied the standalone ProjectM 2.3.55 native report after Milkbeat 1.0.12 also continued crashing. A preset switch is not required. The report records SIGSEGV/SEGV_MAPERR at `0x88`, on the GL render thread, inside the PowerVR driver's `glBlitFramebuffer`. Its ARM `libprojectmtv.so` build ID and 1,612,560-byte size match the published 2.3.55 AAR exactly. Personal photographs and randomized installation paths are not committed; [transcribed diagnostic fields](reported-crash.json) retain the useful identifiers.

Rebuilt unchanged main `76757e6e` using the pinned NDK. The rebuild's complete ELF build ID differs because it retains build/debug metadata, but its `.text` bytes and virtual address match the released library exactly: address `0x85390`, 910,400 bytes, SHA-256 `990c0cea15b0fbbe94fc0f71e5cf4c3a373242697c4a1e9384cba68840426c3b`. The corresponding unstripped symbols map the caller to `Renderer::Framebuffer::SetSize`, line124, through `MilkdropPreset::RenderFrame`, line96, and `ProjectM::RenderFrame`, line229. This is the old-image resize copy; Auto can trigger it during an unchanged preset.

## Candidate

Patch0038 uses a cached fullscreen textured draw on Imagination/PowerVR contexts for framebuffer resizing, Native-trails detail recombination and host-scaled presentation. It uses the existing Shader and Sampler implementations, preserves touched state, routes the image copy only to colour zero, and finishes resizing auxiliary attachments before copying. Primary colour formats remain unchanged. Other GPUs retain framebuffer blits. Copy resources remember the existing context-forget generation and drop stale names without GPU deletion on a replacement context.

## Local controls so far

- The original real-GL resize control fails because the PowerVR-selected branch calls `glBlitFramebuffer`; the candidate avoids that call.
- Resize, mixed RGBA/integer attachment, actual host C API, caller-state, Native-trails and replacement-context controls pass on Mac GL. Small scaling is byte-identical; the 4K scaling control differs by at most one 8-bit channel step. Nearest detail recombination is byte-identical. Repeated resize reuses its copy program.
- The first replacement-context control caught stale copy resources deleting an aliased new program. Context-generation cleanup corrects it and the control passes.
- The JNI presentation control fails before routing the PowerVR case through the new copy API and passes afterwards; ordinary presentation retains its blit.
- Both ARM core builds pass and contain the new copy shader. All38 patches apply to clean pinned source.

Full sanitizer checks, Android/GLES runtime validation, documentation/release checks, current-head Codex review and CI are still pending at this checkpoint. Host vendor selection does not emulate the proprietary driver. The affected Fire TV must confirm the final crash outcome; this record does not claim it has already been tested there.
