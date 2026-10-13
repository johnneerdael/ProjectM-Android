"""Static specialization uses native shape indices without time/audio samples."""
import math
import pytest
from test_effect_families import read
from test_source_appearance import appearance


def group(body,count=3):
    d=appearance(read('fWaveAlpha=0\nshapecode_0_enabled=1\nshapecode_0_num_inst='+str(count)+'\n'
        'shape_0_per_frame1='+body+'\n'))
    shape=next(e for e in d['elements'] if e['id']=='shape_0')
    assert 'instance_motion' in shape, 'source instance-motion export is missing'
    return shape['instance_motion']


def test_constant_instance_offsets_supply_each_native_index_and_group_bound():
    m=group('x=.2+.1*instance;y=.5;rad=.2;ang=0;sides=4;')
    assert m['expansion_complete'] is True
    assert m['processed_instances']==3
    assert [r['instance'] for r in m['instances']]==[0,1,2]
    assert [r['center_trajectory']['center_source_xy'][0] for r in m['instances']]==pytest.approx([.2,.3,.4])
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound']==0


def test_instance_phase_offsets_keep_time_circles_and_shared_speed():
    m=group('x=.5+.2*cos(2*time+instance);y=.5+.2*sin(2*time+instance);rad=.1;ang=0;sides=4;')
    assert all(r['center_trajectory']['path_kind']=='circle' for r in m['instances'])
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound']==pytest.approx(.8)
    matrix=m['instances'][1]['center_trajectory']['harmonic_matrix_source_xy']
    assert matrix[0]==pytest.approx([.2*math.cos(1),-.2*math.sin(1)])


def test_instance_literal_trigonometry_is_folded_without_sampling_time():
    m=group('x=.5+.1*cos(instance);y=.5+.1*sin(instance);rad=.1;ang=time;sides=4;')
    assert m['known_path_instances']==3
    assert m['instances'][2]['center_trajectory']['center_source_xy']==pytest.approx([.5+.1*math.cos(2),.5+.1*math.sin(2)])
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound']==pytest.approx(.1)


def test_eel_tolerance_selects_instance_branch_with_actual_native_rule():
    m=group('x=if(equal(instance,.000009),.2,.8);y=.5;rad=.1;ang=0;sides=4;')
    assert [r['center_trajectory']['center_source_xy'][0] for r in m['instances']]==pytest.approx([.2,.8,.8])


def test_instance_radius_division_preserves_native_near_zero_guard():
    m=group('x=.5;y=.5;rad=.1/(instance+1);ang=2*time;sides=4;')
    assert [r['maximum_vertex_speed_ndc_per_second_upper_bound'] for r in m['instances']]==pytest.approx([.2,.1,2*.1/3])


def test_one_audio_dependent_instance_keeps_whole_group_bound_unknown():
    m=group('x=if(equal(instance,0),bass,.5);y=.5;rad=.1;ang=0;sides=4;')
    assert m['expansion_complete'] is True
    assert m['known_speed_instances']==2
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound'] is None
    assert m['instances'][0]['maximum_vertex_speed_ndc_per_second_upper_bound'] is None


def test_stateful_local_input_is_not_replaced_by_instance_constant():
    m=group('k=k+1;x=.5+.1*instance+k;y=.5;rad=.1;ang=0;sides=4;')
    assert m['known_path_instances']==0
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound'] is None


def test_local_write_to_instance_does_not_change_original_native_iteration_index():
    m=group('instance=instance+1;x=.1*instance;y=.5;rad=.1;ang=0;sides=4;')
    assert [r['center_trajectory']['center_source_xy'][0] for r in m['instances']]==pytest.approx([.1,.2,.3])


def test_single_native_instance_is_proved_zero_without_forcing_all_rows():
    m=group('x=.2+.1*instance;y=.5;rad=.1;ang=0;sides=4;',count=1)
    assert m['instances'][0]['center_trajectory']['center_source_xy']==pytest.approx([.2,.5])


def test_count_above_expansion_budget_is_not_silently_truncated():
    m=group('x=.5+.01*instance;y=.5;rad=.1;ang=0;sides=4;',count=1025)
    assert m['configured_instances']==1025
    assert m['expansion_complete'] is False
    assert m['processed_instances']==0
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound'] is None
    assert m['unknown_reasons']


def test_one_invalid_native_projection_keeps_aggregate_unknown():
    m=group('x=.5+2e38*instance;y=.5;rad=.1;ang=0;sides=4;')
    assert m['known_speed_instances']==1
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound'] is None


def test_group_has_no_frames_or_visible_motion_claim():
    m=group('x=.2+.1*instance;y=.5;rad=.1;ang=0;sides=4;')
    assert m['uses_equation_execution'] is False
    assert m['uses_rendered_images'] is False
    assert m['visible_motion_speed'] is None


def test_work_budget_keeps_partial_results_and_no_complete_group_claim():
    from shader_fields import Field
    from source_instances import shape_instance_motion
    controls={name:Field('constant',detail={'value':value}) for name,value in [('y',.5),('rad',.1),('ang',0),('sides',4)]}
    # x = instance + instance + instance: instance-dependent work is redone per instance and counted.
    index=Field('input',detail={'name':'instance'})
    controls['x']=Field('add',(Field('add',(index,index)),index))
    m=shape_instance_motion(controls,3,max_node_visits=9)
    assert m['processed_instances']==1
    assert m['expansion_complete'] is False
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound'] is None
    assert 'budget' in m['unknown_reasons'][0]


def test_instance_varying_sides_are_constant_within_each_instance():
    m=group('x=.2+.1*instance;y=.5;rad=.1;ang=time;sides=3+instance;')
    assert [r['effective_sides'] for r in m['instances']]==[3,4,5]
    assert m['maximum_vertex_speed_ndc_per_second_upper_bound']==pytest.approx(.1)


def test_instance_division_zero_guard_does_not_invent_infinite_radius():
    m=group('x=.2+.1*instance;y=.5;rad=.1/instance;ang=time;sides=4;')
    assert m['instances'][0]['maximum_vertex_speed_ndc_per_second_upper_bound']==0
    assert m['instances'][1]['maximum_vertex_speed_ndc_per_second_upper_bound']==pytest.approx(.1)


def test_instance_independent_subgraphs_are_specialised_once_for_all_instances():
    # A large time-only subtree shared by 1000 instances must not exhaust the visit budget: it specialises
    # identically for every instance (speed budget 1 s per preset), only instance terms are redone.
    from shader_fields import Field
    from source_instances import shape_instance_motion
    time=Field('input',detail={'name':'time'})
    terms=[Field('multiply',(time,Field('constant',detail={'value':.001*k}))) for k in range(256)]
    while len(terms)>1:terms=[Field('add',(terms[i],terms[i+1])) for i in range(0,len(terms),2)]
    shared=terms[0]
    index=Field('input',detail={'name':'instance'})
    controls={name:Field('constant',detail={'value':value}) for name,value in [('y',.5),('rad',.01),('ang',0),('sides',4)]}
    controls['x']=Field('add',(Field('multiply',(Field('sin',(shared,)),Field('constant',detail={'value':.01}))),
                               Field('multiply',(index,Field('constant',detail={'value':.0009})))))
    m=shape_instance_motion(controls,1000)
    assert m['expansion_complete'] is True and m['processed_instances']==1000
