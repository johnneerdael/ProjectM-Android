"""Standard-library evaluation of exported time-only source expressions.

Exports serialise equation graphs as {'root', 'nodes'}. When a graph depends on
source time alone (constants and ``time``), it is a closed-form function that
can be sampled at declared times without executing preset frames. Arithmetic is
nominal binary64 with projectm-eval semantics for EEL graphs: int is floor,
division by |d|<1e-5 is 0, sqrt takes |x|, pow returns 0 for NaN results and for
a near-zero base with a negative exponent, ``%`` (remainder) is the C remainder
of truncated integers with divisor 0 giving 0, and EEL equal is |a-b|<1e-5.
``evaluate_inputs`` evaluates graphs over other declared inputs (for example
per-point ``sample``). Native float32 rounding is not reproduced. Hue bands mirror source_colour_character.HUE_BANDS.
"""
import colorsys
import math

HUE_BANDS={'red':((0,15),(345,360)),'orange':((15,45),),'yellow':((45,75),),
           'green':((75,165),),'cyan':((165,195),),'blue':((195,255),),
           'purple':((255,285),),'pink':((285,345),)}
SATURATION_FLOOR=.08
VALUE_FLOOR=.02
UNARY={'sin':math.sin,'cos':math.cos,'tan':math.tan,'abs':abs,'negate':lambda v:-v,
       'sqr':lambda v:v*v,'floor':math.floor,'ceil':math.ceil,'int':math.floor,
       'sign':lambda v:(v>0)-(v<0),'exp':math.exp,'atan':math.atan}


SUPPORTED={'constant','input','add','subtract','multiply','divide','eel_divide','min','max','pow','sqrt',
           'less','greater','less_equal','greater_equal','select','remainder','eel_equal',*UNARY}


def input_names(expression):
    """Input names of a supported serialised graph, or None when an operation is unsupported."""
    if not isinstance(expression,dict) or not isinstance(expression.get('nodes'),list):return None
    names=set()
    for node in expression['nodes']:
        if node.get('op') not in SUPPORTED:return None
        if node.get('op')=='input':names.add(node.get('detail',{}).get('name'))
    return names


def time_only(expression):
    """True when every input of the serialised graph is ``time``."""
    names=input_names(expression)
    return names is not None and names<={'time'}


def _remainder(a,b):
    # projectm-eval _mod: C remainder of truncated integers; divisor 0 gives 0.
    divisor=math.trunc(b)
    if divisor==0:return 0.0
    dividend=math.trunc(a)
    return float(int(math.fmod(dividend,divisor)))


def evaluate_inputs(expression,inputs):
    """Evaluate a supported serialised graph with every input named in ``inputs``."""
    names=input_names(expression)
    if names is None:raise ValueError('expression contains an unsupported operation')
    missing=names-set(inputs)
    if missing:raise ValueError('expression inputs not supplied: '+', '.join(sorted(map(str,missing))))
    nodes=expression['nodes'];memo={}
    def value(index):
        if index in memo:return memo[index]
        node=nodes[index];op=node['op'];args=[value(a) for a in node['args']]
        if op=='constant':result=float(node['detail']['value'])
        elif op=='input':result=float(inputs[node['detail']['name']])
        elif op=='add':result=args[0]+args[1]
        elif op=='subtract':result=args[0]-args[1]
        elif op=='multiply':result=args[0]*args[1]
        elif op=='eel_divide':result=0.0 if abs(args[1])<1e-5 else args[0]/args[1]
        elif op=='divide':result=0.0 if args[1]==0 else args[0]/args[1]
        elif op=='remainder':result=_remainder(args[0],args[1])
        elif op=='eel_equal':result=float(abs(args[0]-args[1])<1e-5)
        elif op=='min':result=min(args)
        elif op=='max':result=max(args)
        elif op=='pow':
            if abs(args[0])<1e-5 and args[1]<0:result=0.0
            else:
                try:result=math.pow(args[0],args[1])
                except ValueError:result=0.0
        elif op=='sqrt':result=math.sqrt(abs(args[0]))
        elif op in ('less','greater','less_equal','greater_equal'):
            result=float({'less':args[0]<args[1],'greater':args[0]>args[1],
                          'less_equal':args[0]<=args[1],'greater_equal':args[0]>=args[1]}[op])
        elif op=='select':result=args[1] if args[0]!=0 else args[2]
        else:result=float(UNARY[op](args[0]))
        if not math.isfinite(result):raise ValueError('nonfinite expression value')
        memo[index]=result
        return result
    try:return value(expression['root'])
    except (OverflowError,ZeroDivisionError) as error:raise ValueError('expression outside finite domain: '+str(error)) from error


def evaluate(expression,time):
    """Evaluate a time-only serialised graph at one declared source time."""
    if not time_only(expression):raise ValueError('expression is not a supported time-only graph')
    try:return evaluate_inputs(expression,{'time':time})
    except ValueError as error:raise ValueError(str(error).replace('expression','time-expression',1)) from error


def hue_family(rgb):
    hue,saturation,value=colorsys.rgb_to_hsv(*[min(1.,max(0.,c)) for c in rgb])
    if value<VALUE_FLOOR or saturation<SATURATION_FLOOR:return 'grayscale'
    degrees=hue*360
    return next(name for name,bands in HUE_BANDS.items() if any(a<=degrees<b for a,b in bands))


def wave_colour(channels,time,normalize):
    """Built-in wave RGB at a declared time: clamp to [0,1], then optional max-normalisation above 0.01."""
    rgb=[]
    for name in ('wave_r','wave_g','wave_b'):
        curve=(channels.get(name) or {}).get('raw_time_curve') or {}
        expression=(channels.get(name) or {}).get('time_only_expression')
        if expression is not None:rgb.append(evaluate(expression,time))
        elif curve.get('curve_kind')=='constant' and type(curve.get('constant_value')) in (int,float):rgb.append(curve['constant_value'])
        else:raise ValueError(name+' is not a closed-form function of time')
    rgb=[min(1.,max(0.,c)) for c in rgb]
    peak=max(rgb)
    if normalize and peak>.01:rgb=[c/peak for c in rgb]
    return rgb
