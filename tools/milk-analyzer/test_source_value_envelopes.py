"""Conditional value ranges do not provide unknown input timing."""
import pytest
from test_effect_families import read
from test_source_appearance import appearance
from shader_fields import Field


def shape(body):
    d=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1='+body+'\n'))
    return next(e for e in d['elements'] if e['id']=='shape_0')


def channel(expression):return shape('r='+expression+';')['material_temporal']['channels']['r']


def test_audio_sine_has_bounded_value_but_unknown_time_rate():
    c=channel('.5+.2*sin(bass)')
    assert c['raw_time_curve']['curve_kind']=='unknown'
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None
    assert c['raw_time_curve']['nominal_continuity']=='unknown'
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([.3,.7])
    assert c['possible_native_wrap_jump'] is False
    assert c['raw_time_curve']['value_envelope']['assumed_finite_input_names']==['bass']


def test_state_sine_bounds_preserve_named_finite_input_premise():
    c=channel('.1+.5*sin(k+bass*.03)')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([-.4,.6])
    assert set(c['raw_time_curve']['value_envelope']['assumed_finite_input_names'])=={'bass','k'}
    assert c['possible_native_wrap_jump'] is True
    assert c['raw_time_curve']['period_seconds'] is None


def test_nested_min_max_can_bound_an_unbounded_input_without_audio_domain_guess():
    c=channel('min(max(bass,0),1)')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([0,1])
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None
    assert c['possible_native_wrap_jump'] is False


def test_direct_band_input_has_no_invented_range():
    c=channel('bass')
    assert c['raw_time_curve']['nominal_value_range'] is None
    assert c['possible_native_wrap_jump'] is None


def test_conditional_branch_union_has_bounded_values_without_continuity():
    c=channel('if(above(bass,1),.2,.8)')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([.2,.8])
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None
    assert c['raw_time_curve']['nominal_continuity']=='unknown'


def test_bounded_sine_of_square_has_no_false_rate():
    c=channel('.5+.2*sin(sqr(bass))')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([.3,.7])
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None


def test_singular_or_unknown_effects_are_not_hidden_by_sine_range():
    from source_control_bounds import scalar_value_envelope
    cases=[Field('sin',(Field('unknown',detail={'reason':'unmodeled effect'}),)),
           Field('sin',(Field('divide',(Field('constant',detail={'value':1}),Field('input',detail={'name':'bass'}))),))]
    for field in cases:
        result=scalar_value_envelope(field)
        assert result['nominal_value_range'] is None
        assert result['unknown_reasons']


def test_sine_of_bounded_division_uses_proved_denominator_separation():
    c=channel('.5+.2*sin(bass/(2+sin(mid)))')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([.3,.7])
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None


def test_zero_times_unbounded_finite_input_does_not_emit_nan_interval():
    from source_control_bounds import scalar_value_envelope
    field=Field('multiply',(Field('constant',detail={'value':0}),Field('input',detail={'name':'bass'})))
    result=scalar_value_envelope(field)
    assert result['nominal_value_range']==pytest.approx([0,0])


def test_finite_input_assumption_is_not_a_zero_initialization_or_render_certificate():
    c=channel('.5+.2*cos(k)')
    envelope=c['raw_time_curve']['value_envelope']
    assert envelope['uses_equation_execution'] is False
    assert envelope['uses_rendered_images'] is False
    assert envelope['native_numeric_certified'] is False
    assert envelope['nominal_value_range']==pytest.approx([.3,.7])


def test_known_overflow_inside_bounded_trig_is_not_hidden():
    from source_control_bounds import scalar_value_envelope
    large=Field('constant',detail={'value':1e308})
    field=Field('sin',(Field('multiply',(large,large)),))
    result=scalar_value_envelope(field)
    assert result['nominal_value_range'] is None
    assert result['unknown_reasons']


def test_uninitialized_input_and_random_calls_remain_opaque():
    from source_control_bounds import scalar_value_envelope
    for child in [Field('uninitialized',detail={'name':'mus'}),Field('rand',(Field('constant',detail={'value':10}),))]:
        result=scalar_value_envelope(Field('sin',(child,)))
        assert result['nominal_value_range'] is None


def test_value_bounds_do_not_mark_conditional_colour_changes_smooth():
    c=channel('if(equal(bass,1),.2,.8)')
    assert c['raw_time_curve']['nominal_value_range']==pytest.approx([.2,.8])
    assert c['raw_time_curve']['nominal_continuity']=='unknown'
    assert c['raw_time_curve']['maximum_absolute_control_rate_per_second'] is None


def test_eel_division_by_unproved_denominator_is_finite_under_bounded_trig():
    # projectm-eval returns 0 when |divisor| < 1e-5, so an EEL quotient of finite operands is an arbitrary finite
    # value: cos() of it stays in [-1, 1] (warp centre cx=.5+.6*cos(musictime) with musictime += mid^3*.02*(75/fps)).
    # GLSL division keeps an unproved denominator unknown (undefined at zero).
    from source_control_bounds import scalar_value_envelope
    def quotient(op):
        return Field(op, (Field('input', detail={'name': 'mid'}), Field('input', detail={'name': 'fps'})))
    field = Field('add', (Field('constant', detail={'value': .5}),
                          Field('multiply', (Field('constant', detail={'value': .6}), Field('cos', (quotient('eel_divide'),))))))
    assert scalar_value_envelope(field)['nominal_value_range'] == pytest.approx([-.1, 1.1])
    assert scalar_value_envelope(quotient('eel_divide'))['nominal_value_range'] is None
    assert scalar_value_envelope(Field('cos', (quotient('divide'),)))['nominal_value_range'] is None


def test_arctangent_bounds_any_finite_argument():
    # ag=atan((y-.5+q5)/(x-.5-q4)) about a moving centre: atan maps every finite value into (-pi/2, pi/2),
    # monotonically, and atan2 into [-pi, pi].
    import math
    from source_control_bounds import scalar_value_envelope
    mid, fps = Field('input', detail={'name': 'mid'}), Field('input', detail={'name': 'fps'})
    ratio = Field('eel_divide', (mid, fps))
    assert scalar_value_envelope(Field('atan', (ratio,)))['nominal_value_range'] == pytest.approx([-math.pi / 2, math.pi / 2])
    bounded = Field('atan', (Field('sin', (mid,)),))
    assert scalar_value_envelope(bounded)['nominal_value_range'] == pytest.approx([math.atan(-1), math.atan(1)])
    assert scalar_value_envelope(Field('atan2', (mid, fps)))['nominal_value_range'] == pytest.approx([-math.pi, math.pi])


def test_radius_from_squares_keeps_a_nonnegative_lower_bound():
    # rd=sqrt(sqr(dx)+sqr(dy)): squares, and sums/products of non-negative intervals, are exactly non-negative under
    # IEEE rounding; the outward rounding step must not push 0 to -5e-324 and make sqrt unprovable.
    import math
    from source_control_bounds import scalar_value_envelope
    x, y = Field('input', detail={'name': 'x'}), Field('input', detail={'name': 'y'})
    centred = lambda v: Field('subtract', (v, Field('constant', detail={'value': .5})))
    rd = Field('sqrt', (Field('add', (Field('sqr', (centred(x),)), Field('sqr', (centred(y),)))),))
    span = scalar_value_envelope(rd, input_domains={'x': [0, 1], 'y': [0, 1]})['nominal_value_range']
    assert span[0] == 0. and span[1] == pytest.approx(math.sqrt(.5))
    product = Field('multiply', (Field('sqr', (x,)), Field('sqr', (y,))))
    assert scalar_value_envelope(product, input_domains={'x': [-1, 1], 'y': [-1, 1]})['nominal_value_range'][0] == 0.
