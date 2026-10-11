"""Draw an approximate prediction image from frozen understanding-SDK facts.

The input is a ``preset-understanding-v1`` summary only: no preset source,
equations, shaders or rendered frames are read. Supported now: affine polar
custom-wave recipes with their declared projection, raw affine colour labels,
and the qualified central radial feedback map combined with the conditional
RGBA8 decay orbit. Retained curve copies of age n are drawn at the closed-form
position F^n(r) and the stored level orbit[n]/255; levels at the floor persist.
The image illustrates the source interpretation for human comparison; it is no
renderer, no capture and never a classification input.
"""
import argparse,hashlib,json,math
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

POLICY='sdk-prediction-illustration-v1'


def _exact(value):
    return Fraction(int(value['numerator']),int(value['denominator']))


def _facts(summary):
    rows={}
    for group in summary['facts'].values():
        for fact in group:rows[fact['path']]=fact['value']
    return rows


def _curve_inputs(facts):
    """Pair each supported curve recipe with its projection component."""
    projections={}
    for path,value in facts.items():
        if '/curve_projection/components/' in path and isinstance(value,dict) and \
                value.get('status') in {'conditional_projected_coordinates','partial_projection'}:
            projections[value.get('component_id')]=value
    curves=[]
    for path,value in facts.items():
        if not path.endswith('/parameters/source_curve_recipe') or value.get('policy')!='source-parametric-wave-v1':continue
        element=facts.get(path.rsplit('/parameters/',1)[0]+'/id')
        projection=projections.get(element)
        if projection is None:continue
        curves.append((element,value,projection))
    return curves


def _colour(recipe,samples,time):
    """Raw affine labels with the native signed modulo, then [0,1] clamp."""
    material=recipe.get('spatial_vertex_colour') or {}
    channels=material.get('channels') or {}
    period=material.get('native_colour_modulo_period') or 1.0
    rgb=[]
    for name in 'rgb':
        row=channels.get(name) or {}
        coefficients=row.get('affine_coefficients_exact')
        if coefficients is None:
            rgb.append(np.ones_like(samples));continue
        c={key:float(_exact(coefficients[key])) for key in ('constant','sample','time')}
        raw=c['constant']+c['sample']*samples+c['time']*time
        rgb.append(np.clip(np.fmod(raw,period),0,1))
    return np.stack(rgb,axis=-1)


def _feedback(facts):
    radial=facts.get('/analysis/visual_description/static_behaviour/affine_radial_feedback')
    persistence=facts.get('/analysis/visual_description/static_behaviour/feedback_persistence')
    if not isinstance(radial,dict) or radial.get('status')!='conditional_affine_radial_sampler':return None
    if not isinstance(persistence,dict) or persistence.get('status')!='conditional_quantized_decay_orbit':return None
    coefficients=radial['zoom_affine_coefficients_exact']
    return {'a':float(_exact(coefficients['a'])),'b':float(_exact(coefficients['b'])),
            'orbit':persistence['level_orbit_from_full'],'floor':persistence['floor_level_from_full'],
            'aspect':radial['native_aspect_xy'],'viewport':radial['viewport']}


def _retained_radius(radius,feedback,steps):
    """Closed-form inverse feature map F^n(r)=a^n r/(1-b r S_n)."""
    a,b=feedback['a'],feedback['b']
    total=steps if a==1 else (a**steps-1)/(a-1)
    denominator=1-b*radius*total
    with np.errstate(divide='ignore',invalid='ignore'):
        return np.where(denominator>0,a**steps*radius/denominator,np.inf)


def _spread(facts,identity):
    for path,value in facts.items():
        if '/curve_feedback_relation/components/' in path and isinstance(value,dict) and value.get('component_id')==identity:
            spread=value.get('bilinear_diffusion_spread')
            if isinstance(spread,dict) and spread.get('status')=='conditional_bilinear_spread_bound':return spread
    return None


def _spread_sigma(spread,age):
    """Uniform-offset reference spread sqrt(age*v), not the conservative ceiling."""
    if spread is None or age<=0:return 0.0
    return math.sqrt(age*spread['per_step_variance_uniform_offset_reference_texels2'])


def illustrate(summary,*,time,fps,history_steps):
    facts=_facts(summary)
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    width,height=context.get('viewport',[480,270])
    image=np.zeros((height,width,3),np.float32)
    used=[];limitations=[]
    feedback=_feedback(facts)
    if feedback is None:limitations.append('no qualified radial feedback plus decay orbit: only the fresh curve is drawn')
    for identity,recipe,projection in _curve_inputs(facts):
        count=recipe['sample_domain']['effective_samples']
        samples=np.linspace(0.0,1.0,count)
        R={key:float(_exact(v)) for key,v in recipe['radius_affine_coefficients_exact'].items()}
        P={key:float(_exact(v)) for key,v in recipe['phase_affine_coefficients_exact'].items()}
        centre=np.array(projection['nominal_centre_pixels'],np.float64)
        scale=np.array(projection['nominal_source_to_pixel_scale_xy'],np.float64)
        trig=recipe.get('axis_trig_functions',['sin','cos'])
        functions={'sin':np.sin,'cos':np.cos}
        spread=_spread(facts,identity) if feedback is not None else None
        if feedback is not None and spread is None:limitations.append(identity+': no bilinear spread record; layers drawn unblurred')
        ages=range(history_steps,-1,-1) if feedback is not None else [0]
        for age in ages:
            drawn=time-age/fps
            radius=R['constant']+R['sample']*samples+R['time']*drawn
            phase=P['constant']+P['sample']*samples+P['time']*drawn
            offset=np.stack([functions[trig[0]](phase)*radius,functions[trig[1]](phase)*radius],axis=-1)*scale
            colour=_colour(recipe,samples,drawn)
            if age:
                # Move the drawn points with the retained-feature map in native
                # radius units (pixels / half the long viewport side).
                half=max(width,height)/2
                pixel_radius=np.hypot(offset[:,0],offset[:,1])
                moved=_retained_radius(pixel_radius/half,feedback,age)*half
                with np.errstate(divide='ignore',invalid='ignore'):
                    factor=np.where(pixel_radius>0,moved/pixel_radius,1.0)
                offset=offset*factor[:,None]
                orbit=feedback['orbit']
                level=orbit[age] if age<len(orbit) else feedback['floor']
                colour=colour*(level/255)
            points=centre+offset
            layer=np.zeros_like(image);mask=np.zeros(image.shape[:2],np.float32)
            for index in range(count-1):
                if not (np.all(np.isfinite(points[index:index+2]))):continue
                start=tuple(int(round(v)) for v in points[index]);end=tuple(int(round(v)) for v in points[index+1])
                cv2.line(layer,start,end,tuple(float(v) for v in colour[index]),1,cv2.LINE_AA)
                cv2.line(mask,start,end,1.0,1,cv2.LINE_AA)
            sigma=_spread_sigma(spread,age)
            if sigma>0:
                layer=cv2.GaussianBlur(layer,(0,0),sigma);mask=cv2.GaussianBlur(mask,(0,0),sigma)
            # Premultiplied "over": the newer layer replaces older stored levels.
            with np.errstate(divide='ignore',invalid='ignore'):
                coverage=np.clip(mask,0,1)[...,None]
                colour_layer=np.where(mask[...,None]>1e-6,layer/np.maximum(mask[...,None],1e-6),0)
            image=image*(1-coverage)+colour_layer*coverage
        used.append(identity)
    return image,used,limitations


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('summary',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--time',type=float,default=5.0,help='declared source time in seconds')
    parser.add_argument('--history-steps',type=int,default=150)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('output exists; frozen predictions are never overwritten')
    data=args.summary.read_bytes();summary=json.loads(data)
    if summary.get('policy')!='preset-understanding-v1':parser.error('preset-understanding-v1 summary required')
    fps=float(_facts(summary).get('/analysis/visual_description/static_behaviour/context',{}).get('feedback_fps',30))
    image,used,limitations=illustrate(summary,time=args.time,fps=fps,history_steps=args.history_steps)
    rgb=(np.clip(image,0,1)*255+.5).astype(np.uint8)
    cv2.imwrite(str(args.output),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    identity={'policy':POLICY,'summary_sha256':hashlib.sha256(data).hexdigest(),
        'illustrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'image_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'declared_time_seconds':args.time,
        'history_steps':args.history_steps,'drawn_components':used,'limitations':limitations+[
            'Illustration of frozen source facts; 1px antialiased layers blurred by the uniform-offset spread reference, newer layers over older ones',
            'Not a renderer: smoothing, filtering, exact raster, waveform/audio-driven elements and composite effects are omitted'],
        'uses_rendered_images':False,'uses_equation_execution':False,'reads_preset_source':False}
    args.output.with_suffix('.json').write_text(json.dumps(identity,indent=2)+'\n')
    print(json.dumps(identity))


if __name__=='__main__':
    main()
