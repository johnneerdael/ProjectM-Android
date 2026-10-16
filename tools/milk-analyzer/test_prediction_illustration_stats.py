import numpy as np


def test_frame_stats_also_summarise_the_canvas_before_the_composite():
    # Previews teach the static maths: comparing the canvas (feedback buffer) level with the displayed level tells
    # whether a static miss sits in the equilibrium (canvas) or in the composite transfer. The canvas hook is additive:
    # display statistics are unchanged when it is used.
    from prediction_illustration import FrameStats
    stats = FrameStats(start=1)
    for k in range(3):
        stats.record_canvas(np.full((4, 4, 3), .2, np.float32))
        stats(k / 30, np.full((18, 32, 3), .5, np.float32))
    s = stats.summary()
    assert abs(s['canvas_mean_luminance'] - .2) < 1e-6 and abs(s['mean_luminance'] - 128 / 255) < 1e-6
