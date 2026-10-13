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
    # hq is smooth (random every 4th texel); lq varies texel to texel.
    lq = _noise_texture('noisevol_lq')
    assert np.abs(np.diff(volume, axis=2)).mean() < np.abs(np.diff(lq, axis=2)).mean()
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
