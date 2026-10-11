"""Declared custom-wave projection and prepared-coordinate operator envelopes.

These are conditional source bounds, not evaluated points, rendered frames,
raster coverage or driver certification.
"""
from fractions import Fraction
import math

import numpy as np


POLICY='source-curve-projection-v1'


def _number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('expected a finite declared scalar')
    return Fraction(value)


def _exact(value):
    if not isinstance(value,dict):raise ValueError('exact coefficient metadata is absent')
    if any(type(value.get(key)) not in {str,int} for key in ('numerator','denominator')):
        raise ValueError('exact coefficient numerator/denominator must be integer strings or integers')
    numerator=int(value['numerator'])
    denominator=int(value['denominator'])
    if denominator<=0 or max(abs(numerator).bit_length(),denominator.bit_length())>65536:
        raise ValueError('invalid or excessive exact coefficient metadata')
    return Fraction(numerator,denominator)


def _span(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2:raise ValueError('finite interval is absent')
    low,high=map(_number,value)
    if low>high:raise ValueError('declared interval is reversed')
    return low,high


def _coefficients(recipe,name):
    exact=recipe.get(name+'_affine_coefficients_exact')
    if isinstance(exact,dict):return {key:(_exact(exact[key]),)*2 for key in ('constant','sample','time')}
    spans=recipe.get(name+'_affine_coefficient_enclosures')
    if isinstance(spans,dict):return {key:_span(spans[key]) for key in ('constant','sample','time')}
    raise ValueError(name+' requires exact or explicitly enclosed source coefficients; numeric displays are insufficient')


def _multiply(a,b):
    values=[x*y for x in a for y in b]
    return min(values),max(values)


def _add(a,b):return a[0]+b[0],a[1]+b[1]


def _maxabs(span):return max(map(abs,span))


def _outward(value,upper):
    rounded=float(value)
    if not math.isfinite(rounded):raise ValueError('projected bound exceeds finite binary64 domain')
    if (Fraction(rounded)<value if upper else Fraction(rounded)>value):
        rounded=math.nextafter(rounded,math.inf if upper else -math.inf)
    if not math.isfinite(rounded):raise ValueError('projected outward bound is nonfinite')
    return rounded


def _enclosure(span):return [_outward(span[0],False),_outward(span[1],True)]


def _box_enclosure(box):return [_enclosure(span) for span in box]


def _f32_vertices(box):
    result=[]
    with np.errstate(over='ignore',invalid='ignore'):
        for span in box:
            endpoints=[float(np.float32(value)) for value in _enclosure(span)]
            if not all(math.isfinite(value) for value in endpoints):raise ValueError('vertex bbox lacks a finite native float32 conversion domain')
            result.append(tuple(map(Fraction,endpoints)))
    return result


def _screen_box(vertices):
    # orthogonalProjection flips vertex Y. Top-left viewport Y reverses clip Y
    # again, so both screen-fraction lanes equal (vertex_coordinate+1)/2.
    return [((span[0]+1)/2,(span[1]+1)/2) for span in vertices]


def _smoothing_operator():
    """Bound the existing four-tap helper without evaluating any positions.

    custom_wave.smooth_position implements the same constants/association.
    Its execution API is deliberately not called by this source producer.
    """
    coefficients=[np.float32(value) for value in (-.15,1.15,1.15,-.15)]
    inverse=np.float32(1)/(coefficients[0]+coefficients[1]+coefficients[2]+coefficients[3])
    exact_c=list(map(lambda value:Fraction(float(value)),coefficients))
    inverse=Fraction(float(inverse))
    weights=[coefficient*inverse for coefficient in exact_c]
    return exact_c,inverse,weights


def _smoothed_box(vertices,coefficients,inverse,weights):
    result=[]
    u=Fraction(1,2**24)
    gamma=8*u/(1-8*u)
    smallest=Fraction(1,2**149)
    largest=Fraction(float(np.finfo(np.float32).max))
    for span in vertices:
        magnitude=_maxabs(span)
        # This sufficient guard also keeps the ordered product/add intermediates
        # finite. Do not cancel an overflowing possible intermediate away.
        if sum(map(abs,coefficients))*magnitude>largest:
            raise ValueError('smoothing envelope cannot establish finite float32 intermediates')
        low=sum(weight*(span[0] if weight>=0 else span[1]) for weight in weights)
        high=sum(weight*(span[1] if weight>=0 else span[0]) for weight in weights)
        padding=gamma*sum(map(abs,weights))*magnitude+8*smallest*max(abs(inverse),1)
        result.append((low-padding,high+padding))
    return _f32_vertices(result)


def curve_projection(recipe,context=None):
    """Project a source parametric recipe using a declared viewport/time domain.

    Context keys: viewport (default1920x1080), source_time_domain (optional
    finite interval), wave_use_dots (optional bool; unknown includes line mode).
    Exact coefficient metadata or caller-declared coefficient enclosures are
    required; approximate numeric displays cannot prove zero or bounded growth.
    """
    context_supported=context is None or isinstance(context,dict)
    context={} if context is None or not context_supported else context
    result={'policy':POLICY,'status':'unresolved','viewport':None,'viewport_was_defaulted':context_supported and 'viewport' not in context,
        'coefficient_domain_basis':'declared_exact_or_enclosed_source_coefficients',
        'source_time_domain':None,'time_domain_is_observed':False,'radius_source_interval':None,
        'nominal_radius_pixels_upper_bound':None,'nominal_centre_screen_fraction':None,'nominal_centre_pixels':None,
        'native_inverse_aspect_xy':None,'nominal_source_to_screenfraction_scale_xy':None,
        'nominal_source_to_pixel_scale_xy':None,'native_stored_aspect_source_to_pixel_scale_xy':None,
        'unsmoothed_bbox_screen_fraction':None,'unsmoothed_bbox_pixels':None,
        'prepared_centerline_bbox_screen_fraction':None,'prepared_centerline_bbox_pixels':None,
        'possible_coordinate_clipping':None,'visible_outside_points_verified':False,
        'maximum_nominal_fixed_sample_point_speed_pixels_per_second':None,
        'maximum_nominal_fixed_sample_point_speed_screen_fraction_per_second':None,
        'maximum_nominal_prepared_vertex_speed_pixels_per_second':None,
        'maximum_nominal_interior_locus_normal_speed_pixels_per_second':None,
        'maximum_nominal_interior_locus_normal_speed_screen_fraction_per_second':None,
        'signed_final_clip_ndc_angular_orientation':None,'smoothing_operator':None,
        'raster_coverage_fraction':None,'visible_motion_speed':None,'native_numeric_certified':False,
        'uses_equation_execution':False,'uses_rendered_images':False,'whole_preset_activity_credit':False,
        'unknown_reasons':[],
        'source_curve_provenance':recipe.get('source_provenance',{}) if isinstance(recipe,dict) else {},
        'source_anchors':{'aspect':'ProjectM.cpp GetRenderContext aspectX/Y and invAspectX/Y',
            'point_projection':'CustomWaveform.cpp point construction before SmoothWave',
            'clip_projection':'PresetState.cpp orthogonalProjection; DrawPrepared and untextured vertex shader',
            'smoothing':'CustomWaveform.cpp SmoothWave and custom_wave.py smooth_position',
            'original':'MilkDrop2 vis_milk2/milkdropfs.cpp DrawCustomWaves/SmoothWave; plugin.cpp inverse aspects'},
        'conditions':['The declared viewport is the native rendering target, not a measured panel/UI/surface size or device-capability claim',
            'Native inverse aspects are stored float32 reciprocals; ideal real-ratio source coordinates map to pixel scale max(width,height) on both axes',
            'Vertex x=(2*x-1)*invAspectX and y=(1-2*y)*invAspectY precede orthographic Y reversal; top-left screen fractions are .5+(x-.5)*invAspectX and .5-(y-.5)*invAspectY',
            'Coordinate boxes use independent angular [-1,1] enclosures and need not be attained; potential clipping is not a reached or visible outside point',
            'Radius growth requires a finite declared source-time domain for coordinate bounds; no time-zero box is promoted into a lifetime enclosure',
            'Exact/enclosed affine coefficients and source centres are fixed during these partial calculations; coefficient value enclosures do not supply a rate for varying coefficients',
            'Supplied source radius/centre envelopes hold before point upload; native EEL and trigonometric arithmetic rounding are not certified here',
            'Point and interior-locus rates are continuous nominal source partials before float32 storage, with fixed viewport/sample count and finite source intermediates; native steps/cadence remain unknown',
            'Line smoothing has negative four-tap weights and can overshoot; its interval operator includes original points plus possible generated midpoint coordinates',
            'Smoothing rounding padding assumes ordinary finite IEEE binary32 products/adds (or contraction with no greater error), gradual underflow and unchanged constants; driver/FMA/flush behavior is uncertified',
            'Original MilkDrop2 uses the same point/sample and smoothing formulas but casts point coordinates before aspect multiplication; packed colours and raster conventions remain separate',
            'Line/dot widths, pixel centres, thick-repeat offsets, clipping/rasterization, interpolation, alpha, storage, feedback and later composition do not acquire coverage, visibility or stationary-pixel proofs']}
    try:
        if not context_supported:raise ValueError('projection context must be a JSON object or omitted')
        if not isinstance(recipe,dict) or recipe.get('policy')!='source-parametric-wave-v1':raise ValueError('supported source curve recipe is absent')
        viewport=context.get('viewport',[1920,1080])
        if not isinstance(viewport,(list,tuple)) or len(viewport)!=2 or any(type(value) is not int or not 0<value<2**31 for value in viewport):
            raise ValueError('viewport requires two positive native int32 dimensions')
        width,height=viewport
        result['viewport']=list(viewport)
        domain=recipe.get('sample_domain',{})
        if not isinstance(domain,dict):raise ValueError('sample_domain must be a JSON object')
        count=domain.get('effective_samples')
        if type(count) is not int or not 2<=count<=512 or domain.get('single_dot_nonfinite_sample_excluded') is not True:
            raise ValueError('finite native multi-point sample domain is unproved; single-dot 0/0 is excluded')
        sample=_span(domain.get('native_float32_endpoint_interval'))
        radius=_coefficients(recipe,'radius')
        phase=_coefficients(recipe,'phase')
        centres=recipe.get('centre_source_xy_exact')
        if not isinstance(centres,list) or len(centres)!=2:raise ValueError('exact source centre metadata is absent')
        centres=list(map(_exact,centres))
        time=None if context.get('source_time_domain') is None else _span(context['source_time_domain'])
        if time is not None:result['source_time_domain']=_enclosure(time)
        span=_add(radius['constant'],_multiply(radius['sample'],sample))
        if radius['time']==(0,0):bounded_radius=span
        elif time is not None:bounded_radius=_add(span,_multiply(radius['time'],time))
        else:
            bounded_radius=None
            result['unknown_reasons'].append('time-growing radius has no finite declared source-time domain')
        with np.errstate(over='ignore',invalid='ignore'):
            w,h=np.float32(width),np.float32(height)
            inverse=[np.float32(1)/(w/h) if height>width else np.float32(1),
                     np.float32(1)/(h/w) if width>height else np.float32(1)]
        inverse=list(map(lambda value:Fraction(float(value)),inverse))
        longest=max(viewport)
        pixel_scales=[width*inverse[0],height*inverse[1]]
        pixel_norm=max(pixel_scales)
        fraction_norm=max(inverse)
        centre_screen=[Fraction(1,2)+(centres[0]-Fraction(1,2))*Fraction(longest,width),
                       Fraction(1,2)-(centres[1]-Fraction(1,2))*Fraction(longest,height)]
        centre_pixels=[value*size for value,size in zip(centre_screen,viewport)]
        # Validate display conversions before installing any metadata, avoiding
        # an infinite partial value when a later bound correctly abstains.
        displayed_centre_screen=[_outward(value,True) for value in centre_screen]
        displayed_centre_pixels=[_outward(value,True) for value in centre_pixels]
        result.update(native_inverse_aspect_xy=list(map(float,inverse)),
            nominal_source_to_screenfraction_scale_xy=[float(Fraction(longest,width)),-float(Fraction(longest,height))],
            nominal_source_to_pixel_scale_xy=[longest,-longest],
            native_stored_aspect_source_to_pixel_scale_xy=[float(pixel_scales[0]),-float(pixel_scales[1])],
            nominal_centre_screen_fraction=displayed_centre_screen,
            nominal_centre_pixels=displayed_centre_pixels,
            signed_final_clip_ndc_angular_orientation=recipe.get('signed_native_ndc_angular_orientation'))
        coefficients,normal,weights=_smoothing_operator()
        gain=sum(map(abs,weights))
        dots=context.get('wave_use_dots')
        if dots is not None and not isinstance(dots,bool):raise ValueError('wave_use_dots must be a bool or unknown')
        result['smoothing_operator']={'applied':False if dots is True else True if dots is False else None,
            'negative_weights_present':True,'native_float32_constants':list(map(float,coefficients)),
            'native_float32_inverse_sum':float(normal),'nominal_l1_gain_upper_bound':_outward(gain,True),
            'native_numeric_certified':False,'nominal_midpoint_only':'four-tap affine coordinate operator; original endpoints retained',
            'unknown_style_enclosure_includes_line_mode':dots is None}
        point_rate=None
        radial_time=_maxabs(radius['time'])
        angular_time=_maxabs(phase['time'])
        if bounded_radius is not None:
            magnitude=_maxabs(bounded_radius)
            result['radius_source_interval']=_enclosure(bounded_radius)
            result['nominal_radius_pixels_upper_bound']=_outward(magnitude*longest,True)
            source_box=[(centre-magnitude,centre+magnitude) for centre in centres]
            vertex_box=[((2*source_box[0][0]-1)*inverse[0],(2*source_box[0][1]-1)*inverse[0]),
                        ((1-2*source_box[1][1])*inverse[1],(1-2*source_box[1][0])*inverse[1])]
            vertices=_f32_vertices(vertex_box)
            unsmoothed=_screen_box(vertices)
            result['unsmoothed_bbox_screen_fraction']=_box_enclosure(unsmoothed)
            result['unsmoothed_bbox_pixels']=_box_enclosure([_multiply(span,(size,size)) for span,size in zip(unsmoothed,viewport)])
            if dots is True:prepared=vertices
            else:
                smoothed=_smoothed_box(vertices,coefficients,normal,weights)
                prepared=[(min(a[0],b[0]),max(a[1],b[1])) for a,b in zip(vertices,smoothed)]
            screen=_screen_box(prepared)
            result['prepared_centerline_bbox_screen_fraction']=_box_enclosure(screen)
            result['prepared_centerline_bbox_pixels']=_box_enclosure([_multiply(span,(size,size)) for span,size in zip(screen,viewport)])
            result['possible_coordinate_clipping']=any(span[0]<0 or span[1]>1 for span in screen)
            # Triangle-norm ceiling avoids an unsafe rounded square root. For
            # zero radial rate this is the exact angular product ceiling.
            point_rate=radial_time+magnitude*angular_time
        elif angular_time==0:point_rate=radial_time
        if point_rate is not None:
            result['maximum_nominal_fixed_sample_point_speed_pixels_per_second']=_outward(point_rate*pixel_norm,True)
            result['maximum_nominal_fixed_sample_point_speed_screen_fraction_per_second']=_outward(point_rate*fraction_norm,True)
            result['maximum_nominal_prepared_vertex_speed_pixels_per_second']=_outward(point_rate*pixel_norm*(1 if dots is True else max(1,gain)),True)
        # Recompute the relation from the supplied coefficient domains. Reusing
        # a recipe's narrower derived scalar would erase caller uncertainty.
        if phase['sample'][0]<=0<=phase['sample'][1]:
            result['unknown_reasons'].append('sample phase coefficient domain includes zero; interior fixed-angle locus conversion is unresolved')
        else:
            ratios=[numerator/denominator for numerator in phase['time'] for denominator in phase['sample']]
            product=_multiply(radius['sample'],(min(ratios),max(ratios)))
            locus_span=_add(radius['time'],(-product[1],-product[0]))
            locus_rate=_maxabs(locus_span)
            result['maximum_nominal_interior_locus_normal_speed_pixels_per_second']=_outward(locus_rate*pixel_norm,True)
            result['maximum_nominal_interior_locus_normal_speed_screen_fraction_per_second']=_outward(locus_rate*fraction_norm,True)
        result['status']='conditional_projected_coordinates' if bounded_radius is not None else 'partial_projection'
    except (ValueError,OverflowError,KeyError) as error:
        result['unknown_reasons'].append(str(error))
    return result
