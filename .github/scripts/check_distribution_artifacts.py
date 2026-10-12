"""Check the packaged distribution, using Android SDK tools for binary manifests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


def aapt2():
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or Path.home()/'Library/Android/sdk')
    tools = sorted((sdk/'build-tools').glob('*/aapt2'))
    if not tools: raise ValueError('Android SDK aapt2 is required')
    return str(tools[-1])


def sdk_dump(apk, kind):
    command = [aapt2(), 'dump', kind, str(apk)]
    if kind == 'xmltree': command += ['--file', 'AndroidManifest.xml']
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def check_apk(apk, distribution, target, version, version_code, require_qualified=False, badging=None, xml=None):
    if distribution not in ('github', 'fdroid') or target not in ('tv', 'android'): raise ValueError('invalid distribution/target')
    badging = sdk_dump(apk, 'badging') if badging is None else badging
    xml = sdk_dump(apk, 'xmltree') if xml is None else xml
    package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    expected = 'nl.neerdael.projectmtv' if target == 'tv' else 'nl.neerdael.projectm'
    if not package or package[1] != expected: raise ValueError('unexpected application package')
    if package[2] != str(version_code) or package[3] != version: raise ValueError('unexpected application version/code')
    if (target == 'tv') != ('leanback-launchable-activity:' in badging): raise ValueError('incorrect device launcher')
    if 'android.permission.RECORD_AUDIO' not in badging: raise ValueError('audio capture permission missing')
    if distribution == 'fdroid':
        if 'android.permission.REQUEST_INSTALL_PACKAGES' in badging: raise ValueError('F-Droid install permission is present')
        if 'UpdateFileProvider' in xml: raise ValueError('F-Droid update provider is present')
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        presets = [n for n in names if n.startswith('assets/presets/') and n.endswith('.milk')]
        textures = [n for n in names if n.startswith('assets/textures/') and not n.endswith('/')]
        count = 20 if distribution == 'fdroid' else 9606
        if len(presets) != count: raise ValueError(f'{distribution} must have {count} presets')
        if distribution == 'github' and len(textures) != 74: raise ValueError('GitHub full texture collection missing')
        if distribution == 'fdroid':
            selection = json.loads(archive.read('assets/starter-selection.json'))
            records = selection['presets']
            if require_qualified and selection.get('status') != 'qualified': raise ValueError('starter selection is not runtime qualified')
            if len(records) != 20 or len({r['name'] for r in records}) != 20: raise ValueError('invalid 20-preset selection')
            expected_names = {'assets/presets/' + r['name'] for r in records}
            if set(presets) != expected_names: raise ValueError('starter manifest differs from packaged presets')
            for r in records:
                if hashlib.sha256(archive.read('assets/presets/'+r['name'])).hexdigest() != r['sha256']:
                    raise ValueError('starter source hash mismatch')
            index = archive.read('assets/presets.idx').decode().splitlines()
            if {line.split('\t')[0] for line in index} != {r['name'] for r in records} or len(index) != 20:
                raise ValueError('stale starter preset index')
            for genre in ['chill', 'normal', 'intense']:
                rows = archive.read(f'assets/preset-genres/genres/{genre}.idx').decode().splitlines()
                if not {line.split('\t')[0] for line in rows} <= {r['name'] for r in records}:
                    raise ValueError('full collection leaked into starter mood index')
            for name in names:
                if name.endswith('.dex') and b'application/vnd.android.package-archive' in archive.read(name):
                    raise ValueError('F-Droid APK updater implementation is present')
    return {'package': expected, 'presets': len(presets), 'textures': len(textures), 'bytes': Path(apk).stat().st_size}


def check_core(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if sum(n.startswith('assets/presets/') and n.endswith('.milk') for n in names) != 9606:
            raise ValueError('canonical core AAR must contain the full preset collection')
        if sum(n.startswith('assets/textures/') and not n.endswith('/') for n in names) != 74:
            raise ValueError('canonical core AAR must contain the full texture collection')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apk', type=Path, required=True);p.add_argument('--distribution', choices=['github','fdroid'], required=True)
    p.add_argument('--target', choices=['tv','android'], required=True);p.add_argument('--version', required=True);p.add_argument('--version-code', type=int, required=True)
    p.add_argument('--core-aar', type=Path);p.add_argument('--require-qualified', action='store_true')
    a = p.parse_args()
    result = check_apk(a.apk,a.distribution,a.target,a.version,a.version_code,a.require_qualified)
    if a.core_aar: check_core(a.core_aar)
    print(json.dumps(result, sort_keys=True))


if __name__=='__main__': main()
