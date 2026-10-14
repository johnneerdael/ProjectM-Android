"""Straight-line evaluation of exported stage programs for the illustration numeric policy.

grid_math.evaluate_grid is the strict reference: it checks every node's type and finiteness, runs only
the selected lanes of each branch and proves which subgraphs are uniform. Under GLES_IEEE_ILLUSTRATION
those checks never reject a value, so the same arithmetic can run as one ordered list of numpy steps:
both branches of a select are computed and combined per lane, uniform values keep a length-1 lane axis
(numpy broadcasting does the hoisting), and the plan is built once per exported program.

Programs with loops, arrays, matrices, uninitialised components or unknown operations are not compiled;
callers fall back to evaluate_grid for them. Any UnresolvedMath during a run also means "use the reference".
"""
import numpy as np

from field_math import (BINARY, UNARY, SWIZZLE, SEPARATE_ARITHMETIC, UnresolvedMath, mix_values,
                        numeric_layout, typed)

_UNSUPPORTED = {'unknown', 'uninitialized', 'loop_slot', 'loop_result', 'loop_eel_result', 'loop_eel_slot', 'array',
                'array_index', 'array_write', 'index', 'index_guard', 'matrix_constructor', 'matrix_cast',
                'matrix_product', 'write_member', 'flat_component', 'sequence', 'mul', 'reflect', 'all', 'any'}
_DTYPES = {'float': np.float32, 'int': np.int32, 'bool': np.bool_}
_PLANS = {}


def _convert(value, dtype, *, zero_extend=False):
    """grid_math._convert without the lane-count check (lane axis is 1 for uniform values)."""
    base, shape = numeric_layout(dtype)
    array = np.asarray(value)
    # Already the stored type and layout: nothing to convert.
    if array.dtype == _DTYPES[base] and array.ndim == 1 + len(shape) and array.shape[1:] == shape and base != 'int':return array
    if array.ndim == 0:array = array.reshape(1)
    lanes = array.shape[0]
    size = int(np.prod(shape)) if shape else 1
    flat = array.reshape(lanes, -1)
    if ('[' in dtype or len(shape) == 2) and flat.shape[1] != size:raise UnresolvedMath('matrix/array size mismatch: ' + dtype)
    if flat.shape[1] == 1:flat = np.broadcast_to(flat, (lanes, size))
    elif flat.shape[1] >= size:flat = flat[:, :size]
    elif zero_extend:flat = np.pad(flat, ((0, 0), (0, size - flat.shape[1])))
    else:raise UnresolvedMath('insufficient grid components for ' + dtype)
    if base == 'int' and np.any((flat < np.iinfo(np.int32).min) | (flat > np.iinfo(np.int32).max)):
        raise UnresolvedMath('integer grid conversion outside signed 32-bit range')
    return flat.astype(_DTYPES[base]).reshape((lanes,) + shape)


def _align(args):
    rank = max(a.ndim for a in args)
    return [a.reshape(a.shape + (1,) * (rank - a.ndim)) if a.ndim == 1 else a for a in args]


def compile_program(program):
    """Ordered evaluation plan for an exported {'root','nodes'[,'plans']} graph, or None (use the reference)."""
    key = id(program)
    cached = _PLANS.get(key)
    if cached is not None and cached[0] is program:return cached[1]
    nodes = program.get('nodes') or []
    plan = None
    if not program.get('plans') and nodes and not any(n.get('op') in _UNSUPPORTED for n in nodes):
        order = [];state = {}
        stack = [(program['root'], False)]
        while stack:
            index, expanded = stack.pop()
            if expanded:order.append(index);state[index] = 2;continue
            if state.get(index):continue
            state[index] = 1;stack.append((index, True))
            for arg in reversed(nodes[index]['args']):
                if not state.get(arg):stack.append((arg, False))
        # Constants are typed once per program, not once per evaluation.
        constants = {}
        for index in order:
            node = nodes[index]
            if node['op'] == 'constant':
                try:constants[index] = typed(node['detail']['value'], node.get('dtype', 'float'))[None]
                except UnresolvedMath:constants = None;break
        plan = None if constants is None else {'order': order, 'nodes': nodes, 'root': program['root'], 'constants': constants}
    if len(_PLANS) > 4096:_PLANS.clear()
    _PLANS[key] = (program, plan)
    return plan


def _maskable(nodes, index, inputs, memo):
    """field_math.maskable_math on exported nodes."""
    if index in memo:return memo[index]
    memo[index] = True
    node = nodes[index];op = node['op']
    result = True
    if op in {'unknown', 'uninitialized', 'sample', 'sequence', 'index', 'index_guard', 'write_member'} or op.startswith(('loop_', 'array')):
        result = False
    elif op == 'input':
        detail = node.get('detail') or {};name = detail.get('name')
        if name not in inputs and 'unbound_default' not in detail:result = False
        else:
            value = inputs.get(name, detail.get('unbound_default'))
            try:
                if not np.all(np.isfinite(value)):result = False
                else:
                    base, _ = numeric_layout(node.get('dtype', 'float'))
                    if base == 'float':
                        with np.errstate(over='ignore', invalid='ignore'):
                            if not np.all(np.isfinite(np.asarray(value, dtype=np.float32))):result = False
                    elif base == 'int' and np.any((np.asarray(value) < np.iinfo(np.int32).min) | (np.asarray(value) > np.iinfo(np.int32).max)):
                        result = False
            except (ValueError, TypeError, OverflowError):result = False
    if result:result = all(_maskable(nodes, a, inputs, memo) for a in node['args'])
    memo[index] = result
    return result


def run(plan, *, batch_shape, inputs, sample, rng):
    """Evaluate a compiled plan over the grid; returns batch_shape + component shape (float32 or int/bool)."""
    nodes = plan['nodes'];size = int(np.prod(batch_shape));values = {};masks = {}
    with np.errstate(all='ignore'):
        for index in plan['order']:
            node = nodes[index];op = node['op'];dtype = node.get('dtype', 'float');detail = node.get('detail') or {}
            if op == 'narrow':op = 'cast'
            if op == 'member' and isinstance(detail.get('field'), str) and detail['field'] and set(detail['field']) <= set('xyzwrgba'):
                detail = {**detail, 'swizzle': True}
            args = [values[a] for a in node['args']]
            zero_extend = False
            if op == 'constant':
                values[index] = plan['constants'][index];continue
            elif op == 'input':
                name = detail['name']
                if name in inputs:data = np.asarray(inputs[name])
                elif 'unbound_default' in detail:data = np.asarray(detail['unbound_default'])
                else:raise UnresolvedMath('missing symbolic grid input: ' + name)
                _, shape = numeric_layout(dtype)
                if not np.all(np.isfinite(data)):raise UnresolvedMath('nonfinite symbolic grid input: ' + name)
                if data.shape == tuple(batch_shape) + shape:raw = data.reshape((size,) + shape)
                elif data.shape == shape or data.shape == ():raw = typed(data, dtype)[None]
                else:raise UnresolvedMath('invalid grid/uniform input shape: ' + name)
            elif op == 'select':
                predicate = args[0]
                if predicate.ndim != 1:raise UnresolvedMath('vector grid condition not implemented')
                chosen = predicate.astype(bool)
                a, b = _convert(args[1], dtype), _convert(args[2], dtype)
                if chosen.shape[0] == 1:raw = a if chosen[0] else b
                else:raw = np.where(chosen.reshape((-1,) + (1,) * (max(a.ndim, b.ndim) - 1)), a, b)
            elif op in ('and', 'or'):
                left, right = args[0].astype(bool), args[1].astype(bool)
                if left.ndim != 1 or right.ndim != 1:raise UnresolvedMath('vector logical grid condition not implemented')
                raw = (left & right) if op == 'and' else (left | right)
            elif op == 'sample':
                coordinates = args[0]
                if len(node['args']) != 1:raise UnresolvedMath('texture grid overload not implemented')
                if coordinates.shape[0] != size:coordinates = np.broadcast_to(coordinates, (size,) + coordinates.shape[1:])
                coordinates = np.array(coordinates, copy=True)
                if not np.all(np.isfinite(coordinates)):
                    wrap = (detail.get('sampling_policy') or {}).get('wrap')
                    coordinates = np.where(np.isnan(coordinates), 0. if wrap else 1., coordinates)
                    coordinates = np.where(np.isinf(coordinates), 0. if wrap else np.clip(coordinates, 0., 1.), coordinates)
                raw = np.asarray(sample(detail, coordinates))
                _, shape = numeric_layout(dtype)
                if raw.shape == shape:raw = np.broadcast_to(raw, (size,) + shape)
            elif op == 'multiply' and detail.get('zero_guard') and all(_maskable(nodes, a, inputs, masks) for a in node['args']):
                left, right = _align(args)
                raw = np.where((left == 0) | (right == 0), 0, np.multiply(left, right))
            elif op == 'domain_checked':raw = args[0]
            elif op == 'source_domain_guard':
                lo, hi = detail['bounds']
                if np.any(~np.isfinite(args[0])) or np.any((args[0] < lo) | (args[0] > hi)):
                    raise UnresolvedMath('source domain violated by shader input')
                raw = np.ones(args[0].shape[0], dtype=bool)
            elif op == 'cast':raw = args[0];zero_extend = True
            elif op in ('construct', 'aggregate', 'components'):
                lanes = max(a.shape[0] for a in args)
                raw = np.concatenate([np.broadcast_to(a.reshape(a.shape[0], -1), (lanes, a.reshape(a.shape[0], -1).shape[1])) for a in args], axis=1)
            elif op == 'member':
                if not detail.get('swizzle'):raise UnresolvedMath('struct/matrix grid member not implemented')
                flat = args[0].reshape(args[0].shape[0], -1)
                raw = flat[:, [SWIZZLE[c] if flat.shape[1] > 1 else 0 for c in detail['field']]]
            elif op == 'unary':
                operator = detail['operator']
                if operator == 0:raw = -args[0]
                elif operator == 1:raw = +args[0]
                elif operator == 2:raw = np.logical_not(args[0])
                else:raise UnresolvedMath('stateful grid unary operator not implemented')
            elif op == 'remainder' and dtype.startswith('float'):raw = np.mod(*_align(args))
            elif op in BINARY:
                operands = _align(args)
                if dtype.startswith('int') and op in {'add', 'subtract', 'multiply'}:operands = [a.astype(np.int64) for a in operands]
                raw = BINARY[op](*operands)
            elif op in UNARY:raw = UNARY[op](args[0])
            elif op == 'dot':raw = np.sum(args[0] * args[1], axis=1)
            elif op == 'log10':raw = np.log(args[0]) / np.log(np.float32(10))
            elif op in ('length', 'distance', 'normalize'):
                value = args[0] - args[1] if op == 'distance' else args[0]
                norm = np.abs(value) if value.ndim == 1 else np.linalg.norm(value, axis=tuple(range(1, value.ndim)))
                raw = value / norm.reshape((norm.shape[0],) + (1,) * (value.ndim - 1)) if op == 'normalize' else norm
            elif op == 'cross':raw = np.cross(*np.broadcast_arrays(*args))
            elif op == 'pow':
                base, exponent = _align(args)
                with np.errstate(over='ignore'):
                    raw = np.exp2(exponent * np.log2(np.maximum(np.abs(base), np.float32(2. ** -127)))).astype(np.float32)
            elif op == 'rsqrt':raw = 1 / np.sqrt(args[0])
            elif op == 'atan2':raw = np.arctan2(*_align(args))
            elif op == 'min':raw = np.minimum(*_align(args))
            elif op == 'max':raw = np.maximum(*_align(args))
            elif op == 'clamp':raw = np.clip(*_align(args))
            elif op == 'saturate':raw = np.clip(args[0], 0, 1)
            elif op == 'lerp':
                a, b, t = _align(args);raw = mix_values(a, b, t, arithmetic_profile=SEPARATE_ARITHMETIC)
            elif op == 'frac':raw = args[0] - np.floor(args[0])
            elif op == 'step':
                a, b = _align(args);raw = np.asarray(b >= a, dtype=np.float32)
            elif op == 'smoothstep':
                a, b, x = _align(args);t = np.clip((x - a) / (b - a), 0, 1);raw = t * t * (3 - 2 * t)
            elif op == 'fmod':raw = np.mod(*_align(args))
            elif op == 'eel_divide':
                a, b = _align(args);small = np.abs(b) < 1e-5
                raw = np.where(small, 0, a / np.where(small, 1, b)).astype(np.result_type(a, b, np.float32))
            elif op == 'eel_equal':
                a, b = _align(args);raw = np.asarray(np.abs(a - b) < 1e-5, dtype=np.float32)
            elif op == 'rand':
                limit = np.maximum(1., np.floor(np.asarray(args[0], dtype=np.float64)))
                site = (detail.get('equation_phase'), detail.get('site_index'))
                if site[1] is not None and hasattr(rng, 'site_value'):raw = (rng.site_value(site) * limit).astype(np.float32)
                elif limit.size and np.all(limit == limit.flat[0]):raw = np.full(limit.shape, rng.random() * limit.flat[0], dtype=np.float32)
                else:raw = (rng.random(limit.shape) * limit).astype(np.float32)
            elif op == 'bnot':raw = np.asarray(np.abs(args[0]) < 1e-5, dtype=np.float32)
            elif op == 'negate':raw = -args[0]
            elif op == 'sqr':raw = args[0] * args[0]
            elif op == 'int':raw = np.floor(args[0])
            elif op in ('band', 'bor', '_and', '_or'):
                a, b = _align(args);combine = np.logical_and if op in ('band', '_and') else np.logical_or
                raw = np.asarray(combine(np.abs(a) > 1e-5, np.abs(b) > 1e-5), dtype=np.float32)
            else:raise UnresolvedMath('grid operation not compiled: ' + op)
            values[index] = _convert(raw, dtype, zero_extend=zero_extend)
    result = values[plan['root']]
    if result.shape[0] != size:result = np.broadcast_to(result, (size,) + result.shape[1:])
    return np.array(result.reshape(tuple(batch_shape) + result.shape[1:]), copy=True)
