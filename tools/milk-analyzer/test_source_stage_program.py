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


def test_frame_program_steps_persistent_state():
    from test_effect_families import read
    from prediction_illustration import _FrameStepper
    source = read('per_frame_1=acc=acc*0.5+bass;\nper_frame_2=q1=acc;\n')
    frame = appearance(source)['stage_programs']['frame']
    assert 'acc' in frame['state'] and 'q1' in frame['outputs']
    stepper = _FrameStepper(frame)
    values = [stepper.step((k + 1) / 30, 30, {'bass': 1., 'mid': 0, 'treb': 0, 'bass_att': 0, 'mid_att': 0, 'treb_att': 0}, k + 1)['q1']
              for k in range(20)]
    assert abs(values[0] - 1.) < 1e-9 and abs(values[1] - 1.5) < 1e-9 and abs(values[-1] - 2.) < 1e-4


import pytest

_COMPILED_CASES = [
    ('warp', 'shader_body{ret=GetPixel(uv)*.5+.1;}'),
    ('warp', 'shader_body{float2 d=uv-.5; ret=tex2D(sampler_main,uv+d*.03).xyz*.97 - .004;}'),
    ('composite', 'shader_body{float3 c=tex2D(sampler_main,uv).xyz; ret=lerp(c,1-c,.3)*float3(1.2,.9,.7);}'),
    ('composite', 'shader_body{float3 c=GetPixel(uv); if(c.x>.5) ret=c.zyx; else ret=pow(c,2.2);}'),
    ('warp', 'shader_body{float2 p=normalize(uv-.5+.001)*length(uv-.5); ret=GetBlur1(uv+p*.02)*1.1-GetPixel(uv)*.1;}'),
    ('composite', 'shader_body{float3 n=tex2D(sampler_noise_lq,uv*3).xyz; ret=saturate(GetPixel(uv)+(n-.5)*.2); ret*=step(.2,ret.y);}'),
    ('warp', 'shader_body{float a=atan2(uv.y-.5,uv.x-.5); float r=frac(a*3/3.14159+time*.1); ret=GetPixel(float2(r,uv.y)).xyz*max(.5,min(.9,r));}'),
    ('composite', 'shader_body{float3 c=GetPixel(uv); float v=dot(c,float3(.3,.59,.11)); ret=float3(v,v*v,abs(sin(v*6)));}'),
]


@pytest.mark.parametrize('stage,code', _COMPILED_CASES)
def test_compiled_stage_plan_matches_the_reference_evaluator(stage, code, monkeypatch):
    import prediction_illustration as P
    from test_effect_families import shader
    from test_source_appearance import appearance
    programs = appearance(shader(code, stage='comp' if stage == 'composite' else stage))['stage_programs']['stages']
    assert programs[stage]['status'] == 'exported', programs[stage]
    rng = np.random.default_rng(3)
    image = rng.random((9, 16, 3)).astype(np.float32)
    columns, rows = np.meshgrid((np.arange(16) + .5) / 16, (np.arange(9) + .5) / 9)
    uv = np.stack([columns, rows, columns, rows], -1)
    used = []
    import stage_compiled
    original = stage_compiled.run
    monkeypatch.setattr(stage_compiled, 'run', lambda *a, **k: (used.append(1), original(*a, **k))[1])
    monkeypatch.setattr(P, '_COMPILED_STAGES', [False])
    reference = P._evaluate_stage(programs[stage]['program'], image, uv, 1.5, 30., {'bass': 1.2, 'treb': .8})
    monkeypatch.setattr(P, '_COMPILED_STAGES', [True])
    compiled = P._evaluate_stage(programs[stage]['program'], image, uv, 1.5, 30., {'bass': 1.2, 'treb': .8})
    assert used, 'compiled plan was not used'
    assert np.array_equal(reference, compiled)


def _rand_site_program():
    # ret = rand(10)*.05 as a shader that inlines a main per-frame site (q1 = rand(10)).
    nodes = [{'op': 'multiply', 'dtype': 'float', 'args': [1, 3], 'detail': {}},
             {'op': 'rand', 'dtype': 'float', 'args': [2], 'detail': {'site_index': 0, 'equation_phase': 'per_frame_'}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 10.}},
             {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': .05}}]
    return {'root': 0, 'nodes': nodes, 'plans': []}


@pytest.mark.parametrize('compiled', [False, True])
def test_inlined_per_frame_rand_reads_the_frame_steppers_draw(compiled, monkeypatch):
    # The engine ran the main per-frame code once this frame; the shader sees that frame's value of the site.
    import prediction_illustration as P
    monkeypatch.setattr(P, '_COMPILED_STAGES', [compiled])
    class Sites:
        cache = {('per_frame_', 0): .25}
    monkeypatch.setitem(P._TERM_CONTEXT, 'site_rng', Sites())
    image = np.zeros((4, 4, 3), np.float32)
    columns, rows = np.meshgrid((np.arange(4) + .5) / 4, (np.arange(4) + .5) / 4)
    uv = np.stack([columns, rows, columns, rows], -1)
    out = P._evaluate_stage(_rand_site_program(), image, uv, 1., 30., {})
    assert np.allclose(out, .25 * 10 * .05)


@pytest.mark.parametrize('compiled', [False, True])
def test_stage_rand_without_a_stepper_is_deterministic_per_frame(compiled, monkeypatch):
    import prediction_illustration as P
    monkeypatch.setattr(P, '_COMPILED_STAGES', [compiled])
    monkeypatch.setitem(P._TERM_CONTEXT, 'site_rng', None)
    image = np.zeros((4, 4, 3), np.float32)
    columns, rows = np.meshgrid((np.arange(4) + .5) / 4, (np.arange(4) + .5) / 4)
    uv = np.stack([columns, rows, columns, rows], -1)
    first = P._evaluate_stage(_rand_site_program(), image, uv, 1., 30., {})
    second = P._evaluate_stage(_rand_site_program(), image, uv, 1., 30., {})
    assert np.array_equal(first, second)
