import importlib.util
import io
import json
from pathlib import Path
import subprocess
import shutil
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / 'fdroid_metadata.py'


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'F-Droid recipe generator missing')
        spec = importlib.util.spec_from_file_location('fdroid_metadata', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.release = dict(schema_version=1, version='2.4.10', version_code=120,
                            source_sha='a' * 40, tag='v2.4.10', collection_id='c' * 64)

    def test_two_recipe_identities_and_reproducible_binary_urls(self):
        for target, appid, flavor, apk in [('tv', 'nl.neerdael.projectmtv', 'fdroidTv', 'TV'),
                                          ('android', 'nl.neerdael.projectm', 'fdroidAndroid', 'Android')]:
            app = self.module.generate_metadata(self.release, target)
            self.assertEqual(app.id, appid)
            build = app.Builds[-1]
            self.assertEqual(build.gradle, [flavor])
            self.assertEqual(build.commit, 'a' * 40)
            self.assertEqual(build.rm, ['docs/superpowers/evidence'])
            self.assertIn('projectmDistribution=fdroid', build.gradleprops)
            self.assertIn('androidTouchscreen=' + str(target == 'android').lower(), build.gradleprops)
            self.assertTrue(app.Binaries.endswith(f'projectM-{apk}-FDroid-%v.apk'))
            self.assertTrue(app.AllowedAPKSigningKeys)
            rendered = self.module.render(app)
            self.assertNotIn('Summary:', rendered)
            self.assertNotIn('Description:', rendered)

    def test_fdroid_parser_round_trip_and_maintainer_fields(self):
        from fdroidserver import metadata
        app = self.module.generate_metadata(self.release, 'tv')
        app.MaintainerNotes = 'Keep this maintainer decision.'
        app.AuthorEmail = 'maintainer@example.org'
        updated = self.module.generate_metadata(self.release, 'tv', app)
        parsed = metadata.parse_yaml_metadata(io.StringIO(self.module.render(updated)))
        self.assertEqual(parsed['MaintainerNotes'], app.MaintainerNotes)
        self.assertEqual(parsed['AuthorEmail'], app.AuthorEmail)
        app['FutureMaintainerField'] = 'preserve by refusing unsupported serialization'
        updated = self.module.generate_metadata(self.release, 'tv', app)
        self.assertEqual(updated['FutureMaintainerField'], app['FutureMaintainerField'])
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            self.module.render(updated)

    def test_http_update_discovery_supports_new_release_lines(self):
        from fdroidserver import checkupdates
        app = self.module.generate_metadata(self.release, 'tv')
        self.assertEqual(app.UpdateCheckMode, 'HTTP')
        self.assertEqual(app.AutoUpdateMode, 'Version v%v')
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(self.release).encode())):
            self.assertEqual(checkupdates.check_http(app), ('2.4.10', 120))

    def test_real_importer_selects_platform_title_and_screenshots(self):
        from fdroidserver import update, common
        config = {}
        common.fill_config_defaults(config)
        repository = SCRIPT.parents[2]
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            apps = {}
            for target, (appid, _, _, _) in self.module.TARGETS.items():
                apps[appid] = self.module.generate_metadata(self.release, target)
                checkout = root / 'build' / appid
                checkout.mkdir(parents=True)
                shutil.copytree(repository / 'src', checkout / 'src')
                if (repository / 'fastlane').exists():
                    shutil.copytree(repository / 'fastlane', checkout / 'fastlane')
            try:
                os.chdir(root)
                with patch.object(update, 'config', config):
                    update.insert_localized_app_metadata(apps)
                self.assertEqual(apps['nl.neerdael.projectm']['localized']['en-US']['name'], 'ProjectM Android')
                self.assertEqual(apps['nl.neerdael.projectmtv']['localized']['en-US']['name'], 'ProjectM TV')
                self.assertTrue(list((root / 'repo/nl.neerdael.projectm/en-US/phoneScreenshots').glob('*.png')))
                self.assertFalse((root / 'repo/nl.neerdael.projectm/en-US/tvScreenshots').exists(), 'legacy TV screenshots leak into phone listing')
                self.assertTrue(list((root / 'repo/nl.neerdael.projectmtv/en-US/tvScreenshots').glob('*.jpg')))
            finally:
                os.chdir(previous)

    def test_pinned_checkupdates_cli_auto_adds_both_future_builds(self):
        from fdroidserver import checkupdates
        previous = Path.cwd()
        newer = dict(self.release, version='2.5.0', version_code=130, tag='v2.5.0')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'metadata').mkdir()
            (root / 'config').mkdir()
            (root / 'config/categories.yml').write_text('Multimedia:\n  name: Multimedia\n')
            for target, (appid, _, _, _) in self.module.TARGETS.items():
                (root / 'metadata' / (appid + '.yml')).write_text(self.module.render(self.module.generate_metadata(self.release, target)))
            for command in [['git', 'init'], ['git', 'config', 'user.name', 'F-Droid test'],
                            ['git', 'config', 'user.email', 'test@example.org'], ['git', 'add', '.'],
                            ['git', 'commit', '-m', 'Fixture baseline']]:
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            try:
                os.chdir(root)
                args = ['fdroid checkupdates', '--allow-dirty', '--auto', *[values[0] for values in self.module.TARGETS.values()]]
                with patch.object(sys, 'argv', args), patch('urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(json.dumps(newer).encode())):
                    with self.assertRaises(SystemExit) as exited:
                        checkupdates.main()
                    self.assertEqual(exited.exception.code, 0)
                for target, (appid, flavor, _, _) in self.module.TARGETS.items():
                    app = self.module.parse((root / 'metadata' / (appid + '.yml')).read_text(), appid)
                    self.assertEqual(app.CurrentVersionCode, 130)
                    self.assertEqual(app.Builds[-1].commit, 'v2.5.0')
                    self.assertEqual(app.Builds[-1].gradle, [flavor])
                    self.assertEqual(app.AutoName, self.module.TARGETS[target][3])
                    self.assertEqual(len(app.Builds), 2)
            finally:
                os.chdir(previous)

    def test_prebuild_applies_substitution_without_editing_version_baseline(self):
        app = self.module.generate_metadata(self.release, 'tv')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app').mkdir()
            properties = root / 'gradle.properties'
            properties.write_text('org.gradle.jvmargs=-Xmx2g\nprojectmReleaseVersion=old\nprojectmReleaseVersionCode=1\n')
            script = app.Builds[-1].prebuild[0].replace('$$VERSION$$', '2.4.10').replace('$$VERCODE$$', '120')
            subprocess.run(['bash', '-eu', '-c', script], cwd=root / 'app', check=True)
            self.assertEqual(properties.read_text().count('projectmReleaseVersion='), 1)
            self.assertIn('projectmReleaseVersionCode=120', properties.read_text())
            self.assertIn('org.gradle.jvmargs=-Xmx2g', properties.read_text())

    def test_invalid_identity_and_rollback_are_rejected(self):
        original = self.module.generate_metadata(self.release, 'tv')
        for field, value in [('source_sha', 'v2.4.10'), ('version', '2.4.10-ci.1'),
                             ('version_code', True), ('tag', 'v2.4.9'), ('collection_id', 'wrong')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.module.generate_metadata(dict(self.release, **{field: value}), 'tv')
        with self.assertRaisesRegex(ValueError, 'rollback'):
            self.module.generate_metadata(dict(self.release, version='2.4.9', tag='v2.4.9', version_code=119), 'tv', original)
        with self.assertRaisesRegex(ValueError, 'source'):
            self.module.generate_metadata(dict(self.release, source_sha='b' * 40), 'tv', original)


if __name__ == '__main__':
    unittest.main()
