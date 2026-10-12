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

    def test_tagged_source_declares_update_identity(self):
        app = self.module.generate_metadata(self.release, 'tv')
        self.assertEqual(app.AutoUpdateMode, 'Version')
        self.assertEqual(app.UpdateCheckMode, r'Tags ^v\d+\.\d+\.\d+$')
        # fdroiddata review: '.' reuses the version-code file for the version name.
        self.assertEqual(app.UpdateCheckData, r'gradle.properties|projectmReleaseVersionCode=(\d+)|'
                                              r'.|projectmReleaseVersion=(\d+\.\d+\.\d+)')
        self.assertFalse(app.Builds[-1].prebuild)
        rendered = self.module.render(app)
        self.assertNotIn('prebuild', rendered)
        self.assertNotIn('VercodeOperation', rendered)

    def test_rendered_recipes_pass_rewritemeta_unchanged(self):
        # fdroiddata CI fails a merge request whose metadata rewritemeta would reformat.
        from fdroidserver import rewritemeta
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'metadata').mkdir()
            (root / 'config').mkdir()
            (root / 'config/categories.yml').write_text('Multimedia:\n  name: Multimedia\n')
            rendered = {}
            for target, (appid, _, _, _) in self.module.TARGETS.items():
                rendered[appid] = self.module.render(self.module.generate_metadata(self.release, target))
                (root / 'metadata' / (appid + '.yml')).write_text(rendered[appid])
            try:
                os.chdir(root)
                with patch.object(sys, 'argv', ['fdroid rewritemeta', *rendered]):
                    rewritemeta.main()
            finally:
                os.chdir(previous)
            for appid, text in rendered.items():
                self.assertEqual((root / 'metadata' / (appid + '.yml')).read_text(), text, appid)
                # Layout of fdroiddata's job (ruamel.yaml 0.18): long values start on the next line.
                self.assertIn('\nBinaries: \n  https://', text)

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

    def test_pinned_checkupdates_cli_reads_release_tags_and_auto_adds_both_builds(self):
        from fdroidserver import checkupdates
        sys.path.insert(0, str(SCRIPT.parent))
        from release_commit import create
        previous = Path.cwd()

        def run(*command, cwd):
            subprocess.run(command, cwd=cwd, check=True, capture_output=True)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Upstream: an older tag without a declared version, then a release-commit tag.
            source = root / 'source'
            source.mkdir()
            for command in [['git', 'init', '-q', '-b', 'main'], ['git', 'config', 'user.name', 'Upstream'],
                            ['git', 'config', 'user.email', 'upstream@example.org']]:
                run(*command, cwd=source)
            (source / 'gradle.properties').write_text('org.gradle.jvmargs=-Xmx2g\n')
            run('git', 'add', '.', cwd=source)
            run('git', 'commit', '-q', '-m', 'Older release', cwd=source)
            run('git', 'tag', 'v2.4.9', cwd=source)
            (source / 'README').write_text('next\n')
            run('git', 'add', '.', cwd=source)
            run('git', 'commit', '-q', '-m', 'Merge the next release', cwd=source)
            tagged = create(source, 'HEAD', '2.5.0', 130)
            run('git', 'tag', 'v2.5.0', tagged, cwd=source)
            fdroiddata = root / 'fdroiddata'
            (fdroiddata / 'metadata').mkdir(parents=True)
            (fdroiddata / 'config').mkdir()
            (fdroiddata / 'config/categories.yml').write_text('Multimedia:\n  name: Multimedia\n')
            for target, (appid, _, _, _) in self.module.TARGETS.items():
                app = self.module.generate_metadata(self.release, target)
                app.Repo = str(source)
                app.Builds[-1].submodules = False
                (fdroiddata / 'metadata' / (appid + '.yml')).write_text(self.module.render(app))
            for command in [['git', 'init', '-q'], ['git', 'config', 'user.name', 'F-Droid test'],
                            ['git', 'config', 'user.email', 'test@example.org'], ['git', 'add', '.'],
                            ['git', 'commit', '-q', '-m', 'Fixture baseline']]:
                run(*command, cwd=fdroiddata)
            try:
                os.chdir(fdroiddata)
                args = ['fdroid checkupdates', '--allow-dirty', '--auto', *[values[0] for values in self.module.TARGETS.values()]]
                with patch.object(sys, 'argv', args):
                    with self.assertRaises(SystemExit) as exited:
                        checkupdates.main()
                    self.assertEqual(exited.exception.code, 0)
                for target, (appid, flavor, _, _) in self.module.TARGETS.items():
                    app = self.module.parse((fdroiddata / 'metadata' / (appid + '.yml')).read_text(), appid)
                    self.assertEqual((app.CurrentVersion, app.CurrentVersionCode), ('2.5.0', 130))
                    # Auto-update records the release tag's full commit hash.
                    self.assertEqual(app.Builds[-1].commit, tagged)
                    self.assertEqual(app.Builds[-1].gradle, [flavor])
                    self.assertFalse(app.Builds[-1].get('prebuild'))
                    self.assertEqual(app.AutoName, self.module.TARGETS[target][3])
                    self.assertEqual(len(app.Builds), 2)
            finally:
                os.chdir(previous)

    def test_merge_request_description_follows_fdroiddata_inclusion_template(self):
        repository = SCRIPT.parents[2]
        for target, (appid, flavor, _, title) in self.module.TARGETS.items():
            with self.subTest(target=target):
                text = self.module.merge_request_description(target)
                for heading in ['## Abstract', '## Checklist', '### Policy', '### Docs', '### Merge Request Setup',
                                '### Metadata', '### Pipeline']:
                    self.assertIn('\n' + heading + '\n', '\n' + text)
                self.assertIn(f'`metadata/{appid}.yml`', text)
                self.assertIn('UpdateCheckMode: Tags', text)
                self.assertIn('* [ ] All pipelines should pass.', text)
                screenshot = text.split(f'![{title} screenshot](', 1)[1].split(')', 1)[0]
                local = screenshot.split('/main/', 1)[1]
                self.assertTrue((repository / local).is_file(), local)
                self.assertTrue(local.startswith(f'src/{flavor}/fastlane/'))

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
