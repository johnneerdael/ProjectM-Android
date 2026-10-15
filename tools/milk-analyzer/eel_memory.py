"""Evaluation of exported EEL graphs, including fixed-count loops and megabuf/gmegabuf memory.

Graphs are the serialised {'root','nodes','plans'} form of source_stage_program.serialise or
source_appearance._expression. Arithmetic follows projectm-eval (TreeFunctions.c): division by
|d|<1e-5 is 0, sqrt takes |x|, pow gives 0 for NaN results, EEL equal is |a-b|<1e-5.

Memory (MemoryBuffer.c): an index addresses item int32(index + 0.0001), truncated toward zero, and
is valid in [0, 128*65536); reads outside give 0 and writes outside are discarded. ``megabuf`` is
the preset's buffer shared by its per-frame, per-pixel, shape and wave code; ``gmegabuf`` is the
process-wide buffer. Both start zeroed here. A graph reads a buffer as the input
``memory:<space>`` and each write yields a new memory version, so reads see exactly the writes
that precede them in source order.

``loop(n, body)`` (execute_loop) reads n once, truncates it to an integer, caps it at 1048576 and
runs the body that many times. A loop is exported as a plan: the names it writes (variables and
``memory:<space>``), each name's start-of-iteration slot, and its end-of-iteration update.
"""
import json
import math
import time

import numpy as np

MAX_LOOP_COUNT = 1048576
MEMORY_ITEMS = 128 * 65536
_UNARY_NP = {'sin': np.sin, 'cos': np.cos, 'tan': np.tan, 'abs': np.abs, 'negate': np.negative, 'sqr': np.square,
             'floor': np.floor, 'ceil': np.ceil, 'int': np.floor, 'sign': np.sign, 'exp': np.exp, 'atan': np.arctan,
             'log': lambda v: np.where(v > 0, np.log(np.where(v > 0, v, 1.)), 0.),
             'log10': lambda v: np.where(v > 0, np.log10(np.where(v > 0, v, 1.)), 0.),
             'asin': lambda v: np.where(np.abs(v) <= 1, np.arcsin(np.clip(v, -1, 1)), 0.),
             'acos': lambda v: np.where(np.abs(v) <= 1, np.arccos(np.clip(v, -1, 1)), 0.)}
STOCHASTIC = {'rand'}
MEMORY_OPS = {'array_mem_read', 'array_mem_write'}
BITWISE_OPS = {'eel_bitwise_and', 'eel_bitwise_or'}
LOOP_OPS = {'loop_eel_result', 'loop_eel_slot'}


def memory_index(index):
    """Item addressed by a projectm-eval memory index, or None outside the buffer."""
    shifted = float(index) + .0001
    if not math.isfinite(shifted) or not -2147483648. < shifted < 2147483648.:return None
    item = int(shifted)
    return item if 0 <= item < MEMORY_ITEMS else None


def loop_count(value):
    """Iterations of loop(value, ...): integer truncation, at most MAX_LOOP_COUNT, none when <= 0."""
    value = float(value)
    if math.isnan(value) or value < 1:return 0
    return MAX_LOOP_COUNT if value >= MAX_LOOP_COUNT else int(value)


class Memory:
    """One version of a zero-initialised buffer: shared base items plus this version's own writes."""
    __slots__ = ('base', 'overlay')

    def __init__(self, base=None, overlay=None):
        self.base = {} if base is None else base
        self.overlay = {} if overlay is None else overlay

    def read(self, index):
        item = memory_index(index)
        if item is None:return 0.
        return self.overlay.get(item, self.base.get(item, 0.))

    def write(self, index, value):
        item = memory_index(index)
        if item is None:return self
        return Memory(self.base, {**self.overlay, item: float(value)})

    def items(self):
        return {**self.base, **self.overlay}

    def owned_copy(self):
        return Memory(self.items(), {})


def _apply(op, node, args, rng, batch_shape=None):
    with np.errstate(all='ignore'):
        if op == 'rand' and rng is not None and hasattr(rng, 'site_draw'):
            detail = node.get('detail') or {}
            if detail.get('equation_phase') in getattr(rng, 'site_phases', ('per_frame_',)) and detail.get('site_index') is not None:
                # A main-code rand call site runs once per block in the engine (once per frame for per-frame
                # code, once per load for init code): every place that inlines the same site sees one draw.
                return rng.site_draw((detail['equation_phase'], detail['site_index']), np.maximum(1., np.floor(args[0])))
        if op == 'rand' and rng is not None:
            # projectm-eval rand(x): continuous uniform on [0, max(1, floor(x))], one draw per call.
            limit = np.maximum(1., np.floor(args[0]))
            shape = np.broadcast_shapes(np.shape(limit), tuple(batch_shape)) if batch_shape else np.shape(limit)
            return rng.random(shape) * limit
        if op == 'add':return args[0] + args[1]
        if op == 'subtract':return args[0] - args[1]
        if op == 'multiply':return args[0] * args[1]
        if op == 'eel_divide':return np.where(np.abs(args[1]) < 1e-5, 0., args[0] / np.where(np.abs(args[1]) < 1e-5, 1., args[1]))
        if op == 'divide':return np.where(args[1] == 0, 0., args[0] / np.where(args[1] == 0, 1., args[1]))
        if op == 'remainder':
            divisor = np.trunc(args[1]);return np.where(divisor == 0, 0., np.fmod(np.trunc(args[0]), np.where(divisor == 0, 1., divisor)))
        if op == 'eel_equal':return (np.abs(args[0] - args[1]) < 1e-5).astype(np.float64)
        if op == 'atan2':return np.arctan2(args[0], args[1])
        if op == 'sigmoid':
            t = 1 + np.exp(np.minimum(700., -args[0] * args[1]));return np.where(np.abs(t) > 1e-5, 1 / t, 0.)
        if op == 'bnot':return (np.abs(args[0]) < 1e-5).astype(np.float64)
        if op in ('band', '_and'):return ((np.abs(args[0]) > 1e-5) & (np.abs(args[1]) > 1e-5)).astype(np.float64)
        if op in ('bor', '_or'):return ((np.abs(args[0]) > 1e-5) | (np.abs(args[1]) > 1e-5)).astype(np.float64)
        if op == 'min':return np.minimum(args[0], args[1])
        if op == 'max':return np.maximum(args[0], args[1])
        if op == 'pow':
            result = np.where((np.abs(args[0]) < 1e-5) & (args[1] < 0), 0., np.power(args[0], args[1]))
            return np.where(np.isnan(result), 0., result)
        if op == 'sqrt':return np.sqrt(np.abs(args[0]))
        if op == 'less':return (args[0] < args[1]).astype(np.float64)
        if op == 'greater':return (args[0] > args[1]).astype(np.float64)
        if op == 'less_equal':return (args[0] <= args[1]).astype(np.float64)
        if op == 'greater_equal':return (args[0] >= args[1]).astype(np.float64)
        if op in BITWISE_OPS:
            # projectm-eval (double build): (int64)a & (int64)b, C truncation toward zero.
            a, b = (np.where(np.isfinite(v) & (np.abs(v) < 9.2e18), np.trunc(v), 0.).astype(np.int64) for v in args[:2])
            return (a & b if op == 'eel_bitwise_and' else a | b).astype(np.float64)
        if op == 'select':
            if isinstance(args[1], Memory) or isinstance(args[2], Memory):
                if np.ndim(args[0]):raise ValueError('memory version selected per evaluated point')
                return args[1] if args[0] != 0 else args[2]
            return np.where(args[0] != 0, args[1], args[2])
        return _UNARY_NP[op](args[0])


def _read(memory, index):
    if np.ndim(index) == 0:return np.float64(memory.read(float(index)))
    return np.vectorize(memory.read, otypes=[np.float64])(index)


def _write(memory, index, value):
    if np.ndim(index) or np.ndim(value):raise ValueError('vectorised memory write is not a single source write')
    return memory.write(float(index), float(value))


def input_names(expression, *, stochastic=False):
    """Inputs of a graph this module evaluates (None when an operation is unsupported).

    Loop slots are not inputs; nodes reached only through a loop plan's updates are included.
    """
    from time_expression import SUPPORTED
    if not isinstance(expression, dict) or not isinstance(expression.get('nodes'), list):return None
    # Exported graphs are immutable and re-scanned per point and frame; the cache holds a reference to
    # each graph (so its id is not reused) and its node count (a graph edited in place misses).
    key = (id(expression), id(expression['nodes']), len(expression['nodes']), stochastic)
    cached = _NAMES_CACHE.get(key)
    if cached is not None and cached[0] is expression:return None if cached[1] is None else set(cached[1])
    allowed = SUPPORTED | MEMORY_OPS | LOOP_OPS | BITWISE_OPS | (STOCHASTIC if stochastic else set())
    names = set()
    for node in expression['nodes']:
        # A loop the exporter could not resolve carries no plan: the graph cannot be evaluated.
        if node.get('op') not in allowed or (node.get('op') in ('loop_eel_result', 'loop_eel_slot') and 'plan_ref' not in (node.get('detail') or {})):
            names = None;break
        if node.get('op') == 'input':names.add(node.get('detail', {}).get('name'))
    if len(_NAMES_CACHE) > 200000:_NAMES_CACHE.clear()
    _NAMES_CACHE[key] = (expression, None if names is None else frozenset(names))
    return names


_NAMES_CACHE = {}


class WorkBudget:
    """Deterministic evaluation budget in work units (graph nodes per frame step, loop body nodes per iteration).

    Unlike a wall-clock deadline it cuts at the same point on any machine and under any load, so static
    probes that step programs give reproducible results."""
    def __init__(self, units):
        self.left = float(units)

    def spend(self, units):
        self.left -= units
        if self.left < 0:raise ValueError('evaluation budget exceeded')


def evaluate_np(expression, inputs, rng=None, batch_shape=None, deadline=None):
    """Value of a serialised graph over declared inputs (vectorised; rand needs an rng).

    batch_shape: the shape of the evaluated batch, so every point gets its own rand draw (as every
    instance or frame does in the engine) even when the rand argument is a constant.
    deadline: a WorkBudget charged per loop iteration (deterministic), or a time.perf_counter() value after
    which loops stop; both raise ValueError('evaluation budget exceeded').
    """
    names = input_names(expression, stochastic=rng is not None)
    if names is None or names - set(inputs):raise ValueError('point program not evaluable')
    return _evaluator(expression['nodes'], expression.get('plans') or [], inputs, rng, batch_shape, deadline)(expression['root'])


_MERGED = {}


def evaluate_many_np(expressions, inputs, rng=None, batch_shape=None, deadline=None):
    """Values of several serialised graphs evaluated together: structurally identical subgraphs (a loop
    serialised into every program that reads its results) are merged and computed once."""
    # The same programs are evaluated every frame: merge them once (the cache holds the programs, so ids stay valid).
    key = tuple(id(e) for e in expressions)
    cached = _MERGED.get(key)
    if cached is not None and all(a is b for a, b in zip(cached[0], expressions)):merged, roots = cached[1]
    else:
        merged, roots = merge_graphs(expressions)
        if len(_MERGED) > 4096:_MERGED.clear()
        _MERGED[key] = (tuple(expressions), (merged, roots))
    names = input_names(merged, stochastic=rng is not None)
    if names is None or names - set(inputs):raise ValueError('point program not evaluable')
    value = _evaluator(merged['nodes'], merged['plans'], inputs, rng, batch_shape, deadline)
    return [value(root) for root in roots]


def merge_graphs(expressions):
    """One graph holding every expression's nodes once, plus each expression's root in it.

    Nodes are keyed by operation, detail and argument keys; a loop slot is keyed by its name and the
    depth of its plan on the enclosing loop stack, so the same loop serialised into different graphs
    (different plan_ref numbers) gets one key. rand nodes keep their site detail, so distinct sites
    stay distinct draws.
    """
    keys = {};info = []

    def intern(key, payload):
        found = keys.get(key)
        if found is None:found = keys[key] = len(info);info.append(payload)
        return found

    def keyed(graph):
        nodes = graph['nodes'];plans = graph.get('plans') or [];memo = {}

        def plan_key(ref, stack):
            plan = plans[ref];inner = stack + (ref,)
            updates = tuple(node_key(plan['updates'][name], inner) for name in plan['names'])
            rest = json.dumps({k: v for k, v in plan.items() if k not in ('names', 'updates')}, sort_keys=True)
            return intern(('plan', tuple(plan['names']), updates, rest), ('plan', plan, updates))

        def node_key(index, stack):
            memo_key = (index, stack)
            if memo_key in memo:return memo[memo_key]
            node = nodes[index];op = node['op'];detail = dict(node.get('detail') or {})
            ref = detail.pop('plan_ref', None)
            if op == 'loop_eel_slot':
                depth = len(stack) - 1 - stack.index(ref)
                key = intern(('slot', detail.get('name'), depth), ('slot', node, depth))
            elif op == 'loop_eel_result':
                count = len(plans[ref]['names'])
                outer = tuple(node_key(arg, stack) for arg in node['args'][:1 + count])
                plan = plan_key(ref, stack)
                key = intern(('result', json.dumps(detail, sort_keys=True), outer, plan), ('result', node, outer + (plan,)))
            else:
                args = tuple(node_key(arg, stack) for arg in node['args'])
                # A rand call made inside a loop body is tied to that loop by its depth on the stack.
                depth = len(stack) - 1 - stack.index(ref) if ref is not None and ref in stack else None
                key = intern((op, json.dumps(detail, sort_keys=True), args, depth), ('node', node, (args, depth)))
            memo[memo_key] = key
            return key
        return node_key(graph['root'], ())

    root_keys = [keyed(graph) for graph in expressions]
    nodes = [];plans = [];built = {}

    def build_plan(key, stack):
        # One plan per loop and context: every result node of the loop reads the same run.
        if ('plan', key, stack) in built:return built[('plan', key, stack)]
        _, plan, updates = info[key]
        ref = len(plans);entry = {k: v for k, v in plan.items() if k not in ('updates',)};plans.append(entry)
        built[('plan', key, stack)] = ref
        inner = stack + (ref,)
        entry['updates'] = {name: build(update, inner) for name, update in zip(plan['names'], updates)}
        return ref

    def build(key, stack):
        kind, node, args = info[key]
        if kind == 'slot':
            # The slot's plan is the enclosing loop at its recorded depth (slots are keyed by depth).
            memo_key = (key, stack[len(stack) - 1 - args])
        else:memo_key = (key, stack)
        if memo_key in built:return built[memo_key]
        detail = {k: v for k, v in (node.get('detail') or {}).items() if k != 'plan_ref'}
        if kind == 'slot':detail['plan_ref'] = memo_key[1];new_args = []
        elif kind == 'result':
            *outer, plan = args
            new_args = [build(arg, stack) for arg in outer]
            ref = build_plan(plan, stack);detail['plan_ref'] = ref
            new_args += [plans[ref]['updates'][name] for name in plans[ref]['names']]
        else:
            args, depth = args
            new_args = [build(arg, stack) for arg in args]
            if depth is not None:detail['plan_ref'] = stack[len(stack) - 1 - depth]
        nodes.append({'op': node['op'], 'dtype': node.get('dtype'), 'args': new_args, 'detail': detail})
        built[memo_key] = len(nodes) - 1
        return built[memo_key]

    roots = [build(key, ()) for key in root_keys]
    return {'root': roots[0] if roots else None, 'nodes': nodes, 'plans': plans}, roots


def _scalar_condition(value):
    return not isinstance(value, Memory) and np.ndim(value) == 0


def _evaluator(nodes, plans, inputs, rng, batch_shape, deadline):
    """value(index) over one graph's nodes with a memo shared by every root asked for."""
    stochastic = rng is not None
    sizes = {}

    def body_size(plan_ref):
        # Nodes one loop iteration evaluates: everything reachable from the plan's updates (at least 1).
        if plan_ref not in sizes:
            seen = set();todo = list(plans[plan_ref]['updates'].values())
            while todo:
                index = todo.pop()
                if index in seen:continue
                seen.add(index);todo.extend(nodes[index]['args'])
            sizes[plan_ref] = max(1, len(seen))
        return sizes[plan_ref]
    # Which loop plans each node's value depends on (through slots, directly or via nested loops).
    depends = {}

    def plans_of(index):
        if index in depends:return depends[index]
        depends[index] = frozenset()
        node = nodes[index];found = set()
        # A loop slot, and a rand call made inside a loop body, take a new value every iteration.
        if node['op'] in ('loop_eel_slot', 'rand') and 'plan_ref' in (node.get('detail') or {}):found.add(node['detail']['plan_ref'])
        for arg in node['args']:found |= plans_of(arg)
        if node['op'] == 'loop_eel_result':
            plan = node['detail']['plan_ref'];inner = set()
            for update in plans[plan]['updates'].values():inner |= plans_of(update)
            found |= inner - {plan}
        depends[index] = frozenset(found)
        return depends[index]

    active = [];slots = {};memo = {None: {}}

    def store(index):
        own = plans_of(index)
        for plan in reversed(active):
            if plan in own:return memo[plan]
        return memo[None]

    def value(index):
        table = store(index)
        if index in table:return table[index]
        node = nodes[index];op = node['op']
        if op == 'constant':result = np.float64(node['detail']['value'])
        elif op == 'input':
            raw = inputs[node['detail']['name']]
            result = raw if isinstance(raw, Memory) else np.asarray(raw, np.float64)
        elif op == 'loop_eel_slot':result = slots[node['detail']['plan_ref']][node['detail']['name']]
        elif op == 'loop_eel_result':result = run_loop(index)[node['detail']['name']]
        elif op == 'array_mem_read':result = _read(value(node['args'][0]), value(node['args'][1]))
        elif op == 'array_mem_write':result = _write(value(node['args'][0]), value(node['args'][1]), value(node['args'][2]))
        elif op == 'rand' and not stochastic:result = np.abs(value(node['args'][0]))
        elif op in ('select', '_and', '_or') and _scalar_condition(condition := value(node['args'][0])):
            # projectm-eval's if(), && and || run only the branch they need (a rand or memory write in the
            # other branch has no effect); vector conditions keep the elementwise eager form.
            if op == 'select':result = value(node['args'][1] if float(condition) != 0 else node['args'][2])
            else:
                truth = abs(float(condition)) > 1e-5
                if truth == (op == '_or'):result = np.float64(truth)
                else:result = np.float64(abs(float(value(node['args'][1]))) > 1e-5)
        else:result = _apply(op, node, [value(arg) for arg in node['args']], rng, batch_shape)
        table[index] = result
        return result

    def run_loop(index):
        node = nodes[index];plan_ref = node['detail']['plan_ref'];plan = plans[plan_ref]
        table = store(index);key = ('loop', plan_ref)
        if key in table:return table[key]
        count_value = value(node['args'][0])
        if np.ndim(count_value):raise ValueError('loop count varies across evaluated points')
        count = loop_count(count_value)
        current = {}
        for name, initial in zip(plan['names'], node['args'][1:1 + len(plan['names'])]):
            start = value(initial)
            current[name] = start.owned_copy() if isinstance(start, Memory) else start
        active.append(plan_ref)
        budget = deadline if isinstance(deadline, WorkBudget) else None
        cost = body_size(plan_ref) if budget is not None else 0
        try:
            for iteration in range(count):
                if budget is not None:budget.spend(cost)
                elif deadline is not None and iteration % 256 == 0 and time.perf_counter() > deadline:
                    raise ValueError('evaluation budget exceeded')
                memo[plan_ref] = {};slots[plan_ref] = current
                updated = {name: value(plan['updates'][name]) for name in plan['names']}
                for name, result in updated.items():
                    if isinstance(result, Memory):
                        start = current[name]
                        if isinstance(start, Memory) and result.base is start.base:
                            start.base.update(result.overlay);updated[name] = Memory(start.base, {})
                        else:updated[name] = result.owned_copy()
                current = updated
        finally:
            active.pop();memo.pop(plan_ref, None);slots.pop(plan_ref, None)
        table[key] = current
        return current

    return value
