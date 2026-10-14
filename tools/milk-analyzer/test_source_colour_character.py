"""General source colour controls; no image palette or sampled time fitting."""
import math
from types import SimpleNamespace
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile

import pytest


def character(elements, *, weights=None, processing=None, transfer=None):
    from source_colour_character import colour_character
    analysis=SimpleNamespace(source={'preset_sha256':'a'*64,'parser_inputs':{}},values={},main={},
                             outputs={},stages={'composite':{'kind':'custom_composite'}},profile='gles300')
    description={'elements':elements,'colour_processing':{'stages':{'composite':processing or {}}},
                 'texture_colour_transfer':{'stages':{'composite':transfer or {}}}}
    prominence={'by_component':{e['id']:{'displayed_contribution_interval':(weights or {}).get(e['id'],[0,.5]),
        'known_invalid_native_domain':False,'unknown_reasons':[]} for e in elements}}
    result=colour_character(analysis,description,prominence,{'viewport':[1920,1080],'feedback_fps':30})
    json.dumps(result,allow_nan=False)
    return result


def shape(center,edge=None, *, identity='shape_0',alpha=1,textured=False):
    return {'id':identity,'stage':'drawing','material':{'centre_vertex_rgba':[*center,alpha],
        'perimeter_vertex_rgba':[*list(center if edge is None else edge),alpha],
        'border_vertex_rgba':[0,0,0,0],'border_draw_enabled':False,
        'texture':{'role':'previous_main' if textured else 'untextured_vertex_gradient'},'unknown_reasons':[]}}


@pytest.mark.parametrize('rgb,family',[
    ([.5,.5,.5],'grayscale'),([1,0,0],'red'),([1,.5,0],'orange'),([1,1,0],'yellow'),
    ([0,1,0],'green'),([0,1,1],'cyan'),([0,0,1],'blue'),([.5,0,1],'purple'),([1,0,.5],'pink')])
def test_native_constant_material_exports_real_hsv_family(rgb,family):
    component=character([shape(rgb)])['by_component']['shape_0']
    assert component['source_palette']['anchors'][0]['hue_family']==family
    assert component['source_palette']['hue_families_possible']==[family]
    assert component['status']=='known_source_colour'


def test_warm_gradient_includes_intermediate_orange_without_sampling_pixels():
    component=character([shape([1,0,0],[1,1,0])])['by_component']['shape_0']
    assert set(component['source_palette']['hue_families_possible'])=={'red','orange','yellow'}
    assert component['source_palette']['temperature_candidates']==['warm']
    assert component['source_palette']['model']=='native_vertex_gradient_box'


def test_cool_gradient_and_partial_unknown_channels_retain_quantified_constraints():
    cool=character([shape([0,0,1],[0,1,1])])['by_component']['shape_0']
    partial=character([shape([1,None,0])])['by_component']['shape_0']
    assert set(cool['source_palette']['hue_families_possible'])=={'blue','cyan'}
    assert partial['status']=='partial_source_colour'
    assert set(partial['source_palette']['hue_families_possible'])=={'red','orange','yellow'}
    assert partial['source_palette']['rgb_component_intervals']==[[1,1],[0,1],[0,0]]


def test_builtin_wave_reuses_normalized_native_colour_and_alpha_contract():
    element={'id':'builtin_wave','stage':'drawing','wave_material':{'constant_vertex_rgb':[0,.5,1],
        'rgb_component_envelopes':[[0,0],[.5,.5],[1,1]],'alpha_recipe':{'final_alpha_envelope':[.5,.5]}}}
    component=character([element])['by_component']['builtin_wave']
    assert component['source_palette']['anchors'][0]['rgb']==[0,.5,1]
    assert component['source_palette']['hue_families_possible']==['blue']


def test_inherited_feedback_is_not_a_known_hue_or_a_useful_descriptor():
    element={'id':'shader_warp','stage':'warp','colour':{'mode_code':4}}
    result=character([element]);component=result['by_component']['shader_warp']
    assert component['status']=='inherited_colour'
    assert component['source_palette']['hue_families_possible']==[]
    assert result['candidate_palette_hierarchy']==[]
    assert result['useful_hue_description'] is False


def test_textured_white_keeps_feedback_palette_unknown_and_red_tint_is_conditional():
    white=character([shape([1,1,1],textured=True)])['by_component']['shape_0']
    red=character([shape([1,0,0],textured=True)])['by_component']['shape_0']
    assert white['status']=='inherited_colour'
    assert white['source_palette']['hue_families_possible']==[]
    assert red['status']=='inherited_tinted_colour'
    assert set(red['source_palette']['hue_families_possible'])=={'red','grayscale'}


def test_zero_prominence_excludes_accents_but_invalid_domain_remains_unknown():
    elements=[shape([1,0,0]),shape([0,0,1],identity='shape_1')]
    result=character(elements,weights={'shape_0':[0,0],'shape_1':[0,.01]})
    assert result['by_component']['shape_0']['eligible_accent'] is False
    assert {r['hue_family'] for r in result['candidate_palette_hierarchy']}=={'blue'}


def test_palette_hierarchy_weights_contribution_and_caps_overlapping_upper_bounds():
    elements=[shape([1,0,0]),shape([0,0,1],identity='shape_1'),shape([1,0,0],identity='shape_2')]
    result=character(elements,weights={'shape_0':[0,.8],'shape_1':[0,.02],'shape_2':[0,.8]})
    assert result['candidate_palette_hierarchy'][0]['hue_family']=='red'
    assert result['candidate_palette_hierarchy'][0]['weight_interval']==[0,1]
    assert all(row['weight_interval'][0]==0 for row in result['candidate_palette_hierarchy'])


def test_final_pointwise_channel_processing_propagates_tint_inversion_and_gamma():
    processing={'channels':[{'base':{'kind':'sample_channel','canonical_texture':'main','sample_channel':i},
        'steps_from_base':[{'operation':'power','value':2},{'operation':'one_minus'}]} for i in range(3)]}
    component=character([shape([1,0,0])],processing=processing)['by_component']['shape_0']
    assert component['final_candidate_palette']['anchors'][0]['rgb']==[0,1,1]
    assert component['final_candidate_palette']['hue_families_possible']==['cyan']


def test_generic_affine_rgb_matrix_and_offset_transform_palette_without_case_rules():
    transfer={'source_model':'affine_sample_colour','coordinate_sample_dependency':False,
        'base_uv_matrix_rgb':[[0]*4]*3,'constant_offset_rgb':[0,0,0],
        'sample_contributions':[{'canonical_texture':'main','matrix_rgb_rgba':[[0,0,.5,0],[0,1,0,0],[1,0,0,0]],
        'coordinate_expression':None}]}
    component=character([shape([1,0,0])],transfer=transfer)['by_component']['shape_0']
    assert component['final_candidate_palette']['anchors'][0]['rgb']==[0,0,1]
    assert component['final_candidate_palette']['transfer_model']=='conditional_affine_main_rgb'


def test_dynamic_generated_colour_reports_source_box_without_claiming_reached_diversity():
    element={'id':'shader_composite','stage':'composite','colour':{'mode_code':3,
        'bias_rgb':[.5]*3,'amplitude_rgb':[.5]*3,'phase_offsets_rad':[0,2,4]}}
    component=character([element])['by_component']['shader_composite']
    assert component['status']=='dynamic_source_colour'
    assert component['source_palette']['rgb_component_intervals']==[[0,1]]*3
    assert component['source_palette']['reached_palette_verified'] is False


def test_unknown_nonlinear_processing_does_not_relabel_source_as_final_colour():
    processing={'channels':[{'base':{'kind':'source_expression'},'steps_from_base':[]}]*3}
    component=character([shape([1,0,0])],processing=processing)['by_component']['shape_0']
    assert component['source_palette']['hue_families_possible']==['red']
    assert component['final_candidate_palette']['hue_families_possible']==[]
    assert component['unknown_reasons']


def source_character(raw):
    import effect_families as ef
    from source_colour_character import colour_character
    from source_appearance import appearance_from_analysis
    from source_prominence import prominence_evidence
    raw=('MILKDROP_PRESET_VERSION=201\n[preset00]\nPSVERSION_COMP=0\nfWaveAlpha=0\n'+raw).encode()
    reader=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/adapters/milk-native-reader'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'colour.milk';path.write_bytes(raw)
        source=json.loads(subprocess.check_output([str(reader),str(path)]))
    source['preset_sha256']=hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    token=ef._CACHE.set({})
    try:
        analysis=ef._Analysis(source,'gles300',None);analysis.input_scenario=None
        analysis.main_equations();analysis.primitives()
        analysis.shader('warp','warp_');analysis.shader('composite','comp_');analysis.contribution_gates()
        description=appearance_from_analysis(analysis)
        context={'viewport':[1920,1080],'feedback_fps':30}
        result=colour_character(analysis,description,prominence_evidence(analysis,description,context),context)
    finally:ef._CACHE.reset(token)
    json.dumps(result,allow_nan=False)
    return result


def test_actual_custom_wave_frame_and_point_colours_use_native_modulo_and_host_domains():
    result=source_character('wavecode_0_enabled=1\nwavecode_0_r=1\nwavecode_0_g=0\nwavecode_0_b=0\n'
        'wave_0_per_frame1=r=0;g=1;\nwave_0_per_point1=g=0;b=1;\n')
    component=result['by_component']['wave_0']
    assert component['source_palette']['hue_families_possible']==['blue']
    assert component['source_palette']['anchors'][0]['rgb'][2]==pytest.approx(1)


def test_actual_point_domain_produces_warm_gradient_without_audio_or_time_samples():
    result=source_character('wavecode_0_enabled=1\nwave_0_per_point1=r=1;g=sample;b=0;\n')
    component=result['by_component']['wave_0']
    assert set(component['source_palette']['hue_families_possible'])=={'red','orange','yellow'}
    assert component['source_palette']['channel_domain_evidence']['g']['declared_input_domains']=={'sample':[0,1]}


def test_known_invalid_native_wave_colour_remains_unknown_even_with_zero_alpha():
    result=source_character('wavecode_0_enabled=1\nwave_0_per_point1=r=1e100;g=0;b=0;a=0;\n')
    component=result['by_component']['wave_0']
    assert component['status']=='unknown_colour'
    assert component['eligible_accent'] is True
    assert component['source_palette']['hue_families_possible']==[]


def test_native_legacy_inversion_changes_red_candidate_into_cyan():
    result=source_character('fGammaAdj=1\nbInvert=1\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=1;g=0;b=0;r2=1;g2=0;b2=0;a=1;a2=1;\n')
    component=result['by_component']['shape_0']
    assert component['source_palette']['hue_families_possible']==['red']
    assert component['final_candidate_palette']['hue_families_possible']==['cyan']


def test_disabled_native_legacy_tint_keeps_shared_gray_and_exact_box():
    result=source_character('fGammaAdj=1\nfShader=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=.5;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;border_a=0;\n')
    component=result['by_component']['shape_0']
    assert component['final_candidate_palette']['rgb_component_intervals']==component['source_palette']['rgb_component_intervals']
    assert component['final_candidate_palette']['hue_families_possible']==['grayscale']


def test_dynamic_shared_gray_stays_gray_through_untinted_identical_filters():
    result=source_character('fGammaAdj=1\nfShader=0\nbBrighten=1\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=.5+.4*sin(time);g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;border_a=0;\n')
    assert result['by_component']['shape_0']['final_candidate_palette']['hue_families_possible']==['grayscale']


def test_native_legacy_tint_amount_controls_the_colour_box():
    result=source_character('fGammaAdj=1\nfShader=.3\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=1;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;border_a=0;\n')
    box=result['by_component']['shape_0']['final_candidate_palette']['rgb_component_intervals']
    assert all(span[0]>.89 and span[0]<.91 for span in box)


def test_legacy_brighten_interval_is_ordered_and_encloses_both_endpoints():
    result=source_character('fGammaAdj=1\nfShader=0\nbBrighten=1\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=r=.2+.1*sin(time);g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;border_a=0;\n')
    box=result['by_component']['shape_0']['final_candidate_palette']['rgb_component_intervals']
    assert box[0][0]<=box[0][1]
    assert box[0]==pytest.approx([.19,.51],abs=2e-6)


def test_legacy_palette_clamps_stored_main_before_tint_not_after():
    from effect_families import _constant
    from engine_profiles import CORE_2334_ENGINE
    from source_colour_character import _final_palette,_palette
    analysis=SimpleNamespace(source={'values':{'fShader':'1'},'parser_inputs':{'engine':CORE_2334_ENGINE}},
        stages={'composite':{'kind':'legacy_composite'}},main={name:_constant(1 if name=='gamma' else 0)
            for name in ('gamma','echo_alpha','brighten','darken','solarize','invert')})
    source=_palette((),[[2.,3.]]*3,model='raw_warp_rgb_box')
    palette,_=_final_palette(analysis,{}, {'stage':'warp'},source)
    assert source['rgb_component_intervals']==[[2.,3.]]*3
    assert all(span==pytest.approx([2/3,1.]) for span in palette['rgb_component_intervals'])
    assert palette['hue_families_possible']!=['grayscale']


def test_nonlinear_suffix_interval_keeps_interior_extremum_instead_of_only_corners():
    processing={'channels':[{'base':{'kind':'sample_channel','canonical_texture':'main','sample_channel':0},
        'steps_from_base':[{'operation':'add_constant','value':-.5},{'operation':'abs'}]},
        *[{'base':{'kind':'sample_channel','canonical_texture':'main','sample_channel':i},'steps_from_base':[]} for i in (1,2)]]}
    component=character([shape([0,0,0],[1,0,0])],processing=processing)['by_component']['shape_0']
    assert component['final_candidate_palette']['rgb_component_intervals'][0]==pytest.approx([0,.5])


def test_joint_dynamic_native_channel_identity_preserves_grayscale_under_modulo():
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=.5+.5*sin(time);g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;\n')
    component=result['by_component']['shape_0']
    assert component['source_palette']['hue_families_possible']==['grayscale']
    assert component['source_palette']['model']=='correlated_native_shared_scalar_rgb'


def test_separate_random_colour_calls_are_not_a_shared_gray_scalar():
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=int(rand(100))/100;g=int(rand(100))/100;b=int(rand(100))/100;'
        'r2=r;g2=g;b2=b;a=1;a2=1;\n')
    component=result['by_component']['shape_0']
    assert component['source_palette']['model']!='correlated_native_shared_scalar_rgb'
    assert set(component['source_palette']['hue_families_possible'])!={'grayscale'}


def test_copied_single_random_colour_value_keeps_true_gray_correlation():
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=int(rand(100))/100;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;\n')
    component=result['by_component']['shape_0']
    assert component['source_palette']['model']=='correlated_native_shared_scalar_rgb'


def test_distinct_random_calls_cannot_cancel_to_a_constant():
    from effect_families import _EEL,_number,_same
    call={'kind':'call','function':'rand','args':[{'kind':'constant','value':100.}]}
    model=_EEL(equation_phase='shape_0_per_frame')
    a=model.lower(call);b=model.lower(call)
    assert not _same(a,b)
    from shader_fields import Field
    assert _number(Field('subtract',(a,b),'float')) is None
    assert _same(a,a)


def test_quantized_random_native_rgb_exports_bounded_palette_and_refresh_scope():
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=int(rand(100))/100;g=int(rand(100))/100;b=int(rand(100))/100;'
        'r2=r;g2=g;b2=b;a=1;a2=1;\n')
    component=result['by_component']['shape_0']
    recipe=component['source_palette']['stochastic_vertex_colour']
    assert recipe['centre']['shared_random_draw'] is False
    assert len(recipe['centre']['distinct_source_sites'])==3
    from primitives import colour_modulo
    assert recipe['centre']['encoded_rgb_component_intervals']==[[0.,float(colour_modulo(1.))]]*3
    assert recipe['centre']['refresh_scope']=='shape_instance_invocation'
    assert recipe['actual_palette_verified'] is False
    assert result['useful_hue_description']


def test_init_random_palette_is_not_frame_refresh():
    result=source_character('shapecode_0_enabled=1\n'
        'shape_0_init1=shade=rand(100);\n'
        'shape_0_per_frame1=r=shade/100;g=r;b=r;r2=r;g2=r;b2=r;a=1;a2=1;\n')
    recipe=result['by_component']['shape_0']['source_palette']['stochastic_vertex_colour']
    assert recipe['centre']['shared_random_draw'] is True
    assert recipe['centre']['refresh_scope']=='preset_initialization'


@pytest.mark.parametrize('border', ['border_r=1;border_g=0;border_b=0;', 'border_r=bass;border_g=0;border_b=0;'])
def test_random_fill_box_retains_live_constant_or_unknown_border(border):
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=rand(10)/100;g=rand(10)/100;b=rand(10)/100;'
        'r2=r;g2=g;b2=b;a=1;a2=1;border_a=1;'+border+'\n')
    palette=result['by_component']['shape_0']['source_palette']
    assert palette['rgb_component_intervals'][0][1]>.99
    assert palette['rgb_component_intervals'][1][1]<.11


def test_random_fill_box_does_not_include_disabled_border():
    result=source_character('shapecode_0_enabled=1\nshape_0_per_frame1='
        'r=rand(10)/100;g=rand(10)/100;b=rand(10)/100;'
        'r2=r;g2=g;b2=b;a=1;a2=1;border_a=0;border_r=1;\n')
    assert result['by_component']['shape_0']['source_palette']['rgb_component_intervals'][0][1]<.11


def test_random_walk_wave_positions_are_a_stochastic_point_recurrence():
    # Each point steps .01 left or right at random; the walk carries from point to point.
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\nwave_0_init1=mx=.5;\n'
        'wave_0_per_point1=mx=mx+.01*(2*below(rand(2),1)-1);\nwave_0_per_point2=x=mx;y=.5;r=1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['positions_closed_form'] is True and record['stochastic'] is True
    assert set(record['point_recurrence']['state'])=={'mx'}
    low,high=record['position_bounds']['x']
    # 512 steps of .01 from .5: the walk stays far inside +-5.12 and moves off the start.
    assert .5-1.<low<.5<high<.5+1. and high-low>.02


def test_per_point_t_variables_restart_each_frame_from_the_wave_frame_values():
    # CustomWaveform::InitPerPointEvaluationVariables copies q and t from the wave's per-frame context at
    # every frame: a per-point counter in t3 restarts from the per-frame t3; the wave's own variables carry.
    from eel_memory import evaluate_np
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\nwave_0_init1=t4=5;\n'
        'wave_0_per_frame1=t3=2;\nwave_0_per_point1=t3=t3+1;t4=t4+1;mx=mx+1;x=t3/1000+t4/1000+mx/1000;y=.5;r=1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    state=record['point_recurrence']['state']
    assert float(evaluate_np(state['t3']['frame_start'],{}))==2.
    assert float(evaluate_np(state['t4']['frame_start'],{}))==5.
    assert 'frame_start' not in state['mx']


def test_uninitialized_wave_frame_variables_persist_as_wave_state():
    # old is written but never initialised: it persists across frames from 0 (t1 = .01, .02, ...).
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_frame1=t1=old+.01;old=t1;\nwave_0_per_point1=x=sample;y=.5;r=t1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='closed_form_point_colours'
    assert 'old' in record['frame_recurrence']['state']


def test_wave_point_names_never_written_in_the_wave_read_zero():
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_point1=x=sample;y=.5;r=.5+v;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='closed_form_point_colours' and abs(record['mean_rgb'][0]-.5)<1e-9


def test_wave_colours_over_main_frame_state_keep_their_programs_for_frame_stepping():
    result=source_character('per_frame_1=acc=acc+.1;q1=acc;\nwavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_point1=x=sample;y=.5;r=q1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='frame_state_point_colours' and record['mean_rgb'] is None
    assert record['positions_closed_form'] is True and record['programs'] is not None
    assert record['frame_inputs']==['acc']


def test_frame_state_wave_colours_keep_their_waveform_inputs():
    result=source_character('per_frame_1=acc=acc+.1;q1=acc;\nwavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_point1=x=.5+value1;y=.5;r=q1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='frame_state_point_colours' and 'waveform_inputs' in record


def test_spectrum_wave_positions_read_the_spectrum_not_frame_state():
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bSpectrum=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_point1=x=.5+value1;y=sample;r=1;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['waveform_inputs']['params']['spectrum'] is True
    assert 'value1' not in (record.get('frame_inputs') or [])


def test_large_per_point_programs_are_exported():
    # A 3D Lissajous point projected in perspective: well over 256 graph nodes, all closed-form.
    def terms(seed):
        return '+'.join(f'.1*sin(sample*{seed+k}.3+time*.{seed+k})' for k in range(1,13))
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        f'wave_0_per_point1=ox={terms(10)};oy={terms(30)};oz={terms(50)}-3;'
        'mx=ox*cos(time)+oz*sin(time);mz=-ox*sin(time)+oz*cos(time);ox=mx;oz=mz;'
        'my=oy*cos(time*.7)-oz*sin(time*.7);mz=oy*sin(time*.7)+oz*cos(time*.7);oy=my;oz=mz;'
        'x=ox*.5/oz+.5;y=oy*.5/oz+.5;r=1;g=1;b=1;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['positions_closed_form'] is True and record['programs']['x'] is not None


def test_unresolved_point_colour_keeps_closed_form_positions():
    # The colour reads an input nothing defines a domain for; the positions are still drawable.
    result=source_character('wavecode_0_enabled=1\nwavecode_0_bUseDots=1\n'
        'wave_0_per_point1=x=sample;y=.5+.1*sin(sample*6);r=1;g=1;b=1;a=1;\nwave_0_per_point2=r=megabuf(sample*100);\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='unknown'
    assert record['positions_closed_form'] is True and record['programs']['x'] is not None
    assert record['programs'].get('r') is None


def test_recurrence_state_order_is_independent_of_string_hashing():
    # Consumers draw rand values in state order; a set-driven order changed the random walk of every
    # wave between processes (PYTHONHASHSEED), so group measures compared different random draws.
    import os, subprocess, sys
    code = ('import json,sys;sys.path.insert(0,".");from test_source_colour_character import source_character;'
            'r=source_character("wavecode_0_enabled=1\\nwavecode_0_bUseDots=1\\nwave_0_init1=zb=.5;ya=.5;mc=.5;\\n'
            'wave_0_per_point1=zb=zb+.01*(rand(2)-.5);ya=ya+.01*(rand(2)-.5);mc=mc+.01*(rand(2)-.5);\\n'
            'wave_0_per_point2=x=zb;y=ya+mc-.5;r=1;g=0;b=0;a=1;\\n");'
            'd=r["by_component"]["wave_0"]["source_palette"]["point_colour_distribution"];'
            'print(json.dumps([list(d["point_recurrence"]["state"]),d["position_bounds"]]))')
    outputs = {subprocess.run([sys.executable, '-c', code], cwd=os.path.dirname(os.path.abspath(__file__)), capture_output=True, text=True,
                              env={**os.environ, 'PYTHONHASHSEED': seed}).stdout for seed in ('1', '2', '3')}
    assert len(outputs) == 1 and json.loads(outputs.pop())[0] == ['mc', 'ya', 'zb']


def test_per_frame_sample_count_keeps_the_wave_with_its_count_program():
    # samples = 256 + 50*sin(time*.94) (demonlord's opaque black wave_0, which wipes the canvas each frame):
    # the wave must not be dropped; its count at load and the count program for frame stepping are kept.
    from eel_memory import evaluate_np
    result=source_character('wavecode_0_enabled=1\nwavecode_0_samples=102\n'
        'wave_0_per_frame1=samples = 256 + 50*sin(time*.939493949);\n'
        'wave_0_per_point1=x=sample;y=.5;r=0;g=0;b=0;a=1;\n')
    record=result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['status']=='closed_form_point_colours' and record['sample_count']==256
    program=record['sample_count_program']
    assert abs(float(evaluate_np(program,{'time':1.}))-(256+50*math.sin(.939493949)))<1e-6


def test_wave_state_fed_by_a_large_main_per_frame_graph_keeps_its_recurrence():
    # Flexi - alien web bouncer: rot = rot + q6, where q6 inlines the main per-frame physics (474-768 nodes).
    # The recurrence used the 256-node default, so it was dropped and the waves reading rot were never drawn.
    q6 = '+'.join(f'sin(x1*{i}.5)*.0001' for i in range(1, 121))
    result = source_character('per_frame_1=x1=x1+.01;\nper_frame_2=q6=' + q6 + ';\nwavecode_0_enabled=1\nwavecode_0_samples=64\n'
        'wave_0_per_frame1=rot = rot + q6;\nwave_0_per_frame2=t2 = rot;\n'
        'wave_0_per_point1=x=.5+.2*sin(t2+sample*6);y=.5+.2*cos(t2+sample*6);r=1;g=0;b=0;a=1;\n')
    record = result['by_component']['wave_0']['source_palette']['point_colour_distribution']
    assert record['positions_closed_form'] is True and record.get('frame_recurrence')
    assert 'rot' in record['frame_recurrence']['state']
