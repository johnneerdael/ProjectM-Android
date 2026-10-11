"""Native motion vectors are a drawing element with an engine grid rule."""
import json

import pytest

from test_effect_families import read as read_raw
from test_source_shape_state_export import read,report,PRESETS

CONTEXT={'viewport':[480,270],'feedback_fps':30}


def vectors(source):
    value=report(source,CONTEXT)['motion_vectors']
    json.dumps(value,allow_nan=False)
    return value


def test_legacy_flag_enables_one_bottom_row_of_white_vectors():
    value=vectors(read(PRESETS/'Rovastar and Krash - Seas Of Tron.milk'))
    assert value['status']=='described' and value['activation']=='active'
    # (i+.25)/63.25 places the 64th column at exactly 1.0, outside the .9999 filter.
    assert len(value['columns_screen_fraction'])==63
    assert value['rows_screen_fraction_from_top']==[pytest.approx(.8)]
    assert value['vector_count']==63
    assert value['colour_rgba'][:3]==[1.0,1.0,1.0]
    assert value['drawn_into_feedback'] is True


def test_default_preset_has_inactive_vectors():
    value=vectors(read_raw('fWaveAlpha=0\n'))
    assert value['activation']=='inactive'


def test_explicit_grid_and_offset():
    value=vectors(read_raw('mv_a=0.5\nnMotionVectorsX=4\nnMotionVectorsY=3\nmv_dx=0.1\nmv_r=0.2\n'))
    columns=[(i+.25)/3.25+.1 for i in range(4)]
    assert value['columns_screen_fraction']==[pytest.approx(v) for v in columns if .0001<v<.9999]
    assert value['rows_screen_fraction_from_top']==[pytest.approx(1-(i+.25)/2.25) for i in range(3) if (i+.25)/2.25<.9999]
    assert value['colour_rgba'][0]==pytest.approx(.2)


def test_dynamic_alpha_keeps_possible_activation():
    value=vectors(read_raw('nMotionVectorsX=8\nnMotionVectorsY=4\nper_frame_1=mv_a=bass-1;\n'))
    assert value['activation'] in {'possible','active',None}
