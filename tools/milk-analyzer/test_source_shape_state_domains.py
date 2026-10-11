"""Source shape recurrences require initialization and inductive closure."""
import pytest
import test_native_reader


POLICY = 'projectmtv-core-2.2.8-v1'


def source(initial, transition, extra=''):
    return test_native_reader.NativeReaderTest().read(
        'shapecode_0_enabled=1\nshapecode_0_num_inst=311\n'
        'shape_0_init1=' + initial + '\nshape_0_per_frame1=' + transition + '\n' + extra)


def prove(initial, transition, **kwargs):
    from source_shape_state_domains import shape_state_domain_evidence
    return shape_state_domain_evidence(source(initial, transition), policy=POLICY,
                                      shape_index=0, **kwargs)


REFLECT = 'mx=mx+.0002*cos(ma);mx=if(above(mx,.9),.9-mx,mx);mx=if(below(mx,.1),.9+mx,mx);x=mx;'


def test_reflection_proves_initialization_and_one_full_transition():
    report = prove('mx=0;ma=0;', 'ma=ma+bass;' + REFLECT)
    assert report['state_domains']['mx'] == [0., 1.0000000000000002]
    assert 'ma' not in report['state_domains']
    assert report['instance_output_domains']['x'][0] >= 0
    assert report['instance_output_domains']['x'][1] <= 1.0000000000000002
    assert report['obligations']['mx'] == {'initialization': 'proven', 'transition': 'proven'}
    assert report['native_numeric_certified'] is False
    assert report['visible_motion_certified'] is False
    assert report['uses_equation_execution'] is False


def test_tan_axis_does_not_erase_independent_cos_axis_or_become_bounded():
    report = prove('mx=0;my=0;ma=0;', 'ma=ma+bass;' + REFLECT +
        'my=my+.0002*tan(ma);my=if(above(my,.9),.9-my,my);my=if(below(my,.1),.9+my,my);y=my;')
    assert 'mx' in report['state_domains']
    assert 'my' not in report['state_domains']
    assert 'y' not in report['instance_output_domains']
    assert any('tan' in reason for reason in report['unresolved_native_operations'])


def test_missing_local_initialization_is_not_zero_filled():
    report = prove('', REFLECT)
    assert 'mx' not in report['state_domains']
    assert 'mx' in report['unknown_state_reasons']


def test_explicit_initial_local_domain_includes_init_and_cannot_override_assignment():
    good = prove('', REFLECT, initial_local_domains={'mx':[0,0], 'ma':[0,0]})
    assert 'mx' in good['state_domains']
    bad = prove('mx=-20;ma=0;', REFLECT, candidate_domains={'mx':[0,1]},
                initial_local_domains={'mx':[0,0], 'ma':[0,0]})
    assert 'mx' not in bad['state_domains']
    assert 'initialization' in bad['unknown_state_reasons']['mx']


def test_unbounded_growth_and_oversized_reflection_step_are_not_invariants():
    growth = prove('mx=0;', 'mx=mx+1;x=mx;')
    assert not growth['state_domains']
    huge = prove('mx=0;ma=0;', REFLECT.replace('.0002','2'), candidate_domains={'mx':[0,1]})
    assert not huge['state_domains']


def test_generic_clamp_and_wrap_with_different_variable_names():
    clamp = prove('position=-2;', 'position=max(-2,min(3,position+.4));x=position;')
    assert clamp['state_domains']['position'] == [-2.,3.]
    wrap = prove('position=0;', 'position=position+.01;position=if(above(position,1),0,position);x=position;')
    assert wrap['state_domains']['position'] == [0.,1.]


def test_nested_assignment_branch_merges_all_modified_variables():
    report = prove('mx=0;other=0;',
        'if(above(instance,0),mx=min(1,mx+.1),other=2);x=mx;y=other;',
        candidate_domains={'mx':[0,1], 'other':[0,2]})
    assert report['state_domains'] == {'mx':[0.,1.], 'other':[0.,2.]}


def test_q_t_and_shape_configuration_reset_instead_of_persisting_init_assignments():
    report = prove('mx=0;x=-99;t1=.2;q1=99;',
        'mx=min(1,mx+.1);y=x;x=mx;rad=t1;a=q1;')
    assert report['instance_output_domains']['y'] == [.5,.5]
    assert report['instance_output_domains']['rad'] == [.2,.2]
    assert 'a' not in report['instance_output_domains']
    assert not set(report['state_domains']) & {'x','q1','t1'}


@pytest.mark.parametrize('extra, transition', [
    ('per_frame_1=reg00=2;\n', REFLECT),
    ('', REFLECT + 'a=gmegabuf(0);'),
    ('', REFLECT + 'a=loop(3,mx=mx+1);'),
    ('', 'mx=mx+sin(1/(ma-ma));x=mx;'),
])
def test_register_memory_loop_and_singular_argument_do_not_certify(extra, transition):
    from source_shape_state_domains import shape_state_domain_evidence
    report = shape_state_domain_evidence(source('mx=0;ma=0;',transition,extra),
                                        policy=POLICY,shape_index=0)
    assert 'mx' not in report['state_domains']


def test_dead_branch_singular_expression_is_not_executed_nominally():
    report = prove('mx=0;', 'mx=if(above(1,0),min(1,mx+.1),tan(1/0));x=mx;',
                   candidate_domains={'mx':[0,1]})
    assert 'mx' in report['state_domains']


def test_explicit_candidate_bad_domain_and_reset_candidate_are_rejected():
    for candidate in ({'mx':[1,0]}, {'mx':[0,float('inf')]}, {'x':[0,1]}):
        report = prove('mx=0;ma=0;', REFLECT, candidate_domains=candidate)
        assert report['status']=='unsupported'


def test_zero_allocation_policy_rejects_wrong_engine_identity():
    from source_shape_state_domains import shape_state_domain_evidence, ZERO_POLICY
    value=source('',REFLECT)
    value['parser_inputs']['engine']['patches_sha256']='unbound-engine'
    report=shape_state_domain_evidence(value,policy=POLICY,shape_index=0,
                                       initial_variable_policy=ZERO_POLICY)
    assert report['status']=='unsupported'
    assert 'engine identity' in report['reason']


def test_init_only_local_is_invariant_and_q_cannot_be_zero_filled():
    report=prove('anchor=.25;', 'x=anchor;y=q1;')
    assert report['state_domains']['anchor']==[.25,.25]
    assert report['instance_output_domains']['x']==[.25,.25]
    assert 'y' not in report['instance_output_domains']


def test_proof_must_be_rechecked_after_coupled_invalid_box_is_removed():
    report=prove('mx=0;other=0;', 'mx=min(1,mx+other);other=other+1;x=mx;',
                 candidate_domains={'mx':[0,1], 'other':[0,1]})
    assert not report['state_domains']


def test_negative_unbounded_step_and_cancelled_singularity_remain_unknown():
    report=prove('mx=0;ma=0;', 'mx=mx+0*tan(ma);x=mx;',
                 candidate_domains={'mx':[0,1]})
    assert not report['state_domains']


def test_infinite_intermediate_cannot_cancel_into_nominal_proof():
    report=prove('mx=0;', 'mx=1e200*1e200-1e200*1e200;x=mx;',
                 candidate_domains={'mx':[0,1]})
    assert report['status']=='unsupported'


def test_source34_real_shapes_native_zero_policy_proves_sin_axes_only():
    import json
    import subprocess
    from pathlib import Path
    from source_shape_state_domains import shape_state_domain_evidence,ZERO_POLICY
    reader=Path('build/preset-corpus/source34/adapters/milk-native-reader')
    if not reader.is_file():pytest.skip('source34 reader required for engine-bound allocation policy')
    cases=[("loin bowel - don't you understand baby, i don't want a big studio in the hills - how to impress dullards2.milk",True),
           ('suksma - fiShbRaiN - witchcraft (phugly megalopolish remix)2 - skekseas.milk',False)]
    for name,sin in cases:
        path=Path('core/src/main/assets/presets')/name
        value=json.loads(subprocess.check_output([str(reader),str(path)]))
        report=shape_state_domain_evidence(value,policy=POLICY,shape_index=0,
                                           initial_variable_policy=ZERO_POLICY)
        assert report['state_domains']['mx'][0]==0
        assert ('my' in report['state_domains']) is sin
        assert ('y' in report['instance_output_domains']) is sin
        assert 'ma' not in report['state_domains']


def test_missing_crossphase_tree_cannot_hide_shared_register_effects():
    from source_shape_state_domains import shape_state_domain_evidence
    value=source('mx=0;ma=0;',REFLECT,'per_frame_1=reg00=2;\n')
    value['sections']['per_frame_'].pop('projectm_raw_tree')
    report=shape_state_domain_evidence(value,policy=POLICY,shape_index=0)
    assert report['status']=='unsupported'
    assert not report['state_domains']


def test_native_configuration_is_part_of_proof_request_identity():
    from source_shape_state_domains import shape_state_domain_evidence
    a=source('mx=0;','mx=min(1,mx+.1);y=x;x=mx;')
    b=source('mx=0;','mx=min(1,mx+.1);y=x;x=mx;','shapecode_0_x=.75\n')
    first=shape_state_domain_evidence(a,policy=POLICY,shape_index=0)
    second=shape_state_domain_evidence(b,policy=POLICY,shape_index=0)
    assert first['request_sha256']!=second['request_sha256']


@pytest.mark.parametrize('formula',['mx*(mx=1)','below(mx,mx=1)','cos(mx=1)'])
def test_embedded_operand_writes_reject_native_pointer_aliases(formula):
    reader=test_native_reader.NativeReaderTest()
    native=reader.execute({'initial':{'scope':'shape','code':'mx=0;'},
                           'frame':{'scope':'shape','code':'mx='+formula+';x=mx;'}},
                          [{'program':'initial'},{'program':'frame','capture':['mx','x']}])
    if formula=='mx*(mx=1)':assert native['steps'][-1]=={'mx':1.,'x':1.}
    report=prove('mx=0;','mx='+formula+';x=mx;',candidate_domains={'mx':[0,0]})
    assert report['status']=='unsupported'
    assert 'reference aliases' in report['reason']
    assert not report['state_domains']
    assert not report['instance_output_domains']


@pytest.mark.parametrize('divisor',['0','.000001','-.000001','.00001','-.00001','.00002'])
def test_source34_guarded_division_matches_native_threshold_boundaries(divisor):
    reader=test_native_reader.NativeReaderTest()
    expression='1/bass';number=float(divisor)
    native=reader.execute({'frame':'x='+expression+';'},
                          [{'program':'frame','variables':{'bass':number},'capture':['x']}])['steps'][0]['x']
    report=prove('mx=0;','mx='+expression+';x=mx;',input_domains={'bass':[number,number]})
    bounds=report['instance_output_domains']['x']
    assert bounds[0]<=native<=bounds[1]
    if abs(float(divisor))<.00001:assert bounds==[0.,0.]
    else:assert native!=0


def test_guarded_division_crossing_epsilon_seam_remains_unknown():
    report=prove('mx=0;','mx=1/bass;x=mx;',input_domains={'bass':[0,.00002]})
    assert 'mx' not in report['state_domains']
    assert 'x' not in report['instance_output_domains']
    assert any('seam' in x for x in report['unresolved_native_operations'])


def test_source34_if_uses_exact_nonzero_truth_despite_division_epsilon():
    native=test_native_reader.NativeReaderTest().execute({'frame':'x=if(bass,1,2);'},
                    [{'program':'frame','variables':{'bass':.000001},'capture':['x']}])['steps'][0]['x']
    assert native==1
    report=prove('mx=0;','mx=if(bass,1,2);x=mx;',input_domains={'bass':[.000001,.000001]})
    assert report['instance_output_domains']['x']==[1.,1.]

