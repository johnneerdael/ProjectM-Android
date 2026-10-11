"""Standard-library evaluation of exported time-only source expressions.

Exports serialise equation graphs as {'root', 'nodes'}. When a graph depends on
source time alone (constants and ``time``), it is a closed-form function that
can be sampled at declared times without executing preset frames. Arithmetic is
nominal binary64 with EEL division semantics (x/0 = 0); native float32 rounding
is not reproduced. Hue bands mirror source_colour_character.HUE_BANDS.
"""
import colorsys
import math

HUE_BANDS={'red':((0,15),(345,360)),'orange':((15,45),),'yellow':((45,75),),
           'green':((75,165),),'cyan':((165,195),),'blue':((195,255),),
           'purple':((255,285),),'pink':((285,345),)}
SATURATION_FLOOR=.08
VALUE_FLOOR=.02
UNARY={'sin':math.sin,'cos':math.cos,'tan':math.tan,'abs':abs,'negate':lambda v:-v,
       'sqr':lambda v:v*v,'floor':math.floor,'ceil':math.ceil,'int':lambda v:float(math.trunc(v)),
       'sign':lambda v:(v>0)-(v<0),'exp':math.exp,'atan':math.atan}


def time_only(expression):
    """True when every input of the serialised graph is ``time``."""
    if not isinstance(expression,dict) or not isinstance(expression.get('nodes'),list):return False
    for node in expression['nodes']:
        if node.get('op')=='input' and node.get('detail',{}).get('name')!='time':return False
        if node.get('op') not in {'constant','input','add','subtract','multiply','divide','eel_divide','min','max',
                                  'pow','sqrt','less','greater','less_equal','greater_equal','select',*UNARY}:return False
    return True


def evaluate(expression,time):
    """Evaluate a time-only serialised graph at one declared source time."""
    if not time_only(expression):raise ValueError('expression is not a supported time-only graph')
    nodes=expression['nodes'];memo={}
    def value(index):
        if index in memo:return memo[index]
        node=nodes[index];op=node['op'];args=[value(a) for a in node['args']]
        if op=='constant':result=float(node['detail']['value'])
        elif op=='input':result=float(time)
        elif op=='add':result=args[0]+args[1]
        elif op=='subtract':result=args[0]-args[1]
        elif op=='multiply':result=args[0]*args[1]
        elif op in ('divide','eel_divide'):result=0.0 if args[1]==0 else args[0]/args[1]
        elif op=='min':result=min(args)
        elif op=='max':result=max(args)
        elif op=='pow':result=math.pow(args[0],args[1])
        elif op=='sqrt':result=math.sqrt(abs(args[0]))
        elif op in ('less','greater','less_equal','greater_equal'):
            result=float({'less':args[0]<args[1],'greater':args[0]>args[1],
                          'less_equal':args[0]<=args[1],'greater_equal':args[0]>=args[1]}[op])
        elif op=='select':result=args[1] if args[0]!=0 else args[2]
        else:result=float(UNARY[op](args[0]))
        if not math.isfinite(result):raise ValueError('nonfinite time-expression value')
        memo[index]=result
        return result
    return value(expression['root'])


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
