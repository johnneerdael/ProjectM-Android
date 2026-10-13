"""Bounded source-DAG specialization for native custom-shape instance indices."""
import math
from shader_fields import Field

MAX_INSTANCES=1024
MAX_NODE_VISITS=262144


def shape_instance_motion(controls,count,*,max_instances=MAX_INSTANCES,max_node_visits=MAX_NODE_VISITS):
    from effect_families import _CACHE,_EEL,_number
    from source_appearance import _phase_literal
    from source_geometry import shape_geometry
    from source_motion import planar_trajectory,shape_vertex_motion
    result={'policy':'source-custom-shape-instance-motion-v1','configured_instances':count,
        'instance_expansion_limit':max_instances,'node_visit_budget':max_node_visits,
        'processed_instances':0,'known_path_instances':0,'known_speed_instances':0,
        'expansion_complete':False,'instances':[],'nominal_continuity':'unknown',
        'maximum_vertex_speed_ndc_per_second_upper_bound':None,
        'visible_motion_speed':None,'unknown_reasons':[],
        'uses_equation_execution':False,'uses_rendered_images':False,
        'conditions':['Substitute original native index 0..configured_count-1 into existing source control DAGs',
                      'Native per-instance reset and incoming custom-state/audio inputs retain their source meanings',
                      'Supported literal arithmetic and sin/cos use nominal double formulas, not executed frames or native trig parity',
                      'Geometry/speed premises from each instance apply; clipping, materials, feedback and visible motion remain separate',
                      'Aggregate bound requires every configured instance to be processed with a known finite bound; budgets do not clamp native counts']}
    if type(count) is not int or count<1 or count>max_instances:
        result['unknown_reasons']=['configured instance count is outside the declared source expansion budget'];return result
    visits=0
    # Subgraphs that never read `instance` specialise identically for every instance: they are computed
    # once and shared (exact), so only instance-dependent work is redone and counted per instance.
    dependent={}
    def reads_instance(node,depth=0):
        key=id(node)
        if key not in dependent:
            if depth>64:return True
            dependent[key]=(node.op=='input' and node.detail.get('name')=='instance') or any(reads_instance(arg,depth+1) for arg in node.args)
        return dependent[key]
    shared={}
    for index in range(count):
        memo={};token=_CACHE.set({})
        def specialize(node,depth=0):
            nonlocal visits
            if id(node) in memo:return memo[id(node)]
            if id(node) in shared:return shared[id(node)]
            if depth>64 or visits>=max_node_visits:raise ValueError('source instance specialization node/depth budget exceeded')
            visits+=1
            if node.op=='input' and node.dtype=='float' and node.detail.get('name')=='instance':
                value=Field('constant',detail={'value':float(index)})
            else:
                args=tuple(specialize(arg,depth+1) for arg in node.args)
                if node.op=='select' and len(args)==3 and _number(args[0]) is not None:
                    value=args[1] if _number(args[0]) else args[2]
                elif node.op=='eel_divide':value=_EEL.operation(node.op,args)
                else:value=Field(node.op,args,node.dtype,node.detail)
                literal=_phase_literal(value)
                if literal is None and value.op in {'sin','cos'} and value.dtype=='float' and len(value.args)==1:
                    argument=_phase_literal(value.args[0])
                    if argument is not None:literal=(math.sin if value.op=='sin' else math.cos)(argument)
                if literal is not None:value=Field('constant',dtype=value.dtype,detail={'value':literal})
            memo[id(node)]=value
            if not reads_instance(node):shared[id(node)]=value
            return value
        try:
            specialized={name:specialize(controls[name]) for name in ('x','y','rad','ang','sides')}
            trajectory=planar_trajectory([specialized['x'],specialized['y']])
            geometry=shape_geometry(specialized,1)
            motion=shape_vertex_motion(specialized,geometry,trajectory)
            compact={k:v for k,v in trajectory.items() if k not in ['axis_curves','conditions','visible_motion_speed']}
            row={'instance':index,'center_trajectory':compact,
                 'effective_sides':geometry['effective_sides'],'nominal_continuity':motion['nominal_continuity'],
                 'maximum_vertex_speed_ndc_per_second_upper_bound':motion['maximum_vertex_speed_ndc_per_second_upper_bound'],
                 'unknown_reasons':motion['unknown_reasons']}
            result['instances'].append(row)
            result['processed_instances']+=1
            result['known_path_instances']+=int(trajectory['path_kind']!='unknown')
            result['known_speed_instances']+=int(row['maximum_vertex_speed_ndc_per_second_upper_bound'] is not None)
        except (ValueError,RecursionError) as error:
            result['unknown_reasons'].append(str(error));break
        finally:_CACHE.reset(token)
    result['expansion_complete']=result['processed_instances']==count
    if result['expansion_complete']:
        from source_control_bounds import merge_continuity
        result['nominal_continuity']=merge_continuity([r['nominal_continuity'] for r in result['instances']])
    if result['expansion_complete'] and result['known_speed_instances']==count:
        result['maximum_vertex_speed_ndc_per_second_upper_bound']=max(r['maximum_vertex_speed_ndc_per_second_upper_bound'] for r in result['instances'])
    elif not result['unknown_reasons']:result['unknown_reasons']=['one or more native instances have unresolved nominal speed']
    return result
