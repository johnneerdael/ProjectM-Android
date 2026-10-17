# Renderer line refactor

The Android engine port is based on ProjectM Android `09da40d1`, pinned projectM `6f64807467e312034883a4389e6aa80a675458bc`, evaluator `22fb0cfd8f2dfbcd2b68f2443e7f44e19b32c09a` and unchanged patches0001–0036. Patch0037 adapts upstream proposal [projectM-visualizer/projectm#1047](https://github.com/projectM-visualizer/projectm/pull/1047) at `ba122baa24cd1794c2a413ec8e308c8ab6e9e4fe`.

## Scope

Move generic colored points, padded batching, line drawing and line shader resources into Renderer. Extend Mesh to own/update streamed interleaved instance data, configure attributes/divisors/strip offsets and draw independent vertex/instance counts. Use Mesh for line strips and motion-vector quads. Retain the existing indexed draw path and keep MilkDrop sizing/sample/fade/dot/canvas/thick-pass policy in MilkdropPreset.

The TV engine retains constructor/prewarm shader compilation, uniform-location caching, per-instance shape styles, Native-trails prepared-geometry replay, packed/floating motion-UV sampling and shader-failure fallback. The generic shader source bytes are unchanged.

## Validation

Validation is in progress. This file will record observed results and backend limits before the PR is opened. Existing historical image, corpus and timing evidence is preserved.
