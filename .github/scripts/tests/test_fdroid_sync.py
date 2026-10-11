import base64
import importlib.util
import json
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
                    + ([{'new_path': 'unmanaged.yml', 'old_path': 'unmanaged.yml'}] if self.extra_file else [])}
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

    def publish(self, fork, branch, expected_sha, master_sha, path, content, message):
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

    def test_creates_one_phone_mr_and_repeat_has_no_writes(self):
        result = self.sync()
        self.assertEqual(len(result), 2)
        self.assertEqual(len(self.api.mrs), 2)
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
        self.api.files[appid] = self.api.files[appid].replace('UpdateCheckMode: HTTP', 'UpdateCheckMode: None')
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


if __name__ == '__main__':
    unittest.main()
