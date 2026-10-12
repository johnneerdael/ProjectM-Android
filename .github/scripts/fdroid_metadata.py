"""Generate the two source-build recipes using the pinned F-Droid metadata API."""
import argparse
import copy
import io
import json
from pathlib import Path
import re

from fdroidserver import metadata

REPO = 'https://github.com/johnneerdael/ProjectM-Android'
SIGNING_KEY = 'ee51370f485325d703adbca4d811989d90e044da6181f7629965e6add03cfcef'
TARGETS = {'tv': ('nl.neerdael.projectmtv', 'fdroidTv', 'TV', 'ProjectM TV'),
           'android': ('nl.neerdael.projectm', 'fdroidAndroid', 'Android', 'ProjectM Android')}
MANAGED = ('AutoName', 'RepoType', 'Repo', 'Binaries', 'Builds', 'AllowedAPKSigningKeys',
           'AutoUpdateMode', 'UpdateCheckMode', 'UpdateCheckData', 'VercodeOperation',
           'UpdateCheckIgnore', 'UpdateCheckName', 'CurrentVersion', 'CurrentVersionCode')


def validate_release(release):
    if (release.get('schema_version') != 1 or
            not re.fullmatch(r'\d+\.\d+\.\d+', str(release.get('version', ''))) or
            type(release.get('version_code')) is not int or
            not 1 <= release['version_code'] <= 2100000000 or
            release.get('tag') != 'v' + release['version'] or
            not re.fullmatch(r'[0-9a-f]{40}', str(release.get('source_sha', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(release.get('collection_id', '')))):
        raise ValueError('Invalid published release identity')
    return release


def generate_metadata(release, target, existing=None):
    validate_release(release)
    if target not in TARGETS:
        raise ValueError('Unknown F-Droid target')
    appid, flavor, apk, title = TARGETS[target]
    app = copy.deepcopy(existing) if existing is not None else metadata.App()
    if app.get('id') and app.id != appid:
        raise ValueError('Metadata package identity differs')
    if app.get('CurrentVersionCode'):
        previous = int(app.CurrentVersionCode)
        if release['version_code'] < previous:
            raise ValueError('Refusing release rollback')
        if release['version_code'] == previous:
            builds = app.get('Builds', [])
            if (app.CurrentVersion != release['version'] or not builds or
                    builds[-1].commit not in (release['source_sha'], release['tag'])):
                raise ValueError('Same version code refers to another source')
    app.id = appid
    if existing is None:
        app.Categories = ['Multimedia']
        app.License = 'LGPL-2.1-only'
        app.AuthorName = 'John Neerdael'
        app.SourceCode = REPO
        app.IssueTracker = REPO + '/issues'
        app.Changelog = REPO + '/releases'
    app.AutoName = title
    app.RepoType = 'git'
    app.Repo = REPO + '.git'
    app.Binaries = REPO + f'/releases/download/v%v/projectM-{apk}-FDroid-%v.apk'
    app.AllowedAPKSigningKeys = [SIGNING_KEY]
    app.AutoUpdateMode = 'Version v%v'
    app.UpdateCheckMode = 'HTTP'
    # fdroidserver 2.4.5 cannot parse the conditional package/label in app/build.gradle.
    # HTTP discovery and APK identity checks are authoritative; retain each flavor's name.
    app.UpdateCheckName = 'Ignore'
    app.UpdateCheckData = (REPO + '/releases/latest/download/release-version.json|'
                           r'"version_code"\s*:\s*(\d+)|.|"version"\s*:\s*"(\d+\.\d+\.\d+)"')
    app.VercodeOperation = []
    app.UpdateCheckIgnore = None
    app.CurrentVersion = release['version']
    app.CurrentVersionCode = release['version_code']
    build = metadata.Build()
    build.versionName = release['version']
    build.versionCode = release['version_code']
    build.commit = release['source_sha']
    build.subdir = 'app'
    build.submodules = True
    # Historical research archives are neither app source nor runtime assets.
    build.rm = ['docs/superpowers/evidence']
    build.sudo = ["sdkmanager 'cmake;3.22.1'"]
    build.gradle = [flavor]
    build.gradleprops = ['projectmDistribution=fdroid', 'androidTouchscreen=' + str(target == 'android').lower()]
    # Runs in :app. F-Droid substitutes these constants for every auto-generated build.
    build.prebuild = ["sed -i.bak -e '/^projectmReleaseVersion=/d' -e '/^projectmReleaseVersionCode=/d' ../gradle.properties && "
                      "rm ../gradle.properties.bak && "
                      "printf '\\nprojectmReleaseVersion=$$VERSION$$\\nprojectmReleaseVersionCode=$$VERCODE$$\\n' >> ../gradle.properties"]
    build.ndk = '27.3.13750724'
    app.Builds = [build]
    return app


def parse(text, appid):
    stream = io.StringIO(text)
    stream.name = appid + '.yml'
    app = metadata.App()
    app.update(metadata.parse_yaml_metadata(stream))
    app.Builds = [metadata.Build(build) for build in app.get('Builds', [])]
    app.id = appid
    return app


def render(app):
    # The pinned writer drops unknown keys: stop rather than silently erase future fields.
    unsupported = set(app) - set(metadata.yaml_app_fields) - {'id', 'Provides', 'metadatapath', 'added', 'lastUpdated'}
    if unsupported:
        raise ValueError('Cannot serialize unsupported maintainer fields: ' + ', '.join(sorted(unsupported)))
    for build in app.Builds:
        unknown = set(build) - set(metadata.build_flags)
        if unknown:
            raise ValueError('Cannot serialize unsupported build fields: ' + ', '.join(sorted(unknown)))
    stream = io.StringIO()
    metadata.write_yaml(stream, copy.deepcopy(app))
    return stream.getvalue()


def managed_fields(app):
    return {key: app.get(key) for key in MANAGED}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    release = validate_release(json.loads(args.release_json.read_text()))
    args.output.mkdir(parents=True, exist_ok=True)
    for target, (appid, _, _, _) in TARGETS.items():
        (args.output / (appid + '.yml')).write_text(render(generate_metadata(release, target)))


if __name__ == '__main__':
    main()
