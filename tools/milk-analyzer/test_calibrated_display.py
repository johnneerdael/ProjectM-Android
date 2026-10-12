import math

from calibrated_display import predict


def test_tree_model_predicts_with_transform_and_interval():
    column = 'motion:/x#max'
    model = {'columns': [column], 'label_source': 'test ruler', 'targets': {
        'mean_flow_screen_widths_per_s': {'transform': 'log1p10', 'baseline': math.log1p(1.), 'oof_spearman': .7,
            'residual_p10': -.1, 'residual_p90': .1,
            # one stump: x <= 0.5 -> -0.2, else +0.2
            'trees': [[[0., 0, .5, 1, 2, 0], [-.2, 0, 0., 0, 0, 1], [.2, 0, 0., 0, 0, 1]]]}}}
    summary = {'facts': {'motion': [{'path': '/x', 'value': .8}]}}
    result = predict(summary, model)['mean_flow_screen_widths_per_s']
    assert math.isclose(result['value'], math.expm1(math.log1p(1.) + .2) / 10)
    assert result['interval'][0] < result['value'] < result['interval'][1]
    assert result['evidence'] == 'source-calibrated'
    missing = predict({'facts': {}}, model)['mean_flow_screen_widths_per_s']
    assert math.isclose(missing['value'], math.expm1(math.log1p(1.) - .2) / 10)  # missing sentinel goes left
