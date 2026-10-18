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
MilkDrop visuals on your TV, phone or tablet, with 9,606 presets and the same ProjectM TV Engine on every device. On the TV the visuals follow a music app; on touchscreen Android you choose microphone input or phone playback.

GitHub editions include the full collection. F-Droid editions start with **20 curated presets** and offer the full collection as an optional download. [Choose your edition](getting-started.md#choose-an-edition). **[ProjectM Android is now on F-Droid](https://f-droid.org/en/packages/nl.neerdael.projectm/)** for phones and tablets.

**PowerVR crashes are fixed in 2.3.56+.** The reporter confirms the fix on Fire TV Stick 4K Max (2nd generation); it applies automatically to all supported Imagination/PowerVR GPUs. See [affected device families and upgrade instructions](troubleshooting.md#powervr-framebuffer-crashes-fixed-in-2356).

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

    Swipe and tap on phones, or use the remote on TV. Every setting is described, including phone audio input and TV diagnostics.

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

    What to check when visuals ignore the music, titles are missing, the picture stutters or a preset stays black.

    [:octicons-arrow-right-24: Troubleshooting](troubleshooting.md)

</div>

ProjectM TV listens to the music app's own audio session. [ProjectM Android](getting-started.md#install-on-a-phone-or-tablet) supports microphone input and phone playback capture with your consent. Neither app stores audio. They use the network for GitHub app updates when enabled, for optional F-Droid collection downloads when you request them, and for the temporary local custom-pack upload page.

## What makes it different

<div class="grid cards pm-two" markdown>

-   :material-check-decagram:{ .lg .middle } **Presets that work**

    ---

    Where projectM differs from MilkDrop 2, the maintained engine patches restore MilkDrop 2's behaviour: its tolerant equation loading, the HLSL its compiler accepted and its Direct3D pixel rules. The catalog links each change to its visual evidence.

    [:octicons-arrow-right-24: Patch catalog](engine/patches.md)

-   :material-monitor-screenshot:{ .lg .middle } **4K without the darkness**

    ---

    Lines, blur and texel steps keep their authored size, and feedback runs on an authored-scale canvas with sharp native geometry drawn on top. This addresses the resolution-scaling part of projectM issue #682.

    [:octicons-arrow-right-24: Rendering at 4K](engine/resolution.md)

-   :material-chip:{ .lg .middle } **Adaptive quality**

    ---

    Shaders compile in the background, resolution follows frame rate and free memory, and blends adapt to whichever of the GPU or CPU is the limit.

    [:octicons-arrow-right-24: Frame pipeline](engine/pipeline.md)

-   :material-function-variant:{ .lg .middle } **Understood from source**

    ---

    Every preset mood is worked out from the preset's source code without rendering it. The feedback, colour and motion mathematics is checked against real renders, including chaotic presets predicted frame for frame.

    [:octicons-arrow-right-24: How it works](predictor.md) · [Predictions vs renders](predictor/gallery.md)

</div>

## Write presets

The authoring guide explains how `.milk` presets actually execute, based on MilkDrop 2's code and an analysis of thousands of real presets. It covers the [file format](authoring/milk-format.md), [frame order](authoring/execution.md), [equations](authoring/equations.md), [shaders](authoring/shaders.md), [textures](authoring/textures.md), [effects](authoring/effects.md), [testing and prediction](authoring/testing.md) and ends with a [checklist](authoring/checklist.md) of mistakes found in real presets.

[:octicons-arrow-right-24: Start writing presets](authoring/index.md){ .md-button }

---

ProjectM TV is open source (LGPL-2.1), and its presets and textures are CC0. Its engine also powers [Milkbeat](https://github.com/johnneerdael/Milkbeat), a music player for Android TV by the same author. [Project on GitHub](https://github.com/johnneerdael/ProjectM-Android) · [Releases](https://github.com/johnneerdael/ProjectM-Android/releases) · [Report an issue](https://github.com/johnneerdael/ProjectM-Android/issues) · [Build and test](development.md)
