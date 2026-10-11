"""Nominal warp colour transfer, not full feedback/stored-image dynamics."""
import math
import numpy as np


def _colour_bounds(matrices,bias,norm,dependency):
    result={'policy':'source-fixed-coordinate-colour-bounds-v1',
        'raw_rgb_bounds_if_samples_unit_interval':None,
        'maximum_colour_difference_gain':norm,'sufficient_contraction_bound':None,
        'ideal_colour_perturbation_half_life_upper_bound_warp_evaluations':None,
        'actual_feedback_stability':None,
        'conditions':['Each previous-main sampled RGB component independently lies in [0,1]; source does not certify that premise',
                      'Bounds use nominal real arithmetic before shader float32 rounding; no discrete GPU sensitivity certificate is supplied',
                      'Difference gain holds coordinates and non-image inputs fixed, using the RGB infinity norm',
                      'Contraction/decay estimates require image-independent nonexpansive sampling and identical external inputs across compared states',
                      'Drawing, blend/storage quantization, blur, masks, discard and authored/native detail are outside this colour-only operator',
                      'A failed sufficient bound does not prove amplification or instability; no flashing or mood score is inferred']}
    if matrices is None or bias is None or norm is None:return result
    low=np.array(bias,dtype=float);high=low.copy()
    for matrix in matrices:
        low+=np.minimum(matrix,0).sum(axis=1)
        high+=np.maximum(matrix,0).sum(axis=1)
    if np.all(np.isfinite(low)) and np.all(np.isfinite(high)):
        result['raw_rgb_bounds_if_samples_unit_interval']=np.stack((low,high),axis=1).tolist()
    if dependency is False:
        result['sufficient_contraction_bound']=norm<1
        if 0<norm<1:
            result['ideal_colour_perturbation_half_life_upper_bound_warp_evaluations']=math.log(.5)/math.log(norm)
    return result


def feedback_transfer(analysis):
    from effect_families import _parts,_walk
    from shader_fields import Field
    from source_appearance import _phase_literal,_canonical_lane,_data_return,_expression
    from field_math import SWIZZLE
    result={'policy':'source-warp-colour-transfer-v1',
        'scope':'selected warp RGB before storage/drawing/detail, holding sample coordinates fixed',
        'source_model':'unknown','matrix_rgb':None,'constant_offset_rgb':None,
        'direct_colour_gain_norm':None,'uniform_diagonal_gain':None,
        'nominal_half_life_warp_evaluations':None,'source_sample_sites':None,
        'coordinate_feedback_dependency':None,'sample_contributions':[],
        'actual_feedback_persistence':None,'unknown_reasons':[],
        'colour_bounds':_colour_bounds(None,None,None,None),
        'conditions':['Custom source must remain selected and execute in valid input/sample domains',
                      'Colour weights hold sampling coordinates fixed; image-driven coordinates can add nonlinear response',
                      'Nominal half life excludes UNORM storage/rounding, clipping, source injection, blur, motion vectors and authored/native detail',
                      'Composite/display gain is not included; stale/discard feedback remains unresolved'],
        'uses_rendered_images':False,'uses_equation_execution':False,'uses_shader_execution':False}
    decay=getattr(analysis,'main',{}).get('decay');known_decay=None if decay is None else _phase_literal(decay)
    if known_decay is not None:
        with np.errstate(over='ignore',invalid='ignore'):known_decay=float(np.float32(known_decay))
        known_decay=min(known_decay,1.) if math.isfinite(known_decay) else None
    result['vertex_colour_binding']={'rgba':[known_decay,known_decay,known_decay,1.],
        'basis':'source31 warp vertex shader emits vec4(min(float32(main-frame decay),1), same, same,1)',
        'observed_runtime_binding':False}
    selection=analysis.stages['warp'];field=analysis.outputs.get('warp')
    if selection['kind']=='fixed_warp':
        decay=getattr(analysis,'main',{}).get('decay');value=None if decay is None else _phase_literal(decay)
        if value is None:
            result['unknown_reasons']=['fixed warp decay is not a supported constant'];return result
        with np.errstate(over='ignore',invalid='ignore'):gain=float(np.float32(value))
        if not math.isfinite(gain):
            result['unknown_reasons']=['nonfinite native decay conversion'];return result
        gain=min(gain,1.);matrix=np.eye(3)*gain;bias=np.zeros(3);norm=abs(gain)
        matrices={0:matrix};sites=1;dependent=False;result['source_model']='fixed_main_decay'
    elif field is not None:
        samples={};memo={};active=set();injections=[]
        def visit(node):
            key=id(node)
            if key in memo:return memo[key]
            if key in active or len(memo)+len(active)>=4096:raise ValueError('warp transfer graph budget/cycle unresolved')
            active.add(key)
            try:value=calculate(node)
            finally:active.remove(key)
            if not math.isfinite(value[0]) or any(not math.isfinite(c) for c in value[1].values()):
                raise ValueError('warp transfer coefficients are nonfinite')
            memo[key]=value;return value
        image_dependent_injection=[False]
        def image_independent(node):
            # Terms with no direct previous-image colour lane: either image-free, or reading images only
            # nonlinearly/through coordinates. They are held fixed (partial-derivative scope) and flagged.
            nodes=[n for n,_ in _walk(node)]
            if any(n.op in {'unknown','uninitialized'} or n.op.startswith('loop_') for n in nodes):return False
            if node.op in {'add','subtract','multiply','divide','cast','member'}:
                if any(n.op=='sample' for n in nodes):return False
            elif any(n.op=='sample' for n in nodes):image_dependent_injection[0]=True
            return True
        def calculate(node):
            # (known constant part, {(texture, site, lane): coefficient}, injected field or None)
            node=_canonical_lane(node);literal=_phase_literal(node)
            if literal is not None:return literal,{},None
            if node.op=='member' and node.dtype=='float' and node.detail.get('swizzle') and len(node.detail.get('field',''))==1:
                parent=node.args[0];lane=SWIZZLE[node.detail['field']]
                if parent.op=='input' and parent.detail.get('name')=='_vDiffuse' and parent.dtype=='float4':
                    coefficient=1. if lane==3 else known_decay
                    if coefficient is None:raise ValueError('native vertex colour decay is not a supported constant')
                    return coefficient,{},None
                texture=parent.detail.get('canonical_texture') if parent.op=='sample' else None
                if texture in {'main','blur1','blur2','blur3'} and lane<3:
                    site=parent.detail.get('site_index')
                    if site is None:raise ValueError('previous-image sample site identity unresolved')
                    samples[(texture,site)]=parent;return 0.,{(texture,site,lane):1.},None
            if node.op=='cast' and node.dtype=='float' and node.args[0].dtype=='float':return visit(node.args[0])
            if node.dtype=='float' and image_independent(node):
                # Spatial/time/random terms that never read an image are injections, not feedback gain.
                injections.append(node);return 0.,{},node
            if node.op not in {'add','subtract','multiply','divide'} or node.dtype!='float':
                raise ValueError('warp RGB is not supported affine previous-image sample colour')
            a,at,ai=visit(node.args[0]);b,bt,bi=visit(node.args[1])
            const=lambda v:Field('constant',detail={'value':float(v)})
            def full(c,inj):return inj if c==0 else Field('add',(inj,const(c)),'float') if inj is not None else const(c)
            if node.op in {'add','subtract'}:
                sign=1 if node.op=='add' else -1;terms=dict(at)
                for key,c in bt.items():terms[key]=terms.get(key,0)+sign*c
                inj=ai if bi is None else (Field(node.op,(ai,bi),'float') if ai is not None else
                    (bi if sign==1 else Field('unary',(bi,),'float',{'operator':0})))
                return a+sign*b,terms,inj
            if node.op=='divide':
                if bi is not None and not bt:
                    if at:raise ValueError('previous-image colour divided by an image-independent field')
                    injections.append(node);return 0.,{},Field('divide',(full(a,ai),full(b,bi)),'float')
                if bt or b==0:raise ValueError('warp transfer divisor is not a finite nonzero constant')
                return a/b,{key:c/b for key,c in at.items()},None if ai is None else Field('divide',(ai,const(b)),'float')
            if at and bt:raise ValueError('nonlinear product of previous-image colour')
            if (at and bi is not None) or (bt and ai is not None):raise ValueError('previous-image colour scaled by an image-independent field')
            if ai is None and bi is None:inj=None
            elif ai is not None and bi is not None:
                # (a+A)(b+B) = ab + aB + bA + AB: the constant part stays exact.
                inj=Field('add',(Field('add',(Field('multiply',(ai,bi),'float'),Field('multiply',(const(a),bi),'float')),'float'),
                                  Field('multiply',(const(b),ai),'float')),'float')
            elif ai is not None:inj=Field('multiply',(ai,const(b)),'float')
            else:inj=Field('multiply',(const(a),bi),'float')
            return a*b,{**{key:c*b for key,c in at.items()},**{key:c*a for key,c in bt.items()}},inj
        try:
            lanes=[visit(node) for node in _parts(_data_return(field))[:3]]
            if len(lanes)!=3:raise ValueError('warp RGB lanes unresolved')
            matrices={site:np.zeros((3,3)) for site in samples}
            for row,(offset,terms,_) in enumerate(lanes):
                for (texture,site,column),coefficient in terms.items():matrices[(texture,site)][row,column]=coefficient
            matrices={site:m for site,m in matrices.items() if np.any(m!=0)}
            matrix=sum(matrices.values(),np.zeros((3,3)));bias=np.array([v[0] for v in lanes])
            injected=any(v[2] is not None for v in lanes)
            norm=max((sum(abs(m[row,col]) for m in matrices.values() for col in range(3)) for row in range(3)),default=0.)
            sites=len(matrices);dependent=False
            for (texture,site),m in matrices.items():
                sample=samples[(texture,site)]
                nodes=list(_walk(sample.args[0]))
                if any(n.op=='sample' and n.detail.get('canonical_texture') in {'main','blur1','blur2','blur3'} for n,p in nodes):dependent=True
                elif dependent is not True and any(n.op in {'unknown','uninitialized'} or n.op.startswith('loop_') for n,p in nodes):dependent=None
                result['sample_contributions'].append({'sample_site_index':site,'texture':texture,'matrix_rgb':m.tolist(),
                    'coordinate_expression':_expression(sample.args[0]),'sampling_policy':sample.detail.get('sampling_policy')})
            result['source_model']='affine_previous_image_samples' if any(t!='main' for t,_ in matrices) else 'affine_previous_main_samples'
            if image_dependent_injection[0]:dependent=True
            result['image_independent_injection']={'present':injected,'term_count':len({id(n) for n in injections}),
                'reads_images_nonlinearly_or_via_coordinates':image_dependent_injection[0],
                'expressions':[_expression(n) for n in list({id(n):n for n in injections}.values())[:4]],
                'lane_expressions_rgb':[None if v[2] is None else _expression(v[2]) for v in lanes],
                'note':'spatial/time/random terms added to every warp evaluation; not feedback gain'}
            diagonal=[m[0,0] for m in matrices.values() if np.array_equal(m,np.eye(3)*m[0,0])]
            result['uniform_content_gain']=float(sum(diagonal)) if len(diagonal)==len(matrices) and matrices else None
        except (ValueError,RecursionError) as error:
            result['unknown_reasons']=[str(error)];return result
        gain=float(matrix[0,0]) if sites<=1 and np.array_equal(matrix,np.eye(3)*matrix[0,0]) else None
    else:
        result['unknown_reasons']=['warp source/selection is unresolved'];return result
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(bias)) or not math.isfinite(norm):
        result['unknown_reasons']=['aggregate transfer is nonfinite'];return result
    if any(isinstance(key,tuple) and key[0]!='main' for key in matrices):
        # Blur sites are spatially filtered previous content: keep the approximate content gain and
        # per-site matrices, but issue no strict transfer, bounds or decay certificate.
        result['unknown_reasons']=['blur sample sites are spatially filtered; strict colour transfer not certified']
        result.update(source_sample_sites=sites,coordinate_feedback_dependency=dependent)
        return result
    if result.get('image_independent_injection',{}).get('present'):
        # The known constant offset excludes injected fields; bounds need every additive term.
        result.update(matrix_rgb=matrix.tolist(),constant_offset_rgb=None,constant_offset_rgb_excluding_injection=bias.tolist(),
            direct_colour_gain_norm=float(norm),uniform_diagonal_gain=gain,source_sample_sites=sites,coordinate_feedback_dependency=dependent)
        if gain is not None and 0<gain<1 and dependent is False:
            result['nominal_half_life_warp_evaluations']=math.log(.5)/math.log(gain)
        return result
    result.update(matrix_rgb=matrix.tolist(),constant_offset_rgb=bias.tolist(),direct_colour_gain_norm=float(norm),
        uniform_diagonal_gain=gain,source_sample_sites=sites,coordinate_feedback_dependency=dependent)
    result['colour_bounds']=_colour_bounds(list(matrices.values()),bias,float(norm),dependent)
    if gain is not None and 0<gain<1 and dependent is False:
        result['nominal_half_life_warp_evaluations']=math.log(.5)/math.log(gain)
    return result
