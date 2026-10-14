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
    assert a.shape == (256, 256, 4) and b.shape == (256, 256, 4)
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


def test_point_pixels_follow_gl_point_coverage():
    from prediction_illustration import _point_pixels
    # native-ruler probe: x=0.5 (window 240) -> column 239; x=0 -> column -1 (not drawn); y=0.25 -> row 255
    cols, rows = _point_pixels(np.array([240., 0.]), np.array([255., 135.]), 1, 270)
    assert list(cols) == [239, -1] and rows[0] == 255
    cols, rows = _point_pixels(np.array([240.]), np.array([255.]), 2, 270)
    assert cols[0] == 239 and rows[0] == 254


def test_frame_wave_alpha_applies_volume_ramp_and_clamp():
    from prediction_illustration import _frame_wave_alpha, _frame_wave_colour
    material = {'alpha_recipe': {'alpha_envelope_without_volume_modulation': [.2, .2], 'mode_gain': 1.,
                                 'volume_ramp': {'enabled': True, 'start': .75, 'end': 1.17}}, 'normalization_enabled': True}
    quiet = _frame_wave_alpha(material, {'bass': .5, 'mid': .5, 'treb': .5})
    loud = _frame_wave_alpha(material, {'bass': 3., 'mid': 3., 'treb': 3.})
    assert quiet == 0.0 and abs(loud - min(1., .2 * (3 * .999 - .75) / .42)) < 1e-6
    assert _frame_wave_colour(material, {'wave_r': .2, 'wave_g': .1, 'wave_b': .4}) == [.5, .25, 1.]
    assert _frame_wave_colour(material, {}) is None


def test_frame_stepper_reads_never_written_variables_as_zero():
    from prediction_illustration import _FrameStepper
    # speed = speed + 1 - ghost   (ghost is never written: projectm-eval reads 0)
    update = {'root': 4, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'state:per_frame_:speed'}},
                                   {'op': 'constant', 'args': [], 'detail': {'value': 1.}},
                                   {'op': 'add', 'args': [0, 1], 'detail': {}},
                                   {'op': 'input', 'args': [], 'detail': {'name': 'ghost'}},
                                   {'op': 'subtract', 'args': [2, 3], 'detail': {}}]}
    stepper = _FrameStepper({'state': {'speed': {'initial': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 0.}}]},
                                                 'update': update}}, 'outputs': {}})
    for frame in range(3):
        values = stepper.step(frame / 30, 30, {'bass': 1.}, frame)
    assert values['speed'] == 3. and values['ghost'] == 0. and not stepper.failed


def test_named_textures_load_bundled_images_with_their_size():
    from prediction_illustration import _named_texture, _texsize, TEXTURE_DIRECTORY
    if not (TEXTURE_DIRECTORY / 'devboxb.jpg').exists():
        pytest.skip('bundled textures not present')
    image = _named_texture('devboxb')
    assert image is not None and image.ndim == 3 and image.shape[2] == 3 and 0 <= image.min() and image.max() <= 1
    assert _named_texture('fw_devboxb') is image
    assert list(_texsize('devboxb', 480, 270)[:2]) == [image.shape[1], image.shape[0]]
    assert _named_texture('no_such_texture_name') is None


def test_mode3_wave_alpha_uses_reference_alpha_and_treble_squared():
    from prediction_illustration import _frame_wave_alpha
    material = {'alpha_recipe': {'alpha_envelope_without_volume_modulation': [.1, .9], 'mode3_formula': 'x',
                                 'reference_table': [{'maximum_size': 256, 'mode3_base_alpha': .075}, {'maximum_size': 512, 'mode3_base_alpha': .15},
                                                     {'maximum_size': None, 'mode3_base_alpha': .44}], 'volume_ramp': {'enabled': False}}}
    alpha = _frame_wave_alpha(material, {'treb': 1.5, 'bass': 1., 'mid': 1.}, 3, 480)
    assert abs(alpha - .15 * 1.3 * 2.25) < 1e-6
    assert _frame_wave_alpha(material, {'treb': 1.5}, 3, 4000) == 1.0  # .44*1.3*2.25 clamps


def test_gl_lines_are_half_open_along_the_major_axis():
    from prediction_illustration import _gl_line_pixels
    # 1.25 px long horizontal line from a pixel centre covers that pixel only (end pixel excluded).
    rows, cols = _gl_line_pixels([10.5], [5.5], [11.75], [5.5], 32, 16)
    assert list(cols) == [10] and list(rows) == [5]
    # Ten pixels to the right covers columns 10-19; the reversed line covers 11-20 (exit excluded).
    rows, cols = _gl_line_pixels([10.5], [5.5], [20.5], [5.5], 32, 16)
    assert sorted(cols) == list(range(10, 20))
    rows, cols = _gl_line_pixels([20.5], [5.5], [10.5], [5.5], 32, 16)
    assert sorted(cols) == list(range(11, 21))
    # y-major diagonal: one pixel per row.
    rows, cols = _gl_line_pixels([3.5], [2.5], [5.5], [8.5], 32, 16)
    assert sorted(rows) == list(range(2, 8)) and len(cols) == 6


def test_control_with_unbounded_unknown_term_is_held_whole():
    from prediction_illustration import _control_field, _UNRESOLVED_TERMS
    x, y = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 4))
    # dx = q*x - x with the q*x half unknown: summing only -x would invent a strong leftward flow.
    control = {'terms': [{'kind': 'unresolved_inputs', 'expression': None, 'sign': 1},
                         {'kind': 'coordinate_affine', 'coefficients': {'x': -1.}, 'constant': 0.}], 'value_range': None}
    assert np.all(_control_field(control, 'dx', x, y, 0.) == 0.)
    assert np.all(_control_field({**control, 'value_range': [.1, .3]}, 'dx', x, y, 0.) == .2)
    zoom = {'terms': [{'kind': 'unresolved_inputs', 'expression': None}], 'value_range': None}
    assert np.all(_control_field(zoom, 'zoom', x, y, 0.) == 1.)
    resolved = {'terms': [{'kind': 'coordinate_affine', 'coefficients': {'x': -1.}, 'constant': 0.}]}
    assert np.allclose(_control_field(resolved, 'dx', x, y, 0.), -x)
    _UNRESOLVED_TERMS.clear()


def test_motion_vector_minimum_length_is_in_texture_units():
    from prediction_illustration import _motion_vector_marks
    facts = {'/analysis/visual_description/static_behaviour/motion_vectors': {
        'status': 'described', 'vector_count': 1, 'columns_screen_fraction': [.5], 'rows_screen_fraction_from_top': [.5],
        'length_scale': [.25, .25], 'colour_rgba': [1, 1, 1, 1]}}
    width, height = 480, 270
    still = (np.full((height, width), 239.5, np.float32), np.full((height, width), 134.5, np.float32))
    (start, end, _), = _motion_vector_marks(facts, lambda t: still, 0., width, height, still)
    minimum = np.hypot(1.25 / width, 1.25 / height)
    assert start == (240., 135.) and np.allclose(end, (240 + minimum * width, 135 + minimum * height))


def test_frame_stepper_sees_float32_engine_time():
    from prediction_illustration import _FrameStepper
    # gate = above(time, 0.1): RenderContext::time is a float, so frame 2 (time 3/30) passes the
    # threshold in the engine (float32(0.1) > 0.1) although 3/30 == 0.1 in double precision.
    nodes = [{'op': 'input', 'args': [], 'detail': {'name': 'time'}},
             {'op': 'constant', 'args': [], 'detail': {'value': .1}},
             {'op': 'greater', 'args': [0, 1], 'detail': {}}]
    stepper = _FrameStepper({'state': {}, 'outputs': {'gate': {'root': 2, 'nodes': nodes}}})
    values = [stepper.step((k + 1) / 30, 30, {'bass': 1.}, k)['gate'] for k in range(3)]
    assert values == [0., 0., 1.]


def test_thick_custom_wave_flat_line_lights_one_row():
    from prediction_illustration import _draw_points
    # x = sample, y = .5, thick: native ruler lights a single row (passes offset right and up by
    # 1/viewportX in NDC: half a pixel horizontally, H/(2W) pixels vertically).
    record = {'sample_count': 32, 'draw_flags': {'thick': True, 'additive': True},
              'programs': {'x': {'root': 0, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'sample'}}]},
                           'y': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': .5}}]},
                           **{c: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 1.}}]} for c in 'rgba'}}}
    width, height = 480, 270
    def to_pixels(point):
        return ((point[0] - .5) * width + width / 2, height / 2 - (point[1] - .5) * width)
    image = _draw_points(np.zeros((height, width, 3), np.float32), record, 1., to_pixels)
    lit = np.nonzero(image[:, 20:460, 0].max(axis=1) > .5)[0]
    assert list(lit) == [135]


def test_shader_rad_ang_follow_engine_frames():
    from prediction_illustration import _rad_ang
    warp = _rad_ang(480, 270)
    comp = _rad_ang(480, 270, 'composite')
    # y is measured downward from the top: the top-centre pixel has a negative warp angle and a composite
    # angle near 1.5 pi (FinalComposite::UvToMathSpace wraps to [0, 2 pi)).
    assert -np.pi / 2 - .05 < warp[0, 240, 1] < -np.pi / 2 + .05
    assert 1.5 * np.pi - .05 < comp[0, 240, 1] < 1.5 * np.pi + .05
    # Composite radius is 1 at the corners; the warp radius is hypot(x*aspectX, y*aspectY).
    assert abs(comp[0, 0, 0] - 1) < .01 and abs(warp[0, 0, 0] - np.hypot(1, 270 / 480)) < .01


def test_alpha_blended_dots_converge_to_their_colour():
    from prediction_illustration import _draw_points
    # 64 identical thick dots at one position, alpha .5, alpha blending: GL composites them in turn,
    # so the pixel converges to the dot colour instead of summing past it.
    constant = lambda v: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': v}}]}
    record = {'sample_count': 64, 'draw_flags': {'dots': True, 'thick': True, 'additive': False},
              'programs': {'x': constant(.5), 'y': constant(.5), 'r': constant(1.), 'g': constant(.5), 'b': constant(0.), 'a': constant(.5)}}
    def to_pixels(point):
        return ((point[0] - .5) * 64 + 32, 18 - (point[1] - .5) * 64)
    image = _draw_points(np.zeros((36, 64, 3), np.float32), record, 1., to_pixels)
    lit = image[image.max(axis=-1) > 0]
    assert len(lit) == 4 and np.allclose(lit, [1., .5, 0.], atol=1e-4)


def test_point_samplers_read_exactly_one_texel():
    # A one-texel offset from each texel centre (shader arithmetic in float32) must read exactly the
    # neighbour: bilinear weights of ~1e-7 on the texel two away would satisfy a strict "> 0" test.
    from prediction_illustration import _texture_lookup
    width = 480
    source = np.zeros((1, width, 3), np.float32); source[0, 240, 1] = 1.
    centres = (np.arange(width, dtype=np.float32) + np.float32(.5)) / np.float32(width)
    for offset in (-1, 1):
        coordinates = np.stack([centres + np.float32(offset) / np.float32(width), np.full(width, .5, np.float32)], axis=1)
        values = _texture_lookup(source, coordinates, wrap=True, linear=False)[:, 1]
        assert np.flatnonzero(values).tolist() == [240 - offset] and values[240 - offset] == 1.
    # Linear sampling between two texel centres still interpolates.
    halfway = np.array([[241 / width, .5]], np.float32)
    assert abs(_texture_lookup(source, halfway, wrap=True, linear=True)[0, 1] - .5) < 1e-4


def test_hue_shader_interpolates_the_engine_corner_colours():
    # FinalComposite::ApplyHueShaderColors: corner shades 0.6+0.3*sin(...), normalised by their max and
    # mapped to 0.5+0.5*shade, then bilinear across the screen (x right, y up).
    import math
    from prediction_illustration import _hue_shader
    t = 3.
    def corner(i):
        s = [.6 + .3 * math.sin(t * 30 * .0143 + 3 + i * 21), .6 + .3 * math.sin(t * 30 * .0107 + 1 + i * 13),
             .6 + .3 * math.sin(t * 30 * .0129 + 6 + i * 9)]
        m = max(s);return [.5 + .5 * v / m for v in s]
    hue = _hue_shader(2, 2, t, cell_centres=False)
    # Top-down rows: row 0 is y=1 (top). Corner order: 0 at (x=1,y=1), 1 at (0,1), 2 at (1,0), 3 at (0,0).
    assert np.allclose(hue[0, 1, :3], corner(0), atol=1e-6) and np.allclose(hue[0, 0, :3], corner(1), atol=1e-6)
    assert np.allclose(hue[1, 1, :3], corner(2), atol=1e-6) and np.allclose(hue[1, 0, :3], corner(3), atol=1e-6)
    assert hue.shape == (2, 2, 4) and np.all(hue[..., 3] == 1.)


def test_dark_builtin_wave_covers_by_its_raster_not_its_colour():
    from prediction_illustration import _blend_wave_layer
    # A non-maximised wave (projectM keeps wave_r/g/b when the largest is <= 0.01) is near black.
    # Alpha blending replaces covered pixels with it at full alpha: a dark line cuts a red canvas.
    image = np.zeros((4, 6, 3), np.float32); image[..., 0] = 1.
    layer = np.zeros_like(image); mask = np.zeros(image.shape[:2], np.float32)
    layer[2, 1:5] = (.009, .005, 0.); mask[2, 1:5] = 1.
    canvas_alpha = np.zeros(image.shape[:2], np.float32)
    out, alpha_out = _blend_wave_layer(image, canvas_alpha, layer, mask, 1., False)
    assert np.allclose(out[2, 1:5], (.009, .005, 0.)) and np.all(out[0, :, 0] == 1.)
    assert np.all(alpha_out[2, 1:5] == 1.) and np.all(alpha_out[0] == 0.)
    # Additive blending adds the colour: a dark line barely changes the canvas.
    out, _ = _blend_wave_layer(image, canvas_alpha, layer, mask, 1., True)
    assert np.allclose(out[2, 1:5, 0], 1.)


def test_positions_only_cloud_draws_in_its_authored_colour():
    from prediction_illustration import _draw_points, _point_clouds
    const = lambda v: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': v}}]}
    record = {'status': 'unknown', 'positions_only': True, 'positions_closed_form': True, 'sample_count': 4,
              'programs': {'x': const(.5), 'y': const(.5)}, 'authored_rgba': [1., 0., 0., 1.],
              'draw_flags': {'dots': True, 'thick': False, 'additive': False}}
    facts = {'/analysis/visual_description/static_behaviour/colour/components/0':
             {'component_id': 'wave_0', 'source_palette': {'point_colour_distribution': record}}}
    assert [name for name, _ in _point_clouds(facts)] == ['wave_0']
    width, height = 48, 27
    image = _draw_points(np.zeros((height, width, 3), np.float32), record, 1., lambda p: (p[0] * width, (1 - p[1]) * height))
    assert image[..., 0].max() == 1. and image[..., 1].max() == 0.


def test_canvas_starts_cleared_when_the_history_covers_the_time_since_load():
    from prediction_illustration import _initial_canvas
    flat = {'state_rgb': [1., 1., 1.]}
    # projectM clears the feedback canvas at load: 150 frames at 30 fps is the whole first 5 s.
    image, note = _initial_canvas(flat, (4, 6), time=5., fps=30., history_steps=150)
    assert not image.any() and 'cleared' in note
    # A shorter history stands in for the earlier frames with the flat-field steady state.
    image, note = _initial_canvas(flat, (4, 6), time=20., fps=30., history_steps=150)
    assert np.all(image == 1.) and 'flat-field' in note


def test_non_finite_shader_output_is_stored_like_the_gpu():
    from prediction_illustration import _stored
    # 1/0 in a shader gives inf, inf*0 gives NaN; an RGBA8 target stores NaN as 0 and clamps infinities.
    values = np.array([np.nan, np.inf, -np.inf, .5, 1.7, -.2], np.float32)
    assert list(_stored(values)) == [0., 1., 0., .5, 1., 0.]


def test_noise_volumes_are_32_cubed_and_sampled_in_three_dimensions():
    from prediction_illustration import _noise_texture, _texture_lookup_3d, _texsize
    volume = _noise_texture('noisevol_hq')
    assert volume.shape == (32, 32, 32, 4)
    assert list(_texsize('noisevol_hq', 480, 270)[:2]) == [32, 32]
    lq = _noise_texture('noisevol_lq')
    # Texel centres read the texel; z selects the slice; wrap repeats.
    c = (np.array([[3, 5, 7]]) + .5) / 32
    assert np.allclose(_texture_lookup_3d(lq, c, wrap=True, linear=True)[0], lq[7, 5, 3])
    assert np.allclose(_texture_lookup_3d(lq, c + 1, wrap=True, linear=True)[0], lq[7, 5, 3])


def test_additive_line_wave_accumulates_every_segment():
    from prediction_illustration import _draw_points
    # x runs .2 -> .8 -> .2 at y = .5: the same row is drawn twice. GL adds both passes of an additive
    # wave, so the retraced pixels reach twice the colour (0.3 -> 0.6), not one layer's value.
    xs = {'root': 0, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'sample'}}]}
    record = {'sample_count': 3, 'draw_flags': {'thick': False, 'additive': True, 'dots': False},
              'programs': {'x': {'root': 4, 'nodes': [
                  {'op': 'input', 'args': [], 'detail': {'name': 'sample'}}, {'op': 'constant', 'args': [], 'detail': {'value': .5}},
                  {'op': 'subtract', 'args': [0, 1], 'detail': {}}, {'op': 'abs', 'args': [2], 'detail': {}},
                  {'op': 'add', 'args': [3, 5], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .3}}]},
                  'y': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': .5}}]},
                  **{c: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': v}}]} for c, v in zip('rgba', (.3, .3, .3, 1.))}}}
    width, height = 100, 50
    image = _draw_points(np.zeros((height, width, 3), np.float32), record, 1., lambda p: (p[0] * width, (1 - p[1]) * height))
    row = image[25, 35:65, 0]
    assert np.allclose(row, .6, atol=1e-6)


def test_alpha_line_wave_blends_every_overlapping_segment():
    from prediction_illustration import _draw_points
    # The same row is drawn twice by one alpha-blended strip (x .8 -> .3 -> .8). GL blends each fragment
    # over the framebuffer in order, so the retraced pixels compound: .5 then .5 + .5*.5 = .75 (r92 zigzag
    # ribbons), not the single layer's .5.
    record = {'sample_count': 3, 'draw_flags': {'thick': False, 'additive': False, 'dots': False},
              'programs': {'x': {'root': 4, 'nodes': [
                  {'op': 'input', 'args': [], 'detail': {'name': 'sample'}}, {'op': 'constant', 'args': [], 'detail': {'value': .5}},
                  {'op': 'subtract', 'args': [0, 1], 'detail': {}}, {'op': 'abs', 'args': [2], 'detail': {}},
                  {'op': 'add', 'args': [3, 5], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .3}}]},
                  'y': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': .5}}]},
                  **{c: {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': v}}]} for c, v in zip('rgba', (1., 1., 1., .5))}}}
    width, height = 100, 50
    canvas = {'alpha': np.zeros((height, width), np.float32)}
    image = _draw_points(np.zeros((height, width, 3), np.float32), record, 1., lambda p: (p[0] * width, (1 - p[1]) * height), canvas)
    assert np.allclose(image[25, 35:65, 0], .75, atol=1e-6)
    # The framebuffer alpha follows the same blend (src alpha weights its own alpha): .25 then .25 + .25*.5.
    assert np.allclose(canvas['alpha'][25, 35:65], .375, atol=1e-6)


def test_legacy_echo_follows_the_per_frame_orientation():
    from prediction_illustration import _composite
    # Patch 0008: the echo reads per-frame echo_orient (truncated, mod 4). Orientation 1 mirrors left-right.
    image = np.zeros((4, 8, 3), np.float32); image[:, :4] = 1.
    facts = {'/analysis/visual_description/x/legacy_response': {
        'echo_selection': 'active or possible native echo',
        'native_control_ranges': {'echo_alpha': [.5, .5], 'echo_zoom': [1., 1.], 'echo_orient': [0., 3.]}}}
    plain, _ = _composite(image.copy(), facts, controls={'echo_orient': .7})
    mirrored, _ = _composite(image.copy(), facts, controls={'echo_orient': 1.9})
    assert np.allclose(plain[:, :4], 1.) and np.allclose(plain[:, 4:], 0.)
    assert np.allclose(mirrored, .5)


def test_inlined_per_frame_rand_is_drawn_once_per_frame():
    from prediction_illustration import _evaluate_np, _FrameSiteRandom
    # q30 = int(rand(1000))/1000*6.28 is evaluated once per frame in the engine; every shape instance or
    # control that inlines it must see the same value within the frame (q31 = q30 - 3.14 stays opposite).
    site = lambda i: {'op': 'rand', 'args': [1], 'detail': {'site_index': i, 'equation_phase': 'per_frame_', 'value_binding': 'stateful_random_call'}}
    expr = lambda i: {'root': 0, 'nodes': [site(i), {'op': 'constant', 'args': [], 'detail': {'value': 1000.}}]}
    frame = _FrameSiteRandom(np.random.default_rng(3))
    a = float(_evaluate_np(expr(6), {}, frame)); b = float(_evaluate_np(expr(6), {}, frame))
    c = float(_evaluate_np(expr(4), {}, frame))
    assert a == b and a != c
    nxt = _FrameSiteRandom(np.random.default_rng(4))
    assert float(_evaluate_np(expr(6), {}, nxt)) != a


def test_mesh_term_reads_frame_state_and_zero_for_names_never_written():
    from prediction_illustration import _control_field, _TERM_CONTEXT
    # zoom = 1 + musictime*x + tim  (musictime: per-frame state from the stepper; tim: never written -> 0)
    nodes = [{'op': 'input', 'args': [], 'detail': {'name': 'musictime'}}, {'op': 'input', 'args': [], 'detail': {'name': 'x'}},
             {'op': 'multiply', 'args': [0, 1], 'detail': {}}, {'op': 'input', 'args': [], 'detail': {'name': 'tim'}},
             {'op': 'add', 'args': [2, 3], 'detail': {}}]
    control = {'terms': [{'kind': 'constant', 'value': 1.}, {'kind': 'unresolved_inputs', 'expression': {'root': 4, 'nodes': nodes}}], 'value_range': None}
    x, y = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 3))
    _TERM_CONTEXT.update(rng=np.random.default_rng(1), bands={'bass': 1.}, stage={'musictime': 2.})
    try:
        assert np.allclose(_control_field(control, 'zoom', x, y, 0.), 1 + 2 * x)
    finally:
        for key in ('rng', 'bands', 'stage'): _TERM_CONTEXT.pop(key, None)


def test_mesh_term_with_eel_bitwise_operations_is_evaluated_not_held_neutral():
    # The evaluator supports EEL '&'/'|' (eel_memory); a per-pixel term using them must move the mesh
    # rather than hold the whole control at its neutral value (r90: zoom/rot frozen at 1/0).
    from prediction_illustration import _control_field, _TERM_CONTEXT, _UNRESOLVED_TERMS
    # zoom = 1 + (3 & 1) * 0.1 * x
    nodes = [{'op': 'constant', 'args': [], 'detail': {'value': 3.}}, {'op': 'constant', 'args': [], 'detail': {'value': 1.}},
             {'op': 'eel_bitwise_and', 'args': [0, 1], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': .1}},
             {'op': 'multiply', 'args': [2, 3], 'detail': {}}, {'op': 'input', 'args': [], 'detail': {'name': 'x'}},
             {'op': 'multiply', 'args': [4, 5], 'detail': {}}]
    control = {'terms': [{'kind': 'constant', 'value': 1.}, {'kind': 'unresolved_inputs', 'expression': {'root': 6, 'nodes': nodes}}], 'value_range': None}
    x, y = np.meshgrid(np.linspace(0, 1, 5), np.linspace(0, 1, 3))
    _TERM_CONTEXT.update(rng=np.random.default_rng(1), bands={}, stage={})
    _UNRESOLVED_TERMS.clear()
    try:
        assert np.allclose(_control_field(control, 'zoom', x, y, 0.), 1 + .1 * x)
        assert not any('held whole' in t for t in _UNRESOLVED_TERMS)
    finally:
        for key in ('rng', 'bands', 'stage'): _TERM_CONTEXT.pop(key, None)


def _constant_mesh(**overrides):
    values = {'zoom': 1., 'zoomexp': 1., 'rot': 0., 'warp': 0., 'cx': .5, 'cy': .5, 'dx': 0., 'dy': 0., 'sx': 1., 'sy': 1., **overrides}
    return {'controls': {name: {'status': 'described', 'terms': [{'kind': 'constant', 'value': v}], 'value_range': None}
                         for name, v in values.items()}}


def test_negative_zoom_with_fractional_power_samples_the_origin_only_where_undefined():
    # Engine (MilkDrop CPU powf, patch 0015): a negative zoom keeps a defined signed result for an
    # integer nested power (zoomexp 1: the zoom itself) and NaN for a fractional one. Triangles touching
    # a NaN vertex sample far outside (Apple-observed NaN mesh rule): texture coordinate 0. The rest of
    # the field stays illustrated instead of the whole field being abandoned (r90).
    from prediction_illustration import _backward_map, _UNRESOLVED_TERMS
    _UNRESOLVED_TERMS.clear()
    map_x, map_y = _backward_map(_constant_mesh(zoom=-.5, zoomexp=1.5), 32, 18, grid=(4, 2))(0.)
    assert np.all(map_x == -.5) and np.all(map_y == -.5)
    assert any('nonfinite' in t for t in _UNRESOLVED_TERMS)
    # zoomexp exactly 1: the signed zoom reflects the sample (defined, no substitution).
    _UNRESOLVED_TERMS.clear()
    map_x, _ = _backward_map(_constant_mesh(zoom=-.5, zoomexp=1.), 32, 18, grid=(4, 2))(0.)
    assert np.all(np.isfinite(map_x)) and not any('nonfinite' in t for t in _UNRESOLVED_TERMS)


def test_main_warp_clamps_to_the_edge_texel_when_texture_wrap_is_off():
    # bTexWrap=0: a zoom-out samples beyond the texture; GL_CLAMP_TO_EDGE repeats the edge texel (a border
    # colour fills the outside), while wrap repeats the opposite side (r94's solid star blob).
    import prediction_illustration as P
    mesh = {**_constant_mesh(zoom=.5), 'texture_wrap': 0}
    facts = {'/analysis/visual_description/static_behaviour/mesh_field': mesh,
             '/analysis/visual_description/static_behaviour/context': {'viewport': [32, 18]}}
    assert P._main_wrap(facts, {}) is False
    assert P._main_wrap({**facts, '/analysis/visual_description/static_behaviour/mesh_field': {**mesh, 'texture_wrap': 1}}, {}) is True
    # A per-frame wrap write overrides the header value.
    assert P._main_wrap(facts, {'wrap': 1.}) is True


def test_overlapping_motion_vectors_compound_their_alpha():
    # Motion vectors are alpha-blended GL lines: where two vectors cross the same pixels the blends
    # compound (.5 then .75), as for line waves (r95: long overlapping vectors under a large rotation).
    from prediction_illustration import _draw_motion_vectors
    image = np.zeros((10, 40, 3), np.float32)
    marks = [((5., 5.), (35., 5.), None), ((5., 5.), (35., 5.), None)]
    out = _draw_motion_vectors(image, marks, (1., 1., 1., .5))
    assert np.allclose(out[5, 10:30, 0], .75, atol=1e-6) or np.allclose(out[4, 10:30, 0], .75, atol=1e-6)
    assert image.max() == 0.  # the input canvas is not modified in place


def test_conditionally_active_borders_follow_the_per_frame_alpha():
    # active null: the alpha range includes 0 (r95: ib_a = bass_att*0.2 only on bass). The border is drawn
    # with the frame's stepped alpha, and not at all when that alpha is 0; active false stays off.
    from prediction_illustration import _dynamic_border_operators
    row = {'border': 'outer', 'alpha_range': [0., .4], 'rgb_ranges': [[0., 0.]] * 3, 'active': None, 'inverted_inner_radius': False}
    facts = {'/analysis/visual_description/static_behaviour/borders': {'status': 'described', 'borders': [row],
             'control_ranges': {'ob_size': [.5, .5], 'ob_r': [0., 0.], 'ob_g': [0., 0.], 'ob_b': [0., 0.], 'ob_a': [0., .4]}}}
    (mask, colour), = _dynamic_border_operators(facts, 8, 8, {'ob_a': .3})
    assert np.isclose(mask.max(), .3) and np.all(colour == 0)
    assert _dynamic_border_operators(facts, 8, 8, {'ob_a': 0.})[0][0].max() == 0.
    row['active'] = False
    assert _dynamic_border_operators(facts, 8, 8, {'ob_a': .3}) == []


def test_noise_textures_are_rgba_with_random_alpha_and_shaders_read_it():
    # MilkdropNoise fills all four bytes; a shader offsetting by N.zw = noise*2-1 must see a zero-mean w,
    # not a padded alpha of 1 (which shifts the image half a texel every frame, r70).
    import prediction_illustration as P
    lq = P._noise_texture('noise_lq')
    assert abs(float(lq[..., 3].mean()) - .5) < .01 and lq[..., 3].std() > .25
    # Smoothed textures use MilkDrop's 216-value range wrapped into 8 bits (mean about 0.53).
    assert abs(float(P._noise_texture('noise_hq')[..., 3].mean()) - .529) < .03
    from test_source_stage_program import evaluate
    out = evaluate('warp', 'shader_body{ret=tex2D(sampler_noise_lq, uv*7.3).w;}', image_value=0.)
    assert abs(float(out.mean()) - .5) < .1


def test_per_frame_decay_is_used_each_frame_and_clamped_like_per_pixel_mesh():
    # Fitting Butterfly writes decay = decay + sin(bass_att) every frame: the static persistence is
    # unknown, but each frame's value is known; PerPixelMesh clamps it with min(decay, 1).
    from prediction_illustration import _feedback_gain
    assert _feedback_gain({'decay': 1.37}, None, per_frame=True) == 1.
    assert _feedback_gain({'decay': .8}, .5, per_frame=True) == .8
    assert _feedback_gain({'decay': -.2}, .5, per_frame=True) == 0.
    assert _feedback_gain({'decay': .8}, .5, per_frame=False) == .5


def test_random_texture_slots_use_the_mean_of_matching_bundled_images():
    # projectM picks one bundled image per randNN slot at each load; the expectation over that choice is
    # the per-pixel mean of the candidates, far smoother than the noise stand-in used before (r81).
    import prediction_illustration as P
    any_image = P._random_texture_standin('rand00')
    noise = P._noise_texture('noise_mq')[..., :3]
    assert any_image.shape == (256, 256, 3)
    assert np.abs(np.diff(any_image, axis=1)).mean() < np.abs(np.diff(noise, axis=1)).mean() / 2
    names = [n for n in P._texture_names() if n.startswith('cells')]
    if names:
        filtered = P._random_texture_standin('rand03_cells')
        assert not np.allclose(filtered, any_image)


def test_shapes_with_per_frame_side_counts_are_drawn_with_the_clamped_frame_value():
    # Hexcollie Surge: sides = int(abs(sin(time*.5)*7)) on a full-screen textured triangle. The static side
    # count is unknown, so the shape was dropped and the canvas turned white; CustomShape clamps to [3, 100].
    import prediction_illustration as P
    base = '/analysis/visual_description/elements/2'
    facts = {base + '/material': {'texture': {'role': 'previous_main'}, 'centre_vertex_rgba': [1, 1, 1, .5]},
             base + '/geometry': {'effective_sides': None, 'configured_instances': 1},
             base + '/motion_controls/0': {'control': 'side_count', 'constant_value': None,
                                           'expression': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 1.7}}]}}}
    shape, = P._textured_shapes(facts, {})
    assert shape['sides'] is None and P._shape_sides(shape, 0., {}) == 3
    shape['controls']['side_count']['expression']['nodes'][0]['detail']['value'] = 6.9
    assert P._shape_sides(shape, 0., {}) == 6
    assert not P._textured_shapes({k: v for k, v in facts.items() if 'motion_controls' not in k}, {})


def test_motion_vector_colour_follows_the_per_frame_program():
    # suplient (r83): mv_r/g/b = sin(...)/2+.5 and mv_a = bass_att*.4 are written each frame; the static
    # colour is unresolved, which drew opaque white vectors and a grey canvas.
    import prediction_illustration as P
    facts = {'/analysis/visual_description/static_behaviour/motion_vectors': {'colour_rgba': [None, None, None, [0., .8]]}}
    held = {'mv_r': .9, 'mv_g': .2, 'mv_b': 1.4, 'mv_a': .3}
    assert P._mv_rgba(facts, held, {'mv_r', 'mv_g', 'mv_b', 'mv_a'}) == [.9, .2, 1., .3]
    assert P._mv_rgba(facts, {}, set()) == [1., 1., 1., .4]  # unresolved colour stays white; alpha range midpoint
    static = {'/analysis/visual_description/static_behaviour/motion_vectors': {'colour_rgba': [.38, .38, .27, .03]}}
    assert P._mv_rgba(static, held, set()) == [.38, .38, .27, .03]


def test_texture_lookup_fast_path_matches_the_reference_bilinear_and_nearest_rules():
    # Speed (offline facet precompute): the C-level lookup must give the same GL bilinear/nearest values
    # as the reference formula for wrapped and clamped coordinates, including out-of-range ones.
    import prediction_illustration as P
    rng = np.random.default_rng(5)
    source = rng.random((17, 23, 4)).astype(np.float32)
    coords = rng.uniform(-1.3, 2.4, (500, 2))
    for wrap in (True, False):
        for linear in (True, False):
            fast = P._texture_lookup(source, coords, wrap=wrap, linear=linear)
            ref = P._texture_lookup_reference(source, coords, wrap=wrap, linear=linear)
            assert np.allclose(fast, ref, atol=2e-6), (wrap, linear)


def test_seeded_illustrations_draw_per_load_randomness_reproducibly():
    # Facet precompute: per-load randomness (hue offsets, noise, rand) is sampled per seed. Without a seed
    # the illustration is unchanged; a seed is reproducible; different seeds draw different hue offsets.
    import prediction_illustration as P
    assert P._hue_offsets(None) == (0., 0., 0., 0.)
    a, b = P._hue_offsets(1), P._hue_offsets(2)
    assert a == P._hue_offsets(1) and a != b
    assert all(0 <= v < limit for v, limit in zip(a, (648.41, 537.51, 426.61, 315.71)))
    lq0 = P._noise_texture('noise_lq')
    P._SEED[0] = 3
    try:
        lq3 = P._noise_texture('noise_lq')
        assert not np.array_equal(lq0, lq3) and abs(float(lq3[..., 3].mean()) - .5) < .01
    finally:
        P._SEED[0] = None
    assert np.array_equal(P._noise_texture('noise_lq'), lq0)


def test_milkdrop_cubic_interpolation_is_per_byte_clamped_and_truncated():
    from prediction_illustration import _dw_cubic
    # fCubicInterpolate(a0=y3-y2-y0+y1, a1=y0-y1-a0, a2=y2-y0, a3=y1) on bytes/255; clamp; (uint32)(f*255).
    out = _dw_cubic(*[np.array([[v, v, v, v]], np.uint8) for v in (0, 255, 255, 0)], .5)
    f = (0 - 1 - 0 + 1) * .125 + (0 - 1 - 0) * .25 + (1 - 0) * .5 + 1
    assert out.dtype == np.uint8 and out[0, 0] == int(min(1., f) * 255)
    assert _dw_cubic(*[np.array([[v] * 4], np.uint8) for v in (40, 80, 120, 160)], 0.)[0, 0] == 80


def test_noise_2d_keeps_lattice_texels_and_smooths_between():
    from prediction_illustration import _milkdrop_noise_2d
    raw, smooth = _milkdrop_noise_2d(np.random.default_rng(5), 32, 4, keep_raw=True)
    assert smooth.shape == (32, 32, 4) and smooth.dtype == np.uint8
    assert np.array_equal(smooth[::4, ::4], raw[::4, ::4])
    assert not np.array_equal(smooth[1::4], raw[1::4])


def test_noise_volume_smoothing_touches_only_the_first_two_slices():
    # MilkdropNoise::generate3D indexes z*size instead of z*size*size: every smoothing access lands below flat
    # index 2048, so slices 2..31 keep the raw bytes, (rand % 216) + 108 wrapped to 108..255 and 0..67.
    from prediction_illustration import _milkdrop_noise_3d
    raw, volume = _milkdrop_noise_3d(np.random.default_rng(3), 32, 4, keep_raw=True)
    assert np.array_equal(volume[2:], raw[2:])
    assert not np.array_equal(volume[:2], raw[:2])
    values = set(np.unique(volume[2:]).tolist())
    assert values <= set(range(0, 68)) | set(range(108, 256)) and 0 in values and 255 in values


def test_shape_blend_follows_the_frame_additive_value():
    from prediction_illustration import _shape_blend
    expression={'root':0,'nodes':[{'op':'input','dtype':'float','args':[],'detail':{'name':'q1'}}]}
    shape={'blend':None,'flags':{'additive':expression}}
    assert _shape_blend(shape,{'q1':1.},0.) == 'source_alpha_additive'
    assert _shape_blend(shape,{'q1':.9},0.) == 'source_alpha_over'  # (int) truncation
    assert _shape_blend({'blend':'source_alpha_over','flags':{}},{},0.) == 'source_alpha_over'
    assert _shape_blend({'blend':None,'flags':{}},{},0.) is None


def test_inlined_eel_loops_fold_to_their_frame_value_before_grid_evaluation():
    # A Q graph with a projectm-eval loop reaches a shader program; the grid evaluator runs shader loops
    # only, so the loop (no pixel inputs) is evaluated once for the frame and enters as a constant.
    from test_eel_memory import seq, assign, var, num, call, lowered
    from source_stage_program import serialise
    from prediction_illustration import _fold_eel_loops
    tree = seq(assign(var('s'), num(0)), call('loop', num(3), assign(var('s'), call('_add', var('s'), var('b')))))
    loop = serialise(lowered(tree).environment['s'])
    assert any(n['op'].startswith('loop_eel') for n in loop['nodes'])
    nodes = list(loop['nodes']); base = len(nodes)
    nodes.append({'op': 'input', 'dtype': 'float', 'args': [], 'detail': {'name': '_uv'}})
    nodes.append({'op': 'multiply', 'dtype': 'float', 'args': [loop['root'], base], 'detail': {}})
    program = {'root': base + 1, 'nodes': nodes, 'plans': loop.get('plans', [])}
    folded = _fold_eel_loops(program, {'b': 2.})
    root = folded['nodes'][folded['root']]
    constant = folded['nodes'][root['args'][0]]
    assert constant['op'] == 'constant' and constant['detail']['value'] == 6.
    assert folded['nodes'][root['args'][1]]['detail']['name'] == '_uv'
    assert program['nodes'][loop['root']]['op'] != 'constant'  # the exported program is not edited


def test_point_state_restarts_t_and_q_from_their_frame_start_values():
    from prediction_illustration import _restart_point_state
    constant=lambda v:{'root':0,'nodes':[{'op':'constant','dtype':'float','args':[],'detail':{'value':v}}]}
    points={'state':{'t3':{'frame_start':constant(0.)},'mx':{}}}
    assert _restart_point_state(points,{'t3':111.,'mx':7.},{}) == {'t3':0.,'mx':7.}


def test_constant_inner_border_follows_a_per_frame_outer_size():
    # ib colour/alpha are constant but its band [1-ob_size-ib_size, 1-ob_size] moves with a per-frame
    # ob_size (no static ndc_band): it is drawn on the per-frame path, never dropped.
    from prediction_illustration import _dynamic_border_operators, _sprite_operators
    record = {'status': 'described', 'control_ranges': {'ob_size': [0., .05], 'ib_size': [.1, .1]},
              'borders': [{'border': 'outer', 'alpha_range': [1., 1.], 'rgb_ranges': [[.2, .4], [.4, .4], [.2, .2]], 'active': True, 'ndc_band': None},
                          {'border': 'inner', 'alpha_range': [1., 1.], 'rgb_ranges': [[0., 0.], [0., 0.], [0., 0.]], 'active': True, 'ndc_band': None}]}
    facts = {'/analysis/visual_description/static_behaviour/borders': record}
    assert _sprite_operators(facts, 20, 20) == []
    ops = _dynamic_border_operators(facts, 20, 20, {'ob_size': 0., 'ib_size': .1, 'ob_a': 1., 'ib_a': 1., 'ob_r': .3, 'ob_g': .4, 'ob_b': .2,
                                                     'ib_r': 0., 'ib_g': 0., 'ib_b': 0.})
    inner = ops[-1]
    assert np.allclose(inner[1], 0.) and inner[0][10, 0] == 1. and inner[0][10, 10] == 0.


def test_legacy_display_uses_the_frames_stepped_gamma():
    # Patch 0049: the engine redraws with this frame's evaluated gamma; a loose static range [0, 8]
    # (gamma = 1 + beatdrop*.28) must not brighten every frame by its midpoint.
    from prediction_illustration import _composite
    facts = {'/x/legacy_response': {'native_control_ranges': {'gamma': [0., 8.], 'echo_alpha': [0., 0.]},
                                    'echo_selection': 'native gamma-only branch', 'gamma_absolute_weight_sum_upper': 8.}}
    image = np.full((4, 4, 3), .1, np.float32)
    shown, _ = _composite(image, facts, {'gamma': 1.})
    assert np.allclose(shown, .1)
    shown, _ = _composite(image, facts, {'gamma': 1.28})
    assert np.allclose(shown, .128, atol=1e-6)


def test_builtin_wave_controls_prefer_the_frames_stepped_values():
    # Waveform::Draw reads wave_mystery/x/y from the main per-frame context after its code ran: a stepped
    # value (here -1: a vertical mode-6 line) wins over an expression the time/band evaluator cannot run.
    from prediction_illustration import _builtin_wave_frame
    unevaluable = {'root': 0, 'nodes': [{'op': 'rand', 'dtype': 'float', 'args': [1], 'detail': {}},
                                        {'op': 'constant', 'dtype': 'float', 'args': [], 'detail': {'value': 60.}}]}
    recipe = {'effective_mode': 6, 'control_expressions': {'wave_mystery': unevaluable}, 'wave_x': .5, 'wave_y': .5}
    bands = {'bass': 1., 'mid': 1., 'treb': 1.}
    lines, _ = _builtin_wave_frame(recipe, 1., 30, bands, (480, 270), stepped={'wave_mystery': -1.})
    xs = lines[0][:, 0]
    assert np.ptp(xs) < .3 * np.ptp(lines[0][:, 1])


def test_cold_stream_follows_projectm_eval_rand():
    # projectm-eval rand(n): MilkDrop's Mersenne Twister (seed 0x4141f00d), genrand_int32 / 0xFFFFFFFF * n.
    from prediction_illustration import _cold_eval_stream
    stream = _cold_eval_stream()
    assert int(stream.random() * 60) == 13 and int(stream.random() * 60) == 20
    assert abs(float(_cold_eval_stream().random()) - 978073627 / 4294967295) < 1e-12


def test_unevaluable_blend_flag_falls_back_to_unset_inputs_reading_zero():
    # A flag whose inputs are missing must not drop the shape: projectm-eval reads unset variables as 0.
    from prediction_illustration import _shape_blend
    expression = {'root': 0, 'nodes': [{'op': 'input', 'dtype': 'float', 'args': [], 'detail': {'name': 'flip'}}]}
    assert _shape_blend({'blend': None, 'flags': {'additive': expression}}, {}, 0.) == 'source_alpha_over'


def test_motion_vectors_with_per_frame_grid_counts_use_the_frames_values():
    # mv_x written per frame (Martin - QBikal - Surface Turbulence: 54-64 on beats) leaves no static grid;
    # the frame's stepped counts give MotionVectors' grid (source_motion_vector_element._positions).
    from prediction_illustration import _motion_vector_marks
    facts = {'/analysis/visual_description/static_behaviour/motion_vectors': {'status': 'partial', 'activation': 'possible',
             'control_ranges': {'mv_a': [.5, .5], 'mv_x': None, 'mv_y': [48., 48.], 'mv_dx': [0., 0.], 'mv_dy': [0., 0.], 'mv_l': [.85, .85]}}}
    W, H = 64, 48
    maps = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    marks = _motion_vector_marks(facts, lambda t: maps, 1., W, H, maps, controls={'mv_x': 12., 'mv_y': 9., 'mv_a': .5, 'mv_l': .85, 'mv_dx': 0., 'mv_dy': 0.})
    from source_motion_vector_element import _positions
    # MotionVectors keeps positions strictly inside (.0001, .9999): an integer count's last position is 1.
    assert len(marks) == len(_positions(12., 0., 1, 64)) * len(_positions(9., 0., -1, 48)) == 11 * 8
    assert _motion_vector_marks(facts, lambda t: maps, 1., W, H, maps, controls={'mv_x': 12., 'mv_y': 9., 'mv_a': 0.}) == []


def test_legacy_filters_follow_the_frames_evaluated_flags():
    # Patch 0008 on main: brighten/darken/solarize/invert come from each frame's evaluated value; a toggled
    # invert (range [0, 1]) inverts exactly the frames that set it.
    from prediction_illustration import _composite
    facts = {'/x/legacy_response': {'native_control_ranges': {'invert': [0., 1.], 'echo_alpha': [0., 0.]},
                                    'echo_selection': 'native gamma-only branch', 'gamma_absolute_weight_sum_upper': 1.}}
    image = np.full((2, 2, 3), .2, np.float32)
    assert np.allclose(_composite(image, facts, {'invert': 1.})[0], .8)
    assert np.allclose(_composite(image, facts, {'invert': 0.})[0], .2)


def test_builtin_wave_mode_and_flags_follow_the_frame():
    # Patch 0007 on main: wave_mode (truncated, remainder over 16 modes) and dots/thick/additive come from
    # the evaluated frame; a static recipe value is used when the frame program does not write them.
    from prediction_illustration import _frame_wave_mode, _frame_wave_flags
    outputs = {'wave_mode', 'wave_usedots', 'wave_thick', 'wave_additive'}
    assert _frame_wave_mode({'effective_mode': None}, {'wave_mode': 22.7}, outputs) == 6
    assert _frame_wave_mode({'effective_mode': 3}, {'wave_mode': 5.}, set()) == 3
    assert _frame_wave_mode({'effective_mode': None}, {}, set()) is None
    held = {'wave_usedots': 1., 'wave_thick': 0., 'wave_additive': .5}
    assert _frame_wave_flags({'dots': False, 'thick': True}, held, outputs, False) == (True, False, True)
    assert _frame_wave_flags({'dots': False, 'thick': True}, {}, set(), False) == (False, True, False)


def test_cold_stream_skips_draws_of_other_blocks_in_engine_order():
    # A shape init draw at load and per-frame wave draws take values from the same projectm-eval stream: the
    # main per-frame rand reads the stream after them (Willie Wonka: shape_0_init red=rand(20)).
    import numpy as np
    from prediction_illustration import _FrameStepper
    rand = {'root': 0, 'nodes': [{'op': 'rand', 'args': [1], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 1.}}]}
    program = {'state': {}, 'outputs': {'q1': rand}}
    raw = np.random.RandomState(0x4141f00d)._bit_generator.random_raw(20).astype(np.float64) / 4294967295.
    stepper = _FrameStepper(program, rng_seed=None, rand_skips=(1, 2))
    first = stepper.step(1 / 30, 30, {}, 0)['q1']; second = stepper.step(2 / 30, 30, {}, 1)['q1']
    assert abs(first - raw[1]) < 1e-12 and abs(second - raw[4]) < 1e-12


def test_stepper_draws_rand_sites_in_statement_order_and_shares_copies():
    # per_frame_init: index4=int(rand(2)); index3=int(rand(4)) (suksma byT). The engine draws site 0 then site 1
    # whatever order the state variables are listed in, and a variable that copies a site reads the same draw.
    import numpy as np
    from prediction_illustration import _FrameStepper
    def rand_site(site, phase, limit):
        return {'root': 0, 'nodes': [{'op': 'rand', 'args': [1], 'detail': {'site_index': site, 'equation_phase': phase}},
                                     {'op': 'constant', 'args': [], 'detail': {'value': limit}}]}
    keep = lambda name: {'root': 0, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': name}}]}
    state = {'a_late': {'initial': rand_site(1, 'per_frame_init_', 100.), 'update': keep('a_late')},
             'b_copy': {'initial': rand_site(0, 'per_frame_init_', 100.), 'update': keep('b_copy')},
             'c_early': {'initial': rand_site(0, 'per_frame_init_', 100.), 'update': keep('c_early')}}
    outputs = {'q1': rand_site(1, 'per_frame_', 1.), 'q2': rand_site(0, 'per_frame_', 1.)}
    raw = np.random.RandomState(0x4141f00d)._bit_generator.random_raw(8).astype(np.float64) / 4294967295.
    values = _FrameStepper({'state': state, 'outputs': outputs}, rng_seed=None).step(1 / 30, 30, {}, 0)
    assert abs(values['c_early'] - 100 * raw[0]) < 1e-9 and values['b_copy'] == values['c_early']
    assert abs(values['a_late'] - 100 * raw[1]) < 1e-9
    assert abs(values['q2'] - raw[2]) < 1e-12 and abs(values['q1'] - raw[3]) < 1e-12


def test_stepper_guarded_rand_site_draws_only_when_its_branch_runs():
    # q1=if(0, rand(1), 5); q2=rand(1): the guarded site never runs, so q2 reads the first draw.
    import numpy as np
    from prediction_illustration import _FrameStepper
    guarded = {'root': 0, 'nodes': [{'op': 'select', 'args': [1, 2, 4], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 0.}},
                                    {'op': 'rand', 'args': [3], 'detail': {'site_index': 0, 'equation_phase': 'per_frame_'}},
                                    {'op': 'constant', 'args': [], 'detail': {'value': 1.}}, {'op': 'constant', 'args': [], 'detail': {'value': 5.}}]}
    plain = {'root': 0, 'nodes': [{'op': 'rand', 'args': [1], 'detail': {'site_index': 1, 'equation_phase': 'per_frame_'}},
                                  {'op': 'constant', 'args': [], 'detail': {'value': 1.}}]}
    raw = np.random.RandomState(0x4141f00d)._bit_generator.random_raw(4).astype(np.float64) / 4294967295.
    values = _FrameStepper({'state': {}, 'outputs': {'q1': guarded, 'q2': plain}}, rng_seed=None).step(1 / 30, 30, {}, 0)
    assert values['q1'] == 5. and abs(values['q2'] - raw[0]) < 1e-12


def test_custom_wave_sample_count_follows_its_per_frame_program():
    # samples = 256 + 50*sin(time) each frame, clamped to 0..512 and truncated as CustomWaveform does.
    import math
    from prediction_illustration import _frame_sample_count
    program = {'root': 0, 'nodes': [{'op': 'add', 'args': [1, 2], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 256.}},
                                    {'op': 'multiply', 'args': [3, 4], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 50.}},
                                    {'op': 'sin', 'args': [5], 'detail': {}}, {'op': 'input', 'args': [], 'detail': {'name': 'time'}}]}
    record = {'sample_count': 256, 'sample_count_program': program}
    assert _frame_sample_count(record, {}, 1.) == math.trunc(256 + 50 * math.sin(1.))
    assert _frame_sample_count({'sample_count': 102}, {}, 1.) == 102
    big = {'sample_count': 256, 'sample_count_program': {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': 900.}}]}}
    assert _frame_sample_count(big, {}, 1.) == 512


def _reference_gl_line_pixels(x0, y0, x1, y1, width, height):
    # The per-exit loop the vectorised rasteriser replaced (same diamond-exit rule).
    import numpy as np
    x0, y0, x1, y1 = (np.asarray(v, np.float64).ravel() for v in (x0, y0, x1, y1))
    dx, dy = x1 - x0, y1 - y0; xmajor = np.abs(dx) >= np.abs(dy)
    a0 = np.where(xmajor, x0, y0); a1 = np.where(xmajor, x1, y1); b0 = np.where(xmajor, y0, x0); b1 = np.where(xmajor, y1, x1)
    step = np.where(a1 >= a0, 1., -1.); span = np.abs(a1 - a0)
    first = np.where(step > 0, np.floor(a0) + 1, np.ceil(a0) - 1)
    out = set()
    for k in range(int(np.ceil(span.max())) + 1 if len(span) else 0):
        exit_ = first + step * k; offset = (exit_ - a0) * step
        keep = (offset > 0) & (offset <= span)
        centre = exit_ - .5 * step
        t = np.clip(np.where(span > 0, (centre - a0) * step / np.where(span > 0, span, 1.), 0.), 0, 1)
        minor = np.floor(b0 + (b1 - b0) * t); major = np.floor(centre)
        col = np.where(xmajor, major, minor); row = np.where(xmajor, minor, major)
        for s in np.nonzero(keep)[0]:
            if 0 <= col[s] < width and 0 <= row[s] < height:out.add((int(row[s]), int(col[s]), int(s)))
    return out


def test_vectorised_line_raster_matches_the_per_exit_rule_including_off_screen_segments():
    import numpy as np
    from prediction_illustration import _gl_line_pixels
    rng = np.random.default_rng(7)
    for scale in (1., 5., 40.):
        x0, x1 = rng.uniform(-scale * 64, scale * 64, (2, 300)) + 32; y0, y1 = rng.uniform(-scale * 36, scale * 36, (2, 300)) + 18
        rows, cols, seg = _gl_line_pixels(x0, y0, x1, y1, 64, 36, return_index=True)
        assert set(zip(rows.tolist(), cols.tolist(), seg.tolist())) == _reference_gl_line_pixels(x0, y0, x1, y1, 64, 36)
        assert len(rows) == len(set(zip(rows.tolist(), cols.tolist(), seg.tolist())))
    # Degenerate and exactly integer-aligned segments.
    x0 = np.array([3., 3., 2.5, 10.]); y0 = np.array([3., 3., 2.5, 1.]); x1 = np.array([3., 9., 2.5, 10.]); y1 = np.array([3., 3., 7.5, 30.])
    rows, cols, seg = _gl_line_pixels(x0, y0, x1, y1, 64, 36, return_index=True)
    assert set(zip(rows.tolist(), cols.tolist(), seg.tolist())) == _reference_gl_line_pixels(x0, y0, x1, y1, 64, 36)


def test_line_segments_with_non_finite_endpoints_draw_nothing():
    # A NaN or infinite vertex has no defined raster; casting NaN to int is platform-dependent (it can land on 0).
    import numpy as np
    from prediction_illustration import _gl_line_pixels
    nan, inf = float('nan'), float('inf')
    rows, cols, seg = _gl_line_pixels([nan, 5., 2., 1.], [3., nan, 2., 1.], [10., 20., inf, 30.], [3., 3., 2., 1.], 64, 36, return_index=True)
    assert set(seg.tolist()) == {3} and len(rows) == 29


def _shape_record(radius, angle, textured=False):
    const = lambda name, value: {'control': name, 'constant_value': value}
    channel = lambda v: {'op_dummy': None} if False else {'root': 0, 'nodes': [{'op': 'constant', 'args': [], 'detail': {'value': v}}]}
    return {'controls': {'position_x': const('position_x', .45), 'position_y': const('position_y', .55),
                         'radius': const('radius', radius), 'rotation': const('rotation', angle)},
            'texture': {'tex_zoom_source': .7, 'tex_angle_source_rad': .4}, 'sides': 5, 'textured': textured,
            'channels': {'centre': {'r': channel(1.), 'g': channel(.2), 'b': channel(.1), 'a': channel(1.)},
                         'perimeter': {'r2': channel(.1), 'g2': channel(.3), 'b2': channel(1.), 'a2': channel(.6)},
                         'border': {}},
            'blend': 'source_alpha_over', 'flags': {}, 'held': {}, 'thick_outline': False}


def test_negative_shape_radius_draws_the_point_mirrored_polygon():
    # CustomShape places vertices at centre + rad*(cos t, sin t): a negative rad mirrors the polygon through its
    # centre (same as |rad| with ang + pi) while texture coordinates keep their angles. It is drawn, not skipped.
    import math
    import numpy as np
    from prediction_illustration import _draw_textured_shape
    rng = np.random.default_rng(1)
    canvas = rng.random((36, 64, 3)).astype(np.float32)
    for textured in (False, True):
        negative, drawn = _draw_textured_shape(canvas.copy(), _shape_record(-.3, .2, textured), 1., True, canvas)
        mirrored, _ = _draw_textured_shape(canvas.copy(), _shape_record(.3, .2 + math.pi, textured), 1., True, canvas)
        assert drawn and not np.array_equal(negative, canvas)
        assert np.allclose(negative, mirrored, atol=1e-5)


def test_per_pixel_terms_read_the_frames_memory_and_unwritten_memory_as_zero(monkeypatch):
    # martin + flexi - carpet weaver bipolar 02: per-pixel code reads megabuf. Per-frame writes must be visible;
    # memory nobody wrote reads 0 (an empty Memory, not a plain number the reader cannot index).
    import prediction_illustration as P
    from eel_memory import Memory, evaluate_np
    expression = {'root': 0, 'nodes': [{'op': 'array_mem_read', 'args': [1, 2], 'detail': {}},
                                       {'op': 'input', 'args': [], 'detail': {'name': 'memory:global'}},
                                       {'op': 'constant', 'args': [], 'detail': {'value': 3.}}]}
    monkeypatch.setitem(P._TERM_CONTEXT, 'stage', {'memory:global': Memory().write(3, .7), 'q1': 2.})
    assert float(evaluate_np(expression, P._term_inputs(expression, {}))) == .7
    monkeypatch.setitem(P._TERM_CONTEXT, 'stage', {})
    assert float(evaluate_np(expression, P._term_inputs(expression, {}))) == 0.
