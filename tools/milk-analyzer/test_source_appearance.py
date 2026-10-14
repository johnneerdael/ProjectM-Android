"""Machine-readable mental-map traits from source, never rendered images."""
import json
import math
import pytest
from test_effect_families import shader,read,analyze


def appearance(source):
    result=analyze(source)
    assert 'visual_description' in result,'structured source appearance export missing'
    return result['visual_description']


def test_generated_phase_palette_exports_numeric_rgb_parameters():
    result=appearance(shader('shader_body {ret=.5+.5*cos(time+float3(0,2,4));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==3
    assert colour['bias_rgb']==[.5]*3 and colour['amplitude_rgb']==[.5]*3
    assert colour['phase_offsets_rad']==[0,2,4]
    assert colour['common_phase_expression']['nodes']
    assert colour['distinct_channel_phases']==3
    assert colour['depends_on_time']==1
    assert result['uses_rendered_images'] is False
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('code',[
    'shader_body {ret=sin(time);}',
    'shader_body {ret=float3(1,.5,.2)*sin(time);}',
    'shader_body {ret=GetPixel(uv);}',
    'shader_body {float3 unused=.5+.5*cos(time+float3(0,2,4));ret=0;}',
    'shader_body {ret=float4(1,0,0,sin(time));}',
])
def test_monochrome_inherited_and_dead_forms_are_not_generated_varied_palettes(code):
    result=appearance(shader(code))
    assert all(element['colour']['mode_code']!=3 for element in result['elements'])


def test_shape_audio_routes_target_named_controls_and_coefficients():
    source=read('PSVERSION_COMP=0\nfWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_sides=5\n'
        'shapecode_0_rad=.2\nshape_0_per_frame1=rad=.2+bass*.05;ang=mid*.1;r=treb*.3;\n')
    result=appearance(source)
    element=next(row for row in result['elements'] if row['id']=='shape_0')
    assert element['family_codes']==[3]
    routes={row['control']:row for row in element['audio_routes']}
    assert routes['radius']['input_code']==1 and routes['radius']['linear_gain']==pytest.approx(.05)
    assert routes['rotation']['input_code']==2 and routes['rotation']['linear_gain']==pytest.approx(.1)
    assert routes['colour_r']['input_code']==3 and routes['colour_r']['linear_gain']==pytest.approx(.3)
    assert all(row['visible_response_strength'] is None for row in routes.values())


def test_rgb_shader_bass_mid_high_routes_do_not_claim_stems_or_image_strength():
    result=appearance(shader('shader_body {ret=float3(bass*.2,mid*.1,treb*.3);}'))
    routes=result['elements'][0]['audio_routes']
    assert {(r['control'],r['input_code']) for r in routes}=={('colour_r',1),('colour_g',2),('colour_b',3)}
    assert all(r['visible_response_strength'] is None for r in routes)


def test_alpha_only_audio_is_not_exported_as_colour_response():
    result=appearance(shader('shader_body {ret=float4(1,0,0,bass);}'))
    assert not result['elements'][0]['audio_routes']


def test_clipped_white_oscillators_are_not_multicolour_candidates():
    result=appearance(shader('shader_body {ret=10+.1*cos(time+float3(0,2,4));}'))
    assert result['elements'][0]['colour']['mode_code']!=3


def test_preference_description_keeps_flashing_and_motion_uncertainty():
    result=appearance(shader('shader_body {ret=.5+.5*cos(time+float3(0,2,4));}'))
    assert result['activity']['flashing']['value'] is None
    assert result['activity']['flashing']['status']=='unknown'
    assert result['activity']['flashing']['hazards']==[]
    assert result['activity']['motion_intensity']['value'] is None
    assert result['activity']['motion_intensity']['status']=='unknown'
    assert result['mood_matches']['chill']['eligible'] is None


def test_final_constant_composite_removes_warp_element_and_audio_routes():
    result=appearance(read('PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv)*bass;}\n'
        'comp_1=`shader_body {ret=0;}\n'))
    assert [row['id'] for row in result['elements']]==['shader_composite']
    assert not result['elements'][0]['audio_routes']


def test_q_bridge_explains_shader_audio_dependency_with_main_source_formula():
    result=appearance(read('PSVERSION_COMP=2\nper_frame_1=q1=bass*.2;\n'
        'comp_1=`shader_body {ret=float3(q1,0,0);}\n'))
    route=next(row for row in result['elements'][0]['audio_routes'] if row['control']=='colour_r')
    assert route['input_code']==1
    assert route['q_bridge_expressions']['q1']['nodes']
    assert route['linear_gain'] is None #shader-side coefficient is not yet the composed gain


def test_fixed_tint_modulation_is_distinct_from_inherited_or_varied_palette():
    result=appearance(shader('shader_body {ret=float3(1,.5,.2)*sin(time);}'))
    assert result['elements'][0]['colour']['mode_code']==2
    assert result['elements'][0]['colour']['tint_rgb']==pytest.approx([1,.5,.2],abs=1e-7)


def test_fps_driven_phase_is_not_mislabelled_time_driven():
    result=appearance(shader('shader_body {ret=.5+.5*cos(fps+float3(0,2,4));}'))
    assert result['elements'][0]['colour']['mode_code']==3
    assert result['elements'][0]['colour']['depends_on_time']==0


def test_palette_under_common_spatial_mask_retains_colour_generator_parameters():
    result=appearance(shader('shader_body {float f=length(uv-.5);'
        'ret=(.5+.5*cos(time+float3(0,2,4)))*(1-smoothstep(.1,.3,f));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==3
    assert colour['phase_offsets_rad']==[0,2,4]
    assert colour['shared_multiplier_expressions']
    assert colour['guaranteed_visible'] is False


def test_masked_palette_does_not_appear_through_zero_or_monochrome_composite():
    result=appearance(read('PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
        'warp_1=`shader_body {ret=.5+.5*cos(time+float3(0,2,4));}\n'
        'comp_1=`shader_body {ret=GetPixel(uv).rrr;}\n'))
    assert result['elements'][-1]['colour']['mode_code']==1
    assert result['mood_matches']['psychedelic']['candidate'] is not True


def test_global_feedback_transform_routes_distinguish_audio_bands():
    result=appearance(read('fWaveAlpha=0\nper_frame_1=zoom=1+bass*.05;rot=mid*.2;warp=treb*.3;\n'))
    element=next(e for e in result['elements'] if e['id']=='mesh_warp')
    routes={r['control']:r for r in element['audio_routes']}
    assert routes['zoom']['input_code']==1 and routes['zoom']['linear_gain']==pytest.approx(.05)
    assert routes['rotation']['input_code']==2 and routes['rotation']['linear_gain']==pytest.approx(.2)
    assert routes['deformation']['input_code']==3 and routes['deformation']['linear_gain']==pytest.approx(.3)


def test_uv_orig_bypass_does_not_claim_native_zoom_audio_response():
    result=appearance(read('PSVERSION_WARP=2\nper_frame_1=zoom=1+bass*.05;\n'
        'warp_1=`shader_body {ret=GetPixel(uv_orig);}\n'))
    assert not any(e['id']=='mesh_warp' for e in result['elements'])


def test_loop_only_bass_does_not_invent_other_bands_or_channels():
    result=appearance(shader('shader_body {float v=0;for(int n=0;n<2;n++){v+=bass;}ret=float3(v,0,0);}'))
    routes=result['elements'][0]['audio_routes']
    assert {(r['control'],r['input_code']) for r in routes}=={('colour_r',1)}


def test_unrelated_loop_preserves_palette_data_but_keeps_execution_uncertainty():
    result=appearance(shader('shader_body {for(int n=0;n<2;n++){}ret=.5+.5*cos(time+float3(0,2,4));}'))
    assert result['elements'][0]['colour']['mode_code']==3
    assert result['execution_unknowns']


def test_zero_clipped_common_multiplier_removes_palette_candidate():
    result=appearance(shader('shader_body {ret=(.5+.5*cos(time+float3(0,2,4)))*saturate(-1)*GetPixel(uv).r;}'))
    element=next(e for e in result['elements'] if e['id']=='shader_composite')
    assert element['colour']['mode_code']!=3
    assert result['mood_matches']['psychedelic']['candidate'] is not True


def test_main_q_bridge_reaches_shape_radius():
    source=read('fWaveAlpha=0\nper_frame_1=q1=bass*.2;\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=rad=.2+q1*.05;\n')
    result=appearance(source)
    route=next(r for e in result['elements'] if e['id']=='shape_0' for r in e['audio_routes'] if r['control']=='radius')
    assert route['input_code']==1
    assert route['linear_gain']==pytest.approx(.01)
    assert any(n['op']=='input' and n['detail'].get('name')=='bass' for n in route['expression']['nodes'])


def test_native_shape_frame_q_load_replaces_init_q_but_local_write_overrides():
    common='fWaveAlpha=0\nper_frame_1=q1=bass*.2;\nshapecode_0_enabled=1\nshape_0_init1=q1=.5;\n'
    loaded=appearance(read(common+'shape_0_per_frame1=rad=.2+q1*.05;\n'))
    element=next(e for e in loaded['elements'] if e['id']=='shape_0')
    assert any(r['control']=='radius' and r['input_code']==1 for r in element['audio_routes'])
    overridden=appearance(read(common+'shape_0_per_frame1=q1=.5;rad=.2+q1*.05;\n'))
    element=next(e for e in overridden['elements'] if e['id']=='shape_0')
    assert not any(r['control']=='radius' for r in element['audio_routes'])


def test_unwritten_main_q_zero_replaces_audio_dependent_shape_init_q():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_init1=q1=bass*.2;\n'
        'shape_0_per_frame1=rad=.2+q1*.05;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['parameters']['rad']==pytest.approx(.2)
    assert not any(r['control']=='radius' for r in element['audio_routes'])


@pytest.mark.parametrize('mask',['clamp(-1,0,1)','saturate(abs(0))'])
def test_supported_constant_zero_masks_do_not_generate_palette(mask):
    source=shader('shader_body {ret=(.5+.5*cos(time+float3(0,2,4)))*'+mask+';}')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shader_composite')
    assert element['colour']['mode_code']!=3


def test_hidden_loop_samples_do_not_claim_resources_resolved():
    source=shader('shader_body {float v=0;for(int n=0;n<2;n++){v+=GetPixel(uv).r*bass;}ret=float3(v,0,0);}')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shader_composite')
    expression=element['audio_routes'][0]['expression']
    assert expression['resources_resolved'] is not True


def test_independent_rgb_phase_rates_export_each_control_program():
    result=appearance(shader('shader_body {ret=.5+.5*sin(time*float3(42,23,13.37));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==5
    assert colour['distinct_channel_phases'] is None
    assert len(colour['channel_phase_expressions'])==3
    assert colour['oscillator_function_codes']==[2,2,2]
    assert colour['depends_on_time']==1


def test_affine_time_palette_exports_period_and_unmasked_component_speed():
    result=appearance(shader('shader_body {ret=.5+.25*cos(2*time+float3(0,2,4));}'))
    temporal=result['elements'][0]['colour']['temporal']
    assert temporal['angular_rate_rad_per_second_rgb']==pytest.approx([2]*3)
    assert temporal['cycle_frequency_hz_rgb']==pytest.approx([1/math.pi]*3)
    assert temporal['period_seconds_rgb']==pytest.approx([math.pi]*3)
    assert temporal['unmasked_component_slope_rgb_per_second']==pytest.approx([.5]*3)
    assert temporal['visible_flash_frequency_hz'] is None
    assert temporal['shader_time_wrap_seconds']==10000
    assert result['mood_matches']['chill']['eligible'] is None


def test_independent_time_rates_keep_signed_direction_and_partial_unknowns():
    result=appearance(shader('shader_body {ret=.5+.5*sin(float3(-2*time,3*time,time*bass));}'))
    temporal=result['elements'][0]['colour']['temporal']
    assert temporal['angular_rate_rad_per_second_rgb']==[-2,3,None]
    assert temporal['cycle_frequency_hz_rgb'][:2]==pytest.approx([1/math.pi,3/math.tau])
    assert temporal['cycle_frequency_hz_rgb'][2] is None
    assert temporal['channel_status']==['computed','computed','unknown']


@pytest.mark.parametrize('phase',['time*time','sin(time)','fps','int(time)','time+GetPixel(uv).r','time+bass'])
def test_nonaffine_or_undeclared_inputs_do_not_claim_fixed_palette_frequency(phase):
    result=appearance(shader('shader_body {ret=.5+.5*cos(('+phase+')+float3(0,2,4));}'))
    temporal=next(e for e in result['elements'] if e['id']=='shader_composite')['colour']['temporal']
    assert temporal['angular_rate_rad_per_second_rgb']==[None]*3
    assert temporal['period_seconds_rgb']==[None]*3
    assert temporal['channel_status']==['unknown']*3


def test_masked_time_palette_rate_does_not_claim_final_brightness_speed():
    result=appearance(shader('shader_body {ret=(.5+.5*cos(2*time+float3(0,2,4)))*GetPixel(uv).r;}'))
    colour=next(e for e in result['elements'] if e['id']=='shader_composite')['colour']
    assert colour['temporal']['angular_rate_rad_per_second_rgb']==[2]*3
    assert colour['temporal']['scope']=='unmasked source RGB oscillators between shader-clock wraps'
    assert colour['shared_multiplier_expressions']
    assert colour['temporal']['visible_flash_frequency_hz'] is None


def test_quantized_phase_keeps_integer_conversion_in_exported_common_program():
    result=appearance(shader('shader_body {ret=.5+.5*cos(int(time)+float3(0,2,4));}'))
    colour=result['elements'][0]['colour']
    assert any(n['dtype']=='int' and n['op'] in {'cast','construct'}
               for n in colour['common_phase_expression']['nodes'])


def test_quantized_and_continuous_channel_phases_are_distinct():
    result=appearance(shader('shader_body {ret=.5+.5*cos(float3(time,int(time)+2,time+4));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==5
    assert colour['temporal']['angular_rate_rad_per_second_rgb']==[1,None,1]


@pytest.mark.parametrize('phases',['time,2*time-time,time','time,-time,time'])
def test_equivalent_cosine_channels_do_not_invent_varied_palette(phases):
    source=read('PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
        'warp_1=`shader_body {float2 z=uv-.5;for(int n=0;n<4;n++){'
        'z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+float2(.1,.2);}ret=GetPixel(z);}\n'
        'comp_1=`shader_body {ret=(.5+.5*cos(float3('+phases+')))*GetPixel(uv).r;}\n')
    result=appearance(source)
    assert result['mood_matches']['psychedelic']['candidate'] is None
    colour=next(e for e in result['elements'] if e['id']=='shader_composite')['colour']
    assert colour['mode_code'] not in {3,5}


def test_cosine_even_normalization_preserves_distinct_phase_offsets():
    result=appearance(shader('shader_body {ret=.5+.5*cos(float3(-2*time,2*time+2,-2*time-4));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==3
    assert colour['phase_offsets_rad']==[0,2,4]
    assert colour['temporal']['angular_rate_rad_per_second_rgb']==[-2,2,-2]


def test_sine_opposite_time_direction_is_not_cosine_even():
    result=appearance(shader('shader_body {ret=.5+.5*sin(float3(time,-time,time));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==3
    assert colour['distinct_channel_phases']==2


def test_phase_identity_budget_failure_cannot_merge_unrelated_programs():
    code='shader_body {float a=time,b=time,c=time;'+('a=sin(a);b=cos(b);c=abs(c);'*260)+\
         'ret=.5+.5*cos(float3(a,b+2,c+4));}'
    result=appearance(shader(code))
    assert result['status']=='conditional source description'
    colour=result['elements'][0]['colour']
    assert colour['mode_code'] is None
    assert any('phase identity unresolved' in r for r in colour['unknown_reasons'])


def test_constant_colour_respects_integer_constructor_truncation():
    result=appearance(shader('shader_body {ret=float3(int(.8),int(1.8),int(-.8));}'))
    assert result['elements'][0]['colour']['constant_rgb']==[0,1,0]


def test_integer_zero_multiplier_cannot_establish_palette_or_timing():
    result=appearance(shader('shader_body {ret=(.5+.5*cos(time+float3(0,2,4)))*int(.8)*GetPixel(uv).r;}'))
    colour=next(e for e in result['elements'] if e['id']=='shader_composite')['colour']
    assert colour['mode_code'] not in {3,5}
    assert 'temporal' not in colour


def test_integer_channel_quantization_is_not_a_shared_monochrome_signal():
    result=appearance(shader('shader_body {ret=float3(time,int(time),time);}'))
    assert result['elements'][0]['colour']['mode_code'] is None


def test_large_sample_colour_graph_retains_inherited_description_without_false_identity():
    code='shader_body {float a=GetPixel(uv).r;'+('a=sin(a)+.1;'*150)+'ret=float3(a,a*.3,a*.5);}'
    result=appearance(shader(code))
    assert result['status']=='conditional source description'
    colour=next(e for e in result['elements'] if e['id']=='shader_composite')['colour']
    assert colour['mode_code']==4


def test_constant_literal_shared_dag_is_folded_once_per_distinct_node(monkeypatch):
    import source_appearance as module
    from shader_fields import Field
    value=Field('constant',detail={'value':1.})
    for _ in range(18):value=Field('add',(value,value))
    calls=0;original=module._phase_literal
    def counted(*args,**kwargs):
        nonlocal calls
        calls+=1
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'_phase_literal',counted)
    assert module._phase_literal(value)==2**18
    assert calls<100


def test_sine_oddness_and_amplitude_sign_cannot_invent_varied_palette():
    source=read('PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
        'warp_1=`shader_body {float2 z=uv-.5;for(int n=0;n<4;n++){'
        'z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+float2(.1,.2);}ret=GetPixel(z);}\n'
        'comp_1=`shader_body {ret=(.5+float3(.5*sin(time),-.5*sin(-time),.5*sin(time)))*GetPixel(uv).r;}\n')
    result=appearance(source)
    assert result['mood_matches']['psychedelic']['candidate'] is None


def test_independent_phase_programs_retain_original_negative_amplitudes():
    result=appearance(shader('shader_body {ret=.5+float3(-.5*sin(time),.5*sin(2*time),.5*sin(3*time));}'))
    colour=result['elements'][0]['colour']
    assert colour['mode_code']==5
    assert colour['amplitude_rgb']==[-.5,.5,.5]
    assert colour['oscillator_function_codes']==[2,2,2]


def test_shape_opacity_threshold_exports_band_threshold_and_control_jump():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=a=if(above(bass,1.2),.8,.1);\n'))
    route=next(r for e in result['elements'] for r in e['audio_routes'] if r['control']=='opacity')
    trigger=route['switch_triggers'][0]
    assert trigger['input_code']==1 and trigger['comparison']=='greater'
    assert trigger['threshold_value']==pytest.approx(1.2)
    assert trigger['control_true_value']==pytest.approx(.8)
    assert trigger['control_false_value']==pytest.approx(.1)
    assert trigger['absolute_control_jump']==pytest.approx(.7)
    assert trigger['trigger_frequency_hz'] is None
    assert result['activity']['flashing']['value'] is None


def test_shader_reversed_threshold_preserves_band_direction():
    result=appearance(shader('shader_body {ret=float3(1.2<bass?0.8:0.1,0,0);}'))
    trigger=result['elements'][0]['audio_routes'][0]['switch_triggers'][0]
    assert trigger['comparison']=='greater'
    assert trigger['absolute_control_jump']==pytest.approx(.7)


def test_nested_switch_has_no_fabricated_whole_control_jump():
    result=appearance(shader('shader_body {ret=float3((bass>1.2?0.8:0.1)*mid,0,0);}'))
    trigger=result['elements'][0]['audio_routes'][0]['switch_triggers'][0]
    assert trigger['input_code']==1
    assert trigger['absolute_control_jump'] is None


def test_dynamic_threshold_retains_expression_instead_of_fixed_number():
    result=appearance(shader('shader_body {ret=float3(bass>mid?1:0,0,0);}'))
    trigger=next(r for r in result['elements'][0]['audio_routes'] if r['input_code']==1)['switch_triggers'][0]
    assert trigger['threshold_value'] is None
    assert trigger['threshold_expression']['nodes']


@pytest.mark.parametrize('code',['ret=float3((bass>1.2?0.8:0.1)*0,0,0);',
                               'ret=float3(int(bass)>1.2?1:0,0,0);',
                               'ret=float3(bass>1.2?0.1:0.1,0,0);'])
def test_dead_quantized_or_zero_jump_paths_do_not_assert_direct_band_switch(code):
    result=appearance(shader('shader_body {'+code+'}'))
    assert not any(r['switch_triggers'] for e in result['elements'] for r in e['audio_routes'])


def test_integer_switch_branches_report_whole_control_jump_and_path():
    result=appearance(shader('shader_body {ret=float3(bass>1.2?1:0,0,0);}'))
    trigger=result['elements'][0]['audio_routes'][0]['switch_triggers'][0]
    assert trigger['absolute_control_jump']==1
    assert isinstance(trigger['source_graph_path'],str)
    assert trigger['source_graph_path'].startswith('output')


@pytest.mark.parametrize('code',['ret=float3(bass>1.2?1:1,0,0);','ret=float3(bass>bass,0,0);'])
def test_constant_integer_branch_and_self_predicate_have_no_switch_site(code):
    result=appearance(shader('shader_body {'+code+'}'))
    assert not any(r['switch_triggers'] for e in result['elements'] for r in e['audio_routes'])


def test_shape_frame_reload_discards_init_parameter_writes_but_retains_scratch():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_rad=.2\n'
        'shape_0_init1=rad=.9;x=.9;r=bass;t1=.25;k=.3;\n'
        'shape_0_per_frame1=y=t1;x=k;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['parameters']['rad']==pytest.approx(.2)
    assert element['parameters']['x']==pytest.approx(.3)
    assert element['parameters']['y']==pytest.approx(.25)
    assert not any(r['control']=='colour_r' for r in element['audio_routes'])


def test_shape_instance_count_comes_from_configuration_not_equation_write():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_num_inst=3\n'
        'shape_0_per_frame1=num_inst=0;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['parameters']['instances']==3


def test_persistent_shape_local_counter_is_not_a_constant_radius():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_init1=k=.3;\n'
        'shape_0_per_frame1=k=k+.1;rad=k;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['parameters']['rad'] is None


def test_main_reset_and_persistent_counter_do_not_invent_constant_shape_q_radius():
    source=read('fWaveAlpha=0\nper_frame_init_1=k=.3;wave_a=1;\n'
        'per_frame_1=k=k+.1;q1=k;\nshapecode_0_enabled=1\nshape_0_per_frame1=rad=q1;\n')
    result=appearance(source)
    assert not any(e['id']=='builtin_wave' for e in result['elements'])
    element=next(e for e in result['elements'] if e['id']=='shape_0')
    assert element['parameters']['rad'] is None


def test_static_square_geometry_exports_area_coefficient_and_radius_units():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_sides=4\n'
        'shapecode_0_rad=.2\nshapecode_0_num_inst=3\n'))
    element=next(e for e in result['elements'] if e['id']=='shape_0')
    geometry=element['geometry']
    assert geometry['effective_sides']==4 and geometry['configured_instances']==3
    assert geometry['radius_ndc']==pytest.approx(.2)
    assert geometry['nominal_area_fraction_per_aspect_y']==pytest.approx(.02)
    assert geometry['summed_nominal_area_fraction_per_aspect_y']==pytest.approx(.06)
    assert geometry['circumcircle_width_fraction_per_aspect_y']==pytest.approx(.2)
    assert geometry['circumcircle_height_fraction']==pytest.approx(.2)
    assert geometry['visible_coverage_fraction'] is None
    assert element['approximate_screen_coverage'] is None


@pytest.mark.parametrize('sides,effective',[(2.8,3),(101,100),(-2147483648.5,3)])
def test_geometry_uses_native_side_truncation_and_clamp(sides,effective):
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=sides='+str(sides)+';\n')
    geometry=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['geometry']
    assert geometry['effective_sides']==effective


def test_audio_dependent_radius_remains_unknown_geometry():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=rad=.2+bass*.05;\n')
    geometry=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['geometry']
    assert geometry['radius_ndc'] is None
    assert geometry['nominal_area_fraction_per_aspect_y'] is None
    assert geometry['unknown_reasons']


def test_instance_dependent_radius_does_not_claim_one_size_for_every_copy():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_num_inst=3\n'
        'shape_0_per_frame1=rad=.2+instance*.05;\n')
    geometry=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['geometry']
    assert geometry['configured_instances']==3
    assert geometry['summed_nominal_area_fraction_per_aspect_y'] is None


def test_negative_radius_preserves_sign_but_positive_geometric_area():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_rad=-.2\n')
    geometry=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['geometry']
    assert geometry['radius_ndc']==pytest.approx(-.2)
    assert geometry['nominal_area_fraction_per_aspect_y']==pytest.approx(.02)


@pytest.mark.parametrize('body',[
 'shape_0_init1=k=bass;\nshape_0_per_frame1=rad=k;\n',
 'per_frame_init_1=q1=bass;\nshape_0_per_frame1=rad=q1;\n'])
def test_init_captured_audio_is_not_current_frame_reactivity(body):
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\n'+body)
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert not any(r['control']=='radius' for r in element['audio_routes'])
    assert element['geometry']['radius_ndc'] is None


def test_unregistered_eel_volume_is_not_engine_volume_aggregate():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=rad=vol+vol_att;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert not element['audio_routes']


def test_shader_volume_macros_still_export_engine_aggregate_codes():
    result=appearance(shader('shader_body {ret=float3(vol,vol_att,0);}'))
    assert {r['input_code'] for r in result['elements'][0]['audio_routes']}=={7,8}


def test_native_if_assignment_merges_shape_radius_branches():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=if(above(bass,1),rad=.8,rad=.1);\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['parameters']['rad'] is None
    assert element['geometry']['radius_ndc'] is None
    route=next(r for r in element['audio_routes'] if r['control']=='radius')
    assert route['switch_triggers'][0]['absolute_control_jump']==pytest.approx(.7)


@pytest.mark.parametrize('code,radius',[('rad+=.1;',.2),('rad*=2;',.2)])
def test_compound_shape_parameter_assignments_update_geometry(code,radius):
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1='+code+'\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['geometry']['radius_ndc']==pytest.approx(radius)


def test_compound_persistent_local_is_not_replaced_by_its_init_value():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_init1=k=.3;\n'
        'shape_0_per_frame1=k+=.1;rad=k;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['geometry']['radius_ndc'] is None


def test_eel_guarded_small_denominator_does_not_create_huge_nominal_shape():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=d=.000001;rad=.1/d;\n')
    assert not any(e['id']=='shape_0' for e in appearance(source)['elements'])


def test_nested_assignment_aliases_are_not_folded_as_value_snapshots():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=rad=(rad=.2)+(rad=.3);\n'))
    assert any('reference aliases' in r['reason'] for r in result['execution_unknowns'])


def test_shape_motion_exports_linear_drift_and_sinusoidal_excursion():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*time;y=.5+.2*sin(2*time);ang=.3*time;\n'))
    element=next(e for e in result['elements'] if e['id']=='shape_0')
    controls={r['control']:r for r in element['motion_controls']}
    assert controls['position_x']['curve_kind']=='linear_time'
    assert controls['position_x']['signed_linear_rate_per_second']==pytest.approx(.1)
    assert controls['position_y']['curve_kind']=='sinusoidal_time'
    assert controls['position_y']['nominal_value_range']==pytest.approx([.3,.7])
    assert controls['position_y']['period_seconds']==pytest.approx(math.pi)
    assert controls['position_y']['maximum_absolute_control_rate_per_second']==pytest.approx(.4)
    assert controls['rotation']['signed_linear_rate_per_second']==pytest.approx(.3)
    assert all(r['visible_motion_speed'] is None for r in controls.values())


def test_constant_feedback_rotation_is_not_stationary_image_claim():
    result=appearance(read('fWaveAlpha=0\nper_frame_1=rot=.02;\n'))
    element=next(e for e in result['elements'] if e['id']=='mesh_warp')
    rotation=next(r for r in element['motion_controls'] if r['control']=='rotation')
    assert rotation['curve_kind']=='constant'
    assert rotation['constant_value']==pytest.approx(.02)
    assert rotation['maximum_absolute_control_rate_per_second']==0
    assert rotation['application']=='feedback sampling transform each step'
    assert rotation['visible_motion_speed'] is None
    assert result['activity']['motion_intensity']['value'] is None


@pytest.mark.parametrize('formula',['.5+sin(time*time)','bass*.1','k'])
def test_unsupported_motion_curve_keeps_unknown_rate(formula):
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x='+formula+';\n'))
    element=next(e for e in result['elements'] if e['id']=='shape_0')
    control=next(r for r in element['motion_controls'] if r['control']=='position_x')
    assert control['curve_kind']=='unknown'
    assert control['maximum_absolute_control_rate_per_second'] is None


def test_motion_oscillator_outside_colour_range_is_still_a_valid_source_curve():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=2+.1*cos(-3*time+1);\n'))
    element=next(e for e in result['elements'] if e['id']=='shape_0')
    control=next(r for r in element['motion_controls'] if r['control']=='position_x')
    assert control['curve_kind']=='sinusoidal_time'
    assert control['maximum_absolute_control_rate_per_second']==pytest.approx(.3)
    assert control['nominal_value_range']==pytest.approx([1.9,2.1])


def test_native_mesh_families_and_motion_controls_share_one_element():
    result=appearance(read('fWaveAlpha=0\nper_frame_1=zoom=1.02;rot=.02;\n'))
    mesh=[e for e in result['elements'] if e['stage']=='mesh_warp']
    assert len(mesh)==1 and mesh[0]['id']=='mesh_warp'
    assert 'radial_feedback_transform' in mesh[0]['mechanisms']
    assert mesh[0]['legacy_ids']==['shader_mesh_warp']
    assert mesh[0]['motion_controls']


@pytest.mark.parametrize('formula,value',[('(.5+.2*sin(time))*0',0),('.5+.2*sin(0*time+1)',.5+.2*math.sin(1))])
def test_inactive_motion_oscillators_are_constant_without_period(formula,value):
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=x='+formula+';\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    control=next(r for r in element['motion_controls'] if r['control']=='position_x')
    assert control['curve_kind']=='constant'
    assert control['constant_value']==pytest.approx(value)
    assert control['period_seconds'] is None and control['frequency_hz'] is None
    assert control['maximum_absolute_control_rate_per_second']==0


@pytest.mark.parametrize('code',['per_frame_1=k=time;\n','per_frame_init_1=k=.3;\n'])
def test_private_main_locals_do_not_become_per_pixel_motion(code):
    result=appearance(read('fWaveAlpha=0\n'+code+'per_pixel_1=rot=k;\n'))
    control=next(r for e in result['elements'] if e['id']=='mesh_warp' for r in e['motion_controls'] if r['control']=='rotation')
    assert control['curve_kind']=='unknown'
    assert control['maximum_absolute_control_rate_per_second'] is None


def test_per_pixel_q_copy_still_carries_main_time_curve():
    result=appearance(read('fWaveAlpha=0\nper_frame_1=q1=time;\nper_pixel_1=rot=q1;\n'))
    control=next(r for e in result['elements'] if e['id']=='mesh_warp' for r in e['motion_controls'] if r['control']=='rotation')
    assert control['signed_linear_rate_per_second']==1


def test_per_pixel_readonly_time_is_loaded_before_main_frame_writes():
    result=appearance(read('fWaveAlpha=0\nper_frame_1=time=.3;\nper_pixel_1=rot=time;\n'))
    control=next(r for e in result['elements'] if e['id']=='mesh_warp' for r in e['motion_controls'] if r['control']=='rotation')
    assert control['signed_linear_rate_per_second']==1


def test_per_pixel_q_accumulation_is_not_a_constant_for_all_vertices():
    result=appearance(read('fWaveAlpha=0\nper_frame_init_1=q1=.3;\nper_pixel_1=q1+=.1;rot=q1;\n'))
    control=next(r for e in result['elements'] if e['id']=='mesh_warp' for r in e['motion_controls'] if r['control']=='rotation')
    assert control['curve_kind']=='unknown'


def test_per_pixel_readonly_writes_can_accumulate_across_vertices():
    result=appearance(read('fWaveAlpha=0\nper_pixel_1=time+=.1;rot=time;\n'))
    control=next(r for e in result['elements'] if e['id']=='mesh_warp' for r in e['motion_controls'] if r['control']=='rotation')
    assert control['curve_kind']=='unknown'


def test_composition_separates_feedback_draws_from_display_composite():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'PSVERSION_COMP=2\ncomp_1=`shader_body {ret=GetPixel(uv)*2;}\n'))
    composition=result['composition']
    assert composition['normal_feedback_flow']==['previous_main','warp','drawing_and_filters','retained_main']
    assert composition['normal_display_flow']==['retained_main','flip_or_diffusion_exact_copy','composite','display']
    assert composition['display_elements'][0]=='shape_0'
    assert composition['shader_sample_reads']['composite'][0]['source_role']=='current_warp_with_draws'
    assert composition['render_context_resolved'] is False


def test_composite_constant_hides_draws_without_claiming_no_feedback_producers():
    result=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'PSVERSION_COMP=2\ncomp_1=`shader_body {ret=0;}\n'))
    composition=result['composition']
    assert 'shape_0' not in composition['display_elements']
    assert composition['configured_drawing_order']==['shape_0']
    assert composition['shader_sample_reads']['composite']==[]


def test_blur_read_age_remains_unknown_without_render_context():
    result=appearance(shader('shader_body {ret=GetBlur1(uv);}'))
    read=result['composition']['shader_sample_reads']['composite'][0]
    assert read['source_role']=='blur_history'
    assert read['frame_age'] is None
    assert result['composition']['feedback_detail_path']=='conditional_on_render_context'


def test_dead_sampler_does_not_create_a_composition_read():
    result=appearance(shader('shader_body {float3 unused=GetPixel(uv);ret=0;}'))
    assert result['composition']['shader_sample_reads']['composite']==[]


def test_warp_clip_keeps_stale_composite_influence_unresolved():
    result=appearance(shader('shader_body {clip(uv.x-.5);ret=0;}',stage='warp'))
    composition=result['composition']
    assert composition['warp_discard_or_incomplete_write']=='possible_or_unresolved'
    assert composition['composite_feedback_influence']=='normally_display_only_but_stale_pixels_may_feed_back'


@pytest.mark.parametrize('mask',['int(.8)','int(.8)+int(-.8)'])
def test_typed_zero_masks_remove_composition_reads_and_upstream_display(mask):
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nPSVERSION_COMP=2\n'
        'comp_1=`shader_body {float2 p=uv-.5;ret=GetPixel(float2(atan2(p.y,p.x),1/length(p)))*('+mask+');}\n')
    result=appearance(source)
    assert result['composition']['shader_sample_reads']['composite']==[]
    assert result['composition']['display_elements']==[]
    assert not any(5 in e['family_codes'] for e in result['elements'])


def test_typed_nonzero_integer_mask_retains_composition_read():
    result=appearance(shader('shader_body {ret=GetPixel(uv)*int(1.8);}'))
    assert len(result['composition']['shader_sample_reads']['composite'])==1


def test_uniform_integer_vector_zero_mask_removes_feedback_dependency():
    result=appearance(shader('shader_body {ret=GetPixel(uv)*int3(.8,.8,.8);}'))
    assert result['composition']['shader_sample_reads']['composite']==[]


def test_dead_data_slice_keeps_loop_execution_obligation():
    result=appearance(shader('shader_body {for(int n=0;n<2;n++){}ret=GetPixel(uv)*int(.8);}'))
    assert result['composition']['shader_sample_reads']['composite']==[]
    assert result['execution_unknowns']


@pytest.mark.parametrize('cast',['float(16777217)','(float)16777217'])
def test_scalar_float_narrowing_removes_a_rounded_zero_mask(cast):
    result=appearance(shader('shader_body {ret=GetPixel(uv)*('+cast+'-16777216.0);}'))
    assert result['composition']['shader_sample_reads']['composite']==[]


def test_shape_material_exports_fill_gradient_border_and_blend():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_additive=1\n'
        'shapecode_0_r=1\nshapecode_0_g=0\nshapecode_0_b=0\nshapecode_0_a=.8\n'
        'shapecode_0_r2=0\nshapecode_0_g2=1\nshapecode_0_b2=0\nshapecode_0_a2=.2\n'
        'shapecode_0_border_r=0\nshapecode_0_border_g=0\nshapecode_0_border_b=1\nshapecode_0_border_a=.3\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['centre_vertex_rgba']==pytest.approx([1,0,0,.8],abs=2e-7)
    assert material['perimeter_vertex_rgba']==pytest.approx([0,1,0,.2],abs=2e-7)
    assert material['border_vertex_rgba']==pytest.approx([0,0,1,.3],abs=2e-7)
    assert material['blend_mode']=='source_alpha_additive'
    assert material['texture']['role']=='untextured_vertex_gradient'
    assert material['final_palette_verified'] is False


def test_material_colour_wrap_uses_existing_native_modulo_policy():
    from primitives import colour_modulo
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=r=1.2;g=-.2;\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['centre_vertex_rgba'][:2]==pytest.approx(colour_modulo([1.2,-.2]).tolist())
    assert material['centre_vertex_rgba'][0]<.3


def test_dynamic_material_channel_remains_unknown_without_hiding_other_colours():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=r=bass*.2;\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['centre_vertex_rgba'][0] is None
    assert material['centre_vertex_rgba'][1:]==pytest.approx([0,0,1],abs=2e-7)


def test_named_shape_texture_is_request_with_fallback_not_observed_binding():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_textured=1\n'
        'shapecode_0_image=my-colours\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['texture']['requested_name']=='my-colours'
    assert material['texture']['role']=='named_image_request'
    assert material['texture']['fallback_role']=='previous_main'
    assert material['texture']['actual_asset_sha256'] is None


def test_textured_shape_without_name_uses_previous_main_role():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_textured=1\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['texture']['role']=='previous_main'


def test_fractional_material_style_flags_follow_native_integer_conversion():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=textured=.9;additive=.9;\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['blend_mode']=='source_alpha_over'
    assert material['texture']['role']=='untextured_vertex_gradient'


def test_dynamic_additive_flag_exports_its_per_frame_expression():
    # CustomShape::Draw reads additive after each instance's per-frame code: a beat-switched blend
    # (additive = q1) must reach readers as an expression, not only as an unknown blend mode.
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nper_frame_1=q1=above(bass,1.5);\n'
        'shape_0_per_frame1=additive=q1;\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['blend_mode'] is None
    expression=material['flag_expressions']['additive']
    from eel_memory import evaluate_np
    assert float(evaluate_np(expression,{'bass':2.})) == 1. and float(evaluate_np(expression,{'bass':1.})) == 0.


def test_shape_state_read_only_by_the_blend_flag_is_stepped():
    # additive = flip with a persistent flip (EoS - dark side of the moon): the recurrence must include
    # flip, or the frame's blend cannot be evaluated.
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_textured=1\n'
        'shape_0_per_frame1=flip=(flip+.6)*below(flip,1.1);additive=flip;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert 'flip' in element['frame_recurrence']['state']


def test_negative_border_alpha_can_wrap_positive_but_outline_stays_disabled():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshape_0_per_frame1=border_a=-.2;\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['border_vertex_rgba'][3]>.7
    assert material['border_draw_enabled'] is False


def test_audio_routes_cover_edge_border_and_texture_material_controls():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_textured=1\nshapecode_0_border_a=.5\n'
        'shape_0_per_frame1=r2=bass*.2;border_b=treb*.3;a2=mid*.1;tex_ang=bass_att*.4;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    routes={(r['control'],r['input_code']) for r in element['audio_routes']}
    assert {('perimeter_colour_r',1),('border_colour_b',3),('perimeter_opacity',2),('texture_rotation',4)}<=routes


def test_unused_texture_and_disabled_border_colour_routes_are_not_live():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=tex_ang=bass;border_r=mid;border_a=-.2;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert not any(r['control'] in {'texture_rotation','border_colour_r'} for r in element['audio_routes'])


def test_border_enable_threshold_uses_native_float_literal_against_double_equation_value():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=border_a=.0001;border_r=mid;\n')
    element=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')
    assert element['material']['border_draw_enabled'] is True
    assert any(r['control']=='border_colour_r' and r['input_code']==2 for r in element['audio_routes'])


def test_configured_border_threshold_is_float32_equal_and_disabled():
    source=read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_border_a=.0001\n')
    material=next(e for e in appearance(source)['elements'] if e['id']=='shape_0')['material']
    assert material['border_draw_enabled'] is False


def test_fixed_warp_decay_has_nominal_gain_not_display_composite_gain():
    source=read('fWaveAlpha=0\nfDecay=.98\nPSVERSION_COMP=2\n'
        'comp_1=`shader_body {ret=GetPixel(uv)*2;}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==pytest.approx(.98)
    assert feedback['nominal_half_life_warp_evaluations']==pytest.approx(math.log(.5)/math.log(.98),rel=2e-6)
    assert feedback['actual_feedback_persistence'] is None


def test_custom_warp_ret_does_not_implicitly_apply_configured_decay():
    source=read('fWaveAlpha=0\nfDecay=.5\nPSVERSION_WARP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv);}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==1
    assert feedback['nominal_half_life_warp_evaluations'] is None


def test_warp_colour_transfer_tracks_channel_mixing_and_bias():
    feedback=appearance(shader('shader_body {ret=GetPixel(uv).bgr*float3(.8,.9,1.1)+float3(.1,0,0);}',stage='warp'))['feedback_transfer']
    for actual,expected in zip(feedback['matrix_rgb'],[[0,0,.8],[0,.9,0],[1.1,0,0]]):
        assert actual==pytest.approx(expected,abs=2e-7)
    assert feedback['constant_offset_rgb']==pytest.approx([.1,0,0],abs=2e-7)
    assert feedback['coordinate_feedback_dependency'] is False


def test_multicopy_feedback_weight_counts_samples_at_different_positions():
    feedback=appearance(shader('shader_body {ret=GetPixel(uv)*.6+GetPixel(uv*.5)*.6;}',stage='warp'))['feedback_transfer']
    assert feedback['direct_colour_gain_norm']==pytest.approx(1.2,abs=2e-7)
    assert feedback['source_sample_sites']==2


def test_image_driven_coordinates_cannot_certify_feedback_attenuation():
    feedback=appearance(shader('shader_body {ret=GetPixel(uv+.1*GetPixel(uv).rg)*.8;}',stage='warp'))['feedback_transfer']
    assert feedback['coordinate_feedback_dependency'] is True
    assert feedback['nominal_half_life_warp_evaluations'] is None


@pytest.mark.parametrize('body',['ret=GetPixel(uv)*bass;','ret=pow(GetPixel(uv),2);','ret=GetBlur1(uv);'])
def test_unsupported_feedback_colour_transfer_retains_unknown_model(body):
    feedback=appearance(shader('shader_body {'+body+'}',stage='warp'))['feedback_transfer']
    assert feedback['matrix_rgb'] is None
    assert feedback['unknown_reasons']


def test_negative_feedback_gain_is_not_slow_positive_trail_claim():
    feedback=appearance(shader('shader_body {ret=GetPixel(uv)*-.9;}',stage='warp'))['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==pytest.approx(-.9,abs=2e-7)
    assert feedback['nominal_half_life_warp_evaluations'] is None


def test_known_coordinate_feedback_dependency_survives_another_unknown_coordinate_path():
    body='shader_body {float2 q=uv;for(int n=0;n<2;n++){q+=.01;}'\
         'ret=GetPixel(uv+.1*GetPixel(uv).rg)*.4+GetPixel(q)*.4;}'
    feedback=appearance(shader(body,stage='warp'))['feedback_transfer']
    assert feedback['coordinate_feedback_dependency'] is True


def test_colour_processing_preserves_power_then_inversion_order():
    result=appearance(shader('shader_body {ret=1-pow(GetPixel(uv),.5);}'))
    record=result['colour_processing']['stages']['composite']
    assert record['channels'][0]['base']['kind']=='sample_channel'
    assert [s['operation'] for s in record['channels'][0]['steps_from_base']]==['abs','power','domain_guard','one_minus']
    assert record['channels'][0]['steps_from_base'][1]['value']==pytest.approx(.5)
    assert record['final_palette_verified'] is False


def test_rgb_tint_bias_and_clamp_are_recorded_per_channel():
    result=appearance(shader('shader_body {ret=saturate(GetPixel(uv)*float3(.5,1,2)+float3(.1,0,-.1));}'))
    channels=result['colour_processing']['stages']['composite']['channels']
    assert [s['operation'] for s in channels[0]['steps_from_base']]==['multiply_constant','add_constant','saturate']
    assert channels[0]['steps_from_base'][0]['value']==pytest.approx(.5)
    assert channels[2]['steps_from_base'][0]['value']==2


def test_swizzled_sample_colour_channels_are_explicit():
    result=appearance(shader('shader_body {ret=GetPixel(uv).bgr;}'))
    channels=result['colour_processing']['stages']['composite']['channels']
    assert [c['base']['sample_channel'] for c in channels]==[2,1,0]


def test_dynamic_power_is_not_exported_as_a_constant_gamma():
    result=appearance(shader('shader_body {ret=pow(GetPixel(uv),bass);}'))
    channels=result['colour_processing']['stages']['composite']['channels']
    assert not any(s['operation']=='power' for c in channels for s in c['steps_from_base'])
    assert channels[0]['base']['kind']=='source_expression'


def test_alpha_only_colour_operations_do_not_enter_rgb_processing():
    result=appearance(shader('shader_body {ret=float4(.2,.3,.4,pow(GetPixel(uv).a,2));}'))
    channels=result['colour_processing']['stages']['composite']['channels']
    assert all(c['base']['kind']=='constant' and not c['steps_from_base'] for c in channels)


def test_missing_custom_stage_has_unknown_processing_not_fabricated_shader_chain():
    result=appearance(read('fWaveAlpha=0\nPSVERSION_COMP=2\ncomp_1=`shader_body {ret=bad_unknown_name;}\n'))
    stage=result['colour_processing']['stages']['composite']
    assert stage['channels'] is None
    assert stage['unknown_reasons']


def test_warp_transfer_resolves_supplied_vertex_decay_factor():
    source=read('fWaveAlpha=0\nfDecay=.9\nPSVERSION_WARP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv)*_vDiffuse.rgb;}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==pytest.approx(.9,abs=2e-7)
    assert feedback['vertex_colour_binding']['rgba']==pytest.approx([.9,.9,.9,1],abs=2e-7)


def test_dynamic_vertex_decay_does_not_invent_constant_transfer():
    source=read('fWaveAlpha=0\nper_frame_1=decay=.8+.1*bass;\nPSVERSION_WARP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv)*_vDiffuse.rgb;}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain'] is None
    assert feedback['vertex_colour_binding']['rgba']==[None,None,None,1]
    assert feedback['unknown_reasons']==['native vertex colour decay is not a supported constant']


def test_custom_vertex_alpha_is_one_and_does_not_apply_decay_twice():
    source=read('fWaveAlpha=0\nfDecay=.9\nPSVERSION_WARP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv)*_vDiffuse.a;}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==1


def test_supplied_vertex_decay_is_capped_before_custom_warp_use():
    source=read('fWaveAlpha=0\nfDecay=1.5\nPSVERSION_WARP=2\n'
        'warp_1=`shader_body {ret=GetPixel(uv)*_vDiffuse.r;}\n')
    feedback=appearance(source)['feedback_transfer']
    assert feedback['uniform_diagonal_gain']==1
    assert feedback['vertex_colour_binding']['rgba']==[1,1,1,1]


def test_fractal_with_generated_colour_marks_conditional_psychedelic_potential():
    source=read('PSVERSION_WARP=2\nPSVERSION_COMP=2\n'
        'warp_1=`shader_body {float2 z=uv-.5;for(int n=0;n<4;n++){'
        'z=float2(z.x*z.x-z.y*z.y,2*z.x*z.y)+float2(.1,.2);}ret=GetPixel(z);}\n'
        'comp_1=`shader_body {ret=(.5+.5*cos(time+float3(0,2,4)))*GetPixel(uv).r;}\n')
    result=appearance(source)
    assert any(7 in element['family_codes'] for element in result['elements'])
    assert result['mood_matches']['psychedelic']['candidate'] is True
    assert result['mood_matches']['psychedelic']['confidence'] is None
    assert result['mood_matches']['chill']['eligible'] is None


def test_exported_control_formulas_keep_texture_identity_and_obligations():
    expressions=[]
    for name in ['main','noise_lq','blur1']:
        result=appearance(shader('shader_body {ret=tex2D(sampler_'+name+',uv).rgb*bass;}'))
        element=next(e for e in result['elements'] if e['id']=='shader_composite')
        expression=element['audio_routes'][0]['expression']
        sample=next(n for n in expression['nodes'] if n['op']=='sample')
        assert sample['detail']['canonical_texture']==name
        assert sample['detail']['sampler']=='sampler_'+name
        assert expression['resources_resolved'] is False
        expressions.append(json.dumps(expression,sort_keys=True))
    assert len(set(expressions))==3


def test_per_frame_side_count_is_exported_as_a_motion_control():
    from test_effect_families import read
    record = appearance(read('shapecode_0_enabled=1\nshapecode_0_textured=1\nshapecode_0_rad=1.4\n'
                             'shape_0_per_frame1=sides=int(abs(sin(time*.5)*7));\n'))
    shape = next(e for e in record['elements'] if e.get('id') == 'shape_0')
    assert [c['control'] for c in shape['motion_controls']].count('side_count') == 1
    fixed = appearance(read('shapecode_0_enabled=1\nshapecode_0_sides=5\n'))
    assert 'side_count' not in [c['control'] for e in fixed['elements'] if e.get('id') == 'shape_0' for c in e['motion_controls']]
