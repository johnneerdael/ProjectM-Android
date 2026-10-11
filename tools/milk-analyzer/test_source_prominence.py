"""Frozen mathematical prominence controls; no raster frames or audio samples."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

import pytest


def evidence(body='', *, composite='ret=GetPixel(uv);', viewport=(1920,1080), config='', compiled=True, shader_version=2, domains=None, scenario=None):
    import effect_families as ef
    from source_appearance import appearance_from_analysis
    import source_prominence
    raw=('MILKDROP_PRESET_VERSION=201\n[preset00]\nfWaveAlpha=0\n'
         'PSVERSION_COMP='+str(shader_version)+'\ncomp_1=`shader_body {'+composite+'}\n'
         'shapecode_0_enabled=1\nshapecode_0_sides=4\nshapecode_0_rad=.5\n'
         'shapecode_0_a=1\nshapecode_0_a2=1\nshapecode_0_border_a=0\n'+config+
         'shape_0_per_frame1='+body+'\n').encode()
    reader=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'control.milk';path.write_bytes(raw)
        source=json.loads(subprocess.check_output([str(reader),str(path)]))
    source['preset_sha256']=hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    code=source['sections']['comp_']['source']
    compatibility={'composite':{'source_sha256':hashlib.sha256(code.encode()).hexdigest(),
        'request':{'code':code,'stage':'composite','profile':'gles300'},
        'translation':{'engine_archive_sha256':source['parser_inputs']['engine_archive_sha256']},
        'offline_accepted':True}}
    token=ef._CACHE.set({})
    try:
        analysis=ef._Analysis(source,'gles300',compatibility if compiled else None);analysis.input_scenario=scenario
        analysis.main_equations();analysis.primitives()
        analysis.shader('warp','warp_');analysis.shader('composite','comp_');analysis.contribution_gates()
        description=appearance_from_analysis(analysis)
        context={'viewport':list(viewport),'feedback_fps':30}
        if domains is not None:context['scalar_input_domains']=domains
        result=source_prominence.prominence_evidence(analysis,description,context)
    finally:ef._CACHE.reset(token)
    json.dumps(result,allow_nan=False)
    return result['by_component']['shape_0'],result


def test_shape_radius_is_ndc_and_horizontal_aspect_uses_actual_viewport():
    square,_=evidence(viewport=(1080,1080))
    wide,_=evidence()
    portrait,_=evidence(viewport=(1080,1920))
    assert square['support']['area_fraction_interval']==pytest.approx([.125,.125])
    assert wide['support']['area_fraction_interval']==pytest.approx([.125*9/16]*2)
    assert portrait['support']['area_fraction_interval']==pytest.approx([.125,.125])
    assert wide['visible_contrast_interval'][0]==0


def test_half_clipped_polygon_has_half_area_and_offscreen_has_zero():
    centered,_=evidence()
    clipped,_=evidence('x=0;')
    offscreen,_=evidence('x=-2;')
    expected=centered['support']['area_fraction_interval'][1]/2+(.5/math.sqrt(2))/1920/2
    assert clipped['support']['area_fraction_interval']==pytest.approx([expected]*2)
    assert offscreen['support']['area_fraction_interval']==[0,0]
    assert offscreen['displayed_contribution_interval']==[0,0]


def test_viewport_covering_polygon_and_tiny_polygon_keep_quantified_extent():
    large,_=evidence('rad=10;')
    tiny,_=evidence('rad=.001;')
    assert large['support']['area_fraction_interval']==[1,1]
    assert tiny['source_contribution_interval'][1]==pytest.approx(.001**2/2*9/16)
    assert tiny['displayed_contribution_interval'][1]<.00001


def test_transparent_fill_is_zero_but_visible_border_remains_possible():
    transparent,_=evidence('a=0;a2=0;')
    border,_=evidence('a=0;a2=0;border_a=1;')
    assert transparent['displayed_contribution_interval']==[0,0]
    assert border['displayed_contribution_interval'][1]>0
    assert border['unknown_reasons']


def test_coincident_instances_do_not_sum_union_coverage_above_one():
    single,_=evidence()
    repeated,_=evidence(config='shapecode_0_num_inst=20\n')
    assert repeated['support']['area_fraction_interval']==single['support']['area_fraction_interval']
    assert repeated['source_contribution_interval'][1]<=1
    assert repeated['support']['summed_nominal_area_fraction']>1


def test_large_instance_group_has_analytic_tiny_area_bound_without_enumeration():
    row,_=evidence('rad=.001;x=.2+.001*instance;',config='shapecode_0_num_inst=1024\n')
    expected=1024*.001**2*.5*9/16
    assert row['support']['area_fraction_interval'][1]<=expected*1.00001
    assert row['support']['method']=='aggregate polygon area envelope'
    assert len(row['support']['parameter_ranges'])==1
    assert row['support']['configured_instances']==1024


def test_large_instance_radius_domain_includes_every_instance():
    row,_=evidence('rad=.001+.000001*instance;',config='shapecode_0_num_inst=1024\n')
    assert row['support']['area_fraction_interval'][1]>=1024*.002023**2*.5*9/16
    assert row['support']['area_fraction_interval'][1]<.002


def test_large_instance_invalid_position_cannot_be_hidden_by_zero_radius_alpha():
    row,_=evidence('x=1e100;rad=0;a=0;a2=0;',config='shapecode_0_num_inst=1024\n')
    assert row['known_invalid_native_domain']
    assert row['displayed_contribution_interval'][1]>0


def test_large_instance_octagon_bound_encloses_ideal_trig_product():
    from decimal import Decimal
    row,_=evidence('rad=.001;sides=8;',config='shapecode_0_num_inst=1024\n')
    # Independently calculated with 80-digit arithmetic and native float32 rad.
    ideal=Decimal('.0004072935446542592259129667')
    assert Decimal.from_float(row['support']['area_fraction_interval'][1])>=ideal


def test_large_instance_unknown_sides_does_not_get_an_invented_area_bound():
    row,_=evidence('rad=.001;sides=bass;',config='shapecode_0_num_inst=1024\n')
    assert row['support']['area_fraction_interval']==[0.,1.]


def test_large_instance_native_corner_overflow_cannot_be_hidden_by_zero_alpha():
    row,_=evidence('x=1e38;rad=3e38;ang=0;a=0;a2=0;',
                   viewport=(1080,1080),config='shapecode_0_num_inst=1024\n')
    assert row['known_invalid_native_domain']
    assert row['displayed_contribution_interval'][1]>0


def test_large_instance_finite_corner_addition_keeps_zero_alpha_certificate():
    row,_=evidence('x=1e38;rad=1e38;ang=0;a=0;a2=0;',
                   viewport=(1080,1080),config='shapecode_0_num_inst=1024\n')
    assert not row['known_invalid_native_domain']
    assert row['displayed_contribution_interval']==[0.,0.]


def test_separated_instance_overlap_union_has_safe_bounds():
    row,_=evidence('x=.1+.04*instance;',config='shapecode_0_num_inst=20\n')
    assert 0<row['support']['area_fraction_interval'][0]<=row['support']['area_fraction_interval'][1]<=1


def test_translucent_separated_instances_do_not_multiply_summed_area_twice():
    row,_=evidence('x=.1+.04*instance;a=.1;a2=.1;',config='shapecode_0_num_inst=20\n')
    assert row['source_contribution_interval'][1]<=row['support']['summed_clipped_area_fraction_upper']*.100001


@pytest.mark.parametrize('gain',[.01,.5,2])
def test_later_pointwise_composite_transfer_attenuates_or_amplifies(gain):
    row,_=evidence(composite='ret=GetPixel(uv)*'+str(gain)+';')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(gain)
    assert row['displayed_contribution_interval'][1]==pytest.approx(row['displayed_support_fraction_interval'][1]*min(1,gain))


def test_amplification_of_translucent_fill_is_not_clamped_to_input_alpha():
    row,_=evidence('a=.1;a2=.1;',composite='ret=GetPixel(uv)*2;')
    baseline,_=evidence('a=.1;a2=.1;')
    assert row['displayed_contribution_interval'][1]==pytest.approx(baseline['displayed_contribution_interval'][1]*2)


def test_fractional_colour_power_bounds_influence_without_inventing_a_derivative():
    row,_=evidence('a=.01;a2=.01;',composite='ret=pow(GetPixel(uv),.5);')
    transfer=row['final_transfer']
    assert transfer['difference_gain_interval'][1] is None
    assert transfer['sampled_colour_modulus']['status']=='bounded'
    assert row['displayed_contribution_interval'][1]<row['displayed_support_fraction_interval'][1]*.11
    assert row['displayed_contribution_interval'][1]>row['source_contribution_interval'][1]
    assert row['feedback_contribution_interval']==[0,1]


def test_fractional_colour_resampling_uses_local_change_not_tiny_source_integral():
    row,_=evidence('rad=.001;a=.01;a2=.01;',
        composite='ret=pow(GetPixel(float2(.5,.5)),.5);')
    assert row['displayed_support_fraction_interval']==[0,1]
    assert row['displayed_contribution_interval'][1]==pytest.approx(.1,rel=1e-5)


def test_fractional_colour_invalid_incoming_source_cannot_use_conditional_modulus():
    row,_=evidence('rad=1e100;',composite='ret=pow(GetPixel(uv),.5);')
    assert row['known_invalid_native_domain']
    assert row['displayed_contribution_interval']==[0,1]


def test_fractional_colour_history_driven_coordinates_keep_unknown_transfer():
    row,_=evidence('a=.01;a2=.01;',
        composite='ret=pow(GetPixel(uv+GetPixel(uv).xy*.1),.5);')
    assert row['final_transfer']['difference_gain_interval'][1] is None
    assert not row['final_transfer'].get('sampled_colour_modulus')


def test_fractional_colour_blur_modulus_does_not_assume_unit_main_to_blur_gain():
    row,_=evidence('rad=10;a=.0001;a2=.0001;r=g=b=r2=g2=b2=1;',
        composite='ret=pow(GetBlur1(uv),.5);',config='fBlur1Min=0\nfBlur1Max=.01\n')
    assert row['final_transfer']['sampled_colour_modulus']['status']=='bounded'
    assert row['displayed_contribution_interval'][1]>=.1
    assert any('blur' in reason and 'propagation' in reason for reason in row['unknown_reasons'])


@pytest.mark.parametrize('composite',[
    'ret=GetBlur1(uv);',
    'ret=GetBlur1(uv)*GetBlur1(uv);',
    'ret=GetPixel(uv)+GetBlur1(uv);',
    'ret=tex2D(sampler_blur1,uv).rgb;',
    'ret=pow(tex2D(sampler_blur1,uv).rgb,.5);',
    'ret=tex2D(sampler_blur1,uv).rgb*tex2D(sampler_blur1,uv).rgb;',
])
def test_existing_blur_site_gain_is_not_an_incoming_main_gain(composite):
    row,_=evidence('rad=10;a=.1;a2=.1;r=g=b=r2=g2=b2=1;',
        composite=composite,config='fBlur1Min=0\nfBlur1Max=.01\n')
    transfer=row['final_transfer']
    assert transfer['difference_gain_interval'][1] is None
    assert transfer['sample_site_difference_gain_interval'][1] is not None or transfer.get('sampled_colour_modulus',{}).get('status')=='bounded'
    assert row['displayed_contribution_interval'][1]==1
    assert any('blur' in reason and 'propagation' in reason for reason in row['unknown_reasons'])


def test_constant_composite_disconnects_configured_drawing():
    row,_=evidence(composite='ret=float3(.3,.4,.5);')
    assert row['final_transfer']['difference_gain_interval']==[0,0]
    assert row['displayed_contribution_interval']==[0,0]


def test_resampling_tiny_source_can_cover_display_and_history_stays_unknown():
    row,result=evidence('rad=.001;',composite='ret=GetPixel(float2(.5,.5));')
    assert row['displayed_support_fraction_interval']==[0,1]
    assert row['displayed_contribution_interval'][1]==pytest.approx(1)
    assert row['feedback_contribution_interval']==[0,1]
    assert result['uses_rendered_images'] is False


@pytest.mark.parametrize('instances',[2,20])
@pytest.mark.parametrize('additive',[0,1])
def test_resampling_overlapping_instances_bounds_aggregate_per_texel_influence(instances,additive):
    row,_=evidence('a=.1;a2=.1;r=g=b=r2=g2=b2=1;',
        config=f'shapecode_0_num_inst={instances}\nshapecode_0_additive={additive}\n',
        composite='ret=GetPixel(float2(.5,.5));')
    alpha=row['opacity']['interval'][1]
    realized_ceiling=min(1,instances*alpha) if additive else 1-(1-alpha)**instances
    assert row['displayed_contribution_interval'][1]>=realized_ceiling-1e-10
    assert row['displayed_contribution_interval'][1]==pytest.approx(min(1,instances*alpha))
    assert row['source_contribution_interval'][1]<=row['support']['area_fraction_interval'][1]


def test_resampling_transparent_fill_with_possible_border_keeps_unknown_influence():
    row,_=evidence('a=0;a2=0;border_a=1;',composite='ret=GetPixel(float2(.5,.5));')
    assert row['opacity']['border_possible'] is True
    assert row['displayed_contribution_interval']==[0,1]
    assert any('border stroke' in reason for reason in row['unknown_reasons'])


def test_pointwise_repeated_fill_keeps_source_integral_bound():
    row,_=evidence('a=.1;a2=.1;r=g=b=r2=g2=b2=1;',
        config='shapecode_0_num_inst=2\nshapecode_0_additive=1\n')
    alpha=row['opacity']['interval'][1]
    expected=row['source_contribution_interval'][1]+row['sampling_support_allowance_fraction']*min(1,2*alpha)
    assert row['displayed_contribution_interval'][1]==pytest.approx(expected)


def test_saturated_affine_composite_independent_output_is_zero():
    row,_=evidence(composite='ret=saturate(GetPixel(uv)+2);')
    assert row['displayed_contribution_interval']==[0,0]
    assert 'saturation' in row['final_transfer']['method']


@pytest.mark.parametrize('composite',['ret=pow(GetPixel(uv),.5);','ret=GetPixel(uv)*bass;'])
def test_gamma_and_unknown_mask_do_not_invent_transparency(composite):
    row,_=evidence(composite=composite)
    assert row['displayed_contribution_interval'][1] is None or row['displayed_contribution_interval'][1]>0
    assert row['visible_contrast_interval'][0]==0


def test_dynamic_center_still_has_radius_area_upper_bound():
    row,_=evidence('x=.5+sin(time);rad=.01;')
    assert row['support']['area_fraction_interval'][0]==0
    assert row['support']['area_fraction_interval'][1]==pytest.approx(.01**2/2*9/16)


def test_source_context_and_model_hashes_are_stable_and_context_sensitive():
    _,first=evidence();_,repeat=evidence();_,other=evidence(viewport=(1280,720))
    assert first['provenance']==repeat['provenance']
    assert first['provenance']['preset_sha256']==other['provenance']['preset_sha256']
    assert first['provenance']['context_sha256']!=other['provenance']['context_sha256']


def test_missing_viewport_retains_unknown_area_without_assuming_square():
    row,_=evidence(viewport=(0,0))
    assert row['support']['area_fraction_interval']==[0,1]
    assert any('viewport' in reason for reason in row['unknown_reasons'])


def test_clipping_area_tracks_source_angle_plus_quarter_pi():
    # With ang=pi/4 the native four-sided polygon is a diamond in NDC.
    # At x=0 the half-diamond is 1/2 of its uncut support, even at wide aspect.
    row,_=evidence('ang=.7853981633974483;x=0;')
    shift=1/1920;radius=.5;aspect=9/16
    expected=.125*aspect/2+radius*shift/2-shift*shift/(4*aspect)
    assert row['support']['area_fraction_interval']==pytest.approx([expected]*2,abs=1e-8)


def test_unqualified_custom_compilation_cannot_resolve_a_disconnected_zero():
    row,_=evidence(composite='ret=0;',compiled=False)
    assert row['final_transfer']['difference_gain_interval']==[0,None]
    assert row['displayed_contribution_interval'][1]>0


def test_invalid_composite_domain_does_not_resolve_zero_by_saturation():
    row,_=evidence(composite='ret=saturate(GetPixel(uv/0)+2);')
    assert row['final_transfer']['difference_gain_interval'][1] is None
    assert row['displayed_contribution_interval'][1]>0


def test_dynamic_offscreen_domain_proves_no_support_without_sampling_time():
    row,_=evidence('x=-3+.1*sin(time);')
    assert row['support']['area_fraction_interval']==[0,0]
    assert row['displayed_contribution_interval']==[0,0]


def test_unknown_texture_alpha_keeps_possible_contribution():
    row,_=evidence(config='shapecode_0_textured=1\nshapecode_0_image=missing.png\n')
    assert row['opacity']['interval'][0]==0
    assert row['opacity']['interval'][1]>0
    assert row['unknown_reasons']


def test_z3_relational_range_rejects_impossible_on_screen_center():
    python=os.environ.get('MILK_PROOF_PYTHON')
    if python is None:pytest.skip('set MILK_PROOF_PYTHON to the pinned optional Z3 environment')
    from shader_fields import Field
    from effect_families import _constant
    from source_prominence import _shape_support
    from source_proofs import ProofSession
    bass=Field('input',detail={'name':'bass'})
    center=Field('subtract',(Field('add',(_constant(-3),bass)),bass))
    controls={'x':center,'y':_constant(.5),'rad':_constant(.5),'ang':_constant(0),'sides':_constant(4)}
    baseline,_=_shape_support(controls,1,[1920,1080],{'bass':[-2,2]})
    with ProofSession(python):refined,_=_shape_support(controls,1,[1920,1080],{'bass':[-2,2]})
    assert baseline['area_fraction_interval'][1]>0
    assert refined['area_fraction_interval']==[0,0]
    proof=refined['parameter_ranges'][0]['range_evidence']['x']['solver_refinement']
    assert proof['nominal_value_range'][0]<=-3<=proof['nominal_value_range'][1]<-2
    assert proof['native_numeric_certified'] is False


def test_gradient_alpha_integral_can_bound_a_clipped_subset_tighter_than_endpoint_max():
    row,_=evidence('a=1;a2=0;')
    assert row['source_contribution_interval'][1]==pytest.approx(.125*9/16/3)
    assert row['incoming_source_rgb_integral_intervals'] is not None


@pytest.mark.parametrize('flags,factor',[('',1),('bDarken=1\n',2),('bBrighten=1\nbSolarize=1\n',4)])
def test_native_legacy_gamma_and_filter_gain_uses_bounded_pointwise_transfer(flags,factor):
    row,_=evidence('a=.1;a2=.1;',shader_version=0,config='fGammaAdj=.5\n'+flags)
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(.5*factor)
    assert row['final_transfer']['pointwise_support_preserved'] is True


@pytest.mark.parametrize('viewport',[(1000,2000),(0,0)])
def test_legacy_gamma_only_portrait_or_unknown_viewport_does_not_preserve_source_support(viewport):
    row,_=evidence('a=.1;a2=.1;',shader_version=0,viewport=viewport,config='fGammaAdj=1\n')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(1)
    assert row['final_transfer']['pointwise_support_preserved'] is False
    assert row['displayed_support_fraction_interval']==[0,1]
    assert row['displayed_contribution_interval'][1]>=.09999


@pytest.mark.parametrize('viewport',[(2000,1000),(1000,1000)])
def test_legacy_gamma_only_landscape_and_square_keep_source_integral_bound(viewport):
    row,_=evidence('a=.1;a2=.1;',shader_version=0,viewport=viewport,config='fGammaAdj=1\n')
    assert row['final_transfer']['pointwise_support_preserved'] is True
    assert row['displayed_contribution_interval'][1]==pytest.approx(
        row['source_contribution_interval'][1]+row['sampling_support_allowance_fraction']*row['opacity']['interval'][1])


def test_legacy_portrait_transparent_finite_source_stays_zero():
    row,_=evidence('a=0;a2=0;',shader_version=0,viewport=(1000,2000),config='fGammaAdj=1\n')
    assert row['displayed_contribution_interval']==[0,0]


def test_legacy_portrait_invalid_source_cannot_use_small_gamma_ceiling():
    row,_=evidence('r=1e100;r2=1e100;a=0;a2=0;',shader_version=0,viewport=(1000,2000),config='fGammaAdj=.1\n')
    assert row['known_invalid_native_domain'] is True
    assert row['displayed_contribution_interval']==[0,1]


@pytest.mark.parametrize('alpha,gamma,gain,pointwise',[
    (.5,.5,1,False),(.5,0,1,False),(.5,2,2,False),
    (-.5,.5,.5,True),(.001,.5,.5,True),(2,.5,3,False),
    (.5,-2,1,False),(.5,100,8,False),
])
def test_legacy_echo_uses_native_branch_and_absolute_blend_redraw_gain(alpha,gamma,gain,pointwise):
    row,_=evidence('a=.1;a2=.1;',shader_version=0,
        config=f'fVideoEchoAlpha={alpha}\nfGammaAdj={gamma}\n')
    transfer=row['final_transfer']
    assert transfer['difference_gain_interval'][1]==pytest.approx(gain)
    assert transfer['pointwise_support_preserved'] is pointwise
    if not pointwise:
        assert row['displayed_support_fraction_interval']==[0,1]
        assert row['displayed_contribution_interval'][1]>=.09999
        assert row['feedback_contribution_interval']==[0,1]
        assert transfer['legacy_response']['sample_textures']==['main']


def test_legacy_echo_filters_follow_gamma_echo_and_hue_before_ordered_polynomials():
    row,_=evidence(shader_version=0,config='fVideoEchoAlpha=.5\nfGammaAdj=2\nbBrighten=1\nbDarken=1\nbSolarize=1\nbInvert=1\n')
    transfer=row['final_transfer']
    assert transfer['difference_gain_interval'][1]==pytest.approx(16)
    assert transfer['legacy_response']['application_order']==['hue_and_gamma_echo_draws','brighten','darken','solarize','invert']


@pytest.mark.parametrize('zoom',[-2,0,1e100])
def test_legacy_echo_zoom_uses_native_post_equation_clamp(zoom):
    row,_=evidence(shader_version=0,config=f'fVideoEchoAlpha=.5\nper_frame_1=echo_zoom={zoom};\n')
    transfer=row['final_transfer']
    assert transfer['difference_gain_interval'][1]==pytest.approx(2)
    assert transfer['legacy_response']['native_control_ranges']['echo_zoom']==pytest.approx([max(.001,min(1000,zoom))]*2)


def test_legacy_echo_declared_domains_bound_dynamic_gain_and_native_gamma_clamp():
    row,_=evidence(shader_version=0,config='per_frame_1=echo_alpha=bass;gamma=treb;\n',domains={'bass':[.1,.2],'treb':[.2,.5]})
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(1)
    assert row['final_transfer']['legacy_response']['native_control_ranges']['gamma']==pytest.approx([.2,.5])


@pytest.mark.parametrize('control',['echo_alpha=1e100;','echo_alpha=1e100*1e100*1e100*1e100;','gamma=1e100*1e100*1e100*1e100;'])
def test_legacy_invalid_controls_retain_unknown_transfer(control):
    row,_=evidence(shader_version=0,config='fVideoEchoAlpha=.5\nper_frame_1='+control+'\n')
    assert row['final_transfer']['difference_gain_interval'][1] is None
    assert row['final_transfer']['unknown_reasons']


def test_legacy_undefined_orientation_conversion_uses_native_gamma_only_fallback():
    row,_=evidence(shader_version=0,config='fVideoEchoAlpha=.5\nfGammaAdj=.5\nper_frame_1=echo_orient=1e100;\n')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(.5)
    assert row['final_transfer']['legacy_response']['echo_selection']=='native orientation conversion fallback'


def test_legacy_out_of_range_static_tint_gain_is_not_assumed_unit():
    row,_=evidence(shader_version=0,config='fShader=10\nfVideoEchoAlpha=.5\nfGammaAdj=2\n')
    assert row['final_transfer']['difference_gain_interval'][1]>=2*(10/3-1)


def test_legacy_echo_tint_product_overflow_keeps_unknown_native_domain():
    row,_=evidence(shader_version=0,config='fShader=10\nper_frame_1=echo_alpha=1e38;\n')
    assert row['final_transfer']['difference_gain_interval'][1] is None


@pytest.mark.parametrize('orientation',[-2147483648.5,2147483647.5])
def test_legacy_orientation_native_truncation_precedes_integer_domain_check(orientation):
    row,_=evidence(shader_version=0,config=f'fVideoEchoAlpha=.5\nfGammaAdj=.5\nper_frame_1=echo_orient={orientation};\n')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(1)
    assert row['final_transfer']['pointwise_support_preserved'] is False


def test_legacy_gamma_post_equation_clamp_precedes_float32_conversion():
    row,_=evidence(shader_version=0,config='fVideoEchoAlpha=.5\nper_frame_1=gamma=1e100;\n')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(8)


@pytest.mark.parametrize('gamma',[0,.1,.5])
def test_legacy_gamma_does_not_bound_known_invalid_incoming_native_domain(gamma):
    row,_=evidence('r=1e100;r2=1e100;a=0;a2=0;',shader_version=0,config=f'fGammaAdj={gamma}\n')
    assert row['known_invalid_native_domain'] is True
    assert row['displayed_contribution_interval']==[0,1]


def test_opaque_legacy_control_is_not_certified_by_native_gamma_clamp():
    from source_prominence import _final_transfer
    from shader_fields import Field
    from test_source_static_behaviour import analysis
    a=analysis('PSVERSION_COMP=0\nfVideoEchoAlpha=.5\n')
    a.main['gamma']=Field('unknown',detail={'reason':'unresolved source control'})
    assert _final_transfer(a,{})['difference_gain_interval'][1] is None


def test_custom_composite_does_not_apply_legacy_echo_controls():
    row,_=evidence(config='fVideoEchoAlpha=2\nfGammaAdj=8\nbBrighten=1\n')
    assert row['final_transfer']['difference_gain_interval'][1]==pytest.approx(1)
    assert 'legacy_response' not in row['final_transfer']


def test_history_dependent_coordinates_do_not_reuse_fixed_sample_alpha_gain():
    row,_=evidence('a=.001;a2=.001;',composite='ret=GetPixel(uv+GetPixel(uv).xy*.1)*.01;')
    assert row['final_transfer']['difference_gain_interval'][1] is None
    assert row['displayed_contribution_interval'][1]>=.00999


def test_pointwise_lookup_includes_bilinear_support_allowance():
    row,_=evidence('rad=.001;')
    assert row['displayed_support_fraction_interval'][1]>row['support']['area_fraction_interval'][1]
    assert row['sampling_support_allowance_fraction']>0


@pytest.mark.parametrize('body',['r=1e100;r2=1e100;a=0;a2=0;','rad=1e100;a=0;a2=0;',
    'tex_zoom=0;a=0;a2=0;','additive=1e100;a=0;a2=0;'])
def test_known_invalid_native_inputs_do_not_become_zero_by_transparency(body):
    row,_=evidence(body,config='shapecode_0_textured=1\n' if 'tex_zoom' in body else '')
    assert row['displayed_contribution_interval'][1]>0
    assert row['feedback_contribution_interval'][1]>0
    assert row['unknown_reasons']


def test_full_shader_domain_budget_keeps_unknown_transfer_and_component_bounds():
    code='ret='+ '+'.join('GetPixel(uv+float2('+str(i/1000)+',.1))/48' for i in range(48))+';'
    row,result=evidence(composite=code)
    assert row['final_transfer']['difference_gain_interval']==[0,None]
    assert row['final_transfer']['pointwise_support_preserved'] is False
    assert any('domain guard unresolved' in reason for reason in row['unknown_reasons'])
    assert row['support']['area_fraction_interval'][1]<.1
    assert 'shader_composite' in result['by_component']


@pytest.mark.parametrize('name,sha',[
    ('amandio c - hat track - mrt sth.milk','31a14cb9bf98685f3c0b1e278da836e16d8a57e096fe58d22878d0386c71b1b2'),
    ('Nivush - Crazy Diamonds.milk','31ec688577a888e65d6f63b945fe2d123da5a3971acd1eb9ca17f4cd58cf12f0'),
    ('amandio c - new life.milk','7ab8c98263347a97bc79c5b2dcfb0530a134880d54907268296368a07434ae21'),
])
def test_original_literal_budget_cases_preserve_local_unknown_geometry(name,sha):
    import effect_families as ef
    import source_prominence
    from source_appearance import appearance_from_analysis
    root=Path(__file__).resolve().parents[2]
    path=root/'core/src/main/assets/presets'/name;raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==sha
    source=json.loads(subprocess.check_output([str(root/'build/preset-corpus/source34/adapters/milk-native-reader'),str(path)]))
    source['preset_sha256']=sha;source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    token=ef._CACHE.set({})
    try:
        analysis=ef._Analysis(source,'gles300',None);analysis.input_scenario=None
        analysis.main_equations();analysis.primitives();analysis.shader('warp','warp_')
        analysis.shader('composite','comp_');analysis.contribution_gates()
        description=appearance_from_analysis(analysis)
        result=source_prominence.prominence_evidence(analysis,description,{'viewport':[1920,1080],'feedback_fps':30})
    finally:ef._CACHE.reset(token)
    json.dumps(result,allow_nan=False)
    assert any('literal' in reason for reason in result['unknown_reasons'])
    assert any(identity.startswith('shape_') for identity in result['by_component'])


def test_transparency_with_known_invalid_texture_uv_stays_unknown_after_budget_fallback():
    row,_=evidence('tex_zoom=0;a=0;a2=0;',config='shapecode_0_textured=1\n')
    assert row['known_invalid_native_domain'] is True
    assert row['displayed_contribution_interval'][1]>0


def test_global_field_budget_still_propagates_and_sets_counter_flag(monkeypatch):
    import effect_families as ef
    from test_source_static_behaviour import analysis
    from source_prominence import _final_transfer
    code='ret='+ '+'.join('GetPixel(uv+float2('+str(i/1000)+',.1))/48' for i in range(48))+';'
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {'+code+'}\n')
    token=ef._CACHE.set({})
    monkeypatch.setattr(ef,'MAX_FIELD_VISITS',1000)
    try:
        with pytest.raises(ef._SemanticBudget):_final_transfer(a,{})
        assert ef._CACHE.get()['traversal_budget_exhausted'] is True
    finally:ef._CACHE.reset(token)


def test_declared_context_audio_domain_bounds_radius_without_audio_execution():
    row,_=evidence('rad=bass;',domains={'bass':[.1,.2]})
    assert row['support']['area_fraction_interval'][1]==pytest.approx(.2**2*.5*9/16)


def test_conflicting_scenario_and_context_domains_are_rejected_explicitly():
    from source_input_scenario import validate_scenario
    scenario=validate_scenario({'schema_version':1,'name':'prior-audio-domain','audio_band_ranges':{'bass':[.1,.2]}})
    with pytest.raises(ValueError,match='conflicting'):
        evidence('rad=bass;',domains={'bass':[.3,.4]},scenario=scenario)
