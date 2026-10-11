"""Structure of per-pixel (mesh) warp control fields, from source graphs only.

Each native warp control (zoom, rot, warp, cx, cy, dx, dy, sx, sy) is a pure
per-vertex formula of mesh coordinates (x, y, rad, ang), audio, time and
uniform inputs. This pass decomposes each into:

- coordinate gates: ``select`` branches whose predicate is a threshold on one
  mesh coordinate become interval regions (for example a band 0.35<y<0.65);
- signed additive terms: constants, uniform audio/time terms (bounded with
  declared input domains), coordinate-affine terms and spatial oscillators
  sin/cos(kx*x+ky*y+kr*rad+ka*ang+w*t+phi) with wavelength and phase velocity;
- motion semantics using the pinned engine convention: the warp samples from
  (u-dx, v-dy) after zoom/rotation about (cx, cy), so retained content moves by
  +dx (right) and +dy (down, y=0 at the top) per feedback step; zoom>1 expands
  and zoom<1 contracts content about the centre. A same-axis affine term
  d=a+b*c gives the backward map c-d=(1-b)*c-a: features scale by 1/(1-b) per
  step toward c*=-a/b.

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
        row.update(pattern='angular_lobes',angular_lobes=abs(ka),
            angular_rotation_radians_per_second=-float(omega)/ka if omega else 0.0,
            angular_lobes_integer=float(ka).is_integer())
    else:row['pattern']='mixed_coordinate_oscillator'
    return row


def _classify(sign,node,domains,scale,aspect,depth):
    deps=_dependencies(node)
    row={'sign':sign,'kind':'unclassified','dependencies':{key:sorted(value) for key,value in deps.items() if value}}
    if deps['other'] or deps['unsupported_ops']:
        row['kind']='unresolved_inputs';return row
    linear=_linear(node)
    if not deps['coordinates']:
        value=_envelope(node,domains)
        if linear is not None and set(linear)=={'const'}:
            row.update(kind='constant',value=sign*float(linear['const']))
        else:
            row.update(kind='uniform',value_range=None if value is None else sorted([sign*value[0],sign*value[1]]))
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


def _axis_summary(control,region,domains,scale,fps):
    """Constant offset, same-axis coefficient and derived per-step motion for dx/dy."""
    axis='x' if control=='dx' else 'y'
    other='y' if axis=='x' else 'x'
    a=0.0;b=0.0;cross=0.0;open_terms=[]
    for term in region['terms']:
        if term['kind']=='constant':a+=term['value']
        elif term['kind']=='coordinate_affine':
            coefficients=term['coefficients']
            if set(coefficients)-{axis,other}:open_terms.append('radius/angle dependence');continue
            a+=term['constant'];b+=coefficients.get(axis,0.0);cross+=coefficients.get(other,0.0)
        elif term['kind'] in ('uniform','spatial_oscillator'):continue
        else:open_terms.append(term['kind'])
    row={'constant_offset':a,'same_axis_coefficient':b,'cross_axis_coefficient':cross,
         'translation_pixels_per_step':a*scale if not b and not cross else None,
         'translation_pixels_per_second':a*scale*fps if not b and not cross and fps else None,
         'fixed_point':None,'feature_scale_per_step':None,'thin_line_peak_gain_per_step':None,
         'behaviour':None,'open_terms':open_terms}
    if b:
        if b==1:row['behaviour']='degenerate_same_axis_map'
        else:
            scale_step=1/(1-b)
            row.update(fixed_point=-a/b,feature_scale_per_step=scale_step,
                # A sub-texel line across this axis is hit by about |s| of the
                # backward samples, so its peak gain per step is min(1,|s|).
                thin_line_peak_gain_per_step=min(1.0,abs(scale_step)),
                behaviour='compression_toward_fixed_line' if abs(scale_step)<1 else 'expansion_from_fixed_line')
            if scale_step<0:row['behaviour']+='_with_mirror'
    elif a:row['behaviour']='uniform_translation'
    if cross:row['behaviour']=(row['behaviour']+'+' if row['behaviour'] else '')+'shear'
    return row


def mesh_field_structure(analysis,context=None):
    """Describe every native per-pixel warp control field; see module docstring."""
    from scene_equations import _scalar
    result={'policy':POLICY,'status':'unknown','controls':{},'patterns':[],'per_pixel_equations_present':None,
        'pixel_scale':None,'coordinate_domains':None,'visible_motion_speed':None,'native_numeric_certified':False,
        'uses_equation_execution':False,'uses_rendered_images':False,'whole_preset_activity_credit':False,
        'unknown_reasons':[],
        'conditions':['Engine convention: warp samples (u-dx, v-dy) after zoom/rotation about (cx, cy); retained content moves +dx right and +dy down (y=0 top) per feedback step',
            'Per-pixel x/y are aspect-corrected: both measure the long side, so 1 unit is max(width, height) pixels; rad=1 is half the long side',
            'Coordinate gates are single-coordinate thresholds; boundary strictness, mesh interpolation between vertices and texel sampling are not resolved',
            'Uniform audio/time ranges use declared input domains, not observed music; oscillator speeds are nominal phase velocities of a control field, not visible feature speeds',
            'Fields act on the sampling map each feedback step; displayed motion also depends on content, decay, shaders and composition',
            'Compression by s per step leaves a sub-texel line hit by about |s| of the backward bilinear samples: peak gain min(1,|s|) per step on top of decay; expansion keeps peak brightness']}
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
                                 'screen_fraction':_screen_fraction(region['box'],domains),
                                 'terms':region['terms'],
                                 **({'axis_motion':_axis_summary(control,region,domains,scale,fps)} if control in ('dx','dy') else {})}
                                for region in regions]
                row['status']='described'
            except _Budget as error:row['unknown_reasons'].append(str(error))
        result['patterns']=_patterns(result['controls'],scale,fps)
        result['status']='described' if all(r['status']=='described' for r in result['controls'].values()) else 'partial'
    except (ValueError,TypeError,KeyError) as error:
        result['unknown_reasons'].append(str(error))
    return result


def _patterns(controls,scale,fps):
    """Readable pattern records derived from the per-control decomposition."""
    rows=[]
    zoom=controls.get('zoom',{})
    if zoom.get('status')=='described' and zoom.get('uniform_across_mesh') and zoom.get('value_range'):
        low,high=zoom['value_range']
        if not (low==high==1.0):
            rows.append({'pattern':'uniform_zoom','control':'zoom','value_range':[low,high],
                'content_motion':'contracts toward the zoom centre' if high<1 else 'expands from the zoom centre' if low>1 else 'contracts or expands',
                'percent_per_step_range':[(low-1)*100,(high-1)*100],
                'thin_line_peak_gain_per_step_range':[min(1.0,low),min(1.0,high)],
                'audio_inputs':zoom['dependencies'].get('audio',[])})
    elif zoom.get('status')=='described' and not zoom.get('uniform_across_mesh'):
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
                             ('constant_offset','same_axis_coefficient','cross_axis_coefficient','fixed_point',
                              'feature_scale_per_step','thin_line_peak_gain_per_step',
                              'translation_pixels_per_step','translation_pixels_per_second')}})
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
