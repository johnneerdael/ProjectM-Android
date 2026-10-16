# Custom preset packs

Upload your own MilkDrop presets and textures to either visualizer from another device on the same network. No file picker, USB stick or storage permission is needed.

In F-Droid editions, your custom pack is separate from the optional Cream of the Crop download. Downloading or removing that collection leaves Custom available. All combines Custom with the currently available starter or full library; the Mood options use that library's measured attributes.

## Upload a pack

1. Put your `.milk` files and any texture images in one ZIP. Folders inside the ZIP are fine.
2. On the device running the visualizer, open **Settings › Advanced › Custom preset pack**. A QR code appears.
3. Scan it with another phone on the same Wi-Fi or Ethernet network. The browser opens an **Upload preset pack** page.
4. Choose the ZIP and select **Upload ZIP**. Keep the visualizer's dialog open while it imports; it shows *Importing: N presets…*.
5. When it finishes, the visualizer shows *Imported N presets and M textures. Custom is now selected.*

![Custom preset pack dialog with its QR code over the Advanced panel](images/setup/custom-pack-upload.jpg)

![Browser upload page after importing a two-preset ZIP, at a 390 px phone viewport](images/setup/custom-pack-browser.png)

*The QR code in the capture is an example and no longer active; scan the code the visualizer shows.*

On a phone or tablet, use a second device for the upload. Switching from the visualizer to a browser on the same phone pauses the app and closes its upload listener.

## What gets imported

| Item | Limit |
|---|---|
| Presets | Up to **50,000** `.milk` files (any case, nested folders), 8 MiB each |
| Textures | Up to 5,000 images: PNG, JPG/JPEG, TGA, BMP/DIB, DDS, 64 MiB each |
| ZIP | 2 GiB compressed, 4 GiB extracted presets and images, 250,000 entries |
| Other files | Ignored |

Presets refer to images by name without extension, ignoring case (`sampler_clouds` finds `Clouds.PNG`). **Texture names must therefore be unique ignoring case and extension across the whole ZIP**, even in different folders. Some DDS compression formats are not supported by every device's GPU.

## How packs behave

- **One pack at a time.** A successful upload replaces the previous pack.
- In **Preset mood**, the **Collection** row (*Built-in* or *Custom*) appears once a pack exists. **Custom** plays only the pack's presets. With nothing selected and *Built-in*, bundled and custom presets play together. While any Mood option is on, only bundled presets with attributes play: custom presets have no attributes, so choose *Custom* to play them.
- **Textures:** a custom preset uses its pack's images first and falls back to the available base collection's textures. The texture-free F-Droid starters supply none; download the full collection or include required images in your ZIP. Base presets keep their own images. During a blend, each preset retains its source images. This needs an [engine change](engine/patches.md#0010-each-preset-keeps-its-own-textures), because MilkDrop only ever had one texture folder.
- **Skips** for presets that fail to load, stay black or run too slowly apply to custom presets as well.
- **Persistence.** The pack and the Custom selection survive restarts and app updates. Packs are excluded from Android backup, so upload the ZIP again after reinstalling, clearing app data or restoring onto another device.
- **Safety.** An invalid ZIP, cancellation or insufficient storage leaves the previous pack in place. Replacing a pack temporarily needs room for the old pack, the incoming ZIP and the new pack.

## Network and privacy

- The listener runs **only while the dialog is open**. Closing the dialog or leaving the app stops it and cancels an unfinished upload.
- Each time the dialog opens it uses a new random port and a random 128-bit session path, shown only inside the QR code.
- It binds a private IPv4 address on Wi-Fi (preferred) or Ethernet. VPN and point-to-point interfaces are never used. Guest networks that isolate clients may block the uploading device from reaching the visualizer.
- The page must be opened at the address in the QR code. Only one import runs at a time, and a transfer may take up to one hour.
- The upload uses plain HTTP on your local network and is not encrypted. Use a network you trust.

## Make presets

See [Writing presets](authoring/index.md) for how presets work, and [Test and predict presets](authoring/testing.md) for checking a pack before you upload it.
