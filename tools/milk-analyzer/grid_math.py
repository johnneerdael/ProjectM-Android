"""Evaluate typed source expressions over coordinate fields without GPU images.

The scalar evaluator remains the reference for supported arithmetic. This engine
retains a distinct lane axis and component axes, uses binary32, and evaluates
conditional branches only for selected lanes. Texture callbacks receive explicit
coordinates and native history metadata. Unknown operations/domains remain errors.
"""
import re
import numpy as np
from field_math import UnresolvedMath,typed,SWIZZLE,BINARY,UNARY,matrix_cast,matrix_constructor,numeric_layout,maskable_math
from field_math import GLES_HIGHP_INFINITY,INFINITY_OPERATIONS,check_infinity_operation
from field_math import SEPARATE_ARITHMETIC,APPLE_MIX_FMA,mix_values
from shader_fields import Field


def _layout(dtype):
    return numeric_layout(dtype)


def _convert(value,dtype,count,*,zero_extend=False,allow_nan=False,allow_infinity=False):
    base,shape=_layout(dtype);array=np.asarray(value)
    if array.shape[:1]!=(count,):raise UnresolvedMath('grid operation lost its lane axis')
    if (np.any(np.isinf(array)) and not (allow_infinity and base in {'float','bool'})) or (np.any(np.isnan(array)) and not (allow_nan and base=='float')):
        raise UnresolvedMath('nonfinite grid value for '+dtype)
    size=int(np.prod(shape)) if shape else 1
    flat=array.reshape(count,-1)
    if ('[' in dtype or len(shape)==2) and flat.shape[1]!=size:
        raise UnresolvedMath('matrix/array constructor size mismatch: '+dtype)
    if flat.shape[1]==1:flat=np.repeat(flat,size,axis=1)
    elif flat.shape[1]>=size:flat=flat[:,:size]
    elif zero_extend:flat=np.pad(flat,((0,0),(0,size-flat.shape[1])))
    else:raise UnresolvedMath('insufficient grid components for '+dtype)
    if base=='int' and np.any((flat<np.iinfo(np.int32).min)|(flat>np.iinfo(np.int32).max)):
        raise UnresolvedMath('integer grid conversion outside signed32-bit range')
    result=flat.astype({'float':np.float32,'int':np.int32,'bool':np.bool_}[base]).reshape((count,)+shape)
    if (np.any(np.isinf(result)) and not (allow_infinity and base=='float')) or (np.any(np.isnan(result)) and not (allow_nan and base=='float')):
        raise UnresolvedMath('nonfinite grid narrowing to '+dtype)
    return result


def evaluate_grid(field:Field,*,batch_shape:tuple[int,...],inputs=None,sample=None,on_sample=None,coordinate_profile='strict',numeric_policy='strict',arithmetic_profile=SEPARATE_ARITHMETIC,work_policy='full-grid-v1',work=None,sample_detail=None):
    if work_policy not in {'full-grid-v1','uniform-proof-v1'}:raise UnresolvedMath('unsupported shader work policy')
    if work is not None and not isinstance(work,dict):raise ValueError('shader work dictionary required')
    if arithmetic_profile not in (SEPARATE_ARITHMETIC,APPLE_MIX_FMA):raise UnresolvedMath('unsupported shader arithmetic profile')
    if numeric_policy not in {'strict',GLES_HIGHP_INFINITY}:raise UnresolvedMath('unsupported shader numeric policy')
    highp=numeric_policy==GLES_HIGHP_INFINITY
    if highp and coordinate_profile!='strict':raise UnresolvedMath('unsupported mixed shader numeric/coordinate policies')
    if coordinate_profile not in ('strict','apple-m4pro-gl41-nan-sampler-v1'):
        raise UnresolvedMath('unsupported shader coordinate profile')
    if not batch_shape or any(type(n) is not int or n<=0 for n in batch_shape):
        raise UnresolvedMath('positive explicit grid dimensions required')
    inputs=inputs or {};size=int(np.prod(batch_shape));cache={};bound={}
    from shader_uniformity import UniformityProof,sampler_coordinate_roots
    blocked=sampler_coordinate_roots(field) if work_policy=='uniform-proof-v1' else None
    uniform=UniformityProof(inputs,batch_shape,blocked=blocked) if work_policy=='uniform-proof-v1' and blocked is not None else None
    uniform_values={};work_counts={'uniform_subgraphs':0,'math_lanes_avoided':0}
    contexts=[np.arange(size,dtype=np.int64)]
    states=[{}];loop_cache={};stored_cache={};loop_steps=0;context_keys={}
    nan_coordinates=False

    def convert(value,dtype,count,**kwargs):
        return _convert(value,dtype,count,allow_nan=nan_coordinates,allow_infinity=highp,**kwargs)

    def context(indices,parent,update=None):
        if update is None:
            # Expressions are pure within one immutable loop-state snapshot.
            # Reusing an exact lane sequence avoids exponential recomputation of
            # the same predecessor graph through component/select branches.
            state=states[parent];key=(id(state),indices.tobytes())
            if key in context_keys:return context_keys[key]
            contexts.append(indices);states.append(state)
            result=len(contexts)-1;context_keys[key]=result;return result
        # A loop update establishes a distinct state epoch even for equal lanes.
        contexts.append(indices);states.append({**states[parent],**update});return len(contexts)-1

    def bind(name,dtype,ctx,*,unbound_default=None):
        key=(name,dtype)
        if key not in bound:
            if name in inputs:data=np.asarray(inputs[name])
            elif unbound_default is not None:data=np.asarray(unbound_default)
            else:raise UnresolvedMath('missing symbolic grid input: '+name)
            _,shape=_layout(dtype)
            if not np.all(np.isfinite(data)):raise UnresolvedMath('nonfinite symbolic grid input: '+name)
            if data.shape==batch_shape+shape:bound[key]=data.reshape((size,)+shape)
            elif data.shape==shape or data.shape==():
                value=typed(data,dtype);bound[key]=np.broadcast_to(value,(size,)+shape)
            else:raise UnresolvedMath('invalid grid/uniform input shape: '+name)
        return bound[key][contexts[ctx]]

    def align(args):
        # Functions with scalar/vector overloads may retain a scalar operand.
        rank=max(a.ndim for a in args)
        return [a.reshape(a.shape+(1,)*(rank-a.ndim)) if a.ndim==1 else a for a in args]

    def stored(node,ctx):
        """Carry undefined components as masks; source arithmetic still reads them."""
        key=(id(node),ctx,nan_coordinates)
        if key in stored_cache:return stored_cache[key]
        lanes=contexts[ctx];count=len(lanes);_,shape=_layout(node.dtype)
        if node.op=='uninitialized':
            data=np.zeros((count,)+shape,dtype=np.float32);valid=np.zeros_like(data,dtype=bool)
        elif node.op=='loop_slot':
            state=states[ctx].get(id(node.detail['plan']))
            if state is None:raise UnresolvedMath('loop state outside execution context')
            values,known=state[node.detail['name']];data=values[lanes];valid=known[lanes]
        elif node.op=='loop_result':data,valid=loop(node,ctx,partial=True)
        elif node.op=='array':
            parts=[stored(arg,ctx) for arg in node.args]
            data=np.stack([p[0] for p in parts],axis=1)
            valid=np.stack([p[1] for p in parts],axis=1)
        elif node.op in {'array_index','array_write'}:
            values,known=stored(node.args[0],ctx)
            index=visit(node.args[1],ctx)
            if index.shape!=(count,) or np.any((index<0)|(index>=values.shape[1])):
                raise UnresolvedMath('array index out of bounds')
            index=index.astype(np.int64)
            if node.op=='array_index':
                data=values[np.arange(count),index];valid=known[np.arange(count),index]
            else:
                replacement,replacement_valid=stored(node.args[2],ctx)
                data=values.copy();valid=known.copy()
                data[np.arange(count),index]=replacement
                valid[np.arange(count),index]=replacement_valid
        elif node.op=='components':
            parts=[stored(arg,ctx) for arg in node.args]
            data=np.concatenate([part[0].reshape(count,-1) for part in parts],axis=1)
            valid=np.concatenate([part[1].reshape(count,-1) for part in parts],axis=1).reshape((count,)+shape)
            data=convert(data,node.dtype,count)
        elif node.op in {'flat_component','member'}:
            values,known=stored(node.args[0],ctx)
            values=values.reshape(count,-1);known=known.reshape(count,-1)
            if node.op=='flat_component':indices=[node.detail['index']]
            else:
                if not node.detail.get('swizzle'):raise UnresolvedMath('unsupported component member')
                indices=[SWIZZLE[c] if values.shape[1]>1 else 0 for c in node.detail['field']]
            if any(i<0 or i>=values.shape[1] for i in indices):raise UnresolvedMath('component index out of bounds')
            data=convert(values[:,indices],node.dtype,count);valid=known[:,indices].reshape(data.shape)
        elif node.op=='select':
            predicate=visit(node.args[0],ctx)
            if predicate.shape!=(count,):raise UnresolvedMath('vector stored condition not implemented')
            chosen=predicate.astype(bool);data=np.zeros((count,)+shape,dtype=np.float32);valid=np.zeros_like(data,dtype=bool)
            for mask,branch in [(chosen,node.args[1]),(~chosen,node.args[2])]:
                if np.any(mask):
                    values,known=stored(branch,ctx if np.all(mask) else context(lanes[mask],ctx))
                    data[mask]=convert(values,node.dtype,int(mask.sum()));valid[mask]=known
            data=convert(data,node.dtype,count)
        elif node.op=='cast':
            values,known=stored(node.args[0],ctx);old_size=values.reshape(count,-1).shape[1]
            data=convert(values,node.dtype,count,zero_extend=True)
            boolean_type=re.sub(r'^(?:float|int|bool)','bool',node.dtype)
            valid=convert(known,boolean_type,count,zero_extend=True)
            if old_size>1 and data.reshape(count,-1).shape[1]>old_size:
                valid.reshape(count,-1)[:,old_size:]=True
        else:data=visit(node,ctx);valid=np.ones_like(data,dtype=bool)
        stored_cache[key]=(data,valid);return data,valid

    def loop(node,ctx,*,partial=False):
        nonlocal loop_steps
        plan=node.detail['plan'];key=(id(plan),ctx,nan_coordinates);lanes=contexts[ctx]
        if key not in loop_cache:
            state={}
            for name,argument in zip(plan.names,node.args):
                _,shape=_layout(argument.dtype)
                data=np.zeros((size,)+shape,dtype={'float':np.float32,'int':np.int32,'bool':np.bool_}[_layout(argument.dtype)[0]])
                valid=np.zeros((size,)+shape,dtype=bool)
                values,known=stored(argument,ctx);data[lanes]=values;valid[lanes]=known
                state[name]=(data,valid)
            active=lanes.copy()
            for iteration in range(plan.iteration_limit+1):
                loop_ctx=context(active,ctx,{id(plan):state})
                if plan.condition is not None:
                    condition=visit(plan.condition,loop_ctx)
                    if condition.shape!=(len(active),):raise UnresolvedMath('vector loop condition not implemented')
                    active=active[condition.astype(bool)]
                if not len(active):break
                if iteration==plan.iteration_limit:raise UnresolvedMath('shader loop iteration budget exhausted')
                loop_steps+=1
                if loop_steps>16384:raise UnresolvedMath('nested shader iteration budget exhausted')
                body_ctx=context(active,ctx,{id(plan):state})
                for effect in plan.effects:visit(effect,body_ctx)
                updates={name:stored(value,body_ctx) for name,value in plan.updates.items()}
                new=dict(state)
                for name,(value,known) in updates.items():
                    data,valid=state[name];data=data.copy();valid=valid.copy()
                    data[active]=value;valid[active]=known;new[name]=(data,valid)
                state=new
            loop_cache[key]=state
        if node.detail['name'] is None:
            data=np.ones(len(lanes),dtype=bool)
            return (data,data.copy()) if partial else data
        data,valid=loop_cache[key][node.detail['name']]
        if partial:return data[lanes],valid[lanes]
        if not np.all(valid[lanes]):raise UnresolvedMath('uninitialized shader loop output')
        return data[lanes]

    def visit(node,ctx):
        nonlocal nan_coordinates
        key=(id(node),ctx,nan_coordinates)
        if key in cache:return cache[key]
        lanes=contexts[ctx];count=len(lanes);op=node.op
        if uniform is not None and count>1 and uniform.is_uniform(node):
            # The proof excludes pixels, samples, evolving loop state and
            # effects. Use the same numerical interpreter on one lane; do not
            # replace arithmetic with a different scalar implementation.
            identity=(id(node),nan_coordinates)
            if identity not in uniform_values:
                # The observed NaN-coordinate policy is enabled only inside a
                # sample call. Retain its existing domain handling there.
                if not nan_coordinates:
                    value=evaluate_grid(node,batch_shape=(1,),inputs=inputs,
                        coordinate_profile=coordinate_profile,numeric_policy=numeric_policy,
                        arithmetic_profile=arithmetic_profile,work_policy='full-grid-v1')[0]
                    uniform_values[identity]=value
                    work_counts['uniform_subgraphs']+=1
            if identity in uniform_values:
                value=uniform_values[identity]
                # Cached values retain the original writable lane ownership,
                # including sampler callbacks that wrap coordinates in place.
                result=np.broadcast_to(value,(count,)+np.asarray(value).shape).copy()
                cache[key]=result;work_counts['math_lanes_avoided']+=count-1
                return result
        if op=='unknown':raise UnresolvedMath(node.detail['reason'])
        if op=='constant':
            value=typed(node.detail['value'],node.dtype)
            raw=np.broadcast_to(value,(count,)+value.shape)
        elif op=='input':raw=bind(node.detail['name'],node.dtype,ctx,
                                  unbound_default=node.detail.get('unbound_default'))
        elif op=='loop_slot':
            state=states[ctx].get(id(node.detail['plan']))
            if state is None:raise UnresolvedMath('loop state outside execution context')
            data,valid=state[node.detail['name']]
            if not np.all(valid[lanes]):raise UnresolvedMath('uninitialized shader loop read')
            raw=data[lanes]
        elif op=='loop_result':raw=loop(node,ctx)
        elif op in {'components','member','flat_component','array','array_index','array_write'}:
            raw,valid=stored(node,ctx)
            if not np.all(valid):raise UnresolvedMath('uninitialized shader component read')
        elif op=='select':
            predicate=visit(node.args[0],ctx)
            if predicate.shape!=(count,):raise UnresolvedMath('vector grid condition not implemented')
            chosen=predicate.astype(bool)
            if np.all(chosen):raw=visit(node.args[1],ctx)
            elif not np.any(chosen):raw=visit(node.args[2],ctx)
            else:
                _,shape=_layout(node.dtype);raw=np.empty((count,)+shape,dtype=np.float32)
                for mask,branch in [(chosen,node.args[1]),(~chosen,node.args[2])]:
                    branch_count=int(mask.sum())
                    raw[mask]=convert(visit(branch,context(lanes[mask],ctx)),node.dtype,branch_count)
        elif op in {'and','or'}:
            left=visit(node.args[0],ctx)
            if left.shape!=(count,):raise UnresolvedMath('vector logical grid condition not implemented')
            raw=left.astype(bool).copy();needed=raw if op=='and' else ~raw
            if np.any(needed):
                right=visit(node.args[1],ctx if np.all(needed) else context(lanes[needed],ctx))
                if right.shape!=(int(needed.sum()),):raise UnresolvedMath('vector logical grid RHS not implemented')
                raw[needed]=right.astype(bool)
        elif op=='sample':
            detail=node.detail if sample_detail is None else sample_detail(node.detail)
            if not isinstance(detail,dict):raise ValueError('sample detail binding must return a dictionary')
            if sample is None:raise UnresolvedMath('texture function not supplied: '+detail['sampler'])
            if len(node.args)!=1 and not (len(node.args)==2 and detail.get('lod_effect')=='base level only'
                    and detail.get('sampling_policy',{}).get('mipmapped') is False
                    and detail.get('sampling_policy',{}).get('base_level')==0):
                raise UnresolvedMath('texture grid overload not implemented')
            prior=nan_coordinates
            try:
                nan_coordinates=coordinate_profile!='strict'
                coordinates=visit(node.args[0],ctx)
            finally:nan_coordinates=prior
            for argument in node.args[1:]:
                if not np.all(np.isfinite(visit(argument,ctx))):raise UnresolvedMath('nonfinite texture argument')
            if np.any(np.isinf(coordinates)):raise UnresolvedMath('nonfinite texture coordinates')
            if np.any(np.isnan(coordinates)):
                policy=detail.get('sampling_policy',{})
                if coordinates.shape[-1]!=2 or type(policy.get('wrap')) is not bool:
                    raise UnresolvedMath('NaN sampler addressing policy unresolved')
                # Observed Apple addressing, not a change to shader arithmetic.
                coordinates=np.where(np.isnan(coordinates),0 if policy['wrap'] else 1,coordinates)
            if on_sample is not None:on_sample(detail,coordinates.copy(),lanes.copy())
            raw=np.asarray(sample(detail,coordinates))
            _,shape=_layout(node.dtype)
            if raw.shape==shape:raw=np.broadcast_to(raw,(count,)+shape)
        elif op=='multiply' and node.detail.get('zero_guard') and not nan_coordinates and all(maskable_math(a,inputs) for a in node.args):
            _,shape=_layout(node.dtype)
            try:right=visit(node.args[1],ctx)
            except UnresolvedMath:
                left=visit(node.args[0],ctx)
                zero=np.all(left.reshape(count,-1)==0,axis=1)
                if not np.any(zero):raise
                raw=np.zeros((count,)+shape,dtype=np.float32)
                if np.any(~zero):
                    active=context(lanes[~zero],ctx)
                    right=visit(node.args[1],active)
                    raw[~zero]=np.multiply(*align([left[~zero],right]))
            else:
                zero=np.all(right.reshape(count,-1)==0,axis=1)
                raw=np.zeros((count,)+shape,dtype=np.float32)
                if np.any(~zero):
                    active=ctx if not np.any(zero) else context(lanes[~zero],ctx)
                    left=visit(node.args[0],active)
                    operands=align([left,right[~zero]])
                    raw[~zero]=np.where((operands[0]==0)|(operands[1]==0),0,np.multiply(*operands))
        else:
            args=[visit(a,ctx) for a in node.args]
            if highp:check_infinity_operation(op,args)
            if op=='sequence':raw=args[-1]
            elif op=='source_domain_guard':
                lo,hi=node.detail['bounds']
                if np.any(~np.isfinite(args[0])) or np.any((args[0]<lo)|(args[0]>hi)):
                    raise UnresolvedMath('source domain violated by shader input')
                raw=np.ones(count,dtype=bool)
            elif op=='index_guard':
                index=args[0]
                if index.shape!=(count,) or np.any((index<0)|(index>=node.detail['length'])):
                    raise UnresolvedMath('shader index out of bounds')
                raw=np.ones(count,dtype=bool)
            elif op in {'construct','aggregate'}:raw=np.concatenate([a.reshape(count,-1) for a in args],axis=1)
            elif op=='matrix_constructor':
                raw=matrix_constructor(args,node.dtype,[a.dtype for a in node.args],count=count)
            elif op=='matrix_cast':raw=matrix_cast(args[0],node.dtype,node.args[0].dtype)
            elif op=='matrix_product':raw=np.matmul(*args)
            elif op=='domain_checked':raw=args[0]
            elif op=='cast':raw=args[0]
            elif op=='member':
                if not node.detail.get('swizzle'):raise UnresolvedMath('struct/matrix grid member not implemented')
                raw=args[0][:,[SWIZZLE[c] for c in node.detail['field']]]
            elif op=='write_member':
                raw=args[0].copy();indices=[SWIZZLE[c] for c in node.detail['field']]
                raw[:,indices]=args[1].reshape(count,-1)
            elif op=='index':
                indices=args[1]
                if indices.shape!=(count,) or np.any(indices!=np.trunc(indices)):
                    raise UnresolvedMath('invalid grid index')
                index=indices.astype(np.int64)
                if np.any((index<0)|(index>=args[0].shape[1])):raise UnresolvedMath('grid index out of bounds')
                raw=args[0][np.arange(count),index]
            elif op=='unary':
                operator=node.detail['operator']
                if operator==0:raw=-args[0]
                elif operator==1:raw=+args[0]
                elif operator==2:raw=np.logical_not(args[0])
                else:raise UnresolvedMath('stateful grid unary operator not implemented')
            elif op=='remainder' and node.dtype.startswith('float'):raw=np.mod(*align(args))
            elif op in BINARY:
                operands=align(args)
                if node.dtype.startswith('int') and op in {'add','subtract','multiply'}:
                    operands=[a.astype(np.int64) for a in operands]
                raw=BINARY[op](*operands)
                if (nan_coordinates or highp) and op=='multiply' and node.detail.get('zero_guard'):
                    raw=np.where((operands[0]==0)|(operands[1]==0),0,raw)
            elif op in UNARY:raw=UNARY[op](args[0])
            elif op=='mul':
                left_shape=_layout(node.args[0].dtype)[1];right_shape=_layout(node.args[1].dtype)[1]
                if not left_shape or not right_shape:raw=np.multiply(*align(args))
                elif len(left_shape)==len(right_shape)==1:raw=np.sum(args[0]*args[1],axis=1)
                elif len(left_shape)==1:raw=np.matmul(args[0][:,None,:],args[1])[:,0,:]
                elif len(right_shape)==1:raw=np.matmul(args[0],args[1][...,None])[...,0]
                else:raw=np.matmul(*args)
            elif op=='dot':raw=np.sum(args[0]*args[1],axis=1)
            elif op=='reflect':
                incident,normal=args
                product=incident*normal
                dot=product if product.ndim==1 else np.sum(product,axis=1,keepdims=True)
                raw=incident-np.float32(2)*dot*normal
            elif op=='log10':raw=np.log(args[0])/np.log(np.float32(10))
            elif op in {'length','distance','normalize'}:
                value=args[0]-args[1] if op=='distance' else args[0]
                norm=np.abs(value) if value.ndim==1 else np.linalg.norm(value,axis=tuple(range(1,value.ndim)))
                raw=value/norm.reshape((count,)+(1,)*(value.ndim-1)) if op=='normalize' else norm
            elif op=='cross':raw=np.cross(*args)
            elif op=='pow':
                base,exponent=align(args)
                if np.any(base<0):raise UnresolvedMath('pow grid negative base domain')
                if np.any((base==0)&(exponent<=0)):raise UnresolvedMath('pow grid zero base with nonpositive exponent domain')
                raw=np.power(base,exponent)
            elif op=='rsqrt':raw=1/np.sqrt(args[0])
            elif op=='atan2':raw=np.arctan2(*align(args))
            elif op=='min':raw=np.minimum(*align(args))
            elif op=='max':raw=np.maximum(*align(args))
            elif op=='clamp':raw=np.clip(*align(args))
            elif op=='saturate':raw=np.clip(args[0],0,1)
            elif op=='lerp':
                a,b,t=align(args);raw=mix_values(a,b,t,arithmetic_profile=arithmetic_profile)
            elif op=='frac':raw=args[0]-np.floor(args[0])
            elif op=='step':
                a,b=align(args);raw=np.asarray(b>=a,dtype=np.float32)
            elif op=='smoothstep':
                a,b,x=align(args);t=np.clip((x-a)/(b-a),0,1);raw=t*t*(3-2*t)
            elif op=='fmod':raw=np.mod(*align(args))
            elif op=='eel_divide':
                # Inlined per-frame (projectm-eval) graphs: division by |b| < 1e-5 yields 0.
                a,b=align(args);small=np.abs(b)<1e-5
                raw=np.where(small,0,a/np.where(small,1,b)).astype(np.result_type(a,b,np.float32))
            elif op=='eel_equal':
                a,b=align(args);raw=np.asarray(np.abs(a-b)<1e-5,dtype=np.float32)
            elif op=='bnot':raw=np.asarray(np.abs(args[0])<1e-5,dtype=np.float32)
            elif op=='negate':raw=-args[0]
            elif op=='sqr':raw=args[0]*args[0]
            elif op=='int':raw=np.floor(args[0])  # time_expression's projectm-eval int
            elif op in {'band','bor'}:
                a,b=align(args);combine=np.logical_and if op=='band' else np.logical_or
                raw=np.asarray(combine(np.abs(a)>1e-5,np.abs(b)>1e-5),dtype=np.float32)
            elif op in {'all','any'}:
                function=np.all if op=='all' else np.any
                raw=function(args[0],axis=tuple(range(1,args[0].ndim)))
            else:raise UnresolvedMath('grid operation not implemented: '+op)
        propagates_nan={'divide','add','subtract','multiply','dot','member','components','cast','construct','aggregate','unary'}
        if (np.any(np.isinf(raw)) and not (highp and op in INFINITY_OPERATIONS)) or (np.any(np.isnan(raw)) and not (nan_coordinates and op in propagates_nan)):
            raise UnresolvedMath('unresolved grid numeric domain: '+op)
        result=convert(raw,node.dtype,count,zero_extend=op=='cast');cache[key]=result
        return result
    try:
        with np.errstate(all='ignore'):
            result=visit(field,0)
        output=result.reshape(batch_shape+result.shape[1:])
        # Keep the existing writable return contract; the one-lane proof only
        # removes intermediate math arrays, not the caller's output ownership.
        return output if output.flags.writeable else output.copy()
    except UnresolvedMath:raise
    except (KeyError,IndexError,TypeError,ValueError) as error:
        raise UnresolvedMath('unsupported grid expression: '+str(error)) from error
    finally:
        # Recursive evaluator closures form cycles. NumPy buffers can dwarf the
        # object count that triggers cyclic GC, so release their per-call state
        # deterministically on success and on every failure. Returned arrays keep
        # their own NumPy storage references; caller dictionaries are not mutated.
        cache.clear();bound.clear();stored_cache.clear();loop_cache.clear()
        contexts.clear();states.clear();context_keys.clear()
        uniform_values.clear()
        if uniform is not None:
            if work is not None:
                work.update(work_counts,uniform_proof_nodes=uniform.nodes,
                            uniform_proof_budget_exceeded=uniform.budget_exceeded)
            uniform.release()
        inputs=None;sample=None;on_sample=None;sample_detail=None
