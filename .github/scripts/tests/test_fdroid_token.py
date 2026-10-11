import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'validate_fdroid_token.py'

class TokenTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(),'GitLab permission validator missing')
        spec=importlib.util.spec_from_file_location('token_check',SOURCE);self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.responses={
            'personal_access_tokens/self':{'scopes':['api'],'active':True,'revoked':False,'expires_at':None},
            'projects/johnneerdael%2Ffdroiddata':{'id':123,'path_with_namespace':'johnneerdael/fdroiddata','archived':False,'permissions':{'project_access':{'access_level':40}}},
            'projects/123/repository/branches/nl.neerdael.projectmtv':{'name':'nl.neerdael.projectmtv','can_push':True,'protected':False},
            'projects/fdroid%2Ffdroiddata/merge_requests/50236':{'source_project_id':123,'source_branch':'nl.neerdael.projectmtv','state':'opened'},
        }
    def validate(self):return self.module.validate('johnneerdael/fdroiddata',lambda endpoint:self.responses[endpoint])
    def test_active_api_token_can_update_existing_source_branch(self):self.assertTrue(self.validate()['branch_can_push'])
    def test_read_only_scope_rejected(self):
        self.responses['personal_access_tokens/self']['scopes']=['read_api']
        with self.assertRaisesRegex(ValueError,'api scope'):self.validate()
    def test_insufficient_fork_role_rejected(self):
        self.responses['projects/johnneerdael%2Ffdroiddata']['permissions']['project_access']['access_level']=20
        with self.assertRaisesRegex(ValueError,'Developer'):self.validate()
    def test_branch_permission_and_source_identity_checked(self):
        self.responses['projects/123/repository/branches/nl.neerdael.projectmtv']['can_push']=False
        with self.assertRaisesRegex(ValueError,'push'):self.validate()
    def test_revoked_token_rejected(self):
        self.responses['personal_access_tokens/self']['revoked']=True
        with self.assertRaisesRegex(ValueError,'inactive'):self.validate()
    def test_project_limited_token_requires_real_write_probe(self):
        self.assertTrue(hasattr(self.module,'AccessError'),'scoped token errors are not handled')
        def api(endpoint,*args,**kwargs):
            if endpoint=='personal_access_tokens/self':raise self.module.AccessError(403,endpoint)
            return self.responses[endpoint]
        with self.assertRaisesRegex(ValueError,'write probe'):self.module.validate('johnneerdael/fdroiddata',api)
    def test_scoped_token_probe_creates_and_removes_only_new_branch(self):
        self.assertTrue(hasattr(self.module,'AccessError'),'scoped token errors are not handled')
        calls=[]
        def api(endpoint,method='GET',payload=None):
            calls.append((endpoint,method,payload))
            if endpoint=='personal_access_tokens/self':raise self.module.AccessError(403,endpoint)
            if method=='POST':return {'name':payload['branch']}
            if method=='DELETE':return None
            return self.responses[endpoint]
        result=self.module.validate('johnneerdael/fdroiddata',api,'unique-run')
        self.assertTrue(result['repository_write_verified'])
        writes=[c for c in calls if c[1]!='GET']
        self.assertEqual([c[1] for c in writes],['POST','DELETE'])
        self.assertEqual(writes[0][2]['branch'],'codex-fdroid-permission-check-unique-run')
        self.assertTrue(writes[1][0].endswith('codex-fdroid-permission-check-unique-run'))

if __name__=='__main__':unittest.main()
