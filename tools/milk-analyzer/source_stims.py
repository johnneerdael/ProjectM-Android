"""Supplemental may-dependencies of phase-local recurrent scalar state.

Adapted from Stims' monotone predecessor-source closure and dataflow fixtures:
zz-plant/stims@36e902704cab7a3c39bfc0a6b2bf587d8ba7e291,
packages/milkdrop-toolchain/src/preset-dataflow.ts, public domain (Unlicense).
Only the dependency-set algorithm is reused. Native parsing, causal slicing,
initial inputs and phase storage rules remain ProjectM TV's own contracts.
Never substitute this closure into a numeric expression or certify reaction.
"""
from collections import deque
import hashlib
from pathlib import Path
import re

from effect_families import _CACHE, _EEL, _SemanticBudget, _constant, _walk
from equation_loading import select_equation
from scene_equations import MAIN, Q, READONLY, _scalar, _variables, source_settings
from shader_fields import Field

POLICY = 'source-stims-main-local-may-dependencies-v1'
STIMS_COMMIT = '36e902704cab7a3c39bfc0a6b2bf587d8ba7e291'


def _facts(field):
    dependencies = set(); unknown = set()
    for index, (node, _) in enumerate(_walk(field)):
        if index >= 250000:
            raise _SemanticBudget('Stims causal field traversal budget exceeded')
        if node.op == 'input':
            dependencies.add(node.detail['name'])
            if str(node.detail['name']).startswith('memory:'):
                unknown.add('shared memory buffer content depends on writes in other phases and earlier frames')
        if node.op == 'unknown':
            unknown.add(node.detail.get('reason', 'unsupported source value'))
        if node.op == 'rand':
            unknown.add('random stream and cross-phase conditional call-count dependence remains unqualified')
    return dependencies, unknown


def dependency_fixpoint(outputs, predecessors, *, initial=None, max_states=512):
    """Close explicitly supplied predecessor edges; retain initial uncertainty.

    Callers must qualify storage/reset boundaries before supplying an edge.
    Initial seeds are unioned because an output may occur in the first frame.
    This is a finite monotone worklist, with no guessed eight-frame cutoff.
    Missing initial seeds remain explicit unknowns, never assumed constants.
    """
    if type(max_states) is not int or max_states < 0:
        raise ValueError('nonnegative integer state budget required')
    if len(predecessors) > max_states:
        return {'status': 'unresolved', 'converged': False, 'state_count': len(predecessors),
                'outputs': {}, 'unresolved_reasons': ['phase-local predecessor budget exceeded']}
    initial = initial or {}
    state_names = set(predecessors)
    direct = {}; reasons = {}; edges = {}; dependents = {name: set() for name in state_names}
    for name, field in predecessors.items():
        dependencies, unknown = _facts(field)
        seed = initial.get(name)
        if seed is None:
            unknown.add('initial state not supplied: ' + name)
        else:
            seed_dependencies, seed_unknown = _facts(seed)
            dependencies |= seed_dependencies; unknown |= seed_unknown
        edges[name] = dependencies & state_names
        direct[name] = dependencies - state_names
        reasons[name] = unknown
        for dependency in edges[name]:
            dependents[dependency].add(name)
    pending = deque(sorted(state_names)); queued = set(state_names); updates = 0
    while pending:
        name = pending.popleft(); queued.remove(name)
        dependencies = set(direct[name]); unknown = set(reasons[name])
        for dependency in edges[name]:
            dependencies |= direct[dependency]; unknown |= reasons[dependency]
        if dependencies != direct[name] or unknown != reasons[name]:
            direct[name] = dependencies; reasons[name] = unknown; updates += 1
            for dependent in sorted(dependents[name] - queued):
                pending.append(dependent); queued.add(dependent)
    rows = {}
    for name, field in outputs.items():
        baseline, unknown = _facts(field)
        references = baseline & state_names
        dependencies = baseline - state_names
        for reference in references:
            dependencies |= direct[reference]; unknown |= reasons[reference]
        rows[name] = {'baseline_input_dependencies': sorted(baseline),
                      'may_input_dependencies': sorted(dependencies),
                      'newly_exposed_input_dependencies': sorted(dependencies - baseline),
                      'predecessor_inputs': sorted(references),
                      'unresolved_reasons': sorted(unknown),
                      'quantitative_value_preserved_unknown': bool(references or unknown)}
    unknown = sorted({reason for row in rows.values() for reason in row['unresolved_reasons']})
    return {'status': 'partial' if unknown else 'source_may_dependencies', 'converged': True,
            'state_count': len(state_names), 'worklist_updates': updates,
            'outputs': rows, 'unresolved_reasons': unknown}


def source_phase_dependency_evidence(source, *, max_states=512):
    """Analyze native main locals only, preserving Q reload and shared effects.

    No custom, pixel, register or memory-bank edge is supplied to the closure.
    Read-before-write locals refer to the *previous* final main-frame value.
    The existing EEL lowerer preserves statement order, dead branches and
    unsupported pointer aliases/loops. Bounds and source graphs are untouched.
    """
    # Structural identity must intern shared DAGs for the whole phase. The
    # caller's analyzer scope may have ended before this public supplement runs.
    token = _CACHE.set({}) if _CACHE.get() is None else None
    metadata = {}
    try:
        return _source_phase_dependency_evidence(source, max_states=max_states, metadata=metadata)
    except _SemanticBudget as error:
        return {**metadata, 'status': 'unresolved', 'converged': False,
                'state_count': 0, 'outputs': {}, 'unresolved_reasons': [str(error)]}
    finally:
        if token is not None:
            _CACHE.reset(token)


def _source_phase_dependency_evidence(source, *, max_states, metadata):
    policy = source.get('equation_assembly_policy', 'strict-raw-v1')
    selected = {prefix: select_equation(source.get('sections', {}).get(prefix), prefix, policy=policy)
                for prefix in ('per_frame_init_', 'per_frame_')}
    record = {'policy': POLICY, 'phase': 'per_frame_',
              'preset_sha256': source.get('preset_sha256'), 'equation_loader_policy': policy,
              'provenance': {'reference_repository': 'https://github.com/zz-plant/stims',
                             'reference_commit': STIMS_COMMIT,
                             'reference_component': 'packages/milkdrop-toolchain/src/preset-dataflow.ts',
                             'reference_license': 'Unlicense',
                             'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
              'uses_equation_execution': False, 'numeric_bounds_changed': False,
              'guaranteed_visible_audio_reaction': False,
              'scope': 'main private scalar predecessor may-dependencies; no numeric or cell-alias inference',
              'conditions': ['Initial audio snapshots remain distinct declared unknown inputs',
                             'Main Q reloads its init snapshot; custom/pixel Q writes are isolated',
                             'Shared register/memory, loop and native pointer-alias uncertainty is retained',
                             'Random stream and cross-phase call-count dependencies are not inferred',
                             'Causal slicing retains existing finite usable-domain premises; no absence proof for unsupported/nonfinite arithmetic',
                             'A may-dependency is neither a nonzero derivative nor a guaranteed visible response'],
              'section_sha256': {prefix: hashlib.sha256((item.get('code') or '').encode()).hexdigest()
                                 for prefix, item in selected.items()}}
    metadata.update(record)
    if any(item['compile_status'] not in {'accepted', 'omitted'} or
           (item['compile_status'] == 'accepted' and item['tree_status'] != 'parsed')
           for item in selected.values()):
        return {**record, 'status': 'unresolved', 'converged': False, 'outputs': {}, 'state_count': 0,
                'unresolved_reasons': ['native main equation loading/tree unresolved']}
    values = source_settings(source)
    defaults = {name: _constant(_scalar(values, key, default, kind))
                for name, (key, default, kind) in MAIN.items()}
    defaults.update({name: _constant(0) for name in Q})
    init = _EEL({**defaults, **{name: Field('input', detail={'name': 'init:per_frame_init_:' + name})
                              for name in READONLY}}, equation_phase='per_frame_init_')
    init.lower(selected['per_frame_init_']['tree'])
    resets = {**defaults, **{name: Field('input', detail={'name': name}) for name in
                            (*READONLY, 'meshx', 'meshy', 'pixelsx', 'pixelsy', 'aspectx', 'aspecty')},
              **{name: init.environment.get(name, _constant(0)) for name in Q}}
    tree = selected['per_frame_']['tree']
    local_names = _variables(tree) - resets.keys()
    registers = {name for name in local_names if re.fullmatch(r'reg[0-9]{2}', name)}
    locals_written = (_EEL.assignment_targets(tree) & local_names) - registers
    environment = dict(init.environment)
    for name in local_names:
        if name in registers:
            environment[name] = Field('input', detail={'name': 'shared:' + name})
        elif name in locals_written:
            environment[name] = Field('input', detail={'name': 'state:per_frame_:' + name})
        elif name not in environment:
            environment[name] = Field('unknown', detail={'reason': 'unbound native local: ' + name})
    environment.update(resets)
    frame = _EEL(environment, equation_phase='per_frame_'); frame.lower(tree)
    predecessors = {'state:per_frame_:' + name: frame.environment[name] for name in locals_written}
    initial = {key: init.environment.get(key.rsplit(':', 1)[1], Field('unknown', detail={
                   'reason': 'initial local value remains unqualified: ' + key})) for key in predecessors}
    outputs = {name: value for name, value in frame.environment.items()
               if name in MAIN or name in frame.written or name in Q}
    result = dependency_fixpoint(outputs, predecessors, initial=initial, max_states=max_states)
    unknown = set(result['unresolved_reasons']) | set(init.unknown) | set(frame.unknown)
    # A memory access can alias writes outside this phase, even in disabled init.
    pending = [section.get('projectm_raw_tree') or section.get('tree')
               for prefix, section in source.get('sections', {}).items() if prefix not in {'warp_', 'comp_'}]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get('function') == 'mem':
                unknown.add('shared memory cell/bank alias and cross-phase effects remain unresolved')
            pending.extend(value for value in node.values() if isinstance(value, (dict, list)))
        elif isinstance(node, list):
            pending.extend(node)
    if any(item['compile_status'] == 'omitted' for item in selected.values()):
        unknown.add('native loader omitted a rejected equation block')
    if unknown and result['status'] != 'unresolved':
        result['status'] = 'partial'
    return {**record, **result, 'unresolved_reasons': sorted(unknown)}
