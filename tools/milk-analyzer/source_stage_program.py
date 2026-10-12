"""Serialised warp/composite shader output programs (typed source graphs, not executed here).

Each authored stage's returned RGB field is exported as a bounded {'root','nodes'} graph
that keeps texture-sample nodes inline with their coordinate subgraphs and sampling
policy. A consumer can evaluate it per pixel with ``grid_math.evaluate_grid`` and a
texture callback, which reproduces the translated shader arithmetic without a GPU.
Loop plans are exported as a plan table; unknown nodes and graphs over the node budget are reported, not exported.
The program is source structure: it carries no texture contents, no Q/time values and
no claim about the displayed image.
"""
import json

POLICY='source-stage-program-v1'
MAX_NODES=6000


def _jsonable(value):
    try:
        json.dumps(value)
        return True
    except (TypeError,ValueError):
        return False


def serialise(field):
    """Serialise a typed graph; loop plans become a 'plans' table referenced by node detail 'plan_ref'."""
    nodes=[];ids={};plans=[];plan_ids={}
    def register(plan):
        key=id(plan)
        if key in plan_ids:return plan_ids[key]
        index=len(plans);plan_ids[key]=index
        entry={'names':list(plan.names),'condition':None,'updates':{},'effects':[],'iteration_limit':plan.iteration_limit}
        plans.append(entry)
        entry['condition']=None if plan.condition is None else visit(plan.condition)
        entry['updates']={name:visit(value) for name,value in plan.updates.items()}
        entry['effects']=[visit(effect) for effect in plan.effects]
        return index
    def visit(node):
        key=id(node)
        if key in ids:return ids[key]
        if node.op=='unknown':raise ValueError('stage program contains unknown: '+str(node.detail.get('reason',''))[:120])
        if len(nodes)>=MAX_NODES:raise ValueError('stage program node budget exceeded')
        index=len(nodes);ids[key]=index;nodes.append(None)
        detail={k:v for k,v in node.detail.items() if k!='plan' and _jsonable(v)}
        args=[visit(arg) for arg in node.args]
        if 'plan' in node.detail:detail['plan_ref']=register(node.detail['plan'])
        nodes[index]={'op':node.op,'dtype':node.dtype,'args':args,'detail':detail}
        return index
    root=visit(field)
    return {'root':root,'nodes':nodes,'plans':plans}


def stage_programs(analysis):
    from source_appearance import _data_return
    result={'policy':POLICY,'stages':{},'uses_shader_execution':False,'uses_rendered_images':False,
            'conditions':['Typed translated-shader graphs; texture contents, Q/time values and bindings are supplied by the consumer',
                          'Sample nodes keep their coordinate subgraphs and sampling policy; nested samples are evaluated in order',
                          'Loop plans are a table (names, condition/update/effect node indices, iteration limit); unknown nodes or over-budget graphs are not exported']}
    for stage in ('warp','composite'):
        field=(getattr(analysis,'outputs',{}) or {}).get(stage)
        row={'status':'absent','program':None,'inputs':[],'textures':[],'unknown_reasons':[]}
        if field is not None:
            try:
                program=serialise(_data_return(field))
                row.update(status='exported',program=program,
                    inputs=sorted({n['detail'].get('name') for n in program['nodes'] if n['op']=='input'},key=str),
                    textures=sorted({n['detail'].get('canonical_texture') for n in program['nodes'] if n['op']=='sample'},key=str))
            except (ValueError,RecursionError) as error:
                row.update(status='unsupported',unknown_reasons=[str(error)])
        result['stages'][stage]=row
    return result
