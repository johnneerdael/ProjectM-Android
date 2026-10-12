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

If no player is found, the app retries after the next track change (with notification access) and otherwise once a minute. Audio that a video app sends to the TV already **Dolby-encoded** never passes through Android's mixer and cannot be visualized. [Why the app listens to the player's session](engine/pipeline.md#audio-listening-to-the-player-not-the-room).

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

Capture stopping when you open another app or lock the device is expected. Microphone resumes on return; Phone playback requires new consent. Notification access enables track titles and does not grant playback capture. [Phone setup](getting-started.md#touchscreen-phone-or-tablet).

## Track titles are missing

Open **Track display › Track info**. If it reads *Off · Allow*, select it and choose **Configure**, then enable the installed app (ProjectM TV or ProjectM Android) in Android's notification access ([walkthrough](getting-started.md#track-titles-optional)). **Dismiss** only hides the automatic reminder.

If the title shows but not the cover, the music app may not provide artwork. On TV, covers are verified with Spotify and Milkbeat; SoundCloud and SmartTube provide title and artist only.

## The picture stutters

1. Keep **Advanced › Resolution** on **Auto**. Fixed sizes and Native ignore frame rate.
2. Lower **Detail** if the preset's equations are CPU-heavy; resolution does not help those.
3. On a 4K panel keep **Native trails** on **Standard**.
4. If stutter happens only during changes, set **Transitions** to **Lightweight**.

The main panel shows frame rate and render size on both builds; TV Diagnostics adds memory state. More in [Picture quality and performance](picture-quality.md#when-playback-stutters).

## The render size is lower than my TV

Auto lowers resolution to hold the target frame rate and to keep memory free for the music app; TV Diagnostics shows *resolution reduced for memory headroom* when memory is the reason. To test a preset at full size, choose **Advanced › Resolution › Native**. Memory protection still applies. Android often runs its menus at 1080p on a 4K TV; Diagnostics lists **Panel** (the physical display) separately from **UI**.

## The app closes at preset changes

If the visualizer closes by itself, often when one preset changes into the next, while the music keeps playing:

1. Open the app again and check **Advanced › Last exit**. Select it for the [exit report](settings.md#exit-report): *crashed (native code)* or *killed by signal* points to the graphics driver or the engine, *killed for low memory* to memory.
2. Try **Advanced › Transitions › Lightweight**, then **Classic**. If only Auto blends crash, the lower blend resolution is involved.
3. Turn **Advanced › Shader binary cache** **Off**. If the crashes stop, the GPU driver cannot reuse program binaries between OpenGL contexts.
4. If they continue, also turn **Advanced › Background compile** **Off**. Switches then pause the picture while each preset compiles, often for a second or two. If the crashes stop only now, the driver fails when two threads compile at once.
5. Report the result with a photo of the exit report, the device model and which switches you changed. Turn the switches back **On** afterwards if they made no difference.

These switches exist to diagnose crashes first reported on a Fire TV Stick 4K Max (2nd gen, PowerVR GE9215 GPU). Leave them **On** otherwise.

## Native trails says inactive or fallback

Native trails works only above 1330p. On a 1080p TV, Diagnostics shows *inactive (render 1080p)*, which is expected. *Canvas fallback* usually means no supported whole-number authored canvas exists at this render size; *shader/resource fallback* means the GPU driver rejected the trails shaders. In both cases the standard renderer is used. Please report the Diagnostics text and your TV model.

## A preset is black, frozen or skipped

- Some presets build up slowly from black. Give them a few seconds of music.
- With **Skip blank presets** on, a preset that stays black while music plays is passed over, and skipped permanently the second time.
- With **Skip slow presets** on (Auto resolution only), a preset that cannot reach half the target frame rate even at the lowest resolution is skipped permanently.
- Presets that cannot be read or parsed are skipped too.

**Advanced › Skipped presets** shows the count; select it to reset the list. Presets that still fail are skipped again.

## My mix has fewer presets than expected

F-Droid editions start with 20 presets, so Mood counts are small. Open **Advanced › Cream of the Crop** to download the complete library. [Collection setup](getting-started.md#optional-collection-in-f-droid-editions).

The Mood panel counts only presets this device can play, so skipped presets reduce it. Options that would leave no presets are dimmed. If every match in your mix is skipped, the header reads *No presets left in your mix; playing All*. Custom-pack presets are not played while an option is active; choose *Custom* in the Collection row. A full-collection download made before attributes existed offers only the Collection choice; download it again. See [Preset moods](predictive-collections.md).

## The collection download failed or disappeared

Keep the visualizer open while downloading. Leaving during download/preparation cancels it; retry from **Advanced › Cream of the Crop**. Allow at least 184.2 MiB free during installation. The archive is fetched from GitHub, so a network block or unavailable release can prevent downloading; the 20 starters remain usable offline.

An incomplete or corrupted collection is rejected. After a restart, missing or changed installed files cause the app to use the starters. Download it again from the same setting. Removing the collection keeps your custom pack. Clearing app data, reinstalling or restoring on another device requires downloading again.

## A mood feels wrong

Mood attributes are predictions from a short measurement (Style, from source structure, is the least certain) and will improve. Report the preset name (shown at the top of the settings panel), the options you selected, the song and your device in a [GitHub issue](https://github.com/johnneerdael/ProjectM-Android/issues).

## A legacy preset looks dark or sparse

Some presets are dark by design. For example, **BrainStain- boiling-mix2(redi jedi full carb mix)** shows only a zoomed crop of its image through video echo and then squares the colours with its darken filter, so it looks sparse even though its waveform is bright. The first frame of a preset can be black while its feedback builds up. When you report dark output, include the music and how long after the preset started you looked.

## A preset looks different from MilkDrop or another player

ProjectM TV Engine follows MilkDrop 2 closely and fixes many differences that other projectM players still have; see the [patch catalog](engine/patches.md). Remaining reasons a preset can look different:

- **Random textures** (`rand00`…`rand15`) choose new images every time a preset loads.
- **Chaotic feedback** amplifies tiny differences in timing and audio.
- **Aspect ratio**: a preset composed for 4:3 is a different picture at 16:9.
- **GPU drivers** differ in edge cases, such as power functions of negative numbers.
- A shader that fails to translate falls back to a simple default. Please report these.

Negative motion zoom uses MilkDrop 2's CPU power calculation for valid integer nested exponents. Fractional negative powers still produce nonfinite coordinates with no portable appearance guarantee. **Great Tulip Majesty (txtr wrap)** has the same invalid power domain in the original source; its tested 30-frame emulator replay is unchanged by this correction. A source predictor can decline to forecast it even while the app renders a picture.

Include the preset name, your device and the app version when you report a difference.

## Updating fails

- Production releases are signed with one permanent key. A locally built debug APK cannot replace them; uninstall first or use the [separate test build](development.md#test-on-a-tv-without-replacing-the-release).
- If Android asks whether the visualizer may install unknown apps, allow it, return, and select **Install** again.

## Custom pack upload does not open

- The uploading device and the device running the visualizer must be on the same Wi-Fi or Ethernet network. VPN interfaces are never used, and guest networks often isolate devices.
- Keep the dialog open in the visualizer; closing it or leaving the app stops the upload page. Use another device to upload to the phone version.
- A new QR code is generated each time the dialog opens. Scan the current one.

For anything else, open a [GitHub issue](https://github.com/johnneerdael/ProjectM-Android/issues) with the app version, device model, Android version and a screenshot of the settings or exit report. Include TV Diagnostics lines when available.
