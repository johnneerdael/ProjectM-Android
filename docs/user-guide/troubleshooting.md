# Troubleshooting

On TV, most problems show up in **Advanced › Diagnostics**: open the settings panel, select **Advanced ›**, and the Diagnostics card appears beside it. The [settings reference](settings.md#diagnostics) explains every line. On phones, use the main panel's **Audio input**, **Audio** meter, frame rate and render size; the separate Diagnostics card is TV-only.

## Visuals do not react to the music

### Android TV / Google TV

Start the music **on the TV** before opening ProjectM TV. Check the **Audio** meter in the main panel and the **Audio** line in Diagnostics:

| Diagnostics shows | Meaning | What to do |
|---|---|---|
| `no capture (permission?)` | Record-audio permission is missing | Allow it under Android **Settings › Apps › ProjectM TV › Permissions** |
| `no player session found yet` | The app has not found the player's audio session | Wait a few seconds; it searches automatically, and again when the track changes |
| `… silent / no data` | Attached, but no audio arrives | Make sure the music is actually playing; try a verified player |
| `player session N, 0.42 (live)` | Audio is arriving | Everything works; try another preset |

If no player is found, the app retries after the next track change (with notification access) and otherwise once a minute. Audio that a video app sends to the TV already Dolby-encoded never passes through Android's mixer, so it cannot be visualized. See [why the app listens to the player's session](engine/pipeline.md#audio-listening-to-the-player-not-the-room).

### Phone or tablet audio

Tap the visuals to open the menu. Check **Audio input** and the **Audio** meter:

| What you see | What to do |
|---|---|
| **No access** or **Permission needed** | Allow Record audio under **Settings › Apps › ProjectM Android › Permissions**, then reopen the app |
| **Microphone · Unavailable** | The microphone recorder could not start. Check microphone availability and select Microphone again |
| Microphone is selected but the meter is silent | Check Android's microphone privacy switch, make sound near the device and check whether another app is using the microphone |
| **Phone playback · Tap to start** | Select Phone playback and approve Android's capture prompt; this is required again after leaving and returning |
| Phone playback is listening but the meter is silent | Keep music playing on the same device when the visualizer opens. Try a player that allows Android playback capture; protected/opted-out audio cannot be captured |
| Phone playback is unavailable on an older device | Playback capture needs Android 10+. Use Microphone on earlier supported versions |

Capture stops when you open another app or lock the device; this is expected. Microphone resumes when you return, and Phone playback asks for consent again. Notification access enables track titles but does not grant playback capture. See [Phone setup](getting-started.md#touchscreen-phone-or-tablet).

## Track titles are missing

Open **Track display › Track info**. If it reads *Off · Allow*, select it and choose **Configure**, then enable the installed app (ProjectM TV or ProjectM Android) in Android's notification access ([walkthrough](getting-started.md#track-titles-optional)). **Dismiss** only hides the automatic reminder.

If the title shows but not the cover, the music app may not provide artwork. On TV, covers are verified with Spotify and Milkbeat; SoundCloud and SmartTube provide title and artist only.

## The picture stutters

1. Keep **Advanced › Resolution** on **Auto**. Fixed sizes and Native ignore frame rate.
2. Lower **Detail** if the preset's equations are CPU-heavy; resolution does not help those.
3. On a 4K panel keep **Native trails** on **Standard**.
4. If stutter happens only during changes, set **Transitions** to **Lightweight**.

The main panel shows frame rate and render size on both builds, and TV Diagnostics adds memory state. More in [Picture quality and performance](picture-quality.md#when-playback-stutters).

## The render size is lower than my TV

Auto lowers resolution to hold the target frame rate and to keep memory free for the music app; TV Diagnostics shows *resolution reduced for memory headroom* when memory is the reason. To test a preset at full size, choose **Advanced › Resolution › Native**. Memory protection still applies. Android often runs its menus at 1080p on a 4K TV; Diagnostics lists **Panel** (the physical display) separately from **UI**.

## The app closes at preset changes

If the visualizer closes by itself while the music keeps playing, often as one preset changes into the next:

**PowerVR/Imagination users: this framebuffer crash is fixed. Upgrade to ProjectM 2.3.56+ or Milkbeat 1.0.13+ first.** [Device models and upgrade details](#powervr-framebuffer-crashes-fixed-in-2356) are below.

1. Reopen the app and select **Advanced › Last exit** for the [exit report](settings.md#exit-report). Saved native reports include the signal, crashing thread and available stack, without connecting ADB.
2. Use **Copy report**, or photograph the report, and include the app version and device model. Mention whether the first preset works, whether the failure follows an automatic or manual change, and the names of the presets if known.
3. Android's *crashed (native code)* reason identifies a native failure, but does not establish whether the engine or graphics driver caused it. *Killed for low memory* means Android reported a memory kill. A missing native report is reported explicitly and does not mean the app exited normally.

A crash can also happen while the same preset keeps playing: Auto may change its rendering resolution without changing presets. Instant transitions do not bypass those resizes.

### PowerVR framebuffer crashes: fixed in 2.3.56

**Upgrade to ProjectM 2.3.56 or later, or Milkbeat 1.0.13 or later.** These releases fix the PowerVR framebuffer-blit crash, including failures during preset changes and while the same preset plays. The affected Fire TV Stick 4K Max (2nd generation, `AFTKRT`) has been retested and the reporter confirms that the crashes are fixed.

The fix applies automatically to **all supported Imagination/PowerVR GPUs**, rather than a whitelist of box or phone models. It replaces the failing `glBlitFramebuffer` copies with textured draws for feedback resizing, Native-trails recombination and scaled presentation. No compatibility switch is needed, and setting transitions to Lightweight or 0 seconds is not a substitute for upgrading.

These identified devices receive the fix. ProjectM supports Android 5.0+; Milkbeat requires Android 8.0+ on TV, so the older Fire OS 5/6 entries are ProjectM-only:

| Device | Build model / codename | GPU | Coverage |
|---|---|---|---|
| Fire TV Stick 4K Max, 2nd generation (2023) | `AFTKRT` | GE9215 | Crash fix confirmed by the reporter |
| Fire TV Stick 4K Max, 1st generation (2021) | `AFTKA` | GE9215 | Same GPU; automatic fix applies |
| Fire TV Stick 4K, 2nd generation (2023) | `AFTKM` | GE9215 | Same GPU; automatic fix applies |
| Fire TV Stick 4K Plus (2025) | `AFTMA08C15` | GE9215 | Same GPU; automatic fix applies |
| Google TV Streamer (4K, 2024) | `kirkwood` (codename) | PowerVR Rogue GE9215 | Same GPU; automatic fix applies |
| Fire TV Stick 4K, 1st generation (2018) | `AFTMM` | GE8300 | ProjectM fix applies; below Milkbeat's minimum Android version |
| Fire TV Stick, 3rd generation (2020) | `AFTSSS` | GE8300 | Automatic PowerVR fix applies |
| Fire TV Stick Lite, 1st generation (2020) | `AFTSS` | GE8300 | Automatic PowerVR fix applies |
| Fire TV Stick HD (2024) | `AFTSS` | GE8300 | Automatic PowerVR fix applies |
| Fire TV box, 2nd generation (2015) | `AFTS` | PowerVR Rogue GX6250 | ProjectM fix applies; below Milkbeat's minimum Android version |
| realme C2 | `RMX1941` | PowerVR GE8320 | Related driver-side blit crash reported; automatic fix applies |
| Redmi 9A | Helio G25 models | PowerVR GE8320 | Automatic PowerVR fix applies |
| Lenovo Tab M10 HD, 2nd generation | Helio P22T models | PowerVR GE8320 | Automatic PowerVR fix applies |
| Lenovo Tab M10 FHD Plus, 2nd generation | Helio P22T models | PowerVR GE8320 | Automatic PowerVR fix applies |

Amazon's [manufacturer specifications](https://developer.amazon.com/docs/device-specs/device-specifications-fire-tv-streaming-media-player.html) identify the nine Fire TV models. The Google TV Streamer's GPU is identified in a [device-owner report in AndroidX Media](https://github.com/androidx/media/issues/3347); that report concerns a separate video-decoder problem, not a ProjectM crash. The [GE8320 report on Imagination's forum](https://forums.imgtec.com/t/crash-glblitframebuffer-on-powervr-ge8320/4178) identifies a realme C2 blit crash on driver `1.10@5130912` during screen rotation.

Xiaomi identifies the Redmi 9A's GE8320 in its [manufacturer specifications](https://www.mi.com/es/redmi-9a/specs/). Lenovo's product references identify GE8320 graphics in [Tab M10 HD (2nd Gen)](https://psref.lenovo.com/Product/Lenovo_Tablets/Tab_M10_HD_2nd_Gen) and [Tab M10 FHD Plus (2nd Gen)](https://psref.lenovo.com/Product/IdeaPad/Tab_M10_FHD_Plus_2nd_Gen).

The table is an identification aid, not the boundary of the fix: other supported PowerVR phones, tablets and TV boxes also take the corrected path. Sharing a GPU does not mean every firmware previously crashed; the confirmed ProjectM retest above is the original `AFTKRT` case. Do not confuse the Fire TV Stick 4K Plus with the Vega OS-based Fire TV Stick 4K Select, which cannot run this Android APK.

Use the matching [TV or phone/tablet edition](getting-started.md#choose-an-edition). F-Droid updates can arrive later than GitHub releases: check the installed version before assuming the fix is present. Current F-Droid-flavor APKs are also attached to [GitHub Releases](https://github.com/johnneerdael/ProjectM-Android/releases/latest); these retain the F-Droid edition's starter collection and update behavior. The [patch record](engine/patches.md#0038-powervr-framebuffer-copies) explains the implementation and validation.

If a crash continues on a fixed version, use **Advanced › Last exit** and include the report, GPU, device model and installed version. This fix addresses the framebuffer-blit failure; the report can distinguish a different failure.

The former **Background compile** and **Shader binary cache** switches were removed after they failed to resolve the reported crashes. Compilation and binary caching run with their normal enabled defaults, including installations that previously saved those options as Off. The earlier PowerVR framebuffer-retirement protection remains in place as a separate safeguard.

## Native trails says inactive or fallback

Native trails works only above 1330p, so on a 1080p TV Diagnostics shows *inactive (render 1080p)*. That is expected. *Canvas fallback* usually means no supported whole-number authored canvas exists at this render size; *shader/resource fallback* means the GPU driver rejected the trails shaders. Either way, the standard renderer is used. Please report the Diagnostics text and your TV model.

## A preset is black, frozen or skipped

- Some presets build up slowly from black. Give them a few seconds of music.
- With **Skip blank presets** on, a preset that stays black while music plays is passed over, and skipped permanently the second time.
- With **Skip slow presets** on (Auto resolution only), a preset that cannot reach half the target frame rate even at the lowest resolution is skipped permanently.
- Presets that cannot be read or parsed are skipped too.

**Advanced › Skipped presets** shows the count, and selecting it resets the list. Presets that still fail are skipped again.

## My mix has fewer presets than expected

F-Droid editions start with 20 presets, so Mood counts are small. To download the complete library, open **Advanced › Cream of the Crop** (see [Collection setup](getting-started.md#optional-collection-in-f-droid-editions)).

The Mood panel counts only presets this device can play, so skipped presets reduce it. Options that would leave no presets are dimmed. When no preset matches your mix, either because every match is skipped or because a deselection leaves no preset that fits every group, the header reads *No presets match your mix; playing All*. Custom-pack presets do not play while an option is active; to play them, choose *Custom* in the Collection row. A full-collection download made before attributes existed offers only the Collection choice, and the header asks you to download the full collection again (Settings › Advanced › Cream of the Crop). See [Preset moods](predictive-collections.md).

## The collection download failed or disappeared

Keep the visualizer open while downloading. Leaving during the download or preparation cancels it; retry from **Advanced › Cream of the Crop**. Allow at least 186.1 MiB free during installation. The archive comes from GitHub, so a network block or an unavailable release can prevent the download. The 20 starters remain usable offline.

An incomplete or corrupted collection is rejected. If installed files are missing or changed after a restart, the app uses the starters; download the collection again from the same setting. Removing the collection keeps your custom pack. After clearing app data, reinstalling or restoring on another device, you need to download it again.

## A mood feels wrong

Mood attributes are predictions from a short measurement and will improve. Style, which comes from source structure, is the least certain. Report the preset name (shown at the top of the settings panel), the options you selected, the song and your device in a [GitHub issue](https://github.com/johnneerdael/ProjectM-Android/issues).

## A legacy preset looks dark or sparse

Some presets are dark by design. **BrainStain- boiling-mix2(redi jedi full carb mix)**, for example, shows only a zoomed crop of its image through video echo and then squares the colours with its darken filter, so it looks sparse even though its waveform is bright. The first frame of a preset can be black while its feedback builds up. When you report dark output, include the music and how long after the preset started you looked.

## A preset looks different from MilkDrop or another player

ProjectM TV Engine follows MilkDrop 2 closely and fixes many differences that other projectM players still have (see the [patch catalog](engine/patches.md)). A preset can still look different for these reasons:

- Random textures (`rand00`…`rand15`) choose new images every time a preset loads.
- Chaotic feedback amplifies tiny differences in timing and audio.
- A preset composed for a 4:3 aspect ratio is a different picture at 16:9.
- GPU drivers differ in edge cases, such as power functions of negative numbers.
- A shader that fails to translate falls back to a simple default. Please report these.

Negative motion zoom uses MilkDrop 2's CPU power calculation for valid integer nested exponents. Fractional negative powers still produce nonfinite coordinates, and their appearance is not guaranteed to be the same across devices. **Great Tulip Majesty (txtr wrap)** has the same invalid power domain in the original source; its tested 30-frame emulator replay is unchanged by this correction. A source predictor can decline to forecast it even while the app renders a picture.

Include the preset name, your device and the app version when you report a difference.

## Updating fails

- Production releases are signed with one permanent key. A locally built debug APK cannot replace them; uninstall first or use the [separate test build](development.md#test-on-a-tv-without-replacing-the-release).
- If Android asks whether the visualizer may install unknown apps, allow it, return, and select **Install** again.

## Custom pack upload does not open

- The uploading device and the device running the visualizer must be on the same Wi-Fi or Ethernet network. VPN interfaces are never used, and guest networks often isolate devices from each other.
- Keep the dialog open in the visualizer; closing it or leaving the app stops the upload page. Use another device to upload to the phone version.
- The dialog generates a new QR code each time it opens, so scan the current one.

For anything else, open a [GitHub issue](https://github.com/johnneerdael/ProjectM-Android/issues) with the app version, device model, Android version and a screenshot of the settings or exit report. Include TV Diagnostics lines when available.
