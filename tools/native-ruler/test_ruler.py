import json,tempfile,unittest
from pathlib import Path
import ruler_cache as rc

class CacheTest(unittest.TestCase):
    base=dict(preset_sha256='p',pcm_sha256='a',binary_sha256='b',swiftshader='s',config={'size':[480,270],'frames':300,'window':60,'version':1})
    def ident(self,**kw):return rc.run_identity(**{**self.base,**kw})
    def write(self,row):
        d=tempfile.mkdtemp();t=Path(d)/'x.json';t.write_text(json.dumps(row));return t
    def test_matching_identity_reuses(self):
        t=self.write({'status':'measured','identity':self.ident()})
        self.assertTrue(rc.can_reuse(t,self.ident()))
    def test_any_changed_input_rerenders(self):
        t=self.write({'status':'measured','identity':self.ident()})
        for kw in ({'preset_sha256':'q'},{'pcm_sha256':'z'},{'binary_sha256':'z'},{'swiftshader':'z'},
                   {'config':{'size':[480,270],'frames':301,'window':60,'version':1}}):
            self.assertFalse(rc.can_reuse(t,self.ident(**kw)),kw)
    def test_result_without_identity_is_not_reused(self):
        t=self.write({'status':'measured','preset_sha256':'p'})
        self.assertFalse(rc.can_reuse(t,self.ident()))
    def test_missing_or_corrupt_file(self):
        self.assertFalse(rc.can_reuse(Path('/nonexistent/x.json'),self.ident()))
        d=Path(tempfile.mkdtemp())/'x.json';d.write_text('{')
        self.assertFalse(rc.can_reuse(d,self.ident()))
if __name__=='__main__':unittest.main()
