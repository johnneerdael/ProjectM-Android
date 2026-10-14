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

A custom composite shader can mirror as well (for example
``lerp(tex2D(sampler_main, uv), tex2D(sampler_main, (uv-.5)*float2(-1,1)+.5), .5)``).
Its exported program is evaluated on two independent noise canvases; the
difference of the two displays cancels everything the canvas does not drive
(procedural patterns, hue tints), and the correlation of that difference with
its own left-right and top-bottom flips is the mirror score. Heavily blurred noise
has few independent samples and correlates with any copy of itself by chance, so
the score must also exceed the correlation with shifted, unflipped copies (the
null for that preset) by a margin. Nonlinear transfers
after a mirrored blend keep the symmetry, so they are measured, not modelled.

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


COMPOSITE_PROGRAM='/analysis/visual_description/stage_programs'
# Canvas noise amplitudes: a high-gain composite (x50, then solarize) saturates bright noise, so faint
# canvases are tried as well; the strongest mirror correlation over the levels is kept.
_NOISE_LEVELS=(.005,.05,.25)
_MIN_SCORE=.5
_NULL_MARGIN=.4


def _correlation(a,b):
    a=a-a.mean();b=b-b.mean();norm=math.sqrt(float((a*a).sum())*float((b*b).sum()))
    return 0. if norm<=1e-12 else float((a*b).sum())/norm


def _composite_shader_mirrors(facts,size=(64,36)):
    stage=((facts.get(COMPOSITE_PROGRAM) or {}).get('stages') or {}).get('composite') or {}
    if stage.get('status')!='exported' or not isinstance(stage.get('program'),dict):return []
    import numpy as np
    from prediction_illustration import BANDS,_evaluate_stage
    width,height=size
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1)
    bands={band:1. for band in BANDS};rng=np.random.default_rng(20261014);best={}
    luma=np.array([.2126,.7152,.0722])
    for level in _NOISE_LEVELS:
        try:
            shown=[np.clip(np.nan_to_num(np.asarray(_evaluate_stage(stage['program'],(level*rng.random((height,width,3))).astype(np.float32),
                                                                     uv,5.,30.,bands,stage='composite'),np.float64)),0,1)[...,:3]@luma for _ in range(2)]
        except Exception:  # noqa: BLE001 - an unevaluable composite reports no measured mirror
            return []
        driven=shown[0]-shown[1]
        if float(driven.std())<1e-6:continue
        null=max([abs(_correlation(driven,np.roll(driven,k,axis=1))) for k in (width//4,width//2,3*width//4)]+
                 [abs(_correlation(driven,np.roll(driven,k,axis=0))) for k in (height//4,height//2)])
        for flip,mirrored in (('left-right',driven[:,::-1]),('top-bottom',driven[::-1])):
            score=_correlation(driven,mirrored)
            if score>=_MIN_SCORE and score-null>=_NULL_MARGIN:best[flip]=max(best.get(flip,0.),score)
    return [{'operator':'composite_shader_mirror','flip':flip,'mirror_line':'screen centre','symmetry_score':round(score,3),
             'measurement':'exported composite program on two %dx%d noise canvases (levels %s); canvas-driven display difference vs its flip, above the shifted-copy null by %.1f'%(width,height,list(_NOISE_LEVELS),_NULL_MARGIN),
             'evidence':COMPOSITE_PROGRAM+'/stages/composite'} for flip,score in sorted(best.items())]


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
        if row.get('status')!='described' or not isinstance(span,list) or len(span)!=2:continue
        if not all(type(v) in (int,float) for v in span) or not max(span)<0:continue
        # A stretch that is negative everywhere reflects every point; a spatially varying
        # magnitude distorts the reflected copy but keeps the flip direction.
        centre=_constant((controls.get(centre_name) or {}).get('value_range'))
        # Without a uniform decay fact the mirrored copy's weight is unknown; a prior of 0.9 per step
        # is used only for the score, and the record says so.
        score=_score(1.,max(0.,min(1.,decay if decay is not None else .9)))
        out['operators'].append({'operator':'feedback_mirror','control':name,'flip':direction,'mirror_line':line,
            'mirror_centre':centre,'per_step_scale_range':sorted(1/abs(v) for v in span),'decay_gain':decay,
            'uniform_stretch':bool(row.get('uniform_across_mesh')),
            'symmetry_score':score,'decay_assumed':decay is None,'evidence':STATIC+'/mesh_field'})
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
    out['operators'].extend(_composite_shader_mirrors(facts))
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
        elif row['operator']=='composite_shader_mirror':
            parts.append('the composite shader blends in a '+row['flip']+' mirrored copy of the image (mirror correlation %.2f)'%row['symmetry_score'])
        else:
            parts.append('the composite echo adds a '+row['flip']+' mirrored copy at %.0f%% opacity'%(100*row['echo_alpha']))
    shape={2:'two-fold mirror symmetry',4:'four-fold (kaleidoscope-like) mirror symmetry'}.get(record.get('fold'),'')
    return 'Mirrors: '+'; '.join(parts)+('. Together: '+shape if shape else '')+' (upper estimate; zoom, scale and drawing make it inexact).'
