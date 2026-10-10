"""End-to-end source behaviour uses native selection and declared context."""
import pytest


def analysis(raw, *, qualified=True):
    from test_effect_families import read
    from effect_families import _Analysis
    import hashlib
    source=read(raw)
    compatibility={}
    if qualified:
        for stage,prefix in [('warp','warp_'),('composite','comp_')]:
            if source['sections'].get(prefix,{}).get('source'):
                code=source['sections'][prefix]['source']
                compatibility[stage]={'source_sha256':hashlib.sha256(code.encode()).hexdigest(),
                    'request':{'code':code,'stage':stage,'profile':'gles300'},
                    'translation':{'engine_archive_sha256':source['parser_inputs']['engine_archive_sha256']},
                    'offline_accepted':True}
    a=_Analysis(source,'gles300',compatibility if qualified else None)
    a.input_scenario=None
    a.main_equations();a.primitives();a.shader('warp','warp_');a.shader('composite','comp_');a.contribution_gates()
    return a


def test_declared_context_rejects_invalid_viewport_and_fps():
    from source_static_behaviour import validate_context
    with pytest.raises(ValueError):validate_context({'viewport':[0,1080],'feedback_fps':30})
    with pytest.raises(ValueError):validate_context({'viewport':[1920,1080],'feedback_fps':float('nan')})


def test_constant_qualified_composite_can_have_complete_calm_model():
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.1,.2,.3);}\n')
    result=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30})
    assert result['uses_rendered_images'] is False
    assert result['uses_equation_execution'] is False
    assert result['output_model_complete'] is True
    assert 'Chill' in result['classification']['eligible_bands']


@pytest.mark.parametrize('formula,band',[
    ('.5+.025*sin(.2*time)','Chill'),
    ('.5+.075*sin(6.283185307*time)','Normal'),
    ('.5+.4*sin(25.13274123*time)','Intense'),
])
def test_real_source_uniform_temporal_program_can_qualify_activity_band(formula,band):
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret='+formula+';}\n')
    result=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1000,1000],
        'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,100]}})
    assert result['output_model_complete']
    assert band in result['classification']['eligible_bands']


def test_short_clock_domain_does_not_prove_full_period_contrast_attainment():
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=.5+.4*sin(25*time);}\n')
    result=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1000,1000],
        'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,.001]}})
    assert 'Intense' not in result['classification']['eligible_bands']


@pytest.mark.parametrize('formula',[
    '.5+.4*sin(25*time+uv.x)',
    'GetPixel(uv)*(.5+.4*sin(25*time))',
    '1+.4*sin(25*time)',
])
def test_uniform_full_cycle_weight_does_not_apply_to_spatial_sampled_or_clipped_rgb(formula):
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret='+formula+';}\n')
    result=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1000,1000],
        'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,100]}})
    assert 'Intense' not in result['classification']['eligible_bands']


def test_unqualified_composite_cannot_certify_chill():
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.1,.2,.3);}\n',qualified=False)
    result=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30})
    assert result['output_model_complete'] is False
    assert result['classification']['eligible_bands']==[]


def test_activity_domain_changes_context_identity():
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('fWaveAlpha=0\nfRot=.01\nwarp=0\nzoom=1\n')
    desc=appearance_from_analysis(a)
    first=static_behaviour(a,desc,{'viewport':[1920,1080],'feedback_fps':15})
    second=static_behaviour(a,desc,{'viewport':[1920,1080],'feedback_fps':30})
    assert first['context_sha256']!=second['context_sha256']


def test_declared_input_rate_changes_context_and_reaches_motion_producer():
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    a=analysis('fWaveAlpha=0\nshapecode_0_enabled=1\n'
        'shape_0_per_frame1=x=.5+.1*bass;y=.5;rad=.2;ang=0;sides=4;\n')
    desc=appearance_from_analysis(a)
    base={'viewport':[1000,1000],'feedback_fps':30,'scalar_input_domains':{'bass':[0,2]}}
    one=static_behaviour(a,desc,{**base,'scalar_input_maximum_rates_per_second':{'bass':1}})
    two=static_behaviour(a,desc,{**base,'scalar_input_maximum_rates_per_second':{'bass':2}})
    assert one['context_sha256']!=two['context_sha256']
    rows=[[r for r in report['motion']['contributions'] if r['kind']=='geometry_declared_input_transport'][0] for report in (one,two)]
    assert rows[1]['maximum_speed_vp_per_second']==pytest.approx(2*rows[0]['maximum_speed_vp_per_second'])
    assert one['classification']['eligible_bands']==two['classification']['eligible_bands']==[]


def test_declared_rates_normalize_and_reject_invalid_inputs():
    from source_static_behaviour import validate_context
    base={'viewport':[1000,1000],'feedback_fps':30}
    assert validate_context(base)['scalar_input_maximum_rates_per_second']=={}
    assert validate_context({**base,'scalar_input_maximum_rates_per_second':{'bass':0}})['scalar_input_maximum_rates_per_second']=={'bass':0.}
    with pytest.raises(ValueError):validate_context({**base,'scalar_input_maximum_rates_per_second':{'bass':-1}})


def test_normal_static_export_includes_behaviour_without_execution(tmp_path):
    from effect_family_export import export_preset
    from test_core2331_warp import BINARIES
    path=tmp_path/'behaviour.milk';path.write_text('[preset00]\nfWaveAlpha=0\n')
    result,_=export_preset(path,reader=BINARIES/'milk-native-reader')
    report=result['analysis']['visual_description']['static_behaviour']
    assert report['uses_shader_execution'] is False
    assert report['uses_equation_execution'] is False
    assert report['uses_rendered_images'] is False
    assert report['context']['feedback_fps']==30


def test_changed_behaviour_context_separates_export_cache(tmp_path):
    from effect_family_export import export_preset
    from test_core2331_warp import BINARIES
    path=tmp_path/'behaviour.milk';path.write_text('[preset00]\nfWaveAlpha=0\n')
    kwargs={'reader':BINARIES/'milk-native-reader','cache':tmp_path/'cache'}
    first,_=export_preset(path,behaviour_context={'viewport':[1920,1080],'feedback_fps':15},**kwargs)
    second,hit=export_preset(path,behaviour_context={'viewport':[1920,1080],'feedback_fps':30},**kwargs)
    assert hit is False and first['cache_key']!=second['cache_key']


def test_static_report_joins_hue_candidates_and_hashes_colour_model():
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.1,.2,.3);}\n')
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['colour']['uses_rendered_images'] is False
    assert report['colour']['components']
    assert 'source_colour_character.py' in report['model_sources']


@pytest.mark.parametrize('body',[
    'while(bass>0){}ret=float3(.1,.2,.3);',
    'float x[1]={0};x[int(time)]=1;ret=float3(.1,.2,.3);',
])
def test_unresolved_execution_cannot_certify_constant_output_as_chill(body):
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {'+body+'}\n')
    result=appearance_from_analysis(a)['static_behaviour']
    assert result['output_model_complete'] is False
    assert result['classification']['eligible_bands']==[]


def test_discard_shader_retains_partial_report_without_crashing():
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {clip(-1);ret=float3(.1,.2,.3);}\n')
    result=appearance_from_analysis(a)['static_behaviour']
    assert result['output_model_complete'] is False
    assert result['classification']['eligible_bands']==[]


def test_one_producer_budget_failure_preserves_other_useful_source_evidence(monkeypatch):
    import source_prominence
    from effect_families import _SemanticBudget
    from source_appearance import appearance_from_analysis
    def exhausted(*args):raise _SemanticBudget('synthetic independent prominence budget')
    monkeypatch.setattr(source_prominence,'prominence_evidence',exhausted)
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.1,.2,.3);}\n')
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['flashing']['records']
    assert report['colour']['components']
    assert report['producer_failures']['prominence']['reason']=='synthetic independent prominence budget'
    assert report['output_model_complete'] is False
    assert report['classification']['eligible_bands']==[]


def test_flash_failure_does_not_certify_chill_from_retained_calm_motion(monkeypatch):
    import source_flash_behaviour
    from source_appearance import appearance_from_analysis
    def exhausted(*args):raise ValueError('synthetic incomplete flash model')
    monkeypatch.setattr(source_flash_behaviour,'flash_evidence',exhausted)
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.1,.2,.3);}\n')
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['colour']['components']
    assert report['producer_failures']['flashing']
    assert report['classification']['eligible_bands']==[]
    assert 'Chill' not in report['classification']['predicted_bands']


@pytest.mark.parametrize('offset,expected',[(2.,[1.,1.,1.]),(-2.,[0.,0.,0.])])
def test_fully_saturated_output_retains_raw_response_without_false_intense(offset,expected):
    from source_appearance import appearance_from_analysis
    expression=f'{offset}+.5*sin(time*100)'
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3('+','.join([expression]*3)+');}\n')
    a.behaviour_context={'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,4]}}
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['flashing']['records'][0]['maximum_brightness_change_per_second']>0
    assert report['displayed_output']['constant_rgb']==expected
    assert 'Intense' not in report['classification']['predicted_bands']
    assert report['classification']['flash_possible'] is False


def test_unknown_output_storage_does_not_gain_a_clamp_certificate():
    from source_static_behaviour import static_behaviour
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(2+.5*sin(time*100),2,2);}\n')
    report=static_behaviour(a,appearance_from_analysis(a),
        {'viewport':[1920,1080],'feedback_fps':30,'output_storage':'unknown'})
    assert report['displayed_output']['constant_rgb'] is None
    assert report['output_model_complete'] is False
    assert report['classification']['eligible_bands']==[]


def test_partially_saturated_rgb_keeps_remaining_channel_contrast():
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(2+.5*sin(time*100),2,.5+.1*sin(time*100));}\n')
    a.behaviour_context={'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,4]}}
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['displayed_output']['constant_rgb'] is None
    assert report['displayed_output']['maximum_rgb_difference']==pytest.approx(.2)
    assert report['flashing']['records'][0]['periodic_contrast_range'][1]==pytest.approx(1.)
    assert 'Intense' not in report['classification']['predicted_bands']


def test_output_storage_policy_participates_in_export_cache_identity(tmp_path):
    from effect_family_export import export_preset
    from test_core2331_warp import BINARIES
    path=tmp_path/'storage.milk';path.write_text('[preset00]\nfWaveAlpha=0\n')
    base={'reader':BINARIES/'milk-native-reader','cache':tmp_path/'cache'}
    a,_=export_preset(path,behaviour_context={'viewport':[1920,1080],'feedback_fps':30},**base)
    b,hit=export_preset(path,behaviour_context={'viewport':[1920,1080],'feedback_fps':30,'output_storage':'unknown'},**base)
    assert not hit
    assert a['cache_key']!=b['cache_key']


def test_nominal_saturation_does_not_hide_unbounded_native_phase_domain():
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(2+.5*sin(time*1e38),2,2);}\n')
    report=appearance_from_analysis(a)['static_behaviour']
    assert report['displayed_output']['constant_rgb']==[1.,1.,1.]
    assert report['displayed_output']['native_finite_guard']['status']!='bounded'
    assert report['classification']['eligible_bands']==[]
    assert 'Chill' not in report['classification']['predicted_bands']


@pytest.mark.parametrize('factor,qualified',[(100,True),(1e38,False)])
def test_declared_shader_clock_domain_can_qualify_finite_basic_intermediates(factor,qualified):
    from source_static_behaviour import static_behaviour
    from source_appearance import appearance_from_analysis
    a=analysis(f'PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {{ret=float3(2+.5*sin(time*{factor}),2,2);}}\n')
    report=static_behaviour(a,appearance_from_analysis(a),{'viewport':[1920,1080],'feedback_fps':30,
                          'scalar_input_domains':{'_c2.x':[0,4]}})
    assert (report['displayed_output']['native_finite_guard']['status']=='bounded') is qualified
    if not qualified:assert report['classification']['eligible_bands']==[]


def test_context_preferences_are_exported_and_change_source_mapping():
    from source_static_behaviour import static_behaviour
    from source_appearance import appearance_from_analysis
    a=analysis('PSVERSION_COMP=2\nfWaveAlpha=0\ncomp_1=`shader_body {ret=float3(.5+.4*sin(time*12),.5,.5);}\n')
    base={'viewport':[1920,1080],'feedback_fps':30,'scalar_input_domains':{'_c2.x':[0,4]}}
    before=static_behaviour(a,appearance_from_analysis(a),base)
    after=static_behaviour(a,appearance_from_analysis(a),{**base,'activity_preferences':{'flash_contrast_reference':2.}})
    assert before['context_sha256']!=after['context_sha256']
    assert before['classification']['intensity']['value']>after['classification']['intensity']['value']
    assert after['classification']['preference_rules']['flash_contrast_reference']==2.


def test_activity_preferences_separate_export_cache_identity(tmp_path):
    from effect_family_export import export_preset
    from test_core2331_warp import BINARIES
    path=tmp_path/'preference.milk';path.write_text('[preset00]\nfWaveAlpha=0\n')
    base={'reader':BINARIES/'milk-native-reader','cache':tmp_path/'cache'}
    ctx={'viewport':[1920,1080],'feedback_fps':30}
    a,_=export_preset(path,behaviour_context=ctx,**base)
    b,hit=export_preset(path,behaviour_context={**ctx,'activity_preferences':{'motion_reference_vp_s':1.5}},**base)
    assert not hit and a['cache_key']!=b['cache_key']
