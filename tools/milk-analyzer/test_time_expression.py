"""Time-only expression evaluation and hue bands stay consistent."""
import math

import pytest

from time_expression import evaluate,time_only,hue_family,wave_colour,HUE_BANDS


def graph(nodes,root=0):return {'root':root,'nodes':nodes}


def test_evaluates_sum_of_sines_with_abs():
    # abs(.1 + .6*(sin(.346*t)+sin(1.334*t)))
    nodes=[{'op':'abs','args':[1],'detail':{}},{'op':'add','args':[2,3],'detail':{}},
           {'op':'constant','args':[],'detail':{'value':.1}},{'op':'multiply','args':[4,5],'detail':{}},
           {'op':'constant','args':[],'detail':{'value':.6}},{'op':'add','args':[6,9],'detail':{}},
           {'op':'sin','args':[7],'detail':{}},{'op':'multiply','args':[8,12],'detail':{}},
           {'op':'constant','args':[],'detail':{'value':.346}},{'op':'sin','args':[10],'detail':{}},
           {'op':'multiply','args':[11,12],'detail':{}},{'op':'constant','args':[],'detail':{'value':1.334}},
           {'op':'input','args':[],'detail':{'name':'time'}}]
    expression=graph(nodes)
    assert time_only(expression)
    t=5.0
    assert evaluate(expression,t)==pytest.approx(abs(.1+.6*(math.sin(.346*t)+math.sin(1.334*t))))


def test_audio_input_is_not_time_only():
    expression=graph([{'op':'input','args':[],'detail':{'name':'bass'}}])
    assert not time_only(expression)
    with pytest.raises(ValueError):evaluate(expression,1.0)


def test_eel_division_by_zero_is_zero():
    nodes=[{'op':'divide','args':[1,2],'detail':{}},{'op':'constant','args':[],'detail':{'value':1}},
           {'op':'constant','args':[],'detail':{'value':0}}]
    assert evaluate(graph(nodes),0.)==0.0


def test_hue_families_and_normalisation():
    assert hue_family([1,.2,.5])=='pink'
    assert hue_family([.01,.01,.01])=='grayscale'
    channels={name:{'raw_time_curve':{'curve_kind':'constant','constant_value':v}} for name,v in
              (('wave_r',.5),('wave_g',.1),('wave_b',.25))}
    assert wave_colour(channels,0.,True)==[1.0,.2,.5]
    assert wave_colour(channels,0.,False)==[.5,.1,.25]


def test_hue_bands_match_colour_character():
    from source_colour_character import HUE_BANDS as SOURCE_BANDS
    assert HUE_BANDS==SOURCE_BANDS


def test_projectm_eval_semantics():
    c=lambda v:{'op':'constant','args':[],'detail':{'value':v}}
    assert evaluate(graph([{'op':'int','args':[1],'detail':{}},c(-0.5)]),0.)==-1.0
    assert evaluate(graph([{'op':'eel_divide','args':[1,2],'detail':{}},c(1),c(1e-6)]),0.)==0.0
    assert evaluate(graph([{'op':'pow','args':[1,2],'detail':{}},c(0.0),c(-1)]),0.)==0.0
    assert evaluate(graph([{'op':'pow','args':[1,2],'detail':{}},c(-2.0),c(0.5)]),0.)==0.0


def test_overflow_becomes_value_error():
    nodes=[{'op':'exp','args':[1],'detail':{}},{'op':'multiply','args':[2,3],'detail':{}},
           {'op':'input','args':[],'detail':{'name':'time'}},{'op':'constant','args':[],'detail':{'value':10}}]
    with pytest.raises(ValueError):evaluate(graph(nodes),100.)


def test_eel_boolean_functions_use_projectm_eval_close_factor():
    from time_expression import evaluate_inputs
    graph = lambda op, n: {'root': n, 'nodes': [{'op': 'input', 'args': [], 'detail': {'name': 'a'}},
                                                {'op': 'input', 'args': [], 'detail': {'name': 'b'}},
                                                {'op': op, 'args': [0] if op == 'bnot' else [0, 1], 'detail': {}}]}
    assert evaluate_inputs(graph('bnot', 2), {'a': 5e-6, 'b': 0}) == 1.0
    assert evaluate_inputs(graph('bnot', 2), {'a': 2e-5, 'b': 0}) == 0.0
    assert evaluate_inputs(graph('band', 2), {'a': 1., 'b': 1e-6}) == 0.0
    assert evaluate_inputs(graph('bor', 2), {'a': 1e-6, 'b': -3.}) == 1.0
