"""Nominal source-only RGB difference bounds through the target blur bank.

No image/field construction, shader execution or EEL evaluation occurs here.
The existing range producer supplies native float32 scale/bias/decode constants.
Kernel normalization, filtering and clamp are nominal real-valued operators;
target sampling/arithmetic/storage errors remain a separate additive contract.
"""
import math
from fractions import Fraction

import numpy as np

from blur import CORE_2315_BLUR,_coefficients
from source_uniforms import blur_decode_bindings


POLICY='source-fixed-control-blur-rgb-supnorm-v1'
CONTROL_NAMES=tuple('blur'+str(i)+'_'+side for side in ('min','max') for i in range(1,4))+('blur1_edge_darken',)


def _multiply_upper(a,b):
    from source_sampling_motion import _finite_round
    value=_finite_round(Fraction(a)*Fraction(b),upper=True)
    if value is None:raise ValueError('nominal blur gain product overflow/underflow')
    return value


def _control(field,domains):
    """Retain original invalid/unknown nodes, including before clamps and zeros."""
    from source_appearance import _phase_literal
    from source_control_bounds import scalar_value_envelope
    if field is None:raise ValueError('main-frame blur control is missing')
    inputs=set();pending=[field];seen=set()
    while pending:
        node=pending.pop()
        if id(node) in seen:continue
        if len(seen)>=512:raise ValueError('blur control original-domain node budget exceeded')
        seen.add(id(node))
        # Traverse original arguments before any clipping/cancellation pruning;
        # this local budget does not consume the coupled family traversal budget.
        pending.extend(node.args)
        if node.op in {'unknown','uninitialized','unresolved','sequence'} or node.op.startswith('loop_'):
            raise ValueError('main-frame blur control contains unknown state or unsupported source')
        if node.op=='input':
            name=node.detail.get('name');inputs.add(name)
            if name not in domains:raise ValueError('blur control input lacks a declared domain: '+str(name))
        if node.op=='constant':
            value=node.detail.get('value')
            if type(value) not in {int,float} or not math.isfinite(value):
                raise ValueError('blur control has a nonfinite original constant')
        literal=_phase_literal(node)
        if literal is not None:continue
        report=scalar_value_envelope(node,input_domains=domains)
        span=report['nominal_value_range']
        if span is None or not all(math.isfinite(v) for v in span):
            raise ValueError('blur control original domain is unresolved before clamp: '+
                             '; '.join(report['unknown_reasons']))
    literal=_phase_literal(field)
    if literal is not None:
        return {'binding_status':'source_constant','source_value_range':[literal,literal],
                'assumed_finite_input_names':sorted(inputs),'range_evidence':[]}
    report=scalar_value_envelope(field,input_domains=domains)
    return {'binding_status':'source_bounded','source_value_range':report['nominal_value_range'],
            'assumed_finite_input_names':sorted(inputs),'range_evidence':[report]}


def blur_propagation_evidence(main,*,input_domains=None):
    """Bound main RGB supnorm changes with all live blur controls held fixed.

    ``main`` is the analyzer's post-main-frame source Field mapping. Domains
    are explicit scalar input intervals, not observed frame/state values.
    Six range controls must resolve through ``blur_decode_bindings``; dynamic
    ranges remain unknown even if bounded. Edge darkening may be source-bounded.
    Use encoded gains for ``sampler_blurN`` sites: source graphs already expand
    GetBlurN's decode. Use getblur gains only for an unexpanded RGB GetBlurN site.
    """
    from source_sampling_motion import _finite_round
    result={'policy':POLICY,'blur_range_policy':CORE_2315_BLUR,'status':'unresolved',
        'norm':'RGB image supnorm: maximum absolute channel difference over all source texels',
        'controls':{},'held_fixed_control_names':sorted(CONTROL_NAMES),
        'declared_input_domains':dict(input_domains or {}),'range_binding':None,
        'edge_factor_absolute_upper':None,'levels':[],'unknown_reasons':[],
        'native_numeric_certified':False,'observed_runtime_binding':False,
        'uses_equation_execution':False,'uses_shader_execution':False,'uses_rendered_images':False,
        'pointwise_support_preserved':False,
        'input_lane_contract':{'main_rgba_to_blur_rgb_alpha_gain':0,
            'encoded_blur_sample_alpha':1,'encoded_blur_sample_alpha_difference_gain':0,
            'getblur_return_channels':'RGB'},
        'numeric_error_contract':{
            'native_pair_error_bound':None,
            'conditional_round_to_nearest_unorm8_pair_error_per_pass':_finite_round(Fraction(1,255),upper=True),
            'encoded_difference_formula':'min(1, G*main_rgb_delta + sum(pass_pair_error[j]*error_gain[j]))',
            'getblur_difference_formula':'gap*encoded_difference + decode_pair_error',
            'conditions':['The optional1/255 term applies only to ideal nondithered nearest-unorm8 storage in both states',
                'Each pass_pair_error bounds the sum of both states deviations from its nominal pass at actual incoming data',
                'Include CPU edge-coefficient rounding, kernel coefficient/sampling normalization, shader FMA/precision and storage/dither in errors',
                'Native arithmetic/sampling/storage and GetBlur decode pair errors are not supplied or certified by this report']},
        'conditions':['Requires the caller-verified source34 patched blur math lineage and matching blur allocation/pass schedule',
            'All live blur control values and decode bindings are identical in the two compared states; domain bounds are premises',
            'Native float32 range coefficients come from the existing patched producer, preserving fallback and clamp-then-expand order',
            'Nominal nonnegative normalized kernels and fixed-coordinate bilinear clamp-to-edge sampling are nonexpansive in RGB supnorm',
            'Each horizontal pass applies its progressive scale and bias then normalized storage clamp; each vertical pass is clamped too',
            'Only vertical pass1 applies edge darkening; its spatial factor is(1-edge)+edge*s with s in[0,1]',
            'Relevant EEL, upload and shader intermediates must remain finite; native rounding/error remains separate from nominal gains',
            'Changing controls, dimensions, coordinates, history, shader selection or allocation is outside this held-fixed input-difference bound',
            'Encoded sample gains exclude GetBlur decode; multiplying an already-expanded source graph by decoded gain would double-count decode',
            'Global norm does not preserve support/area or certify actual temporal changes, whole-loop contraction, appearance or mood']}
    try:
        domains=dict(input_domains or {})
        for name in CONTROL_NAMES:
            try:result['controls'][name]=_control(main.get(name),domains)
            except (ValueError,RecursionError,OverflowError) as error:
                raise ValueError(name+': '+str(error)) from error
        binding=blur_decode_bindings(main);result['range_binding']=binding
        if binding['status']!='source_constant':
            raise ValueError('main-frame blur triplet is not supported constant source: '+
                             '; '.join(binding['unknown_reasons']))
        low=np.asarray(binding['safe_ranges']['minimum'],dtype=np.float32)
        high=np.asarray(binding['safe_ranges']['maximum'],dtype=np.float32)
        coefficients=_coefficients(low,high)
        if coefficients is None:raise ValueError('existing native blur coefficient producer unresolved')
        scales,biases=coefficients
        edge=result['controls']['blur1_edge_darken']['source_value_range']
        with np.errstate(over='ignore',invalid='ignore'):edge32=[float(np.float32(v)) for v in edge]
        if not all(math.isfinite(v) for v in edge32):
            raise ValueError('edge darkening float32 upload is nonfinite; blur-range fallback does not cover edge')
        result['controls']['blur1_edge_darken']['native_float32_value_range']=edge32
        # This uses nominal 1-edge, explicitly separating rounding of native c1.
        edge_gain=_finite_round(max(Fraction(1),*(abs(1-Fraction(v)) for v in edge32)),upper=True)
        if edge_gain is None:raise ValueError('nominal edge coefficient gain overflow')
        result['edge_factor_absolute_upper']=edge_gain
        gain=1.;error_gains=[]
        for index,(scale,bias) in enumerate(zip(scales,biases)):
            scale=float(scale);bias=float(bias)
            vertical=edge_gain if index==0 else 1.
            horizontal_gain=_multiply_upper(gain,scale)
            error_gains=[_multiply_upper(v,scale) for v in error_gains]+[1.]
            gain=_multiply_upper(horizontal_gain,vertical)
            error_gains=[_multiply_upper(v,vertical) for v in error_gains]+[1.]
            gap=float(np.float32(high[index]-low[index]))
            result['levels'].append({'level':index+1,'encoded_texture':'blur'+str(index+1),
                'horizontal_pass':index*2,'vertical_pass':index*2+1,
                'progressive_scale':scale,'progressive_bias':bias,
                'horizontal_encoded_rgb_supnorm_gain_upper':horizontal_gain,
                'vertical_edge_factor_absolute_upper':vertical,
                'encoded_rgb_supnorm_gain_upper':gain,'encoded_rgb_difference_ceiling':1.,
                'getblur_decode_scale':gap,'getblur_decode_bias':float(low[index]),
                'getblur_rgb_supnorm_gain_upper':_multiply_upper(gain,gap),
                'getblur_rgb_difference_ceiling':gap,
                'encoded_per_pass_pair_error_gains':list(error_gains),
                'getblur_per_pass_pair_error_gains':[_multiply_upper(v,gap) for v in error_gains]})
        result['status']='bounded'
    except (ValueError,RecursionError,OverflowError) as error:
        result['levels']=[];result['unknown_reasons']=[str(error)]
    return result
