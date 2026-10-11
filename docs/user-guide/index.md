---
title: ProjectM TV
hide:
  - navigation
  - toc
---

<div class="pm-hero" markdown>
![A ProjectM TV preset with the playing track's cover, artist and title](images/launch.jpg)
<div class="pm-hero__text" markdown>
# ProjectM TV
MilkDrop visuals for the music on your Android TV, up to 4K, with 9,606 presets and an engine tuned to behave like the original MilkDrop 2.

[Get started](getting-started.md){ .md-button .md-button--primary } [Write presets](authoring/index.md){ .md-button } [Explore the engine](engine/index.md){ .md-button }
</div>
</div>

<div class="pm-download" markdown>
**Install on your TV with the Downloader app: code `4821216`**. Install *Downloader* by AFTVnews, enter the code and confirm. [More install options](getting-started.md#install-on-the-tv).
</div>

## Use it

<div class="grid cards" markdown>

-   :material-television-play:{ .lg .middle } **Install and get started**

    ---

    Permissions, track titles and good first settings, with screenshots.

    [:octicons-arrow-right-24: Get started](getting-started.md)

-   :material-remote-tv:{ .lg .middle } **Remote and settings**

    ---

    Every key and every setting, including the live Diagnostics card.

    [:octicons-arrow-right-24: Controls](controls.md) · [Settings](settings.md)

-   :material-palette-swatch-variant:{ .lg .middle } **Preset moods** *(beta)*

    ---

    Chill, Normal and Intense, from a measured activity score, with example captures.

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

ProjectM TV listens to the music app's own audio session. The separate [ProjectM Android touchscreen build](getting-started.md#install-on-a-phone-or-tablet) supports microphone input and consented phone playback capture. Neither stores audio, and only goes online if you turn on auto-update.

## What makes it different

<div class="grid cards pm-two" markdown>

-   :material-check-decagram:{ .lg .middle } **Presets that work**

    ---

    Most of the fourteen engine patches restore MilkDrop 2's behaviour where projectM differs: tolerant equation loading, HLSL its compiler accepted, and Direct3D pixel rules. Each comes with before/after proof.

    [:octicons-arrow-right-24: Patch catalog](engine/patches.md)

-   :material-monitor-screenshot:{ .lg .middle } **4K without the darkness**

    ---

    Lines, blur and texel steps keep their authored size, and feedback runs on an authored-scale canvas with sharp native geometry on top. This addresses the resolution-scaling part of projectM issue #682.

    [:octicons-arrow-right-24: Rendering at 4K](engine/resolution.md)

-   :material-chip:{ .lg .middle } **Built for a TV box**

    ---

    Background shader compilation, resolution that follows frame rate and free memory, and blends that adapt to the GPU or CPU limit.

    [:octicons-arrow-right-24: Frame pipeline](engine/pipeline.md)

-   :material-function-variant:{ .lg .middle } **Understood from source**

    ---

    In a research audit, predictions made from preset code alone scored 95 or more out of 100, on 20 observable claims, for 85 of 100 randomly chosen presets.

    [:octicons-arrow-right-24: The road ahead](predictor.md)

</div>

## Write presets

A source-level guide to how `.milk` presets really execute, built from MilkDrop 2's code and the analysis of thousands of real presets: [file format](authoring/milk-format.md), [frame order](authoring/execution.md), [equations](authoring/equations.md), [shaders](authoring/shaders.md), [textures](authoring/textures.md), [effects](authoring/effects.md), [testing and prediction](authoring/testing.md) and a [checklist](authoring/checklist.md) of mistakes found in real presets.

[:octicons-arrow-right-24: Start writing presets](authoring/index.md){ .md-button }

---

ProjectM TV is open source (LGPL-2.1), and its presets and textures are CC0. Its engine also powers **[Milkbeat](https://github.com/johnneerdael/Milkbeat)**, a music player for Android TV by the same author. [Project on GitHub](https://github.com/johnneerdael/ProjectM-TV) · [Releases](https://github.com/johnneerdael/ProjectM-TV/releases) · [Report an issue](https://github.com/johnneerdael/ProjectM-TV/issues) · [Build and test](development.md)
