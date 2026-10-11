"""Shape state is independent nominal export evidence, never mood credit."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / 'build/preset-corpus/source34/adapters/milk-native-reader'
PRESETS = ROOT / 'core/src/main/assets/presets'


def read(path):
    assert READER.is_file(), 'exact source34 reader required'
    source = json.loads(subprocess.check_output([str(READER), str(path)]))
    source['preset_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    from engine_profiles import CORE_2334_ENGINE
    assert source['parser_inputs']['engine'] == CORE_2334_ENGINE
    source['parser_inputs']['setting_lookup_policy'] = 'native-case-insensitive-v1'
    return source


def report(source, context=None):
    from effect_families import _Analysis
    from source_appearance import appearance_from_analysis
    from source_static_behaviour import static_behaviour
    analysis = _Analysis(source, 'gles300', None)
    analysis.input_scenario = None
    analysis.main_equations(); analysis.primitives()
    analysis.shader('warp', 'warp_'); analysis.shader('composite', 'comp_')
    analysis.contribution_gates()
    description = appearance_from_analysis(analysis)
    return static_behaviour(analysis, description, context)


@pytest.mark.parametrize('name,paired', [
    ("loin bowel - don't you understand baby, i don't want a big studio in the hills - how to impress dullards2.milk", True),
    ('suksma - fiShbRaiN - witchcraft (phugly megalopolish remix)2 - skekseas.milk', False),
])
def test_actual_source34_exports_conditional_copied_state_without_mood_credit(name, paired):
    from source_shape_state_domains import ZERO_POLICY
    value = report(read(PRESETS / name))
    shape = value['shape_state']['by_component']['shape_0']
    assert shape['initial_variable_policy'] == ZERO_POLICY
    assert shape['state_domains']['mx'][0] == 0
    assert ('my' in shape['state_domains']) is paired
    assert ('y' in shape['instance_output_domains']) is paired
    assert 'ma' not in shape['state_domains']
    assert shape['native_numeric_certified'] is False
    assert shape['visible_motion_certified'] is False
    assert value['motion']['unresolved_contributors']
    assert value['classification']['eligible_bands'] == []
    assert value['output_model_complete'] is False
    for name in ('source_shape_state_domains.py', 'source_proofs_worker.py'):
        assert value['model_sources'][name] == hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    json.dumps(value, allow_nan=False)


def test_export_uses_native_active_shape_count_and_filters_declared_domains(tmp_path):
    path = tmp_path / 'instances.milk'
    path.write_text('[preset00]\nshapecode_0_enabled=1\nshapecode_0_num_inst=3suffix\n'
                    'shape_0_per_frame1=x=instance;y=q1;\n'
                    'shapecode_1_enabled=0\nshape_1_per_frame1=x=.1;\n'
                    'shapecode_2_enabled=1\nshapecode_2_num_inst=0\n'
                    'shape_2_per_frame1=x=.2;\n')
    value = report(read(path), {'viewport':[1920,1080], 'feedback_fps':30,
                   'scalar_input_domains':{'instance':[99,99], 'mx':[0,1],
                                           '_c2.x':[0,100], 'bass':[0,2]}})
    shapes = value['shape_state']['by_component']
    assert set(shapes) == {'shape_0'}
    shape = shapes['shape_0']
    assert shape['native_instance_count'] == 3
    assert shape['instance_output_domains']['x'] == [0.,2.]
    assert 'y' not in shape['instance_output_domains']
    assert shape['input_domains'] == {'bass':[0,2], 'instance':[0,2]}


@pytest.mark.parametrize('engine', [None, [], 'malformed', {},
                                  {'commit':'unmatched', 'patches_sha256':'unmatched'}])
def test_malformed_or_unmatched_engine_never_acquires_native_zero_policy(tmp_path, engine):
    path = tmp_path / 'unbound.milk'
    path.write_text('[preset00]\nshapecode_0_enabled=1\n'
                    'shape_0_per_frame1=mx=min(1,mx+.1);x=mx;y=q1;\n')
    source = read(path)
    source['parser_inputs']['engine'] = copy.deepcopy(engine)
    source['parser_inputs'].pop('setting_lookup_policy')
    from types import SimpleNamespace
    from source_static_behaviour import _shape_state, validate_context
    value = _shape_state(SimpleNamespace(source=source, policy='projectmtv-core-2.2.8-v1'),
                         {}, validate_context())
    shape = value['by_component']['shape_0']
    assert shape.get('initial_variable_policy') is None
    assert 'mx' not in shape['state_domains']
    assert 'x' not in shape['instance_output_domains']
    assert 'y' not in shape['instance_output_domains']


def test_shape_producer_failure_preserves_independent_evidence(tmp_path, monkeypatch):
    import source_shape_state_domains
    from effect_families import _SemanticBudget
    def exhausted(*args, **kwargs):
        raise _SemanticBudget('synthetic independent shape state budget')
    monkeypatch.setattr(source_shape_state_domains, 'shape_state_domain_evidence', exhausted)
    path = tmp_path / 'failure.milk'
    path.write_text('[preset00]\nshapecode_0_enabled=1\nshape_0_per_frame1=x=.2;\n')
    value = report(read(path))
    assert value['producer_failures']['shape_state']['reason'] == 'synthetic independent shape state budget'
    assert value['shape_state']['by_component'] == {}
    assert value['motion']['contributions']
    assert value['prominence']['components']
    assert value['colour']['components']
