"""Evaluate declared shader arithmetic without GPU rendering or image references.

Only explicit inputs and caller-supplied texture functions are used. Unresolved
operations and nonfinite domains raise rather than becoming plausible colours.
Float operations use binary32; this is not a guarantee of GPU bit identity (FMA,
transcendentals and driver handling of undefined domains can differ).
"""
import functools
import re
import numpy as np
from shader_fields import Field


class UnresolvedMath(ValueError):
    pass


GLES_HIGHP_INFINITY='gles300-highp-infinity-v1'
# Illustration only (never a proof): IEEE infinities and NaN propagate as on GLES hardware; non-finite
# sample coordinates are addressed like the edge (wrap -> 0, clamp -> nearest edge).
GLES_IEEE_ILLUSTRATION='gles300-ieee-illustration-v1'
INFINITY_OPERATIONS={'add','subtract','multiply','divide','dot','mul','member','index','components',
    'cast','construct','aggregate','unary','abs','min','max','clamp','saturate',
    'sequence','select','write_member','less','greater','less_equal','greater_equal',
    'equal','not_equal','and','or','all','any','loop_result','loop_slot'}


def check_infinity_operation(op,args):
    if any(np.any(np.isinf(a)) for a in args) and op not in INFINITY_OPERATIONS:
        raise UnresolvedMath('highp infinity consumer not established: '+op)
    if op=='divide':
        numerator,denominator=np.broadcast_arrays(*args)
        tiny=np.finfo(np.float32).tiny
        if np.any((np.abs(numerator)>0)&(np.abs(numerator)<tiny)) or np.any((np.abs(denominator)>0)&(np.abs(denominator)<tiny)):
            raise UnresolvedMath('highp division subnormal flushing policy unresolved')
        zero=denominator==0
        if np.any(zero&((numerator<=0)|np.signbit(denominator))):
            raise UnresolvedMath('highp zero division sign or NaN domain unresolved')


def maskable_math(field, inputs):
    """Only discard pure numeric work; preserve unresolved reads and effects."""
    pending=[field];seen=set()
    while pending:
        node=pending.pop()
        if id(node) in seen:continue
        seen.add(id(node))
        if node.op in {'unknown','uninitialized','sample','sequence','index','index_guard','write_member'} or node.op.startswith(('loop_','array')):
            return False
        if node.op=='input':
            name=node.detail['name']
            if name not in inputs and 'unbound_default' not in node.detail:return False
            value=inputs.get(name,node.detail.get('unbound_default'))
            try:
                if not np.all(np.isfinite(value)):return False
                base,_=numeric_layout(node.dtype)
                if base=='float':
                    with np.errstate(over='ignore',invalid='ignore'):
                        if not np.all(np.isfinite(np.asarray(value,dtype=np.float32))):return False
                elif base=='int' and np.any((np.asarray(value)<np.iinfo(np.int32).min)|(np.asarray(value)>np.iinfo(np.int32).max)):
                    return False
            except (ValueError,TypeError,OverflowError):return False
        pending.extend(node.args)
    return True


def matrix_cast(value,dtype,source_dtype):
    rows,cols=map(int,re.fullmatch(r'float([2-4])x([2-4])',dtype).groups())
    source=re.fullmatch(r'(float|int|bool)([1-4])?(?:x([1-4]))?',source_dtype)
    if source is None:raise UnresolvedMath('matrix cast source type not implemented')
    _,r,c=source.groups();shape=(int(r),int(c)) if c else (int(r),) if r else ()
    data=np.asarray(value);prefix=data.shape[:-len(shape)] if shape else data.shape
    if not shape:
        result=np.zeros(prefix+(rows,cols),dtype=np.float32)
        indices=np.arange(min(rows,cols));result[...,indices,indices]=data[...,None]
    elif len(shape)==2:
        result=np.broadcast_to(np.eye(rows,cols,dtype=np.float32),prefix+(rows,cols)).copy()
        rr,cc=min(rows,shape[0]),min(cols,shape[1]);result[...,:rr,:cc]=data[...,:rr,:cc]
    else:
        if shape[0]<rows*cols:raise UnresolvedMath('matrix cast has insufficient vector components')
        result=data[...,:rows*cols].reshape(prefix+(cols,rows)).swapaxes(-1,-2)
    return result


def matrix_constructor(args,dtype,arg_types,*,count=None):
    rows,cols=map(int,re.fullmatch(r'float([2-4])x([2-4])',dtype).groups())
    # Native helper ignores matrix arguments; scalar/vector arguments fill rows.
    shape=(count,-1) if count is not None else (-1,)
    values=[np.asarray(a).reshape(shape) for a,t in zip(args,arg_types) if 'x' not in t]
    flat=np.concatenate(values,axis=-1) if values else np.empty((count,0) if count is not None else (0,))
    size=flat.shape[-1]
    if size>rows*cols:raise UnresolvedMath('overfilled native matrix constructor')
    padding=((0,0),(0,rows*cols-size)) if count is not None else (0,rows*cols-size)
    return np.pad(flat,padding).reshape((count,rows,cols) if count is not None else (rows,cols))


@functools.lru_cache(maxsize=None)
def numeric_layout(dtype):
    # Pure parse of a dtype string (a few distinct values, evaluated per node per frame): memoised.
    array=re.fullmatch(r'(.+)\[([1-9][0-9]*)\]',dtype)
    if array:
        base,shape=numeric_layout(array[1]);return base,(int(array[2]),)+shape
    match=re.fullmatch(r'(float|int|bool)([1-4])?(?:x([1-4]))?',dtype)
    if not match:raise UnresolvedMath('numeric type not implemented: '+dtype)
    base,rows,cols=match.groups()
    shape=(int(rows),int(cols)) if cols else ((int(rows),) if rows else ())
    return base,shape


def typed(value,dtype,*,allow_infinity=False):
    base,shape=numeric_layout(dtype)
    data=np.asarray(value)
    if np.any(np.isnan(data)) or (np.any(np.isinf(data)) and not (allow_infinity and base in {'float','bool'})):
        raise UnresolvedMath('nonfinite value for '+dtype)
    size=int(np.prod(shape)) if shape else 1
    flat=data.reshape(-1)
    if ('[' in dtype or len(shape)==2) and flat.size!=size:
        raise UnresolvedMath('matrix/array constructor size mismatch: '+dtype)
    if flat.size==1:flat=np.repeat(flat,size)
    elif flat.size>=size:flat=flat[:size]
    else:raise UnresolvedMath('insufficient components for '+dtype)
    if base=='int' and np.any((flat<np.iinfo(np.int32).min)|(flat>np.iinfo(np.int32).max)):
        raise UnresolvedMath('integer conversion outside signed 32-bit range')
    converted=flat.astype({'float':np.float32,'int':np.int32,'bool':np.bool_}[base]).reshape(shape)
    if np.any(np.isnan(converted)) or (np.any(np.isinf(converted)) and not (allow_infinity and base=='float')):
        raise UnresolvedMath('nonfinite narrowing to '+dtype)
    return converted


SWIZZLE={c:i for names in ['xyzw','rgba'] for i,c in enumerate(names)}
BINARY={'add':np.add,'subtract':np.subtract,'multiply':np.multiply,'divide':np.divide,
        'remainder':np.fmod,'less':np.less,'greater':np.greater,'less_equal':np.less_equal,
        'greater_equal':np.greater_equal,'equal':np.equal,'not_equal':np.not_equal,
        'and':np.logical_and,'or':np.logical_or,'bit_and':np.bitwise_and,
        'bit_or':np.bitwise_or,'bit_xor':np.bitwise_xor}
UNARY={'sin':np.sin,'cos':np.cos,'tan':np.tan,'asin':np.arcsin,'acos':np.arccos,
       'atan':np.arctan,'abs':np.abs,'sqrt':np.sqrt,'exp':np.exp,'exp2':np.exp2,'log':np.log,
       'log2':np.log2,'floor':np.floor,'ceil':np.ceil,'round':np.rint,
       'trunc':np.trunc,'sign':np.sign,'modf_fraction':lambda value:np.modf(value)[0]}

SEPARATE_ARITHMETIC='separate-float32-v1'
APPLE_MIX_FMA='apple-m4pro-gles-mix-nested-fma-v1'


def mix_values(a,b,t,*,arithmetic_profile=SEPARATE_ARITHMETIC):
    if arithmetic_profile not in (SEPARATE_ARITHMETIC,APPLE_MIX_FMA):
        raise UnresolvedMath('unsupported shader arithmetic profile')
    a,b,t=np.broadcast_arrays(*(np.asarray(x,np.float32) for x in (a,b,t)))
    if arithmetic_profile==SEPARATE_ARITHMETIC:return a+t*(b-a)
    if not np.all(np.isfinite([a,b,t])):
        raise UnresolvedMath('finite inputs required for fused mix')
    from custom_wave import _fmaf
    fused=_fmaf()
    return np.asarray([fused(y,z,fused(-x,z,x)) for x,y,z in zip(a.flat,b.flat,t.flat)],np.float32).reshape(a.shape)


def evaluate(field:Field,*,inputs=None,sample=None,numeric_policy='strict',arithmetic_profile=SEPARATE_ARITHMETIC):
    if arithmetic_profile not in (SEPARATE_ARITHMETIC,APPLE_MIX_FMA):raise UnresolvedMath('unsupported shader arithmetic profile')
    if numeric_policy not in {'strict',GLES_HIGHP_INFINITY}:raise UnresolvedMath('unsupported shader numeric policy')
    highp=numeric_policy==GLES_HIGHP_INFINITY
    inputs=inputs or {};cache={}
    pending=[field];seen=set()
    while pending:
        node=pending.pop()
        if id(node) in seen:continue
        seen.add(id(node))
        if node.op in {'loop_result','array','array_index','array_write'}:
            # Evaluate the whole graph in one lane so loop guards and multiple
            # outputs share one execution and its texture samples.
            from grid_math import evaluate_grid
            def one_sample(detail,coordinates):return sample(detail,coordinates[0])
            return evaluate_grid(field,batch_shape=(1,),inputs=inputs,sample=one_sample if sample else None,numeric_policy=numeric_policy,arithmetic_profile=arithmetic_profile)[0]
        pending.extend(node.args)
    def visit(node):
        key=id(node)
        if key in cache:return cache[key]
        op=node.op
        if op=='unknown':raise UnresolvedMath(node.detail['reason'])
        if op=='constant':raw=node.detail['value']
        elif op=='input':
            name=node.detail['name']
            if name in inputs:raw=inputs[name]
            elif 'unbound_default' in node.detail:raw=node.detail['unbound_default']
            else:raise UnresolvedMath('missing symbolic input: '+name)
        elif op=='select':
            condition=visit(node.args[0])
            if condition.size!=1:raise UnresolvedMath('vector condition not implemented')
            raw=visit(node.args[1] if condition.item() else node.args[2])
        elif op in {'and','or'}:
            left=visit(node.args[0])
            if left.size!=1:raise UnresolvedMath('vector logical condition not implemented')
            needs_right=bool(left.item()) if op=='and' else not bool(left.item())
            raw=visit(node.args[1]) if needs_right else left
        elif op=='sample':
            if sample is None:raise UnresolvedMath('texture function not supplied: '+node.detail['sampler'])
            if len(node.args)!=1 and not (len(node.args)==2 and node.detail.get('lod_effect')=='base level only'
                    and node.detail.get('sampling_policy',{}).get('mipmapped') is False
                    and node.detail.get('sampling_policy',{}).get('base_level')==0):
                raise UnresolvedMath('texture overload not implemented')
            values=[visit(arg) for arg in node.args]
            if any(not np.all(np.isfinite(v)) for v in values):raise UnresolvedMath('nonfinite texture coordinates')
            raw=sample(node.detail,values[0])
        elif op=='multiply' and node.detail.get('zero_guard') and all(maskable_math(a,inputs) for a in node.args):
            # Native GLSL mult0 returns zero regardless of the other numeric
            # argument, including a division's unspecified nonfinite result.
            try:right=visit(node.args[1])
            except UnresolvedMath:
                left=visit(node.args[0])
                if not np.all(left==0):raise
                raw=np.zeros(numeric_layout(node.dtype)[1],dtype=np.float32)
            else:
                if np.all(right==0):raw=np.zeros(numeric_layout(node.dtype)[1],dtype=np.float32)
                else:
                    left=visit(node.args[0]);raw=np.where((left==0)|(right==0),0,left*right)
        else:
            args=[visit(a) for a in node.args]
            if highp:check_infinity_operation(op,args)
            if op=='sequence':raw=args[-1]
            elif op=='source_domain_guard':
                lo,hi=node.detail['bounds']
                if np.any(~np.isfinite(args[0])) or np.any((args[0]<lo)|(args[0]>hi)):
                    raise UnresolvedMath('source domain violated by shader input')
                raw=True
            elif op=='index_guard':
                index=args[0]
                if index.size!=1 or index.item()<0 or index.item()>=node.detail['length']:
                    raise UnresolvedMath('shader index out of bounds')
                raw=True
            elif op in {'construct','aggregate','components'}:raw=np.concatenate([np.asarray(a).reshape(-1) for a in args])
            elif op=='matrix_constructor':raw=matrix_constructor(args,node.dtype,[a.dtype for a in node.args])
            elif op=='matrix_cast':raw=matrix_cast(args[0],node.dtype,node.args[0].dtype)
            elif op=='matrix_product':raw=np.matmul(*args)
            elif op=='flat_component':raw=args[0].reshape(-1)[node.detail['index']]
            elif op=='domain_checked':raw=args[0]
            elif op=='cast':
                raw=args[0]
                match=re.fullmatch(r'(float|int|bool)([1-4])',node.dtype)
                if match and raw.ndim==1 and raw.size<int(match[2]):
                    # GLSLGenerator::CompleteConstructorArguments zero-extends
                    # vector casts, rather than inventing extra components.
                    raw=np.pad(raw,(0,int(match[2])-raw.size))
            elif op=='member':
                if not node.detail.get('swizzle'):raise UnresolvedMath('struct/matrix member not implemented')
                raw=args[0].reshape(-1)[[SWIZZLE[c] for c in node.detail['field']]]
            elif op=='write_member':
                raw=args[0].copy().reshape(-1);indices=[SWIZZLE[c] for c in node.detail['field']]
                raw[indices]=np.broadcast_to(args[1],(len(indices),))
            elif op=='index':
                index=args[1]
                if index.size!=1 or index.item()!=int(index.item()):raise UnresolvedMath('invalid index')
                i=int(index.item())
                if i<0 or i>=len(args[0]):raise UnresolvedMath('index out of bounds')
                raw=args[0][i]
            elif op=='unary':
                operator=node.detail['operator']
                if operator==0:raw=-args[0]
                elif operator==1:raw=+args[0]
                elif operator==2:raw=np.logical_not(args[0])
                else:raise UnresolvedMath('stateful unary operator not implemented')
            elif op=='remainder' and node.dtype.startswith('float'):raw=np.mod(*args)
            elif op in BINARY:
                operands=[a.astype(np.int64) for a in args] if node.dtype.startswith('int') and op in {'add','subtract','multiply'} else args
                raw=BINARY[op](*operands)
                if op=='multiply' and node.detail.get('zero_guard'):
                    raw=np.where((operands[0]==0)|(operands[1]==0),0,raw)
            elif op in UNARY:raw=UNARY[op](args[0])
            elif op=='mul':raw=args[0]*args[1] if args[0].ndim==0 or args[1].ndim==0 else np.matmul(*args)
            elif op=='dot':raw=np.dot(*args)
            elif op=='reflect':raw=args[0]-np.float32(2)*np.dot(args[1],args[0])*args[1]
            elif op=='log10':raw=np.log(args[0])/np.log(np.float32(10))
            elif op=='length':raw=np.linalg.norm(args[0])
            elif op=='distance':raw=np.linalg.norm(args[0]-args[1])
            elif op=='normalize':raw=args[0]/np.linalg.norm(args[0])
            elif op=='cross':raw=np.cross(*args)
            elif op=='pow':
                if np.any(args[0]<0):raise UnresolvedMath('pow negative base domain')
                if np.any((args[0]==0)&(args[1]<=0)):raise UnresolvedMath('pow zero base with nonpositive exponent domain')
                raw=np.power(*args)
            elif op=='rsqrt':raw=1/np.sqrt(args[0])
            elif op=='atan2':raw=np.arctan2(*args)
            elif op=='min':raw=np.minimum(*args)
            elif op=='max':raw=np.maximum(*args)
            elif op=='clamp':raw=np.clip(*args)
            elif op=='saturate':raw=np.clip(args[0],0,1)
            elif op=='lerp':raw=mix_values(*args,arithmetic_profile=arithmetic_profile)
            elif op=='frac':raw=args[0]-np.floor(args[0])
            elif op=='step':raw=np.asarray(args[1]>=args[0],dtype=np.float32)
            elif op=='smoothstep':
                t=np.clip((args[2]-args[0])/(args[1]-args[0]),0,1);raw=t*t*(3-2*t)
            elif op=='fmod':raw=np.mod(*args)
            elif op=='all':raw=np.all(args[0])
            elif op=='any':raw=np.any(args[0])
            else:raise UnresolvedMath('operation not implemented: '+op)
        allow_infinity=highp and op in INFINITY_OPERATIONS
        if np.any(np.isnan(raw)) or (np.any(np.isinf(raw)) and not allow_infinity):
            raise UnresolvedMath('unresolved numeric domain: '+op)
        result=typed(raw,node.dtype,allow_infinity=allow_infinity);cache[key]=result
        return result
    try:
        with np.errstate(all='ignore'):return visit(field)
    except UnresolvedMath:raise
    except (KeyError,IndexError,TypeError,ValueError) as exc:
        raise UnresolvedMath('unsupported numeric expression: '+str(exc)) from exc
