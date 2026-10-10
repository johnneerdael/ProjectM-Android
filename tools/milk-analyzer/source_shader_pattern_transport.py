"""Conditional rigid translation of pure generated RGB, from typed source only.

Exact rational coefficients describe nominal real arithmetic after literal
conversion. GPU rounding, perceived movement and later passes stay separate.
"""
from fractions import Fraction
import hashlib
import math
from pathlib import Path

POLICY = 'source-pure-shader-rigid-translation-v1'
CLOCKS = {'time', '_c2.x', ':native-render-time-f32'}
UV = ('_uv.x', '_uv.y', '_uv.z', '_uv.w')
OUTER = {'add', 'subtract', 'multiply', 'divide', 'negate', 'sin', 'cos',
         'abs', 'sqrt', 'pow', 'min', 'max', 'clamp', 'saturate', 'frac',
         'floor', 'length', 'distance', 'dot', 'lerp', 'domain_checked'}


def _exact_phase(field):
    """Small exact numeric adapter for already-lowered scalar affine graphs.

Use existing lane/literal projections; do not fold arithmetic coefficients
through binary64. Unsupported/nonlinear operations return no affine phase.
    """
    from source_flash_behaviour import _project_uniform_lanes
    from source_appearance import _canonical_lane, _phase_literal
    from effect_families import _parts
    from shader_fields import Field
    memo = {}; active = set()

    def visit(node, depth=0):
        key = id(node)
        if key in memo:return memo[key]
        if depth > 64 or len(memo)+len(active) >= 512 or key in active:
            raise ValueError('exact phase traversal budget/cycle exceeded')
        active.add(key)
        try:result = calculate(node, depth)
        finally:active.remove(key)
        memo[key] = result
        return result

    def calculate(node, depth):
        if node.op == 'member':
            projected = _project_uniform_lanes(_canonical_lane(node))
            if projected.op == 'input':return visit(projected,depth+1)
        if node.op == 'constant' or node.op in {'cast', 'narrow', 'construct'}:
            # Literal conversion follows existing typed float/int policy.
            literal = _phase_literal(node)
            if literal is not None:return (Fraction(0),)*5+(Fraction(literal),)
            return None
        if node.dtype != 'float':return None
        if node.op == 'input':
            name = node.detail.get('name')
            if name not in {*UV, *CLOCKS}:return None
            values = [Fraction(0)]*6
            values[UV.index(name) if name in UV else 4] = Fraction(1)
            return tuple(values)
        if node.op == 'dot' and len(node.args) == 2:
            left,right = map(_parts,node.args)
            if len(left) != len(right):return None
            total = (Fraction(0),)*6
            for a,b in zip(left,right):
                value = visit(_project_uniform_lanes(Field('multiply',(a,b),'float')),depth+1)
                if value is None:return None
                total = tuple(x+y for x,y in zip(total,value))
            return total
        if node.op == 'negate' or node.op == 'unary' and node.detail.get('operator') in {0, 1}:
            value = visit(node.args[0], depth+1)
            if value is None:return None
            sign = -1 if node.op == 'negate' or node.detail.get('operator') == 0 else 1
            return tuple(sign*v for v in value)
        if node.op not in {'add', 'subtract', 'multiply', 'divide'} or len(node.args) != 2:return None
        a, b = (visit(arg, depth+1) for arg in node.args)
        if a is None or b is None:return None
        if node.op in {'add', 'subtract'}:
            sign = 1 if node.op == 'add' else -1
            return tuple(x+sign*y for x,y in zip(a,b))
        if node.op == 'multiply':
            if not any(a[:5]):return tuple(a[5]*v for v in b)
            if not any(b[:5]):return tuple(b[5]*v for v in a)
            return None
        if any(b[:5]) or b[5] == 0:return None
        return tuple(v/b[5] for v in a)

    return visit(_project_uniform_lanes(field))


def _solve(rows):
    """Solve all K*v=-omega exactly; use minimum-norm solution for rank one."""
    spatial = [row for row in rows if any(row[:2])]
    if any(not any(row[:2]) and row[2] != 0 for row in rows):
        raise ValueError('time-only colour modulation cannot translate spatial coordinates')
    if not spatial:raise ValueError('no generated spatial pattern')
    a,b,w = spatial[0]
    second = next((row for row in spatial[1:] if a*row[1]-b*row[0] != 0), None)
    if second is None:
        norm = a*a+b*b
        velocity = (-w*a/norm, -w*b/norm); rank = 1
    else:
        c,d,z = second; determinant = a*d-b*c
        velocity = ((-w*d+b*z)/determinant, (-a*z+w*c)/determinant); rank = 2
    if any(kx*velocity[0]+ky*velocity[1] != -omega for kx,ky,omega in rows):
        raise ValueError('generated phases have no single consistent translation velocity')
    return velocity, rank


def _guard_projection(field):
    """Expand typed dot lanes for the existing scalar envelope producer."""
    from effect_families import _parts
    from shader_fields import Field
    from source_appearance import _canonical_lane
    from source_flash_behaviour import _project_uniform_lanes
    memo = {}
    def visit(node,depth=0):
        if id(node) in memo:return memo[id(node)]
        if depth>64 or len(memo)>=512:raise ValueError('pattern guard projection budget exceeded')
        canonical = _canonical_lane(node)
        if canonical.op == 'dot' and len(canonical.args)==2:
            left,right = map(_parts,canonical.args)
            if not left or len(left)!=len(right):raise ValueError('dot guard dimensions unresolved')
            products = [Field('multiply',(visit(a,depth+1),visit(b,depth+1)),'float') for a,b in zip(left,right)]
            result = products[0]
            for product in products[1:]:result=Field('add',(result,product),'float')
        else:
            result = Field(canonical.op,tuple(visit(a,depth+1) for a in canonical.args),canonical.dtype,canonical.detail)
        memo[id(node)] = result
        return result
    return _project_uniform_lanes(visit(field))


def rigid_shader_pattern_transport(analysis, stage, context=None):
    """Return a stage-local nominal identity, or explicit unresolved reasons.

Context uses the existing viewport/scalar_input_domains keys. Source custom
selection must already be qualified by the native-profile selection contract.
    """
    from source_activity import blackout_colour_channels
    from source_appearance import _expression
    from source_control_bounds import scalar_value_envelope
    from source_forms import known_invalid_phase_offset
    from source_sampling import _affine_basis_map
    from source_temporal import affine_time_parameters, clock_kinds
    from effect_families import _parts, _walk
    if stage not in {'warp', 'composite'}:raise ValueError('warp or composite stage required')
    request = context or {}
    result = {'policy': POLICY, 'status': 'unresolved', 'stage': stage,
        'component_id': 'shader_'+stage, 'coordinate_basis': 'normalized_viewport_uv',
        'signed_velocity_vp_per_second': None, 'maximum_pattern_speed_vp_per_second': None,
        'constraint_rank': None, 'velocity_unique': None, 'phase_constraints': [],
        'native_coordinate_recipe': None, 'clock_kinds': [], 'shader_time_wrap_seconds': None,
        'shader_selection': dict(analysis.stages[stage]),
        'engine_archive_sha256': analysis.source.get('parser_inputs',{}).get('engine_archive_sha256'),
        'source_sha256': analysis.source.get('preset_sha256'),
        'model_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'unknown_reasons': [], 'domain_guards': [], 'native_numeric_certified': False,
        'nominal_translation_identity_proved': False, 'all_rgb_factors_accounted_for': False,
        'complete_content_transport_proved': False, 'visible_motion_speed_vp_per_second': None,
        'uses_shader_execution': False, 'uses_equation_execution': False, 'uses_rendered_images': False,
        'conditions': ['Nominal RGB identity G(u,t)=F(u-v*t), at points where the original graph is defined and finite',
            'Exact rational coefficients use original typed literals; arithmetic/GPU rounding and interpolation are excluded',
            'Clock continuity excludes wrap/reset events; no feedback-FPS multiplier is applied',
            'All generated RGB factors share one velocity; this is sufficient and may miss other moving patterns',
            'Rank-one velocity is the minimum-norm representative; tangential transport is unidentifiable',
            'Clipping, storage, later passes, contrast, coverage and dominant or perceived screen motion remain separate']}
    try:
        selected = analysis.stages[stage]
        if selected['kind'] != 'custom_'+stage:raise ValueError('selected custom shader required')
        if selected.get('source_contains_clip'):raise ValueError('clip/discard can alter the translating support')
        field = analysis.outputs.get(stage)
        if field is None:raise ValueError('selected shader RGB output unavailable')
        prefix = 'warp_' if stage == 'warp' else 'comp_'
        if any(row.get('section') == prefix for row in getattr(analysis,'unknowns', [])):
            raise ValueError('original shader lowering/domain effects unresolved')
        original = []
        for item in _walk(field, preserve_zero_products=True):
            if len(original) >= 512:raise ValueError('pattern original graph budget exceeded')
            original.append(item)
        for node,path in original:
            if node.op in {'sample','sequence','unknown','uninitialized'} or node.op.startswith('loop_'):
                raise ValueError('sample/history/control effect excludes pure generated pattern: '+node.op)
            if node.op in {'cast','narrow'} and _exact_phase(node) is None:
                raise ValueError('dynamic typed conversion excludes continuous coordinate identity')
        if known_invalid_phase_offset(field,preserve_zero_products=True):
            raise ValueError('known invalid original shader arithmetic')
        channels = blackout_colour_channels(field)
        if len(channels) != 3:raise ValueError('three scalar generated RGB channels required')
        rows = []; seen = set(); active = set(); uses_mesh = False
        coordinate_rows = []

        def visit(node, path, depth=0):
            nonlocal uses_mesh
            key = id(node)
            if key in seen:return
            if depth > 64 or len(seen)+len(active) >= 512 or key in active:
                raise ValueError('pattern traversal budget/cycle exceeded')
            active.add(key)
            try:
                exact = _exact_phase(node)
                if exact is not None:
                    # Reuse existing affine admission, but never its rounded
                    # coefficients for rank or consistency proof.
                    matrix, offsets = _affine_basis_map(node, ('_uv',), output_width=1)
                    if affine_time_parameters(offsets[0]) is None:
                        raise ValueError('existing affine phase admission unresolved')
                    coordinate_rows.append((exact, path, node))
                    uses_mesh |= bool(any(exact[:2]))
                    return
                if node.op not in OUTER and node.op != 'unary':
                    raise ValueError('generated pattern operation/input unsupported: '+node.op)
                if node.op == 'unary' and node.detail.get('operator') not in {0,1}:
                    raise ValueError('stateful/discrete unary operation unresolved')
                for index,arg in enumerate(node.args):
                    for lane,part in enumerate(_parts(arg)):
                        visit(part, path+[index,lane], depth+1)
            finally:
                active.remove(key); seen.add(key)

        for index,channel in enumerate(channels):visit(channel,[index])
        matrix = ((Fraction(1),Fraction(0)),(Fraction(0),Fraction(1)))
        if stage == 'warp' and uses_mesh:
            from source_native_warp import native_warp_recipe
            recipe = native_warp_recipe(analysis, consumed=True)
            result['native_coordinate_recipe'] = recipe
            if recipe['model_kind'] != 'uniform_affine':
                raise ValueError('mesh UV requires a time-independent uniform native affine coordinate recipe')
            viewport = request.get('viewport', [1920,1080])
            if len(viewport) != 2 or any(type(v) is not int or v<=0 for v in viewport):
                raise ValueError('positive viewport dimensions required for native coordinates')
            ax = min(1.,viewport[0]/viewport[1]); ay = min(1.,viewport[1]/viewport[0])
            p = recipe['native_float32_controls']; c,s = recipe['rotation_matrix'][0][0],recipe['rotation_matrix'][1][0]
            matrix = ((Fraction(c)/(Fraction(p['zoom'])*Fraction(p['sx'])),
                       -Fraction(s)*Fraction(ay)/(Fraction(p['zoom'])*Fraction(p['sy'])*Fraction(ax))),
                      (Fraction(s)*Fraction(ax)/(Fraction(p['zoom'])*Fraction(p['sx'])*Fraction(ay)),
                       Fraction(c)/(Fraction(p['zoom'])*Fraction(p['sy']))))
        kinds = set()
        for exact,path,node in coordinate_rows:
            a,b,c,d,omega,bias = exact
            gradient = (a*matrix[0][0]+b*matrix[1][0]+c,
                        a*matrix[0][1]+b*matrix[1][1]+d)
            rows.append((*gradient,omega)); kinds.update(clock_kinds(node))
            result['phase_constraints'].append({'source_graph_path':path,'phase_expression':_expression(node),
                'exact_uv4_coefficients':[str(v) for v in exact[:4]],
                'exact_viewport_gradient':[str(v) for v in gradient],
                'exact_time_coefficient':str(omega),'exact_constant_offset':str(bias)})
        if len(kinds)>1:raise ValueError('independently wrapping and native clocks have no global shared time domain')
        result['clock_kinds'] = sorted(kinds)
        result['shader_time_wrap_seconds'] = 10000 if 'shader_time_wrapped' in kinds else None
        velocity,rank = _solve(rows)
        domains = {name:[0.,1.] for name in UV}
        domains.update({'time':[0.,10000.], '_c2.x':[0.,10000.]})
        domains.update(request.get('scalar_input_domains', {}))
        if stage == 'warp' and uses_mesh:
            for name in UV[:2]:
                if name not in request.get('scalar_input_domains', {}):
                    raise ValueError('native mesh coordinate domain must be explicitly supplied: '+name)
            result['conditions'].append('Caller mesh-UV domains include selected native affine output and fixed finite texel offset')
        result['declared_scalar_input_domains'] = domains
        for channel in channels:
            guard = scalar_value_envelope(_guard_projection(channel),input_domains=domains)
            result['domain_guards'].append(guard)
            span = guard['nominal_value_range']
            if span is None or any(not math.isfinite(v) for v in span):
                raise ValueError('generated RGB finite/domain envelope unresolved')
        # Include intermediate phase ranges, not just bounded trig outputs.
        for node,path in original:
            if node.dtype != 'float':continue
            guard = scalar_value_envelope(_guard_projection(node),input_domains=domains)
            span = guard['nominal_value_range']
            if span is None or any(not math.isfinite(v) or abs(v)>3.4028234663852886e38 for v in span):
                raise ValueError('original intermediate finite binary32 domain unresolved')
        values = [float(v) for v in velocity]
        from source_native_lookup_transport import _norm_upper
        speed = _norm_upper(values)
        if speed is None or any(not math.isfinite(v) or exact != 0 and v == 0 for exact,v in zip(velocity,values)):
            raise ValueError('pattern velocity overflows/underflows report units')
        # Outward endpoints account for rational->float velocity conversion.
        upper_values = [math.nextafter(abs(v),math.inf) if Fraction(v)!=exact else abs(v)
                        for exact,v in zip(velocity,values)]
        speed = _norm_upper(upper_values)
        if speed is None:raise ValueError('outward pattern speed exceeds report units')
        result.update(status='conditional_rigid_translation',signed_velocity_vp_per_second=values,
            exact_signed_velocity_vp_per_second=[str(v) for v in velocity],
            maximum_pattern_speed_vp_per_second=speed,constraint_rank=rank,velocity_unique=rank==2,
            nominal_translation_identity_proved=True,all_rgb_factors_accounted_for=True)
    except (ValueError,OverflowError,RecursionError,IndexError,ZeroDivisionError) as error:
        result['unknown_reasons'] = [str(error)]
    return result


def generated_shader_pattern_transport(analysis, stage, context=None):
    """Keep full-stage proof separate from live colour subfield identities.

Subfields retain their original colour-graph path and parent obligations. Never
join them into total motion or infer moving texture/history from a local mask.
    """
    import copy
    from effect_families import _CACHE, _deps, _parts, _walk
    from shader_fields import Field
    from source_appearance import _digest, _expression
    token = _CACHE.set({}) if _CACHE.get() is None else None
    try:
        full = rigid_shader_pattern_transport(analysis,stage,context)
        result = {'policy': POLICY, 'stage': stage,
            'full_pattern': full if full['nominal_translation_identity_proved'] else None,
            'full_pattern_report': full, 'partial_patterns': [], 'unknown_reasons': [],
            'included_in_total_motion': False, 'uses_shader_execution': False,
            'uses_equation_execution': False, 'uses_rendered_images': False}
        if result['full_pattern'] is not None:return result
        field = analysis.outputs.get(stage)
        if field is None or analysis.stages[stage]['kind'] != 'custom_'+stage:return result
        prefixes = []; identities = set(); attempts = 0
        for count,(node,path) in enumerate(_walk(field,sample_coordinates=False,constant_clipping=True)):
            if count >= 512:
                result['unknown_reasons'].append('partial colour traversal budget exceeded');break
            if any(path == prefix or path.startswith(prefix+'/') for prefix in prefixes):continue
            if node.op not in {'sin','cos','abs','sqrt','pow','length','distance','frac','floor'}:continue
            deps = _deps(node)
            if '_uv' not in deps or not deps & {'time','_c2',':native-render-time-f32'}:continue
            accepted = False
            for lane,part in enumerate(_parts(node)):
                attempts += 1
                if attempts > 32:
                    result['unknown_reasons'].append('partial generator proof budget exceeded');return result
                if part.dtype != 'float':continue
                identity = _digest(_expression(part))
                if identity in identities:continue
                isolated = copy.copy(analysis)
                isolated.outputs = {stage:Field('components',(part,part,part),'float3')}
                report = rigid_shader_pattern_transport(isolated,stage,context)
                if not report['nominal_translation_identity_proved']:continue
                if report['maximum_pattern_speed_vp_per_second'] == 0:continue
                identities.add(identity); accepted = True
                report.update(source_graph_path=path, projected_lane_index=lane,
                    generator_op=node.op, pattern_id='generated_'+identity,
                    role='live_generated_colour_subfield', included_in_total_motion=False,
                    parent_colour_context_held_fixed=True, full_stage_transport_proved=False,
                    parent_conditions=['This isolated generated colour subfield is translated before its parent colour operations',
                        'Parent samples/history, masks, other colour factors and later passes are held fixed and can alter or cancel apparent motion',
                        'Live source use is not nonzero contrast, dominance, visible movement or a complete stage motion bound'])
                result['partial_patterns'].append(report)
            if accepted:prefixes.append(path)
        return result
    except (ValueError,OverflowError,RecursionError,IndexError) as error:
        return {'policy':POLICY,'stage':stage,'full_pattern':None,'partial_patterns':[],
                'included_in_total_motion':False,'unknown_reasons':[str(error)]}
    finally:
        if token is not None:_CACHE.reset(token)
