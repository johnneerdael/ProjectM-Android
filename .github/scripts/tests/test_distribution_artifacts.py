import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SOURCE = Path(__file__).resolve().parents[1] / 'check_distribution_artifacts.py'


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'distribution artifact verifier is missing')
        spec=importlib.util.spec_from_file_location('distribution_check',SOURCE)
        self.check=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.check)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.apk=Path(self.temp.name)/'app.apk'
        self.badging="package: name='nl.neerdael.projectmtv' versionCode='88' versionName='2.3.39'\nleanback-launchable-activity: name='MainActivity'\nuses-permission: name='android.permission.RECORD_AUDIO'\n"
        self.xml='E: manifest\n'

    def make_apk(self,count=20,qualified=False,dex=b'no updater'):
        with zipfile.ZipFile(self.apk,'w') as z:
            records=[]
            for i in range(count):
                name=f'{i}.milk';data=str(i).encode();z.writestr('assets/presets/'+name,data)
                records.append({'name':name,'sha256':__import__('hashlib').sha256(data).hexdigest()})
            z.writestr('assets/starter-selection.json',json.dumps({'status':'qualified' if qualified else 'candidate','presets':records}))
            z.writestr('assets/presets.idx',''.join(f'{i}.milk\t0\n' for i in range(count)))
            for g in ['chill','normal','intense']: z.writestr(f'assets/preset-genres/genres/{g}.idx','0.milk\t0\n')
            z.writestr('classes.dex',dex)

    def verify(self,require=False):
        return self.check.check_apk(self.apk,'fdroid','tv','2.3.39',88,require,self.badging,self.xml)

    def test_twenty_starters_and_exact_identity(self):
        self.make_apk();self.assertEqual(self.verify()['presets'],20)
        self.badging=self.badging.replace('88','49')
        with self.assertRaisesRegex(ValueError,'version'): self.verify()

    def test_full_assets_cannot_leak_into_fdroid(self):
        self.make_apk(21)
        with self.assertRaisesRegex(ValueError,'20'): self.verify()

    def test_sideloaded_fdroid_cannot_include_install_permission(self):
        self.make_apk();self.badging+="uses-permission: name='android.permission.REQUEST_INSTALL_PACKAGES'\n"
        with self.assertRaisesRegex(ValueError,'permission'): self.verify()

    def test_updater_implementation_and_provider_are_rejected(self):
        self.make_apk(dex=b'application/vnd.android.package-archive')
        with self.assertRaisesRegex(ValueError,'updater'): self.verify()
        self.make_apk();self.xml+='com.example.projectm.visualizer.UpdateFileProvider'
        with self.assertRaisesRegex(ValueError,'provider'): self.verify()

    def test_release_requires_runtime_qualification(self):
        self.make_apk()
        with self.assertRaisesRegex(ValueError,'qualified'): self.verify(True)
        self.make_apk(qualified=True);self.verify(True)

    def test_phone_identity_and_launcher_are_checked(self):
        self.make_apk()
        with self.assertRaisesRegex(ValueError,'package'): self.check.check_apk(self.apk,'fdroid','android','2.3.39',88,False,self.badging,self.xml)


if __name__=='__main__': unittest.main()
