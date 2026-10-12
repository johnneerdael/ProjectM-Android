import numpy as np

from test_effect_families import shader
from test_source_appearance import appearance


def evaluate(stage, code, image_value=.8):
    from prediction_illustration import _evaluate_stage
    programs = appearance(shader(code, stage='comp' if stage == 'composite' else stage))['stage_programs']['stages']
    assert programs[stage]['status'] == 'exported', programs[stage]
    image = np.full((9, 16, 3), image_value, np.float32)
    columns, rows = np.meshgrid((np.arange(16) + .5) / 16, (np.arange(9) + .5) / 9)
    uv = np.stack([columns, rows, columns, rows], -1)
    return _evaluate_stage(programs[stage]['program'], image, uv, 1., 30., {})


def test_warp_program_round_trip_reproduces_shader_arithmetic():
    out = evaluate('warp', 'shader_body{ret=GetPixel(uv)*.5+.1;}')
    assert np.allclose(out, .5 * .8 + .1, atol=1e-6)


def test_loop_plan_is_serialised_and_evaluated():
    out = evaluate('composite', 'shader_body{float3 a=0;float n=0;while(n<3){a+=.1;n++;} ret=a;}')
    assert np.allclose(out, .3, atol=1e-6)
