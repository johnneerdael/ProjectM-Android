"""Frame-free, conservative mechanism recognition from native EEL/typed HLSL IR.

This recognizes program constructions, not moods, genres or certified pictures.
Only contributing RGB and sample-coordinate slices supply shader evidence. Loop
control effects are reported separately: executing dead arithmetic is not drawing
that arithmetic. Neither equations nor shaders are executed by this module.
"""
import hashlib
import json
import math
import re
from contextvars import ContextVar
from pathlib import Path

from equation_loading import select_equation
from scene_equations import MAIN, SHAPE, READONLY, _scalar, source_settings
from shader_fields import Field, ShaderFields, uses_input_components
from stage_resolution import resolve_stages

SCHEMA_VERSION = 1
POLICY = 'source-effect-families-v1'
# Equation audio names, and the shader constants packing them (_c3 bass/mid/treb/vol, _c4 the attenuated bands).
AUDIO_INPUTS = {'bass', 'mid', 'treb', 'bass_att', 'mid_att', 'treb_att', 'vol', 'vol_att', '_c3', '_c4'}
SPATIAL = {'_uv', '_uv_orig', '_rad_ang', 'x', 'y', 'rad', 'ang'}
_CACHE = ContextVar('effect_family_symbolic_cache', default=None)
MAX_FIELD_VISITS = 250000
MAX_NORMALIZED_TERMS = 256
_IMPORT_MODEL_HASHES = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted(Path(__file__).parent.glob('*.py'))
                        if not path.name.startswith('test_')}


class _SemanticBudget(ValueError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _constant(value):
    return Field('constant', detail={'value': value})


def _strip(value):
    while value.op in {'cast', 'narrow'} and len(value.args) == 1:
        value = value.args[0]
    return value


def _number(value):
    cache = _CACHE.get()
    key = ('number', id(value))
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    # Typed scalar constants must be folded before any representation stripping:
    # int(.8) is zero, not .8, and can disconnect a source output completely.
    from source_appearance import _phase_literal
    result=_phase_literal(value)
    if result is None:
        if value.op in {'cast','narrow'} and len(value.args)==1:
            source=_number(value.args[0])
            result=None if source is None else _uniform_scalar_conversion(source,value.dtype)
        else:result=_number_uncached(value)
    if cache is not None:
        cache[key] = (value, result)
    return result


def _uniform_scalar_conversion(number,dtype):
    """Convert a proved uniform scalar/vector literal without erasing its type."""
    base=re.match(r'[A-Za-z]+',dtype)[0]
    if base=='int':
        if not -(2**31)-1<number<2**31:return None
        return float(math.trunc(number))
    if base=='bool':return float(number!=0)
    if base=='float':
        import numpy as np
        from field_math import typed,UnresolvedMath
        try:
            with np.errstate(over='ignore',invalid='ignore'):result=float(typed(number,'float'))
        except UnresolvedMath:return None
        return result if math.isfinite(result) else None
    return None


def _number_uncached(value):
    """Restricted constant folding only; no shader/equation execution."""
    value = _strip(value)
    if value.op == 'constant' and isinstance(value.detail.get('value'), (int, float, bool)):
        result = float(value.detail['value'])
        return result if math.isfinite(result) else None
    if value.op in {'negate', 'unary'} and len(value.args) == 1:
        number = _number(value.args[0])
        if number is not None and (value.op == 'negate' or value.detail.get('operator') == 0):
            return -number
    if value.op in {'construct', 'components'} and value.args:
        numbers = [_number(arg) for arg in value.args]
        if all(n is not None and n == numbers[0] for n in numbers):
            return _uniform_scalar_conversion(numbers[0],value.dtype)
    if value.op in {'add', 'subtract', 'multiply', 'divide'} and len(value.args) == 2:
        a, b = map(_number, value.args)
        if value.op == 'multiply' and (a == 0 or b == 0):
            return 0.
        if a is not None and b is not None and not (value.op == 'divide' and b == 0):
            result = {'add': lambda: a+b, 'subtract': lambda: a-b,
                      'multiply': lambda: a*b, 'divide': lambda: a/b}[value.op]()
            if value.detail.get('numeric_domain')=='shader-float32':
                return _uniform_scalar_conversion(result,value.dtype)
            return result if math.isfinite(result) else None
    if value.op=='eel_equal' and len(value.args)==2:
        a,b=map(_number,value.args)
        if a is not None and b is not None:return float(abs(a-b)<.00001)
        return None
    if value.op in {'less', 'greater', 'less_equal', 'greater_equal', 'equal', 'not_equal'}:
        a, b = map(_number, value.args)
        if a is not None and b is not None:
            return float({'less': a < b, 'greater': a > b, 'less_equal': a <= b,
                          'greater_equal': a >= b, 'equal': a == b, 'not_equal': a != b}[value.op])
    if value.op in {'and', 'or'}:
        a, b = map(_number, value.args)
        if value.op == 'and' and (a == 0 or b == 0):
            return 0.
        if value.op == 'or' and (a not in {0, None} or b not in {0, None}):
            return 1.
        if a is not None and b is not None:
            return float(bool(a) and bool(b) if value.op == 'and' else bool(a) or bool(b))
    return None


def _initial_condition(value):
    """Substitute initial loop slots only for a static zero-iteration proof."""
    plan = value.detail['plan']
    memo = {}
    def substitute(node):
        if id(node) in memo:
            return memo[id(node)]
        if node.op == 'loop_slot' and node.detail.get('plan') is plan:
            result = value.args[plan.names.index(node.detail['name'])]
        else:
            result = Field(node.op, tuple(substitute(arg) for arg in node.args), node.dtype, node.detail)
        memo[id(node)] = result
        return result
    return _number(substitute(plan.condition)) if plan.condition is not None else 1.


def _parts(value):
    cache = _CACHE.get(); key = ('parts', id(value))
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    # Preserve scalar numeric conversions in the sink graph. Downstream pattern
    # helpers may ignore representation casts, but quantitative consumers must
    # distinguish int(time) from continuous time.
    result = tuple(ShaderFields.parts(_PARTS, value))
    if cache is not None:
        cache[key] = (value, result)
    return result


def _surface_level(sample):
    """0 for the previous image, N for blurN of it; None for any other texture."""
    surface = sample.detail.get('surface'); texture = sample.detail.get('canonical_texture') or ''
    if surface == 'pre_composite_feedback':
        return 0
    if surface == 'blur_of_pre_composite_feedback' and texture[:4] == 'blur' and texture[4:].isdigit():
        return int(texture[4:])
    return None


def _surface_terms(value, scale=1., depth=0):
    """(coefficient, level) for previous-image and blur samples entering value linearly. Component
    selections (.x, .xyz) and constant-affine blur decodes are looked through; nonlinear products
    contribute nothing."""
    found = []
    for coefficient, term in _terms(value, scale):
        node = _strip(term); unwrapped = False
        while node.op == 'member' and node.args:
            node = _strip(node.args[0]); unwrapped = True
        if node.op == 'sample':
            level = _surface_level(node)
            if level is not None:
                found.append((coefficient, level))
        elif unwrapped and depth < 4 and node.op in {'add', 'subtract', 'multiply', 'divide'}:
            found.extend(_surface_terms(node, coefficient, depth+1))
    return found


def _rgb_output(value):
    """Follow the native ret.xyz sink, retaining execution-effect wrappers."""
    if value.op == 'sequence':
        return Field('sequence', value.args[:-1]+(_rgb_output(value.args[-1]),), 'float3')
    # Preserve casts until parts applies scalar broadcast/vector truncation.
    # Stripping a float3 cast first would invent lanes for scalar returns and
    # follow discarded float4 values instead of the native RGB assignment.
    parts = _parts(value)
    if len(parts) < 3:
        return Field('unknown', dtype='float3', detail={'reason': 'native RGB output type unresolved'})
    return Field('components', parts[:3], 'float3')


class _StaticParts(ShaderFields):
    def parts(self, value):
        return _parts(value)

    def unsupported(self, reason, args=(), dtype='float'):
        return Field('unknown', args, dtype, {'reason': reason})


_PARTS = _StaticParts(stage='composite', frame=0, warp_reads_blur=False)


def _project(value, indices):
    # Casts can broadcast/truncate lanes or convert their numeric type. Apply
    # typed parts before selecting components instead of erasing that meaning.
    cache = _CACHE.get(); key = ('projection', id(value), tuple(indices))
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    result = _project_uncached(value, indices)
    if cache is not None:
        cache[key] = (value, result)
    return result


def _project_uncached(value, indices):
    shape = ShaderFields.shape(value.dtype)
    if shape is None:
        return Field('unknown', detail={'reason': 'component projection type unresolved'})
    if tuple(indices) == tuple(range(shape[1])) and value.op not in {'cast','construct','aggregate'}:
        return value
    dtype = shape[0] if len(indices) == 1 else shape[0]+str(len(indices))
    if value.op in {'loop_result', 'loop_slot'}:
        return Field(value.op, value.args, dtype, {**value.detail, 'read_components': tuple(indices)})
    parts = _parts(value)
    if any(index >= len(parts) for index in indices):
        return Field('unknown', detail={'reason': 'component projection exceeds type'})
    chosen = tuple(parts[index] for index in indices)
    return chosen[0] if len(chosen) == 1 else Field('components', chosen, dtype)


def _children(value, *, plans=True):
    cache = _CACHE.get(); key = ('children', id(value), plans)
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    result = _children_uncached(value, plans=plans)
    if cache is not None:
        cache[key] = (value, result)
    return result


def _children_uncached(value, *, plans=True):
    """Traverse data, including selected loop updates and their control reads."""
    if value.op in {'cast','construct','aggregate'} and ShaderFields.shape(value.dtype) is not None:
        if value.op == 'cast' and ShaderFields.shape(value.dtype)[1] == 1:
            # The walk already yields this conversion node. Rebuilding it via
            # parts/coerce would manufacture an endless chain of scalar casts.
            return _parts(value.args[0])[:1] if value.args else ()
        parts = _parts(value)
        if any(p.op in {'member','flat_component'} and p.args and p.args[0] is value for p in parts):
            return value.args # Opaque cross-lane types retain their source dependencies.
        return parts
    if value.op == 'member' and value.detail.get('swizzle') and value.args:
        source = value.args[0]; fields = value.detail.get('field', '')
        if source.op == 'member' and source.detail.get('swizzle'):
            inner = source.detail.get('field', '')
            indices = ['xyzw'.index(c) if c in 'xyzw' else 'rgba'.index(c) for c in fields]
            if all(index < len(inner) for index in indices):
                return (Field('member', source.args, value.dtype,
                              {'field': ''.join(inner[i] for i in indices), 'swizzle': True}),)
        if source.op not in {'input', 'sample', 'uninitialized', 'unknown'}:
            indices = tuple('xyzw'.index(c) if c in 'xyzw' else 'rgba'.index(c) for c in fields)
            projected = _project(source, indices)
            if projected.op == 'member' and len(projected.args) == 1 and projected.args[0] is source:
                # Cross-lane operations such as normalize depend on the whole
                # vector. A generic member of itself cannot slice those reads.
                return (source,)
            return (projected,)
    if value.op == 'sequence':
        return value.args[-1:]
    if value.op == 'select':
        number = _number(value.args[0])
        if number is not None:
            return (value.args[1 if number else 2],)
    if value.op == 'multiply' and any(_number(arg) == 0 for arg in value.args):
        return ()
    if value.op == 'subtract' and len(value.args) == 2 and _same(*value.args):
        if _number(value) == 0:
            return ()
        # x-x is zero only in a finite domain. Native author programs may
        # produce NaN/Inf, so abstain from a positive mechanism claim instead
        # of asserting a constant zero for those unresolved inputs.
        return (Field('unknown', dtype=value.dtype, detail={
            'reason': 'algebraic cancellation requires finite intermediate values; contribution unresolved'}),)
    if plans and value.op == 'loop_result':
        plan = value.detail['plan']
        name = value.detail.get('name')
        if name is None:
            return ()  # effect-only loops do not contribute their values to RGB
        if _initial_condition(value) == 0:
            initial = value.args[plan.names.index(name)]
            indices = value.detail.get('read_components')
            return (_project(initial, indices) if indices is not None else initial,)
        update = plan.updates.get(name)
        # Native loop arguments hold every initialized carried slot for runtime
        # storage, including unrelated slots. Only selected/transitively read
        # slots supply causal data evidence for this output.
        indices = value.detail.get('read_components')
        def selected(node):
            return _project(node, indices) if indices is not None else node
        result = [selected(value.args[plan.names.index(name)])]
        if update is not None:
            result.append(selected(update))
        if plan.condition is not None:
            result.append(plan.condition)
        # Other evolving slots may feed this slot through the loop body.
        pending = [selected(update)] if update is not None else []
        if plan.condition is not None:
            pending.append(plan.condition)
        seen = set()
        while pending:
            node = pending.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            if node.op == 'loop_slot' and node.detail.get('plan') is plan:
                slot_name = node.detail['name']
                initial = value.args[plan.names.index(slot_name)]
                components = node.detail.get('read_components')
                if components is not None:
                    initial = _project(initial, components)
                if all(existing is not initial for existing in result):
                    result.append(initial)
                dependency = plan.updates.get(slot_name)
                if dependency is not None and components is not None:
                    dependency = _project(dependency, components)
                if dependency is not None and all(existing is not dependency for existing in result):
                    result.append(dependency)
                    pending.append(dependency)
            pending.extend(_children(node))
        return tuple(result)
    return value.args


def _walk(value,*,sample_coordinates=True,constant_clipping=False,preserve_zero_products=False):
    pending = [(value, 'output')]
    seen = set()
    while pending:
        node, path = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        cache = _CACHE.get()
        if cache is not None:
            cache['field_visits'] = cache.get('field_visits', 0)+1
            if cache['field_visits'] > MAX_FIELD_VISITS:
                cache['traversal_budget_exhausted'] = True
                raise _SemanticBudget('static field traversal budget exceeded')
        yield node, path
        children=() if node.op=='sample' and not sample_coordinates else _children(node)
        if preserve_zero_products and node.op=='multiply':children=node.args
        if constant_clipping:
            from source_forms import constant_colour_clip_children
            clipped=constant_colour_clip_children(node)
            if clipped is not None:children=clipped
        pending.extend((arg, path + '/' + node.op + '[' + str(index) + ']')
                       for index, arg in enumerate(children))


def _deps(value):
    cache = _CACHE.get()
    key = ('dependencies', id(value))
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    result = {node.detail['name'] for node, _ in _walk(value) if node.op == 'input'}
    if cache is not None:
        cache[key] = (value, result)
    return result


def _masked_by_output(root,target):
    """One causal DAG pass identifies descendants of unknown multipliers."""
    cache=_CACHE.get()
    if cache is None:
        # Preserve the original identity test for callers outside an audit:
        # without shared parts/projection memoization, synthetic node identities
        # need not agree between separately captured walks and child edges.
        return any(n.op=='multiply' and any(k is target for k,path in _walk(n)) and _number(n) is None
                   for n,path in _walk(root))
    key=('output_multiplier_nodes',id(root))
    saved=None if cache is None else cache.get(key)
    if saved is not None and saved[0] is root:
        nodes,masked=saved[1:]
    else:
        # _walk charges the existing traversal budget. Capture each causal edge
        # as visited, retaining synthesized nodes and strong identity throughout.
        nodes={};edges={};pending=[]
        for node,path in _walk(root):
            key_id=id(node);nodes[key_id]=node;edges[key_id]=tuple(_children(node))
            if node.op=='multiply' and _number(node) is None:pending.append(node)
        masked=set()
        while pending:
            node=pending.pop();key_id=id(node)
            if key_id in masked:continue
            masked.add(key_id);pending.extend(edges.get(key_id,()))
        # Do not cache partial graph facts if a walk/domain/budget check failed.
        if cache is not None:cache[key]=(root,nodes,masked)
    return id(target) in masked and nodes.get(id(target)) is target


def _has(value, op):
    return any(node.op == op for node, _ in _walk(value))


def _ops_below(roots, ops):
    """{id(node): wanted ops in the subtree} for each root's first argument and its descendants.

    One memoised post-order pass over subtrees an earlier _walk already visited, so it adds no
    traversal-budget charge and visits each node once however many roots share it."""
    wanted = frozenset(ops); memo = {}
    for root in roots:
        stack = [(root.args[0], False)]
        while stack:
            node, done = stack.pop()
            if id(node) in memo:continue
            children = _children(node)
            if done:
                found = wanted & {node.op}
                for child in children:found = found | memo.get(id(child), frozenset())
                memo[id(node)] = frozenset(found)
            else:
                stack.append((node, True)); stack.extend((child, False) for child in children if id(child) not in memo)
    return memo


def _sample_offset(node):
    """(base, offset lanes) of a sample at uv + offset: base is the identity UV term of each lane,
    offset lanes are (constant, {key: (coefficient, term)}) for the remaining terms. None otherwise."""
    lanes = _parts(node.args[0])
    if len(lanes) != 2:return None
    base, offset = [], []
    for lane in lanes:
        identity, rest, constant = None, {}, 0.
        for coefficient, term in _terms(lane):
            number = _number(term)
            if number is not None:constant += coefficient*number
            elif identity is None and coefficient == 1 and _affine_degree(term) == 1 and \
                    _spatial_inputs(term) <= {'_uv', '_uv_orig'}:identity = term
            else:rest[_key(term)] = (coefficient, term)
        if identity is None:return None
        base.append(_key(identity)); offset.append((round(constant, 9), rest))
    return tuple(base), offset


def _offset_signature(lanes, sign=1):
    return tuple((sign*c+0., tuple(sorted((k, round(sign*v[0], 9)+0.) for k, v in r.items()))) for c, r in lanes)


def _weighted_samples(value):
    """{(base, offset lanes, sampler): weight} when value is a constant-weighted sum of image samples
    at uv offsets (channel selections and casts allowed); None when another term takes part."""
    found = {}
    for coefficient, term in _terms(value):
        node = _strip(term)
        while node.op in {'member', 'cast', 'flat_component'} and node.args:node = _strip(node.args[0])
        if node.op != 'sample':return None
        located = _sample_offset(node)
        if located is None:return None
        key = (located[0], _offset_signature(located[1]), node.detail.get('sampler'))
        found[key] = found.get(key, 0.) + round(coefficient, 9)
    return found


def _negated(signature):
    return tuple((-c+0., tuple((k, -v+0.) for k, v in terms)) for c, terms in signature)


def _is_spatial_input(node):
    return (node.op=='input' and node.detail.get('name') in SPATIAL and not
            (node.detail.get('equation_phase') in {'per_frame_','per_frame_init_'} and
             node.detail.get('value_binding')=='phase_scalar_snapshot'))


def _spatial_inputs(value):
    cache=_CACHE.get();key=('spatial_inputs',id(value))
    if cache is not None and key in cache and cache[key][0] is value:return cache[key][1]
    result={node.detail['name'] for node,path in _walk(value) if _is_spatial_input(node)}
    if cache is not None:cache[key]=(value,result)
    return result


def _spatial(value):
    return bool(_spatial_inputs(value))


def _key(value):
    """Structural identity survives helpers, casts and author temporary names."""
    value = _strip(value)
    cache = _CACHE.get()
    if cache is None:
        cache = {}
    identifier = ('key', id(value))
    saved = cache.get(identifier)
    if saved is not None and saved[0] is value:
        return saved[1]
    if value.op == 'member':
        field = value.detail.get('field', '')
        field = ''.join('xyzw'['rgba'.index(c)] if c in 'rgba' else c for c in field)
        identity = ('member', _key(value.args[0]), field)
    elif value.op == 'loop_slot':
        identity = ('slot', id(value.detail['plan']), value.detail['name'], value.detail.get('read_components'))
    elif value.op == 'input':
        identity = ('input', value.detail['name'],value.detail.get('equation_phase'),
                    value.detail.get('value_binding'),value.detail.get('state_scope'))
    elif value.op == 'constant':
        identity = ('constant', str(_number(value)))
    elif value.op == 'rand':
        # Equal call syntax is not equal evaluated storage. Exact aliases keep
        # the same node; separate stateful draws cannot cancel or prove grey.
        identity = ('stateful_rand_value', id(value))
    else:
        detail = tuple((name, str(value.detail.get(name))) for name in
                       ('operator', 'index', 'sampler', 'surface', 'name', 'field', 'read_components') if name in value.detail)
        if value.op == 'loop_result':
            detail += (('plan', id(value.detail['plan'])),)
        identity = (value.op, detail, tuple(_key(arg) for arg in value.args))
    # Interned small integers avoid exponential tuple expansions of shared DAGs.
    intern = cache.setdefault('intern', {})
    result = intern.setdefault(identity, len(intern)) if _CACHE.get() is not None else identity
    cache[identifier] = (value, result)
    return result


def _same(a, b):
    return _key(a) == _key(b)


def _angle(value):
    cache=_CACHE.get();key=('angle_presence',id(value))
    if cache is not None and key in cache and cache[key][0] is value:return cache[key][1]
    result=any(node.op == 'atan2' and _spatial(node) or
               node.op == 'member' and node.detail.get('field') in {'y', 'g'} and
               node.args[0].op == 'input' and node.args[0].detail.get('name') == '_rad_ang' or
               _is_spatial_input(node) and node.detail.get('name') == 'ang'
               for node, _ in _walk(value))
    if cache is not None:cache[key]=(value,result)
    return result


def _radius(value):
    cache=_CACHE.get();key=('radius_presence',id(value))
    if cache is not None and key in cache and cache[key][0] is value:return cache[key][1]
    result=any(node.op in {'length', 'distance'} and _spatial(node) or
               node.op == 'member' and node.detail.get('field') in {'x', 'r'} and
               node.args[0].op == 'input' and node.args[0].detail.get('name') == '_rad_ang' or
               _is_spatial_input(node) and node.detail.get('name') == 'rad'
               for node, _ in _walk(value))
    if cache is not None:cache[key]=(value,result)
    return result


def _radial_depth(value):
    for node, _ in _walk(value):
        if node.op == 'divide' and not _spatial(node.args[0]) and _radius(node.args[1]):
            return 'reciprocal_radius'
        if node.op in {'log', 'log2', 'log10'} and _radius(node.args[0]):
            return 'log_radius'
    return None


def _box_reflections(value):
    result = []
    for node, _ in _walk(value):
        if node.op != 'subtract':
            continue
        coefficient, factors = _product(node.args[0])
        if coefficient != 2 or len(factors) != 1:
            continue
        clamp = factors[0]
        if clamp.op == 'clamp' and len(clamp.args) == 3 and _number(clamp.args[1]) == -1 and _number(clamp.args[2]) == 1 and _same(node.args[1], clamp.args[0]):
            result.append(node)
    return result


def _affine_degree(value):
    value = _strip(value)
    if not _spatial(value):
        return None if _has(value, 'sample') or _has(value, 'loop_slot') else 0
    if value.op == 'input':
        return 1 if value.detail['name'] in {'_uv', '_uv_orig', 'x', 'y'} else None
    if value.op in {'member', 'flat_component'}:
        return _affine_degree(value.args[0])
    if value.op in {'add', 'subtract', 'construct', 'components'}:
        degrees = [_affine_degree(arg) for arg in value.args]
        return max(degrees) if degrees and all(d is not None for d in degrees) else None
    if value.op == 'multiply':
        a, b = map(_affine_degree, value.args)
        return a+b if a is not None and b is not None and a+b <= 1 else None
    if value.op == 'divide' and _affine_degree(value.args[1]) == 0:
        return _affine_degree(value.args[0])
    return None


def _terms(value, scale=1.):
    value = _strip(value)
    cache = _CACHE.get()
    key = ('terms', id(value))
    saved = cache.get(key) if cache is not None else None
    if saved is not None and saved[0] is value:
        result = saved[1]
    else:
        terms = None
        if value.op in {'add', 'subtract'}:
            terms = _terms(value.args[0]) + _terms(value.args[1], -1 if value.op == 'subtract' else 1)
        elif value.op == 'multiply':
            for index in (0, 1):
                number = _number(value.args[index])
                if number is not None:
                    terms = _terms(value.args[1-index], number)
                    break
        elif value.op == 'divide':
            denominator = _number(value.args[1])
            if denominator not in {None, 0}:
                terms = _terms(value.args[0], 1/denominator)
        if terms is None:
            result = [(1., value)]
        else:
            merged = {}
            for coefficient, term in terms:
                identity = _key(term)
                previous = merged.get(identity, (0., term))[0]
                total = previous+coefficient
                if not math.isfinite(total):
                    raise _SemanticBudget('static normalized coefficient exceeds finite domain')
                merged[identity] = (total, term)
            result = [term for term in merged.values() if term[0] != 0]
            if len(result) > MAX_NORMALIZED_TERMS:
                raise _SemanticBudget('static normalized term budget exceeded')
        if cache is not None:
            cache[key] = (value, result)
            cache['normalized_term_nodes'] = cache.get('normalized_term_nodes', 0)+1
    return [(coefficient*scale, term) for coefficient, term in result]


def _product(value):
    value = _strip(value)
    cache = _CACHE.get(); key = ('product', id(value))
    if cache is not None and key in cache and cache[key][0] is value:
        return cache[key][1]
    result = _product_uncached(value)
    if len(result[1]) > MAX_NORMALIZED_TERMS:
        raise _SemanticBudget('static product factor budget exceeded')
    if cache is not None:
        cache[key] = (value, result)
    return result


def _product_uncached(value):
    value = _strip(value)
    if value.op == 'multiply':
        a, b = map(_product, value.args)
        return a[0]*b[0], a[1]+b[1]
    number = _number(value)
    return (number, []) if number is not None else (1., [value])


def _quadratic(value):
    """Recognize both complex lanes on the same prior scalar components."""
    parts = _parts(value)
    if len(parts) != 2:
        return None
    real = _terms(parts[0]); imaginary = _terms(parts[1])
    squares = []
    for sign, term in real:
        coefficient, factors = _product(term)
        if len(factors) == 2 and _same(*factors) and sign*coefficient in {1., -1.}:
            squares.append((sign*coefficient, factors[0], term))
    for sx, x, tx in squares:
        for sy, y, ty in squares:
            if sx != 1 or sy != -1 or _same(x, y):
                continue
            for sign, term in imaginary:
                coefficient, factors = _product(term)
                if sign*coefficient == 2 and len(factors) == 2 and (
                    _same(factors[0], x) and _same(factors[1], y) or
                    _same(factors[1], x) and _same(factors[0], y)):
                    residual = [n for _, n in real if n is not tx and n is not ty]
                    residual += [n for _, n in imaginary if n is not term]
                    return {'x': x, 'y': y, 'parameter_spatial': any(_spatial(n) for n in residual),
                            'parameter': residual}
    return None


def _trig_pair(value):
    nodes = list(_walk(value))
    cosines = [n for n, _ in nodes if n.op == 'cos']
    sines = [n for n, _ in nodes if n.op == 'sin']
    return [(c.args[0], c, s) for c in cosines for s in sines if _same(c.args[0], s.args[0])]


def _radial_curve(x, y):
    """Require the paired angular factors on separate projected position lanes."""
    for cx, tx in _terms(x):
        scale_x, factors_x = _product(tx)
        for cy, ty in _terms(y):
            scale_y, factors_y = _product(ty)
            for a in factors_x:
                for b in factors_y:
                    if {a.op, b.op} != {'sin', 'cos'} or not _same(a.args[0], b.args[0]):
                        continue
                    radius_x = [f for f in factors_x if f is not a]
                    radius_y = [f for f in factors_y if f is not b]
                    if cx*scale_x == 0 or cy*scale_y == 0 or sorted(_key(f) for f in radius_x) != sorted(_key(f) for f in radius_y):
                        continue
                    return a.args[0]
    return None


def _sector_count(phase):
    for node, _ in _walk(phase):
        if node.op not in {'frac', 'fmod', 'remainder'}:
            continue
        for term_scale, term in _terms(node.args[0]):
            scale, factors = _product(term)
            scale *= term_scale
            if _angle(term) and term.op in {'member', 'atan2', 'input'}:
                count = abs(term_scale)*math.tau
                if round(count) >= 1 and abs(count-round(count)) < .02:
                    return round(count)
            for factor in factors:
                if factor.op == 'divide' and _angle(factor.args[0]):
                    divisor = _number(factor.args[1])
                    if divisor is not None and 6. < abs(divisor) < 6.4:
                        rounded = round(abs(scale))
                        if rounded >= 1 and abs(abs(scale)-rounded) < 1e-5:
                            return rounded
    return None


def _angular_fold(phase):
    for node, _ in _walk(phase):
        if node.op != 'abs':
            continue
        terms = _terms(node.args[0])
        wrapped = [(coefficient, term) for coefficient, term in terms
                   if term.op in {'frac', 'fmod', 'remainder'} and _angle(term.args[0])]
        offset = sum(coefficient*(_number(term) or 0) for coefficient, term in terms if _number(term) is not None)
        if any(abs(coefficient) == 2 for coefficient, _ in wrapped) and abs(offset) == 1:
            return True
    return False


def _complex_coordinate_map(parts):
    if len(parts) != 2:
        return False
    lanes = []
    for lane in parts:
        candidates = [n for n, _ in _walk(lane) if n.dtype == 'float' and n.op in {'subtract', 'multiply', 'add'}]
        if len(candidates) > MAX_NORMALIZED_TERMS:
            raise _SemanticBudget('complex map candidate budget exceeded')
        lanes.append(candidates)
    for x in lanes[0]:
        terms = _terms(x)
        squares = [(coefficient*c, factors) for coefficient, term in terms
                   for c, factors in [_product(term)] if len(factors) == 2 and _same(*factors)]
        if not (any(sign == 1 for sign, _ in squares) and any(sign == -1 for sign, _ in squares)):
            continue
        for y in lanes[1]:
            if _quadratic(Field('components', (x,y), 'float2')):
                return True
    return False


def _periodic_advection(parts):
    for lane in parts:
        terms = _terms(lane)
        base = any(_affine_degree(term) == 1 for _, term in terms)
        offset = any(_has(term, 'sin') or _has(term, 'cos') for _, term in terms)
        if base and offset:
            return True
    return False


class _EelLoopPlan:
    """Plan of a fixed-count EEL loop (eel_memory): written names, their per-iteration updates."""
    kind='eel_count'

    def __init__(self,names):
        from eel_memory import MAX_LOOP_COUNT
        self.names=list(names);self.condition=None;self.updates={};self.effects=[];self.iteration_limit=MAX_LOOP_COUNT


class _EEL:
    """Symbolic native EEL tree substitution; fixed-count loops and megabuf memory are versioned
    (eel_memory); while loops and other stateful forms remain unknown."""
    COMPOUND={'_addop':'add','_subop':'subtract','_mulop':'multiply','_divop':'eel_divide',
              '_modop':'remainder','_orop':'eel_bitwise_or','_andop':'eel_bitwise_and'}
    OPS = {'_add': 'add', '_sub': 'subtract', '_mul': 'multiply', '_div': 'eel_divide',
           '_mod': 'remainder', '_neg': 'negate', '_equal': 'equal',
           '_below': 'less', '_above': 'greater', 'below': 'less', 'above': 'greater',
           'equal': 'equal', 'if': 'select', '/*and*/': 'eel_bitwise_and', '/*or*/': 'eel_bitwise_or'}

    def __init__(self, environment=None,*,equation_phase=None,memory_written=None):
        self.environment = dict(environment or {})
        # Buffers some block of the preset writes; None when unknown. Both buffers start zeroed,
        # so a buffer that no block writes reads 0.
        self.memory_written = memory_written
        self.equation_phase=equation_phase
        self.written = set()
        self.unknown = []
        self.random_site_count = 0
        # Current version of each megabuf/gmegabuf buffer (eel_memory): starts as the buffer input.
        self.memory = {}

    def memory_version(self,space):
        if space not in self.memory:
            self.memory[space]=Field('input',detail={'name':'memory:'+space,'equation_phase':self.equation_phase,
                'value_binding':'memory_buffer'})
        return self.memory[space]

    @staticmethod
    def memory_target(node):
        if isinstance(node,dict) and node.get('kind')=='call' and node.get('function')=='mem' and len(node.get('args',[]))==1:
            return node.get('memory_space') if node.get('memory_space') in {'global','local'} else None
        return None

    @classmethod
    def memory_spaces_written(cls,tree):
        spaces=set();pending=[tree]
        while pending:
            node=pending.pop()
            if isinstance(node,list):pending.extend(node);continue
            if not isinstance(node,dict):continue
            if node.get('function') in {'assign','_set',*cls.COMPOUND} and node.get('args'):
                space=cls.memory_target(node['args'][0])
                if space is not None:spaces.add(space)
            pending.extend(v for v in node.values() if isinstance(v,(dict,list)))
        return spaces

    def fixed_count_loop(self,tree):
        """loop(n, body) as an eel_memory plan: written names get slots, results carry the final values."""
        count=self.lower(tree['args'][0])
        body=tree['args'][1]
        names=sorted(self.assignment_targets(body))+['memory:'+s for s in sorted(self.memory_spaces_written(body))]+['__value']
        plan=_EelLoopPlan(names)
        initial={}
        for name in names:
            if name=='__value':initial[name]=_constant(0)
            elif name.startswith('memory:'):initial[name]=self.memory_version(name.split(':',1)[1])
            else:initial[name]=self.lower({'kind':'variable','name':name})
        outer=dict(self.environment);outer_memory=dict(self.memory)
        for name in names:
            slot=Field('loop_eel_slot',detail={'plan':plan,'name':name})
            if name.startswith('memory:'):self.memory[name.split(':',1)[1]]=slot
            elif name!='__value':self.environment[name]=slot
        result=self.lower(body)
        for name in names:
            if name=='__value':plan.updates[name]=result
            elif name.startswith('memory:'):plan.updates[name]=self.memory[name.split(':',1)[1]]
            else:plan.updates[name]=self.environment[name]
        self.environment=outer;self.memory=outer_memory
        # Arguments: count, start values, then the updates, so graph walkers see what the body reads.
        arguments=(count,*(initial[name] for name in names),*(plan.updates[name] for name in names))
        results={name:Field('loop_eel_result',arguments,detail={'plan':plan,'name':name}) for name in names}
        for name in names:
            if name.startswith('memory:'):self.memory[name.split(':',1)[1]]=results[name]
            elif name!='__value':self.environment[name]=results[name];self.written.add(name)
        return results['__value']

    @classmethod
    def assignment_targets(cls,tree):
        written=set();pending=[tree];seen=set()
        while pending:
            node=pending.pop()
            if not isinstance(node,(dict,list)) or id(node) in seen:continue
            seen.add(id(node))
            if len(seen)>MAX_FIELD_VISITS:raise _SemanticBudget('equation assignment inventory budget exceeded')
            if isinstance(node,list):pending.extend(node);continue
            if node.get('function') in {'assign','_set',*cls.COMPOUND} and node.get('args') and node['args'][0].get('kind')=='variable':
                written.add(node['args'][0]['name'].lower())
            pending.extend(v for v in node.values() if isinstance(v,(dict,list)))
        return written

    def lower(self, tree):
        if tree is None:
            return _constant(0)
        kind = tree.get('kind')
        if kind == 'constant':
            return _constant(tree['value'])
        if kind == 'variable':
            name = tree['name'].lower()
            if name in self.environment:return self.environment[name]
            detail={'name':name}
            if self.equation_phase is not None:
                detail.update(equation_phase=self.equation_phase,
                    value_binding='shared_register' if re.fullmatch(r'reg[0-9]{2}',name) else 'phase_scalar_snapshot')
            return Field('input',detail=detail)
        if kind != 'call':
            self.unknown.append('unrecognized EEL tree node')
            return Field('unknown')
        function = tree['function']
        if function == 'sequence':
            result = _constant(0)
            for instruction in tree.get('instructions', []):
                result = self.lower(instruction)
            return result
        if function == 'mem' and self.memory_target(tree) is not None:
            space=self.memory_target(tree)
            if self.memory_written is not None and space not in self.memory_written:
                self.lower(tree['args'][0]);return _constant(0)
            return Field('array_mem_read',(self.memory_version(space),self.lower(tree['args'][0])),detail={'space':space})
        if function in {'assign','_set',*self.COMPOUND} and self.memory_target(tree['args'][0]) is not None:
            space=self.memory_target(tree['args'][0])
            index=self.lower(tree['args'][0]['args'][0]);right=self.lower(tree['args'][1])
            before=self.memory_version(space)
            value=right if function in {'assign','_set'} else self.operation(self.COMPOUND[function],
                (Field('array_mem_read',(before,index),detail={'space':space}),right))
            self.memory[space]=Field('array_mem_write',(before,index,value),detail={'space':space})
            return value
        if function == 'loop' and len(tree.get('args',[]))==2:
            return self.fixed_count_loop(tree)
        if function in {'assign','_set'} and tree['args'][0].get('kind') == 'variable':
            name = tree['args'][0]['name'].lower()
            value = self.lower(tree['args'][1])
            self.environment[name] = value; self.written.add(name)
            return value
        if function in self.COMPOUND and tree['args'][0].get('kind')=='variable':
            name=tree['args'][0]['name'].lower()
            right=self.lower(tree['args'][1]);left=self.environment.get(name,Field('input',detail={'name':name}))
            value=self.operation(self.COMPOUND[function],(left,right))
            self.environment[name]=value;self.written.add(name)
            return value
        if function in {'if','_if'} and len(tree.get('args', [])) == 3:
            condition = self.lower(tree['args'][0]); number = _number(condition)
            if number is not None:
                return self.lower(tree['args'][1 if number else 2])
            before = dict(self.environment); memory_before = dict(self.memory)
            yes = self.lower(tree['args'][1]); env_yes = dict(self.environment); memory_yes = dict(self.memory)
            self.environment = dict(before); self.memory = dict(memory_before)
            no = self.lower(tree['args'][2]); env_no = dict(self.environment); memory_no = dict(self.memory)
            for name in env_yes.keys() | env_no.keys():
                y = env_yes.get(name, before.get(name, Field('input', detail={'name': name})))
                n = env_no.get(name, before.get(name, Field('input', detail={'name': name})))
                self.environment[name] = y if _same(y, n) else Field('select', (condition, y, n))
            for space in memory_yes.keys() | memory_no.keys():
                # A branch that never touched the buffer keeps the version from before the if.
                base = memory_before.get(space)
                if base is None:
                    base = Field('input', detail={'name': 'memory:' + space, 'equation_phase': self.equation_phase,
                                                  'value_binding': 'memory_buffer'})
                y = memory_yes.get(space, base); n = memory_no.get(space, base)
                self.memory[space] = y if y is n else Field('select', (condition, y, n))
            return Field('select', (condition, yes, no))
        if function in {'loop', 'while', 'mem', 'assign'}:
            self.unknown.append('stateful EEL ' + function + ' is not statically normalized')
            # Invalidate destinations; retaining their pre-loop value would invent absence.
            def writes(node):
                if isinstance(node, dict):
                    if node.get('function') in {'assign','_set',*self.COMPOUND} and node.get('args', [{}])[0].get('kind') == 'variable':
                        name = node['args'][0]['name'].lower()
                        self.environment[name] = Field('unknown', detail={'reason': function})
                        self.written.add(name)
                    for child in node.values():
                        writes(child)
                elif isinstance(node, list):
                    for child in node:
                        writes(child)
            writes(tree)
            return Field('unknown', detail={'reason': function})
        # Native operators can retain pointers to variable storage while later
        # arguments overwrite it. Value substitution cannot certify that case.
        embedded=self.assignment_targets(tree.get('args',[]))
        if embedded:
            reason='native expression reference aliases require separate interpretation'
            self.unknown.append(reason)
            for name in embedded:
                self.environment[name]=Field('unknown',detail={'reason':reason});self.written.add(name)
            return Field('unknown',detail={'reason':reason})
        args=tuple(self.lower(arg) for arg in tree.get('args',[]))
        if function=='rand':
            site=self.random_site_count;self.random_site_count+=1
            return Field('rand',args,detail={'site_index':site,'equation_phase':self.equation_phase,
                'value_binding':'stateful_random_call'})
        return self.operation(self.OPS.get(function,function),args)

    @staticmethod
    def operation(op,args):
        if op=='equal':return Field('eel_equal',args)
        if op=='eel_divide' and len(args)==2:
            denominator=_number(args[1])
            if denominator is not None:
                if abs(denominator)<.00001:return _constant(0)
                return Field('divide',args)
        return Field(op,args)


class _Analysis:
    def __init__(self, source, profile, compatibility):
        self.source = source; self.sections = source['sections']
        self.values = source_settings(source)
        self.stages = resolve_stages(source, profile=profile, compatibility=compatibility or {})
        self.families = []; self.unknowns = []; self.seen = set()
        self.policy = source.get('equation_assembly_policy', 'strict-raw-v1')
        self.profile = profile
        self.outputs = {}

    def evidence(self, section, pattern, path):
        selected = self.sections.get(section, {})
        keys = []; locations = []
        numbered = self.source.get('numbered_source', '')
        if isinstance(numbered, str):
            first = {}
            for line_number, line in enumerate(numbered.splitlines(), 1):
                key = line.partition('=')[0].strip()
                if re.fullmatch(re.escape(section) + r'\d+', key):
                    first.setdefault(key, line_number)
            for index in range(1, len(first)+1):
                key = section + str(index)
                if key not in first:
                    break
                keys.append(key); locations.append({'key': key, 'line': first[key]})
        return {'section': section, 'source_sha256': hashlib.sha256(selected.get('source', '').encode()).hexdigest(),
                'causal_pattern': pattern, 'output_path': path, 'source_keys': keys,
                'source_locations': locations,
                'location_scope': 'section; locations are not inferred token-level pattern spans'}

    def add(self, mechanism, section, node, pattern, *, path='output', parameters=None,
            component=None, conditions=()):
        identity = (mechanism, section, component, _digest(parameters or {}))
        if identity in self.seen:
            return
        self.seen.add(identity)
        stage = {'warp_': 'warp', 'comp_': 'composite', 'per_pixel_': 'mesh_warp'}.get(section, 'drawing')
        extra = list(conditions)
        if stage in {'warp', 'composite'}:
            selected = self.stages[stage]
            if selected['kind'] == 'unknown':
                extra.append('custom shader must compile and remain selected on the target profile')
        if any(n.op == 'select' and _number(n.args[0]) is None for n, _ in _walk(node)):
            extra.append('runtime branch/mask selects this construction')
        output = self.outputs.get(stage)
        dependencies = _deps(node)
        if output is not None:
            dependencies = dependencies | _deps(output)
            if _masked_by_output(output,node):
                extra.append('runtime output multiplier/mask retains this construction')
            if any(n.op == 'select' and _number(n.args[0]) is None for n, _ in _walk(output)):
                extra.append('runtime branch/mask selects this construction')
        deps = sorted(dependencies)
        if any(n.op == 'sample' for n, _ in _walk(node)):
            extra.append('sampled texture/feedback must contain contributing image content')
        self.families.append({'mechanism': mechanism, 'stage': stage, 'component': component,
            'status': 'proven_program_mechanism', 'parameters': parameters or {},
            'input_dependencies': deps, 'conditions': list(dict.fromkeys(extra)),
            'contribution': {'status': 'live', 'basis': 'causal source output slice',
                             'guaranteed_nonzero': False},
            'appearance': {'status': 'conditional', 'guaranteed_visible_family': False,
                          'conditions': ['projection, clipping, opacity and later composition retain the contribution',
                                         'source inputs are in a usable domain'] + list(dict.fromkeys(extra))},
            'evidence': [self.evidence(section, pattern, path)]})

    def equation(self, prefix, environment):
        section = self.sections.get(prefix)
        selected = select_equation(section, prefix, policy=self.policy)
        model = _EEL(environment,equation_phase=prefix,memory_written=self.memory_written())
        if selected['compile_status'] == 'omitted':
            self.unknowns.append({'section': prefix, 'reason': 'native equation loader omits rejected block'})
            return model
        if selected['compile_status'] != 'accepted' or selected['tree_status'] != 'parsed':
            self.unknowns.append({'section': prefix, 'reason': 'active equation tree/loading is unresolved'})
            return model
        model.lower(selected['tree'])
        self.unknowns.extend({'section': prefix, 'reason': reason} for reason in dict.fromkeys(model.unknown))
        return model

    def memory_written(self):
        """megabuf/gmegabuf spaces written by any accepted equation block of the preset."""
        if not hasattr(self,'_memory_written'):
            spaces=set()
            for prefix,section in self.sections.items():
                if not isinstance(section,dict):continue
                selected=select_equation(section,prefix,policy=self.policy)
                if selected['compile_status']!='accepted':continue
                if selected['tree_status']!='parsed':return None
                spaces|=_EEL.memory_spaces_written(selected['tree'])
            self._memory_written=frozenset(spaces)
        return self._memory_written

    def frame_environment(self,prefix,initialized,resets,uninitialized_state=False):
        """Reload target fields; persistent written locals need previous-state inputs.

        uninitialized_state: locals the block writes but init does not set also persist from 0, so
        they read their previous value as 'state:<prefix>:<name>' (custom-wave per-frame contexts).
        """
        selected=select_equation(self.sections.get(prefix),prefix,policy=self.policy)
        written=_EEL.assignment_targets(selected.get('tree'))
        inputs=dict(initialized)
        if uninitialized_state:
            for name in written-inputs.keys()-resets.keys():
                if not re.fullmatch(r'reg[0-9]{2}',name):
                    inputs[name]=Field('input',detail={'name':'state:'+prefix+':'+name,'state_scope':'previous persistent value (initially 0)',
                        'equation_phase':prefix,'value_binding':'phase_scalar_snapshot'})
        for name in inputs.keys()-resets.keys():
            if name in written or re.fullmatch(r'reg[0-9]{2}',name):
                scope='shared:'+name if re.fullmatch(r'reg[0-9]{2}',name) else 'state:'+prefix+':'+name
                inputs[name]=Field('input',detail={'name':scope,'state_scope':'previous persistent or shared register value',
                    'equation_phase':prefix,'value_binding':'shared_register' if scope.startswith('shared:') else 'phase_scalar_snapshot'})
        inputs.update(resets)
        return inputs

    def main_equations(self):
        environment = {name: _constant(_scalar(self.values, key, default, kind))
                       for name, (key, default, kind) in MAIN.items()}
        # Native PresetState: bMotionVectorsOn supplies mv_a=1 unless mv_a is set.
        environment['mv_a'] = _constant(_scalar(self.values, 'mv_a',
            _scalar(self.values, 'bMotionVectorsOn', 0, 'bool'), 'float'))
        # The native preset owns a zero-initialized complete Q snapshot.
        # Init writes then establish values reloaded before main frame code.
        environment.update({f'q{i}':_constant(0) for i in range(1,33)})
        init_inputs={**environment,**{name:Field('input',detail={'name':'init:per_frame_init_:'+name})
                                     for name in READONLY}}
        init = self.equation('per_frame_init_', init_inputs)
        resets={**environment,**{name:Field('input',detail={'name':name}) for name in
            (*READONLY,'meshx','meshy','pixelsx','pixelsy','aspectx','aspecty')},
            **{f'q{i}':init.environment.get(f'q{i}',_constant(0)) for i in range(1,33)}}
        frame = self.equation('per_frame_',self.frame_environment('per_frame_',init.environment,resets))
        self.main = frame.environment
        # Kept for the frame-program export (state recurrence over declared inputs).
        self.frame_init = init.environment
        self.frame_memory = frame.memory; self.frame_init_memory = init.memory
        # PerPixelContext is a separate evaluator. Readonly values are copied
        # before main frame code; warp controls reload each vertex. Q values
        # copy once after main code and may then evolve across vertices.
        readonly=(*READONLY,'meshx','meshy','pixelsx','pixelsy','aspectx','aspecty')
        pixel_resets={**{name:frame.environment.get(name,Field('input',detail={'name':name}))
                         for name in ('zoom','zoomexp','rot','warp','cx','cy','dx','dy','sx','sy')},
                      **{name:Field('input',detail={'name':name,'native_mesh_reset_input':True}) for name in ('x','y','rad','ang')}}
        pixel_initial={**pixel_resets,**{name:resets[name] for name in readonly},
                       **{f'q{i}':frame.environment.get(f'q{i}',_constant(0)) for i in range(1,33)}}
        mesh = self.equation('per_pixel_',self.frame_environment('per_pixel_',pixel_initial,pixel_resets))
        self.mesh_controls=mesh.environment
        for name in ('rot', 'zoom', 'zoomexp', 'sx', 'sy', 'dx', 'dy', 'warp'):
            value = mesh.environment.get(name, _constant(0))
            if _has(value, 'unknown'):
                self.unknowns.append({'section': 'per_pixel_', 'reason': name + ' output unresolved'})
                continue
            if name == 'rot' and _spatial_inputs(value) & {'rad', 'x', 'y', 'ang'}:
                self.add('radial_twist' if 'rad' in _spatial_inputs(value) else 'spatial_rotation',
                         'per_pixel_', value, 'spatial dependence reaches native rotation output',
                         parameters={'native_output': name},
                         conditions=['native mesh sampling coordinates are consumed by the active warp shader'])
            if name in {'zoom', 'zoomexp', 'sx', 'sy'} and (_radius(value) or _number(value) not in {0, 1, None}):
                self.add('radial_feedback_transform', 'per_pixel_', value,
                         'source scaling reaches native feedback mesh output', parameters={'native_output': name},
                         conditions=['active warp uses transformed uv rather than only uv_orig', 'feedback seed is present'])
            if any(node.op in {'sin', 'cos'} and _angle(node.args[0]) for node, _ in _walk(value)):
                self.add('angular_periodic_warp', 'per_pixel_', value,
                         'periodic angular field reaches native warp output', parameters={'native_output': name},
                         conditions=['native mesh sampling coordinates survive the custom shader'])

    def primitives(self):
        self.component_controls={}
        self.component_init={}
        from native_values import live_wave_mode
        from source_waveform import builtin_wave_possible
        alpha = self.main['wave_a']; raw_mode = _number(self.main['wave_mode'])
        mode=None if raw_mode is None else live_wave_mode(raw_mode)
        if builtin_wave_possible(self.main):
            dots = _number(self.main['wave_usedots'])
            mechanism = 'point_cloud_primitive' if dots is not None and dots!=0 else ('circular_wave_primitive' if mode == 0 else 'builtin_wave_primitive')
            self.add(mechanism, 'per_frame_', alpha, 'source builtin waveform mode/opacity gate',
                     component='builtin_wave', parameters={'mode': mode, 'dots': bool(dots) if dots is not None else None},
                     conditions=['audio waveform and volume-dependent opacity permit drawing'])
        for index in range(4):
            for kind in ('wave', 'shape'):
                prefix = f'{kind}code_{index}_'
                if not _scalar(self.values, prefix+'enabled', 0, 'bool'):
                    continue
                if kind == 'wave':
                    defaults = {'samples': (512, 'int'), 'a': (1, 'float'), 'x': (.5, 'float'),
                                'y': (.5, 'float'), 'usedots': (0, 'bool')}
                    env = {name: _constant(_scalar(self.values, prefix + ('bUseDots' if name == 'usedots' else name), default, dtype))
                           for name, (default, dtype) in defaults.items()}
                    init = self.equation(f'wave_{index}_init', env)
                    frame = self.equation(f'wave_{index}_per_frame', init.environment)
                    point = self.equation(f'wave_{index}_per_point', frame.environment)
                    env = point.environment
                    samples = _number(frame.environment['samples'])
                    if _number(env.get('a', _constant(1))) == 0 or samples is not None and samples <= 1:
                        continue
                    xy = Field('construct', (env['x'], env['y']), 'float2')
                    conditions = ['effective sample count is at least two', 'per-point opacity/projection permit drawing',
                                  'no later composite cancels the drawn contribution']
                    dots = _number(env['usedots'])
                    component = f'wave_{index}'
                    if dots is None or dots:
                        point_conditions = conditions + (['custom point mode is selected'] if dots is None else [])
                        self.add('point_cloud_primitive', f'wave_{index}_per_point', xy,
                                 'enabled custom waveform uses point primitive', component=component,
                                 parameters={'authored_samples': _number(frame.environment['samples']),
                                             'independent_particle_state_proven': False}, conditions=point_conditions)
                        if _deps(xy) & {'sample', 'time', 'value1', 'value2'}:
                            self.add('procedural_point_motion', f'wave_{index}_per_point', xy,
                                     'sample/time/audio-dependent custom point positions', component=component,
                                     parameters={'independent_particle_state_proven': False}, conditions=point_conditions)
                    if dots is None or not dots:
                        self.add('custom_wave_primitive', f'wave_{index}_per_point', xy,
                                 'enabled custom line waveform', component=component,
                                 conditions=conditions + (['custom line mode is selected'] if dots is None else []))
                        phase = _radial_curve(env['x'], env['y'])
                        if phase is not None and 'sample' in _deps(phase):
                            from source_parametric_wave import parametric_wave_from_analysis
                            try:curve_recipe=parametric_wave_from_analysis(self,component)
                            except (ValueError,RecursionError,OverflowError):curve_recipe=None
                            self.add('parametric_radial_curve', f'wave_{index}_per_point', xy,
                                     'paired sine/cosine positions with shared radius and sample-dependent phase', component=component,
                                     parameters={'exact_circle_proven': False,
                                                 **({'source_curve_recipe':curve_recipe} if curve_recipe is not None else {})}, conditions=conditions)
                else:
                    env = {name: _constant(_scalar(self.values, prefix+name, default, dtype))
                           for name, (default, dtype) in SHAPE.items()}
                    init_prefix=f'shape_{index}_init'
                    init_inputs={**env,**{name:Field('input',detail={'name':'init:'+init_prefix+':'+name})
                        for name in (*READONLY,*(f'q{i}' for i in range(1,33)))}}
                    init = self.equation(init_prefix, init_inputs)
                    # ShapePerFrameContext::LoadState reloads the main frameQ
                    # snapshot before shape equations; init Q writes do not
                    # persist here. Explicit per-frame local writes still win.
                    shape_resets={**{name:Field('input',detail={'name':name}) for name in READONLY},
                                  **{name:_constant(_scalar(self.values,prefix+name,default,dtype))
                                     for name,(default,dtype) in SHAPE.items()},
                                  'instance':Field('input',detail={'name':'instance'}),
                                  'thick':_constant(_scalar(self.values,prefix+'thickoutline',0,'bool')),
                                  **{f't{i}':init.environment.get(f't{i}',_constant(0)) for i in range(1,9)},
                                  **{f'q{i}':self.main.get(f'q{i}',Field('unknown'))
                                  for i in range(1,33)}}
                    frame_prefix=f'shape_{index}_per_frame'
                    frame = self.equation(frame_prefix,self.frame_environment(frame_prefix,init.environment,shape_resets))
                    env = frame.environment
                    count = _scalar(self.values,prefix+'num_inst',1,'int')
                    if all(_number(env[name]) == 0 for name in ('a', 'a2', 'border_a')) or _number(env['rad']) == 0 or count is not None and count <= 0:
                        continue
                    geometry = Field('construct', (env['x'], env['y'], env['rad']), 'float3')
                    if _has(geometry, 'unknown'):
                        self.unknowns.append({'section': f'shape_{index}_per_frame', 'reason': 'shape geometry is statically unresolved'})
                        continue
                    self.component_controls[f'shape_{index}']=env
                    self.component_init[f'shape_{index}']=init.environment
                    self.add('polygon_shape_primitive', f'shape_{index}_per_frame', geometry,
                             'enabled shape with possible fill/border and nonzero radius', component=f'shape_{index}',
                             parameters={'sides': _number(env['sides']), 'instances': count},
                             conditions=['shape opacity and projection permit drawing'])
                    if 'instance' in _deps(geometry) and count != 1:
                        self.add('procedural_shape_instances', f'shape_{index}_per_frame', geometry,
                                 'instance-dependent repeated shape geometry', component=f'shape_{index}')

    def shader(self, stage, prefix):
        selected = self.stages[stage]
        if selected['kind'] not in {'custom_'+stage, 'unknown'}:
            return
        section = self.sections.get(prefix, {})
        if section.get('status') != 'parsed' or not isinstance(section.get('tree'), list):
            self.unknowns.append({'section': prefix, 'reason': 'active shader tree is unavailable'})
            return
        from source_uniforms import blur_decode_bindings,native_time_component_fields,native_time_contract,main_q_component_fields
        blur_binding=blur_decode_bindings(getattr(self,'main',{}))
        q_fields,q_contract=main_q_component_fields(getattr(self,'main',{}))
        self.native_input_bindings={'blur_decode':blur_binding,'time_oscillators':native_time_contract(),'main_frame_q':q_contract}
        components={} if blur_binding['packed_components'] is None else {
            name:{i:value for i,value in enumerate(values)}
            for name,values in blur_binding['packed_components'].items()}
        model = ShaderFields(stage=stage, frame=1, warp_reads_blur=False,
            known_uniform_components=components,
            known_uniform_component_fields={**native_time_component_fields(),**q_fields},
            main_binding_policy='projectmtv-core-2.2.6-v1',
            global_input_policy=section.get('implicit_global_input_policy', 'strict-v1'),
            array_initializer_policy=section.get('array_initializer_policy', 'legacy-layout-v1'))
        try:
            output = model.lower(section['tree'], language_extensions=section.get('language_extensions', []))
        except (ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
            self.unknowns.append({'section': prefix, 'reason': 'shader lowering: ' + str(error)})
            return
        self.unknowns.extend({'section': prefix, 'reason': reason} for reason in model.unknown)
        if selected['kind'] == 'unknown':
            self.unknowns.append({'section': prefix, 'reason': selected['reason']})
        # An unknown wrapper is not a proof that its apparent child is live.
        if output.op == 'unknown':
            return
        output = _rgb_output(output)
        self.outputs[stage] = output
        if stage == 'warp':
            self.blur_difference(output, prefix)
        self.gradient_relief(output, prefix)
        nodes = list(_walk(output))
        colour_nodes={id(node) for node,path in _walk(output,sample_coordinates=False,constant_clipping=True)}
        self.unknowns.extend({'section': prefix, 'reason': n.detail.get('reason', 'unresolved live typed field')}
                             for n, _ in nodes if n.op in {'unknown', 'uninitialized'})
        for node, path in nodes:
            if node.op in {'sin','cos'} and id(node) in colour_nodes:
                from source_forms import spatial_oscillatory_band
                try:form=spatial_oscillatory_band(node,self)
                except (ValueError,RecursionError):form=None
                if form is not None:
                    self.add('spatial_oscillatory_bands',prefix,node,
                             'constant-affine UV/radius phase supplies a live periodic scalar generator',path=path,parameters=form)
            if node.op=='saturate' and id(node) in colour_nodes:
                from source_forms import periodic_radial_glow
                try:form=periodic_radial_glow(node,self)
                except (ValueError,RecursionError):form=None
                if form is not None:
                    self.add('periodic_radial_glow',prefix,node,
                             'periodic two-dimensional radial falloff reaches live RGB',path=path,parameters=form)
            if node.op == 'loop_result' and node.detail.get('name') is not None:
                self.recurrence(node, prefix, path)
            if node.op in {'smoothstep', 'step'} and node.args:
                band = node.args[-1]
                if band.op == 'abs' and _radius(band.args[0]) and any(
                        _number(term) not in {None, 0} for _, term in _terms(band.args[0])):
                    self.add('radial_band', prefix, node,
                             'bounded absolute radius distance supplies a live annular band', path=path)
            if node.op != 'sample':
                continue
            uv = node.args[0]; parts = _parts(uv)
            self.sample_patterns(node, uv, parts, prefix, path)
        samples = [(node, path) for node, path in nodes if node.op == 'sample' and
                   node.detail.get('surface') == 'pre_composite_feedback']
        affine = [(node, path, self.affine_scale(node.args[0])) for node, path in samples]
        affine = [(node, path, scale) for node, path, scale in affine if scale is not None and scale > 1]
        if len({_key(node.args[0]) for node, _, _ in affine}) >= 2:
            self.add('multi_copy_feedback_recursion', prefix, output,
                     'multiple distinct expanded affine previous-image copies reach output',
                     parameters={'copies': len({_key(node.args[0]) for node, _, _ in affine}),
                                 'sampling_scales': sorted(set(scale for _, _, scale in affine))},
                     conditions=['recursive feedback is retained across frames and a seed is present'])
        self.neighbourhood_blur(samples, prefix, output)
        # Unused loops may still fail to terminate; disclose control uncertainty.
        if _has(output, 'sequence') or model.effects:
            self.unknowns.append({'section': prefix, 'reason': 'loop/domain control effects require runtime termination/domain; no execution performed'})

    def neighbourhood_blur(self, samples, prefix, output):
        """Previous-image samples at uv plus offsets that cancel in pairs (uv+d and uv-d) average the
        neighbourhood: a spatial blur whose radius is the offset. The offset may be constant or vary
        with screen position, audio or time; with feedback the blur accumulates every frame."""
        groups = {}
        for node, _ in samples:
            located = _sample_offset(node)
            if located is not None:groups.setdefault(located[0], []).append((located[1], node))
        signature = _offset_signature
        for members in groups.values():
            offsets = [offset for offset, _ in members]
            present = {signature(o) for o in offsets}
            zero = signature([(0., {}), (0., {})])
            taps = [o for o in offsets if signature(o) != zero and signature(o, -1) in present]
            if len({signature(o) for o in taps}) < 4:continue
            tap_ids = {id(node) for offset, node in members if signature(offset) != zero and signature(offset, -1) in present}
            advected = self.__dict__.get('advected_samples', {}).get(prefix, set())
            if advected and advected <= tap_ids:
                # Every periodic displacement here belongs to a cancelling tap: the taps blur, they do not ripple.
                stage = {'warp_': 'warp', 'comp_': 'composite'}.get(prefix)
                self.families = [f for f in self.families if not (f['mechanism'] == 'uv_advection' and f['stage'] == stage)]
            terms = [term for o in taps for _, rest in o for _, term in rest.values()]
            names = set().union(*(_deps(term) for term in terms)) if terms else set()
            magnitudes = sorted({round(abs(v), 9) for o in taps for c, rest in o
                                 for v in [c] + [coefficient for coefficient, _ in rest.values()] if v})
            self.add('neighbourhood_blur', prefix, output,
                     'previous-image samples at offsets that cancel in pairs average each neighbourhood',
                     parameters={'taps': len({signature(o) for o in taps}),
                                 'radius_spatial': any(_spatial(term) for term in terms),
                                 'radius_audio': bool(names & AUDIO_INPUTS), 'radius_time': bool(names & {'time', 'frame', '_c2'}),
                                 'offsets': magnitudes},
                     conditions=['feedback retains the blurred image across frames'])
            break

    def gradient_relief(self, output, prefix):
        """Central differences of the image: one weighted set of samples at uv+d minus the same set at
        uv-d. The output then follows local slopes, so flat areas read as one level whatever their
        brightness and edges or texture stand out (emboss, relief or normal-map shading)."""
        directions = set()
        for node, _ in _walk(output, sample_coordinates=False):
            if node.op not in {'add', 'subtract'}:continue
            weights = _weighted_samples(node)
            if not weights:continue
            # A pure central difference: every off-centre sample is cancelled by the opposite sample.
            pairs = [(key, weight) for key, weight in weights.items() if key[1] != _negated(key[1])]
            if not pairs or any(weights.get((base, _negated(signature), sampler)) != -weight
                                for (base, signature, sampler), weight in pairs):continue
            directions |= {signature for (_, signature, _), _ in pairs}
        unique = set()
        for signature in directions:
            if _negated(signature) not in unique:unique.add(signature)
        if unique:
            self.add('gradient_relief', prefix, output, 'paired opposite-offset image samples are subtracted (central difference)',
                     parameters={'directions': len(unique)})

    def blur_difference(self, output, prefix):
        """Band-pass feedback: a warp lane adding a finer level of the fed-back image (main = 0,
        blur1-3) and subtracting a coarser one. It sharpens features between the two scales every
        frame, so seeds grow into patterns (reaction-diffusion-like splatter, cells or edges)."""
        lanes = []; fine = set(); coarse = set(); gains = []
        for index, lane in enumerate(_parts(output)[:3]):
            try:
                weights = {}
                for coefficient, level in _surface_terms(lane):
                    weights[level] = weights.get(level, 0.) + coefficient
            except (_SemanticBudget, RecursionError):
                continue
            positive = {level for level, weight in weights.items() if weight > 0}
            negative = {level for level, weight in weights.items() if weight < 0}
            if any(f < k for f in positive for k in negative):
                lanes.append(index); fine |= positive; coarse |= negative; gains.append(sum(weights.values()))
        if lanes:
            self.add('blur_difference_feedback', prefix, output,
                     'a finer fed-back image level is added and a coarser blur subtracted in the warp',
                     parameters={'lanes': lanes, 'fine_levels': sorted(fine), 'coarse_levels': sorted(coarse),
                                 'flat_gain_by_lane': gains},
                     conditions=['the warp stays selected and feedback retains content between frames'])

    def affine_scale(self, uv):
        parts = _parts(uv)
        if len(parts) != 2:
            return None
        scales = []
        for lane in parts:
            spatial_terms = [(coefficient, term) for coefficient, term in _terms(lane) if _spatial(term)]
            if len(spatial_terms) != 1 or _affine_degree(spatial_terms[0][1]) != 1:
                return None
            scales.append(abs(spatial_terms[0][0]))
        return scales[0] if scales[0] == scales[1] else None

    def sample_patterns(self, sample, uv, parts, prefix, path):
        for a, b in [(parts[0], parts[1]), (parts[1], parts[0])] if len(parts) == 2 else []:
            depth = _radial_depth(b)
            if _angle(a) and depth:
                self.add('polar_radial_sampling', prefix, sample,
                         'paired angular and reciprocal/log radius coordinates reach one live image sample', path=path,
                         parameters={'radial_mapping': depth, 'tunnel_appearance_guaranteed': False},
                         conditions=['radius avoids singularities and sampling retains usable depth content'])
        phase = _radial_curve(*parts) if len(parts) == 2 else None
        if phase is not None:
            if _angle(phase) and _angular_fold(phase):
                self.add('angular_mirror_fold', prefix, sample,
                         'periodically wrapped reflected angle reconstructed with paired sine/cosine', path=path,
                         parameters={'sector_count': _sector_count(phase)})
            elif _radius(phase):
                self.add('radial_twist', prefix, sample,
                         'shared spatial/radius-dependent sine/cosine rotation reaches sample coordinates', path=path)
        # One walk of the coordinate graph serves every check below (each walk spends the traversal budget).
        coordinate_nodes = [n for n, _ in _walk(uv)]
        if any(n.op == 'abs' and _spatial(n.args[0]) and not _angle(n.args[0]) and
               not _radius(n.args[0]) and not _has(n.args[0], 'sample') and not _has(n.args[0], 'loop_result')
               for n in coordinate_nodes):
            self.add('cartesian_mirror_fold', prefix, sample,
                     'absolute reflection of spatial image sampling domain', path=path)
        # Periodic wrap of spatial sample coordinates tiles the image; a second wrap of the reflected
        # coordinate (frac(1-uv)) or a parity floor(frac(uv/2)*2) selects mirrored tiles.
        wraps = [n for n in coordinate_nodes if n.op in ('frac', 'floor') and n.args]
        below = _ops_below(wraps, ('sample', 'frac')) if wraps else {}
        fracs = [n for n in wraps if n.op == 'frac' and _spatial(n.args[0]) and 'sample' not in below[id(n.args[0])]]
        if fracs:
            mirrored = len({_key(n.args[0]) for n in fracs}) >= 2 or any(
                n.op == 'floor' and 'frac' in below[id(n.args[0])] for n in wraps)
            self.add('repeat_tiling', prefix, sample, 'periodic wrap (frac) of spatial sample coordinates tiles the image',
                     path=path, parameters={'mirrored': bool(mirrored)})
        coordinate_samples = [n for n in coordinate_nodes if n.op == 'sample']
        if coordinate_samples:
            noise = all(n.detail.get('canonical_texture', '').startswith('noise') for n in coordinate_samples)
            self.add('noise_driven_advection' if noise else 'image_driven_advection', prefix, sample,
                     'sampled image channels causally drive a later contributing sample coordinate', path=path,
                     parameters={'coordinate_samplers': sorted(set(n.detail['sampler'] for n in coordinate_samples))})
            if self.central_gradient(uv):
                self.add('gradient_driven_advection', prefix, sample,
                         'paired central differences on orthogonal offsets drive later image coordinates', path=path)
        elif _periodic_advection(parts):
            self.__dict__.setdefault('advected_samples', {}).setdefault(prefix, set()).add(id(sample))
            self.add('uv_advection', prefix, sample,
                     'spatial periodic vector displacement reaches image coordinates', path=path)
        phases = self.rotation(uv)
        if phases:
            for phase in phases:
                mechanism = 'radial_twist' if _radius(phase) else ('spatial_rotation' if _spatial(phase) else 'global_rotation')
                self.add(mechanism, prefix, sample,
                         'matched two-lane sine/cosine rotation matrix reaches live sample coordinates', path=path)
        if sample.detail.get('surface') == 'pre_composite_feedback':
            if _complex_coordinate_map(parts):
                self.add('nonlinear_feedback_map', prefix, sample,
                         'paired complex quadratic spatial map samples the previous image', path=path,
                         parameters={'construction': 'complex_quadratic_map'},
                         conditions=['nonzero feedback retention and an initial/injected seed'])
            if any(_spatial(fold) for fold in _box_reflections(uv)):
                self.add('nonlinear_feedback_map', prefix, sample,
                         'box-reflected spatial domain samples the previous image', path=path,
                         parameters={'construction': 'box_reflection_map'},
                         conditions=['nonzero feedback retention and an initial/injected seed'])
            scale = self.affine_scale(uv)
            if scale is not None and scale != 1:
                self.add('radial_feedback_transform', prefix, sample,
                         'spatial scale reaches previous-image sampling coordinates', path=path,
                         parameters={'sampling_scale': scale}, conditions=['feedback seed is present'])

    def recurrence(self, node, prefix, path):
        if _initial_condition(node) == 0:
            return
        plan = node.detail['plan']
        # Merge component demand over the same causal fixed point used for
        # tracing. A cross-lane recurrence can require both lanes even when the
        # final return projects one; an independent unused lane cannot.
        reads = [(node.detail['name'], node.detail.get('read_components'))]
        reads.extend((n.detail['name'], n.detail.get('read_components')) for n, _ in _walk(node)
                     if n.op == 'loop_slot' and n.detail.get('plan') is plan)
        demands = {}
        for name, components in reads:
            if name in demands and demands[name] is None:
                continue
            if components is None:
                demands[name] = None
            else:
                demands.setdefault(name, set()).update(components)
        for name in sorted(demands):
            if name not in plan.updates:
                continue
            initial = node.args[plan.names.index(name)]
            detail = {**node.detail, 'name': name}
            if demands[name] is None:
                detail.pop('read_components', None)
            else:
                detail['read_components'] = tuple(sorted(demands[name]))
            state = Field('loop_result', node.args, initial.dtype, detail)
            self.recurrence_state(state, prefix, path)

    def recurrence_state(self, node, prefix, path):
        plan = node.detail['plan']; name = node.detail['name']
        update = plan.updates.get(name)
        if update is None:
            return
        indices = node.detail.get('read_components')
        if indices is not None:
            update = _project(update, indices)
        found = _quadratic(update)
        if found:
            x, y = _strip(found['x']), _strip(found['y'])
            def state_component(value):
                return value.op == 'member' and value.args[0].op == 'loop_slot' and value.args[0].detail.get('plan') is plan and value.args[0].detail.get('name') == name
            if state_component(x) and state_component(y):
                initial = node.args[plan.names.index(name)]
                start_spatial = _spatial(initial); parameter_spatial = found['parameter_spatial']
                changing_parameter = any(k.op == 'loop_slot' and k.detail.get('plan') is plan
                                         for p in found['parameter'] for k, _ in _walk(p))
                subtype = ('unclassified' if changing_parameter else
                           'julia_style' if start_spatial and not parameter_spatial else
                           'mandelbrot_style' if not start_spatial and parameter_spatial and _number(initial) is not None else 'unclassified')
                bailout = plan.condition is not None and any(
                    n.op == 'dot' and any(k.op == 'loop_slot' and k.detail.get('name') == name for k, _ in _walk(n))
                    for n, _ in _walk(plan.condition))
                self.add('complex_quadratic_recurrence', prefix, node,
                         'both lanes of loop-carried z square plus parameter reach output/control', path=path,
                         parameters={'subtype': subtype, 'norm_bailout': bailout,
                                     'iteration_budget_is_termination_proof': False},
                         conditions=['loop executes and terminates within its authored domain'])
        clamps = [n for n, _ in _walk(update) if n.op == 'clamp' and len(n.args) == 3 and
                  _number(n.args[1]) == -1 and _number(n.args[2]) == 1 and
                  any(k.op == 'loop_slot' and k.detail.get('plan') is plan and k.detail.get('name') == name
                      for k, _ in _walk(n.args[0]))]
        if not clamps:
            return
        folded = []
        for candidate, _ in _walk(update):
            if candidate.op != 'subtract':
                continue
            a, b = candidate.args
            for clamp in clamps:
                coefficient, factors = _product(a)
                if coefficient == 2 and len(factors) == 1 and _same(factors[0], clamp) and _same(b, clamp.args[0]):
                    folded.append(candidate)
        if not folded:
            return
        sphere = any(n.op in {'divide', 'multiply'} and any(
            k.op == 'dot' and any(_same(k.args[0], fold) and _same(k.args[1], fold) for fold in folded)
            for k, _ in _walk(n)) for n, _ in _walk(update))
        # Some authors spell the piecewise sphere factor as clamp(max(k/r2,k),
        # 0,1), rather than an if/else. Both act on the same box-folded orbit.
        sphere_control = _has(update, 'select') or any(
            n.op == 'clamp' and _has(n, 'divide') and _has(n, 'dot')
            for n, _ in _walk(update))
        affine_update = False
        if update.op in {'add', 'subtract'}:
            for side in update.args:
                if side.op == 'multiply':
                    for index in (0, 1):
                        scale = _number(side.args[index])
                        transformed = side.args[1-index]
                        if scale is not None and abs(scale) > 1 and any(
                                _same(n, fold) for n, _ in _walk(transformed) for fold in folded):
                            affine_update = True
        mechanism = 'mandelbox_recurrence' if sphere and sphere_control and affine_update else 'iterated_spatial_fold'
        self.add(mechanism, prefix, node,
                 'loop-carried box reflection' + (' with radius-dependent sphere scaling and affine update' if sphere else ''),
                 path=path, parameters={'sphere_fold_proven': bool(sphere), 'dimension': len(_parts(update))},
                 conditions=['loop executes and terminates; final shading exposes its orbit'])

    def rotation(self, uv):
        """Match x*cos-y*sin, x*sin+y*cos, allowing outer offsets/scales."""
        phases = []
        for node, _ in _walk(uv):
            if node.dtype != 'float2':
                continue
            x, y = _parts(node)
            xt = []
            yt = []
            for sign, term in _terms(x):
                scale, factors = _product(term)
                xt.append((sign*scale, factors))
            for sign, term in _terms(y):
                scale, factors = _product(term)
                yt.append((sign*scale, factors))
            for a, af in xt:
                for b, bf in xt:
                    if a != 1 or b != -1 or len(af) != 2 or len(bf) != 2:
                        continue
                    cos = next((f for f in af if f.op == 'cos'), None)
                    sin = next((f for f in bf if f.op == 'sin'), None)
                    if cos is None or sin is None or not _same(cos.args[0], sin.args[0]):
                        continue
                    px = next(f for f in af if f is not cos)
                    py = next(f for f in bf if f is not sin)
                    want = [{_key(px), _key(sin)}, {_key(py), _key(cos)}]
                    if all(any(sign == 1 and set(_key(f) for f in factors) == expected
                               for sign, factors in yt) for expected in want):
                        phases.append(cos.args[0])
        return phases

    def central_gradient(self, uv):
        differences = []
        for node, _ in _walk(uv):
            if node.op != 'subtract':
                continue
            samples = []
            for side in node.args:
                scalar = _strip(side)
                if scalar.op != 'member' or scalar.detail.get('field') not in {'x','y','z','w','r','g','b','a'}:
                    break
                channel = scalar.detail['field']
                source = _strip(scalar.args[0])
                while source.op == 'member':
                    fields = source.detail.get('field', '')
                    index = 'xyzw'.find(channel)
                    if index < 0:
                        index = 'rgba'.find(channel)
                    if index < 0 or index >= len(fields):
                        break
                    channel = fields[index]
                    source = _strip(source.args[0])
                if source.op != 'sample':
                    break
                samples.append((source, channel))
            if len(samples) != 2 or samples[0][1] != samples[1][1]:
                continue
            a, b = (item[0] for item in samples)
            if a.detail['sampler'] != b.detail['sampler']:
                continue
            pa, pb = a.args[0], b.args[0]
            if pa.op != 'add' or pb.op != 'subtract' or not _same(pa.args[0], pb.args[0]) or not _same(pa.args[1], pb.args[1]):
                continue
            offset = _parts(pa.args[1])
            if len(offset) != 2:
                continue
            numbers = list(map(_number, offset))
            if numbers[0] == 0 and numbers[1] not in {0, None}:
                differences.append((_key(pa.args[0]), a.detail['sampler'], samples[0][1], 1, abs(numbers[1])))
            if numbers[1] == 0 and numbers[0] not in {0, None}:
                differences.append((_key(pa.args[0]), a.detail['sampler'], samples[0][1], 0, abs(numbers[0])))
        return any(a[:3] == b[:3] and a[3] != b[3] and a[4] == b[4]
                   for a in differences for b in differences)

    def contribution_gates(self):
        """Drop source-proven disconnected stages across the native pipeline."""
        comp = self.outputs.get('composite')
        if comp is not None and not any(n.op == 'sample' and n.detail.get('canonical_texture') in
                                       {'main', 'blur1', 'blur2', 'blur3'} for n, _ in _walk(comp)):
            self.families = [row for row in self.families if row['stage'] == 'composite']
        warp = self.outputs.get('warp')
        if warp is not None and not uses_input_components(warp, '_uv', {0, 1}):
            self.families = [row for row in self.families if row['stage'] != 'mesh_warp']


def analyze_families(source, *, profile='gles300', compatibility=None,input_scenario=None,behaviour_context=None):
    """Return JSON mechanism evidence from a parsed source; never render or run it.

    Missing compatibility preserves conditional source mechanisms. Bound rejected
    shader evidence selects the native fallback and suppresses custom mechanisms.
    Unknown parser/lowering constructs remain explicit unknowns, never negatives.
    ``numbered_source`` may provide original key/physical-line evidence; source
    section hashes and graph paths remain available without that optional text.
    """
    if not isinstance(source, dict) or not isinstance(source.get('sections'), dict) or not isinstance(source.get('values'), dict):
        raise ValueError('native parsed source dictionary with values and sections required')
    if profile not in {'gles300', 'glsl330'}:
        raise ValueError('supported target profile required')
    if compatibility is not None and not isinstance(compatibility, dict):
        raise ValueError('compatibility dictionary required')
    if input_scenario is not None:
        from source_input_scenario import validate_scenario
        input_scenario=validate_scenario(input_scenario)
    from source_static_behaviour import validate_context
    behaviour_context=validate_context(behaviour_context)
    work_cache = {}
    token = _CACHE.set(work_cache)
    try:
        analysis = _Analysis(source, profile, compatibility)
        analysis.input_scenario=input_scenario
        analysis.behaviour_context=behaviour_context
        budget_exhausted = False
        phases = [('equations', analysis.main_equations), ('drawing', analysis.primitives),
                  ('warp_', lambda: analysis.shader('warp', 'warp_')),
                  ('comp_', lambda: analysis.shader('composite', 'comp_')),
                  ('pipeline', analysis.contribution_gates)]
        for phase, function in phases:
            start = len(analysis.families)
            if phase == 'drawing' and not hasattr(analysis, 'main'):
                continue
            try:
                function()
            except (_SemanticBudget, RecursionError, IndexError) as error:
                budget_exhausted |= isinstance(error, _SemanticBudget)
                analysis.families = analysis.families[:start] if phase != 'pipeline' else []
                analysis.outputs.pop({'warp_': 'warp', 'comp_': 'composite'}.get(phase), None)
                analysis.unknowns.append({'section': phase, 'reason': 'static analysis unresolved: ' + str(error)})
        from source_appearance import appearance_from_analysis
        try:visual_description=appearance_from_analysis(analysis)
        except (_SemanticBudget,RecursionError,ValueError,IndexError) as error:
            budget_exhausted |= isinstance(error,_SemanticBudget)
            visual_description={'schema_version':1,'status':'unknown','unknown_reasons':[str(error)]}
        work = {'field_visits': work_cache.get('field_visits', 0),
                'normalized_term_nodes': work_cache.get('normalized_term_nodes', 0),
                'max_field_visits': MAX_FIELD_VISITS, 'max_normalized_terms': MAX_NORMALIZED_TERMS,
                'budget_exhausted': budget_exhausted or work_cache.get('traversal_budget_exhausted',False)}
    finally:
        _CACHE.reset(token)
    record = {'schema_version': SCHEMA_VERSION, 'analysis_policy': POLICY,
        'basis': 'source-only-symbolic-program-mechanisms',
        'preset_sha256': source.get('preset_sha256'),
        'parsed_source_sha256': _digest({key: source[key] for key in ('values', 'sections', 'parser_inputs') if key in source}),
        'profile': profile, 'compatibility_sha256': _digest(compatibility) if compatibility is not None else None,
        'uses_shader_execution': False, 'uses_equation_execution': False,
        'uses_rendered_images': False, 'stages': analysis.stages,
        'families': sorted(analysis.families, key=lambda row: (row['stage'], row['component'] or '', row['mechanism'], _digest(row['parameters']))),
        'unknowns': analysis.unknowns,
        'visual_description':visual_description,
        'analysis_work': work,
        'appearance_prediction_complete': False, 'mood_labels': [], 'genre_labels': [],
        'limitations': ['Recognized program mechanisms do not guarantee visible or dominant families',
                       'Unrecognized live forms are not proof of family absence',
                       'No waveform, shader-field raster, feedback sequence or audio signal is executed',
                       'Source locations identify sections, not token-exact motif spans']}
    record['behaviour_context']=behaviour_context
    if input_scenario is not None:record['input_scenario']=input_scenario
    record['record_sha256'] = _digest(record)
    return record
