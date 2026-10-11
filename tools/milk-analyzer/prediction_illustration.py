"""Draw an approximate prediction image from frozen understanding-SDK facts.

The input is a ``preset-understanding-v1`` summary only: no preset source,
equations, shaders or rendered frames are read. Supported now: affine polar
custom-wave recipes with their declared projection, raw affine colour labels,
and the qualified central radial feedback map combined with the conditional
RGBA8 decay orbit. Retained curve copies of age n are drawn at the closed-form
position F^n(r) about the screen centre, each channel at its own float32-profile
stored level after n decays.
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
    if not isinstance(persistence,dict) or persistence.get('status') not in {
            'conditional_quantized_decay_orbit','conditional_quantized_decay_orbit_profile_dependent'}:return None
    coefficients=radial['zoom_affine_coefficients_exact']
    return {'a':float(_exact(coefficients['a'])),'b':float(_exact(coefficients['b'])),
            'gain':persistence['decay_gain'],'aspect':radial['native_aspect_xy'],'viewport':radial['viewport']}


def _level_table(gain,steps):
    """Per-level float32-profile stored orbits: table[n][k] after n decays."""
    from source_feedback_persistence import _level_map
    mapping=np.array([level for level,_ in _level_map(gain,'float32')])
    table=[np.arange(256)]
    for _ in range(steps):table.append(mapping[table[-1]])
    return np.stack(table)


def _qualified_relation(facts,identity):
    for path,value in facts.items():
        if ('/curve_feedback_relation/components/' in path and isinstance(value,dict) and
                value.get('component_id')==identity and value.get('status')=='conditional_local_curve_feedback_relation'):
            return value
    return None


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
    if not isinstance(context.get('viewport'),list):raise ValueError('declared static-behaviour viewport is required')
    width,height=context['viewport']
    image=np.zeros((height,width,3),np.float32)
    used=[];limitations=[]
    feedback=_feedback(facts)
    if feedback is None:limitations.append('no qualified radial feedback plus decay orbit: only the fresh curve is drawn')
    table=None if feedback is None else _level_table(feedback['gain'],history_steps)
    for identity,recipe,projection in _curve_inputs(facts):
        count=recipe['sample_domain']['effective_samples']
        samples=np.linspace(0.0,1.0,count)
        R={key:float(_exact(v)) for key,v in recipe['radius_affine_coefficients_exact'].items()}
        P={key:float(_exact(v)) for key,v in recipe['phase_affine_coefficients_exact'].items()}
        if projection.get('viewport')!=[width,height]:
            limitations.append(identity+': projection viewport differs from the declared context; skipped');continue
        missing=[name for name in 'rgb' if (recipe.get('spatial_vertex_colour') or {}).get('channels',{}).get(name,{}).get('affine_coefficients_exact') is None]
        if missing:limitations.append(identity+': channels '+''.join(missing)+' lack affine coefficients and are drawn at full level')
        centre=np.array(projection['nominal_centre_pixels'],np.float64)
        scale=np.array(projection['nominal_source_to_pixel_scale_xy'],np.float64)
        trig=recipe.get('axis_trig_functions',['sin','cos'])
        functions={'sin':np.sin,'cos':np.cos}
        layered=feedback is not None and _qualified_relation(facts,identity) is not None
        if feedback is not None and not layered:
            limitations.append(identity+': no qualified central curve/feedback relation; retained layers omitted')
        spread=_spread(facts,identity) if layered else None
        if layered and spread is None:limitations.append(identity+': no bilinear spread record; layers drawn unblurred')
        ages=range(history_steps,-1,-1) if layered else [0]
        for age in ages:
            drawn=time-age/fps
            radius=R['constant']+R['sample']*samples+R['time']*drawn
            phase=P['constant']+P['sample']*samples+P['time']*drawn
            offset=np.stack([functions[trig[0]](phase)*radius,functions[trig[1]](phase)*radius],axis=-1)*scale
            colour=_colour(recipe,samples,drawn)
            points=centre+offset
            if age:
                # The qualified map is centred on the screen: native radius is the
                # aspect-corrected distance from the screen centre in NDC units.
                screen=np.array([width/2,height/2])
                ndc=(points-screen)/screen*np.array(feedback['aspect'])
                radius_native=np.hypot(ndc[:,0],ndc[:,1])
                moved=_retained_radius(radius_native,feedback,age)
                with np.errstate(divide='ignore',invalid='ignore'):
                    factor=np.where(radius_native>0,moved/radius_native,1.0)
                points=screen+(points-screen)*factor[:,None]
                # Each channel follows its own stored-level orbit from round(c*255).
                colour=table[age][np.clip(np.rint(colour*255),0,255).astype(int)]/255
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


def _mid(span):
    return None if not isinstance(span,list) or len(span)!=2 or None in span else (span[0]+span[1])/2


def _region_contains(box,point):
    for name,span in (box or {}).items():
        value={'x':point[0],'y':point[1]}.get(name)
        if value is None:return False
        low,high=span
        if (low is not None and value<low) or (high is not None and value>high):return False
    return True


def _displacement_terms(control):
    """Per-region callable pieces for one dx/dy control, using mid-range values."""
    regions=[]
    for region in control.get('regions') or []:
        pieces=[];ok=True
        for term in region.get('terms',[]):
            kind=term.get('kind')
            if kind=='constant':pieces.append(('const',term['value']))
            elif kind=='uniform':
                value=_mid(term.get('value_range'))
                if value is None:ok=False;break
                pieces.append(('const',value))
            elif kind=='coordinate_affine':
                if set(term['coefficients'])-{'x','y'}:ok=False;break
                pieces.append(('affine',term['constant'],term['coefficients']))
            elif kind=='spatial_oscillator':
                osc=term['oscillator'];amp=_mid(term.get('amplitude_range'))
                if amp is None or set(osc['coordinate_coefficients'])-{'x','y'}:ok=False;break
                pieces.append(('osc',amp,osc))
            else:ok=False;break
        if not ok:return None
        regions.append((region.get('box') or {},pieces))
    return regions


def _evaluate(regions,point,time):
    for box,pieces in regions:
        if not _region_contains(box,point):continue
        total=0.0
        for piece in pieces:
            if piece[0]=='const':total+=piece[1]
            elif piece[0]=='affine':total+=piece[1]+sum(c*{'x':point[0],'y':point[1]}[k] for k,c in piece[2].items())
            else:
                amp,osc=piece[1],piece[2]
                arg=(sum(c*{'x':point[0],'y':point[1]}[k] for k,c in osc['coordinate_coefficients'].items())+
                     osc['time_coefficient_radians_per_second']*time+osc['phase_radians'])
                total+=amp*(math.sin(arg) if osc['function']=='sin' else math.cos(arg))
        return total
    return 0.0


def _field_map(mesh):
    """Forward per-step map from mesh-field facts, or None when not fully described."""
    controls=(mesh or {}).get('controls') or {}
    if not controls or any(controls.get(name,{}).get('status')!='described' for name in ('zoom','dx','dy','rot','cx','cy')):
        return None
    zoom=controls['zoom']
    if not zoom.get('uniform_across_mesh'):return None
    z=_mid(zoom.get('value_range'));rot=controls['rot'].get('value_range')
    if z is None or z<=0 or rot is None or any(abs(v)>1e-12 for v in rot):return None
    centre=(_mid(controls['cx'].get('value_range')),_mid(controls['cy'].get('value_range')))
    dx,dy=_displacement_terms(controls['dx']),_displacement_terms(controls['dy'])
    if None in centre or dx is None or dy is None:return None
    zoom_gain=min(1.0,z)
    gains=[]
    for control in ('dx','dy'):
        for region in controls[control].get('regions') or []:
            gain=(region.get('axis_motion') or {}).get('thin_line_peak_gain_per_step')
            if type(gain) in (int,float) and gain<1:gains.append((region.get('box') or {},gain))
    def gain(point):
        value=zoom_gain
        for box,factor in gains:
            if _region_contains(box,point):value*=factor
        return value
    def step(point,time):
        # Backward sampling u=c+(p-c)/z-d(p); solve the forward position p.
        p=point
        for _ in range(4):
            d=(_evaluate(dx,p,time),_evaluate(dy,p,time))
            p=(centre[0]+z*(point[0]+d[0]-centre[0]),centre[1]+z*(point[1]+d[1]-centre[1]))
        return p
    step.gain=gain
    return step


def _builtin_wave_paths(facts,aspect):
    """Built-in waveform centre-lines in EEL coordinates, without audio wiggle."""
    paths=[];limitations=[]
    for path,value in facts.items():
        if not path.endswith('/waveform_recipe') or not isinstance(value,dict):continue
        form=value.get('form_name')
        if form=='two_channel_parallel_traces' and value.get('line_angle_rad') is not None:
            angle=value['line_angle_rad'];offset=value.get('separation_normal_offset') or 0.0
            direction=(math.cos(angle),math.sin(angle));normal=(-direction[1],direction[0])
            for sign in (1,-1):
                points=[]
                for t in np.linspace(-1.5,1.5,240):
                    ndc=(direction[0]*t+normal[0]*sign*offset,direction[1]*t+normal[1]*sign*offset)
                    points.append((.5+.5*ndc[0]*aspect[0],.5-.5*ndc[1]*aspect[1]))
                paths.append((path,points))
        else:limitations.append(path+': built-in waveform form '+str(form)+' is not illustrated')
    return paths,limitations


def _wave_colour(facts,path):
    material=facts.get(path.rsplit('/',1)[0]+'/wave_material')
    if not isinstance(material,dict):return (1.0,1.0,1.0),'material absent; white'
    if material.get('constant_vertex_rgb'):return tuple(material['constant_vertex_rgb'][:3]),'constant'
    mids=[_mid(span) for span in material.get('rgb_component_envelopes') or []]
    if len(mids)!=3 or None in mids:return (1.0,1.0,1.0),'colour envelope absent; white'
    if material.get('normalization_enabled') and max(mids)>0:mids=[v/max(mids) for v in mids]
    return tuple(mids),'time-varying colour drawn at envelope midpoints'


def _composite(image,facts):
    for path,value in facts.items():
        if not path.endswith('/legacy_response') or not isinstance(value,dict):continue
        ranges=value.get('native_control_ranges') or {}
        gamma=_mid(ranges.get('gamma'));alpha=_mid(ranges.get('echo_alpha'));zoom=_mid(ranges.get('echo_zoom'))
        orient=_mid(ranges.get('echo_orient'))
        if value.get('echo_selection')=='active or possible native echo' and alpha and zoom:
            height,width=image.shape[:2]
            matrix=np.array([[zoom,0,(1-zoom)*width/2],[0,zoom,(1-zoom)*height/2]],np.float32)
            echo=cv2.warpAffine(image,matrix,(width,height),flags=cv2.INTER_LINEAR)
            code=int(math.fmod(math.trunc(orient or 0),4))
            if code%2:echo=echo[:,::-1]
            if code>=2:echo=echo[::-1]
            image=(1-alpha)*image+alpha*echo
        if gamma:image=image*gamma
        return np.clip(image,0,1),'composite echo/gamma applied'
    return image,None


def illustrate_field(summary,*,time,fps,history_steps):
    """Built-in waves advected through the decomposed per-pixel field, then composite."""
    facts=_facts(summary)
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    if not isinstance(context.get('viewport'),list):raise ValueError('declared static-behaviour viewport is required')
    width,height=context['viewport']
    aspect=(1.0,height/width) if width>=height else (width/height,1.0)
    image=np.zeros((height,width,3),np.float32);limitations=[]
    step=_field_map(facts.get('/analysis/visual_description/static_behaviour/mesh_field'))
    persistence=facts.get('/analysis/visual_description/static_behaviour/feedback_persistence')
    if step is None:limitations.append('per-pixel field not fully described: retained layers omitted')
    table=None
    if step is not None and isinstance(persistence,dict) and persistence.get('decay_gain'):
        table=_level_table(persistence['decay_gain'],history_steps)
    elif step is not None:limitations.append('no decay orbit: retained layers omitted');step=None
    paths,wave_limits=_builtin_wave_paths(facts,aspect);limitations+=wave_limits
    def to_pixels(point):
        return ((point[0]-(.5-.5*aspect[0]))/aspect[0]*width,(point[1]-(.5-.5*aspect[1]))/aspect[1]*height)
    for path,points in paths:
        colour,note=_wave_colour(facts,path);limitations.append(path+': '+note)
        ages=range(history_steps,-1,-1) if step is not None else [0]
        for age in ages:
            moved=list(points);attenuation=np.ones(len(points))
            for k in range(age):
                drawn_time=time-(age-k)/fps
                attenuation*=np.array([step.gain(point) for point in moved])
                moved=[step(point,drawn_time) for point in moved]
            level=np.array(colour) if age==0 else table[age][np.clip(np.rint(np.array(colour)*255),0,255).astype(int)]/255
            pixels=[to_pixels(point) for point in moved]
            for index,(a,b) in enumerate(zip(pixels,pixels[1:])):
                if all(map(math.isfinite,a+b)):
                    shade=tuple(float(v) for v in level*attenuation[index])
                    cv2.line(image,tuple(int(round(v)) for v in a),tuple(int(round(v)) for v in b),shade,1,cv2.LINE_AA)
    image,note=_composite(image,facts)
    if note:limitations.append(note)
    return image,[path for path,_ in paths],limitations


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
    if not used:
        image,used,limitations=illustrate_field(summary,time=args.time,fps=fps,history_steps=args.history_steps)
    rgb=(np.clip(image,0,1)*255+.5).astype(np.uint8)
    cv2.imwrite(str(args.output),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    identity={'policy':POLICY,'summary_sha256':hashlib.sha256(data).hexdigest(),
        'illustrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'image_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'declared_time_seconds':args.time,
        'history_steps':args.history_steps,'drawn_components':used,'limitations':limitations+[
            'Illustration of frozen source facts; 1px antialiased layers blurred by the uniform-offset spread reference, newer layers over older ones',
            'Not a renderer: smoothing, filtering, exact raster, waveform/audio-driven elements, additive waves, wave alpha and composite effects are omitted',
            'Layers older than history_steps, including permanent floor residue, are omitted'],
        'uses_rendered_images':False,'uses_equation_execution':False,'reads_preset_source':False}
    args.output.with_suffix('.json').write_text(json.dumps(identity,indent=2)+'\n')
    print(json.dumps(identity))


if __name__=='__main__':
    main()
