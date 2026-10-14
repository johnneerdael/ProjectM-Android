"""Layout of projectm-eval's single rand() stream across a preset's code blocks.

projectm-eval draws every rand() call from one Mersenne Twister per thread (fixed seed 0x4141f00d, patch
0004). At load the engine runs the main init code, then the init code of all four custom waves and all
four custom shapes, enabled or not (MilkdropPreset::CompileCodeAndRunInitExpressions). Each frame it runs
the main per-frame code, the per-pixel code once per mesh vertex, then the enabled shapes (per-frame code
once per instance) and the enabled waves (per-frame code, then per-point code once per sample). A
consumer stepping only the main per-frame code skips the draws the other blocks take in between.

Counts are rand call sites in each block's parsed tree; a call inside an if() branch, a loop body or the
right side of && / || may not run, so those are counted separately and make the layout inexact.
"""
from scene_equations import _scalar

POLICY = 'source-rand-stream-layout-v1'
_LAZY = {'if': (1, 2), '_if': (1, 2), '_and': (1,), '_or': (1,)}
_LOOPS = {'loop', 'while', '_loop', '_while'}


def _count(tree):
    calls = conditional = 0
    def visit(node, guarded):
        nonlocal calls, conditional
        if not isinstance(node, dict):return
        function = node.get('function') if node.get('kind') == 'call' else None
        if function == 'rand':
            calls += 1
            if guarded:conditional += 1
        lazy = _LAZY.get(function, ())
        for index, arg in enumerate(node.get('args') or []):
            visit(arg, guarded or index in lazy or (function in _LOOPS and (function in ('while', '_while') or index > 0)))
        for instruction in node.get('instructions') or []:visit(instruction, guarded or function in _LOOPS)
    visit(tree, False)
    return {'calls': calls, 'conditional': conditional}


def rand_stream(analysis, mesh=(48, 32)):
    from equation_loading import select_equation
    values = getattr(analysis, 'values', {}) or {}
    sections = getattr(analysis, 'sections', {}) or {}
    policy = getattr(analysis, 'policy', 'strict-raw-v1')
    names = ['per_frame_init_', 'per_frame_', 'per_pixel_']
    names += [f'wave_{i}_{part}' for i in range(4) for part in ('init', 'per_frame', 'per_point')]
    names += [f'shape_{i}_{part}' for i in range(4) for part in ('init', 'per_frame')]
    blocks = {}
    for name in names:
        selected = select_equation(sections.get(name), name, policy=policy)
        blocks[name] = _count(selected.get('tree')) if selected.get('compile_status') == 'accepted' else {'calls': 0, 'conditional': 0}
    load = sum(blocks[f'{kind}_{i}_init']['calls'] for kind in ('wave', 'shape') for i in range(4))
    vertices = (int(mesh[0]) + 1) * (int(mesh[1]) + 1)
    frame = blocks['per_pixel_']['calls'] * vertices
    used = ['per_pixel_'] + [f'{kind}_{i}_init' for kind in ('wave', 'shape') for i in range(4)]
    for i in range(4):
        if _scalar(values, f'shapecode_{i}_enabled', 0, 'bool'):
            instances = max(1, min(1024, _scalar(values, f'shapecode_{i}_num_inst', 1, 'int')))
            frame += blocks[f'shape_{i}_per_frame']['calls'] * instances;used.append(f'shape_{i}_per_frame')
        if _scalar(values, f'wavecode_{i}_enabled', 0, 'bool'):
            samples = max(0, min(512, _scalar(values, f'wavecode_{i}_samples', 512, 'int')))
            frame += blocks[f'wave_{i}_per_frame']['calls'] + blocks[f'wave_{i}_per_point']['calls'] * samples
            used += [f'wave_{i}_per_frame', f'wave_{i}_per_point']
    return {'policy': POLICY, 'blocks': blocks, 'mesh_vertices': vertices,
            'load_draws_after_main_init': load, 'frame_draws_after_main': frame,
            'exact': not any(blocks[name]['conditional'] for name in used),
            'conditions': ['rand call sites per parsed block; guarded calls (if branches, loop bodies, && / || right sides) may not run',
                           'per-frame sample counts use the header wavecode samples; a per-frame samples value changes them']}
