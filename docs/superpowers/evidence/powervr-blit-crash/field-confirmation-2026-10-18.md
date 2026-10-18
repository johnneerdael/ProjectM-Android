# PowerVR field confirmation and device coverage

## Confirmed fix

On 2026-10-18, the original reporter confirmed that the released fix stops the affected device's crashes. In reply to the model question, they identified the original reported device: **Amazon Fire TV Stick 4K Max, 2nd generation (2023), AFTKRT, PowerVR Rogue GE9215**. No additional individually tested model was supplied. This supersedes the pending-device status at the 2026-10-17 engineering checkpoint.

The fix shipped in **ProjectM 2.3.56** (PR #91, main `ebbee71f7e76078cef2d5318bdc3414396652897`) and **Milkbeat 1.0.13** (PR #97, main `bf1c4483ced0ed1353cc163c41199d6fe1af69c1`). The earlier native source binding, test records, image hashes and manifests remain the original engineering evidence, not records of this field test. No firmware revision, test duration or per-model test matrix was provided with the confirmation.

## Every supported PowerVR model receives the fix

This is not a device-model allowlist. Patch 0036 initializes the per-context guard when `GL_VENDOR` contains `Imagination` or `GL_RENDERER` contains `PowerVR`. Patch 0038 uses that same initialized context flag to select textured copies in framebuffer resizing, Native-trails recombination and host-scaled presentation. Thus newly identified PowerVR phone, tablet and TV models already receive the fix without adding model names to the code. Ordinary-vendor framebuffer resizing also retains 0038's colour-zero routing, complete attachment resizing and read-source detachment corrections.

The [user-facing device table](../../../user-guide/troubleshooting.md#powervr-framebuffer-crashes-fixed-in-2356) identifies the same-GE9215 models found in current sources:

| Device | Identifier | Evidence |
|---|---|---|
| Fire TV Stick 4K Max 2nd generation (2023) | AFTKRT | [Amazon manufacturer specification](https://developer.amazon.com/docs/device-specs/device-specifications-fire-tv-streaming-media-player.html); original report and successful field retest |
| Fire TV Stick 4K Max 1st generation (2021) | AFTKA | Same Amazon specification: GE9215, Fire OS 7 |
| Fire TV Stick 4K 2nd generation (2023) | AFTKM | Same Amazon specification: GE9215, Fire OS 8 |
| Fire TV Stick 4K Plus (2025) | AFTMA08C15 | Same Amazon specification: GE9215, Fire OS 8 |
| Google TV Streamer 4K (2024) | kirkwood, codename | [Firsthand device report in AndroidX Media](https://github.com/androidx/media/issues/3347) identifies GE9215; that issue is about video decoding, not this ProjectM crash |

Amazon's same manufacturer table also identifies GE8300 in Fire TV Stick 4K 1st generation (2018/AFTMM), Stick 3rd generation (2020/AFTSSS), Stick Lite 1st generation (2020/AFTSS) and Stick HD (2024/AFTSS), and PowerVR Rogue GX6250 in the Fire TV 2nd-generation box (2015/AFTS). These all select the same PowerVR copy fix; no separate model rule is needed.

Additional manufacturer-identified GE8320 devices covered by the same predicate are [Redmi 9A/Helio G25](https://www.mi.com/es/redmi-9a/specs/), [Lenovo Tab M10 HD 2nd generation/Helio P22T](https://psref.lenovo.com/Product/Lenovo_Tablets/Tab_M10_HD_2nd_Gen) and [Lenovo Tab M10 FHD Plus 2nd generation/Helio P22T](https://psref.lenovo.com/Product/IdeaPad/Tab_M10_FHD_Plus_2nd_Gen). These extend the public inventory to phones and tablets without representing them as additional ProjectM field retests.

This is a sourced identification list, not an assertion that every listed firmware had crashed or that all listed models were individually retested. The complete coverage statement comes from GPU-family detection, not the completeness of a retail-model catalog. No additional GE9215 phone/tablet model was verified in this research. Other PowerVR families remain covered automatically.

Amazon's same specification identifies Fire TV Stick 4K Select (2025) as Vega OS/G310v2, not an Android/PowerVR model; do not include it in this fix's Android device list.

## Other GPU/driver reports checked

| GPU/device | Primary report | Classification and coverage |
|---|---|---|
| PowerVR GE8320, realme C2/RMX1941 | [Imagination developer forum](https://forums.imgtec.com/t/crash-glblitframebuffer-on-powervr-ge8320/4178), repeated on [Epic's support forum](https://forums.unrealengine.com/t/crash-on-screen-rotation-with-powervr-ge8320/2644470) | Actual `glBlitFramebuffer` SIGSEGV during rotation on driver 1.10@5130912. The existing PowerVR-wide ProjectM fix already bypasses its three blit sites on this GPU. This is related-driver evidence, not a second ProjectM field retest. |
| PowerVR GE8320, Galaxy A12 | Same Imagination/Epic report | The reporter says driver 1.13@5776728 did not reproduce the rotation crash. Keep this negative control: GPU name alone does not prove that every firmware was broken. It still selects ProjectM's automatic PowerVR fix. |
| OPPO A78/CPH2483 | The Imagination report names this as GE8320, but [OPPO's manufacturer specification](https://www.oppo.com/en/smartphones/series-a/a78-5g/specs/) identifies Mali-G57 MC2 | Conflicting device identification; do not label it a verified PowerVR model or use the contradictory report to enable a Mali-wide policy. |
| PowerVR GE8320, unspecified OPPO/ColorOS phone | [Filament #5118](https://github.com/google/filament/issues/5118) | The backtrace enters `glCompileShader`/the shader compiler. It does not establish the framebuffer-blit failure. |
| PowerVR GE8322, moto e(7i) power/XT2097, Unisoc SC9863A | [Flutter #192230](https://github.com/flutter/flutter/issues/192230) | EGL/context-lifecycle failure reported for Flutter; not evidence of the same blit call site. ProjectM nevertheless already selects its PowerVR-wide copy path on this renderer. |
| Adreno, historical Android drivers | [Dolphin developers' 2013 driver report](https://dolphin-emu.org/blog/2013/09/26/dolphin-emulator-and-opengl-drivers-hall-fameshame/) | Blit corruption/crashes are reported historically. No matching supported-version ProjectM backtrace/driver range was established; do not turn this into a claim that all current Adreno devices have the confirmed ProjectM fault. |
| Mali, Nexus 10 driver | [Arm vendor support discussion](https://community.arm.com/support-forums/f/mobile-graphics-and-gaming-forum/2661/glblitframebuffer-from-fbo---back-buffer-leaves-trails-on-nexus-10) | Colour-copy trails on Android 4.3/4.4, with a textured-quad workaround; Arm later reports it absent on newer driver trunk. Related blit behavior, not this native crash. Those reported Android versions are below ProjectM's Android 5 minimum. |
| Mali, MSAA resolves | [Babylon Native #988](https://github.com/BabylonJS/BabylonNative/issues/988) and [Arm's MSAA guidance](https://developer.arm.com/documentation/101897/0304/Fragment-shading/Multisampling-for-OpenGL-ES) | Multisampling/resolve reports must be distinguished from ProjectM's single-sample colour copies. No matching ProjectM failure was established. |

The research does not establish an equivalent, currently supported ProjectM crash outside the PowerVR family. Therefore no new non-PowerVR GPU blacklist or speculative runtime policy is introduced by this documentation update. The main release notes should clearly call the PowerVR issue **fixed**, and describe every supported PowerVR model as receiving that fix.

## F-Droid availability

Verified 2026-10-18 with HTTP 200 on the [official ProjectM Android listing](https://f-droid.org/en/packages/nl.neerdael.projectm/) and [package API](https://f-droid.org/api/v1/packages/nl.neerdael.projectm): phone/tablet package `nl.neerdael.projectm`, suggested version 2.3.49/code 98. The listing identifies it as built/signed by the original developer. The [TV package API](https://f-droid.org/api/v1/packages/nl.neerdael.projectmtv) returned 404 at this checkpoint.

Catalog availability is now confirmed for phones/tablets, but its observed version predates the 2.3.56 fix. User guidance links the live store, requires 2.3.56+ for the fix, and explains that GitHub also provides current F-Droid-flavor APKs. Catalog updates and GitHub publication remain independent. These dated catalog observations should not become a permanently hardcoded latest-version promise.
