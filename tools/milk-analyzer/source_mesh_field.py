"""Structure of per-pixel (mesh) warp control fields, from source graphs only.

Each native warp control (zoom, rot, warp, cx, cy, dx, dy, sx, sy) is a pure
per-vertex formula of mesh coordinates (x, y, rad, ang), audio, time and
uniform inputs. This pass decomposes each into:

- coordinate gates: ``select`` branches whose predicate is a threshold on one
  mesh coordinate become interval regions (for example a band 0.35<y<0.65);
- signed additive terms: constants, uniform audio/time terms (bounded with
  declared input domains), coordinate-affine terms and spatial oscillators
  sin/cos(kx*x+ky*y+kr*rad+ka*ang+w*t+phi) with wavelength and phase velocity;
- motion semantics using the pinned engine convention, in per-pixel units: the
  backward map is B(c)=cx+(0.5+(c-0.5)/z^(e^(2rad-1))-cx)/sx (rotated about
  (cx,cy)) minus d(c). Zoom acts about the screen centre; cx/cy centre stretch
  and rotation only. Retained content moves +dx right and +dy down (y=0 top);
  zoom<1 contracts. With z uniform, zoomexp 1, no rotation and a same-axis
  affine d=a+b*c the slope is k=1/(z*s_axis)-b, features scale by 1/k per step
  and the fixed line solves c=B(c).

No equations are executed per frame; nominal real algebra over the source graph
only. Results are not visible motion, coverage or mood certificates.
"""
from fractions import Fraction
import math

POLICY='source-mesh-field-structure-v1'
CONTROLS=('zoom','zoomexp','rot','warp','cx','cy','dx','dy','sx','sy')
COORDINATES=('x','y','rad','ang')
AUDIO={'bass','mid','treb','bass_att','mid_att','treb_att','vol','vol_att'}
TIME={'time','frame','progress','fps'}
COMPARISONS={'less':'<','greater':'>','less_equal':'<=','greater_equal':'>='}
MAX_NODES=4096
MAX_TERMS=64
MAX_REGIONS=32


class _Budget(ValueError):
    pass


def _aspect(context):
    """Native aspect factors: the shorter side is scaled so x/y units are isotropic."""
    viewport=(context or {}).get('viewport')
    if not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or any(type(v) is not int or v<=0 for v in viewport):
        raise ValueError('mesh field geometry requires an explicit declared viewport')
    width,height=viewport
    return (1.0,height/width) if width>=height else (width/height,1.0),max(width,height)


def _domains(aspect):
    ax,ay=aspect
    return {'x':(0.5-0.5*ax,0.5+0.5*ax),'y':(0.5-0.5*ay,0.5+0.5*ay),
            'rad':(0.0,math.hypot(ax,ay)),'ang':(-math.pi,math.pi)}


def _name(node):
    return node.detail.get('name','') if node.op=='input' else None


def _coordinate(node):
    name=_name(node)
    return name if name in COORDINATES and node.detail.get('native_mesh_reset_input') is True else None


def _dependencies(node,seen=None):
    seen={} if seen is None else seen
    if id(node) in seen:return seen[id(node)]
    if len(seen)>MAX_NODES:raise _Budget('mesh field dependency budget exceeded')
    deps={'coordinates':set(),'audio':set(),'time':set(),'q':set(),'other':set(),'unsupported_ops':set()}
    seen[id(node)]=deps
    if node.op=='input':
        name=_name(node)
        if _coordinate(node):deps['coordinates'].add(name)
        elif name in AUDIO:deps['audio'].add(name)
        elif name in TIME:deps['time'].add(name)
        elif name.startswith('q') and name[1:].isdigit():deps['q'].add(name)
        else:deps['other'].add(name)
    from source_warp_transport import PURE
    if node.op not in PURE:deps['unsupported_ops'].add(node.op)
    for child in node.args:
        for key,values in _dependencies(child,seen).items():deps[key]|=values
    return deps


def _linear(node,memo=None):
    """Affine form over mesh coordinates and time with exact constant coefficients."""
    memo={} if memo is None else memo
    if id(node) in memo:return memo[id(node)]
    if len(memo)>MAX_NODES:raise _Budget('mesh field linear-form budget exceeded')
    result=None
    if node.op=='constant':
        value=node.detail.get('value')
        if type(value) in (int,float) and math.isfinite(value):result={'const':Fraction(value)}
    elif node.op=='input':
        name=_coordinate(node) or (_name(node) if _name(node)=='time' else None)
        if name:result={name:Fraction(1),'const':Fraction(0)}
    elif node.op in ('add','subtract') and len(node.args)==2:
        a,b=(_linear(arg,memo) for arg in node.args)
        if a is not None and b is not None:
            sign=1 if node.op=='add' else -1
            result=dict(a)
            for key,value in b.items():result[key]=result.get(key,Fraction(0))+sign*value
    elif node.op=='negate' and len(node.args)==1:
        a=_linear(node.args[0],memo)
        if a is not None:result={key:-value for key,value in a.items()}
    elif node.op=='multiply' and len(node.args)==2:
        a,b=(_linear(arg,memo) for arg in node.args)
        if a is not None and b is not None:
            if set(a)=={'const'}:a,b=b,a
            if set(b)=={'const'}:result={key:value*b['const'] for key,value in a.items()}
    elif node.op in ('divide','eel_divide') and len(node.args)==2:
        a,b=(_linear(arg,memo) for arg in node.args)
        if a is not None and b is not None and set(b)=={'const'} and b['const']!=0:
            result={key:value/b['const'] for key,value in a.items()}
    memo[id(node)]=result
    return result


def _terms(node,sign=1,depth=0):
    if depth>64:raise _Budget('mesh field term depth exceeded')
    if node.op=='add' and len(node.args)==2:
        return _terms(node.args[0],sign,depth+1)+_terms(node.args[1],sign,depth+1)
    if node.op=='subtract' and len(node.args)==2:
        return _terms(node.args[0],sign,depth+1)+_terms(node.args[1],-sign,depth+1)
    if node.op=='negate' and len(node.args)==1:return _terms(node.args[0],-sign,depth+1)
    return [(sign,node)]


def _factors(node,depth=0):
    if depth>64:raise _Budget('mesh field factor depth exceeded')
    if node.op=='multiply' and len(node.args)==2:
        return _factors(node.args[0],depth+1)+_factors(node.args[1],depth+1)
    return [node]


def _predicate(node):
    """Single-coordinate threshold: returns (coordinate, interval_true) or None."""
    if node.op not in COMPARISONS or len(node.args)!=2:return None
    left,right=(_linear(arg) for arg in node.args)
    if left is None or right is None:return None
    difference={key:left.get(key,Fraction(0))-right.get(key,Fraction(0)) for key in set(left)|set(right)}
    variables=[key for key,value in difference.items() if key!='const' and value!=0]
    if len(variables)!=1 or variables[0] not in COORDINATES:return None
    coordinate=variables[0];c=difference[coordinate];k=difference.get('const',Fraction(0))
    threshold=-k/c
    less=node.op in ('less','less_equal')
    if c<0:less=not less
    interval=(-math.inf,float(threshold)) if less else (float(threshold),math.inf)
    return coordinate,interval


def _intersect(box,coordinate,interval):
    low,high=box.get(coordinate,(-math.inf,math.inf))
    return {**box,coordinate:(max(low,interval[0]),min(high,interval[1]))}


def _complement(interval):
    low,high=interval
    return (high,math.inf) if low==-math.inf else (-math.inf,low)


def _is_zero(node):
    linear=_linear(node)
    return linear is not None and all(value==0 for value in linear.values())


def _envelope(node,domains):
    from source_control_bounds import scalar_value_envelope
    try:
        span=scalar_value_envelope(node,input_domains=domains).get('nominal_value_range')
    except (ValueError,ArithmeticError,RecursionError):
        return None
    return None if span is None else [float(span[0]),float(span[1])]


def _oscillator(node,scale,aspect):
    """sin/cos of an affine coordinate/time argument, with travel semantics."""
    if node.op not in ('sin','cos') or len(node.args)!=1:return None
    argument=_linear(node.args[0])
    if argument is None:return None
    k={name:argument.get(name,Fraction(0)) for name in COORDINATES}
    if all(value==0 for value in k.values()):return None
    omega=argument.get('time',Fraction(0))
    row={'function':node.op,'coordinate_coefficients':{name:float(value) for name,value in k.items() if value!=0},
         'time_coefficient_radians_per_second':float(omega),'phase_radians':float(argument.get('const',Fraction(0))),
         'planar_wavelength_units':None,'planar_wavelength_pixels':None,'travel_direction_xy':None,
         'phase_speed_units_per_second':None,'phase_speed_pixels_per_second':None,
         'angular_lobes':None,'angular_rotation_radians_per_second':None,
         'radial_wavelength_rad_units':None,'radial_wavelength_pixels':None,'radial_phase_speed_pixels_per_second':None,
         'pattern':None}
    planar=float(math.hypot(k['x'],k['y']));kr=float(k['rad']);ka=float(k['ang'])
    if planar and not kr and not ka:
        # Constant phase: k.c = -w*t + const, so the pattern moves along k-hat at -w/|k|.
        speed=-float(omega)/planar
        direction=[float(k['x'])/planar,float(k['y'])/planar]
        row.update(pattern='planar_travelling_wave' if omega else 'planar_standing_pattern',
            planar_wavelength_units=2*math.pi/planar,planar_wavelength_pixels=2*math.pi/planar*scale,
            travel_direction_xy=direction,phase_speed_units_per_second=speed,
            phase_speed_pixels_per_second=speed*scale)
    elif kr and not planar and not ka:
        speed=-float(omega)/kr
        # rad=1 is half the long side, so rad units scale by scale/2 pixels.
        row.update(pattern='radial_ring_wave' if omega else 'radial_standing_rings',
            radial_wavelength_rad_units=2*math.pi/abs(kr),radial_wavelength_pixels=2*math.pi/abs(kr)*scale/2,
            radial_phase_speed_pixels_per_second=speed*scale/2)
    elif ka and not planar and not kr:
        row.update(pattern='angular_lobes' if float(ka).is_integer() else 'angular_modulation_with_seam',angular_lobes=abs(ka),
            angular_rotation_radians_per_second=-float(omega)/ka if omega else 0.0,
            angular_lobes_integer=float(ka).is_integer())
    else:row['pattern']='mixed_coordinate_oscillator'
    return row


def _classify(sign,node,domains,scale,aspect,depth):
    deps=_dependencies(node)
    row={'sign':sign,'kind':'unclassified','dependencies':{key:sorted(value) for key,value in deps.items() if value}}
    if deps['other'] or deps['unsupported_ops']:
        row['kind']='unresolved_inputs'
        # Keep the bounded graph (random calls, state or unsupported inputs remain explicit in it).
        from source_appearance import _expression
        row['expression']=_expression(node)
        return row
    linear=_linear(node)
    if not deps['coordinates']:
        value=_envelope(node,domains)
        if linear is not None and set(linear)=={'const'}:
            row.update(kind='constant',value=sign*float(linear['const']))
        else:
            row.update(kind='uniform',value_range=None if value is None else sorted([sign*value[0],sign*value[1]]))
            if deps['audio'] or deps['time']:
                # Per-frame audio/time value: keep the bounded graph for declared-input evaluation.
                from source_appearance import _expression
                row['expression']=_expression(node)
        return row
    if linear is not None and all(value==0 for key,value in linear.items() if key!='const'):
        row.update(kind='constant',value=sign*float(linear.get('const',Fraction(0))))
        return row
    if linear is not None:
        row.update(kind='coordinate_affine',coefficients={key:sign*float(value) for key,value in linear.items()
                                                          if key!='const' and value!=0},
                   constant=sign*float(linear.get('const',Fraction(0))))
        return row
    if node.op=='select' and len(node.args)==3:
        gate=_predicate(node.args[0])
        if gate is not None and depth<8:
            coordinate,interval=gate
            row.update(kind='coordinate_gated',coordinate=coordinate,
                branches=[{'interval':_finite(interval),'terms':_decompose(node.args[1],domains,scale,aspect,depth+1,sign)},
                          {'interval':_finite(_complement(interval)),'terms':_decompose(node.args[2],domains,scale,aspect,depth+1,sign)}])
            return row
    factors=_factors(node)
    oscillators=[f for f in factors if _oscillator(f,scale,aspect) is not None]
    rest=[f for f in factors if f not in oscillators]
    if len(oscillators)==1 and all(not _dependencies(f)['coordinates'] for f in rest):
        osc=_oscillator(oscillators[0],scale,aspect)
        amplitude=[1.0,1.0]
        for factor in rest:
            span=_envelope(factor,domains)
            if span is None:amplitude=None;break
            products=[amplitude[i]*span[j] for i in (0,1) for j in (0,1)]
            amplitude=[min(products),max(products)]
        row.update(kind='spatial_oscillator',oscillator=osc,
            amplitude_range=None if amplitude is None else sorted([sign*amplitude[0],sign*amplitude[1]]),
            amplitude_dependencies=sorted(set().union(*(_dependencies(f)['audio']|_dependencies(f)['time']|_dependencies(f)['q'] for f in rest))) if rest else [])
        return row
    affine=[f for f in factors if _dependencies(f)['coordinates'] and _linear(f) is not None]
    if len(affine)==1 and all(not _dependencies(f)['coordinates'] for f in factors if f is not affine[0]):
        # Uniform (audio/time/q) factor times an affine coordinate form.
        scale_range=[1.0,1.0]
        for factor in (f for f in factors if f is not affine[0]):
            span=_envelope(factor,domains)
            if span is None:scale_range=None;break
            products=[scale_range[i]*span[j] for i in (0,1) for j in (0,1)]
            scale_range=[min(products),max(products)]
        linear=_linear(affine[0])
        coefficients={}
        for key,value in linear.items():
            if key=='const' or value==0 or scale_range is None:continue
            ends=[sign*float(value)*scale_range[0],sign*float(value)*scale_range[1]]
            coefficients[key]=[min(ends),max(ends)]
        row.update(kind='uniform_scaled_coordinate_affine',coefficient_ranges=coefficients if scale_range else None,
            scale_dependencies=sorted(set().union(*(_dependencies(f)['audio']|_dependencies(f)['time']|_dependencies(f)['q']
                                                     for f in factors if f is not affine[0]))))
        return row
    row['kind']='nonlinear_coordinate_term'
    # Keep the bounded source graph so consumers can evaluate the term per mesh point;
    # the contribution is sign * expression (inputs x, y, rad, ang and uniform inputs).
    from source_appearance import _expression
    row['expression']=_expression(node)
    return row


def _finite(interval):
    return [None if math.isinf(interval[0]) else interval[0],None if math.isinf(interval[1]) else interval[1]]


def _decompose(node,domains,scale,aspect,depth=0,sign=1):
    terms=_terms(node,sign)
    if len(terms)>MAX_TERMS:raise _Budget('mesh field term budget exceeded')
    rows=[]
    for term_sign,term in terms:
        if term.op=='constant' and _is_zero(term):continue
        rows.append(_classify(term_sign,term,domains,scale,aspect,depth))
    return rows


def _regions(terms,box=None,depth=0):
    """Expand coordinate gates into disjoint boxes, each with its active terms."""
    box={} if box is None else box
    regions=[{'box':box,'terms':[]}]
    for term in terms:
        if term['kind']!='coordinate_gated':
            for region in regions:region['terms'].append(term)
            continue
        split=[]
        for region in regions:
            for branch in term['branches']:
                low,high=branch['interval']
                interval=(-math.inf if low is None else low,math.inf if high is None else high)
                child=_intersect(region['box'],term['coordinate'],interval)
                for sub in _regions(branch['terms'],child,depth+1):
                    split.append({'box':sub['box'],'terms':region['terms']+sub['terms']})
        if len(split)>MAX_REGIONS:raise _Budget('mesh field region budget exceeded')
        regions=split
    return regions


def _screen_fraction(box,domains):
    fraction=1.0
    for coordinate in ('x','y'):
        if coordinate not in box:continue
        low,high=domains[coordinate];a,b=box[coordinate]
        fraction*=max(0.0,min(high,b)-max(low,a))/(high-low)
    return fraction if all(c in ('x','y') for c in box) else None


def _thin_line(scale_step):
    magnitude=min(1.0,abs(scale_step))
    mean_peak=magnitude if magnitude<=.5 else 1-1/(4*magnitude)
    return magnitude,mean_peak


def _composition(control,controls):
    """Uniform zoom/stretch/centre for one axis, or the reason it is unresolved."""
    axis='x' if control=='dx' else 'y'
    def constant(name):
        row=controls.get(name) or {}
        span=row.get('value_range')
        if row.get('uniform_across_mesh') is not True or not isinstance(span,list) or None in span:return None
        return span
    zoom=constant('zoom');exponent=constant('zoomexp');stretch=constant('sx' if axis=='x' else 'sy')
    centre=constant('cx' if axis=='x' else 'cy');rotation=constant('rot');warp=constant('warp')
    if None in (zoom,exponent,stretch,centre,rotation,warp):return None,'zoom/stretch/centre/rotation/warp are not uniform bounded controls'
    if exponent!=[1.0,1.0]:return None,'zoomexp is not 1: zoom varies with radius'
    if rotation!=[0.0,0.0]:return None,'nonzero rotation couples the axes'
    if warp!=[0.0,0.0]:return None,'procedural warp adds oscillating displacement'
    if centre[0]!=centre[1] or stretch[0]!=stretch[1]:return None,'stretch/centre vary'
    if zoom[0]<=0 or stretch[0]==0:return None,'nonpositive zoom or zero stretch'
    return {'zoom_range':zoom,'stretch':stretch[0],'centre':centre[0]},None


def _axis_summary(control,region,domains,scale,fps,controls):
    """Per-step content motion along one axis for dx/dy within a region."""
    axis='x' if control=='dx' else 'y'
    other='y' if axis=='x' else 'x'
    low=high=0.0;b=0.0;cross=0.0;open_terms=[]
    for term in region['terms']:
        if term['kind']=='constant':low+=term['value'];high+=term['value']
        elif term['kind']=='uniform':
            span=term.get('value_range')
            if span is None:open_terms.append('unbounded uniform term');continue
            low+=span[0];high+=span[1]
        elif term['kind']=='coordinate_affine':
            coefficients=term['coefficients']
            if 'time' in coefficients:open_terms.append('time-growing offset')
            if set(coefficients)-{axis,other,'time'}:open_terms.append('radius/angle dependence');continue
            low+=term['constant'];high+=term['constant'];b+=coefficients.get(axis,0.0);cross+=coefficients.get(other,0.0)
        elif term['kind']=='spatial_oscillator':continue
        else:open_terms.append(term['kind'])
    row={'offset_range':[low,high],'same_axis_coefficient':b,'cross_axis_coefficient':cross,
         'translation_pixels_per_step_range':None,'translation_pixels_per_second_range':None,
         'raw_feature_scale_per_step':None,'composed_feature_scale_per_step_range':None,'fixed_point_range':None,
         'thin_line_integrated_fraction_per_step':None,'thin_line_mean_first_step_peak':None,
         'composition':None,'behaviour':None,'open_terms':open_terms}
    if open_terms:return row
    if b and b!=1:row['raw_feature_scale_per_step']=1/(1-b)
    composed,reason=_composition(control,controls)
    row['composition']=reason or 'uniform zoom about the screen centre and axis stretch folded in'
    if composed is None:
        if not b and not cross:
            row.update(translation_pixels_per_step_range=[low*scale,high*scale],
                       translation_pixels_per_second_range=[low*scale*fps,high*scale*fps] if fps else None,
                       behaviour='translation_component')
        return row
    stretch,centre=composed['stretch'],composed['centre']
    # k=1/(z*stretch)-b is monotone in z, but 1/k and the fixed point have poles
    # where k crosses 0 (degenerate sampling) or 1 (pure translation: no fixed
    # line). Corner values are valid only when neither pole lies in the range.
    z_low,z_high=composed['zoom_range']
    k_values=sorted(1/(z*stretch)-b for z in (z_low,z_high))
    if k_values[0]<=0<=k_values[1]:
        row['behaviour']='degenerate_sampling_possible';return row
    if k_values[0]<1<k_values[1]:
        row['behaviour']='compression_or_expansion_through_translation'
        row['composition']+='; zoom range includes the pure-translation case, so no single fixed line'
        return row
    scales=[];fixed=[]
    for z in composed['zoom_range']:
        # B(c)=centre+(0.5+(c-0.5)/z-centre)/stretch-(a+b*c): slope k, offset m.
        k=1/(z*stretch)-b
        for a in (low,high):
            m=centre+(0.5-0.5/z-centre)/stretch-a
            if k==0:scales.append(math.inf);continue
            scales.append(1/k)
            if k!=1:fixed.append(m/(1-k))
    if any(math.isinf(v) for v in scales):row['behaviour']='degenerate_sampling';return row
    row['composed_feature_scale_per_step_range']=[min(scales),max(scales)]
    if fixed and len(fixed)==len(scales):row['fixed_point_range']=[min(fixed),max(fixed)]
    identity=all(abs(v-1)<1e-12 for v in scales)
    if identity:
        if low or high:
            row.update(translation_pixels_per_step_range=[low*scale,high*scale],
                       translation_pixels_per_second_range=[low*scale*fps,high*scale*fps] if fps else None,
                       behaviour='uniform_translation')
    else:
        smallest=min(abs(v) for v in scales);largest=max(abs(v) for v in scales)
        if largest<1:row['behaviour']='compression_toward_fixed_line'
        elif smallest>1:row['behaviour']='expansion_from_fixed_line'
        else:row['behaviour']='compression_or_expansion'
        if all(v<0 for v in scales):row['behaviour']+='_with_mirror'
        if largest<1:
            fraction,_=_thin_line(largest);_,peak=_thin_line(largest)
            row.update(thin_line_integrated_fraction_per_step=fraction,thin_line_mean_first_step_peak=peak)
    if cross:row['behaviour']=(row['behaviour']+'+' if row['behaviour'] else '')+'shear'
    return row


def mesh_field_structure(analysis,context=None):
    """Describe every native per-pixel warp control field; see module docstring."""
    from scene_equations import _scalar
    result={'policy':POLICY,'status':'unknown','controls':{},'patterns':[],'per_pixel_equations_present':None,
        'pixel_scale':None,'coordinate_domains':None,'visible_motion_speed':None,'native_numeric_certified':False,
        'uses_equation_execution':False,'uses_rendered_images':False,'whole_preset_activity_credit':False,
        'unknown_reasons':[],
        'conditions':['Engine convention: zoom acts about the screen centre; stretch and rotation about (cx, cy); then the warp samples (u-dx, v-dy); retained content moves +dx right and +dy down (y=0 top) per feedback step',
            'Zoom is z^(zoomexp^(2*rad-1)) per vertex; it is uniform only when zoomexp is 1',
            'Per-pixel x/y are aspect-corrected: both measure the long side, so 1 unit is max(width, height) pixels; rad=1 is half the long side',
            'Coordinate gates are single-coordinate thresholds; boundary strictness, mesh interpolation between vertices and texel sampling are not resolved',
            'Uniform audio/time ranges use declared input domains, not observed music; oscillator speeds are nominal phase velocities of a control field, not visible feature speeds',
            'Fields act on the sampling map each feedback step; displayed motion also depends on content, decay, shaders and composition',
            'Compression by s per step scales a line\'s integrated intensity by |s| per step (its peak too once it is about a texel wide); a fresh sharp line\'s phase-averaged first-step peak is |s| for |s|<=1/2 and 1-1/(4|s|) above; expansion keeps integrated intensity']}
    try:
        aspect,scale=_aspect(context)
        domains=_domains(aspect)
        result.update(pixel_scale=scale,coordinate_domains={k:list(v) for k,v in domains.items()})
        fps=(context or {}).get('feedback_fps')
        from source_motion_behaviour import _effective_domains
        declared=dict(_effective_domains(analysis,context))
        envelope_domains={**declared,**{name:list(span) for name,span in domains.items()}}
        controls=getattr(analysis,'mesh_controls',None) or {}
        result['per_pixel_equations_present']=bool(analysis.source.get('per_pixel_equations') or
                                                   any(k.startswith('per_pixel_') for k in analysis.source))
        for control in CONTROLS:
            field=controls.get(control)
            row={'status':'unknown','uniform_across_mesh':None,'dependencies':None,'terms':None,
                 'value_range':None,'regions':None,'unknown_reasons':[]}
            result['controls'][control]=row
            if field is None:
                row['unknown_reasons'].append('control field absent from the native inventory');continue
            try:
                deps=_dependencies(field)
                row['dependencies']={key:sorted(value) for key,value in deps.items() if value}
                row['uniform_across_mesh']=not deps['coordinates']
                row['terms']=_decompose(field,declared,scale,aspect)
                row['value_range']=_envelope(field,envelope_domains)
                regions=_regions(row['terms'])
                row['regions']=[{'box':{k:_finite(v) for k,v in region['box'].items()},
                                 'screen_fraction':_screen_fraction(region['box'],domains),'terms':region['terms']}
                                for region in regions if all(a<b for a,b in region['box'].values())]
                row['status']='described'
            except (_Budget,RecursionError) as error:row['unknown_reasons'].append(str(error))
        for control in ('dx','dy'):
            row=result['controls'][control]
            for region in row.get('regions') or []:
                region['axis_motion']=_axis_summary(control,region,domains,scale,fps,result['controls'])
        result['patterns']=_patterns({**result['controls'],'_rad_max':domains['rad'][1]},scale,fps)
        result['status']='described' if all(r['status']=='described' for r in result['controls'].values()) else 'partial'
    except (ValueError,TypeError,KeyError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def scale_domains_rad(controls):
    return controls.get('_rad_max',math.sqrt(2))


def _radial_zoom_samples(zoom,exponent,rad_max,grid=48):
    """Effective zoom z(rad)^(e^(2rad-1)) when z is constant+uniform+affine-in-rad terms and e is uniform.

    Uniform terms take both endpoints of their declared ranges; the screen
    mean averages a uniform grid over the viewport (rad=1 is half the long
    side, so rad_max fixes the aspect). Returns (min, max, mean) or None.
    """
    if not exponent.get('uniform_across_mesh') or not isinstance(exponent.get('value_range'),list) or None in exponent['value_range']:return None
    constant=0.;slope=0.;uniform=[0.,0.]
    for term in zoom.get('terms') or []:
        kind=term.get('kind')
        if kind=='constant':constant+=term['value']
        elif kind=='uniform' and isinstance(term.get('value_range'),list) and None not in term['value_range']:
            uniform[0]+=term['value_range'][0];uniform[1]+=term['value_range'][1]
        elif kind=='coordinate_affine' and set(term.get('coefficients') or {})<={'rad'}:
            constant+=term.get('constant',0.);slope+=term['coefficients'].get('rad',0.)
        else:return None
    aspect=math.sqrt(max(0.,rad_max*rad_max-1))
    values=[];means=[]
    for e in exponent['value_range']:
        if e<=0:return None
        for u in uniform:
            total=0.;count=0
            for i in range(grid):
                for j in range(max(1,round(grid*aspect))):
                    x=(i+.5)/grid*2-1;y=((j+.5)/max(1,round(grid*aspect))*2-1)*aspect
                    r=math.hypot(x,y);z=constant+slope*r+u
                    if z<=0:return None
                    value=z**(e**(2*r-1));values.append(value);total+=value;count+=1
            means.append(total/count)
    return min(values),max(values),sum(means)/len(means)


def _patterns(controls,scale,fps):
    """Readable pattern records derived from the per-control decomposition."""
    rows=[]
    zoom=controls.get('zoom',{});exponent=controls.get('zoomexp',{})
    if (zoom.get('status')=='described' and zoom.get('uniform_across_mesh') and zoom.get('value_range') and
            exponent.get('uniform_across_mesh') and isinstance(exponent.get('value_range'),list) and None not in exponent['value_range']):
        low,high=zoom['value_range'];e_low,e_high=exponent['value_range']
        if not (low==high==1.0) and low>0 and e_low>0:
            # Effective per-vertex zoom z^(e^(2rad-1)) over rad in [0, rad_max].
            rad_max=max(scale_domains_rad(controls),0.0)
            powers=[e**(2*r-1) for e in (e_low,e_high) for r in (0.0,rad_max)]
            effective=[z**q for z in (low,high) for q in powers]
            lo,hi=min(effective),max(effective)
            rows.append({'pattern':'uniform_zoom' if e_low==e_high==1.0 else 'radial_zoom_profile','control':'zoom',
                'value_range':[low,high],'zoomexp_range':[e_low,e_high],'effective_zoom_range':[lo,hi],
                'content_motion':'contracts toward the screen centre' if hi<1 else 'expands from the screen centre' if lo>1 else 'contracts or expands',
                'percent_per_step_range':[(lo-1)*100,(hi-1)*100],
                'thin_line_integrated_fraction_per_step_range':[min(1.0,lo),min(1.0,hi)],
                'audio_inputs':zoom['dependencies'].get('audio',[])})
    elif zoom.get('status')=='described' and not zoom.get('uniform_across_mesh'):
        profile=_radial_zoom_samples(zoom,exponent,scale_domains_rad(controls))
        if profile is not None:
            lo,hi,mean=profile
            rows.append({'pattern':'radial_zoom_profile','control':'zoom','value_range':zoom.get('value_range'),
                'zoomexp_range':exponent.get('value_range'),'effective_zoom_range':[lo,hi],'zoom_varies_with':'rad',
                'content_motion':'contracts toward the screen centre' if hi<1 else 'expands from the screen centre' if lo>1 else 'contracts or expands',
                'percent_per_step_range':[(lo-1)*100,(hi-1)*100],'screen_mean_percent_per_step':(mean-1)*100,
                'thin_line_integrated_fraction_per_step_range':[min(1.0,lo),min(1.0,hi)],
                'audio_inputs':zoom['dependencies'].get('audio',[])})
        else:
            rows.append({'pattern':'spatially_varying_zoom','control':'zoom','coordinates':zoom['dependencies'].get('coordinates',[]),
                         'value_range':zoom.get('value_range')})
    rot=controls.get('rot',{})
    if rot.get('status')=='described' and rot.get('value_range') and rot['value_range']!=[0.0,0.0]:
        rows.append({'pattern':'uniform_rotation' if rot.get('uniform_across_mesh') else 'spatially_varying_rotation',
                     'control':'rot','value_range_radians_per_step':rot['value_range'],
                     'coordinates':rot['dependencies'].get('coordinates',[]),'audio_inputs':rot['dependencies'].get('audio',[])})
    for control in ('dx','dy'):
        row=controls.get(control,{})
        if row.get('status')!='described':continue
        for region in row.get('regions') or []:
            motion=region.get('axis_motion') or {}
            if motion.get('behaviour'):
                rows.append({'pattern':motion['behaviour'],'control':control,'region':region['box'],
                             'screen_fraction':region['screen_fraction'],**{k:motion[k] for k in
                             ('offset_range','same_axis_coefficient','cross_axis_coefficient','fixed_point_range',
                              'raw_feature_scale_per_step','composed_feature_scale_per_step_range',
                              'thin_line_integrated_fraction_per_step','thin_line_mean_first_step_peak','composition',
                              'translation_pixels_per_step_range','translation_pixels_per_second_range')}})
            for term in region['terms']:
                if term['kind']=='spatial_oscillator':
                    rows.append({'pattern':term['oscillator']['pattern'],'control':control,'region':region['box'],
                                 'screen_fraction':region['screen_fraction'],'oscillator':term['oscillator'],
                                 'amplitude_range':term['amplitude_range'],
                                 'amplitude_pixels_range':None if term['amplitude_range'] is None else [v*scale for v in term['amplitude_range']],
                                 'amplitude_dependencies':term['amplitude_dependencies']})
    for control in ('rot','zoom','sx','sy','cx','cy','warp'):
        row=controls.get(control,{})
        for term in (row.get('terms') or []) if row.get('status')=='described' else []:
            if term['kind']=='spatial_oscillator':
                rows.append({'pattern':term['oscillator']['pattern'],'control':control,'region':{},
                             'oscillator':term['oscillator'],'amplitude_range':term['amplitude_range'],
                             'amplitude_dependencies':term['amplitude_dependencies']})
    return rows
