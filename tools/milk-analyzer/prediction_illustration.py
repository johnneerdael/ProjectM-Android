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


def _terms_field(terms,x,y,time):
    """Vectorised sum of decomposed control terms over per-pixel coordinates."""
    total=np.zeros_like(x)
    for term in terms:
        kind=term.get('kind')
        if kind=='constant':total+=term['value']
        elif kind=='uniform':
            value=_mid(term.get('value_range'))
            if value is None:raise ValueError('unbounded uniform term')
            total+=value
        elif kind=='coordinate_affine':
            coefficients=term['coefficients']
            if set(coefficients)-{'x','y','rad'}:raise ValueError('angle/time affine term not illustrated')
            # Mesh-field convention: x/y measure the long side; rad=1 is half the long side.
            total+=term['constant']+coefficients.get('x',0)*x+coefficients.get('y',0)*y+coefficients.get('rad',0)*2*np.hypot(x-.5,y-.5)
        elif kind=='spatial_oscillator':
            osc=term['oscillator'];amplitude=_mid(term.get('amplitude_range'))
            if amplitude is None or set(osc['coordinate_coefficients'])-{'x','y','rad'}:raise ValueError('oscillator not illustrated')
            argument=(osc['coordinate_coefficients'].get('x',0)*x+osc['coordinate_coefficients'].get('y',0)*y+
                      osc['coordinate_coefficients'].get('rad',0)*2*np.hypot(x-.5,y-.5)+
                      osc['time_coefficient_radians_per_second']*time+osc['phase_radians'])
            total+=amplitude*(np.sin(argument) if osc['function']=='sin' else np.cos(argument))
        elif kind=='coordinate_gated':
            coordinate={'x':x,'y':y}.get(term['coordinate'])
            if coordinate is None:raise ValueError('gate on radius/angle not illustrated')
            for branch in term['branches']:
                low,high=branch['interval']
                mask=np.ones_like(x,dtype=bool)
                if low is not None:mask&=coordinate>low
                if high is not None:mask&=coordinate<high
                total+=np.where(mask,_terms_field(branch['terms'],x,y,time),0.0)
        else:raise ValueError(str(kind)+' term not illustrated')
    return total


def _backward_map(mesh,width,height):
    """Closure computing per-pixel source coordinates from mesh-field facts."""
    controls=(mesh or {}).get('controls') or {}
    names=('zoom','zoomexp','rot','warp','cx','cy','dx','dy','sx','sy')
    if any(controls.get(name,{}).get('status')!='described' for name in names):return None
    long=max(width,height)
    columns,rows=np.meshgrid(np.arange(width)+.5,np.arange(height)+.5)
    x=.5+(columns-width/2)/long;y=.5+(rows-height/2)/long
    rad=2*np.hypot(x-.5,y-.5)
    def sample(time):
        values={name:_terms_field(controls[name]['terms'] or [],x,y,time) for name in names}
        if np.any(values['zoom']<=0) or np.any(values['zoomexp']<=0):raise ValueError('nonpositive zoom/zoomexp not illustrated')
        # The legacy procedural warp (amplitude 0.0035*warp) is omitted; see limitations.
        zoom=np.power(values['zoom'],np.power(values['zoomexp'],2*rad-1))
        u=.5+(x-.5)/zoom;v=.5+(y-.5)/zoom
        u=values['cx']+(u-values['cx'])/values['sx'];v=values['cy']+(v-values['cy'])/values['sy']
        cos,sin=np.cos(values['rot']),np.sin(values['rot'])
        du,dv=u-values['cx'],v-values['cy']
        # Engine formula; per-pixel u/v share the flipped main-texture frame.
        u=du*cos-dv*sin+values['cx'];v=du*sin+dv*cos+values['cy']
        u=u-values['dx'];v=v-values['dy']
        return ((u-.5)*long+width/2-.5).astype(np.float32),((v-.5)*long+height/2-.5).astype(np.float32)
    return sample


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


def _wave_alpha(facts,path,limitations):
    """(alpha, additive) from the wave material alpha recipe; None when the native draw gate skips it."""
    material=facts.get(path.rsplit('/',1)[0]+'/wave_material')
    if not isinstance(material,dict):return 1.0,False
    envelope=(material.get('alpha_recipe') or {}).get('final_alpha_envelope')
    gate=(material.get('native_draw_gate') or {}).get('threshold')
    additive='additive' in str(material.get('blend_mode'))
    if not isinstance(envelope,list) or len(envelope)!=2 or None in envelope:
        limitations.append(path+': alpha unresolved; drawn at alpha 1');return 1.0,additive
    if type(gate) in (int,float) and envelope[1]<gate:
        limitations.append(path+': final alpha below the native draw gate; not drawn');return None,additive
    return min(1.,max(0.,(envelope[0]+envelope[1])/2)),additive


def _wave_colour_at(facts,path,time):
    from time_expression import wave_colour
    material=facts.get(path.rsplit('/',1)[0]+'/wave_material')
    if not isinstance(material,dict):return None
    try:return wave_colour(material.get('channels') or {},time,bool(material.get('normalization_enabled')))
    except (ValueError,KeyError,TypeError):return None


def _palette_display(image,facts,limitations):
    """Approximate display through a composite scalar palette anchored at the flat-field state."""
    palette=facts.get('/analysis/visual_description/nonlinear_texture_colour_bounds/stages/composite/scalar_palette')
    flat=facts.get('/analysis/visual_description/nonlinear_texture_colour_bounds/flat_field')
    if not isinstance(palette,dict) or not palette.get('samples') or not isinstance(flat,dict):return None
    background=flat.get('composite_rgb_at_state');state=flat.get('state_rgb')
    if not isinstance(background,list) or not isinstance(state,list):return None
    samples=palette['samples']
    anchor=min(samples,key=lambda x:sum((a-b)**2 for a,b in zip(x['clamped_rgb'],background)))['scalar']
    black=palette.get('black_content_scalar')
    target=(black[0]+black[1])/2 if isinstance(black,list) else samples[0]['scalar']
    scalars=np.array([x['scalar'] for x in samples]);colours=np.array([x['clamped_rgb'] for x in samples],np.float32)
    deviation=np.clip(np.abs(image-np.array(state,np.float32)).max(axis=-1),0,1)
    # Content departing from the flat state moves along the palette toward black content.
    s=anchor+(target-anchor)*deviation
    order=np.argsort(scalars)
    ramp=np.stack([np.interp(s,scalars[order],colours[order][:,c]) for c in range(3)],axis=-1).astype(np.float32)
    # Flat regions (deviation 0) show the exact flat-field display colour.
    weight=deviation[...,None]
    display=(1-weight)*np.array(background,np.float32)+weight*ramp
    limitations.append('display via the composite scalar palette: flat regions use the flat-field colour; departures from the flat state move along the palette toward the black-content colour (approximation)')
    return display


def _composite(image,facts):
    for path,value in facts.items():
        if not path.endswith('/legacy_response') or not isinstance(value,dict):continue
        ranges=value.get('native_control_ranges') or {}
        alpha=_mid(ranges.get('echo_alpha'));zoom=_mid(ranges.get('echo_zoom'));orient=_mid(ranges.get('echo_orient'))
        weight=value.get('gamma_absolute_weight_sum_upper')
        tint=value.get('tint_amount')
        if type(tint) in (int,float) and tint>.001 and value.get('_illustration_time') is not None:
            from legacy_composite import corner_shades
            # Random per-preset hue offsets are unknown: illustrate with zero offsets (hue placement is not a prediction).
            shades=corner_shades(value['_illustration_time'],[0.,0.,0.,0.],shader_amount=tint)
            height,width=image.shape[:2]
            fx=np.linspace(0,1,width)[None,:,None];fy=np.linspace(0,1,height)[:,None,None]
            top=shades[0]*(1-fx)+shades[1]*fx;bottom=shades[2]*(1-fx)+shades[3]*fx
            image=image*(top*(1-fy)+bottom*fy).astype(np.float32)
        if value.get('echo_selection')=='active or possible native echo' and alpha and zoom:
            height,width=image.shape[:2]
            matrix=np.array([[zoom,0,(1-zoom)*width/2],[0,zoom,(1-zoom)*height/2]],np.float32)
            echo=cv2.warpAffine(image,matrix,(width,height),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
            code=int(math.fmod(math.trunc(orient or 0),4))
            if code%2:echo=echo[:,::-1]
            if code>=2:echo=echo[::-1]
            image=(1-alpha)*image+alpha*echo
        if type(weight) in (int,float):image=image*weight
        return np.clip(image,0,1),'composite echo and gamma redraw weight applied'
    return image,None


def _motion_vector_marks(facts,sample,time,width,height):
    vectors=facts.get('/analysis/visual_description/static_behaviour/motion_vectors')
    if not isinstance(vectors,dict) or vectors.get('status')!='described' or not vectors.get('vector_count'):return []
    if sample is None:return []
    map_x,map_y=sample(time)
    length=_mid(vectors.get('length_scale')) or .9
    colour=vectors.get('colour_rgba') or [1,1,1,1]
    shade=tuple(float(v) if type(v) in (int,float) else 1.0 for v in colour[:3])
    marks=[]
    for fx in vectors['columns_screen_fraction']:
        for fy in vectors['rows_screen_fraction_from_top']:
            px,py=fx*width,fy*height
            i,j=min(height-1,int(py)),min(width-1,int(px))
            ex,ey=px+(map_x[i,j]-px)*length,py+(map_y[i,j]-py)*length
            if math.hypot(ex-px,ey-py)<1.25:ey=py+1.25
            marks.append(((px,py),(ex,ey),shade))
    return marks


_UNARY_NP={'sin':np.sin,'cos':np.cos,'tan':np.tan,'abs':np.abs,'negate':np.negative,'sqr':np.square,'floor':np.floor,
           'ceil':np.ceil,'int':np.floor,'sign':np.sign,'exp':np.exp,'atan':np.arctan}


def _evaluate_np(expression,inputs):
    """Vectorised twin of time_expression.evaluate_inputs (same projectm-eval semantics)."""
    from time_expression import input_names
    names=input_names(expression)
    if names is None or names-set(inputs):raise ValueError('point program not evaluable')
    nodes=expression['nodes'];memo={}
    def value(index):
        if index in memo:return memo[index]
        node=nodes[index];op=node['op'];args=[value(a) for a in node['args']]
        with np.errstate(all='ignore'):
            if op=='constant':result=np.float64(node['detail']['value'])
            elif op=='input':result=np.asarray(inputs[node['detail']['name']],np.float64)
            elif op=='add':result=args[0]+args[1]
            elif op=='subtract':result=args[0]-args[1]
            elif op=='multiply':result=args[0]*args[1]
            elif op=='eel_divide':result=np.where(np.abs(args[1])<1e-5,0.,args[0]/np.where(np.abs(args[1])<1e-5,1.,args[1]))
            elif op=='divide':result=np.where(args[1]==0,0.,args[0]/np.where(args[1]==0,1.,args[1]))
            elif op=='remainder':
                divisor=np.trunc(args[1]);result=np.where(divisor==0,0.,np.fmod(np.trunc(args[0]),np.where(divisor==0,1.,divisor)))
            elif op=='eel_equal':result=(np.abs(args[0]-args[1])<1e-5).astype(np.float64)
            elif op=='min':result=np.minimum(args[0],args[1])
            elif op=='max':result=np.maximum(args[0],args[1])
            elif op=='pow':
                result=np.where((np.abs(args[0])<1e-5)&(args[1]<0),0.,np.power(args[0],args[1]))
                result=np.where(np.isnan(result),0.,result)
            elif op=='sqrt':result=np.sqrt(np.abs(args[0]))
            elif op=='less':result=(args[0]<args[1]).astype(np.float64)
            elif op=='greater':result=(args[0]>args[1]).astype(np.float64)
            elif op=='less_equal':result=(args[0]<=args[1]).astype(np.float64)
            elif op=='greater_equal':result=(args[0]>=args[1]).astype(np.float64)
            elif op=='select':result=np.where(args[0]!=0,args[1],args[2])
            else:result=_UNARY_NP[op](args[0])
        memo[index]=result
        return result
    return value(expression['root'])


def _point_clouds(facts):
    """Closed-form custom-wave point clouds from colour component facts."""
    clouds=[]
    for path,value in facts.items():
        if '/colour/components/' not in path or not isinstance(value,dict):continue
        record=(value.get('source_palette') or {}).get('point_colour_distribution') or {}
        if record.get('status')=='closed_form_point_colours' and record.get('positions_closed_form') and record.get('programs'):
            clouds.append((value.get('component_id') or path,record))
    return clouds


def _draw_points(image,record,time,to_pixels,canvas=None):
    count=int(record['sample_count']);programs=record['programs']
    inputs={**record.get('held_inputs',{}),'time':time,'sample':np.linspace(0.,1.,count) if count>1 else np.zeros(1)}
    values={name:np.broadcast_to(_evaluate_np(programs[name],inputs),(count,)) for name in 'rgbaxy'}
    period=256/255
    rgba=[np.clip(np.fmod(np.fmod(values[c],period)+period,period),0,1) for c in 'rgba']
    flags=record.get('draw_flags') or {}
    height,width=image.shape[:2]
    x,y=values['x'],values['y']
    if count>1 and not flags.get('dots'):
        # projectM CustomWaveform::SmoothWave inserts a 4-tap (-.15,1.15,1.15,-.15)/2 point after
        # every point (2N-1 vertices) for line waves. A controlled published-AAR emulator capture
        # (dots-only wave, decay 0) lit every authored point but the inserted points only at chance
        # level, so dot waves draw the N authored points.
        below=np.concatenate([[0],np.arange(count-2)]);above=np.arange(1,count);above2=np.minimum(count-1,np.arange(2,count+1))
        index=np.arange(count-1)
        mid=lambda v:(-.15*v[below]+1.15*v[index]+1.15*v[above]-.15*v[above2])/2
        x=np.insert(x,np.arange(1,count),mid(x));y=np.insert(y,np.arange(1,count),mid(y))
        rgba=[np.insert(c,np.arange(1,count),c[:-1]) for c in rgba]
    px,py=to_pixels((x,y))
    finite=np.isfinite(px)&np.isfinite(py)
    xs=np.rint(px[finite]).astype(int);ys=np.rint(py[finite]).astype(int)
    colour=np.stack(rgba[:3],axis=-1)[finite];alpha=rgba[3][finite]
    layer=np.zeros_like(image);cover=np.zeros(image.shape[:2],np.float32);alpha_sq=np.zeros(image.shape[:2],np.float32)
    # vertex_point_size 2 for thick waves (2x2 pixels), otherwise 1.
    offsets=range(2) if flags.get('thick') else range(1)
    for dx in offsets:
        for dy in offsets:
            keep=(xs+dx>=0)&(xs+dx<width)&(ys+dy>=0)&(ys+dy<height)
            np.add.at(layer,(ys[keep]+dy,xs[keep]+dx),colour[keep]*alpha[keep,None])
            np.maximum.at(cover,(ys[keep]+dy,xs[keep]+dx),alpha[keep])
            np.add.at(alpha_sq,(ys[keep]+dy,xs[keep]+dx),alpha[keep]**2)
    additive=flags.get('additive',True)
    if canvas is not None:
        # GL applies the same blend factors to alpha: additive dst.a += src.a^2; over src.a^2 + dst.a(1-src.a).
        canvas['alpha']=np.clip(canvas['alpha']+alpha_sq if additive else cover**2+canvas['alpha']*(1-cover),0,1)
    if additive:return np.clip(image+layer,0,1)
    return np.clip(image*(1-cover[...,None])+layer,0,1)


def _sprite_operators(facts,width,height):
    """Per-frame border/darken-centre blends as (alpha map, colour) pairs from the borders fact."""
    record=facts.get('/analysis/visual_description/static_behaviour/borders') or {}
    if record.get('status')!='described':return []
    columns,rows=np.meshgrid((np.arange(width)+.5)/width*2-1,(np.arange(height)+.5)/height*2-1)
    extent=np.maximum(np.abs(columns),np.abs(rows))
    operators=[]
    darken=record.get('darken_centre') or {}
    if darken.get('active') and None not in (darken.get('half_size_ndc') or [None]):
        hx,hy=darken['half_size_ndc']
        # Linear fan from alpha 3/32 at the centre to 0 at the diamond rim.
        weight=np.clip(1-(np.abs(columns)/hx+np.abs(rows)/hy),0,1)
        operators.append((weight*darken['centre_alpha'],np.zeros(3,np.float32)))
    for row in record.get('borders') or []:
        band=row.get('ndc_band');alpha=row.get('alpha_range');rgb=row.get('rgb_ranges')
        if not row.get('active') or band is None or row.get('inverted_inner_radius'):continue
        if alpha is None or alpha[0]!=alpha[1] or any(c is None or c[0]!=c[1] for c in rgb):continue
        mask=((extent>=band[0])&(extent<=band[1])).astype(np.float32)
        operators.append((mask*min(1.,alpha[0]),np.array([c[0] for c in rgb],np.float32)))
    return operators


def _value_at(record,key,expression_key,held,time):
    """Constant or closed-form value of a control/texture field at a declared time."""
    if record is None:return None
    constant=record.get(key)
    if type(constant) in (int,float):return float(constant)
    expression=record.get(expression_key)
    try:return float(np.asarray(_evaluate_np(expression,{**held,'time':time})).reshape(-1)[0])
    except (ValueError,TypeError,KeyError,AttributeError):return None


def _textured_shapes(facts,held):
    """Single-instance custom shapes with closed-form controls: textured (previous frame) or gradient fills."""
    base='/analysis/visual_description/elements/'
    shapes=[]
    for path,material in facts.items():
        if not path.startswith(base) or not path.endswith('/material') or not isinstance(material,dict):continue
        texture=material.get('texture') or {}
        if texture.get('role') not in ('previous_main','untextured_vertex_gradient'):continue
        element=path[:-len('/material')]
        controls={(v or {}).get('control'):v for p,v in facts.items() if p.startswith(element+'/motion_controls/') and isinstance(v,dict)}
        geometry=facts.get(element+'/geometry') or {}
        sides=geometry.get('effective_sides')
        if type(sides) not in (int,float) or (geometry.get('configured_instances') or 1)!=1:continue
        shapes.append({'id':facts.get(element+'/id'),'controls':controls,'texture':texture,'sides':int(sides),
                       'textured':texture.get('role')=='previous_main',
                       'channels':material.get('channel_expressions') or {},'blend':material.get('blend_mode'),
                       'rgb':(material.get('centre_vertex_rgba') or [1,1,1,None])[:3],
                       'thick_outline':bool(material.get('thick_outline')),'held':held})
    return shapes


def _draw_textured_shape(image,shape,time,wrap,source=None,canvas=None):
    """Exact affine fan mapping of a textured shape onto the previous frame.

    projectM CustomShape: vertex NDC = (2x-1 + rad*cos(t)*aspectY, 1-2y + rad*sin(t)); the
    orthographic projection reverses Y, so on screen (bottom-origin fractions) the centre is (x, y)
    and the vertex direction is (cos t, -sin t). Texture coordinates (0.5+0.5*aspY*cos(t')/zoom,
    0.5+0.5*sin(t')/zoom), t' = t - ang + tex_ang, address the stored previous frame, which the same
    reversal leaves flipped, so the copy keeps the screen orientation and is rotated by
    tex_ang - ang. Controlled emulator check: a textured square with tex_zoom .5 shows the scene
    minified ~0.18x without mirroring; a y=.2 shape renders 80% down the frame.
    """
    height,width=image.shape[:2];aspect=min(1.,height/width);held=shape['held']
    def control(name,default=None):
        record=shape['controls'].get(name)
        if record is None:return default
        return _value_at(record,'constant_value','expression',held,time)
    x=control('position_x');y=control('position_y');radius=control('radius');angle=control('rotation',0.)
    zoom=_value_at(shape['texture'],'tex_zoom_source','tex_zoom_expression',held,time)
    tex_angle=_value_at(shape['texture'],'tex_angle_source_rad','tex_angle_expression',held,time)
    def channel(group,name):
        value=_value_at({'expression':(shape['channels'].get(group) or {}).get(name)},'none','expression',held,time)
        if value is None:return None
        period=256/255  # projectM color_modulo, then [0,1]
        return min(1.,max(0.,math.fmod(math.fmod(value,period)+period,period)))
    alphas=[channel('centre','a'),channel('perimeter','a2')]
    centre_rgb=[channel('centre',c) for c in 'rgb'];edge_rgb=[channel('perimeter',c+'2') for c in 'rgb']
    border=[channel('border','border_'+c) for c in 'rgba']
    if None in (x,y,radius,angle,zoom,tex_angle) or None in alphas or zoom==0 or radius<=0:return image,False
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,1-(np.arange(height)+.5)/height)
    # (ux, sn) = s*(cos t, sin t) of the vertex parameterisation; screen up is -sin t.
    ux=(columns-x)/(radius*aspect*.5);sn=-(rows-y)/(radius*.5)
    delta=tex_angle-angle;cos,sin=math.cos(delta),math.sin(delta)
    u=.5+.5/zoom*(cos*ux-sin*sn)*aspect;v=.5-.5/zoom*(sin*ux+cos*sn)
    phi=np.mod(np.arctan2(sn,ux)-(angle+math.pi/4),2*math.pi/shape['sides'])
    edge=math.cos(math.pi/shape['sides'])/np.cos(phi-math.pi/shape['sides'])
    fraction=np.hypot(ux,sn)/edge
    inside=fraction<=1
    if not inside.any():return image,True
    map_x=(u*width-.5).astype(np.float32);map_y=((1-v)*height-.5).astype(np.float32)
    wrap_mode=cv2.BORDER_WRAP if wrap else cv2.BORDER_REPLICATE
    t=np.clip(fraction,0,1)[...,None]
    if shape.get('textured',True):
        sampled=cv2.remap(image if source is None else source,map_x,map_y,cv2.INTER_LINEAR,borderMode=wrap_mode)
        sampled=sampled*np.array([c if c is not None else 1. for c in centre_rgb],np.float32)
    else:
        if None in centre_rgb or None in edge_rgb:return image,False
        sampled=(np.array(centre_rgb,np.float32)*(1-t)+np.array(edge_rgb,np.float32)*t).astype(np.float32)
    alpha=np.where(inside,alphas[0]+(alphas[1]-alphas[0])*np.clip(fraction,0,1),0.)[...,None].astype(np.float32)
    if canvas is not None:
        # Textured fill = vertex colour * texture, so source alpha is vertex alpha times the previous
        # frame's stored alpha (verified: a textured copy of a frame whose alpha is 0 leaves the canvas unchanged).
        if shape.get('textured',True):
            stored=cv2.remap(canvas['previous_alpha'],map_x,map_y,cv2.INTER_LINEAR,borderMode=wrap_mode)
            alpha=alpha*stored[...,None]
        a=alpha[...,0]
        canvas['alpha']=np.clip(canvas['alpha']+a*a if shape['blend']=='source_alpha_additive' else a*a+canvas['alpha']*(1-a),0,1)
    if shape['blend']=='source_alpha_additive':image=np.clip(image+sampled*alpha,0,1)
    else:image=image*(1-alpha)+sampled*alpha
    if None not in border and border[3]>.0001:
        # Outline: the polygon edge in the border colour, alpha-blended over (thick: MilkDrop's 4 offsets).
        aspect_y=min(1.,height/width)
        angles=np.arange(shape['sides'])/shape['sides']*2*math.pi+angle+math.pi/4
        px=(x+radius*aspect_y*.5*np.cos(angles))*width;py=(1-(y-radius*.5*np.sin(angles)))*height
        layer=np.zeros(image.shape[:2],np.float32)
        points=np.stack([px,py],axis=-1)
        for dx,dy in ([(0,0),(1,0),(1,1),(0,1)] if shape.get('thick_outline') else [(0,0)]):
            cv2.polylines(layer,[np.round((points+[dx,dy])*16).astype(np.int32)],True,1.0,1,cv2.LINE_8,4)
        a=layer*border[3]
        image=image*(1-a[...,None])+a[...,None]*np.array(border[:3],np.float32)
        if canvas is not None:canvas['alpha']=a*a+canvas['alpha']*(1-a)
    return image,True


def illustrate_field(summary,*,time,fps,history_steps):
    """Fact-driven feedback illustration: backward map, RGBA8 decay, waves, vectors, composite."""
    facts=_facts(summary)
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    if not isinstance(context.get('viewport'),list):raise ValueError('declared static-behaviour viewport is required')
    width,height=context['viewport']
    aspect=(1.0,height/width) if width>=height else (width/height,1.0)
    image=np.zeros((height,width,3),np.float32);limitations=[]
    # Stored canvas alpha starts cleared; it weights textured copies of the previous frame.
    canvas={'alpha':np.zeros((height,width),np.float32)}
    flat=facts.get('/analysis/visual_description/nonlinear_texture_colour_bounds/flat_field')
    if isinstance(flat,dict) and isinstance(flat.get('state_rgb'),list):
        image[:]=np.array(flat['state_rgb'],np.float32);limitations.append('feedback content starts from the flat-field steady state')
    sample=_backward_map(facts.get('/analysis/visual_description/static_behaviour/mesh_field'),width,height)
    persistence=facts.get('/analysis/visual_description/static_behaviour/feedback_persistence') or {}
    decay=persistence.get('decay_gain')
    if sample is None or type(decay) not in (int,float):
        limitations.append('per-pixel field or decay not fully described: only the fresh drawing is shown');history_steps=0
    paths,wave_limits=_builtin_wave_paths(facts,aspect);limitations+=wave_limits
    long=max(width,height)
    # Wave vertices: x=(2x-1)*invAspectX, y=(1-2y)*invAspectY, then the orthographic projection
    # reverses Y, so the top-left row is height/2-(y-.5)*long (source y grows upward on screen).
    def to_pixels(point):return ((point[0]-.5)*long+width/2,height/2-(point[1]-.5)*long)
    colours={path:_wave_colour(facts,path) for path,_ in paths}
    clouds=_point_clouds(facts)
    sprites=_sprite_operators(facts,width,height)
    held={name:(span[0]+span[1])/2 for name,span in (context.get('scalar_input_domains') or {}).items()
          if isinstance(span,list) and len(span)==2}
    for name in ('bass','mid','treb','bass_att','mid_att','treb_att'):held.setdefault(name,1.0)
    textured=_textured_shapes(facts,held)
    wrap=True
    if textured:limitations.append('textured shapes redraw the previous frame through their polygon (GL texture orientation; audio-driven alpha/zoom held at band midpoints, so beat toggles are not shown)')
    if sprites:limitations.append('borders and darken-centre blended into the feedback canvas every frame')
    if clouds:limitations.append('closed-form custom-wave point clouds drawn per frame (audio held at midpoints; projection uses the long-side square convention)')
    for path,(colour,note) in colours.items():limitations.append(path+': '+note)
    wave_alpha={path:_wave_alpha(facts,path,limitations) for path,_ in paths}
    try:
        for frame in range(history_steps,-1,-1):
            frame_time=time-frame/fps
            previous=image;canvas['previous_alpha']=canvas['alpha']
            if sample is not None and history_steps:
                map_x,map_y=sample(frame_time)
                image=cv2.remap(image,map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)*decay
                image=np.round(np.clip(image,0,1)*255)/255
                # The warp multiplies by vec4(decay,decay,decay,1): stored alpha is resampled, not decayed.
                canvas['alpha']=np.round(np.clip(cv2.remap(canvas['alpha'],map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE),0,1)*255)/255
            for path,points in paths:
                alpha,additive=wave_alpha[path]
                if alpha is None:continue
                pixels=[to_pixels(point) for point in points]
                colour=_wave_colour_at(facts,path,frame_time) or colours[path][0]
                layer=np.zeros_like(image)
                for a,b in zip(pixels,pixels[1:]):
                    cv2.line(layer,tuple(int(round(v)) for v in a),tuple(int(round(v)) for v in b),tuple(colour),1,cv2.LINE_AA)
                coverage=layer.max(axis=-1,keepdims=True)
                image=np.clip(image+layer*alpha,0,1) if additive else image*(1-coverage*alpha)+layer*alpha
                a=coverage[...,0]*alpha
                canvas['alpha']=np.clip(canvas['alpha']+a*a if additive else a*a+canvas['alpha']*(1-a),0,1)
            # Textured shapes sample the previous frame (the warp's input), not the warped canvas.
            for shape in textured:image,_=_draw_textured_shape(image,shape,frame_time,wrap,previous,canvas)
            for _,record in clouds:image=_draw_points(image,record,frame_time,to_pixels,canvas)
            for alpha,colour in sprites:
                image=image*(1-alpha[...,None])+alpha[...,None]*colour
                canvas['alpha']=alpha*alpha+canvas['alpha']*(1-alpha)
            for start,end,shade in _motion_vector_marks(facts,sample,frame_time,width,height):
                cv2.line(image,tuple(int(round(v)) for v in start),tuple(int(round(v)) for v in end),shade,1,cv2.LINE_AA)
        if _motion_vector_marks(facts,sample,time,width,height):limitations.append('motion vectors drawn from the illustrated backward map')
    except ValueError as error:
        limitations.append('field illustration stopped: '+str(error))
    mesh=facts.get('/analysis/visual_description/static_behaviour/mesh_field') or {}
    warp=((mesh.get('controls') or {}).get('warp') or {}).get('value_range')
    if isinstance(warp,list) and warp!=[0.0,0.0]:
        limitations.append('legacy procedural warp (amplitude 0.0035*warp per step) omitted')
    palette_image=_palette_display(image,facts,limitations)
    if palette_image is not None:image=palette_image
    else:
        for path,value in facts.items():
            if path.endswith('/legacy_response') and isinstance(value,dict):value['_illustration_time']=time
        image,note=_composite(image,facts)
        if any(type(v.get('tint_amount')) in (int,float) and v['tint_amount']>.001 for p,v in facts.items()
               if p.endswith('/legacy_response') and isinstance(v,dict)):
            limitations.append('legacy fShader corner tint applied with zero random hue offsets (tint strength known; hue placement illustrative)')
        if note:limitations.append(note)
    limitations.append('closed-form time colours are evaluated per frame; other colours and audio-driven uniform terms use range midpoints; waveform audio wiggle omitted')
    return image,[path for path,_ in paths]+[str(identity) for identity,_ in clouds],limitations


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
            'Illustration of frozen source facts, not a renderer: smoothing, exact raster, audio-driven waveform shape, additive waves and wave alpha are omitted',
            'Content older than history_steps, including permanent floor residue, is omitted'],
        'uses_rendered_images':False,'uses_equation_execution':False,'reads_preset_source':False}
    args.output.with_suffix('.json').write_text(json.dumps(identity,indent=2)+'\n')
    print(json.dumps(identity))


if __name__=='__main__':
    main()
