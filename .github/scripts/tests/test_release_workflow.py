"""Exercise the workflow's real packaging scripts with tagged Gradle output files."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


WORKFLOW = Path(__file__).resolve().parents[2] / "workflows/android-build.yml"


def packaging_scripts(release):
    text = WORKFLOW.read_text().split("\n  apk:\n", 1)[1]
    for match in re.finditer(r"^      - name: ([^\n]+)\n(.*?)(?=^      - |\Z)", text, re.M | re.S):
        name, block = match.groups()
        if not (name.startswith("Build release APK") or name == "Name APK" or "core AAR" in name or name in ("Build release APK for touchscreen Android", "Name Android APK", "Name F-Droid TV APK", "Name F-Droid Android APK")):
            continue
        run = re.search(r"^        run: (.+)$", block, re.M)
        if run is None:
            continue
        if run.group(1) == "|":
            body = block[run.end():].splitlines()
            script = "\n".join(line[10:] for line in body if line.startswith("          "))
        else:
            script = run.group(1)
        script = script.replace("${{ steps.version.outputs.release }}", "true" if release else "false")
        script = script.replace("${{ steps.version.outputs.version }}", "2.1.5")
        yield name, script


class TaggedReleaseSourceTests(unittest.TestCase):
    def test_artifacts_are_built_from_and_published_on_the_release_commit(self):
        build = WORKFLOW.read_text()
        version = build.index('      - name: Determine version\n')
        checkout = build.index('      - name: Check out the version-declaring release source\n')
        first_gradle = build.index('./gradlew')
        self.assertLess(version, checkout)
        self.assertLess(checkout, first_gradle)
        self.assertIn('release_commit.py create', build[checkout:first_gradle])
        self.assertIn('--checkout', build[checkout:first_gradle])
        self.assertIn('--sha "${{ steps.release_source.outputs.release_sha }}"', build)
        release = (WORKFLOW.parent / 'android.yml').read_text()
        tag = release.index('      - name: Tag the version-declaring release source\n')
        publish = release.index('      - name: Publish complete signed artifacts\n')
        self.assertLess(tag, publish)
        self.assertIn('release_commit.py tag', release[tag:publish])
        self.assertIn('--expected "$RELEASE_SHA"', release[tag:publish])
        self.assertIn('--sha "$RELEASE_SHA"', release[publish:])
        self.assertNotIn('--sha "$GITHUB_SHA" --notes', release)


class ArtifactPackagingTests(unittest.TestCase):
    def test_packaged_identity_checks_include_the_ci_version_suffix(self):
        block=WORKFLOW.read_text().split('      - name: Verify all packaged distributions and the staged full core\n',1)[1].split('\n      - uses:',1)[0]
        body=block.split('        run: |\n',1)[1]
        script='\n'.join(line[10:] for line in body.splitlines() if line.startswith('          '))
        for release,suffix in [('true',''),('false','-ci.42')]:
            with self.subTest(release=release),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);tool=root/'python3'
                tool.write_text(f'#!{sys.executable}\n'+'''import os,sys
assert sys.argv[sys.argv.index('--version')+1] == os.environ['BUILT_VERSION_NAME'],sys.argv
assert ('--require-qualified' in sys.argv) == (os.environ['RELEASE']=='true'),sys.argv
with open(os.environ['CHECK_CALLS'],'a') as out:out.write('checked\\n')
''');tool.chmod(0o755)
                env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],PROJECTM_RELEASE_VERSION='2.3.39',
                         PROJECTM_RELEASE_VERSION_CODE='88',VERSION_SUFFIX=suffix,BUILT_VERSION_NAME='2.3.39'+suffix,
                         RELEASE=release,TV_APK='tv.apk',ANDROID_APK='android.apk',FDROID_TV_APK='ftv.apk',
                         FDROID_ANDROID_APK='fandroid.apk',CORE_AAR='core.aar',CHECK_CALLS=str(root/'calls'))
                # Qualification is required only for the two F-Droid checks.
                tool.write_text(tool.read_text().replace("assert ('--require-qualified' in sys.argv) == (os.environ['RELEASE']=='true'),sys.argv", "assert ('--require-qualified' in sys.argv) == (os.environ['RELEASE']=='true' and sys.argv[sys.argv.index('--distribution')+1]=='fdroid'),sys.argv"))
                checked=subprocess.run(['bash','-eu','-c',script],cwd=root,env=env,capture_output=True,text=True)
                self.assertEqual(checked.returncode,0,checked.stderr)
                self.assertEqual((root/'calls').read_text().splitlines(),['checked']*4)

    def test_one_native_core_is_staged_under_canonical_name(self):
        for release in (True, False):
            with self.subTest(release=release), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "gradlew").write_text(f"#!{sys.executable}\n" + """
import sys
from pathlib import Path
policy = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('-PprojectmCoreRenderingPolicy=')), 'native')
fdroid = '-PprojectmDistribution=fdroid' in sys.argv
core = Path('core/build/outputs/aar/core-release.aar')
core.parent.mkdir(parents=True, exist_ok=True)
core.write_bytes((policy + (' starter engine' if fdroid else ' engine')).encode())
if any(a.endswith('assembleRelease') for a in sys.argv):
    apk = Path('app/build/outputs/apk/release/app-release.apk')
    apk.parent.mkdir(parents=True, exist_ok=True)
    touch = '-PandroidTouchscreen=true' in sys.argv
    apk.write_bytes((policy + (' touch apk' if touch else ' apk')).encode())
    mapping = Path('app/build/outputs/mapping/release/mapping.txt')
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text('touch mapping' if touch else 'native mapping')
if fdroid:
    touch = '-PandroidTouchscreen=true' in sys.argv
    flavor = 'fdroidAndroid' if touch else 'fdroidTv'
    apk = Path('app/build/outputs/apk') / flavor / 'release' / ('app-' + flavor + '-release.apk')
    apk.parent.mkdir(parents=True, exist_ok=True)
    apk.write_bytes((policy + (' touch fdroid apk' if touch else ' fdroid apk')).encode())
    mapping = Path('app/build/outputs/mapping') / (flavor + 'Release') / 'mapping.txt'
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text('fdroid touch mapping' if touch else 'fdroid tv mapping')
""")
                (root / "gradlew").chmod(0o755)
                fake_bin = root / "bin"
                fake_bin.mkdir()
                (fake_bin / "git").write_text("#!/bin/sh\nprintf '%s\\n' abc1234\n")
                (fake_bin / "git").chmod(0o755)
                env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ["PATH"],
                           GITHUB_OUTPUT=str(root / "outputs.txt"), GITHUB_RUN_NUMBER="42",
                           PROJECTM_SOURCE_SHA="a" * 40)
                for name, script in packaging_scripts(release):
                    subprocess.run(["bash", "-eu", "-c", script], cwd=root, env=env,
                                   check=True, capture_output=True, text=True)
                suffix = "" if release else "-ci.42-abc1234"
                core = root / f"dist-aar/projectM-TV-core-2.1.5{suffix}.aar"
                self.assertEqual(core.read_bytes(), b"native engine")
                self.assertEqual((root / f"dist/projectM-TV-2.1.5{suffix}.apk").read_bytes(), b"native apk")
                self.assertEqual((root / f"dist/projectM-Android-2.1.5{suffix}.apk").read_bytes(), b"native touch apk")
                self.assertEqual((root / f"dist-mapping/projectM-TV-2.1.5{suffix}-mapping.txt").read_text(), "native mapping")
                self.assertEqual((root / f"dist-mapping/projectM-Android-2.1.5{suffix}-mapping.txt").read_text(), "touch mapping")
                self.assertTrue((root / f"dist/projectM-TV-FDroid-2.1.5{suffix}.apk").exists(),'F-Droid edition missing from staging')
                self.assertEqual((root / f"dist/projectM-TV-FDroid-2.1.5{suffix}.apk").read_bytes(),b'native fdroid apk')
                self.assertEqual((root / f"dist/projectM-Android-FDroid-2.1.5{suffix}.apk").read_bytes(),b'native touch fdroid apk')
                self.assertEqual(len(list((root / "dist").glob("*.apk"))), 4)
                self.assertEqual(len(list((root / "dist-aar").glob("*.aar"))), 1)


class CoreBuildPolicyTests(unittest.TestCase):
    def test_cmake_rejects_retired_capped_policy_before_source_patching(self):
        # Exercise the entry guard only: never configure or mutate the shared submodule.
        source = WORKFLOW.parents[2] / "core/src/main/cpp/CMakeLists.txt"
        guard = source.read_text().split("find_library(", 1)[0].split("project(projectmtv)", 1)[1]
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "guard.cmake"
            script.write_text(guard)
            result = subprocess.run(["cmake", "-DPROJECTMTV_RENDERING_POLICY=capped", "-P", str(script)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("retired", result.stderr.lower())
            native = subprocess.run(["cmake", "-DPROJECTMTV_RENDERING_POLICY=native", "-P", str(script)],
                                    capture_output=True, text=True)
            self.assertEqual(native.returncode, 0, native.stderr)


if __name__ == "__main__":
    unittest.main()
