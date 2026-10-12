import json,tempfile,unittest
from pathlib import Path
import ruler_cache as rc

class ResolveTest(unittest.TestCase):
    def test_relative_inputs_are_absolute_before_the_renderer_changes_cwd(self):
        import os
        old=os.getcwd();d=Path(tempfile.mkdtemp()).resolve()
        try:
            os.chdir(d)
            sw,pr,out=rc.resolve_paths('sw','presets/x','out')
        finally:os.chdir(old)
        self.assertEqual((sw,pr,out),(d/'sw',d/'presets'/'x',d/'out'))
        self.assertTrue(all(p.is_absolute() for p in (sw,pr,out)))

class CacheTest(unittest.TestCase):
    base=dict(preset_sha256='p',pcm_sha256='a',binary_sha256='b',swiftshader='s',textures='t',config={'size':[480,270],'frames':300,'window':60,'version':1})
    def ident(self,**kw):return rc.run_identity(**{**self.base,**kw})
    def write(self,row):
        d=tempfile.mkdtemp();t=Path(d)/'x.json';t.write_text(json.dumps(row));return t
    def test_matching_identity_reuses(self):
        t=self.write({'status':'measured','identity':self.ident()})
        self.assertTrue(rc.can_reuse(t,self.ident()))
    def test_any_changed_input_rerenders(self):
        t=self.write({'status':'measured','identity':self.ident()})
        for kw in ({'preset_sha256':'q'},{'pcm_sha256':'z'},{'binary_sha256':'z'},{'swiftshader':'z'},{'textures':'z'},
                   {'config':{'size':[480,270],'frames':301,'window':60,'version':1}}):
            self.assertFalse(rc.can_reuse(t,self.ident(**kw)),kw)
    def test_result_without_identity_is_not_reused(self):
        t=self.write({'status':'measured','preset_sha256':'p'})
        self.assertFalse(rc.can_reuse(t,self.ident()))
    def test_missing_or_corrupt_file(self):
        self.assertFalse(rc.can_reuse(Path('/nonexistent/x.json'),self.ident()))
        d=Path(tempfile.mkdtemp())/'x.json';d.write_text('{')
        self.assertFalse(rc.can_reuse(d,self.ident()))
    def test_tree_identity_changes_with_texture_bytes_names_and_nesting(self):
        d=Path(tempfile.mkdtemp());(d/'sub').mkdir();(d/'a.png').write_bytes(b'1');(d/'sub'/'b.png').write_bytes(b'2')
        first=rc.tree_identity(d)
        self.assertEqual(first,rc.tree_identity(d))
        (d/'sub'/'b.png').write_bytes(b'3');self.assertNotEqual(first,rc.tree_identity(d))
        (d/'sub'/'b.png').write_bytes(b'2');(d/'a.png').rename(d/'c.png');self.assertNotEqual(first,rc.tree_identity(d))
if __name__=='__main__':unittest.main()
