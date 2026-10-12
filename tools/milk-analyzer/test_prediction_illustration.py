"""The SDK-fact illustrator uses closed-form maps and abstains without facts."""
import numpy as np
import pytest

from prediction_illustration import _retained_radius,illustrate,_spread_sigma


@pytest.mark.parametrize('a,b',[(0.9995139837265015,.01),(1.0,.02),(1.01,0.0)])
def test_closed_form_matches_iterated_inverse_feature_map(a,b):
    radius=np.array([.05,.3,.6])
    iterated=radius.copy()
    for _ in range(25):iterated=a*iterated/(1-b*iterated)
    assert np.allclose(_retained_radius(radius,{'a':a,'b':b},25),iterated,rtol=1e-12)


def test_summary_without_supported_facts_draws_nothing_and_says_why():
    summary={'policy':'preset-understanding-v1','facts':{'context':[{'path':
        '/analysis/visual_description/static_behaviour/context','value':{'viewport':[64,36],'feedback_fps':30}}]}}
    image,used,limitations=illustrate(summary,time=1.0,fps=30.0,history_steps=4)
    assert image.shape==(36,64,3) and not image.any()
    assert used==[]
    assert limitations


def test_spread_reference_uses_uniform_offset_variance():
    spread={'per_step_variance_uniform_offset_reference_texels2':1/6}
    assert _spread_sigma(spread,6)==pytest.approx(1.0)
    assert _spread_sigma(None,6)==0.0


def test_faint_channels_follow_their_own_stored_level_orbit():
    from prediction_illustration import _level_table
    table=_level_table(float(np.float32(.98)),200)
    assert table[200][26]==25
    assert table[200][255]==25
    assert table[0][26]==26


def test_palette_display_keeps_exact_flat_field_colour():
    from prediction_illustration import _palette_display
    base='/analysis/visual_description/nonlinear_texture_colour_bounds'
    facts={base+'/stages/composite/scalar_palette':{'samples':[{'scalar':0.,'clamped_rgb':[1,1,0]},{'scalar':1.,'clamped_rgb':[.6,.4,0]},
            {'scalar':1.4,'clamped_rgb':[.2,0,0]}],'black_content_scalar':[0.,0.]},
           base+'/flat_field':{'state_rgb':[0,1,.5],'composite_rgb_at_state':[.54,.13,0]}}
    image=np.zeros((4,4,3),np.float32);image[:]=[0,1,.5]
    shown=_palette_display(image,facts,[])
    assert np.allclose(shown,[.54,.13,0])


def _shape(textured=True, tex_angle=0.0, sides=4, border=None):
    constant = lambda value: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': value}}]}
    control = lambda value: {'constant_value': value}
    channels = {'centre': {'a': constant(1.), 'r': constant(1.), 'g': constant(1.), 'b': constant(1.)},
                'perimeter': {'a2': constant(1.), 'r2': constant(1.), 'g2': constant(1.), 'b2': constant(1.)},
                'border': {f'border_{c}': constant(v) for c, v in zip('rgba', border or (0., 0., 0., 0.))}}
    return {'id': 't', 'controls': {'position_x': control(.5), 'position_y': control(.5), 'radius': control(.35),
                                    'rotation': control(0.)},
            'texture': {'tex_zoom_source': .5, 'tex_angle_source_rad': tex_angle}, 'sides': sides, 'textured': textured,
            'channels': channels, 'blend': 'source_alpha_over', 'rgb': [1, 1, 1], 'thick_outline': False, 'held': {}}


def test_textured_shape_copy_keeps_screen_orientation():
    # Controlled published-AAR capture: tex_zoom .5 minifies the previous frame ~0.18x without mirroring.
    import numpy as np
    from prediction_illustration import _draw_textured_shape
    source = np.zeros((270, 480, 3), np.float32)
    source[:135, :240, 0] = 1.  # red top-left quadrant
    source[135:, 240:, 2] = 1.  # blue bottom-right quadrant
    out, drawn = _draw_textured_shape(np.zeros_like(source), _shape(), 0., True, source)
    assert drawn
    assert out[125, 230, 0] > .9 and out[125, 230, 2] < .1   # copy of red stays upper-left of centre
    assert out[145, 250, 2] > .9 and out[145, 250, 0] < .1   # copy of blue stays lower-right


def test_untextured_shape_fill_and_outline():
    import numpy as np
    from prediction_illustration import _draw_textured_shape
    image = np.zeros((270, 480, 3), np.float32)
    out, drawn = _draw_textured_shape(image, _shape(textured=False, border=(1., 0., 0., 1.)), 0., True, image)
    assert drawn
    assert out[135, 240].tolist() == [1., 1., 1.]               # white gradient fill at the centre
    assert (out[..., 0] > .5).sum() > (out[..., 1] > .5).sum()  # red outline pixels beyond the fill


def test_declared_audio_requires_all_bands(tmp_path):
    import json
    import pytest
    from prediction_illustration import declared_audio
    good = {'frames': [{'bass': 1, 'mid': 2, 'treb': 3, 'bass_att': 1, 'mid_att': 1, 'treb_att': 1}]}
    (tmp_path / 'good.json').write_text(json.dumps(good))
    record = declared_audio(tmp_path / 'good.json')
    assert record['frames'][0]['mid'] == 2.0 and len(record['sha256']) == 64
    (tmp_path / 'bad.json').write_text(json.dumps({'frames': [{'bass': 1}]}))
    with pytest.raises(ValueError):
        declared_audio(tmp_path / 'bad.json')


def test_seeded_rand_samples_projectm_eval_range():
    import numpy as np
    from prediction_illustration import _evaluate_np
    program = {'root': 1, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 6.7}},
                                    {'op': 'rand', 'args': [0], 'detail': {}}]}
    values = [float(_evaluate_np(program, {}, np.random.default_rng(seed))) for seed in range(200)]
    assert 0 <= min(values) and max(values) < 6 and max(values) > 5  # uniform on [0, floor(6.7))


def test_fit_inputs_trims_vector_width_to_declared_dtype():
    import numpy as np
    from prediction_illustration import _fit_inputs
    expression = {'nodes': [{'op': 'input', 'dtype': 'float2', 'args': [], 'detail': {'name': '_uv'}}]}
    fitted = _fit_inputs(expression, {'_uv': np.zeros((3, 4), np.float32)})
    assert fitted['_uv'].shape == (3, 2)


def test_engine_blur_bank_keeps_top_down_orientation_and_range_uniforms():
    import numpy as np
    from prediction_illustration import _blur_bank
    image=np.zeros((90,160,3),np.float32);image[:20,:30]=1
    textures,uniforms=_blur_bank(image,{'blur1_edge_darken':0.})
    for level,texture in textures.items():
        h,w=texture.shape[:2]
        assert texture[:h//4,:w//4].mean()>4*texture[-h//4:,:w//4].mean()+.05
    assert np.allclose(uniforms['_c5'],[1,0,1,0]) and np.allclose(uniforms['_c6'],[1,0,0,1])
    _,narrow=_blur_bank(image,{'blur1_min':.2,'blur1_max':.8})
    assert np.allclose(narrow['_c5'][:2],[.6,.2]) and np.allclose(narrow['_c6'][2:],[.2,.8])


def test_conditional_wrap_follows_per_frame_wrap_value():
    from prediction_illustration import _sampler_wraps
    conditional={'texture':'main','wrap':None,'wrap_condition':'frame_wrap > 0.0001'}
    assert _sampler_wraps(conditional,{'wrap':1.}) is True
    assert _sampler_wraps(conditional,{'wrap':0.}) is False
    assert _sampler_wraps(conditional,None) is True
    assert _sampler_wraps({'wrap':False},{'wrap':1.}) is False


def test_texsize_uniforms_follow_engine_texture_sizes():
    from prediction_illustration import _texsize, _noise_texture
    assert list(_texsize('noise_lq', 480, 270)[:2]) == [256, 256]
    assert list(_texsize('noise_lq_lite', 480, 270)[:2]) == [32, 32]
    assert list(_texsize('blur1', 480, 270)[:2]) == [112, 68]
    assert list(_texsize('main', 480, 270)[:2]) == [480, 270]
    a = _noise_texture('noise_hq');b = _noise_texture('noise_lq')
    assert a.shape == (256, 256, 3) and b.shape == (256, 256, 3)
    # hq is interpolated from 32 cells (smooth), lq has independent texels
    assert np.abs(np.diff(a, axis=1)).mean() < np.abs(np.diff(b, axis=1)).mean() / 3


def test_mesh_interpolation_is_exact_for_affine_fields_and_top_row_first():
    from prediction_illustration import _mesh_interpolator
    interpolate = _mesh_interpolator((48, 32), 96, 64, True)
    gx, gy = np.meshgrid(np.arange(49), np.arange(33))
    field = 2. * gx + 3. * gy  # vertex values; row 0 is the top edge
    out = interpolate(field.astype(np.float32))
    columns, rows = np.meshgrid(np.arange(96) + .5, np.arange(64) + .5)
    assert np.allclose(out, 2 * columns / 96 * 48 + 3 * rows / 64 * 32, atol=1e-4)
