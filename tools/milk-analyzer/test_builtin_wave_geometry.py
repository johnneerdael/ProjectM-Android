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
