# r165 v2: colour from closed-form shape channels

In v1 the recipe left every palette unresolved, so the reader guessed "perhaps blue" for a green and magenta
picture. The source shows where the colour comes from. The warp is a Julia map (it moves colour and creates
none). The composite is `(pixel - blur)*inten`, per channel and multiplied by 4, so grey input stays grey.
The four shapes' fills are `0.25 + 0.25*sin(time*k)` with a different k for each channel, so their hue
drifts over time and the composite's edge gain makes it vivid.

Two general recipe additions:

- Shape layers get `colour_over_time`: centre and edge RGB from the closed-form channels every 0.5 s over
  30 s, with projectM's colour modulo and neutral audio. It reports ranges, mean saturation and
  time-weighted hue shares. For r165 green leads, then pink, purple and cyan.
- `composite.detail_response`: a grey multi-scale texture at reference scale goes through the exported
  composite, and the result reports the colour the composite creates from structure. For r165 it is grey,
  so displayed colour comes from the elements. For heat-ramp composites (r160, r163) it is yellow, with
  saturation 0.96.

The v2 reading names "green most often, then pink, purple, cyan", which matches the capture.
