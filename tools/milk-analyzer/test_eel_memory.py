from types import SimpleNamespace

import eel_memory as M
from effect_families import _EEL
from source_stage_program import frame_program, serialise


def call(function, *args, **extra):
    return {'kind': 'call', 'function': function, 'args': list(args), 'instructions': [], **extra}


def var(name):
    return {'kind': 'variable', 'name': name}


def num(value):
    return {'kind': 'constant', 'value': float(value)}


def seq(*instructions):
    return {'kind': 'call', 'function': 'sequence', 'args': [], 'instructions': list(instructions)}


def assign(target, value):
    return call('assign', target, value)


def gmem(index):
    return call('mem', index, memory_space='global')


def lowered(tree, environment=None):
    model = _EEL(environment or {})
    model.lower(tree)
    return model


def value(model, name, inputs=None):
    return float(M.evaluate_np(serialise(model.environment[name]), inputs or {}))


def counting_loop(count):
    # i=0; x=0; loop(count, x=x+i; i=i+1)
    return seq(assign(var('i'), num(0)), assign(var('x'), num(0)),
               call('loop', count, seq(assign(var('x'), call('_add', var('x'), var('i'))),
                                      assign(var('i'), call('_add', var('i'), num(1))))))


def test_fixed_count_loop_runs_its_body_sequentially():
    model = lowered(counting_loop(num(4)))
    assert not model.unknown
    assert value(model, 'x') == 6. and value(model, 'i') == 4.


def test_loop_count_is_truncated_once_and_non_positive_counts_skip_the_body():
    assert value(lowered(counting_loop(num(2.9))), 'i') == 2.
    assert value(lowered(counting_loop(num(-3))), 'i') == 0.
    # The count is read before the body runs: a body that changes n does not change the count.
    tree = seq(assign(var('n'), num(3)), assign(var('i'), num(0)),
               call('loop', var('n'), seq(assign(var('n'), num(100)), assign(var('i'), call('_add', var('i'), num(1))))))
    assert value(lowered(tree), 'i') == 3.


def test_loop_count_is_capped_like_projectm_eval():
    assert M.MAX_LOOP_COUNT == 1048576
    assert M.loop_count(5e9) == M.MAX_LOOP_COUNT and M.loop_count(-0.5) == 0 and M.loop_count(3.99) == 3


def test_loop_writes_global_memory_that_later_code_reads():
    # i=0; loop(3, gmegabuf(2*i)=10*i; i=i+1); y=gmegabuf(4)
    tree = seq(assign(var('i'), num(0)),
               call('loop', num(3), seq(assign(gmem(call('_mul', num(2), var('i'))), call('_mul', num(10), var('i'))),
                                        assign(var('i'), call('_add', var('i'), num(1))))),
               assign(var('y'), gmem(num(4))), assign(var('z'), gmem(num(3))))
    model = lowered(tree)
    assert not model.unknown
    assert value(model, 'y', {'memory:global': M.Memory()}) == 20.
    assert value(model, 'z', {'memory:global': M.Memory()}) == 0.


def test_memory_index_rules_follow_projectm_eval():
    memory = M.Memory()
    # int32(index + 0.0001): truncation toward zero, so -1 still addresses item 0.
    assert M.memory_index(1.99995) == 2 and M.memory_index(-1.) == 0 and M.memory_index(-1.5) is None
    assert M.memory_index(M.MEMORY_ITEMS) is None and M.memory_index(M.MEMORY_ITEMS - 1) == M.MEMORY_ITEMS - 1
    written = memory.write(-1., 7.)
    assert written.read(0.) == 7. and memory.read(0.) == 0.
    # Writes outside the buffer are discarded (the assignment still yields its value).
    assert memory.write(-2., 5.).read(0.) == 0.
    tree = assign(var('v'), assign(gmem(num(-2)), num(5)))
    assert value(lowered(tree), 'v', {'memory:global': M.Memory()}) == 5.


def test_local_and_global_buffers_are_separate():
    tree = seq(assign(call('mem', num(1), memory_space='local'), num(3)), assign(var('g'), gmem(num(1))),
               assign(var('l'), call('mem', num(1), memory_space='local')))
    model = lowered(tree)
    inputs = {'memory:global': M.Memory(), 'memory:local': M.Memory()}
    assert value(model, 'g', inputs) == 0. and value(model, 'l', inputs) == 3.


def test_while_loops_stay_unresolved():
    model = lowered(call('while', assign(var('x'), num(0))))
    assert model.unknown and model.environment['x'].op == 'unknown'


def test_frame_program_carries_memory_across_frames():
    from prediction_illustration import _FrameStepper
    init = lowered(assign(gmem(num(0)), num(10)))
    frame = lowered(seq(assign(gmem(num(0)), call('_add', gmem(num(0)), num(1))), assign(var('q1'), gmem(num(0)))))
    analysis = SimpleNamespace(main=frame.environment, frame_init=init.environment,
                               frame_memory=frame.memory, frame_init_memory=init.memory)
    program = frame_program(analysis)
    assert 'memory:global' in program['state'] and not program['unsupported']
    stepper = _FrameStepper(program)
    first = stepper.step(1 / 30, 30, {}, 0)
    second = stepper.step(2 / 30, 30, {}, 1)
    assert first['q1'] == 11. and second['q1'] == 12.
    # The end-of-frame memory is exposed for shape and wave code that runs after the frame code.
    assert second['memory:global'].read(0.) == 12.


def test_shape_code_reads_memory_written_by_frame_code():
    from source_appearance import _expression
    shape = lowered(assign(var('x'), call('_add', num(.5), gmem(call('_mul', num(2), var('instance'))))))
    expression = _expression(shape.environment['x'])
    assert expression['complete']
    memory = M.Memory().write(4., .25)
    assert float(M.evaluate_np(expression, {'memory:global': memory, 'instance': 2.})) == .75
    assert M.input_names(expression) == {'memory:global', 'instance'}


def test_rand_draws_independently_for_every_point_of_a_batch():
    import numpy as np
    graph = {'root': 0, 'nodes': [{'op': 'rand', 'args': [1], 'detail': {}}, {'op': 'constant', 'args': [], 'detail': {'value': 100.}}]}
    values = M.evaluate_np(graph, {}, np.random.default_rng(1), batch_shape=(4000,))
    assert values.shape == (4000,) and len(set(values.tolist())) == 4000
    # projectm-eval rand(x): continuous uniform on [0, max(1, floor(x))].
    assert abs(values.mean() - 50.) < 2. and values.min() >= 0. and values.max() <= 100.


def test_bitwise_operators_truncate_to_integers_like_projectm_eval():
    # /*and*/ and /*or*/: (int64)a & (int64)b, truncation toward zero.
    tree = seq(assign(var('a'), call('/*and*/', num(6.9), num(3.2))), assign(var('o'), call('/*or*/', num(-1.5), num(4.))),
               assign(var('z'), call('/*and*/', num(0.), var('s'))))
    model = lowered(tree)
    assert not model.unknown
    assert value(model, 'a') == 2. and value(model, 'o') == float(-1 | 4) and value(model, 'z', {'s': 37.}) == 0.
    assert M.input_names(serialise(model.environment['a'])) == set()


def test_evaluation_stops_at_its_deadline():
    import time
    import pytest
    tree = seq(assign(var('i'), num(0)), call('loop', num(1000000), assign(var('i'), call('_add', var('i'), num(1)))))
    graph = serialise(lowered(tree).environment['i'])
    with pytest.raises(ValueError, match='budget'):
        M.evaluate_np(graph, {}, deadline=time.perf_counter() - 1)


def test_exec2_and_exec3_evaluate_their_arguments_in_order_and_return_the_last():
    # projectm-eval exec2(a, b) runs a then b and yields b (exec3 likewise with three). Particle presets
    # fill gmegabuf with loop(n, exec2(assign(gmegabuf(i*8), v), assign(i, i+1))) (r93).
    body = call('exec2', assign(gmem(call('_mul', var('i'), num(8))), call('_add', var('i'), num(.5))),
                assign(var('i'), call('_add', var('i'), num(1))))
    model = lowered(seq(assign(var('i'), num(0)), call('loop', num(3), body)))
    assert not model.unknown
    memory = M.evaluate_np(serialise(model.memory['global']), {'memory:global': M.Memory()})
    assert [memory.read(float(k)) for k in (0, 8, 16, 24)] == [.5, 1.5, 2.5, 0.]
    assert value(model, 'i', {'memory:global': M.Memory()}) == 3.
    three = lowered(assign(var('r'), call('exec3', assign(var('a'), num(2)), assign(var('b'), call('_mul', var('a'), num(3))),
                                          call('_add', var('b'), num(1)))))
    assert not three.unknown and value(three, 'r') == 7. and value(three, 'b') == 6.


def test_evaluate_many_runs_a_loop_shared_by_several_programs_once():
    # Per-frame programs are serialised one by one, so a loop feeding several outputs appears in each
    # graph. Evaluated together they share one run (r93: ~98 programs re-ran the same particle loops).
    model = lowered(counting_loop(num(5)))
    x, i = serialise(model.environment['x']), serialise(model.environment['i'])
    calls = []
    original = M.loop_count
    M.loop_count = lambda value: calls.append(1) or original(value)  # run_loop reads the count once per run
    try:
        values = M.evaluate_many_np([x, i, x], {})
    finally:
        M.loop_count = original
    assert [float(v) for v in values] == [10., 5., 10.]
    assert len(calls) == 1
    # Distinct rand sites stay distinct draws; the same site in two programs is one draw.
    import numpy as np
    def rand_graph(site):
        return {'root': 0, 'nodes': [{'op': 'rand', 'args': [1], 'detail': {'site_index': site}},
                                     {'op': 'constant', 'args': [], 'detail': {'value': 1000.}}]}
    a, b, c = M.evaluate_many_np([rand_graph(0), rand_graph(1), rand_graph(0)], {}, np.random.default_rng(3))
    assert float(a) == float(c) and float(a) != float(b)


def test_rand_inside_a_loop_body_draws_every_iteration_but_a_value_drawn_before_the_loop_does_not():
    import numpy as np
    # i=0; loop(3, exec2(assign(gmegabuf(i), rand(1000)), assign(i, i+1))): three independent draws (r93
    # particles all started at one position). x=rand(1000) before the loop is one draw reused inside it.
    body = call('exec2', assign(gmem(var('i')), call('rand', num(1000))), assign(var('i'), call('_add', var('i'), num(1))))
    model = lowered(seq(assign(var('i'), num(0)), call('loop', num(3), body)))
    graph = serialise(model.memory['global'])
    memory = M.evaluate_np(graph, {'memory:global': M.Memory()}, np.random.default_rng(5))
    draws = [memory.read(float(k)) for k in range(3)]
    assert len(set(draws)) == 3
    merged = M.evaluate_many_np([graph], {'memory:global': M.Memory()}, np.random.default_rng(5))[0]
    assert len({merged.read(float(k)) for k in range(3)}) == 3
    before = lowered(seq(assign(var('x'), call('rand', num(1000))), assign(var('i'), num(0)),
                         call('loop', num(3), call('exec2', assign(gmem(var('i')), var('x')), assign(var('i'), call('_add', var('i'), num(1)))))))
    memory = M.evaluate_np(serialise(before.memory['global']), {'memory:global': M.Memory()}, np.random.default_rng(5))
    assert len({memory.read(float(k)) for k in range(3)}) == 1
