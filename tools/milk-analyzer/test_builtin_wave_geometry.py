import numpy as np
import pytest

from builtin_wave_geometry import vertices


def test_line_mode_with_silence_is_a_horizontal_line_at_wave_x_offset():
    (line,), loop = vertices(6, left=np.zeros(544), wave_x=.5, wave_y=.5, mystery=0., viewport=(480, 270))
    assert not loop
    assert np.allclose(line[:, 1], 0., atol=1e-9)  # angle 0 line through the centre
    assert line[0, 0] < -1 and line[-1, 0] > .9  # spans the screen, clipped at +-1.1
    assert len(line) == 2 * 80 - 1  # 240 samples, /3 below 720 px, then midpoint insertion


def test_circle_mode_radius_and_aspect():
    (circle,), loop = vertices(0, left=np.zeros(544), viewport=(480, 270), time=0.)
    assert loop
    radius_x = np.abs(circle[:, 0]).max() / (270 / 480)
    assert abs(radius_x - .5) < .01 and abs(np.abs(circle[:, 1]).max() - .5) < .01


def test_unmodelled_modes_raise():
    with pytest.raises(ValueError):
        vertices(8, left=np.zeros(544))
    with pytest.raises(ValueError):
        vertices(12, left=np.zeros(544))


def test_custom_wave_values_follow_projectm_window_and_smoothing():
    import numpy as np
    from builtin_wave_geometry import custom_wave_values
    data = np.arange(576, dtype=float) - 288
    # no smoothing: centred 100-sample window of the first 480 samples, scaled by scaling*wave_scale*0.004
    v1, v2 = custom_wave_values(data, sample_count=100, scaling=2., wave_scale=.5, smoothing=0., sep=0)
    assert np.allclose(v1, (data[190:290]) * .004) and np.allclose(v1, v2)
    # separation shifts the channels in opposite directions
    a, b = custom_wave_values(data, sample_count=100, smoothing=0., sep=20)
    assert np.allclose(a, data[180:280] * .004) and np.allclose(b, data[200:300] * .004)
    # more points than waveform samples resample the 480 inputs
    c, _ = custom_wave_values(data, sample_count=512, smoothing=0.)
    assert np.isclose(c[511], data[int(511 * 480 / 512)] * .004)


def test_spectrum_matches_a_direct_milkdrop_fft():
    # projectM PCM::UpdateSpectrum + MilkdropFFT(480 in, 512 out, equalize, envelope power 1).
    import math
    import numpy as np
    from builtin_wave_geometry import spectrum
    rng = np.random.default_rng(3)
    window = np.round(rng.normal(0, 30, 576))
    damped = [.5 * (window[i] + window[max(i - 1, 0)]) for i in range(576)]
    envelope = [.5 + .5 * math.sin(i * 2 * math.pi / 480 - math.pi / 2) for i in range(480)]
    x = [damped[i] * envelope[i] for i in range(480)] + [0.] * (1024 - 480)
    expected = []
    for k in range(512):
        re = sum(x[n] * math.cos(-2 * math.pi * k * n / 1024) for n in range(480))
        im = sum(x[n] * math.sin(-2 * math.pi * k * n / 1024) for n in range(480))
        expected.append(-.02 * math.log((512 - k) / 512) * math.hypot(re, im))
    assert np.allclose(spectrum(window), expected, rtol=1e-6, atol=1e-6)


def test_spectrum_custom_wave_values_resample_and_scale_like_projectm():
    import numpy as np
    from builtin_wave_geometry import custom_spectrum_values
    spec = np.arange(512, dtype=float)
    left, right = custom_spectrum_values(spec, spec, sample_count=256, scaling=2., wave_scale=.5, smoothing=0., sep=0)
    # scaling (512 - sep) / 256 = 2: point j reads bin int(2j); mult = 2 * .5 * .15.
    assert np.allclose(left, spec[::2] * .15) and np.allclose(right, left)
    left, _ = custom_spectrum_values(spec, spec, sample_count=512, scaling=1., wave_scale=1., smoothing=0., sep=256)
    assert np.allclose(left, spec[(np.arange(512) * .5).astype(int)] * .15)
