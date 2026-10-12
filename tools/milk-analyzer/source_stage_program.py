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
        if getattr(plan,'kind',None):entry['kind']=plan.kind
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


def frame_program(analysis):
    """Per-frame equation recurrence as graphs: state initial/update programs and per-frame outputs.

    Persistent per-frame variables read before being written appear as inputs named after the
    variable (initially 0) or as 'state:per_frame_:<name>' (initialised by per_frame_init); the
    update program is the variable's end-of-frame value. Outputs are Q1..Q32 and the native
    per-frame controls. Inputs are the engine bands/time (and 'init:per_frame_init_:<band>' for
    init). Stepping this program is evaluating authored equations over declared inputs.
    """
    from scene_equations import MAIN,READONLY
    from shader_fields import Field
    main=getattr(analysis,'main',None) or {};init=getattr(analysis,'frame_init',None) or {}
    readonly=set(READONLY)|{'meshx','meshy','pixelsx','pixelsy','aspectx','aspecty'}
    outputs=[f'q{i}' for i in range(1,33)]+[name for name in MAIN if name in main]
    result={'status':'exported','state':{},'outputs':{},'unsupported':{}}
    def inputs_of(field,seen=None):
        found=set();pending=[field];seen=set()
        while pending:
            node=pending.pop()
            if id(node) in seen:continue
            seen.add(id(node))
            if node.op=='input':found.add(node.detail.get('name'))
            pending.extend(node.args)
        return found
    referenced=set()
    for name in outputs:
        if name in main:referenced|=inputs_of(main[name])
    memory=getattr(analysis,'frame_memory',None) or {}
    for version in memory.values():referenced|=inputs_of(version)
    pending=list(referenced);states=set()
    while pending:
        name=pending.pop()
        base=name.split(':',2)[-1] if isinstance(name,str) and name.startswith('state:per_frame_:') else name
        if not isinstance(base,str) or base in readonly or base in states or base not in main:continue
        states.add(base)
        pending.extend(inputs_of(main[base]))
    for name in sorted(states):
        try:
            initial=init.get(name,Field('constant',detail={'value':0.}))
            result['state'][name]={'initial':serialise(initial),'update':serialise(main[name])}
        except (ValueError,RecursionError) as error:result['unsupported'][name]=str(error)
    # megabuf/gmegabuf persist across frames (eel_memory): the init block's final version starts
    # them (the init block reads zeroed buffers), the frame block's final version updates them.
    init_memory=getattr(analysis,'frame_init_memory',None) or {}
    for space,version in sorted((getattr(analysis,'frame_memory',None) or {}).items()):
        name='memory:'+space
        try:
            initial=init_memory.get(space,Field('input',detail={'name':name}))
            result['state'][name]={'initial':serialise(initial),'update':serialise(version)}
        except (ValueError,RecursionError) as error:result['unsupported'][name]=str(error)
    for name in outputs:
        if name not in main:continue
        try:result['outputs'][name]=serialise(main[name])
        except (ValueError,RecursionError) as error:result['unsupported'][name]=str(error)
    return result


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
    try:result['frame']=frame_program(analysis)
    except Exception as error:  # noqa: BLE001 - optional structural export
        result['frame']={'status':'unsupported','unknown_reasons':[str(error)[:200]]}
    return result
