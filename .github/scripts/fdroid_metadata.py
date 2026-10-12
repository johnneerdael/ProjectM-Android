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
    # Each release tag's gradle.properties declares that release's version and code.
    app.AutoUpdateMode = 'Version'
    app.UpdateCheckMode = r'Tags ^v\d+\.\d+\.\d+$'
    # fdroidserver cannot resolve the conditional package/label in app/build.gradle;
    # retain each flavor's name. Packaged identities are verified in Android CI.
    app.UpdateCheckName = 'Ignore'
    app.UpdateCheckData = (r'gradle.properties|projectmReleaseVersionCode=(\d+)|'
                           r'gradle.properties|projectmReleaseVersion=(\d+\.\d+\.\d+)')
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
    # The tagged source declares its own version: no prebuild edits.
    build.prebuild = []
    build.ndk = '27.3.13750724'
    app.Builds = [build]
    return app


ABSTRACTS = {
    'tv': ('ProjectM TV is a music visualizer for Android TV. It renders audio-reactive MilkDrop presets '
           'for the music another app plays on the TV, controlled with the remote.',
           'images/tvScreenshots/1.jpg'),
    'android': ('ProjectM Android is a music visualizer for phones and tablets. It renders audio-reactive '
                'MilkDrop presets from the microphone or, on Android 10 and later, from playback in '
                'another app that permits capture, controlled with touch gestures.',
                'images/phoneScreenshots/1.png'),
}


def merge_request_description(target):
    """New-app merge request text following fdroiddata's 'App inclusion' template."""
    appid, flavor, _, title = TARGETS[target]
    summary, screenshot = ABSTRACTS[target]
    fastlane = f'src/{flavor}/fastlane/metadata/android/en-US'
    raw = REPO.replace('https://github.com/', 'https://raw.githubusercontent.com/') + '/main/' + fastlane
    return f'''## Abstract

### Please introduce the functions and usage of your app in summary, and also attach some screenshots.

{summary} This F-Droid edition bundles 20 starter presets; on first launch the user can choose to download the optional 9,606-preset *Cream of the Crop* collection (CC0) from this project's GitHub release, or continue offline. It has no built-in app updater: updates come from F-Droid.

![{title} screenshot]({raw}/{screenshot})

### Please elaborate why you wrote this app. Please highlight the unique functions it provides over other similar apps in F-Droid.

It runs ProjectM TV Engine, a maintained fork of [projectM](https://github.com/projectM-visualizer/projectm) (the open-source MilkDrop reimplementation) with compatibility and rendering fixes, so the large MilkDrop preset catalogue plays on Android devices.

- Source: {REPO} (I'm the author)
- License: LGPL-2.1-only for the code; presets and textures are CC0 1.0
- projectM and projectm-eval are git submodules and are built from source with the app.

## Checklist

### Policy

* [x] The app complies with the [inclusion criteria](https://f-droid.org/docs/Inclusion_Policy).
* [x] The original app author has been notified (and does not oppose the inclusion). I am the author.
* [x] The upstream app source code repo contains the app metadata in a Fastlane folder structure (`{fastlane}`: title, summary, description, changelogs, icon and screenshots).

### Docs

* [x] Please read [the guide](https://gitlab.com/fdroid/fdroiddata/-/blob/master/CONTRIBUTING.md) first if this is your first contribution.
* [x] Please make sure your metadata follows the best practice in [our templates](https://gitlab.com/fdroid/fdroiddata/tree/master/templates).
* [x] Please read the [Build Metadata Reference](https://f-droid.org/docs/Build_Metadata_Reference/) and make sure your metadata is valid.
* [x] Please read the [Quick Start Guide](https://f-droid.org/en/docs/Submitting_to_F-Droid_Quick_Start_Guide/).

### Merge Request Setup

* [x] The title of this merge request should follow "New app: app name" format.
* [x] Please make sure your fdroiddata fork is public and your branch is not protected.
* [x] Please read [our Git guide](https://gitlab.com/fdroid/wiki/-/wikis/Tips-for-fdroiddata-contributors/Git-Usage) if you don't know how to rebase your branch.
* [x] All related fdroiddata and RFP issues have been referenced in this merge request (there are none).
* [x] Please only submit one app in one MR.

### Metadata

* [x] Metadata must be put in `metadata/{appid}.yml`.
* [x] Metadata must be a valid YAML file.
* [x] Metadata must use LF as line ending.
* [x] Don't add summary/description/changelog/images or anything that should be provided in upstream repo.
* [x] Releases are tagged and auto update is enabled (`UpdateCheckMode: Tags`). Each release tag's `gradle.properties` declares that release's version name and code.
* [x] There is an issue tracker and contact info of the author (GitHub issues).
* [x] An AuthorName must be added.
* [x] External repos are added as git submodules instead of srclibs.
* [x] Enable Reproducible Builds: `Binaries` and `AllowedAPKSigningKeys` are set, and `fdroid build` verifies the matching signed upstream APK.
* [ ] Setup abi split if the APK is large and the splitted ones can be much smaller: not done, because the universal APK is about 2 MB.
* [x] Only the latest versions should be kept in the metadata before it's merged.
* [x] Don't add any disabled versions in the metadata.
* [x] The `commit` field should be the full hash.

### Pipeline

* [ ] All pipelines should pass.
* [ ] All warnings and errors in the Reports tab should be fixed or explained.

The author ticks the pipeline items once this merge request's pipeline has finished.
'''


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
