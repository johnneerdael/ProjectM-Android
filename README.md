# ProjectM TV

[![Android CI](https://github.com/johnneerdael/ProjectM-Android/actions/workflows/android.yml/badge.svg)](https://github.com/johnneerdael/ProjectM-Android/actions/workflows/android.yml)

ProjectM TV and ProjectM Android turn sound into MilkDrop visuals using 9,606 presets from Jason Fletcher's *Cream of the Crop* collection. **ProjectM TV** listens to a music app on your Android TV or Google TV. **ProjectM Android** runs on touchscreen phones and tablets and uses microphone input or music played locally by another app. Both render in landscape and use the same engine; neither is a music player.

GitHub editions bundle the complete collection. The smaller F-Droid editions start offline with **20 curated presets** and offer an optional, verified download of the full collection.

It runs **ProjectM TV Engine**: [projectM](https://github.com/projectM-visualizer/projectm), the open-source reimplementation of Winamp's MilkDrop, based on unreleased projectM 4.2 master (commit `6f6480746`) plus 35 ordered patches. The patches restore MilkDrop 2's behaviour where projectM differs, keep presets at their authored scale on 4K screens, and make preset changes smooth on TV hardware.

> **Install on your TV with the Downloader app: code `4821216`**
>
> Install *Downloader* by AFTVnews on the TV, open it, enter **4821216** and install the APK it downloads. The code always points to the newest stable release. Details under [Install](#install).

> **Install on your phone or tablet with the Downloader app: code `6565691`**
>
> Install [Downloader by AFTVnews from Google Play](https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en), open it, enter **6565691** and install ProjectM Android. The code points to the newest stable touchscreen APK.

<p align="center">
  <img src="docs/user-guide/images/launch.jpg" alt="ProjectM TV showing a preset, with the playing track's cover, artist and title in the upper left" width="100%">
</p>
<p align="center">
  <img src="docs/user-guide/images/gallery/chill-2.jpg" alt="A calm blue particle preset (Chill)" width="32%">
  <img src="docs/user-guide/images/gallery/normal-2.jpg" alt="A geometric yellow preset (Normal)" width="32%">
  <img src="docs/user-guide/images/gallery/intense-3.jpg" alt="A busy, colourful preset (Intense)" width="32%">
</p>

## User guide

**[johnneerdael.github.io/ProjectM-Android](https://johnneerdael.github.io/ProjectM-Android/)** covers:

- **Using the app:** installation on TV or phones, remote and touchscreen controls, audio input, every setting, [preset moods](https://johnneerdael.github.io/ProjectM-Android/predictive-collections/), custom packs, picture quality and troubleshooting.
- **[ProjectM TV Engine](https://johnneerdael.github.io/ProjectM-Android/engine/):** the patch catalog with before/after proof images and measured benefits, how 4K rendering keeps the authored look (including the resolution-scaling part of [projectM #682](https://github.com/projectM-visualizer/projectm/issues/682)), and how a frame reaches the TV.
- **[Writing presets](https://johnneerdael.github.io/ProjectM-Android/authoring/):** a source-level guide to how `.milk` presets execute, drawn from MilkDrop 2's code and the analysis of thousands of presets.

## Highlights

- **9,606 MilkDrop presets** with smooth blends, shuffled within the mood you choose.
- **Preset moods (beta):** **All**, **Chill**, **Normal** and **Intense**, from a measured activity score; [predicting presets from their source](https://johnneerdael.github.io/ProjectM-Android/predictor/) is in development.
- **Presets that work as on MilkDrop 2:** equation code MilkDrop tolerated, HLSL its compiler accepted, Direct3D pixel and texel rules, live per-frame waveform and display controls, legacy colour shading and spirals, huge rotations and negative zoom. [Patch catalog](https://johnneerdael.github.io/ProjectM-Android/engine/patches/).
- **4K without the darkness:** lines, blur and texel steps scale with resolution; Native trails keeps feedback at an authored-scale canvas with sharp native geometry on top.
- **No freezes at preset changes:** upcoming presets are compiled in the background.
- **Adaptive quality:** resolution follows the target frame rate and live memory headroom, up to the panel's native size.
- **Track titles:** cover, artist and title of the playing track, from the music app's media session.
- **Custom preset packs:** upload up to 50,000 presets and textures from a phone by scanning a QR code.
- **Private:** audio is analysed in memory only. GitHub app updates can be switched off; F-Droid collection downloads require your choice. Custom uploads use a temporary local page.
- **Remote and touchscreen controls** with a settings panel and live status.

## Remote control

| Key | Action |
|---|---|
| Right, Next, Fast forward | Random preset (instant cut) |
| Left, Previous, Rewind | Previous preset (instant cut) |
| Up, Down, Info | Show the current track again (with notification access) |
| Center, Enter, Menu | Open the settings panel |
| Back | Exit the app |

In the panel, Up and Down move between rows, Left and Right change a value, and Center cycles a value or runs an action. Back closes the panel (from *Advanced* or *Track display* it returns to the main panel), Menu closes it, and it hides itself after 10 seconds without input.

## Touchscreen controls

In ProjectM Android, swipe right for a random preset and left for the previous preset, matching the remote's Right/Left actions. Switches are instant cuts. Tap the visuals to open the menu; tap a row to cycle its value or run its action. Scroll vertically to reach every setting, including Advanced and Track display. Use **Back to menu**, **Close menu**, or tap outside the panel. Touch input restarts the 10-second menu timeout.

## Settings

<p align="center">
  <img src="docs/user-guide/images/setup/main-settings.jpg" alt="The main settings panel next to the playing track" width="32%">
  <img src="docs/user-guide/images/setup/track-display-settings.jpg" alt="The track display panel" width="32%">
  <img src="docs/user-guide/images/setup/advanced-settings.jpg" alt="The advanced settings panel with diagnostics" width="32%">
</p>

| Setting | Values | Default |
|---|---|---|
| Audio input (Android only) | Microphone; Phone playback (Android 10+, consent required) | Microphone |
| Auto change | Off, On | On |
| Preset mood | All, Chill, Normal, Intense, Custom (after upload) | All; Custom after an upload |
| Preset duration | 10, 15, 20, 30, 45, 60, 90 s | 30 s |

*Track display ›*

| Setting | What it does | Default |
|---|---|---|
| Track info | Cover, artist and title in the upper left; *Off · Allow* while notification access is missing | On |
| Show for | 10, 20, 30 or 60 s from the start of each track, or *Always* while music plays | Always |
| Pill style | One line (*Title — Artist*) in the lower-left pill instead | Off |

*Advanced ›*

| Setting | What it does | Default |
|---|---|---|
| Resolution | Auto; fixed 720p, 1080p, 1440p, 4K up to the panel; Native. Memory protection stays active | Auto |
| Frame rate | The refresh rate, half or a quarter of it, at least 24 fps | About 30 fps (30 at 60 Hz, 25 at 50 Hz) |
| Detail | Warp mesh: Minimal, Low, Medium, High, Ultra | High on SHIELD/Tegra, Low on low-RAM devices, otherwise Medium |
| Native trails | Standard, Medium, High; active above 1330p | Standard |
| Transition | Instant, 1–10 s | 7 s (2 s on low-RAM devices) |
| Transitions | Auto, Lightweight, Classic | Auto |
| Cut on loud beats | Lets projectM cut to the next preset on a loud beat | Off |
| Skip slow presets | In Auto resolution, skips presets that cannot reach half the target frame rate | On |
| Skip blank presets | Moves on from presets that stay black while music plays; skips them for good the second time | On |
| Auto-update | GitHub editions check for new stable releases; F-Droid editions update through F-Droid | On for GitHub; preserves an explicit Off |
| Cream of the Crop (F-Droid only) | Download or remove the full collection; custom packs stay separate | 20 starters |
| Custom preset pack | Upload one ZIP from a phone or computer on the same network | No pack |
| Skipped presets | Count of skipped presets; select to reset | – |
| Background compile | Prepares upcoming presets' shaders on a second thread; *Off* compiles at the switch (longer pause). Troubleshooting only | On |
| Shader binary cache | Reuses compiled shaders as driver binaries; *Off* always compiles from source. Troubleshooting only | On |
| Last exit | Why the app last closed while on screen (Android 11+); select for recent exits and what the engine was doing | – |

On TV, opening *Advanced* also shows a **Diagnostics** card: render size, memory status, panel and UI size, frame rate, Native trails state, blend, audio source and level, track display, update status, device tier and GPU. The [settings reference](https://johnneerdael.github.io/ProjectM-Android/settings/) explains every value.

## Requirements and limits

- Android TV or Google TV for the TV APK; a touchscreen phone or tablet for the Android APK. Both require Android 5.0 (API 21) or later and OpenGL ES 3.0; visuals stay in landscape.
- At least 2 GB of RAM is highly recommended.
- **TV audio:** a music app playing on the same TV. Spotify, SoundCloud, SmartTube and [Milkbeat](https://github.com/johnneerdael/Milkbeat) have been verified on TV. The TV build has no microphone or line-in input; already Dolby-encoded audio cannot be visualized.
- **Phone audio:** microphone input works independently of a music app. Phone playback capture needs Android 10+, Android's consent and a player that allows capture and keeps playing in the background. The TV player list does not certify phone compatibility. Both builds feed the engine 8-bit mono audio.
- Preset moods are a beta prediction from one short measurement per preset; they will be improved. Chill is not a guarantee of no flashing.
- Some presets still look different from MilkDrop on Windows: random textures change per load, chaotic presets diverge, and GPU drivers differ in undefined arithmetic. Negative warp zoom follows MilkDrop 2’s CPU power calculation for valid integer nested exponents; fractional negative powers still have nonfinite coordinates with no portable appearance guarantee.
- 189 of the 9,795 *Cream of the Crop* presets are not included: 116 cannot react to music, 73 use images with text, logos or people (one is in both groups), and 1 has a missing texture.

## Permissions

| Permission | Why | When |
|---|---|---|
| Record audio | TV: the player's audio session. Android: microphone input or approved phone playback capture | First launch |
| Internet | GitHub app updates, an explicitly requested F-Droid collection download, and the local custom-pack upload page | Granted at install |
| Install apps (GitHub only) | Hands a downloaded app update to Android's installer | The first time you install an update |
| Notification access | Only to read the music app's media session for track titles; no notifications are read | Optional, via *Track display › Track info* |

Nothing the app hears or reads leaves the device.

## Install

**On the TV, with Downloader**

1. Install *Downloader* by AFTVnews from the TV's app store and allow it to install apps.
2. Open Downloader, enter **4821216** and confirm the installation.

The code links to https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-TV.apk. Every version is under [Releases](https://github.com/johnneerdael/ProjectM-Android/releases).

**On a phone or tablet, with Downloader**

1. Install [Downloader by AFTVnews from Google Play](https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en).
2. Open Downloader and enter **6565691**.
3. Allow Downloader to install apps when Android asks, then confirm installation of **ProjectM Android**.

You can also download the [touchscreen Android APK directly](https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-Android.apk). The stable filenames are `projectM-TV.apk` for TV and `projectM-Android.apk` for phones/tablets. The two apps have separate app IDs and settings; auto-update selects the matching APK.

**F-Droid editions**

| Device | Stable APK | Presets | App updates |
|---|---|---|---|
| TV | `projectM-TV-FDroid.apk` | 20 starters; optional full collection | F-Droid |
| Phone/tablet | `projectM-Android-FDroid.apk` | 20 starters; optional full collection | F-Droid |

These APKs are separate release artifacts. F-Droid listings remain subject to its maintainers' acceptance. On first launch, choose **Download (recommended)** or **Use 20 starters**. Reopen **Advanced › Cream of the Crop** to download or remove it later. The download is 38.7 MiB, with 129.5 MiB of unpacked collection contents; allow at least 184.2 MiB of free storage during installation. After installation the collection works offline. Downloading requires the app to stay in the foreground. Custom packs survive collection removal. [Setup and updates](https://johnneerdael.github.io/ProjectM-Android/getting-started/).

**From a computer**

```bash
curl -LO https://github.com/johnneerdael/ProjectM-Android/releases/latest/download/projectM-TV.apk
adb install -r projectM-TV.apk
```

Start music on the TV, open ProjectM TV and allow audio recording. On phones, choose **Audio input** in the menu: **Microphone** (default) or **Phone playback**. Playback capture requires Android 10+, Android's capture consent each session, and a player that permits capture; protected or opted-out audio is silent. Capture stops when the visualizer leaves the foreground. The [getting-started guide](https://johnneerdael.github.io/ProjectM-Android/getting-started/) walks through permissions and track titles with screenshots. Releases are signed with one permanent key; a build signed with your own debug key must be uninstalled before installing a release.

<a id="track-titles"></a>For troubleshooting audio, track titles, stutter and black presets, see the [troubleshooting guide](https://johnneerdael.github.io/ProjectM-Android/troubleshooting/).

## For developers

```bash
git clone --recurse-submodules https://github.com/johnneerdael/ProjectM-Android.git
./gradlew assembleRelease                    # APK + core AAR (signed with your local debug key)
./gradlew :app:assembleRelease -PandroidTouchscreen=true # touchscreen APK (same output path)
./gradlew :app:assembleFdroidTvRelease -PprojectmDistribution=fdroid
./gradlew :app:assembleFdroidAndroidRelease -PprojectmDistribution=fdroid -PandroidTouchscreen=true
./gradlew testDebugUnitTest                  # JVM tests
core/src/test/native/run_native_tests.sh     # native engine and projectM regression controls
```

- **Engine:** the `:core` module builds projectM from the submodule `third_party/projectm`, pinned to `6f64807467e312034883a4389e6aa80a675458bc`, and applies [`tools/projectm-patches/`](tools/projectm-patches) at configure time. Never edit the submodule; add a patch. CMake reports `4.2.0`, but upstream has not released this snapshot as 4.2. `ProjectMJNI.getVersion()` reports that upstream number; identify a build by release version, source revision and artifact checksum.
- **Core library:** each release publishes `projectM-TV-core-<version>.aar` (and the alias `projectM-TV-core.aar`), which [Milkbeat](https://github.com/johnneerdael/Milkbeat) consumes.
- **F-Droid:** [recipe and synchronization tooling](tools/fdroid/README.md) uses the same source/version for both devices. The canonical core AAR keeps all 9,606 presets and 74 textures.
- **Contributing:** pull requests to `main` run the full build after a completed review of their latest commit. Each tested merge publishes a new version automatically, with release notes from the PR's `## Release notes` section.

Further reading: [build and test guide](https://johnneerdael.github.io/ProjectM-Android/development/), [architecture](docs/ARCHITECTURE.md), [patch assessment](docs/UPSTREAM_PATCH_VALUE.md), [releasing](docs/RELEASING.md), [diagnostics](docs/DIAGNOSTICS.md), [profiling](docs/PROFILING.md).

## Credits and third-party content

- [projectM](https://github.com/projectM-visualizer/projectm), the visualization engine (LGPL 2.1), including this project's [shader remainder and precedence fix](https://github.com/projectM-visualizer/projectm/pull/1031) merged upstream
- *Cream of the Crop* presets, curated by Jason Fletcher (ISOSCELES), via [presets-cream-of-the-crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop)
- The MilkDrop texture pack, and textures from the community *MilkDrop 135k+ Presets MegaPack* collected by Incubo_
- The authors of the MilkDrop presets

Sources and licences are listed in [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

## License

The app's own code is licensed under the GNU Lesser General Public License, version 2.1; see [LICENSE](LICENSE). This matches projectM.

The bundled presets and textures are distributed under CC0 1.0 ([LICENSES/CC0-1.0.txt](LICENSES/CC0-1.0.txt)): free for any use. The presets and textures themselves were freely released by their authors; authors who want their work removed can open an issue. Details in [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).
