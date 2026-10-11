"""Mirror operators in feedback and composite, and the symmetry they imply.

Two source constructions mirror the whole image:

- a feedback stretch with constant negative sign (``sx<0`` or ``sy<0``): the
  warp samples ``c + (u-c)/s``, so every feedback step reflects the retained
  image about the stretch centre (scaled by 1/|s|). Content of age k appears
  mirrored when k is odd. With decay d per step, ages 2k and 2k+1 carry weights
  d^(2k) and d^(2k+1), so every drawn pattern P is accompanied by its mirror
  M P at relative weight d;
- a composite echo with mirrored orientation (odd code flips left-right,
  code >= 2 flips top-bottom): the displayed image is (1-a) I + a M Z(I).

For an image A P + B M P with P uncorrelated with its mirror, the energy of
the mirror-symmetric part is (A+B)^2 / (2 (A^2+B^2)); the reported score
2AB/(A^2+B^2) maps that fraction from [1/2, 1] to [0, 1]. Feedback uses
(A, B) = (1, d), the echo (1-a, a). Echo zoom, per-step scale 1/|s|, a moving
stretch centre and later drawing reduce the exactness; the score is an upper
estimate of mirror symmetry, not a measured image statistic.
"""
import math

POLICY='source-mirror-symmetry-v1'
STATIC='/analysis/visual_description/static_behaviour'
AXES={'sx':('left-right','vertical line x=cx','cx'),'sy':('top-bottom','horizontal line y=cy','cy')}


def _score(a,b):
    total=a*a+b*b
    return 0. if total<=0 else 2*a*b/total


def _constant(span):
    if isinstance(span,list) and len(span)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in span) and span[0]==span[1]:
        return float(span[0])
    return None


def mirror_operators(facts):
    """Return the mirror record for a {fact path: value} map from an understanding summary."""
    out={'policy':POLICY,'operators':[],'flip_directions':[],'fold':1,'symmetry_score':0.,
         'conditions':['Stretch and echo controls are uniform constants; the image is otherwise uncorrelated with its mirror',
                       'Echo zoom, per-step scale, a varying centre and later drawing make the symmetry inexact; score is an upper estimate'],
         'uses_rendered_images':False}
    mesh=facts.get(STATIC+'/mesh_field') or {}
    controls=mesh.get('controls') or {}
    decay=(facts.get(STATIC+'/feedback_persistence') or {}).get('decay_gain')
    decay=float(decay) if type(decay) in (int,float) and math.isfinite(decay) else None
    for name,(direction,line,centre_name) in AXES.items():
        row=controls.get(name) or {}
        span=row.get('value_range')
        if row.get('status')!='described' or not row.get('uniform_across_mesh') or not isinstance(span,list) or len(span)!=2:continue
        if not all(type(v) in (int,float) for v in span) or not max(span)<0:continue
        centre=_constant((controls.get(centre_name) or {}).get('value_range'))
        score=_score(1.,max(0.,min(1.,decay))) if decay is not None else None
        out['operators'].append({'operator':'feedback_mirror','control':name,'flip':direction,'mirror_line':line,
            'mirror_centre':centre,'per_step_scale_range':sorted(1/abs(v) for v in span),'decay_gain':decay,
            'symmetry_score':score,'evidence':STATIC+'/mesh_field'})
    for path,value in facts.items():
        if not path.endswith('/legacy_response') or not isinstance(value,dict):continue
        if value.get('echo_selection')!='active or possible native echo':break
        ranges=value.get('native_control_ranges') or {}
        alpha=_constant(ranges.get('echo_alpha'));orient=_constant(ranges.get('echo_orient'))
        if orient is None or alpha is None or alpha<=0.001:break
        code=int(math.fmod(math.trunc(orient),4))
        flips=[d for flag,d in ((code%2!=0,'left-right'),(code>=2,'top-bottom')) if flag]
        alpha=min(1.,alpha)
        for flip in flips:
            out['operators'].append({'operator':'composite_echo_mirror','flip':flip,'mirror_line':'screen centre',
                'echo_alpha':alpha,'echo_zoom':_constant(ranges.get('echo_zoom')),'symmetry_score':_score(1-alpha,alpha),'evidence':path})
        break
    directions={}
    for row in out['operators']:
        if row['symmetry_score'] is not None:directions[row['flip']]=max(directions.get(row['flip'],0.),row['symmetry_score'])
    out['flip_directions']=sorted(directions)
    out['fold']=2**len(directions)
    out['symmetry_score']=max(directions.values(),default=0.)
    return out


def sentence(record):
    """Plain-language mirror sentence, or '' when no mirror operator is present."""
    rows=[r for r in record.get('operators',[]) if r.get('symmetry_score') is not None]
    if not rows:return ''
    parts=[]
    for row in rows:
        if row['operator']=='feedback_mirror':
            parts.append('every feedback step flips the image '+row['flip']+' ('+row['control']+'<0, about the '+row['mirror_line']+
                         '), so each drawn element is joined by its mirror image at %.0f%% of its weight'%(100*(row['decay_gain'] or 0)))
        else:
            parts.append('the composite echo adds a '+row['flip']+' mirrored copy at %.0f%% opacity'%(100*row['echo_alpha']))
    shape={2:'two-fold mirror symmetry',4:'four-fold (kaleidoscope-like) mirror symmetry'}.get(record.get('fold'),'')
    return 'Mirrors: '+'; '.join(parts)+('. Together: '+shape if shape else '')+' (upper estimate; zoom, scale and drawing make it inexact).'
