---
title: ProjectM TV and Android
hide:
  - navigation
  - toc
---

<div class="pm-hero" markdown>
![A ProjectM TV preset with the playing track's cover, artist and title](images/launch.jpg)
<div class="pm-hero__text" markdown>
# ProjectM TV and Android
MilkDrop visuals on your TV, phone or tablet, with 9,606 presets and the same ProjectM TV Engine. Use a music app on the TV, or choose microphone input or phone playback on touchscreen Android.

GitHub editions include the full collection. F-Droid editions start with **20 curated presets** and offer the full collection as an optional download. [Choose your edition](getting-started.md#choose-an-edition).

[Get started](getting-started.md){ .md-button .md-button--primary } [Write presets](authoring/index.md){ .md-button } [Explore the engine](engine/index.md){ .md-button }
</div>
</div>

<div class="pm-download" markdown>
**Install on your TV with the Downloader app: code `4821216`**. Install *Downloader* by AFTVnews, enter the code and confirm. [More install options](getting-started.md#install-on-the-tv).

**Phone or tablet: code `6565691`**. Get [Downloader by AFTVnews from Google Play](https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en), enter the code and install ProjectM Android. [Phone setup](getting-started.md#install-on-a-phone-or-tablet).
</div>

## Use it

<div class="grid cards" markdown>

-   :material-television-play:{ .lg .middle } **Install and get started**

    ---

    Choose the right APK, install with Downloader, and set up audio and track titles.

    [:octicons-arrow-right-24: Get started](getting-started.md)

-   :material-remote-tv:{ .lg .middle } **Touchscreen, remote and settings**

    ---

    Swipe and tap on phones; use the remote on TV. All settings, including phone audio input and TV diagnostics.

    [:octicons-arrow-right-24: Controls](controls.md) · [Settings](settings.md)

-   :material-palette-swatch-variant:{ .lg .middle } **Preset moods**

    ---

    Combine Energy, Brightness, Colour, Palette, Main colour, Movement, Style and Comfort options with live preset counts, all predicted from each preset's source.

    [:octicons-arrow-right-24: Moods](predictive-collections.md)

-   :material-folder-zip:{ .lg .middle } **Custom preset packs**

    ---

    Upload up to 50,000 of your own presets from a phone by scanning a QR code.

    [:octicons-arrow-right-24: Custom packs](custom-packs.md)

-   :material-high-definition-box:{ .lg .middle } **Picture quality**

    ---

    Auto resolution up to 4K, Native trails, transitions and device tiers.

    [:octicons-arrow-right-24: Picture quality](picture-quality.md)

-   :material-lifebuoy:{ .lg .middle } **Troubleshooting**

    ---

    No reaction to music, missing titles, stutter, black presets.

    [:octicons-arrow-right-24: Troubleshooting](troubleshooting.md)

</div>

ProjectM TV listens to the music app's own audio session. [ProjectM Android](getting-started.md#install-on-a-phone-or-tablet) supports microphone input and consented phone playback capture. Neither stores audio. Network use covers GitHub app updates when enabled, optional F-Droid collection downloads when requested, and the temporary local custom-pack upload page.

## What makes it different

<div class="grid cards pm-two" markdown>

-   :material-check-decagram:{ .lg .middle } **Presets that work**

    ---

    The maintained engine patches restore MilkDrop 2's behaviour where projectM differs: tolerant equation loading, HLSL its compiler accepted, and Direct3D pixel rules. The catalog links the changes to their visual evidence.

    [:octicons-arrow-right-24: Patch catalog](engine/patches.md)

-   :material-monitor-screenshot:{ .lg .middle } **4K without the darkness**

    ---

    Lines, blur and texel steps keep their authored size, and feedback runs on an authored-scale canvas with sharp native geometry on top. This addresses the resolution-scaling part of projectM issue #682.

    [:octicons-arrow-right-24: Rendering at 4K](engine/resolution.md)

-   :material-chip:{ .lg .middle } **Adaptive quality**

    ---

    Background shader compilation, resolution that follows frame rate and free memory, and blends that adapt to the GPU or CPU limit.

    [:octicons-arrow-right-24: Frame pipeline](engine/pipeline.md)

-   :material-function-variant:{ .lg .middle } **Understood from source**

    ---

    Every preset mood is worked out from the preset's source code, without rendering it: feedback, colour and motion mathematics checked against real renders, including chaotic presets predicted frame for frame.

    [:octicons-arrow-right-24: How it works](predictor.md) · [Predictions vs renders](predictor/gallery.md)

</div>

## Write presets

A source-level guide to how `.milk` presets really execute, built from MilkDrop 2's code and the analysis of thousands of real presets: [file format](authoring/milk-format.md), [frame order](authoring/execution.md), [equations](authoring/equations.md), [shaders](authoring/shaders.md), [textures](authoring/textures.md), [effects](authoring/effects.md), [testing and prediction](authoring/testing.md) and a [checklist](authoring/checklist.md) of mistakes found in real presets.

[:octicons-arrow-right-24: Start writing presets](authoring/index.md){ .md-button }

---

ProjectM TV is open source (LGPL-2.1), and its presets and textures are CC0. Its engine also powers **[Milkbeat](https://github.com/johnneerdael/Milkbeat)**, a music player for Android TV by the same author. [Project on GitHub](https://github.com/johnneerdael/ProjectM-Android) · [Releases](https://github.com/johnneerdael/ProjectM-Android/releases) · [Report an issue](https://github.com/johnneerdael/ProjectM-Android/issues) · [Build and test](development.md)
