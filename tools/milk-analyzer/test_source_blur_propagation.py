"""Source-only blur difference controls: no fields, images or equation execution."""
import importlib.util
import json
from fractions import Fraction

import numpy as np
import pytest

from shader_fields import Field


def constant(value):
    return Field('constant',dtype='float',detail={'value':value})


def main(minimum=(0,0,0),maximum=(1,1,1),edge=0):
    return {**{'blur'+str(i+1)+'_min':constant(v) for i,v in enumerate(minimum)},
            **{'blur'+str(i+1)+'_max':constant(v) for i,v in enumerate(maximum)},
            'blur1_edge_darken':constant(edge)}


def evidence(controls=None,domains=None):
    assert importlib.util.find_spec('source_blur_propagation'), 'source blur propagation producer is missing'
    from source_blur_propagation import blur_propagation_evidence
    result=blur_propagation_evidence(main() if controls is None else controls,input_domains=domains)
    json.dumps(result,allow_nan=False)
    return result


def test_default_blur_has_nominal_unit_rgb_gain_and_separate_native_errors():
    report=evidence()
    assert report['status']=='bounded'
    assert [v['encoded_rgb_supnorm_gain_upper'] for v in report['levels']]==[1,1,1]
    assert [v['getblur_rgb_supnorm_gain_upper'] for v in report['levels']]==[1,1,1]
    assert report['native_numeric_certified'] is False
    assert report['uses_equation_execution'] is False and report['uses_rendered_images'] is False
    assert report['numeric_error_contract']['native_pair_error_bound'] is None
    error=report['numeric_error_contract']['conditional_round_to_nearest_unorm8_pair_error_per_pass']
    assert error==pytest.approx(1/255) and Fraction(error)>=Fraction(1,255)


def test_progressive_normalization_amplifies_encoded_samples_before_getblur_decode():
    report=evidence(main((.2,.3,.4),(.8,.7,.6)))
    assert report['status']=='bounded'
    encoded=[v['encoded_rgb_supnorm_gain_upper'] for v in report['levels']]
    decoded=[v['getblur_rgb_supnorm_gain_upper'] for v in report['levels']]
    assert encoded==pytest.approx([1/.6,1/.4,1/.2],rel=2e-6)
    assert decoded==pytest.approx([1,1,1],rel=2e-6)
    assert report['levels'][2]['progressive_scale']==pytest.approx(2,rel=2e-6)
    assert report['levels'][2]['encoded_rgb_difference_ceiling']==1
    assert report['levels'][2]['getblur_rgb_difference_ceiling']==pytest.approx(.2,rel=2e-6)


def test_progressive_float32_coefficients_are_not_replaced_by_exact_telescoping():
    report=evidence(main((.11,.23,.34),(.91,.77,.65)))
    decoded=[v['getblur_rgb_supnorm_gain_upper'] for v in report['levels']]
    assert any(v!=1 for v in decoded)
    assert report['range_binding']['policy']=='source31-constant-blur-decode-v1'


@pytest.mark.parametrize('edge,expected',[(0,1),(1,1),(-2,3),(3,2)])
def test_edge_factor_uses_absolute_gain_without_clamping_authored_control(edge,expected):
    report=evidence(main(edge=edge))
    assert report['edge_factor_absolute_upper']==expected
    assert [v['encoded_rgb_supnorm_gain_upper'] for v in report['levels']]==[expected]*3


def test_close_ranges_use_patched_minimum_gap_instead_of_md2_collapsed_range():
    report=evidence(main((.5,.5,.5),(.5,.5,.5)))
    assert report['status']=='bounded'
    assert report['levels'][0]['encoded_rgb_supnorm_gain_upper']==pytest.approx(10,rel=2e-6)
    assert report['levels'][0]['getblur_rgb_supnorm_gain_upper']==pytest.approx(1,rel=2e-6)
    assert all(b>a for a,b in zip(report['range_binding']['safe_ranges']['minimum'],
                                  report['range_binding']['safe_ranges']['maximum']))


def test_order_then_expand_and_triplet_fallback_reuse_existing_native_policy():
    controls=main((.5,.8,0),(.5,.2,1))
    report=evidence(controls)
    from blur import native_ranges,CORE_2315_BLUR
    lo,hi=native_ranges([.5,.8,0],[.5,.2,1],policy=CORE_2315_BLUR)
    assert report['range_binding']['safe_ranges']=={'minimum':lo.tolist(),'maximum':hi.tolist()}
    for value in (1e100,float(np.finfo(np.float32).max)):
        controls=main((value,0,0))
        report=evidence(controls)
        assert report['status']=='bounded'
        assert report['range_binding']['safe_ranges']=={'minimum':[0,0,0],'maximum':[1,1,1]}


def test_dynamic_ranges_remain_unknown_even_with_a_bounded_audio_domain():
    controls=main();controls['blur2_max']=Field('input',detail={'name':'bass'})
    report=evidence(controls,{'bass':[.4,.8]})
    assert report['status']=='unresolved' and report['levels']==[]
    assert any('triplet' in reason for reason in report['unknown_reasons'])


def test_bounded_edge_uses_declared_scalar_domain_while_values_hold_fixed():
    controls=main();controls['blur1_edge_darken']=Field('input',detail={'name':'bass'})
    report=evidence(controls,{'bass':[-2,3]})
    assert report['status']=='bounded'
    assert report['edge_factor_absolute_upper']==3
    assert report['controls']['blur1_edge_darken']['binding_status']=='source_bounded'
    assert report['held_fixed_control_names']==sorted(controls)


def test_missing_or_unknown_edge_domain_never_becomes_zero_darkening():
    controls=main();controls.pop('blur1_edge_darken')
    assert evidence(controls)['status']=='unresolved'
    controls=main();controls['blur1_edge_darken']=Field('sin',(Field('input',detail={'name':'state:phase'}),),'float')
    assert evidence(controls)['status']=='unresolved'


@pytest.mark.parametrize('invalid',[
    Field('divide',(constant(1),constant(0)),'float'),
    Field('sqrt',(constant(-1),),'float'),
    constant(float('inf')),
    Field('multiply',(constant(1e308),constant(1e308)),'float'),
])
def test_invalid_control_before_clamp_is_retained(invalid):
    controls=main();controls['blur1_edge_darken']=Field('clamp',(invalid,constant(0),constant(1)),'float')
    assert evidence(controls)['status']=='unresolved'
    controls['blur1_edge_darken']=Field('multiply',(constant(0),invalid),'float')
    assert evidence(controls)['status']=='unresolved'


def test_edge_upload_overflow_is_unknown_instead_of_range_fallback():
    report=evidence(main(edge=1e100))
    assert report['status']=='unresolved'
    assert any('float32' in reason for reason in report['unknown_reasons'])


def test_extreme_finite_negative_edge_preserves_outward_real_coefficient_bound():
    edge=-float(np.finfo(np.float32).max)
    report=evidence(main(edge=edge))
    assert report['status']=='bounded'
    assert Fraction(report['edge_factor_absolute_upper'])>=1-Fraction(edge)


def test_blur_rgb_and_sampled_alpha_are_independent_of_main_alpha():
    report=evidence()
    assert report['input_lane_contract']['main_rgba_to_blur_rgb_alpha_gain']==0
    assert report['input_lane_contract']['encoded_blur_sample_alpha']==1
    assert report['input_lane_contract']['encoded_blur_sample_alpha_difference_gain']==0
    assert report['input_lane_contract']['getblur_return_channels']=='RGB'


def test_pair_errors_are_propagated_pass_by_pass_separately_from_nominal_gain():
    report=evidence(main((.2,.3,.4),(.8,.7,.6),edge=-2))
    terms=report['levels'][1]['encoded_per_pass_pair_error_gains']
    # At level2, errors after horizontal1 receive edge3 then normalization1.5;
    # vertical1 errors receive only normalization1.5, later pass errors gain1.
    assert terms==pytest.approx([4.5,1.5,1,1],rel=2e-6)
    assert len(report['levels'][2]['encoded_per_pass_pair_error_gains'])==6


def test_actual_source34_main_frame_controls_override_config_and_reset_init():
    import hashlib
    import subprocess
    import tempfile
    from pathlib import Path
    import effect_families as ef
    reader=Path(__file__).resolve().parents[2]/'build/preset-corpus/source34/adapters/milk-native-reader'
    raw=b'MILKDROP_PRESET_VERSION=201\n[preset00]\nb1n=.2\nb1x=.8\nb1ed=0\nper_frame_init_1=blur1_edge_darken=bass;\nper_frame_1=blur1_min=.3;blur1_max=.7;blur1_edge_darken=-2;\n'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'control.milk';path.write_bytes(raw)
        source=json.loads(subprocess.check_output([str(reader),str(path)]))
    source['preset_sha256']=hashlib.sha256(raw).hexdigest()
    source['parser_inputs']['setting_lookup_policy']='native-case-insensitive-v1'
    analysis=ef._Analysis(source,'gles300',{});analysis.main_equations()
    report=evidence(analysis.main)
    assert report['status']=='bounded'
    assert report['levels'][0]['encoded_rgb_supnorm_gain_upper']==pytest.approx(7.5,rel=2e-6)
