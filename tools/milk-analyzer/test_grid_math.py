import unittest
import importlib
import numpy as np
import test_field_math


class GridMathTest(unittest.TestCase):
    def test_declared_mix_profile_preserves_nested_fma_in_scalar_and_grid(self):
        from field_math import evaluate
        from grid_math import evaluate_grid
        _,field=test_field_math.lower('ret=lerp(float3(uv.x),float3(uv.y),bass);')
        inputs={'_uv':[2.0584590435028076,1.4206379652023315,0,0],
                '_c3':[.9552963972091675,0,0,0]}
        profile='apple-m4pro-gles-mix-nested-fma-v1'
        expected=np.full(3,np.float32(1.4491509199142456))
        np.testing.assert_array_equal(evaluate(field,inputs=inputs,arithmetic_profile=profile),expected)
        np.testing.assert_array_equal(evaluate_grid(field,batch_shape=(2,),inputs=inputs,
                                                   arithmetic_profile=profile),np.tile(expected,(2,1)))
        self.assertFalse(np.array_equal(evaluate(field,inputs=inputs),expected))
        inputs={'_uv':[[2.0584590435028076,1.4206379652023315,0,0],
                       [.01025390625,.78466796875,0,0]],'_c3':[.9552963972091675,0,0,0]}
        actual=evaluate_grid(field,batch_shape=(2,),inputs=inputs,arithmetic_profile=profile)
        for lane in range(2):
            np.testing.assert_array_equal(actual[lane],evaluate(field,
                inputs={'_uv':inputs['_uv'][lane],'_c3':inputs['_c3']},arithmetic_profile=profile))

    def test_scalar_loop_fallback_retains_mix_profile(self):
        from field_math import evaluate
        from unittest.mock import patch
        import grid_math
        _,field=test_field_math.lower('float a[2]={.125,.75};ret=lerp(a[0],a[1],bass);')
        calls=[];actual=grid_math.evaluate_grid
        def observe(*args,**kwargs):
            calls.append(kwargs['arithmetic_profile'])
            return actual(*args,**kwargs)
        with patch.object(grid_math,'evaluate_grid',side_effect=observe):
            result=evaluate(field,inputs={'_c3':[.25,0,0,0]},
                            arithmetic_profile='apple-m4pro-gles-mix-nested-fma-v1')
        self.assertEqual(calls,['apple-m4pro-gles-mix-nested-fma-v1'])
        np.testing.assert_array_equal(result,np.full(3,np.float32(.28125)))

    def test_logical_guards_do_not_evaluate_invalid_unselected_rhs_domains(self):
        module=importlib.import_module('grid_math')
        for body,positions,expected in [
            ('ret=(uv.x!=0 && 1/uv.x>0) ? float3(1) : float3(0);',[-1,0,1],[0,0,1]),
            ('ret=(uv.x==0 || log(uv.x)>0) ? float3(1) : float3(0);',[0,.5,2],[1,0,1])]:
            _,field=test_field_math.lower(body)
            uv=np.zeros((3,4),dtype=np.float32);uv[:,0]=positions
            actual=module.evaluate_grid(field,batch_shape=(3,),inputs={'_uv':uv})
            np.testing.assert_allclose(actual,np.repeat(np.array(expected)[:,None],3,axis=1))

    def test_native_vector_operations_match_known_value_and_scalar_execution(self):
        module=importlib.import_module('grid_math')
        from field_math import evaluate
        _,field=test_field_math.lower('float3 a=float3(uv,bass);a.yx=a.xy+float2(.1,.2);ret=normalize(a)+float3(length(uv),0,0);')
        uv=np.zeros((2,3,4),dtype=np.float32)
        uv[...,0]=np.array([[0,.25,.5],[.75,.8,1]])
        uv[...,1]=np.array([[0,.2,.4],[.6,.8,1]])
        inputs={'_uv':uv,'_c3':[.5,0,0,0]}
        actual=module.evaluate_grid(field,batch_shape=(2,3),inputs=inputs)
        np.testing.assert_allclose(actual[0,0],[.2,.1,.5]/np.sqrt(.3),atol=1e-6)
        for i in range(2):
            for j in range(3):
                np.testing.assert_allclose(actual[i,j],evaluate(field,inputs={'_uv':uv[i,j],'_c3':[.5,0,0,0]}),atol=1e-6)

    def test_selected_domains_only_are_evaluated_in_mixed_grid_conditions(self):
        module=importlib.import_module('grid_math')
        _,field=test_field_math.lower('ret=uv.x>0 ? float3(log(uv.x)) : float3(0);')
        uv=np.array([[-1,0,0,0],[0,0,0,0],[.5,0,0,0]],dtype=np.float32)
        result=module.evaluate_grid(field,batch_shape=(3,),inputs={'_uv':uv})
        np.testing.assert_allclose(result,[[0]*3,[0]*3,[np.log(.5)]*3],atol=1e-6)

    def test_matrix_rotation_preserves_each_lane_and_row_vector_convention(self):
        module=importlib.import_module('grid_math')
        _,field=test_field_math.lower('float2x2 m=float2x2(cos(time),-sin(time),sin(time),cos(time));ret=float3(mul(uv,m),0);')
        uv=np.array([[[1,0,0,0],[0,1,0,0]]],dtype=np.float32)
        result=module.evaluate_grid(field,batch_shape=(1,2),inputs={'_uv':uv,'_c2':[np.pi/2,30,0,0]})
        np.testing.assert_allclose(result,[[[0,-1,0],[1,0,0]]],atol=1e-6)

    def test_matrix_index_can_differ_per_lane(self):
        module=importlib.import_module('grid_math')
        _,field=test_field_math.lower('float2x2 m=float2x2(1,2,3,4);ret=float3(m[(int)uv.x],0);')
        result=module.evaluate_grid(field,batch_shape=(2,),inputs={'_uv':[[0,0,0,0],[1,0,0,0]]})
        np.testing.assert_allclose(result,[[1,2,0],[3,4,0]])

    def test_texture_callback_gets_exact_coordinates_and_history_for_all_lanes(self):
        module=importlib.import_module('grid_math')
        _,field=test_field_math.lower('ret=GetPixel(uv+float2(.01,0))*bass;')
        uv=np.array([[[.25,.25,0,0],[.75,.25,0,0]],[[.25,.75,0,0],[.75,.75,0,0]]],dtype=np.float32)
        seen=[]
        def sample(detail,coordinates):
            seen.append((detail['frame'],coordinates.copy()))
            u,v=coordinates[:,0],coordinates[:,1]
            return np.stack((u,v,u*v,np.ones_like(u)),axis=-1)
        actual=module.evaluate_grid(field,batch_shape=(2,2),inputs={'_uv':uv,'_c3':[2,0,0,0]},sample=sample)
        self.assertEqual(seen[0][0],2)
        self.assertEqual(seen[0][1].shape,(4,2))
        np.testing.assert_allclose(actual[0,0],[.52,.5,.13],atol=1e-6)

    def test_uniform_vector_is_not_confused_with_equal_length_batch(self):
        module=importlib.import_module('grid_math')
        _,field=test_field_math.lower('ret=float3(bass,mid,treb);')
        actual=module.evaluate_grid(field,batch_shape=(4,),inputs={'_c3':[.2,.4,.6,1]})
        np.testing.assert_allclose(actual,np.tile([.2,.4,.6],(4,1)),atol=1e-6)

    def test_nonfinite_selected_domain_and_invalid_input_shapes_remain_unresolved(self):
        module=importlib.import_module('grid_math')
        from field_math import UnresolvedMath
        _,field=test_field_math.lower('ret=float3(log(uv.x));')
        with self.assertRaises(UnresolvedMath):
            module.evaluate_grid(field,batch_shape=(2,),inputs={'_uv':[[1,0,0,0],[0,0,0,0]]})
        with self.assertRaises(UnresolvedMath):
            module.evaluate_grid(field,batch_shape=(2,),inputs={'_uv':np.zeros((2,3))})


if __name__=='__main__':unittest.main()


def test_grid_rand_follows_projectm_eval_range_and_draws_once_for_uniform_input():
    import numpy as np
    from grid_math import evaluate_grid
    from shader_fields import Field
    field = Field('rand', (Field('input', detail={'name': 'n'}, dtype='float'),), 'float')
    uniform = np.asarray(evaluate_grid(field, batch_shape=(4, 4), inputs={'n': np.float32(6.)}), np.float32)
    assert uniform.min() == uniform.max() and 0 <= uniform.min() < 6
    small = np.asarray(evaluate_grid(field, batch_shape=(64,), inputs={'n': np.float32(.3)}), np.float32)
    assert 0 <= small.min() and small.max() < 1


class IllustrationNumericPolicyTest(unittest.TestCase):
    def test_ieee_policy_pow_follows_the_measured_engine_exp2_log2_abs_rule(self):
        # Emulator and ruler (2026-10-14): pow(x,y) = exp2(y*log2(|x|)) with log2(0) = -127, so pow(0,0) = 1,
        # pow(0,.0075) = 2^-0.9525 and pow(-.5,.5) = .707; strict policies still refuse these domains (r104).
        from grid_math import evaluate_grid, UnresolvedMath
        from field_math import GLES_IEEE_ILLUSTRATION
        _,field=test_field_math.lower('float z=uv.x*0; ret=float3(pow(z,0.0), pow(z,0.0075), pow(z-0.5,0.5));')
        inputs={'_uv':[[.3,.3,0,0]]}
        with self.assertRaises(UnresolvedMath):
            evaluate_grid(field,batch_shape=(1,),inputs=inputs)
        out=np.asarray(evaluate_grid(field,batch_shape=(1,),inputs=inputs,numeric_policy=GLES_IEEE_ILLUSTRATION),np.float64)[0]
        self.assertAlmostEqual(out[0],1.,places=5)
        self.assertAlmostEqual(out[1],2**(-127*.0075),places=4)
        self.assertAlmostEqual(out[2],.5**.5,places=4)

    def test_ieee_policy_propagates_division_by_zero_and_addresses_nan_samples(self):
        from grid_math import evaluate_grid, UnresolvedMath
        from field_math import GLES_IEEE_ILLUSTRATION
        _,field=test_field_math.lower('float s=1/uv.x; float n=uv.y; n*=s; ret=float3(s, n, tex2D(sampler_main, float2(n,.5)).x);')
        inputs={'_uv':[[0.,0.,0.,0.],[.5,.5,0,0]]}
        seen=[]
        def sample(detail,coordinates):
            seen.append(coordinates.copy());return np.full((len(coordinates),4),.25,np.float32)
        with self.assertRaises(UnresolvedMath):
            evaluate_grid(field,batch_shape=(2,),inputs=inputs,sample=sample)
        out=evaluate_grid(field,batch_shape=(2,),inputs=inputs,sample=sample,numeric_policy=GLES_IEEE_ILLUSTRATION)
        self.assertTrue(np.isinf(out[0,0]) and np.isnan(out[0,1]))
        self.assertEqual(out[1,0],2.)
        # Compound *= is plain GLSL arithmetic (no mult0 zero guard): 0*inf is NaN. The NaN coordinate of
        # lane 0 is addressed like a clamped or wrapped edge, not refused.
        self.assertTrue(np.all(np.isfinite(seen[-1])))
