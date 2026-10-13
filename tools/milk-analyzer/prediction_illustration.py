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


_UNRESOLVED_TERMS=set()
# Linear scale of the simulated viewport relative to the declared one: 1-2 px dots and lines keep
# their share of the picture by weighting with scale^2 (dots) and scale (lines).
_DRAW_SCALE=[1.]
# Per-frame context for mesh terms: seeded rng and declared bands (set by illustrate_field).
_TERM_CONTEXT={}


def _terms_evaluable(expression):
    """Supported operations only: inputs are coordinates, time, bands, the frame's stepped controls or,
    for names nothing supplies, 0 (projectm-eval reads never-written variables as 0)."""
    from time_expression import input_names
    plain={'root':expression['root'],'nodes':[{**n,'op':'abs'} if n['op'] in _STOCHASTIC else n for n in expression['nodes']]}
    return input_names(plain) is not None


def _term_inputs(expression,base):
    """base inputs plus the frame's stepped controls; names nobody supplies read 0. A per-pixel variable
    read before it is written persists across vertices in the engine; here it reads 0 (approximation)."""
    from time_expression import input_names
    plain={'root':expression['root'],'nodes':[{**n,'op':'abs'} if n['op'] in _STOCHASTIC else n for n in expression['nodes']]}
    stage={k:v for k,v in (_TERM_CONTEXT.get('stage') or {}).items() if isinstance(v,(int,float))}
    inputs={**stage,**base}
    for name in input_names(plain) or ():
        if isinstance(name,str) and name not in inputs:
            inputs[name]=0.;_UNRESOLVED_TERMS.add('mesh input %s read as 0 (never written)'%name)
    return inputs


def _terms_field(terms,x,y,time):
    """Vectorised sum of decomposed control terms over per-pixel coordinates."""
    total=np.zeros_like(x)
    for term in terms:
        kind=term.get('kind')
        if kind=='constant':total+=term['value']
        elif kind=='uniform' and term.get('expression') and _TERM_CONTEXT.get('bands') and _terms_evaluable(term['expression']):
            # Declared per-frame bands replace the range midpoint for audio/time-driven uniform terms.
            inputs=_term_inputs(term['expression'],{'time':time,**_TERM_CONTEXT['bands']})
            total+=term.get('sign',1)*float(np.asarray(_evaluate_np(term['expression'],inputs,_TERM_CONTEXT.get('rng'))).reshape(-1)[0])
        elif kind=='uniform':
            value=_mid(term.get('value_range'))
            if value is None:_UNRESOLVED_TERMS.add('unbounded uniform');_TERM_CONTEXT['unknown_addend']=True;value=0.
            total+=value
        elif kind=='coordinate_affine':
            coefficients=term['coefficients']
            if set(coefficients)-{'x','y','rad','ang'}:
                _UNRESOLVED_TERMS.add('affine term in '+','.join(sorted(set(coefficients)-{'x','y','rad','ang'})));continue
            # Mesh-field convention: x/y measure the long side; rad=1 is half the long side;
            # projectM per-pixel ang = -atan2(y*aspectY, x*aspectX) on NDC, i.e. -atan2(y-.5, x-.5) here.
            total+=(term['constant']+coefficients.get('x',0)*x+coefficients.get('y',0)*y+coefficients.get('rad',0)*2*np.hypot(x-.5,y-.5)
                    +coefficients.get('ang',0)*-np.arctan2(y-.5,x-.5))
        elif kind=='spatial_oscillator':
            osc=term['oscillator'];amplitude=_mid(term.get('amplitude_range'))
            if amplitude is None or set(osc['coordinate_coefficients'])-{'x','y','rad','ang'}:
                _UNRESOLVED_TERMS.add('oscillator');continue
            argument=(osc['coordinate_coefficients'].get('x',0)*x+osc['coordinate_coefficients'].get('y',0)*y+
                      osc['coordinate_coefficients'].get('rad',0)*2*np.hypot(x-.5,y-.5)+
                      osc['coordinate_coefficients'].get('ang',0)*-np.arctan2(y-.5,x-.5)+
                      osc['time_coefficient_radians_per_second']*time+osc['phase_radians'])
            total+=amplitude*(np.sin(argument) if osc['function']=='sin' else np.cos(argument))
        elif kind in ('nonlinear_coordinate_term','unresolved_inputs','uniform_scaled_coordinate_affine') and term.get('expression') \
                and _TERM_CONTEXT.get('rng') is not None and _terms_evaluable(term['expression']):
            inputs=_term_inputs(term['expression'],{'x':x,'y':y,'rad':2*np.hypot(x-.5,y-.5),'ang':-np.arctan2(y-.5,x-.5),'time':time,**_TERM_CONTEXT.get('bands',{})})
            total+=term.get('sign',1)*_evaluate_np(term['expression'],inputs,_TERM_CONTEXT['rng'])
        elif kind=='nonlinear_coordinate_term':
            # Not evaluable here (unsupported operation or input): held at its range midpoint, or zero,
            # like other unresolved terms, so the rest of the field is still illustrated.
            expression=term.get('expression')
            from time_expression import input_names
            names=input_names(expression) if expression else None
            inputs={'x':x,'y':y,'rad':2*np.hypot(x-.5,y-.5),'ang':-np.arctan2(y-.5,x-.5),'time':time,
                    **{n:1.0 for n in ('bass','mid','treb','bass_att','mid_att','treb_att')}}
            if names is None or names-set(inputs):
                value=_mid(term.get('value_range'));total+=0. if value is None else value
                if value is None:_TERM_CONTEXT['unknown_addend']=True
                _UNRESOLVED_TERMS.add('nonlinear term '+('operation' if names is None else 'inputs '+','.join(sorted(map(str,names-set(inputs))))))
            else:total+=term.get('sign',1)*_evaluate_np(expression,inputs)
        elif kind=='coordinate_gated':
            coordinate={'x':x,'y':y,'rad':2*np.hypot(x-.5,y-.5),'ang':-np.arctan2(y-.5,x-.5)}.get(term['coordinate'])
            if coordinate is None:_UNRESOLVED_TERMS.add('gate on '+str(term['coordinate']));continue
            for branch in term['branches']:
                low,high=branch['interval']
                mask=np.ones_like(x,dtype=bool)
                if low is not None:mask&=coordinate>low
                if high is not None:mask&=coordinate<high
                total+=np.where(mask,_terms_field(branch['terms'],x,y,time),0.0)
        else:
            # Unresolved terms (random, state or unsupported inputs) are held at their range midpoint;
            # without a range the sum is unknown (its partners may cancel it), so the caller holds the
            # whole control at its neutral value. The substitution is recorded.
            value=_mid(term.get('value_range'))
            if value is None:_TERM_CONTEXT['unknown_addend']=True
            total+=0. if value is None else value
            _UNRESOLVED_TERMS.add(str(kind))
    return total


# Neutral control values (no motion): a control with an unknown, unbounded addend is held here.
_NEUTRAL={'zoom':1.,'zoomexp':1.,'rot':0.,'warp':0.,'cx':.5,'cy':.5,'dx':0.,'dy':0.,'sx':1.,'sy':1.}


def _control_field(control,name,x,y,time):
    """One mesh control over the vertices; neutral when a term is unknown and unbounded."""
    _TERM_CONTEXT.pop('unknown_addend',None)
    total=_terms_field(control['terms'] or [],x,y,time)
    if _TERM_CONTEXT.pop('unknown_addend',None):
        value=_mid(control.get('value_range'))
        _UNRESOLVED_TERMS.add('control %s held whole (unbounded unknown term)'%name)
        return np.full_like(x,_NEUTRAL[name] if value is None else value)
    return total


MESH_GRID=(48,32)  # production per-pixel mesh (native-lib meshWidth/meshHeight defaults; ruler SetMeshSize)


def _mesh_interpolator(grid,width,height,shader_topology):
    """Pixel-centre interpolation of per-vertex values over projectM's warp mesh triangles.

    Vertex (gx, gy) has pos = (gx/GX*2-1, gy/GY*2-1); on screen pos.y grows downward (native-ruler
    probes), so mesh row 0 is the top edge. Each quad is split along indices 0,1,stride /
    1,stride,stride+1 when the preset has a warp shader, otherwise along the legacy diagonal
    0,1,stride+1 / 0,stride,stride+1.
    """
    gx,gy=grid
    columns,rows=np.meshgrid(np.arange(width)+.5,np.arange(height)+.5)
    X=columns/width*gx;Y=rows/height*gy
    i=np.clip(np.floor(X).astype(int),0,gx-1);j=np.clip(np.floor(Y).astype(int),0,gy-1)
    s=(X-i).astype(np.float32);t=(Y-j).astype(np.float32)
    def interpolate(values):
        v00=values[j,i];v10=values[j,i+1];v01=values[j+1,i];v11=values[j+1,i+1]
        if shader_topology:
            low=s+t<=1
            return np.where(low,v00+s*(v10-v00)+t*(v01-v00),v11+(1-s)*(v01-v11)+(1-t)*(v10-v11))
        upper=s>=t
        return np.where(upper,v00+(s-t)*(v10-v00)+t*(v11-v00),v00+(t-s)*(v01-v00)+s*(v11-v00))
    return interpolate


def _backward_map(mesh,width,height,grid=MESH_GRID,shader_topology=True):
    """Closure computing per-pixel source coordinates from mesh-field facts.

    Like the engine, the motion equations are evaluated at the mesh vertices and the source
    coordinates are interpolated linearly over the mesh triangles (grid None: per pixel).
    """
    controls=(mesh or {}).get('controls') or {}
    warp_params=(mesh or {}).get('procedural_warp_parameters')
    names=('zoom','zoomexp','rot','warp','cx','cy','dx','dy','sx','sy')
    if any(controls.get(name,{}).get('status')!='described' for name in names):return None
    long=max(width,height)
    if grid:
        gx,gy=int(grid[0]),int(grid[1])
        columns,rows=np.meshgrid(np.arange(gx+1)/gx*width,np.arange(gy+1)/gy*height)
        interpolate=_mesh_interpolator((gx,gy),width,height,shader_topology)
    else:
        columns,rows=np.meshgrid(np.arange(width)+.5,np.arange(height)+.5);interpolate=None
    # Engine frame: per-pixel x/y and u/v in long-side units with y DOWN on screen (MilkDrop's y=0 at
    # the top); rotation, cx/cy, dx/dy and the per-pixel inputs follow PresetWarpVertexShader in this
    # frame (verified on the native ruler with isolated motion probes, single-step correlation 1.000).
    x=.5+(columns-width/2)/long;y=.5+(rows-height/2)/long
    rad=2*np.hypot(x-.5,y-.5)
    def sample(time):
        values={name:_control_field(controls[name],name,x,y,time) for name in names}
        # Negative zoom with zoomexp exactly 1 is the zoom itself (patch 0047's CPU path: a point
        # reflection of the sample); other nonpositive bases have no defined power and are not illustrated.
        positive=values['zoom']>0
        unsupported=(values['zoom']==0)|(values['zoomexp']<=0)|((~positive)&(values['zoomexp']!=1))
        if np.any(unsupported):raise ValueError('nonpositive zoom with zoomexp != 1 (or zero zoom) not illustrated')
        zoom=np.where(positive,np.power(np.where(positive,values['zoom'],1.),np.power(values['zoomexp'],2*rad-1)),values['zoom'])
        u=.5+(x-.5)/zoom;v=.5+(y-.5)/zoom
        # Stretch near zero would sample at infinity; keep its sign with a 1e-3 magnitude floor.
        stretch=lambda value:np.where(np.abs(value)<1e-3,np.where(value<0,-1e-3,1e-3),value)
        u=values['cx']+(u-values['cx'])/stretch(values['sx']);v=values['cy']+(v-values['cy'])/stretch(values['sy'])
        if warp_params is not None and np.any(values['warp']!=0):
            speed=float(warp_params.get('warp_anim_speed') or 1.);scale=float(warp_params.get('warp_scale') or 1.)
            wt=time*speed;wsi=1./scale if scale else 1.
            f0=11.68+4.0*np.cos(wt*1.413+10);f1=8.77+3.0*np.cos(wt*1.113+7)
            f2=10.54+3.0*np.cos(wt*1.233+3);f3=11.49+4.0*np.cos(wt*0.933+5)
            # Procedural warp on the vertex pos (pos.y grows downward on screen, like v). The built-in
            # warp (no warp shader) compiles PROJECTM_LEGACY_WARP, where pos.y enters with the opposite
            # sign; probes: 0.9987 with the matching formula, 0.46 with the other.
            px=(x-.5)*2*long/width;py=(y-.5)*2*long/height
            w=values['warp']*.0035
            qy=py if shader_topology else -py
            du=w*np.sin(wt*.333+wsi*(px*f0-qy*f3))+w*np.cos(wt*.753-wsi*(px*f1-qy*f2))
            dv=w*np.cos(wt*.375-wsi*(px*f2+qy*f1))+w*np.sin(wt*.825+wsi*(px*f0+qy*f3))
            u=u+du;v=v+dv
        cos,sin=np.cos(values['rot']),np.sin(values['rot'])
        du,dv=u-values['cx'],v-values['cy']
        u=du*cos-dv*sin+values['cx'];v=du*sin+dv*cos+values['cy']
        u=u-values['dx'];v=v-values['dy']
        if interpolate is not None:u=interpolate(u);v=interpolate(v)
        return ((u-.5)*long+width/2-.5).astype(np.float32),((v-.5)*long+height/2-.5).astype(np.float32)
    return sample


def _builtin_wave_dynamic(facts):
    """Built-in waves drawable per frame from declared PCM (modes 0-9 except 8)."""
    rows=[]
    for path,value in facts.items():
        if not path.endswith('/waveform_recipe') or not isinstance(value,dict):continue
        mode=value.get('effective_mode')
        if type(mode) not in (int,float) or int(mode)%16 in (8,10,11,12,13,14,15):continue
        rows.append((path,value))
    return rows


def _builtin_wave_frame(recipe,frame_time,frame_index,bands,viewport):
    """Per-frame built-in wave polylines (NDC) from the declared reference PCM window."""
    from builtin_wave_geometry import vertices,reference_windows
    from time_expression import evaluate_inputs
    windows=_REFERENCE_WINDOWS.get('data')
    if windows is None:windows=_REFERENCE_WINDOWS['data']=reference_windows()
    window=windows[min(len(windows)-1,max(0,frame_index))]
    controls=recipe.get('control_expressions') or {}
    def control(name,default):
        expression=controls.get(name)
        if expression:
            try:return evaluate_inputs(expression,{'time':frame_time,**bands})
            except (ValueError,KeyError,TypeError):pass
        value=recipe.get(name)
        return float(value) if type(value) in (int,float) else default
    pre=recipe.get('preprocess') or {}
    return vertices(int(recipe['effective_mode']),left=window,wave_x=control('wave_x',.5),wave_y=control('wave_y',.5),
                    mystery=control('wave_mystery',0.),scale=float(pre.get('wave_scale') or 1.),
                    smoothing=float(pre.get('wave_smoothing') or 0.),time=frame_time,viewport=viewport)


_REFERENCE_WINDOWS={}


def _builtin_wave_paths(facts,aspect):
    """Built-in waveform centre-lines in EEL coordinates, without audio wiggle."""
    paths=[];limitations=[]
    dynamic={path for path,_ in _builtin_wave_dynamic(facts)}
    for path,value in facts.items():
        if not path.endswith('/waveform_recipe') or not isinstance(value,dict):continue
        if path in dynamic:continue
        form=value.get('form_name')
        if form=='two_channel_parallel_traces' and value.get('line_angle_rad') is not None:
            angle=value['line_angle_rad'];offset=value.get('separation_normal_offset') or 0.0
            direction=(math.cos(angle),math.sin(angle));normal=(-direction[1],direction[0])
            for sign in (1,-1):
                points=[]
                for t in np.linspace(-1.5,1.5,240):
                    ndc=(direction[0]*t+normal[0]*sign*offset,direction[1]*t+normal[1]*sign*offset)
                    # Built-in wave NDC y points up on screen (native-ruler probe: wave_y .8 renders near the top).
                    points.append((.5+.5*ndc[0]*aspect[0],.5+.5*ndc[1]*aspect[1]))
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
        mode=(facts.get(path) or {}).get('effective_mode') if isinstance(facts.get(path),dict) else None
        if _frame_wave_alpha(material,{'bass':1.,'mid':1.,'treb':1.},mode,480) is not None:
            limitations.append(path+': alpha follows the declared per-frame volume ramp');return 1.0,additive
        limitations.append(path+': alpha unresolved; drawn at alpha 1');return 1.0,additive
    if type(gate) in (int,float) and envelope[1]<gate:
        limitations.append(path+': final alpha below the native draw gate; not drawn');return None,additive
    return min(1.,max(0.,(envelope[0]+envelope[1])/2)),additive


def _blend_wave_layer(image,canvas_alpha,layer,mask,alpha,additive):
    """Blend one built-in wave raster into the canvas. Coverage comes from the raster mask, never from
    the colour: a near-black wave (not maximised when its largest channel is <= 0.01) still replaces
    what it covers under alpha blending. The layer holds colour times the raster weight (anti-aliased
    lines), the mask the raster weight alone. Returns (image, canvas alpha)."""
    coverage=np.clip(mask,0,1)[...,None]
    image=np.clip(image+layer*alpha,0,1) if additive else image*(1-coverage*alpha)+layer*alpha
    a=coverage[...,0]*alpha
    return image,np.clip(canvas_alpha+a*a if additive else a*a+canvas_alpha*(1-a),0,1)


def _frame_wave_alpha(material,values,mode=None,texsize=None):
    """Per-frame built-in wave alpha from the alpha recipe: mode-adjusted authored alpha (wave_a from the
    frame program when stepped), or for mode 3 the reference alpha (by MaximizeColorsTextureSize) * 1.3 *
    treb^2; then times the volume ramp (vol = 0.333*(bass+mid+treb)) when enabled, clamped to [0, 1].
    None when the recipe lacks a resolved mode-adjusted alpha."""
    recipe=(material or {}).get('alpha_recipe') or {}
    base=recipe.get('alpha_envelope_without_volume_modulation')
    table=recipe.get('reference_table')
    if mode is not None and int(mode)%16==3 and recipe.get('mode3_formula') and isinstance(table,list) and texsize:
        if type(values.get('treb')) not in (int,float):return None
        row=next((r for r in table if r.get('maximum_size') is None or texsize<=r['maximum_size']),None)
        if row is None or type(row.get('mode3_base_alpha')) not in (int,float):return None
        alpha=float(np.float32(row['mode3_base_alpha'])*np.float32(1.3)*np.float32(values['treb'])**2)
    elif not isinstance(base,list) or len(base)!=2 or None in base or base[0]!=base[1] and type(values.get('wave_a')) not in (int,float):
        return None
    else:
        alpha=float(base[0])
        if type(values.get('wave_a')) in (int,float) and type(recipe.get('mode_gain')) in (int,float):
            alpha=float(values['wave_a'])*float(recipe['mode_gain'])
    ramp=recipe.get('volume_ramp') or {}
    if ramp.get('enabled'):
        if any(type(values.get(k)) not in (int,float) for k in ('bass','mid','treb')):return None
        vol=(values['bass']+values['mid']+values['treb'])*.333
        denominator=float(ramp['end'])-float(ramp['start'])
        if denominator==0:return None
        alpha*=(vol-float(ramp['start']))/denominator
    return min(1.,max(0.,alpha))


def _frame_wave_colour(material,values):
    """Built-in wave colour from the stepped per-frame wave_r/g/b, clamped, then maximised (largest
    channel 1, above 0.01) when bMaximizeWaveColor normalisation is enabled; None without them."""
    rgb=[values.get('wave_'+c) for c in 'rgb']
    if any(type(v) not in (int,float) for v in rgb):return None
    rgb=[min(1.,max(0.,float(v))) for v in rgb]
    peak=max(rgb)
    if (material or {}).get('normalization_enabled') and peak>.01:rgb=[v/peak for v in rgb]
    return rgb


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


def _composite(image,facts,controls=None):
    for path,value in facts.items():
        if not path.endswith('/legacy_response') or not isinstance(value,dict):continue
        ranges=value.get('native_control_ranges') or {}
        alpha=_mid(ranges.get('echo_alpha'));zoom=_mid(ranges.get('echo_zoom'));orient=_mid(ranges.get('echo_orient'))
        # The engine (patch 0008) applies this frame's echo controls: use the stepped values when known.
        frame=controls or {}
        if type(frame.get('echo_alpha')) in (int,float):alpha=min(1.,max(0.,float(frame['echo_alpha'])))
        if type(frame.get('echo_zoom')) in (int,float):zoom=min(1000.,max(.001,float(frame['echo_zoom'])))
        if type(frame.get('echo_orient')) in (int,float):orient=float(frame['echo_orient'])
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
        gamma=ranges.get('gamma')
        if isinstance(gamma,list) and len(gamma)==2 and None not in gamma and gamma[0]!=gamma[1]:
            # Variable gamma: use the midpoint redraw weight rather than the upper bound.
            weight=max(1.,(gamma[0]+gamma[1])/2)
        if type(weight) in (int,float):image=np.clip(image*weight,0,1)
        # Ordered legacy filters after the hue/gamma/echo draws (legacy_composite.apply_filters).
        on=lambda name:isinstance(ranges.get(name),list) and None not in ranges[name] and min(ranges[name])!=0
        if on('brighten'):image=1-(1-image)**2
        if on('darken'):image=image*image
        if on('solarize'):image=np.clip(2*image*(1-image),0,1)
        if on('invert'):image=1-image
        return np.clip(image,0,1),'composite echo, gamma redraw weight and legacy filters applied'
    return image,None


def _mv_alpha(facts):
    vectors=facts.get('/analysis/visual_description/static_behaviour/motion_vectors') or {}
    colour=vectors.get('colour_rgba') or [1,1,1,1]
    return min(1.,max(0.,colour[3])) if len(colour)>3 and type(colour[3]) in (int,float) else 1.


def _gl_line_pixels(x0,y0,x1,y1,width,height,return_index=False):
    """Pixels of aliased 1 px GL lines (window coordinates, pixel centres at i+.5), vectorised.

    Diamond-exit rule along the major axis: a pixel is produced when the segment leaves its diamond,
    i.e. its exit vertex (centre + half a pixel in the drawing direction) lies in (start, end]; the
    pixel holding the end point is not produced, so a line about one pixel long covers one pixel.
    The minor coordinate is taken where the line crosses the pixel centre.
    """
    x0,y0,x1,y1=(np.asarray(v,np.float64).ravel() for v in (x0,y0,x1,y1))
    dx,dy=x1-x0,y1-y0;xmajor=np.abs(dx)>=np.abs(dy)
    a0=np.where(xmajor,x0,y0);a1=np.where(xmajor,x1,y1);b0=np.where(xmajor,y0,x0);b1=np.where(xmajor,y1,x1)
    step=np.where(a1>=a0,1.,-1.);span=np.abs(a1-a0)
    # First exit vertex strictly after the start in the drawing direction (vertices sit on integers).
    first=np.where(step>0,np.floor(a0)+1,np.ceil(a0)-1)
    rows=[];cols=[];segments=[]
    for k in range(int(np.ceil(span.max()))+1 if len(span) else 0):
        exit_=first+step*k;offset=(exit_-a0)*step
        keep=(offset>0)&(offset<=span)
        if not keep.any():continue
        centre=exit_-.5*step
        t=np.clip(np.where(span>0,(centre-a0)*step/np.where(span>0,span,1.),0.),0,1)
        minor=np.floor(b0+(b1-b0)*t);major=np.floor(centre)
        col=np.where(xmajor,major,minor)[keep].astype(int);row=np.where(xmajor,minor,major)[keep].astype(int)
        inside=(col>=0)&(col<width)&(row>=0)&(row<height)
        cols.append(col[inside]);rows.append(row[inside]);segments.append(np.nonzero(keep)[0][inside])
    if not rows:return (np.zeros(0,int),)*(3 if return_index else 2)
    if return_index:return np.concatenate(rows),np.concatenate(cols),np.concatenate(segments)
    return np.concatenate(rows),np.concatenate(cols)


def _motion_vector_marks(facts,sample,time,width,height,maps=None):
    vectors=facts.get('/analysis/visual_description/static_behaviour/motion_vectors')
    if not isinstance(vectors,dict) or vectors.get('status')!='described' or not vectors.get('vector_count'):return []
    if sample is None:return []
    map_x,map_y=maps if maps is not None else sample(time)
    length=_mid(vectors.get('length_scale')) or .9
    colour=vectors.get('colour_rgba') or [1,1,1,1]
    shade=tuple(float(v) if type(v) in (int,float) else 1.0 for v in colour[:3])
    minimum=math.hypot(1.25/width,1.25/height)
    marks=[]
    for fx in vectors['columns_screen_fraction']:
        for fy in vectors['rows_screen_fraction_from_top']:
            px,py=fx*width,fy*height
            i,j=min(height-1,int(py)),min(width-1,int(px))
            # PresetMotionVectorsVertexShader works in texture units: dist=(old-pos)*mv_l, lengthened to
            # minimum_length=|(1.25/W, 1.25/H)| along its direction (or set to (min, min) when ~zero).
            du,dv=(map_x[i,j]+.5-px)/width*length,(map_y[i,j]+.5-py)/height*length
            norm=math.hypot(du,dv)
            if norm<=minimum:du,dv=(du*minimum/norm,dv*minimum/norm) if norm>1e-8 else (minimum,minimum)
            marks.append(((px,py),(px+du*width,py+dv*height),shade))
    return marks


from eel_memory import _UNARY_NP,STOCHASTIC as _STOCHASTIC,Memory  # noqa: E402 - shared projectm-eval numerics


class _FrameSiteRandom:
    """A frame's random source: per-frame rand call sites (inlined main per-frame code) draw once per
    frame and are shared by every instance and control that reads them; other calls draw per call."""
    def __init__(self,generator):
        self.generator=generator;self.cache={}

    def site_draw(self,key,limit):
        if key not in self.cache:self.cache[key]=float(self.generator.random())
        return self.cache[key]*limit

    def __getattr__(self,name):
        return getattr(self.generator,name)


def _evaluate_np(expression,inputs,rng=None,batch_shape=None):
    """Vectorised evaluation with projectm-eval semantics (eel_memory: loops and megabuf included).

    With an rng, projectm-eval rand(x) is sampled as uniform [0, max(1, floor(x))): a seeded
    Monte Carlo draw of the authored distribution, not the engine's random stream.
    """
    from eel_memory import evaluate_np
    return evaluate_np(expression,inputs,rng,batch_shape=batch_shape)


def _point_clouds(facts):
    """Closed-form custom-wave point clouds from colour component facts."""
    clouds=[]
    for path,value in facts.items():
        if '/colour/components/' not in path or not isinstance(value,dict):continue
        record=(value.get('source_palette') or {}).get('point_colour_distribution') or {}
        drawable=record.get('status') in ('closed_form_point_colours','frame_state_point_colours') or record.get('positions_only')
        if drawable and record.get('positions_closed_form') and record.get('programs'):
            clouds.append((value.get('component_id') or path,record))
    return clouds


def _point_pixels(px,py,size,height):
    """First (column, top-down row) covered by size-s GL points at window coordinates (px, py top-down).

    Columns: ceil(px - s/2 - .5). Rows: the GL window y is height - py, its first covered GL row is
    ceil(height - py - s/2 - .5), and the covered top-down rows run upward from height-1 minus that
    row; the returned row is the topmost, so offsets 0..s-1 go down the screen.
    """
    columns=np.ceil(np.asarray(px)-size/2-.5).astype(int)
    first_gl=np.ceil(height-np.asarray(py)-size/2-.5).astype(int)
    rows=height-1-(first_gl+size-1)
    return columns,rows


def _draw_points(image,record,time,to_pixels,canvas=None,audio=None,rng=None,ends=None):
    count=int(record['sample_count']);programs=record['programs']
    inputs={**record.get('held_inputs',{}),**(audio or {}),'time':time,'sample':np.linspace(0.,1.,count) if count>1 else np.zeros(1)}
    stochastic=bool(record.get('stochastic')) and rng is not None
    # Unresolved colour channels (positions-only records) take the wave's authored colour before its code.
    authored=record.get('authored_rgba') or [1.,1.,1.,1.]
    values={name:np.broadcast_to(_evaluate_np(programs[name],inputs,rng if stochastic else None,(count,) if stochastic else None),(count,))
            if name in programs else np.full(count,float(authored['rgba'.index(name)] if authored['rgba'.index(name)] is not None else 1.))
            for name in 'rgbaxy'}
    # A channel written as a per-point state (x=mx after mx's update) takes that state's end-of-point
    # value, so random steps are not drawn twice.
    points=record.get('point_recurrence') or {}
    for name in 'rgbaxy':
        for state,entry in (points.get('state') or {}).items():
            key=points['state_input_prefix']+state
            if ends is not None and key in ends and entry.get('update')==programs.get(name):values[name]=ends[key]
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
    if not flags.get('dots'):
        # Line waves: a 1 px strip through the smoothed vertices, each segment in its start colour
        # (segments drawn into one accumulation layer; overlaps within a frame are not double-counted).
        layer=np.zeros_like(image);cover=np.zeros(image.shape[:2],np.float32)
        colour=np.stack(rgba[:3],axis=-1)*rgba[3][:,None];alpha=rgba[3]
        limit=4*max(width,height)
        valid=[i for i in range(len(px)-1) if np.isfinite(px[i:i+2]).all() and np.isfinite(py[i:i+2]).all()
               and max(abs(px[i]),abs(py[i]),abs(px[i+1]),abs(py[i+1]))<=limit]
        # projectM 4.1.7 thick lines: four passes offset by +x, +y, -x of 1/viewportX in NDC (CustomWaveform
        # uses the width for both): half a pixel right and H/(2W) pixels up (NDC y grows upward), so the
        # same 1 px strip is mostly lit four times (native ruler: a flat line at y=.5 lights one row).
        up=.5*height/width
        for ox,oy in ([(0,0),(.5,0),(.5,-up),(0,-up)] if flags.get('thick') else [(0,0)]):
            pass_layer=np.zeros_like(image)
            colour=colour*min(1.,_DRAW_SCALE[0]) if ox==0 and oy==0 else colour
            if flags.get('additive',True) and valid:
                # Additive blending adds every segment, so self-crossing and retraced strokes accumulate
                # (GL leaves each segment's end pixel to the next one: joints are not counted twice).
                # px/py use pixel centres at integers (the native-ruler-checked cv2 raster); shift by half a
                # pixel into _gl_line_pixels' centres-at-i+.5 window convention.
                v=np.array(valid);h=.5
                rows,cols,seg=_gl_line_pixels(px[v]+ox+h,py[v]+oy+h,px[v+1]+ox+h,py[v+1]+oy+h,width,height,return_index=True)
                np.add.at(pass_layer,(rows,cols),colour[v][seg]);np.add.at(cover,(rows,cols),alpha[v][seg])
            for i in ([] if flags.get('additive',True) else valid):
                a=(int(round((px[i]+ox)*16)),int(round((py[i]+oy)*16)));b=(int(round((px[i+1]+ox)*16)),int(round((py[i+1]+oy)*16)))
                cv2.line(pass_layer,a,b,tuple(float(c) for c in colour[i]),1,cv2.LINE_8,4)
                cv2.line(cover,a,b,float(alpha[i]),1,cv2.LINE_8,4)
            if not flags.get('additive',True):
                # Alpha blending: each thick pass is blended on its own (GL), so repeated passes converge
                # to the line colour instead of summing past it.
                pass_cover=np.zeros(image.shape[:2],np.float32)
                for i in valid:
                    a=(int(round((px[i]+ox)*16)),int(round((py[i]+oy)*16)));b=(int(round((px[i+1]+ox)*16)),int(round((py[i+1]+oy)*16)))
                    cv2.line(pass_cover,a,b,float(alpha[i]),1,cv2.LINE_8,4)
                image=np.clip(image*(1-pass_cover[...,None])+pass_layer,0,1)
                if canvas is not None:canvas['alpha']=np.clip(pass_cover**2+canvas['alpha']*(1-pass_cover),0,1)
            layer+=pass_layer
        if not flags.get('additive',True):return image
        if canvas is not None:
            canvas['alpha']=np.clip(canvas['alpha']+cover**2,0,1)
        return np.clip(image+layer,0,1)
    finite=np.isfinite(px)&np.isfinite(py)
    # GL point coverage: a size-s point at window position w lights pixels whose centres lie in
    # [w - s/2, w + s/2) (native-ruler probe: x=0.5 lands on column 239, a point at x=0 is not drawn).
    # Rows here are top-down, so the half-open interval runs from the bottom edge of the GL window.
    size=2 if flags.get('thick') else 1
    xs,ys=_point_pixels(px[finite],py[finite],size,height)
    colour=np.stack(rgba[:3],axis=-1)[finite];alpha=rgba[3][finite]*min(1.,_DRAW_SCALE[0]**2)
    layer=np.zeros_like(image);alpha_sq=np.zeros(image.shape[:2],np.float32)
    log_clear=np.zeros(image.shape[:2],np.float64);weight=np.zeros(image.shape[:2],np.float32)
    offsets=range(size)
    for dx in offsets:
        for dy in offsets:
            keep=(xs+dx>=0)&(xs+dx<width)&(ys+dy>=0)&(ys+dy<height)
            where=(ys[keep]+dy,xs[keep]+dx)
            np.add.at(layer,where,colour[keep]*alpha[keep,None])
            np.add.at(alpha_sq,where,alpha[keep]**2)
            np.add.at(log_clear,where,np.log(np.clip(1-alpha[keep],1e-6,1)))
            np.add.at(weight,where,alpha[keep])
    additive=flags.get('additive',True)
    if additive:
        # GL applies the same blend factors to alpha: additive dst.a += src.a^2.
        if canvas is not None:canvas['alpha']=np.clip(canvas['alpha']+alpha_sq,0,1)
        return np.clip(image+layer,0,1)
    # Alpha blending composites overlapping points one after another: the background keeps the product
    # of (1 - a) and the points' colours fill the rest (alpha-weighted mean colour; exact for one colour).
    clear=np.exp(log_clear).astype(np.float32);cover=1-clear
    mean=layer/np.maximum(weight,1e-9)[...,None]
    if canvas is not None:canvas['alpha']=np.clip(cover**2+canvas['alpha']*clear,0,1)
    return np.clip(image*clear[...,None]+mean*cover[...,None],0,1)


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


def _dynamic_border_operators(facts,width,height,values):
    """Per-frame border blends for active borders whose colour/alpha/size vary: stepped per-frame
    ob_*/ib_* values (frame program outputs), else the fact's range midpoints. Bands are square
    annuli in NDC: outer [1-ob_size, 1], inner [1-ob_size-ib_size, 1-ob_size]."""
    record=facts.get('/analysis/visual_description/static_behaviour/borders') or {}
    if record.get('status')!='described':return []
    ranges=record.get('control_ranges') or {}
    def control(name):
        value=values.get(name)
        if type(value) in (int,float):return float(value)
        span=ranges.get(name)
        return (span[0]+span[1])/2 if isinstance(span,list) and len(span)==2 and None not in span else None
    columns,rows=np.meshgrid((np.arange(width)+.5)/width*2-1,(np.arange(height)+.5)/height*2-1)
    extent=np.maximum(np.abs(columns),np.abs(rows))
    operators=[]
    for row in record.get('borders') or []:
        rgb=row.get('rgb_ranges') or [];alpha=row.get('alpha_range')
        static=alpha is not None and alpha[0]==alpha[1] and rgb and all(c is not None and c[0]==c[1] for c in rgb)
        if not row.get('active') or static or row.get('inverted_inner_radius'):continue
        prefix='ob_' if row.get('border')=='outer' else 'ib_'
        size_outer=control('ob_size');size=control(prefix+'size');a=control(prefix+'a')
        colour=[control(prefix+c) for c in 'rgb']
        if None in (size_outer,size,a) or None in colour:continue
        low,high=(1-size_outer,1.) if prefix=='ob_' else (1-size_outer-size,1-size_outer)
        mask=((extent>=low)&(extent<=high)).astype(np.float32)
        operators.append((mask*min(1.,max(0.,a)),np.clip(np.array(colour,np.float32),0,1)))
    return operators


def _eval_filled(expression,inputs,rng=None):
    """Scalar value of an EEL graph; inputs it reads but nobody supplies are 0 (projectm-eval)."""
    from eel_memory import input_names
    plain={'root':expression['root'],'nodes':[{**n,'op':'abs'} if n['op'] in _STOCHASTIC else n for n in expression['nodes']]}
    missing=(input_names(plain) or set())-set(inputs)
    value=float(np.asarray(_evaluate_np(expression,{**inputs,**{n:_absent(n) for n in missing}},rng)).reshape(-1)[0])
    return value if math.isfinite(value) else 0.


def _value_at(record,key,expression_key,held,time,rng=None):
    """Constant or closed-form value of a control/texture field at a declared time."""
    if record is None:return None
    constant=record.get(key)
    if type(constant) in (int,float):return float(constant)
    expression=record.get(expression_key)
    try:return float(np.asarray(_evaluate_np(expression,{**held,'time':time},rng)).reshape(-1)[0])
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
        instances=geometry.get('configured_instances') or 1
        if type(sides) not in (int,float) or type(instances) not in (int,float) or not 1<=instances<=1024:continue
        shapes.append({'id':facts.get(element+'/id'),'controls':controls,'texture':texture,'sides':int(sides),
                       'textured':texture.get('role')=='previous_main',
                       'channels':material.get('channel_expressions') or {},'blend':material.get('blend_mode'),
                       'rgb':(material.get('centre_vertex_rgba') or [1,1,1,None])[:3],
                       'thick_outline':bool(material.get('thick_outline')),'held':held,'instances':int(instances),
                       'frame_recurrence':facts.get(element+'/frame_recurrence')})
    return shapes


def _draw_textured_shape(image,shape,time,wrap,source=None,canvas=None,rng=None):
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
        return _value_at(record,'constant_value','expression',held,time,rng)
    x=control('position_x');y=control('position_y');radius=control('radius');angle=control('rotation',0.)
    zoom=_value_at(shape['texture'],'tex_zoom_source','tex_zoom_expression',held,time,rng)
    tex_angle=_value_at(shape['texture'],'tex_angle_source_rad','tex_angle_expression',held,time,rng)
    def channel(group,name):
        value=_value_at({'expression':(shape['channels'].get(group) or {}).get(name)},'none','expression',held,time,rng)
        if value is None:return None
        period=256/255  # projectM color_modulo, then [0,1]
        return min(1.,max(0.,math.fmod(math.fmod(value,period)+period,period)))
    alphas=[channel('centre','a'),channel('perimeter','a2')]
    centre_rgb=[channel('centre',c) for c in 'rgb'];edge_rgb=[channel('perimeter',c+'2') for c in 'rgb']
    border=[channel('border','border_'+c) for c in 'rgba']
    if None in (x,y,radius,angle,zoom,tex_angle) or None in alphas or zoom==0 or radius<=0:return image,False
    # Only the polygon's bounding box can be covered: |dx| <= radius*aspect/2, |dy| <= radius/2 (screen fractions).
    full_image=image;orig_canvas=canvas;full_alpha=canvas['alpha'] if canvas is not None else None
    x0=max(0,int(math.floor((x-radius*aspect*.5)*width))-1);x1=min(width,int(math.ceil((x+radius*aspect*.5)*width))+2)
    y0=max(0,int(math.floor((1-y-radius*.5)*height))-1);y1=min(height,int(math.ceil((1-y+radius*.5)*height))+2)
    if x0>=x1 or y0>=y1:return image,True
    image=full_image[y0:y1,x0:x1]
    if canvas is not None:canvas={**canvas,'alpha':full_alpha[y0:y1,x0:x1]}
    columns,rows=np.meshgrid((np.arange(x0,x1)+.5)/width,1-(np.arange(y0,y1)+.5)/height)
    # (ux, sn) = s*(cos t, sin t) of the vertex parameterisation; screen up is -sin t.
    ux=(columns-x)/(radius*aspect*.5);sn=-(rows-y)/(radius*.5)
    delta=tex_angle-angle;cos,sin=math.cos(delta),math.sin(delta)
    u=.5+.5/zoom*(cos*ux-sin*sn)*aspect;v=.5-.5/zoom*(sin*ux+cos*sn)
    phi=np.mod(np.arctan2(sn,ux)-(angle+math.pi/4),2*math.pi/shape['sides'])
    edge=math.cos(math.pi/shape['sides'])/np.cos(phi-math.pi/shape['sides'])
    fraction=np.hypot(ux,sn)/edge
    inside=fraction<=1
    if not inside.any():return full_image,True
    map_x=(u*width-.5).astype(np.float32);map_y=((1-v)*height-.5).astype(np.float32)
    wrap_mode=cv2.BORDER_WRAP if wrap else cv2.BORDER_REPLICATE
    t=np.clip(fraction,0,1)[...,None]
    if shape.get('textured',True):
        sampled=cv2.remap(full_image if source is None else source,map_x,map_y,cv2.INTER_LINEAR,borderMode=wrap_mode)
        # Textured fill = texture * interpolated vertex colour (centre r,g,b to perimeter r2,g2,b2).
        tint_centre=np.array([c if c is not None else 1. for c in centre_rgb],np.float32)
        tint_edge=np.array([c if c is not None else 1. for c in edge_rgb],np.float32)
        sampled=sampled*(tint_centre*(1-t)+tint_edge*t)
    else:
        if None in centre_rgb or None in edge_rgb:return full_image,False
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
    full_image=full_image.copy();full_image[y0:y1,x0:x1]=image;image=full_image
    if canvas is not None:full_alpha[y0:y1,x0:x1]=canvas['alpha']
    canvas=orig_canvas
    if None not in border and border[3]>.0001:
        # Outline: the polygon edge in the border colour, alpha-blended over (thick: MilkDrop's 4 offsets).
        aspect_y=min(1.,height/width)
        angles=np.arange(shape['sides'])/shape['sides']*2*math.pi+angle+math.pi/4
        px=(x+radius*aspect_y*.5*np.cos(angles))*width;py=(1-(y-radius*.5*np.sin(angles)))*height
        points=np.stack([px,py],axis=-1)
        # Each thick pass is blended on its own; shape borders are offset by 1/viewport in strip
        # units (LineStyleFor ShapeBorder), i.e. half a pixel, so the passes mostly overlap one line.
        for dx,dy in ([(0,0),(.5,0),(.5,.5),(0,.5)] if shape.get('thick_outline') else [(0,0)]):
            layer=np.zeros(image.shape[:2],np.float32)
            cv2.polylines(layer,[np.round((points+[dx,dy])*16).astype(np.int32)],True,1.0,1,cv2.LINE_8,4)
            a=layer*border[3]
            image=image*(1-a[...,None])+a[...,None]*np.array(border[:3],np.float32)
            if canvas is not None:canvas['alpha']=a*a+canvas['alpha']*(1-a)
    return image,True


def _field_from_expression(expression):
    """Rebuild an exported {'root','nodes'[,'plans']} graph as shader_fields.Field objects (with LoopPlans)."""
    from shader_fields import Field,LoopPlan
    nodes=expression['nodes'];built={}
    plans=[LoopPlan(tuple(p['names']),iteration_limit=int(p.get('iteration_limit',1024))) for p in expression.get('plans') or []]
    def build(index):
        if index in built:return built[index]
        node=nodes[index];detail=dict(node.get('detail') or {})
        # The export keeps member fields but not always the swizzle flag; xyzw/rgba fields are swizzles.
        if node['op']=='member' and isinstance(detail.get('field'),str) and detail['field'] and set(detail['field'])<=set('xyzwrgba'):
            detail['swizzle']=True
        if 'plan_ref' in detail:detail['plan']=plans[detail.pop('plan_ref')]
        op=node['op']
        # 'narrow' is the native double->float32 upload; the grid evaluator stores float32, so a cast suffices.
        if op=='narrow':op='cast'
        built[index]=Field(op,tuple(build(a) for a in node['args']),node.get('dtype','float'),detail)
        return built[index]
    root=build(expression['root'])
    for plan,entry in zip(plans,expression.get('plans') or []):
        plan.condition=None if entry.get('condition') is None else build(entry['condition'])
        plan.updates={name:build(i) for name,i in (entry.get('updates') or {}).items()}
        plan.effects=tuple(build(i) for i in entry.get('effects') or [])
    return root


def _fit_inputs(expression,inputs,controls=None):
    """Trim vector inputs to the width each graph declares (composite _uv is float2, warp _uv float4).

    Inputs the uniforms do not supply are taken from the stepped per-frame values (controls): inlined
    Q graphs read persistent per-frame variables such as an accumulator or a beat counter.
    """
    fitted=dict(inputs)
    for node in expression.get('nodes',[]):
        name=node.get('detail',{}).get('name') if node.get('op')=='input' else None
        if isinstance(name,str) and name not in fitted and controls:
            value=controls.get(name,controls.get('state:per_frame_:'+name))
            if type(value) in (int,float):fitted[name]=np.float32(value)
    for node in expression.get('nodes',[]):
        if node.get('op')!='input':continue
        name=node.get('detail',{}).get('name');dtype=node.get('dtype','')
        if isinstance(name,str) and name.startswith('texsize_') and name not in fitted:
            main=np.asarray(inputs.get('texsize_main',[480,270,1/480,1/270]),np.float32)
            fitted[name]=_texsize(name[8:],int(main[0]),int(main[1]))
        value=fitted.get(name)
        if isinstance(value,np.ndarray) and dtype[-1:].isdigit() and dtype.startswith('float'):
            width=int(dtype[-1])
            if value.shape[-1]>width:fitted[name]=value[...,:width]
    return fitted


NOISE_SIZES={'noise_lq':(256,1),'noise_lq_lite':(32,1),'noise_mq':(256,4),'noise_hq':(256,8),
             'noisevol_lq':(32,1),'noisevol_hq':(32,4)}  # (size, zoom) MilkdropNoise; noisevol_* are 32^3 volumes


TEXTURE_DIRECTORY=Path(__file__).resolve().parents[2]/'core/src/main/assets/textures'
_NAMED={}


def _named_texture(name):
    """Bundled image texture by name (RGB float32, rows top-down as uploaded at v=0), or None."""
    key=str(name).lower()
    if key.startswith(('fw_','fc_','pw_','pc_','wf_','cf_','wp_','cp_')):key=key[3:]
    if key not in _NAMED:
        image=None
        try:
            from corpus_inputs import texture_index
            index=_NAMED.setdefault('__index__',texture_index(TEXTURE_DIRECTORY) if TEXTURE_DIRECTORY.is_dir() else {})
            row=index.get(key)
            if row is not None:
                loaded=cv2.imread(row['path'],cv2.IMREAD_COLOR)
                if loaded is not None:image=np.ascontiguousarray(loaded[...,::-1]).astype(np.float32)/255.
        except (OSError,ValueError):image=None
        _NAMED[key]=image
    return _NAMED[key]


def _texsize(name,width,height):
    """texsize_<name> uniform (w, h, 1/w, 1/h): engine noise sizes, blur pass sizes, bundled image sizes,
    256 for other stand-ins."""
    named=_named_texture(name) if name not in NOISE_SIZES and name not in ('main','blur1','blur2','blur3') else None
    if named is not None:h,w=named.shape[:2]
    elif name in NOISE_SIZES:w=h=NOISE_SIZES[name][0]
    elif name in ('blur1','blur2','blur3'):
        from blur import pass_dimensions
        w,h=pass_dimensions(width,height)[2*int(name[4])-1]
    elif name=='main':w,h=width,height
    else:w=h=256
    return np.array([w,h,1/w,1/h],np.float32)


def _rad_ang(width,height,stage='warp'):
    """Per-pixel shader rad/ang in the engine's frames; y is measured downward from the top in both.

    Warp (PerPixelMesh): x, y in -1..1 with mesh row 0 (y=-1) at the top; rad=hypot(x*aspectX,
    y*aspectY), ang=atan2(y*aspectY, x*aspectX) in (-pi, pi]. Composite (FinalComposite::UvToMathSpace):
    the same p from u, v (v=0 at the top), rad normalised to 1 at the corners, ang wrapped to [0, 2pi).
    """
    aspect_x=min(1.,width/height);aspect_y=min(1.,height/width)
    columns,rows=np.meshgrid((np.arange(width)+.5)/width*2-1,(np.arange(height)+.5)/height*2-1)
    px,py=columns*aspect_x,rows*aspect_y
    rad=np.hypot(px,py);ang=np.arctan2(py,px)
    if stage=='composite':
        rad=rad/math.hypot(aspect_x,aspect_y);ang=np.where(ang<0,ang+2*math.pi,ang)
    return np.stack([rad,ang],axis=-1).astype(np.float32)


def _lowlevel_uniforms(width,height):
    """Shader low-level uniforms as pipeline_fields binds them (blur ranges at their [0,1] defaults)."""
    aspect_x=min(1.,width/height);aspect_y=min(1.,height/width)
    size=np.array([width,height,1/width,1/height],np.float32)
    return {'_c0':np.array([aspect_x,aspect_y,1/aspect_x,1/aspect_y],np.float32),'_c1':np.zeros(4,np.float32),
            '_c5':np.array([1,0,1,0],np.float32),'_c6':np.array([1,0,0,1],np.float32),'_c7':size,'texsize_main':size,
            '_c13':np.array([0,1,0,1],np.float32)}


def _blur_bank(image,controls=None):
    """Engine blur textures and their decode uniforms (blur.blur_bank, patched-core range policy).

    Each level is an 8-tap separable pass at the engine's reduced pass size, stored range-normalised
    in unorm8 with blur1 edge darkening; the shader decodes GetBlurN with _c5/_c6. Blur ranges and
    edge darkening come from the per-frame controls (header defaults 0/1/0.25). Returns
    ({1,2,3: top-down RGB}, {'_c5','_c6'}).
    """
    from blur import blur_bank,native_ranges
    from engine_profiles import CORE_2315_BLUR
    controls=controls or {}
    low=[float(controls.get(f'blur{i}_min',0.)) for i in (1,2,3)];high=[float(controls.get(f'blur{i}_max',1.)) for i in (1,2,3)]
    lo,hi=native_ranges(low,high,policy=CORE_2315_BLUR)
    # blur_bank emulates the engine's flipVertical first pass, so its rows come out in the opposite
    # vertical order to its top-down source; one flip restores screen rows. Native-ruler probe: a seeded
    # patch blurred by GetBlur1 matches to 6e-5 mean absolute error (the first pass's one-texel offset
    # makes the orientation observable).
    bank=blur_bank(np.clip(np.nan_to_num(image),0,1).astype(np.float32),levels=3,minimum=low,maximum=high,
                   edge_darken=float(controls.get('blur1_edge_darken',.25)),policy=CORE_2315_BLUR)
    textures={level:np.ascontiguousarray(np.flipud(value)) for level,value in bank.items()}
    uniforms={'_c5':np.array([hi[0]-lo[0],lo[0],hi[1]-lo[1],lo[1]],np.float32),'_c6':np.array([hi[2]-lo[2],lo[2],lo[0],hi[0]],np.float32)}
    return textures,uniforms


def _texture_lookup(source,coordinates,*,wrap,linear):
    """GL texture lookup of (N, 2) normalised coordinates (row 0 at v=0).

    linear: bilinear between the four nearest texel centres. Otherwise GL_NEAREST: the texel
    floor(u*size), so a point sampler reads exactly one texel (no float-error weights on others).
    Wrap repeats; otherwise coordinates clamp to the edge texels.
    """
    th,tw=source.shape[:2]
    if not linear:
        x=np.floor(np.where(np.isfinite(coordinates[:,0]),coordinates[:,0],0.)*tw).astype(np.int64)
        y=np.floor(np.where(np.isfinite(coordinates[:,1]),coordinates[:,1],0.)*th).astype(np.int64)
        x,y=(np.mod(x,tw),np.mod(y,th)) if wrap else (np.clip(x,0,tw-1),np.clip(y,0,th-1))
        return source[y,x].astype(np.float32)
    u=coordinates[:,0]*tw-.5;v=coordinates[:,1]*th-.5
    u=np.where(np.isfinite(u),u,0.);v=np.where(np.isfinite(v),v,0.)
    if wrap:u=np.mod(u,tw);v=np.mod(v,th)
    else:u=np.clip(u,0,tw-1);v=np.clip(v,0,th-1)
    x0=np.floor(u).astype(int);y0=np.floor(v).astype(int);fx=(u-x0)[:,None];fy=(v-y0)[:,None]
    fix=(lambda i,n:np.mod(i,n)) if wrap else (lambda i,n:np.clip(i,0,n-1))
    x1=fix(x0+1,tw);y1=fix(y0+1,th);x0=fix(x0,tw);y0=fix(y0,th)
    return ((source[y0,x0]*(1-fx)+source[y0,x1]*fx)*(1-fy)+(source[y1,x0]*(1-fx)+source[y1,x1]*fx)*fy).astype(np.float32)


def _texture_lookup_3d(volume,coordinates,*,wrap,linear):
    """GL 3D texture lookup of (N, 3) normalised (u, v, w) in a (depth, height, width, C) volume:
    trilinear between texel centres (or the nearest texel), wrapping or clamping each axis."""
    d,h,w=volume.shape[:3]
    sizes=np.array([w,h,d],np.float64)
    c=np.where(np.isfinite(coordinates[:,:3]),coordinates[:,:3],0.)*sizes
    if not linear:
        i=np.floor(c).astype(np.int64)
        i=np.mod(i,sizes.astype(np.int64)) if wrap else np.clip(i,0,sizes.astype(np.int64)-1)
        return volume[i[:,2],i[:,1],i[:,0]].astype(np.float32)
    c=c-.5
    base=np.floor(c).astype(np.int64);f=(c-base)
    out=np.zeros((len(c),volume.shape[3]),np.float32)
    for dx in (0,1):
        for dy in (0,1):
            for dz in (0,1):
                i=base+np.array([dx,dy,dz])
                i=np.mod(i,sizes.astype(np.int64)) if wrap else np.clip(i,0,sizes.astype(np.int64)-1)
                weight=(f[:,0] if dx else 1-f[:,0])*(f[:,1] if dy else 1-f[:,1])*(f[:,2] if dz else 1-f[:,2])
                out+=volume[i[:,2],i[:,1],i[:,0]]*weight[:,None]
    return out


def _sampler_wraps(policy,controls=None):
    """Resolved wrap addressing of an exported sampling policy.

    A null wrap with condition 'frame_wrap > 0.0001' follows the per-frame wrap value (the warp pass
    binds unit 0 with the preset's wrap setting); MilkDrop's default bTexWrap is 1.
    """
    policy=policy or {}
    if type(policy.get('wrap')) is bool:return policy['wrap']
    if policy.get('wrap_condition')=='frame_wrap > 0.0001':
        value=(controls or {}).get('wrap',1.)
        return float(value)>.0001 if type(value) in (int,float) else True
    return True


_NOISE={}


def _noise_texture(name):
    """Deterministic stand-in for projectM noise textures at the engine sizes (lq finest, hq smoothest), values in [0,1]."""
    if name not in _NOISE:
        # MilkdropNoise: random texels every `zoom` texels, cubic in between (lq: every texel; hq: every 8th).
        size,zoom=NOISE_SIZES.get(name,(256,4))
        rng=np.random.default_rng(sum(map(ord,name)))
        if name.startswith('noisevol_'):
            # MilkdropNoise::generate3D: a size^3 volume (z, y, x), random every `zoom` texels, cubic between.
            cells=rng.random((size//zoom,)*3+(3,)).astype(np.float32)
            if zoom>1:
                from scipy.ndimage import zoom as upsample
                cells=upsample(cells,(zoom,zoom,zoom,1),order=3,mode='grid-wrap').clip(0,1).astype(np.float32)
            _NOISE[name]=cells
            return cells
        cells=rng.random((size//zoom,size//zoom,3)).astype(np.float32)
        _NOISE[name]=cells if zoom==1 else cv2.resize(cells,(size,size),interpolation=cv2.INTER_CUBIC).clip(0,1)
    return _NOISE[name]


def _render_constants(context):
    """Readonly per-frame values from the declared render context (PerFrameContext::LoadStateVariables).

    aspectx/aspecty are RenderContext invAspectX/Y: 1 on the long axis and long/short on the other,
    as float32; pixelsx/pixelsy are the viewport; meshx/meshy the per-pixel mesh size.
    """
    viewport=(context or {}).get('viewport')
    if not isinstance(viewport,list) or len(viewport)!=2:return {}
    width,height=float(viewport[0]),float(viewport[1])
    aspect_x=float(np.float32(width/height)) if height>width else 1.
    aspect_y=float(np.float32(height/width)) if width>height else 1.
    values={'pixelsx':width,'pixelsy':height,'aspectx':float(np.float32(1/np.float32(aspect_x))),
            'aspecty':float(np.float32(1/np.float32(aspect_y)))}
    grid=(context or {}).get("mesh_grid")
    if isinstance(grid,list) and len(grid)==2:values.update(meshx=float(grid[0]),meshy=float(grid[1]))
    return values


def _absent(name):
    """Value of an input nobody supplies: projectm-eval variables read 0, memory buffers start zeroed."""
    return Memory() if isinstance(name,str) and name.startswith('memory:') else 0.


class _FrameStepper:
    """Steps the exported per-frame recurrence (stage_programs.frame) under declared bands."""
    def __init__(self,frame,rng_seed=8191,constants=None,deadline=None):
        # Readonly render values the engine loads before frame code (aspect, viewport, mesh).
        self.constants=dict(constants or {});self.deadline=deadline
        self.state_programs=(frame or {}).get('state') or {}
        self.output_programs=(frame or {}).get('outputs') or {}
        self.values=None;self.start={};self.failed=set();self.zero_inputs=set();self.rng=np.random.default_rng(rng_seed)
    def _eval(self,program,inputs):
        # projectm-eval reads a variable that is never written as 0 (for example 'cyyspeed' produced by
        # MilkDrop's joining of a line split across numbered records).
        from eel_memory import input_names
        plain={'root':program['root'],'nodes':[{**n,'op':'abs'} if n['op'] in _STOCHASTIC else n for n in program['nodes']]}
        missing=(input_names(plain) or set())-set(inputs)
        if missing:
            self.zero_inputs|=missing;inputs={**inputs,**{name:_absent(name) for name in missing}}
        from eel_memory import evaluate_np
        value=evaluate_np(program,inputs,self.rng,deadline=self.deadline)
        return value if isinstance(value,Memory) else float(np.asarray(value).reshape(-1)[0])
    def step(self,time,fps,bands,frame_index):
        base={**self.constants,**{k:float(v) for k,v in bands.items()},'time':float(np.float32(time)),'fps':float(np.float32(fps)),'frame':float(frame_index),'progress':0.}
        if self.values is None:
            init_inputs={**base,**{'init:per_frame_init_:'+k:v for k,v in base.items()}}
            self.values={}
            for name,programs in self.state_programs.items():
                try:self.values[name]=self._eval(programs['initial'],init_inputs)
                except Exception:self.values[name]=0.;self.failed.add(name)  # noqa: BLE001
        inputs={**base,**self.values,**{'state:per_frame_:'+k:v for k,v in self.values.items()}}
        # Start-of-frame state: inlined per-frame graphs in shader programs read these values.
        self.start={**self.values,**{'state:per_frame_:'+k:v for k,v in self.values.items()}}
        updated={}
        for name,programs in self.state_programs.items():
            try:value=self._eval(programs['update'],inputs)
            except Exception:value=self.values.get(name,0.);self.failed.add(name)  # noqa: BLE001
            updated[name]=value if isinstance(value,Memory) or math.isfinite(value) else 0.
        outputs={}
        for name,program in self.output_programs.items():
            try:
                value=self._eval(program,inputs)
                if math.isfinite(value):outputs[name]=value
            except Exception:self.failed.add(name)  # noqa: BLE001
        self.values=updated
        return {**{name:_absent(name) for name in self.zero_inputs},**self.values,**{'state:per_frame_:'+k:v for k,v in self.values.items()},**outputs}


def _declared_uniforms(width,height,time,fps,bands):
    """Packed shader uniforms from a declared render state (shader_uniforms layout; Q values unknown -> 0)."""
    from shader_uniforms import source_uniforms
    bands={name:float((bands or {}).get(name,1.)) for name in BANDS}
    render={'time':float(time),'fps':float(fps),'frame':int(round(time*fps)),'progress':0.,**bands}
    q={f'q{i}':float((bands or {}).get(f'q{i}',0.)) for i in range(1,33)}
    scene={'frames':[{'render_inputs':render,'main':q}],'viewport':[width,height]}
    values={k:np.asarray(v,np.float32) for k,v in source_uniforms(scene,0).items()}
    values.update({k:np.float32(bands[k]) for k in BANDS})
    values[':native-render-time-f32']=np.float32(time)
    return values


def _frame_rand(time,fps):
    """Seeded per-frame stand-in for the engine's rand_frame (a new uniform vector every frame)."""
    return np.random.default_rng(7340033+int(round(time*fps))).random(4).astype(np.float32)


def _hue_shader(width,height,time,offsets=(0.,0.,0.,0.),cell_centres=True):
    """Composite vertex colour (hue_shader/_vDiffuse) of FinalComposite::ApplyHueShaderColors.

    Four corner shades 0.6+0.3*sin(time*30*f + phase + i*k + offset), divided by their maximum and mapped
    to 0.5+0.5*shade, are interpolated bilinearly over the screen (x right, y up; rows top-down here).
    The engine draws the random offsets per preset load (PresetState::hueRandomOffsets); zero offsets
    keep the exact cycling and range with an illustrative hue placement.
    """
    import math
    shade=[]
    for i in range(4):
        s=[.6+.3*math.sin(time*30.*.0143+3+i*21+offsets[3]),.6+.3*math.sin(time*30.*.0107+1+i*13+offsets[1]),
           .6+.3*math.sin(time*30.*.0129+6+i*9+offsets[2])]
        m=max(s);shade.append([.5+.5*v/m for v in s])
    shade=np.array(shade,np.float32)
    if cell_centres:xs=(np.arange(width)+.5)/width;ys=1-(np.arange(height)+.5)/height
    else:xs=np.linspace(0.,1.,width);ys=np.linspace(1.,0.,height)
    x,y=np.meshgrid(xs,ys)
    rgb=(shade[0]*(x*y)[...,None]+shade[1]*((1-x)*y)[...,None]+shade[2]*(x*(1-y))[...,None]+shade[3]*((1-x)*(1-y))[...,None])
    return np.concatenate([rgb,np.ones(rgb.shape[:2]+(1,),np.float32)],axis=-1).astype(np.float32)


def _evaluate_stage(program,image,uv,time,fps,bands,diffuse=None,rand=None,controls=None,blur_image=None,stage='warp'):
    """Evaluate an exported stage program per pixel with the shared grid evaluator (source_stage_program).

    blur_image is the canvas the engine's blur textures were made from (default: image).
    """
    from grid_math import evaluate_grid
    from field_math import GLES_IEEE_ILLUSTRATION
    height,width=image.shape[:2]
    blurred,blur_uniforms=_blur_bank(image if blur_image is None else blur_image,controls)
    inputs={'_uv':uv.astype(np.float32),'_uv_orig':uv[...,2:].astype(np.float32),'_rad_ang':_rad_ang(width,height,stage),
            **_lowlevel_uniforms(width,height),**blur_uniforms,**_declared_uniforms(width,height,time,fps,bands),
            'rand_frame':np.asarray(rand if rand is not None else [.5]*4,np.float32),'rand_preset':np.full(4,.5,np.float32)}
    if diffuse is None and stage=='composite':diffuse=_hue_shader(width,height,float(time))
    if diffuse is not None:inputs['_vDiffuse']=np.asarray(diffuse,np.float32)
    def sample(detail,coordinates):
        texture=str(detail.get('canonical_texture','main'))
        source=image
        if texture.startswith('noise'):source=_noise_texture(texture)
        elif texture.startswith('blur'):
            source=blurred[min(3,max(1,int(texture[4:] or 1)))]
        elif texture!='main':
            # Named images: the bundled texture file (declared asset); unknown names keep a noise stand-in.
            named=_named_texture(texture)
            source=named if named is not None else _noise_texture('noise_mq')
        policy=detail.get('sampling_policy') or {}
        if source.ndim==4:
            values=_texture_lookup_3d(source,coordinates,wrap=_sampler_wraps(policy,controls),linear=policy.get('linear') is not False)
        else:values=_texture_lookup(source,coordinates[:,:2],wrap=_sampler_wraps(policy,controls),linear=policy.get('linear') is not False)
        return np.concatenate([values,np.ones((len(values),1),np.float32)],axis=1)
    fitted=_fit_inputs(program,inputs,controls)
    value=np.asarray(evaluate_grid(_field_from_expression(program),batch_shape=(height,width),inputs=fitted,sample=sample,numeric_policy=GLES_IEEE_ILLUSTRATION),np.float32)
    value=value.reshape(height,width,-1)
    return value[...,:3]


def _fit_field_inputs(field,inputs,controls):
    """Add per-frame values for inputs of a rebuilt shader_fields.Field graph that the uniforms lack."""
    fitted=dict(inputs);pending=[field];seen=set()
    while pending:
        node=pending.pop()
        if id(node) in seen:continue
        seen.add(id(node))
        if getattr(node,'op',None)=='input':
            name=node.detail.get('name')
            if isinstance(name,str) and name not in fitted:
                value=controls.get(name,controls.get('state:per_frame_:'+name))
                if type(value) in (int,float):fitted[name]=np.float32(value)
        pending.extend(getattr(node,'args',()))
    return fitted


def _injection_lanes(transfer):
    """Per-lane image-independent warp injections, or None."""
    lanes=((transfer.get('image_independent_injection') or {}).get('lane_expressions_rgb'))
    if not isinstance(lanes,list) or len(lanes)!=3 or all(lane is None for lane in lanes):return None
    try:return [None if lane is None else _field_from_expression(lane) for lane in lanes]
    except (KeyError,TypeError,IndexError):return None


def _main_coordinate_field(transfer):
    """Coordinate expression of the dominant previous-main sample site, when exported."""
    sites=[c for c in transfer.get('sample_contributions') or [] if c.get('texture','main')=='main' and c.get('coordinate_expression')]
    if len(sites)!=1:return None
    try:return _field_from_expression(sites[0]['coordinate_expression'])
    except (KeyError,TypeError,IndexError):return None


def _evaluate_injection(lanes,image,map_x,map_y,time,frame_index,coordinates=None,bands=None,blur_image=None):
    """Evaluate injected warp terms over the pixel grid with the shared grid evaluator.

    _uv.xy is the per-pixel warped sample position and _uv.zw the pixel position (MilkDrop shader
    UV, origin top-left); main/blur samples read the illustrated previous image (blur by the engine blur bank);
    rand_frame is a seeded per-frame stand-in for the engine's random vector.
    """
    from grid_math import evaluate_grid
    from field_math import GLES_IEEE_ILLUSTRATION
    height,width=image.shape[:2]
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([(map_x+.5)/width,(map_y+.5)/height,columns,rows],axis=-1).astype(np.float32)
    aspect_x=min(1.,width/height);aspect_y=min(1.,height/width)
    rng=np.random.default_rng(1000003+frame_index)
    blurred,blur_uniforms=_blur_bank(image if blur_image is None else blur_image,_TERM_CONTEXT.get('bands'))
    controls=_TERM_CONTEXT.get('stage') or _TERM_CONTEXT.get('bands') or {}
    inputs={'_uv':uv,'_rad_ang':_rad_ang(width,height),**_lowlevel_uniforms(width,height),**blur_uniforms,
            **_declared_uniforms(width,height,time,30.,{k:v for k,v in controls.items() if k in BANDS or (k[:1]=='q' and k[1:].isdigit())}),
            **{k:np.float32(v) for k,v in (bands or {}).items()},
            'rand_frame':rng.random(4).astype(np.float32),'rand_preset':np.full(4,.5,np.float32),':native-render-time-f32':np.float32(time)}
    def sample(detail,coordinates):
        texture=detail.get('canonical_texture','main')
        source=image
        if str(texture).startswith('noise'):source=_noise_texture(str(texture))
        elif texture.startswith('blur'):
            source=blurred[min(3,max(1,int(texture[4:] or 1)))]
        policy=detail.get('sampling_policy') or {}
        wrap=_sampler_wraps(policy,_TERM_CONTEXT.get('bands'));linear=policy.get('linear') is not False
        values=_texture_lookup_3d(source,coordinates,wrap=wrap,linear=linear) if source.ndim==4 else _texture_lookup(source,coordinates[:,:2],wrap=wrap,linear=linear)
        return np.concatenate([values,np.ones((len(values),1),np.float32)],axis=1)
    if coordinates is not None:
        value=np.asarray(evaluate_grid(coordinates,batch_shape=(height,width),inputs=_fit_field_inputs(coordinates,inputs,controls),sample=sample,numeric_policy=GLES_IEEE_ILLUSTRATION),np.float32).reshape(height,width,-1)
        return value[...,0]*width-.5,value[...,1]*height-.5
    out=np.zeros((height,width,3),np.float32)
    for index,lane in enumerate(lanes or []):
        if lane is None:continue
        value=evaluate_grid(lane,batch_shape=(height,width),inputs=_fit_field_inputs(lane,inputs,controls),sample=sample,numeric_policy=GLES_IEEE_ILLUSTRATION)
        out[...,index]=np.asarray(value,np.float32).reshape(height,width)
    return out


BANDS=('bass','mid','treb','bass_att','mid_att','treb_att')


def declared_audio(path):
    """Per-frame band values from a milk-audio-inputs report (declared input, not a rendered frame)."""
    report=json.loads(Path(path).read_text())
    frames=report.get('frames')
    if not isinstance(frames,list) or not frames:raise ValueError('audio report has no frames')
    rows=[{name:float(row[name]) for name in BANDS if type(row.get(name)) in (int,float)} for row in frames]
    if any(set(row)!=set(BANDS) for row in rows):raise ValueError('audio report frames need all six bands')
    return {'frames':rows,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'pcm_sha256':report.get('pcm_sha256')}


def _affine_composite(image,facts,time,fps,blur_image=None):
    """Display = sum of matrix x texture(coordinates) + offsets, from texture_colour_transfer.stages.composite."""
    stage=((facts.get('/analysis/visual_description/texture_colour_transfer') or {}).get('stages') or {}).get('composite') or {}
    if stage.get('source_model')!='affine_sample_colour' or not stage.get('sample_contributions'):return None
    from grid_math import evaluate_grid
    from field_math import GLES_IEEE_ILLUSTRATION
    height,width=image.shape[:2]
    columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
    uv=np.stack([columns,rows,columns,rows],axis=-1).astype(np.float32)
    aspect_x=min(1.,width/height);aspect_y=min(1.,height/width)
    blurred,blur_uniforms=_blur_bank(image if blur_image is None else blur_image,_TERM_CONTEXT.get('bands'))
    inputs={'_uv':uv,'_rad_ang':_rad_ang(width,height,'composite'),**_lowlevel_uniforms(width,height),**blur_uniforms,
            ':native-render-time-f32':np.float32(time),'rand_frame':_frame_rand(time,fps)}
    def texture(name):
        if name=='main':return image
        if not name.startswith('blur'):raise ValueError('composite texture not illustrated: '+name)
        # Stored (range-normalised) blur: the exported affine matrix already contains the GetBlurN decode.
        return cv2.resize(blurred[min(3,max(1,int(name[4:] or 1)))],(width,height),interpolation=cv2.INTER_LINEAR)
    try:
        out=np.zeros((height,width,3),np.float32)
        for site in stage['sample_contributions']:
            source=texture(site.get('canonical_texture','main'))
            expression=site['coordinate_expression']
            coordinates=np.asarray(evaluate_grid(_field_from_expression(expression),batch_shape=(height,width),inputs=_fit_inputs(expression,inputs),numeric_policy=GLES_IEEE_ILLUSTRATION),np.float32).reshape(height,width,-1)
            u=np.mod(coordinates[...,0]*width-.5,width).astype(np.float32);v=np.mod(coordinates[...,1]*height-.5,height).astype(np.float32)
            sampled=cv2.remap(source,u,v,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
            rgba=np.concatenate([sampled,np.ones((height,width,1),np.float32)],axis=-1)
            out+=np.einsum('ij,hwj->hwi',np.asarray(site['matrix_rgb_rgba'],np.float32),rgba)
        for lane,expression in enumerate(stage.get('offset_expressions') or []):
            if expression:out[...,lane]+=np.asarray(evaluate_grid(_field_from_expression(expression),batch_shape=(height,width),inputs=_fit_inputs(expression,inputs),numeric_policy=GLES_IEEE_ILLUSTRATION),np.float32).reshape(height,width)
        return np.clip(out,0,1)
    except Exception:  # noqa: BLE001 - fall back to the legacy display model
        return None


def _display(image,facts,time,fps,limitations,blur_image=None):
    """Composite the canvas for display: affine custom composite, scalar palette or the legacy model.

    The engine's composite reads blur textures made from the previous frame's canvas (blur_image).
    """
    program=((facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}).get('composite') or {}
    if program.get('status')=='exported':
        try:
            height,width=image.shape[:2]
            columns,rows=np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)
            uv=np.stack([columns,rows,columns,rows],axis=-1)
            shown=_evaluate_stage(program['program'],image,uv,time,fps,_TERM_CONTEXT.get('bands'),rand=_frame_rand(time,fps),
                                  controls=_TERM_CONTEXT.get('stage') or _TERM_CONTEXT.get('bands'),
                                 blur_image=blur_image,stage='composite')
            limitations.append('composite shader evaluated per pixel from its exported program (engine blur bank, noise stand-ins)')
            return _stored(shown)
        except Exception as error:  # noqa: BLE001 - fall back to the affine/legacy display
            limitations.append('composite program not evaluated: '+str(error)[:120])
    composite_image=_affine_composite(image,facts,time,fps,blur_image)
    palette_image=None if composite_image is not None else _palette_display(image,facts,limitations)
    if composite_image is not None:
        limitations.append('custom composite applied from its exported affine texture transfer (engine blur bank)')
        return composite_image
    if palette_image is not None:return palette_image
    for path,value in facts.items():
        if path.endswith('/legacy_response') and isinstance(value,dict):value['_illustration_time']=time
    shown,note=_composite(image,facts,_TERM_CONTEXT.get('stage'))
    if any(type(v.get('tint_amount')) in (int,float) and v['tint_amount']>.001 for p,v in facts.items()
           if p.endswith('/legacy_response') and isinstance(v,dict)):
        limitations.append('legacy fShader corner tint applied with zero random hue offsets (tint strength known; hue placement illustrative)')
    if note:limitations.append(note)
    return shown


def simulated_display_series(summary,*,seconds=4.,fps=30.,viewport=(160,90),audio=None):
    """Source-only simulated display statistics: per-frame luma, saturation and change (no rendered frames)."""
    rows=[];previous=[None]
    def record(frame_time,shown):
        shown=np.clip(shown,0,1);luma=.2126*shown[...,0]+.7152*shown[...,1]+.0722*shown[...,2]
        mx=shown.max(-1);mn=shown.min(-1);saturation=np.where(mx>0,(mx-mn)/np.maximum(mx,1e-6),0)
        change=None if previous[0] is None else float(np.abs(luma-previous[0]).mean())
        rows.append({'time':frame_time,'mean_luma':float(luma.mean()),'mean_saturation':float(saturation.mean()),
                     'mean_abs_luma_change':change,'global_luma_jump':None if previous[0] is None else float(luma.mean()-previous[0].mean())})
        previous[0]=luma
    steps=int(round(seconds*fps))
    image,_,limitations=illustrate_field(summary,time=steps/fps,fps=fps,history_steps=steps,audio=audio,viewport=viewport,frame_callback=record)
    if not rows:record(steps/fps,image);limitations.append('simulation produced no per-frame rows; final display only')
    return rows,limitations


def _initial_canvas(flat,shape,*,time,fps,history_steps):
    """Feedback canvas before the first simulated frame. projectM clears it to black at preset load, so
    a history covering the whole time since load starts there (a cleared canvas can be an absorbing
    state, e.g. a shader dividing by a canvas sample). A shorter history stands in for the frames it
    omits with the flat-field steady state."""
    image=np.zeros((*shape,3),np.float32)
    if history_steps>=int(round(time*fps)):
        return image,'feedback content starts from the cleared (black) canvas, as at preset load'
    if isinstance(flat,dict) and isinstance(flat.get('state_rgb'),list):
        image[:]=np.array(flat['state_rgb'],np.float32)
        return image,'feedback content starts from the flat-field steady state'
    return image,None


def _stored(values):
    """Shader output as an RGBA8 target stores it: NaN (0*inf, inf-inf) as 0, infinities and other
    values clamped to [0, 1]."""
    return np.clip(np.nan_to_num(np.asarray(values,np.float32),nan=0.,posinf=1.,neginf=0.),0,1)


def illustrate_field(summary,*,time,fps,history_steps,audio=None,viewport=None,frame_callback=None):
    """Fact-driven feedback illustration: backward map, RGBA8 decay, waves, vectors, composite.

    viewport overrides the declared size (all geometry is resolution-independent); frame_callback,
    when given, receives (frame_time, displayed_image) after every simulated frame.
    """
    facts=_facts(summary)
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    if not isinstance(context.get('viewport'),list):raise ValueError('declared static-behaviour viewport is required')
    width,height=viewport or context['viewport']
    _DRAW_SCALE[0]=width/float(context['viewport'][0])
    aspect=(1.0,height/width) if width>=height else (width/height,1.0)
    limitations=[]
    # Stored canvas alpha starts cleared; it weights textured copies of the previous frame.
    canvas={'alpha':np.zeros((height,width),np.float32)}
    flat=facts.get('/analysis/visual_description/nonlinear_texture_colour_bounds/flat_field')
    image,note=_initial_canvas(flat,(height,width),time=time,fps=fps,history_steps=history_steps)
    if note:limitations.append(note)
    persistence=facts.get('/analysis/visual_description/static_behaviour/feedback_persistence') or {}
    decay=persistence.get('decay_gain');offset=0.;injection=None;main_coordinates=None
    frame_record=(facts.get('/analysis/visual_description/stage_programs') or {}).get('frame') or {}
    stepper=_FrameStepper(frame_record,constants=_render_constants(context)) if frame_record.get('status')=='exported' and (frame_record.get('state') or frame_record.get('outputs')) else None
    programs=(facts.get('/analysis/visual_description/stage_programs') or {}).get('stages') or {}
    warp_program=(programs.get('warp') or {}).get('program') if (programs.get('warp') or {}).get('status')=='exported' else None
    composite_program=(programs.get('composite') or {}).get('program') if (programs.get('composite') or {}).get('status')=='exported' else None
    diffuse=((facts.get('/analysis/visual_description/feedback_transfer') or {}).get('vertex_colour_binding') or {}).get('rgba')
    custom_warp=((facts.get('/analysis/visual_description/native_warp_recipe') or {}).get('shader_branch') not in (None,'legacy','unknown')
                 or (facts.get('/analysis/visual_description/feedback_transfer') or {}).get('source_model','').startswith('affine_previous'))
    transfer=facts.get('/analysis/visual_description/feedback_transfer') or {}
    context=facts.get('/analysis/visual_description/static_behaviour/context') or {}
    grid=context.get('mesh_grid') if isinstance(context.get('mesh_grid'),list) and len(context['mesh_grid'])==2 else MESH_GRID
    sample=_backward_map(facts.get('/analysis/visual_description/static_behaviour/mesh_field'),width,height,grid,
                         shader_topology=warp_program is not None or custom_warp)
    if sample is not None:limitations.append('motion evaluated at the %dx%d mesh vertices and interpolated over its triangles'%tuple(grid))
    if type(decay) not in (int,float) and type(transfer.get('uniform_content_gain')) in (int,float):
        # Custom warp: uniform-content gain of all previous-image sample sites plus the known constant
        # offset; blur sites are approximated by the same pixel and injected fields are omitted.
        decay=float(transfer['uniform_content_gain'])
        known=transfer.get('constant_offset_rgb') or transfer.get('constant_offset_rgb_excluding_injection')
        if isinstance(known,list) and len(known)==3 and None not in known:offset=np.array(known,np.float32)
        injection=_injection_lanes(transfer);main_coordinates=_main_coordinate_field(transfer)
        if main_coordinates is not None:limitations.append('main feedback sample uses the exported shader coordinate expression (image-driven displacement included)')
        limitations.append('custom warp approximated as uniform gain %.4g plus constant offset; blur sites read the same pixel'%decay+
                           ('; injected spatial fields evaluated per frame (seeded rand_frame stand-in)' if injection else '; injected spatial fields omitted'))
    if warp_program is not None and sample is not None:
        decay=1.  # the exported warp program supplies the full colour transfer below
        limitations.append('warp shader evaluated per pixel from its exported program (engine blur bank, noise stand-ins)')
    if sample is None or type(decay) not in (int,float):
        limitations.append('per-pixel field or decay not fully described: only the fresh drawing is shown');history_steps=0
    paths,wave_limits=_builtin_wave_paths(facts,aspect);limitations+=wave_limits
    dynamic_waves=_builtin_wave_dynamic(facts)
    if dynamic_waves:limitations.append('built-in waveforms drawn per frame from the declared reference PCM (projectM modes 0-9; wave alignment omitted)')
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
    held.update(_render_constants(context))
    textured=_textured_shapes(facts,held)
    wrap=True
    if textured:limitations.append('textured shapes redraw the previous frame through their polygon (GL texture orientation; audio-driven alpha/zoom held at band midpoints, so beat toggles are not shown)')
    if sprites or _dynamic_border_operators(facts,8,8,{}):limitations.append('borders and darken-centre blended into the feedback canvas every frame (time-varying border colours from the per-frame program)')
    if clouds:limitations.append('closed-form custom-wave point clouds drawn per frame (declared per-frame audio when given, else midpoints; wave per-frame state stepped from its exported recurrence; long-side square projection)')
    for path,(colour,note) in colours.items():limitations.append(path+': '+note)
    wave_alpha={path:_wave_alpha(facts,path,limitations) for path,_ in paths+dynamic_waves}
    _TERM_CONTEXT.pop('stage',None)
    warp_samples_blur='"canonical_texture": "blur' in json.dumps(warp_program) if warp_program is not None else False
    wave_states={};shape_states={}
    previous=image;vector_maps=None
    try:
        # history_steps rendered frames ending at the declared time (native frame k renders at (k+1)/fps).
        for frame in range(max(history_steps-1,0),-1,-1):
            # RenderContext::time is a float widened to PRJM_EVAL_F: equations see float32 time, which
            # decides ties such as a 0.1 s refractory test at exactly three frames.
            frame_time=float(np.float32(time-frame/fps))
            bands=None
            if audio is not None:
                # Native frame k renders at source time (k+1)/fps; nonlinear audio responses are evaluated
                # per frame instead of at band midpoints (E[f(bands)] differs from f(E[bands])).
                index=min(len(audio['frames'])-1,max(0,int(round(frame_time*fps))-1))
                bands=audio['frames'][index];held.update(bands)
            # Blur timing (MilkdropPreset::RenderFrame): blur textures are made from the previous frame's
            # buffer; a warp shader that samples blur reads last frame's update (two canvases back).
            if vector_maps is not None:
                # MilkdropPreset::RenderFrame draws motion vectors into the previous frame before warping it,
                # from the u/v map the previous warp wrote: they reach the screen only through one warp.
                # GLES has no line smoothing, so they are aliased 1 px lines (sub-pixel endpoints).
                marks=_motion_vector_marks(facts,sample,frame_time,width,height,vector_maps)
                if marks:
                    rows,cols=_gl_line_pixels(*np.array([[a[0],a[1],b[0],b[1]] for a,b,_ in marks]).T,width,height)
                    alpha=float(_mv_alpha(facts))
                    image=image.copy();image[rows,cols]=image[rows,cols]*(1-alpha)+np.array(marks[0][2],np.float32)*alpha
            older=previous;previous=image;canvas['previous_alpha']=canvas['alpha']
            # Per-frame base inputs, read by inlined per-frame graphs (e.g. a Q accumulating 30/fps per frame).
            # projectM's frame counter (m_frameCount) is 0 on the first rendered frame, which renders at
            # time 1/fps: frame k has frame = k and time (k+1)/fps.
            frame_number=max(0,int(round(frame_time*fps))-1)
            held.update(fps=float(fps),frame=float(frame_number),progress=0.,time=float(frame_time))
            if stepper is not None:
                held.update(stepper.step(frame_time,fps,{k:held[k] for k in BANDS if k in held},frame_number))
            # Shader programs and per-pixel terms inline Q graphs over start-of-frame state: their inputs
            # take those values.
            stage_controls={**held,**(stepper.start if stepper is not None else {})}
            _TERM_CONTEXT.update(rng=np.random.default_rng(104729+int(round(frame_time*fps))),
                                 bands={k:v for k,v in stage_controls.items() if isinstance(v,(int,float))})
            _TERM_CONTEXT['stage']=stage_controls
            if sample is not None and history_steps:
                map_x,map_y=sample(frame_time)
                vector_maps=(map_x,map_y)
                main_x,main_y=map_x,map_y
                if main_coordinates is not None:
                    try:main_x,main_y=_evaluate_injection(None,image,map_x,map_y,frame_time,int(round(frame_time*fps)),main_coordinates,
                                                          {k:held[k] for k in BANDS if k in held})
                    except Exception as error:  # noqa: BLE001 - fall back to the mesh map
                        limitations.append('shader sample coordinates not evaluated: '+str(error)[:120]);main_coordinates=None
                program_done=False
                if warp_program is not None:
                    try:
                        uv=np.stack([(map_x+.5)/width,(map_y+.5)/height,*np.meshgrid((np.arange(width)+.5)/width,(np.arange(height)+.5)/height)],axis=-1)
                        warped=_evaluate_stage(warp_program,image,uv,frame_time,fps,{k:v for k,v in held.items() if k in BANDS or (k[:1]=='q' and k[1:].isdigit())},diffuse,
                                                rand=_frame_rand(frame_time,fps),controls=stage_controls,blur_image=older if warp_samples_blur else previous)
                        image=_stored(warped)
                        image=np.round(image*255)/255
                        canvas['alpha']=np.ones_like(canvas['alpha'])
                        warped=image;program_done=True
                    except Exception as error:  # noqa: BLE001 - fall back to the transfer model
                        limitations.append('warp program not evaluated: '+str(error)[:120]);warp_program=None;warped=image*0
                if warp_program is None:
                    warped=cv2.remap(image,main_x.astype(np.float32),main_y.astype(np.float32),cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)*decay+offset
                if injection is not None and not program_done:
                    try:warped=warped+_evaluate_injection(injection,image,map_x,map_y,frame_time,int(round(frame_time*fps)),None,
                                                          {k:held[k] for k in BANDS if k in held})
                    except Exception as error:  # noqa: BLE001 - illustration degrades to the gain model
                        limitations.append('injected warp field not evaluated: '+str(error)[:120]);injection=None
                image=warped
                image=np.round(np.clip(image,0,1)*255)/255
                if custom_warp:
                    # MilkdropShader writes float4(ret.xyz, 1.0): a custom warp stores alpha 1 everywhere.
                    canvas['alpha']=np.ones_like(canvas['alpha'])
                else:
                    # The fixed warp multiplies by vec4(decay,decay,decay,1): stored alpha is resampled, not decayed.
                    canvas['alpha']=np.round(np.clip(cv2.remap(canvas['alpha'],map_x,map_y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE),0,1)*255)/255
            for path,points in paths:
                alpha,additive=wave_alpha[path]
                if alpha is None:continue
                pixels=[to_pixels(point) for point in points]
                colour=_wave_colour_at(facts,path,frame_time) or colours[path][0]
                layer=np.zeros_like(image);mask=np.zeros(image.shape[:2],np.float32)
                for a,b in zip(pixels,pixels[1:]):
                    ends=tuple(int(round(v)) for v in a),tuple(int(round(v)) for v in b)
                    cv2.line(layer,*ends,tuple(colour),1,cv2.LINE_AA);cv2.line(mask,*ends,1.0,1,cv2.LINE_AA)
                image,canvas['alpha']=_blend_wave_layer(image,canvas['alpha'],layer,mask,alpha,additive)
            for path,recipe in dynamic_waves:
                alpha,additive=wave_alpha[path]
                if alpha is None:continue
                material=facts.get(path.rsplit('/',1)[0]+'/wave_material') or {}
                # MaximizeColorsTextureSize: the viewport's long side unless lines are scaled above the reference.
                frame_alpha=_frame_wave_alpha(material,held,recipe.get('effective_mode'),max(width,height))
                if frame_alpha is not None:
                    gate=(material.get('native_draw_gate') or {}).get('threshold')
                    if type(gate) in (int,float) and frame_alpha<gate:continue
                    alpha=frame_alpha
                try:polylines,loop=_builtin_wave_frame(recipe,frame_time,int(round(frame_time*fps))-1,
                                                       {k:held[k] for k in BANDS if k in held},(width,height))
                except ValueError:continue
                colour=_frame_wave_colour(material,held) or _wave_colour_at(facts,path,frame_time) or _wave_colour(facts,path)[0]
                # Thick: LineRenderer draws four 1 px passes offset by one pixel (as is, +x, +x+y, +y in NDC,
                # y up on screen), each blended on its own, so pixels two passes cover receive the blend twice.
                # Scaled dots are drawn once as 2x2 blocks (Waveform.cpp: one iteration when lineScale > 0).
                for ox,oy in ([(0,0),(16,0),(16,-16),(0,-16)] if recipe.get('thick') and not recipe.get('dots') else [(0,0)]):
                    layer=np.zeros_like(image);mask=np.zeros(image.shape[:2],np.float32)
                    for points in polylines:
                        # Built-in wave NDC: column=(1+x)/2*W, row=(1-y)/2*H (y up on screen; native-ruler
                        # probe at wave_y .8 matches to the pixel).
                        px=(points[:,0]+1)/2*width;py=(1-points[:,1])/2*height
                        pixel=np.round(np.stack([px,py],-1)*16).astype(np.int32)
                        if recipe.get('dots'):
                            # MilkDrop's main-wave dots are 2x2 pixel blocks (GL point coverage).
                            cols,rows=_point_pixels(px,py,2,height)
                            for x0,y0 in zip(cols,rows):
                                for x in (x0,x0+1):
                                    for y in (y0,y0+1):
                                        if 0<=x<width and 0<=y<height:layer[y,x]=colour;mask[y,x]=1.
                        else:
                            cv2.polylines(layer,[pixel+[ox,oy]],bool(loop),tuple(float(c) for c in colour),1,cv2.LINE_8,4)
                            cv2.polylines(mask,[pixel+[ox,oy]],bool(loop),1.0,1,cv2.LINE_8,4)
                    image,canvas['alpha']=_blend_wave_layer(image,canvas['alpha'],layer,mask,alpha,additive)
            # Textured shapes sample the previous frame (the warp's input), not the warped canvas.
            rng=_FrameSiteRandom(np.random.default_rng(7919+int(round(frame_time*fps))))
            for shape_index,shape in enumerate(textured):
                recurrence=shape.get('frame_recurrence')
                for instance in range(shape.get('instances',1)):
                    held['instance']=float(instance)
                    if recurrence:
                        # Shape per-frame code runs once per instance; its variables persist across instances
                        # and frames. Controls read the start values; the update gives the next run's start.
                        state=shape_states.get(shape_index)
                        if state is None:state=shape_states[shape_index]={n:_eval_filled(e['initial'],{**held,'time':frame_time},rng) for n,e in recurrence['state'].items()}
                        for name,entry in recurrence['state'].items():
                            for alias in entry.get('inputs') or [name]:held[alias]=state[name]
                        values={**held,'time':frame_time}
                        shape_states[shape_index]={n:_eval_filled(e['update'],values,rng) for n,e in recurrence['state'].items()}
                    image,_=_draw_textured_shape(image,shape,frame_time,wrap,previous,canvas,rng)
            held.pop('instance',None)
            for index,(_,record) in enumerate(clouds):
                inputs=dict(bands or {})
                if record.get('frame_inputs'):
                    # Positions inline main per-frame graphs: start-of-frame state and base inputs; never
                    # written names read 0 (projectm-eval).
                    inputs={**{name:0. for name in record['frame_inputs']},
                            **{k:v for k,v in stage_controls.items() if isinstance(v,(int,float))},**inputs}
                if record.get('waveform_inputs'):
                    # value1/value2: this frame's declared reference PCM window, prepared as CustomWaveform does.
                    from source_point_colour import waveform_point_values
                    value1,value2=waveform_point_values(record['waveform_inputs'],int(record['sample_count']),max(0,int(round(frame_time*fps))-1))
                    inputs.update(value1=value1,value2=value2)
                recurrence=record.get('frame_recurrence')
                if recurrence:
                    from source_point_colour import initial_state,step_state,state_inputs
                    frame_index=max(0,int(round(frame_time*fps))-1);entry=wave_states.setdefault(index,{})
                    if 'state' not in entry:
                        entry['state']=initial_state(recurrence,{**record.get('held_inputs',{}),**inputs},rng);entry['frame']=0
                        if frame_index>0:limitations.append('custom-wave state pre-rolled with the first declared frame inputs')
                    while entry['frame']<frame_index:
                        entry['state']=step_state(recurrence,entry['state'],{**record.get('held_inputs',{}),**inputs},float(np.float32((entry['frame']+1)/fps)),entry['frame'],rng)
                        entry['frame']+=1
                    inputs.update(state_inputs(recurrence,entry['state']))
                points=record.get('point_recurrence')
                if points:
                    # Per-point state: evaluated point by point; the last point's value carries into the next frame.
                    from source_point_colour import point_state_series,initial_state
                    count=int(record['sample_count']);entry=wave_states.setdefault(index,{})
                    if 'point' not in entry:entry['point']=initial_state({'state':points['state']},{**record.get('held_inputs',{}),**inputs},rng)
                    base={**record.get('held_inputs',{}),**{k:v for k,v in inputs.items() if np.ndim(v)==0},'time':frame_time}
                    def point_inputs(j):
                        if j>=count:return None
                        values={**base,'sample':j/(count-1) if count>1 else 0.}
                        for name in ('value1','value2'):
                            if name in inputs and np.ndim(inputs[name]):values[name]=float(inputs[name][j])
                        return values
                    series,entry['point']=point_state_series(points,entry['point'],point_inputs,rng)
                    for name in points['state']:inputs[points['state_input_prefix']+name]=np.array([row[name] for row in series])
                    ends={points['state_input_prefix']+name:np.array([row[name] for row in series[1:]]+[entry['point'][name]]) for name in points['state']}
                else:ends=None
                try:image=_draw_points(image,record,frame_time,to_pixels,canvas,inputs,rng,ends)
                except ValueError as error:
                    # One undrawable point cloud is left out instead of stopping the whole illustration.
                    note='point cloud '+str(index)+' not drawn: '+str(error)
                    if note not in limitations:limitations.append(note)
                if recurrence:
                    # End of frame: this frame's per-frame update gives the next frame's start state.
                    entry['state']=step_state(recurrence,entry['state'],{**record.get('held_inputs',{}),**(bands or {})},frame_time,entry['frame'],rng)
                    entry['frame']+=1
            for alpha,colour in sprites+_dynamic_border_operators(facts,width,height,held):
                image=image*(1-alpha[...,None])+alpha[...,None]*colour
                canvas['alpha']=alpha*alpha+canvas['alpha']*(1-alpha)
            if frame_callback is not None:frame_callback(frame_time,_display(image,facts,frame_time,fps,[],previous))
        if _motion_vector_marks(facts,sample,time,width,height):limitations.append('motion vectors drawn from the illustrated backward map')
    except ValueError as error:
        limitations.append('field illustration stopped: '+str(error))
    mesh=facts.get('/analysis/visual_description/static_behaviour/mesh_field') or {}
    warp=((mesh.get('controls') or {}).get('warp') or {}).get('value_range')
    if isinstance(warp,list) and warp!=[0.0,0.0] and not mesh.get('procedural_warp_parameters'):
        limitations.append('legacy procedural warp (amplitude 0.0035*warp per step) omitted')
    if _UNRESOLVED_TERMS:
        limitations.append('mesh terms held at range midpoint or zero: '+', '.join(sorted(_UNRESOLVED_TERMS)));_UNRESOLVED_TERMS.clear()
    image=_display(image,facts,time,fps,limitations,previous)
    limitations.append('closed-form time colours are evaluated per frame; other colours and audio-driven uniform terms use range midpoints; waveform audio wiggle omitted')
    return image,[path for path,_ in paths]+[str(identity) for identity,_ in clouds],limitations


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('summary',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--time',type=float,default=5.0,help='declared source time in seconds')
    parser.add_argument('--history-steps',type=int,default=150)
    parser.add_argument('--audio',type=Path,help='declared per-frame bands (milk-audio-inputs report) instead of band midpoints')
    args=parser.parse_args(argv)
    if args.output.exists():parser.error('output exists; frozen predictions are never overwritten')
    data=args.summary.read_bytes();summary=json.loads(data)
    if summary.get('policy')!='preset-understanding-v1':parser.error('preset-understanding-v1 summary required')
    fps=float(_facts(summary).get('/analysis/visual_description/static_behaviour/context',{}).get('feedback_fps',30))
    # The per-pixel field simulation covers feedback, shaders, shapes and waves; the closed-form orbit
    # illustrator is the fallback when the field or decay is not described.
    audio=declared_audio(args.audio) if args.audio else None
    image,used,limitations=illustrate_field(summary,time=args.time,fps=fps,history_steps=args.history_steps,audio=audio)
    if audio:limitations.append('audio-driven controls use the declared per-frame bands (audio report sha256 %s)'%audio['sha256'][:16])
    if any(l.startswith('per-pixel field or decay not fully described') for l in limitations):
        fallback=illustrate(summary,time=args.time,fps=fps,history_steps=args.history_steps)
        if fallback[1]:image,used,limitations=fallback
    rgb=(np.clip(image,0,1)*255+.5).astype(np.uint8)
    cv2.imwrite(str(args.output),cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR))
    identity={'policy':POLICY,'summary_sha256':hashlib.sha256(data).hexdigest(),
        'illustrator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'image_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'declared_time_seconds':args.time,
        'history_steps':args.history_steps,'drawn_components':used,'limitations':limitations+[
            'Illustration of frozen source facts, not a renderer: smoothing, exact raster, audio-driven waveform shape, additive waves and wave alpha are omitted',
            'Content older than history_steps, including permanent floor residue, is omitted'],
        'uses_rendered_images':False,'uses_equation_execution':False,'reads_preset_source':False,
        'evaluates_exported_closed_form_graphs':True,
        'graph_evaluation_scope':'exported sample/time/audio point programs, shape controls and per-pixel warp terms; no preset frames are executed',
        'declared_audio_sha256':(audio or {}).get('sha256') if 'audio' in locals() else None}
    args.output.with_suffix('.json').write_text(json.dumps(identity,indent=2)+'\n')
    print(json.dumps(identity))


if __name__=='__main__':
    main()
