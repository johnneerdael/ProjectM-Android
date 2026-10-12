import base64
import importlib.util
import json
import re
from pathlib import Path
import sys
import unittest
import urllib.parse
import tempfile
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / 'fdroid_sync.py'
RELEASE = dict(schema_version=1, version='2.4.10', version_code=120, source_sha='a' * 40,
               tag='v2.4.10', collection_id='c' * 64)


class FakeGitLab:
    def __init__(self, module):
        self.module = module
        self.files = {}
        self.branches = {}
        self.messages = {}
        self.mrs = []
        self.writes = []
        self.accepted = {}
        self.master = 'd' * 40
        self.conflict = False
        self.extra_file = False
        self.error = False
        self.conflict_reads = 0

    def __call__(self, endpoint, method='GET', payload=None, missing_ok=False):
        if self.error:
            raise ValueError('GitLab HTTP 403')
        if endpoint == 'projects/johnneerdael%2Ffdroiddata':
            return {'id': 100, 'path_with_namespace': 'johnneerdael/fdroiddata', 'forked_from_project': {'id': 36528}}
        if endpoint == 'projects/fdroid%2Ffdroiddata':
            return {'id': 36528, 'path_with_namespace': 'fdroid/fdroiddata'}
        if endpoint.endswith('/repository/branches/master'):
            return {'commit': {'id': self.master}}
        if '/repository/branches/' in endpoint:
            name = endpoint.rsplit('/', 1)[1]
            sha = self.branches.get(name)
            if self.conflict and sha:
                self.conflict_reads += 1
                if self.conflict_reads > 1:
                    sha = 'f' * 40
            return {'commit': {'id': sha}} if sha else None
        if '/repository/files/' in endpoint:
            path = urllib.parse.unquote(endpoint.split('/repository/files/')[1].split('?')[0])
            appid = Path(path).stem
            content = self.accepted.get(appid) if endpoint.startswith('projects/36528/') else self.files.get(appid)
            return {'content': base64.b64encode(content.encode()).decode()} if content else None
        if '/repository/compare?' in endpoint:
            branch = urllib.parse.parse_qs(endpoint.split('?')[1])['to'][0]
            return {'diffs': [{'new_path': 'metadata/' + branch + '.yml', 'old_path': 'metadata/' + branch + '.yml'}]
                    + ([{'new_path': 'unmanaged.yml', 'old_path': 'unmanaged.yml'}] if self.extra_file else []),
                    'commits': [{'id': self.branches[branch], 'parent_ids': [self.master],
                                 'message': self.messages.get(branch, 'Legacy recipe')}]}
        if '/repository/commits?' in endpoint:
            branch = urllib.parse.parse_qs(endpoint.split('?')[1])['ref_name'][0]
            return [{'message': self.messages[branch]}] if branch in self.messages else []
        if '/merge_requests' in endpoint:
            if method == 'GET':
                return self.mrs
            self.writes.append((endpoint, method, payload))
            mr = dict(iid=50236 if payload['source_branch'].endswith('projectmtv') else 60000,
                      source_project_id=100, target_project_id=36528, target_branch='master',
                      source_branch=payload['source_branch'], state='opened', web_url='https://gitlab.com/example')
            self.mrs.append(mr)
            return mr
        raise AssertionError(endpoint)

    def publish(self, fork, branch, expected_sha, master_sha, path, content, message, before_write=lambda: None):
        before_write()
        self.writes.append(('push', branch, expected_sha, master_sha))
        if self.branches.get(branch) != expected_sha:
            raise ValueError('branch head conflict')
        self.files[branch] = content
        self.messages[branch] = message
        self.branches[branch] = 'e' * 40


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'F-Droid synchronization missing')
        spec = importlib.util.spec_from_file_location('fdroid_sync', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.api = FakeGitLab(self.module)

    def sync(self, release=RELEASE, latest=None):
        return self.module.synchronize(release, 'johnneerdael/fdroiddata', self.api,
                                       self.api.publish, latest or (lambda: RELEASE))

    def test_ownership_uses_compare_history_without_path_filtered_timeout(self):
        self.sync()
        original=self.api.__call__
        calls=[]
        def checked(endpoint,*args,**kwargs):
            calls.append(endpoint)
            if '/repository/commits?' in endpoint:raise TimeoutError('path history read operation timed out')
            if '/repository/compare?' in endpoint:
                branch=urllib.parse.parse_qs(endpoint.split('?')[1])['to'][0]
                result=original(endpoint,*args,**kwargs)
                result['commits']=[{'id':self.api.branches[branch],'parent_ids':[self.api.master],
                                    'message':self.api.messages[branch]}]
                return result
            return original(endpoint,*args,**kwargs)
        result=self.module.synchronize(RELEASE,'johnneerdael/fdroiddata',checked,self.api.publish,lambda:RELEASE)
        self.assertEqual(len(result),2)
        self.assertFalse(any('/repository/commits?' in url for url in calls))

    def test_checkpoint_follows_head_ancestry_not_list_order(self):
        older={'id':'a'*40,'parent_ids':['d'*40],'message':'Sync ProjectM F-Droid older'}
        newest={'id':'b'*40,'parent_ids':['a'*40],'message':'Sync ProjectM F-Droid newest'}
        maintainer={'id':'c'*40,'parent_ids':['b'*40],'message':'Preserve maintainer note'}
        for commits in ([older,newest,maintainer],[maintainer,older,newest]):
            self.assertEqual(self.module.automation_checkpoint({'commits':commits},'c'*40),newest['message'])
        for invalid in ({},{'commits':[]},{'commits':[dict(maintainer,parent_ids=['c'*40])]}):
            with self.assertRaises(ValueError):self.module.automation_checkpoint(invalid,'c'*40)

    def test_creates_one_phone_mr_and_repeat_has_no_writes(self):
        result = self.sync()
        self.assertEqual(len(result), 2)
        self.assertEqual(len(self.api.mrs), 2)
        created = [write[2] for write in self.api.writes
                   if len(write) == 3 and write[1] == 'POST' and write[0].endswith('/merge_requests')]
        self.assertTrue(created)
        for payload in created:
            self.assertIn('## Checklist', payload['description'])
            self.assertIn(f"metadata/{payload['source_branch']}.yml", payload['description'])
        self.api.writes.clear()
        self.sync()
        self.assertFalse(self.api.writes)

    def test_preserves_existing_tv_mr_and_refreshes_master(self):
        self.sync()
        self.api.master = 'b' * 40
        self.api.writes.clear()
        self.sync()
        self.assertEqual(len(self.api.mrs), 2)
        # In this fixture compare reports a changed base until publication.
        self.assertTrue(all(w[0] == 'push' for w in self.api.writes))

    def test_unmanaged_maintainer_fields_survive_but_managed_edits_stop(self):
        self.sync()
        appid = 'nl.neerdael.projectmtv'
        self.api.files[appid] += '\nMaintainerNotes: Keep this decision\n'
        newer = dict(RELEASE, version='2.4.11', tag='v2.4.11', version_code=121, source_sha='b' * 40)
        self.sync(newer, lambda: newer)
        self.assertIn('Keep this decision', self.api.files[appid])
        edited = re.sub(r'^UpdateCheckMode: .*$', 'UpdateCheckMode: None', self.api.files[appid], flags=re.M)
        self.assertNotEqual(edited, self.api.files[appid])
        self.api.files[appid] = edited
        self.api.writes.clear()
        with self.assertRaisesRegex(ValueError, 'maintainer'):
            self.sync(newer, lambda: newer)
        self.assertFalse(self.api.writes)

    def test_accepted_listing_keeps_build_history(self):
        self.sync()
        self.api.accepted.update(self.api.files)
        self.api.writes.clear()
        self.sync()
        self.assertFalse(self.api.writes)

    def test_other_files_and_branch_conflicts_are_rejected(self):
        for concern in ('extra_file', 'conflict'):
            with self.subTest(concern=concern):
                self.api = FakeGitLab(self.module)
                self.sync()
                self.api.writes.clear()
                setattr(self.api, concern, True)
                with self.assertRaises(ValueError):
                    self.sync()
                self.assertFalse(self.api.writes)

    def test_delayed_release_and_http_failure_do_not_write(self):
        newer = dict(RELEASE, version='2.4.11', tag='v2.4.11', version_code=121, source_sha='b' * 40)
        with self.assertRaisesRegex(ValueError, 'latest'):
            self.sync(latest=lambda: newer)
        self.assertFalse(self.api.writes)
        self.api.error = True
        with self.assertRaisesRegex(ValueError, '403'):
            self.sync()

    def test_existing_mr_must_target_upstream_master(self):
        self.sync()
        self.api.mrs[0]['target_branch'] = 'other'
        self.api.writes.clear()
        with self.assertRaisesRegex(ValueError, 'merge request'):
            self.sync()
        self.assertFalse(self.api.writes)

    def test_new_release_during_repository_preparation_cannot_push(self):
        current=[RELEASE]
        newer=dict(RELEASE,version='2.4.11',tag='v2.4.11',version_code=121,source_sha='b'*40)
        def prepare(*args):
            current[0]=newer
            self.api.publish(*args)
        with self.assertRaisesRegex(ValueError,'during repository preparation'):
            self.module.synchronize(RELEASE,'johnneerdael/fdroiddata',self.api,prepare,lambda:current[0])
        self.assertFalse(self.api.writes)

    def test_closed_submission_is_not_reopened_or_duplicated(self):
        self.sync()
        self.api.mrs[0]['state'] = 'closed'
        self.api.writes.clear()
        with self.assertRaisesRegex(ValueError, 'maintainer decision'):
            self.sync()
        self.assertFalse(self.api.writes)

    def test_native_git_publisher_uses_atomic_lease_and_current_master(self):
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream, fork = root / 'upstream', root / 'fork.git'
            real_run(['git', 'init', str(upstream)], check=True, capture_output=True)
            for args in [('config', 'user.name', 'Fixture'), ('config', 'user.email', 'fixture@example.org')]:
                real_run(['git', '-C', str(upstream), *args], check=True)
            (upstream / 'unmanaged.txt').write_text('preserve upstream file')
            real_run(['git', '-C', str(upstream), 'add', '.'], check=True)
            real_run(['git', '-C', str(upstream), 'commit', '-m', 'baseline'], check=True, capture_output=True)
            real_run(['git', '-C', str(upstream), 'branch', '-M', 'master'], check=True)
            real_run(['git', 'clone', '--bare', str(upstream), str(fork)], check=True, capture_output=True)
            master = real_run(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()

            def local_git(command, **kwargs):
                mapped = [str(upstream) if arg == 'https://gitlab.com/fdroid/fdroiddata.git' else
                          str(fork) if arg == 'https://gitlab.com/johnneerdael/fdroiddata.git' else arg for arg in command]
                return real_run(mapped, **kwargs)

            publisher = self.module.GitPublisher('fixture-token')
            self.addCleanup(publisher.workspace.cleanup)
            branch = 'nl.neerdael.projectm'
            with patch.object(self.module.subprocess, 'run', side_effect=local_git):
                publisher('johnneerdael/fdroiddata', branch, None, master, 'metadata/' + branch + '.yml', 'metadata fixture', 'Sync fixture')
                with self.assertRaisesRegex(ValueError, 'branch may have changed'):
                    publisher('johnneerdael/fdroiddata', branch, None, master, 'metadata/' + branch + '.yml', 'overwrite', 'Unexpected writer')
            head = real_run(['git', '--git-dir=' + str(fork), 'rev-parse', branch], check=True, capture_output=True, text=True).stdout.strip()
            parent = real_run(['git', '--git-dir=' + str(fork), 'rev-parse', head + '^'], check=True, capture_output=True, text=True).stdout.strip()
            self.assertEqual(parent, master)
            content = real_run(['git', '--git-dir=' + str(fork), 'show', branch + ':metadata/' + branch + '.yml'], check=True, capture_output=True, text=True).stdout
            self.assertEqual(content, 'metadata fixture')
            self.assertEqual(real_run(['git', '--git-dir=' + str(fork), 'show', branch + ':unmanaged.txt'], check=True, capture_output=True, text=True).stdout, 'preserve upstream file')

    def test_missing_or_malformed_credentials_fail_without_leaking(self):
        for token in ['', 'private\nsecret', 'secret with space']:
            with self.subTest(token=bool(token)), self.assertRaisesRegex(ValueError, 'missing or contains invalid'):
                self.module.GitLabAPI(token)


class LatestReleaseTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('fdroid_sync', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.metadata = dict(RELEASE, version='2.3.42', tag='v2.3.42', version_code=91)
        self.body = json.dumps(self.metadata).encode()

    def latest(self, properties):
        import publish_release
        names = ['release-version.json', 'checksums.txt', 'cream-of-the-crop-2.3.42.zip',
                 'projectM-TV-FDroid-2.3.42.apk', 'projectM-Android-FDroid-2.3.42.apk']
        responses = {
            'repos/johnneerdael/ProjectM-Android/releases/latest': {
                'tag_name': 'v2.3.42', 'assets': [{'name': name} for name in names]},
            'repos/johnneerdael/ProjectM-Android/git/ref/tags/v2.3.42': {
                'object': {'type': 'commit', 'sha': RELEASE['source_sha']}},
            f"repos/johnneerdael/ProjectM-Android/contents/gradle.properties?ref={RELEASE['source_sha']}": {
                'content': base64.b64encode(properties.encode()).decode()},
        }
        with patch.object(publish_release, 'github_api', side_effect=lambda endpoint, *a, **k: responses[endpoint]), \
                patch('urllib.request.urlopen', return_value=__import__('io').BytesIO(self.body)):
            return self.module.latest_release()

    def test_tagged_source_must_declare_the_published_version(self):
        declared = 'org.gradle.jvmargs=-Xmx2g\nprojectmReleaseVersion=2.3.42\nprojectmReleaseVersionCode=91\n'
        self.assertEqual(self.latest(declared), self.metadata)
        for properties in ['org.gradle.jvmargs=-Xmx2g\n', declared.replace('=91', '=90')]:
            with self.subTest(properties=properties), self.assertRaisesRegex(ValueError, 'does not declare'):
                self.latest(properties)


if __name__ == '__main__':
    unittest.main()
