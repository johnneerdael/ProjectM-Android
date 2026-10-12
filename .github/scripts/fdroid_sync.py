"""Synchronize pending F-Droid submissions; never modify accepted build history."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import fdroid_metadata as recipes

UPSTREAM = 'fdroid/fdroiddata'
REPOSITORY = 'johnneerdael/ProjectM-Android'


def query(values):
    return urllib.parse.urlencode(values)


def fingerprint(app):
    canonical = recipes.parse(recipes.render(app), app.id)
    return hashlib.sha256(json.dumps(recipes.managed_fields(canonical), sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def read_file(api, project, appid, ref):
    path = urllib.parse.quote('metadata/' + appid + '.yml', safe='')
    record = api(f'projects/{project}/repository/files/{path}?' + query({'ref': ref}), missing_ok=True)
    if record is None:
        return None
    text = base64.b64decode(record['content'], validate=True).decode('utf-8')
    if len(text) > 256 * 1024:
        raise ValueError('Metadata exceeds expected size')
    return recipes.parse(text, appid)


def automation_checkpoint(comparison, head):
    # GitLab documents compare.commits as complete, even when its diff times out.
    # Follow first-parent ancestry instead of trusting API list ordering or dates.
    commits = comparison.get('commits')
    if not isinstance(commits, list):
        raise ValueError('Missing comparison commit history; preserve submission')
    nodes = {}
    for commit in commits:
        if (not isinstance(commit, dict) or
                not re.fullmatch('[0-9a-f]{40}', str(commit.get('id', ''))) or
                commit['id'] in nodes):
            raise ValueError('Invalid comparison commit history; preserve submission')
        nodes[commit['id']] = commit
    if head not in nodes:
        raise ValueError('Comparison does not contain the validated branch head')
    visited = set()
    while head in nodes:
        if head in visited:
            raise ValueError('Cyclic comparison commit history')
        visited.add(head)
        commit = nodes[head]
        message = commit.get('message', '')
        if not isinstance(message, str):
            raise ValueError('Invalid comparison commit message')
        if message.startswith('Sync ProjectM F-Droid '):
            return message
        parents = commit.get('parent_ids')
        if (not isinstance(parents, list) or
                any(not re.fullmatch('[0-9a-f]{40}', str(parent)) for parent in parents)):
            raise ValueError('Invalid comparison commit parents')
        head = parents[0] if parents else None
    return None


def tagged_release(sha):
    """Return the (version, code) that a release tag's gradle.properties declares, or None."""
    from publish_release import github_api
    from release_commit import declared_release
    properties = github_api(f'repos/{REPOSITORY}/contents/gradle.properties?ref={sha}')
    return declared_release(base64.b64decode(properties['content']).decode())


def checkpoint_identity(checkpoint):
    """Release identity of the last synchronization, from its message and tagged source."""
    match = re.match(r'Sync ProjectM F-Droid v(\d+\.\d+\.\d+) \(([0-9a-f]{40})\)\n', checkpoint)
    if not match:
        return None
    try:
        declared = tagged_release(match[2])
    except (KeyError, RuntimeError, TypeError, ValueError):
        return None
    if declared is None or declared[0] != match[1]:
        return None
    return {'schema_version': 1, 'version': match[1], 'version_code': declared[1],
            'tag': 'v' + match[1], 'source_sha': match[2], 'collection_id': '0' * 64}


def matches_generator(current, target, identity):
    """Adopt a maintainer edit (such as an applied review suggestion) only when the recipe
    equals this generator's output for the checkpointed release; edits to the release
    identity itself or to any other managed field are preserved."""
    if identity is None:
        return False
    try:
        return fingerprint(recipes.generate_metadata(identity, target, current)) == fingerprint(current)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return False


def synchronize(release, fork, api, publisher, latest):
    recipes.validate_release(release)
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', fork) or fork == UPSTREAM:
        raise ValueError('Invalid writable GitLab fork')
    if latest() != release:
        raise ValueError('Requested release is no longer the latest published release')
    project = api('projects/' + urllib.parse.quote(fork, safe=''))
    upstream = api('projects/' + urllib.parse.quote(UPSTREAM, safe=''))
    if (project.get('path_with_namespace') != fork or project.get('archived') or
            project.get('forked_from_project', {}).get('id') != upstream['id'] or
            upstream.get('path_with_namespace') != UPSTREAM):
        raise ValueError('GitLab fork does not belong to the expected upstream')
    pid, uid = project['id'], upstream['id']
    master = api(f'projects/{uid}/repository/branches/master')['commit']['id']
    if not re.fullmatch('[0-9a-f]{40}', master):
        raise ValueError('Invalid upstream master identity')
    results = []
    for target, (appid, flavor, _, title) in recipes.TARGETS.items():
        accepted = read_file(api, uid, appid, master)
        if accepted is not None:
            desired = recipes.generate_metadata(release, target)
            # Once accepted, F-Droid owns version history and subsequent automatic builds.
            for field in ('Repo', 'Binaries', 'AutoUpdateMode', 'UpdateCheckMode', 'UpdateCheckData', 'AllowedAPKSigningKeys'):
                if accepted.get(field) != desired.get(field):
                    raise ValueError(f'Accepted {appid} needs maintainer migration of {field}')
            if not accepted.Builds or accepted.Builds[-1].gradle != [flavor]:
                raise ValueError('Accepted listing uses another distribution flavor')
            results.append({'package': appid, 'state': 'accepted', 'version_code': accepted.CurrentVersionCode})
            continue
        branch_endpoint = f'projects/{pid}/repository/branches/{appid}'
        branch = api(branch_endpoint, missing_ok=True)
        head = branch['commit']['id'] if branch else None
        if head is not None and not re.fullmatch('[0-9a-f]{40}', head):
            raise ValueError('Invalid submission branch identity')
        current = read_file(api, pid, appid, head) if head else None
        mrs = api(f'projects/{uid}/merge_requests?' + query({'state': 'all', 'source_branch': appid, 'per_page': 100}))
        matches = [mr for mr in mrs if mr.get('source_project_id') == pid and mr.get('source_branch') == appid]
        if len(matches) > 1:
            raise ValueError('Multiple merge requests use the managed source branch')
        mr = matches[0] if matches else None
        if mr and mr.get('state') != 'opened':
            raise ValueError('Existing merge request is closed or merged; preserve maintainer decision')
        if mr and (mr.get('target_project_id') != uid or mr.get('target_branch') != 'master'):
            raise ValueError('Existing merge request targets an unexpected branch/project')
        previous_master = None
        if head:
            if current is None:
                raise ValueError('Existing branch has no managed metadata')
            compare = api(f'projects/{pid}/repository/compare?' + query(
                {'from': master, 'to': appid, 'from_project_id': uid}))
            if compare.get('compare_timeout') or not compare.get('diffs'):
                raise ValueError('Cannot establish branch ownership from upstream diff')
            for diff in compare['diffs']:
                if (diff.get('new_path') != 'metadata/' + appid + '.yml' or
                        diff.get('old_path') != 'metadata/' + appid + '.yml' or
                        diff.get('collapsed') or diff.get('too_large')):
                    raise ValueError('Submission branch contains unmanaged files or incomplete diff')
            checkpoint = automation_checkpoint(compare, head)
            if checkpoint:
                expected = re.search(r'^Managed-Metadata-SHA256: ([0-9a-f]{64})$', checkpoint, re.M)
                base = re.search(r'^Target-Master: ([0-9a-f]{40})$', checkpoint, re.M)
                if not expected or not base or (fingerprint(current) != expected[1] and not matches_generator(
                        current, target, checkpoint_identity(checkpoint))):
                    raise ValueError('Managed recipe fields have maintainer edits; refusing overwrite')
                previous_master = base[1]
            else:
                legacy = Path(__file__).parents[2] / 'tools/fdroid/metadata-legacy' / (appid + '.yml')
                if not legacy.exists() or fingerprint(current) != fingerprint(recipes.parse(legacy.read_text(), appid)):
                    raise ValueError('No verified automation baseline; preserve maintainer recipe')
        desired = recipes.generate_metadata(release, target, current)
        text = recipes.render(desired)
        # Recheck even for an unchanged run: a competing writer must not be silently accepted.
        refreshed = api(branch_endpoint, missing_ok=True)
        if (refreshed['commit']['id'] if refreshed else None) != head:
            raise ValueError('Submission branch head changed during validation')
        if current is None or fingerprint(desired) != fingerprint(current) or previous_master != master:
            if latest() != release:
                raise ValueError('A newer latest release appeared before synchronization')
            if api(f'projects/{uid}/repository/branches/master')['commit']['id'] != master:
                raise ValueError('Upstream master changed during synchronization; retry')
            message = (f"Sync ProjectM F-Droid {release['tag']} ({release['source_sha']})\n\n"
                       f'Managed-Metadata-SHA256: {fingerprint(desired)}\nTarget-Master: {master}\n')
            def before_write():
                # Repository preparation may take minutes. Revalidate immediately before push.
                if latest() != release:
                    raise ValueError('A newer latest release appeared during repository preparation')
                if api(f'projects/{uid}/repository/branches/master')['commit']['id'] != master:
                    raise ValueError('Upstream master changed during repository preparation; retry')
                if read_file(api, uid, appid, master) is not None:
                    raise ValueError('Listing was accepted during repository preparation; preserve history')
            publisher(fork, appid, head, master, 'metadata/' + appid + '.yml', text, message, before_write)
        if mr is None:
            if latest() != release:
                raise ValueError('A newer latest release appeared before merge request creation')
            mr = api(f'projects/{pid}/merge_requests', 'POST', {
                'source_branch': appid, 'target_branch': 'master', 'target_project_id': uid,
                'title': 'New app: ' + title, 'allow_collaboration': True,
                'remove_source_branch': True,
                'description': recipes.merge_request_description(target)})
        results.append({'package': appid, 'state': 'submission', 'merge_request': mr['iid'],
                        'version_code': release['version_code']})
    return results


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitLabAPI:
    def __init__(self, credential):
        if not credential or any(ord(char) < 33 or ord(char) > 126 for char in credential):
            raise ValueError('FDROID_GITLAB_TOKEN is missing or contains invalid characters')
        self.credential = credential
        self.opener = urllib.request.build_opener(NoRedirect())

    def __call__(self, endpoint, method='GET', payload=None, missing_ok=False):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request('https://gitlab.com/api/v4/' + endpoint, data=data, method=method,
                                         headers={'PRIVATE-TOKEN': self.credential, 'Accept': 'application/json',
                                                  'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ValueError('GitLab API response exceeds limit')
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            raise ValueError(f'GitLab {method} request returned HTTP {error.code}') from None
        except urllib.error.URLError:
            raise ValueError('Could not reach GitLab API') from None


class GitPublisher:
    """Replace only the verified metadata diff using an atomic expected-head push."""
    def __init__(self, credential):
        self.credential = credential
        self.workspace = tempfile.TemporaryDirectory(prefix='projectm-fdroid-sync-')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.workspace.cleanup()

    def __call__(self, fork, branch, expected_sha, master_sha, path, content, message, before_write=lambda: None):
        root = Path(self.workspace.name)
        askpass = root / 'askpass.sh'
        askpass.write_text('#!/bin/sh\ncase "$1" in\n*Username*) printf "%s\\n" oauth2;;\n*) printf "%s\\n" "$FDROID_GITLAB_TOKEN";;\nesac\n')
        askpass.chmod(0o700)
        env = dict(os.environ, GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT='0',
                   FDROID_GITLAB_TOKEN=self.credential, GIT_AUTHOR_NAME='ProjectM release automation',
                   GIT_AUTHOR_EMAIL='actions@users.noreply.github.com',
                   GIT_COMMITTER_NAME='ProjectM release automation', GIT_COMMITTER_EMAIL='actions@users.noreply.github.com')

        def git(*args, stdin=None):
            try:
                return subprocess.run(['git', *args], cwd=root, env=env, input=stdin,
                                      text=True, capture_output=True, check=True, timeout=300).stdout.strip()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                raise ValueError('GitLab repository operation failed; branch may have changed, retry after inspection') from None

        # Complete ancestry lets the push work even before a fork's object pool catches up.
        # Blob filtering avoids downloading historical app metadata contents.
        if not (root / 'repo.git').exists():
            git('clone', '--bare', '--filter=blob:none',
                'https://gitlab.com/' + UPSTREAM + '.git', 'repo.git')
            git('--git-dir=repo.git', 'config', 'credential.helper', '')
        if git('--git-dir=repo.git', 'rev-parse', 'refs/heads/master') != master_sha:
            raise ValueError('Upstream master advanced before repository preparation')
        git('--git-dir=repo.git', 'read-tree', master_sha)
        blob = git('--git-dir=repo.git', 'hash-object', '-w', '--stdin', stdin=content)
        git('--git-dir=repo.git', 'update-index', '--add', '--cacheinfo', '100644', blob, path)
        tree = git('--git-dir=repo.git', 'write-tree')
        commit = git('--git-dir=repo.git', 'commit-tree', tree, '-p', master_sha, stdin=message)
        lease = f'--force-with-lease=refs/heads/{branch}:{expected_sha or ""}'
        before_write()
        git('--git-dir=repo.git', 'push', lease, 'https://gitlab.com/' + fork + '.git',
            commit + ':refs/heads/' + branch)


def latest_release():
    from publish_release import github_api, tag_commit
    release = github_api(f'repos/{REPOSITORY}/releases/latest')
    tag = release.get('tag_name', '')
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Latest GitHub release is not a stable published version')
    version = tag[1:]
    required = {'release-version.json', 'checksums.txt', f'cream-of-the-crop-{version}.zip',
                f'projectM-TV-FDroid-{version}.apk', f'projectM-Android-FDroid-{version}.apk'}
    names = {asset['name'] for asset in release.get('assets', [])}
    if not required <= names:
        raise ValueError('Latest release lacks the complete F-Droid artifact set')
    url = recipes.REPO + '/releases/download/' + tag + '/release-version.json'
    with urllib.request.urlopen(url, timeout=30) as response:
        body = response.read(8193)
    if len(body) > 8192:
        raise ValueError('Published release metadata exceeds limit')
    metadata = recipes.validate_release(json.loads(body))
    if metadata['tag'] != tag or metadata['source_sha'] != tag_commit(REPOSITORY, tag, github_api):
        raise ValueError('Published version metadata differs from the immutable GitHub tag')
    asset = next(asset for asset in release['assets'] if asset['name'] == 'release-version.json')
    if asset.get('digest') and asset['digest'] != 'sha256:' + hashlib.sha256(body).hexdigest():
        raise ValueError('Published metadata checksum differs')
    # F-Droid's tag update check reads the version from the tagged gradle.properties.
    if tagged_release(metadata['source_sha']) != (metadata['version'], metadata['version_code']):
        raise ValueError('Release tag source does not declare the published version and code')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'sync'])
    parser.add_argument('--release-json', type=Path)
    parser.add_argument('--output', type=Path, default=Path('build/fdroid-metadata'))
    parser.add_argument('--fork', default='johnneerdael/fdroiddata')
    args = parser.parse_args()
    release = json.loads(args.release_json.read_text()) if args.release_json else latest_release()
    recipes.validate_release(release)
    if args.action == 'check':
        args.output.mkdir(parents=True, exist_ok=True)
        for target, (appid, _, _, _) in recipes.TARGETS.items():
            (args.output / (appid + '.yml')).write_text(recipes.render(recipes.generate_metadata(release, target)))
    else:
        credential = os.environ.get('FDROID_GITLAB_TOKEN', '')
        api = GitLabAPI(credential)
        with GitPublisher(credential) as publisher:
            print(json.dumps(synchronize(release, args.fork, api, publisher, latest_release), sort_keys=True))


if __name__ == '__main__':
    main()
