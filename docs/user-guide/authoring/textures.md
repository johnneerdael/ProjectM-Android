# Textures

Shaders sample images through samplers. Declaring `sampler sampler_clouds;` and calling `tex2D(sampler_clouds, uv)` makes the engine find an image named `clouds` and bind it.

## How textures are found

- In projectM, every `sampler_<name>` and every `texsize_<name>` in the warp and composite code binds a texture, whether or not it is used. MilkDrop binds only samplers the compiled shader actually uses, and `texsize_<name>` there only reports an already-loaded texture. Comments are stripped first, so a commented-out declaration binds nothing.
- File extensions searched: `.jpg`, `.dds`, `.png`, `.tga`, `.bmp`, `.dib` (projectM adds `.jpeg`). Names are matched ignoring case.
- MilkDrop searches its `textures` folder, then the preset's own folder. projectM searches its configured texture paths.
- `texsize_<name>` gives `(width, height, 1/width, 1/height)` of that image.

On ProjectM TV, bundled presets use the 74 bundled images. A [custom pack](../custom-packs.md)'s presets look in the pack first and fall back to the bundled images. Texture names must be unique within a pack, ignoring case and extension.

Each referenced image costs width × height × 4 bytes of GPU memory, used or not. `tools/gen-preset-index.py` counts this per preset to decide which presets are memory-heavy.

## Sampler names and filtering

The first three characters after `sampler_` can select filtering and edge behaviour:

| Prefix | Filtering | Edges |
|---|---|---|
| `fw_` or `wf_` | bilinear | wrap (repeat) |
| `fc_` or `cf_` | bilinear | clamp |
| `pw_` or `wp_` | nearest (point) | wrap |
| `pc_` or `cp_` | nearest | clamp |
| none | bilinear | wrap |

So `sampler_pc_main` reads the previous frame with point sampling and clamped edges, and `sampler_fw_clouds` reads `clouds` with bilinear filtering and wrapping.

!!! warning "Any two-letter prefix is stripped"
    MilkDrop removes *any* `XY_` prefix, even an unknown one, and projectM copies that rule ("Milkdrop also removes the XY_ prefix in the case nothing matches"). An image named `ab_stars.png` referenced as `sampler_ab_stars` is therefore looked up as `stars`. Don't give textures names with an underscore in the third position.

`sampler_state { … }` blocks after a declaration are accepted for compatibility, but their fields are ignored. Only the prefix selects the mode.

## Built-in textures

| Name | Contents |
|---|---|
| `main` | The previous frame (warp) or the canvas (composite) |
| `blur1`, `blur2`, `blur3` | Blurred copies, encoded: read them with `GetBlur1/2/3` |
| `noise_lq` | 256×256 random RGBA, sharp |
| `noise_lq_lite` | 32×32 random |
| `noise_mq` | 256×256, smoothed at scale 4 |
| `noise_hq` | 256×256, smoothed at scale 8 |
| `noisevol_lq` | 32×32×32 volume, for `tex3D` |
| `noisevol_hq` | 32×32×32 volume, smoothed at scale 4 |

The noise textures have MilkDrop's sizes and smoothing, but their contents are random each time the program starts. Never rely on a particular noise pattern.

## Random textures: `rand00` to `rand15`

```hlsl
sampler sampler_rand00;          // any image
sampler sampler_rand01_smalltiled; // any image whose name starts with "smalltiled"
```

`randNN` picks a random image from the texture folder. `randNN_prefix` picks one whose name starts with *prefix*. A mode prefix still applies: `sampler_pc_rand00_red` is a point-sampled, clamped image whose name starts with `red`.

MilkDrop 2 picks a file at random from its `textures` folder when it compiles each shader (`PickRandomTexture`, `plugin.cpp:2840`). The prefix match ignores case, and images in the preset's own folder are not candidates. The choice is local to each shader (`plugin.cpp:2927`), so the warp and composite shaders can receive different images for the same slot. Within one shader, each slot may be used only once.

ProjectM TV Engine instead ties the choice to the slot for the whole preset load. The warp and composite shaders see the same image for the same slot, and the choice survives shader reloads. Within one shader, aliases with a name filter fill their slots first; across the two shaders, the first stage to claim a slot wins. If you need the same image in both shaders, don't rely on either behaviour: use a fixed texture name instead.

In both, every new load of the preset makes new choices, so revisiting a preset can look different. If no image matches a prefix, nothing is bound.

ProjectM TV chooses with the system's random device, so choices are not reproducible from a seed. The evaluator's `rand()` has no influence on them. Of the bundled presets, 192 contain random sampler names.

## Transparent images

In ProjectM TV, every image is uploaded with its colour premultiplied by alpha: each channel becomes `(rgb × alpha + 128) >> 8`, and alpha keeps its value. Opaque images lose one step at the top (255 becomes 254). ProjectM TV's earlier releases, based on projectM 4.1.7, loaded images this way through SOIL2, and the current engine keeps those bytes. A fully transparent pixel therefore samples as black, whatever colour the file stored. Do not divide by alpha to recover the colour unless you handle alpha = 0.

## Named images on custom shapes

projectM (not MilkDrop 2) accepts `shapecode_N_image=<name>` on a textured shape: the shape then shows that image instead of the previous frame. The name is a texture name without extension, resolved like a sampler. If no file matches, projectM binds a 1×1 placeholder texture, *not* the previous frame, despite a source comment suggesting otherwise. MilkDrop ignores the key, so a preset that relies on it shows the previous frame there instead. No bundled preset uses it; the *Aurora Ownership* test presets do.

## Checklist

- Keep texture names lowercase-unique, without an `XY_` third-character underscore.
- Declare a sampler once and use it. Every declaration costs memory.
- Read blur through `GetBlurN`, not raw `sampler_blurN`.
- Expect `randNN` images to differ between loads; design for any image in the folder, or use a prefix.
- Bundled presets must reference only bundled textures; CI rejects a missing or excluded image.
