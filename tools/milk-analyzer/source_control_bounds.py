"""Bounded calculus on continuous nominal scalar source-time formulas."""
import math


def merge_continuity(kinds):
    if not kinds or any(k=='unknown' for k in kinds):return 'unknown'
    return 'piecewise_lipschitz' if 'piecewise_lipschitz' in kinds else 'smooth_nominal'


def compound_time_bounds(field,*,_value_only=False,_input_domains=None,_response_input_names=None):
    from source_appearance import _phase_literal
    memo={};active=set();finite_inputs=set()
    def magnitude(span):return None if span is None else max(map(abs,span))
    def add_rates(a,b):return None if a is None or b is None else a+b
    def positive_divide(a,b):
        value=a/b
        if a>0 and b>0 and value==0:raise ValueError('nominal rate quotient underflow')
        return math.nextafter(value,math.inf) if value>0 else value
    def positive_multiply(a,b):
        if a==0 or b==0:return 0.
        value=a*b
        if a>0 and b>0 and value==0:raise ValueError('nominal rate product underflow')
        return math.nextafter(value,math.inf) if value>0 else value
    def product_term(rate,span):
        if rate==0:return 0.
        maximum=magnitude(span)
        if rate is None or maximum is None:return None
        return positive_multiply(rate,maximum)
    def continuity(*items):
        return 'piecewise_lipschitz' if any(i[2]=='piecewise_lipschitz' for i in items) else 'smooth_nominal'
    def checked(span,rate,kind):
        if span is not None:
            if span[0]==math.inf or span[1]==-math.inf:
                raise ValueError('source value envelope has a known overflow endpoint domain')
            if any(math.isnan(v) for v in span) or span[0]>span[1]:span=None
            elif not _value_only and not all(math.isfinite(v) for v in span):span=None
            else:
                # One outward step covers rounding in each endpoint operation.
                span=[math.nextafter(span[0],-math.inf),math.nextafter(span[1],math.inf)]
                if not _value_only and not all(math.isfinite(v) for v in span):span=None
        if rate is not None and (not math.isfinite(rate) or rate<0):rate=None
        elif rate is not None and rate>0:
            rate=math.nextafter(rate,math.inf)
            if not math.isfinite(rate):rate=None
        return span,rate,kind
    def nonnegative(result):
        # Squares and sums/products of same-signed operands are exactly >= 0 under IEEE rounding: the outward
        # rounding step must not move a 0 endpoint below zero.
        span,rate,kind=result
        return ([max(0.,span[0]),span[1]] if span is not None else None),rate,kind
    def visit(node,depth=0):
        key=id(node)
        if key in memo and memo[key][0] is node:return memo[key][1]
        if depth>64 or len(memo)+len(active)>=512 or key in active:raise ValueError('compound source-time node/depth budget exceeded')
        active.add(key)
        try:result=calculate(node,depth)
        finally:active.remove(key)
        memo[key]=(node,result);return result
    def input_result(name):
        if not isinstance(name,str) or not name:return None
        finite_inputs.add(name)
        rate=None if _value_only else float(name in _response_input_names)
        kind='unknown' if _value_only else 'smooth_nominal'
        if _input_domains and name in _input_domains:
            span=_input_domains[name]
            if not isinstance(span,(list,tuple)) or len(span)!=2 or not all(type(v) in {int,float} and math.isfinite(v) for v in span) or span[0]>span[1]:
                raise ValueError('declared scalar input domain invalid')
            return (list(span),rate,kind)
        return ([-math.inf,math.inf],rate,kind)
    def calculate(node,depth):
        literal=_phase_literal(node)
        if literal is not None:return ([literal,literal],0.,'smooth_nominal')
        if _response_input_names is not None and node.op in {'narrow','cast','construct'}:
            return None # Quantized/discrete inputs are not nominal continuous maps.
        if (_response_input_names is not None or _value_only) and node.op=='member' and node.dtype=='float':
            from source_appearance import _canonical_lane
            from field_math import SWIZZLE
            projected=_canonical_lane(node);parent=projected.args[0]
            lane=projected.detail.get('field','')
            if projected.detail.get('swizzle') and len(lane)==1 and lane in SWIZZLE and parent.op=='input' and parent.dtype in {'float2','float3','float4'}:
                index=SWIZZLE[lane]
                name=parent.detail.get('name')
                if index<int(parent.dtype[-1]) and isinstance(name,str) and name:
                    return input_result(name+'.'+'xyzw'[index])
            return None
        if node.dtype!='float' and not (_value_only and node.dtype=='bool' and node.op in
                {'less','greater','less_equal','greater_equal','equal','eel_equal','not_equal'}):return None
        if (_value_only or _response_input_names is not None) and node.op=='unary' and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            if child is None:return None
            if node.detail.get('operator')==1:return child
            if node.detail.get('operator')==0:
                span,rate,kind=child
                return checked(None if span is None else [-span[1],-span[0]],rate,kind)
            return None
        if node.op=='normalized_component' and len(node.args)==1:
            from effect_families import _parts
            vector=node.args[0];index=node.detail.get('index')
            if vector.dtype not in {'float','float2','float3','float4'}:return None
            width=1 if vector.dtype=='float' else int(vector.dtype[-1]);parts=_parts(vector)
            if len(parts)!=width or type(index) is not int or not 0<=index<width or any(v.dtype!='float' for v in parts):return None
            values=[visit(v,depth+1) for v in parts]
            if any(v is None for v in values):return None
            lows=[0. if v[0] is None or v[0][0]<=0<=v[0][1] else min(map(abs,v[0])) for v in values]
            highs=[math.inf if v[0] is None else max(map(abs,v[0])) for v in values]
            minimum=math.nextafter(math.hypot(*lows),-math.inf)
            maximum=math.nextafter(math.hypot(*highs),math.inf)
            if minimum<=0 or not math.isfinite(minimum):return None
            numerator=values[index][0];span=[-1.,1.]
            if numerator is not None:
                if all(math.isfinite(v) for v in numerator) and math.isfinite(maximum):
                    quotients=[x/y for x in numerator for y in (minimum,maximum)]
                    span=[max(-1.,min(quotients)),min(1.,max(quotients))]
                else:
                    if numerator[0]>=0:span[0]=0.
                    if numerator[1]<=0:span[1]=0.
            rates=[v[1] for v in values]
            rate=None if any(r is None for r in rates) else positive_divide(math.hypot(*rates),minimum)
            span,rate,kind=checked(span,rate,continuity(*values))
            if span is not None:span=[max(-1.,span[0]),min(1.,span[1])]
            return span,rate,kind
        if node.op in {'length','distance'} and len(node.args)==(1 if node.op=='length' else 2):
            from effect_families import _parts
            from shader_fields import Field
            types={a.dtype for a in node.args}
            if len(types)!=1 or next(iter(types)) not in {'float','float2','float3','float4'}:return None
            width=1 if node.args[0].dtype=='float' else int(node.args[0].dtype[-1])
            parts=[_parts(a) for a in node.args]
            if any(len(p)!=width or any(v.dtype!='float' for v in p) for p in parts):return None
            components=parts[0] if node.op=='length' else [
                Field('subtract',(a,b),'float') for a,b in zip(*parts)]
            values=[visit(v,depth+1) for v in components]
            if any(v is None for v in values):return None
            lows=[];highs=[]
            for span,rate,kind in values:
                lows.append(0. if span is None or span[0]<=0<=span[1] else min(map(abs,span)))
                highs.append(math.inf if span is None else max(map(abs,span)))
            lower,upper=math.hypot(*lows),math.hypot(*highs)
            if not math.isfinite(lower):return None
            rates=[v[1] for v in values]
            rate=None if any(r is None for r in rates) else math.hypot(*rates)
            span,rate,kind=checked([lower,upper],rate,'piecewise_lipschitz')
            if span is not None:span[0]=max(0.,span[0])
            return span,rate,kind
        if _response_input_names is not None and node.op=='select' and len(node.args)==3:
            from source_polar import _nodes
            from source_forms import known_invalid_phase_offset
            predicate=node.args[0]
            for child,path in _nodes(predicate):
                if child.op in {'unknown','uninitialized','sequence','cast','narrow','construct'} or child.op.startswith('loop_'):return None
                if child.op=='input':
                    name=child.detail.get('name')
                    if not isinstance(name,str) or name in _response_input_names or any(n.startswith(name+'.') for n in _response_input_names):return None
            if known_invalid_phase_offset(predicate,preserve_zero_products=True):return None
            condition=scalar_value_envelope(predicate,input_domains=_input_domains)
            if condition['nominal_value_range'] is None:return None
            finite_inputs.update(condition['assumed_finite_input_names'])
            a=visit(node.args[1],depth+1);b=visit(node.args[2],depth+1)
            if a is None or b is None:return None
            span=None if a[0] is None or b[0] is None else [min(a[0][0],b[0][0]),max(a[0][1],b[0][1])]
            rate=None if a[1] is None or b[1] is None else max(a[1],b[1])
            return checked(span,rate,continuity(a,b))
        if _response_input_names is not None and node.op=='domain_checked' and len(node.args)==1:
            function=node.detail.get('function')
            if function not in {'sqrt','pow'} and not (function=='normalize' and node.args[0].op=='normalized_component'):return None
            return visit(node.args[0],depth+1)
        if _response_input_names is not None and node.op in {'saturate','clamp'}:
            child=visit(node.args[0],depth+1)
            if child is None:return None
            low,high=(0.,1.) if node.op=='saturate' else (_phase_literal(node.args[1]),_phase_literal(node.args[2]))
            if low is None or high is None or low>high:return None
            return ([low,high] if child[0] is None else [min(high,max(low,v)) for v in child[0]],child[1],'piecewise_lipschitz')
        if _response_input_names is not None and node.op in {'sqrt','pow'}:
            child=visit(node.args[0],depth+1)
            exponent=.5 if node.op=='sqrt' else _phase_literal(node.args[1])
            if child is None or child[0] is None or exponent is None:return None
            lo,hi=child[0]
            if not all(math.isfinite(v) for v in (lo,hi,exponent)):return None
            if exponent==1:return child
            if exponent<=0 or lo<0 or lo==0 and exponent<1:return None
            values=[math.pow(v,exponent) for v in (lo,hi)]
            gradients=[0. if v==0 else math.pow(v,exponent-1) for v in (lo,hi)]
            if any(not math.isfinite(v) or base>0 and v==0 for base,v in zip((lo,hi),values)) or any(not math.isfinite(v) or base>0 and v==0 for base,v in zip((lo,hi),gradients)):
                raise ValueError('nonlinear response power overflow/underflow')
            rate=None if child[1] is None else positive_multiply(child[1],positive_multiply(exponent,max(gradients)))
            span,rate,kind=checked([min(values),max(values)],rate,child[2])
            if span is not None:span[0]=max(0.,span[0])
            return span,rate,kind
        if _response_input_names is not None and node.op=='lerp' and len(node.args)==3:
            args=[visit(arg,depth+1) for arg in node.args]
            if any(a is None or a[0] is None for a in args):return None
            a,b,t=args;spans=[v[0] for v in args]
            inverse=[1-t[0][1],1-t[0][0]];difference=[b[0][0]-a[0][1],b[0][1]-a[0][0]]
            rate=add_rates(add_rates(product_term(a[1],inverse),product_term(b[1],t[0])),product_term(t[1],difference))
            span=None
            if all(math.isfinite(v) for s in spans for v in s):
                from fractions import Fraction
                values=[float((1-Fraction(z))*Fraction(x)+Fraction(z)*Fraction(y)) for x in spans[0] for y in spans[1] for z in spans[2]]
                span=[min(values),max(values)]
            return checked(span,rate,continuity(*args))
        if _value_only and node.op=='domain_checked' and len(node.args)==1:
            function=node.detail.get('function')
            if function not in {'sqrt','pow'} and not (function=='normalize' and node.args[0].op=='normalized_component'):return None
            return visit(node.args[0],depth+1)
        if _value_only and node.op in {'frac','floor'} and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            if child is None or child[0] is None:return None
            lo,hi=child[0]
            if node.op=='floor':
                if not all(math.isfinite(v) for v in (lo,hi)):return None
                low,high=math.floor(lo),math.floor(hi)
                lower,upper=float(low),float(high)
                if lower>low:lower=math.nextafter(lower,-math.inf)
                if upper<high:upper=math.nextafter(upper,math.inf)
                if not all(math.isfinite(v) for v in (lower,upper)):return None
                return ([lower,upper],None,'unknown')
            if not all(math.isfinite(v) for v in (lo,hi)) or math.floor(lo)!=math.floor(hi):
                return ([0.,1.],None,'unknown')
            span,_,_=checked([lo-math.floor(lo),hi-math.floor(hi)],None,'unknown')
            if span is not None:span=[max(0.,span[0]),min(1.,span[1])]
            return (span,None,'unknown')
        if _value_only and node.op in {'saturate','clamp'}:
            child=visit(node.args[0],depth+1)
            if child is None or child[0] is None:return None
            low,high=(0.,1.) if node.op=='saturate' else (
                _phase_literal(node.args[1]),_phase_literal(node.args[2]))
            if low is None or high is None or low>high:return None
            return ([min(high,max(low,v)) for v in child[0]],None,'unknown')
        if _value_only and node.op in {'sqrt','pow'}:
            child=visit(node.args[0],depth+1)
            if child is None or child[0] is None:return None
            lo,hi=child[0]
            exponent=.5 if node.op=='sqrt' else _phase_literal(node.args[1])
            if exponent is None or lo<0 or lo==0 and exponent<=0:return None
            if not all(math.isfinite(v) for v in (lo,hi,exponent)):return None
            values=[math.pow(v,exponent) for v in (lo,hi)]
            if any(not math.isfinite(v) or base>0 and v==0 for base,v in zip((lo,hi),values)):
                raise ValueError('nonlinear scalar power overflow/underflow')
            span,_,_=checked([min(values),max(values)],None,'unknown')
            if span is not None:span[0]=max(0.,span[0])
            return (span,None,'unknown')
        if _value_only and node.op=='lerp' and len(node.args)==3:
            args=[visit(arg,depth+1) for arg in node.args]
            if any(a is None or a[0] is None for a in args):return None
            spans=[a[0] for a in args]
            if any(not math.isfinite(v) for s in spans for v in s):return None
            from fractions import Fraction
            values=[float((1-Fraction(t))*Fraction(a)+Fraction(t)*Fraction(b))
                    for a in spans[0] for b in spans[1] for t in spans[2]]
            span,_,_=checked([min(values),max(values)],None,'unknown')
            if span is not None and spans[2][0]>=0 and spans[2][1]<=1:
                span[0]=max(span[0],min(spans[0][0],spans[1][0]))
                span[1]=min(span[1],max(spans[0][1],spans[1][1]))
            return (span,None,'unknown')
        if node.op=='input' and (_value_only or _response_input_names is not None):
            return input_result(node.detail.get('name'))
        if node.op=='input' and node.detail.get('name') in {'time',':native-render-time-f32'}:
            return (None,1.,'smooth_nominal')
        if _value_only and node.op in {'select','less','greater','less_equal','greater_equal','equal','eel_equal','not_equal'}:
            args=[visit(arg,depth+1) for arg in node.args]
            if any(a is None for a in args):return None
            if node.op=='select' and len(args)==3:
                a,b=args[1][0],args[2][0]
                if a is None or b is None:return None
                return checked([min(a[0],b[0]),max(a[1],b[1])],None,'unknown')
            if node.op!='select' and len(args)==2:return ([0.,1.],None,'unknown')
            return None
        if _value_only and node.op=='atan' and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            if child is None or child[0] is None:return None
            return checked([math.atan(child[0][0]),math.atan(child[0][1])],None,'unknown')  # monotone onto (-pi/2, pi/2)
        if _value_only and node.op=='atan2' and len(node.args)==2:
            if any(visit(arg,depth+1) is None for arg in node.args):return None
            return checked([-math.pi,math.pi],None,'unknown')
        if _value_only and node.op=='sqr' and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            if child is None or child[0] is None:return None
            lo,hi=child[0];low=0. if lo<=0<=hi else min(lo*lo,hi*hi)
            return nonnegative(checked([low,max(lo*lo,hi*hi)],None,'unknown'))
        if node.op in {'cast','narrow','construct','components','negate','sin','cos','abs'} and len(node.args)==1:
            child=visit(node.args[0],depth+1)
            if child is None:return None
            span,rate,kind=child
            if node.op in {'cast','narrow','construct','components'}:return child
            if node.op=='negate':return checked(None if span is None else [-span[1],-span[0]],rate,kind)
            if node.op in {'sin','cos'}:
                if span is not None and span[0]==span[1] and rate==0:
                    value=(math.sin if node.op=='sin' else math.cos)(span[0]);return ([value,value],0.,kind)
                return ([-1.,1.],rate,kind)
            if span is not None:
                low=0. if span[0]<=0<=span[1] else min(map(abs,span));high=max(map(abs,span))
                if span[0]>=0 or span[1]<=0:return ([low,high],rate,kind)
                span=[low,high]
            return (span,rate,'piecewise_lipschitz')
        if node.op not in {'add','subtract','multiply','divide','eel_divide','min','max'} or len(node.args)!=2:return None
        a=visit(node.args[0],depth+1);b=visit(node.args[1],depth+1)
        if a is None or b is None:return None
        x,dx,_=a;y,dy,_=b;kind=continuity(a,b)
        if node.op in {'add','subtract'}:
            span=None if x is None or y is None else ([x[0]+y[0],x[1]+y[1]] if node.op=='add' else [x[0]-y[1],x[1]-y[0]])
            result=checked(span,add_rates(dx,dy),kind)
            return nonnegative(result) if node.op=='add' and span is not None and x[0]>=0 and y[0]>=0 else result
        if node.op=='multiply':
            products=None if x is None or y is None else [0. if u==0 or v==0 else u*v for u in x for v in y]
            span=None if products is None else [min(products),max(products)]
            result=checked(span,add_rates(product_term(dx,y),product_term(dy,x)),kind)
            same_sign=span is not None and (x[0]>=0 and y[0]>=0 or x[1]<=0 and y[1]<=0)
            return nonnegative(result) if same_sign else result
        if node.op in {'min','max'}:
            if x is not None and y is not None:
                if x[1]<=y[0]:return a if node.op=='min' else b
                if y[1]<=x[0]:return b if node.op=='min' else a
                op=min if node.op=='min' else max;span=[op(x[0],y[0]),op(x[1],y[1])]
            else:span=None
            rate=None if dx is None or dy is None else max(dx,dy)
            return checked(span,rate,'piecewise_lipschitz')
        if y is None:return None
        if node.op=='eel_divide' and -.00001<y[0]<=y[1]<.00001:
            return ([0.,0.],0.,'smooth_nominal')
        minimum=min(map(abs,y))
        if _value_only and node.op=='eel_divide' and (y[0]<=0<=y[1] or minimum<.00001):
            # projectm-eval returns 0 for |divisor| < 1e-5: the quotient of finite operands is an arbitrary finite value.
            return ([-math.inf,math.inf],None,'unknown')
        if y[0]<=0<=y[1] or node.op=='eel_divide' and minimum<.00001:return None
        span=None if x is None else [min(u/v for u in x for v in y),max(u/v for u in x for v in y)]
        # Quotient rule: Df/|g|min + Dg*|f|max/|g|min^2.
        left=None if dx is None else positive_divide(dx,minimum)
        if dy==0:right=0.
        elif dy is None or x is None:right=None
        else:
            first=positive_divide(dy,minimum);second=positive_divide(magnitude(x),minimum)
            right=positive_multiply(first,second)
        return checked(span,add_rates(left,right),kind)
    result={'policy':'source-compound-time-calculus-v1','nominal_value_range':None,
            'maximum_absolute_control_rate_per_second':None,'nominal_continuity':'unknown',
            'supported_nominal_formula':False,'unknown_reasons':[]}
    try:value=visit(field)
    except (ValueError,RecursionError,OverflowError,ZeroDivisionError) as error:
        result['unknown_reasons']=[str(error)];return result
    if value is None:
        result['unknown_reasons']=['unsupported input, discontinuous operation or unproved denominator domain'];return result
    span,rate,kind=value
    if _value_only:
        if span is not None and not all(math.isfinite(v) for v in span):span=None
        rate=None;kind='unknown'
    result.update(nominal_value_range=span,maximum_absolute_control_rate_per_second=rate,
                  nominal_continuity=kind,supported_nominal_formula=True)
    result['assumed_finite_input_names']=sorted(finite_inputs)
    result['declared_input_domains']={name:list(_input_domains[name]) for name in sorted(finite_inputs)
        if _input_domains and name in _input_domains}
    if _value_only:
        if span is None:result['unknown_reasons']=['no finite source value envelope from supported formula']
    elif rate is None:result['unknown_reasons']=['no finite lifetime nominal rate bound from supported formula']
    return result


def scalar_response_envelope(field,*,input_names,input_domains=None):
    """Nominal Lipschitz bound while selected inputs vary together; others fixed."""
    names=set(input_names)
    if not names or any(not isinstance(name,str) or not name for name in names):
        raise ValueError('response input names must be nonempty scalar names')
    report=compound_time_bounds(field,_input_domains=input_domains,_response_input_names=names)
    finite=report.get('assumed_finite_input_names',[])
    result={'policy':'source-nominal-audio-control-response-v1',
        'maximum_absolute_control_change_per_audio_unit':report['maximum_absolute_control_rate_per_second'],
        'bound_kind':'upper_bound','nominal_continuity':report['nominal_continuity'],
        'varying_input_names':sorted(names),'held_fixed_input_names':sorted(set(finite)-names),
        'assumed_finite_input_names':finite,'declared_input_domains':report.get('declared_input_domains',{}),
        'unknown_reasons':report['unknown_reasons'],
        'visible_response_strength':None,'maximum_time_rate':None,
        'native_numeric_certified':False,'uses_equation_execution':False,'uses_rendered_images':False,
        'conditions':['Nominal real-valued source control response; all inputs and relevant intermediates finite',
                      'Selected scalar inputs vary together by the same delta; all other state/audio/time/coordinates remain fixed',
                      'This is a sufficient upper bound, not a minimum or typical response, or a response direction',
                      'Quantized uploads/casts, discontinuities and unsupported domains remain unresolved',
                      'No recurrent-state derivative, audio time-rate, native/storage rounding, affected screen area or mood claim']}
    from source_symbolic import refine_response
    refinement=None if result['maximum_absolute_control_change_per_audio_unit']==0 else refine_response(field,names,input_domains,report)
    if refinement is not None:
        result['symbolic_refinement']=refinement
        maximum=refinement['maximum_absolute_control_change_per_audio_unit']
        baseline=result['maximum_absolute_control_change_per_audio_unit']
        if maximum is not None and (baseline is None or maximum<baseline):
            result['baseline_absolute_control_change_per_audio_unit']=baseline
            result['maximum_absolute_control_change_per_audio_unit']=maximum
            result['nominal_continuity']='smooth_nominal'
            result['assumed_finite_input_names']=refinement['assumed_finite_input_names']
            result['held_fixed_input_names']=sorted(set(refinement['assumed_finite_input_names'])-names)
            result['declared_input_domains']={n:list(input_domains[n]) for n in refinement['assumed_finite_input_names']
                if input_domains and n in input_domains}
            result['unknown_reasons']=[]
    return result


def scalar_value_envelope(field,*,input_domains=None):
    """Bound scalar values under finite inputs/intermediates; infer no timing."""
    report=compound_time_bounds(field,_value_only=True,_input_domains=input_domains)
    result={'policy':'source-scalar-finite-input-envelope-v1',
        'nominal_value_range':report['nominal_value_range'],
        'assumed_finite_input_names':report.get('assumed_finite_input_names',[]),
        'declared_input_domains':report.get('declared_input_domains',{}),
        'unknown_reasons':report['unknown_reasons'],
        'uses_equation_execution':False,'uses_rendered_images':False,
        'native_numeric_certified':False,
        'conditions':['All listed scalar input values and relevant source intermediates are finite',
                      'Unbounded internal intervals represent arbitrary finite values, not supplied infinities or zero defaults',
                      'Conditional branch unions and bounded trig/clamps infer values only; timing, continuity and visible flashing remain unknown',
                      'Nominal envelope excludes target rounding/libm/overflow behavior; native conversion and appearance qualification stay separate']}

    from source_proofs import scalar_value_evidence
    refinement=scalar_value_evidence(field,input_domains=input_domains,candidate_bounds=report['nominal_value_range'],original_report=report)
    if refinement is not None:result['solver_refinement']=refinement
    return result


def original_scalar_domain_evidence(field,*,input_domains=None,max_nodes=512):
    """Retain finite original arguments before zero/cancel/clamp simplification.

    This optional proof owns its traversal cache: failure must not exhaust a
    caller's ordinary analysis or erase independent partial evidence.
    """
    from effect_families import _CACHE,_walk,_SemanticBudget
    result={'policy':'source-original-scalar-domain-envelope-v1','status':'unresolved',
        'checked_nodes':0,'unknown_reasons':[],'failure_evidence':None,
        'native_numeric_certified':False,'uses_equation_execution':False,'uses_rendered_images':False,
        'conditions':['Original scalar arguments retain finite declared-domain envelopes before algebraic pruning',
            'This is nominal domain evidence, not target rounding/evaluator optimizer or native conversion certification']}
    token=_CACHE.set({})
    try:
        for node,path in _walk(field,preserve_zero_products=True):
            result['checked_nodes']+=1
            if result['checked_nodes']>max_nodes:raise ValueError('original control domain traversal budget exceeded')
            if node.op in {'unknown','uninitialized','unresolved','sequence'} or node.op.startswith('loop_'):
                raise ValueError('original control has unsupported state/execution arguments')
            report=scalar_value_envelope(node,input_domains=input_domains)
            span=report['nominal_value_range']
            if span is None or not all(math.isfinite(v) for v in span):
                result['failure_evidence']={'source_graph_path':path,'operation':node.op,'value_envelope':report}
                raise ValueError('original control argument lacks a finite declared-domain envelope')
        result['status']='bounded'
    except (_SemanticBudget,ValueError,RecursionError,OverflowError,IndexError) as error:
        result['unknown_reasons']=[str(error)]
    finally:_CACHE.reset(token)
    return result
