"""Publish complete release assets and dispatch Milkbeat without executing note text."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError(f"invalid release version: {value}")
    return tuple(map(int, match.groups()))


def github_api(endpoint, method="GET", payload=None, missing_ok=False):
    command = ["gh", "api", endpoint, "--method", method]
    if payload is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True)
    if result.returncode:
        if missing_ok and "(HTTP 404)" in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def run(command):
    subprocess.run(command, check=True)


def tag_commit(repo, tag, api):
    reference = api(f"repos/{repo}/git/ref/tags/{tag}")
    obj = reference["object"]
    while obj["type"] == "tag":
        obj = api(f"repos/{repo}/git/tags/{obj['sha']}")["object"]
    if obj["type"] != "commit":
        raise ValueError("release tag does not refer to a commit")
    return obj["sha"]


def publish(repo, version, sha, notes, assets_dir, api=github_api, command=run, with_touchscreen=False, with_fdroid=False):
    version_tuple(version)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("invalid repository or source commit")
    body = notes.read_text(encoding="utf-8")
    if not body.startswith(f"# ProjectM TV {version}\n"):
        raise ValueError("release notes do not match the built version")
    # The single Native core uses the canonical integration filenames.
    pairs = [(f"projectM-TV-{version}.apk", "projectM-TV.apk"),
             (f"projectM-TV-core-{version}.aar", "projectM-TV-core.aar")]
    historical_native_pair = (f"projectM-TV-core-native-{version}.aar", "projectM-TV-core-native.aar")
    mapping = f"projectM-TV-{version}-mapping.txt"
    if with_touchscreen:
        pairs.append((f"projectM-Android-{version}.apk", "projectM-Android.apk"))
    if with_fdroid:
        if not with_touchscreen:
            raise ValueError('F-Droid publication requires both device editions')
        for target in ('TV', 'Android'):
            pairs.append((f'projectM-{target}-FDroid-{version}.apk',f'projectM-{target}-FDroid.apk'))
    names = [name for pair in pairs for name in pair] + [mapping]
    if with_touchscreen:
        names.append(f"projectM-Android-{version}-mapping.txt")
    if with_fdroid:
        names.extend(f'projectM-{target}-FDroid-{version}-mapping.txt' for target in ('TV','Android'))
        archive_name=f'cream-of-the-crop-{version}.zip'
        names.extend([archive_name,'release-version.json'])
        metadata=json.loads((assets_dir/'release-version.json').read_text())
        if (metadata.get('schema_version')!=1 or metadata.get('version')!=version or
                metadata.get('tag')!=f'v{version}' or metadata.get('source_sha')!=sha or
                type(metadata.get('version_code')) is not int or not 1<=metadata['version_code']<=2100000000):
            raise ValueError('release metadata differs from built source/version')
        archive=assets_dir/archive_name
        archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
        for target in ('TV','Android'):
            with zipfile.ZipFile(assets_dir/f'projectM-{target}-FDroid-{version}.apk') as apk:
                descriptor=json.loads(apk.read('assets/official-pack.json'))
                selection=json.loads(apk.read('assets/starter-selection.json'))
            if selection.get('status')!='qualified':raise ValueError('starter selection must be runtime qualified')
            if (descriptor.get('collection_id')!=metadata.get('collection_id') or
                    descriptor.get('archive_sha256')!=archive_sha or descriptor.get('compressed_bytes')!=archive.stat().st_size):
                raise ValueError('official archive does not match the F-Droid APK descriptor')
    digests = {name: hashlib.sha256((assets_dir / name).read_bytes()).hexdigest() for name in names}
    for versioned, alias in pairs:
        if versioned in digests and alias in digests and digests[versioned] != digests[alias]:
            raise ValueError(f"latest asset alias differs from its versioned artifact: {alias}")
    tag = f"v{version}"
    existing = api(f"repos/{repo}/releases/tags/{tag}", missing_ok=True)
    if existing:
        actual_commit = existing.get("target_commitish") if existing.get("draft") else tag_commit(repo, tag, api)
        if actual_commit != sha:
            raise ValueError("existing release tag belongs to a different commit")
        if not existing.get("draft"):
            assets = {asset["name"]: asset for asset in existing.get("assets", [])}
            uploaded = set(assets)
            # Older releases may not expose digest metadata. When available, check remote
            # aliases too without replacing any published asset.
            for versioned, alias in [*pairs, historical_native_pair]:
                first = assets.get(versioned, {}).get("digest")
                second = assets.get(alias, {}).get("digest")
                if first and second and first != second:
                    raise ValueError(f"published asset alias differs from its versioned artifact: {alias}")
            required = set(names + ["checksums.txt"])
            if set(historical_native_pair) & uploaded:
                # Complete historical dual-policy releases are immutable too. A partial
                # retired pair must never be mistaken for a complete single-core release.
                required.update(historical_native_pair)
            if not required <= uploaded:
                raise ValueError("published release is incomplete; refusing to replace published artifacts")
            return {"url": existing["html_url"], "created": False}
        if set(historical_native_pair) & {asset["name"] for asset in existing.get("assets", [])}:
            raise ValueError("draft contains retired core-native assets; reconcile the draft before publishing the single-core schema")
    # Include versioned and stable aliases of the APK/core, plus the R8 mapping.
    checksums = assets_dir / "checksums.txt"
    checksums.write_text("".join(f"{digests[name]}  {name}\n" for name in names), encoding="utf-8")
    names.append(checksums.name)
    latest = api(f"repos/{repo}/releases/latest", missing_ok=True)
    make_latest = "true" if not latest or version_tuple(version) >= version_tuple(latest["tag_name"]) else "false"
    if not existing:
        existing = api(f"repos/{repo}/releases", "POST", {
            "tag_name": tag, "target_commitish": sha, "name": f"ProjectM TV {version}",
            "body": body, "draft": True, "prerelease": False, "make_latest": "false",
        })
    command(["gh", "release", "upload", tag, *[str(assets_dir / name) for name in names],
             "--repo", repo, "--clobber"])
    result = api(f"repos/{repo}/releases/{existing['id']}", "PATCH", {
        "draft": False, "body": body, "make_latest": make_latest,
    })
    return {"url": result["html_url"], "created": True}


def milkbeat_needs_update(core_version, release_body):
    versions = re.findall(r"github\.com/johnneerdael/ProjectM-TV/releases/tag/v(\d+\.\d+\.\d+)", release_body)
    return not versions or max(map(version_tuple, versions)) < version_tuple(core_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    publish_parser = subcommands.add_parser("publish")
    publish_parser.add_argument("--repo", required=True)
    publish_parser.add_argument("--version", required=True)
    publish_parser.add_argument("--sha", required=True)
    publish_parser.add_argument("--notes", type=Path, required=True)
    publish_parser.add_argument("--assets-dir", type=Path, required=True)
    publish_parser.add_argument("--output", type=Path)
    publish_parser.add_argument("--with-touchscreen", action="store_true",
                                help="Require both TV and touchscreen APKs and mappings")
    publish_parser.add_argument('--with-fdroid',action='store_true',help='Require four editions, collection and release metadata')
    manifest_parser=subcommands.add_parser('manifest')
    manifest_parser.add_argument('--version',required=True);manifest_parser.add_argument('--version-code',type=int,required=True)
    manifest_parser.add_argument('--sha',required=True);manifest_parser.add_argument('--collection-lock',type=Path,required=True)
    manifest_parser.add_argument('--output',type=Path,required=True)
    milkbeat_parser = subcommands.add_parser("milkbeat")
    milkbeat_parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.action == "publish":
        result = publish(args.repo, args.version, args.sha, args.notes, args.assets_dir, with_touchscreen=args.with_touchscreen,with_fdroid=args.with_fdroid)
        if args.output:
            with args.output.open("a", encoding="utf-8") as stream:
                stream.write(f"url={result['url']}\n")
        print(json.dumps(result))
    elif args.action=='manifest':
        stable=args.version.split('-ci.',1)[0];version_tuple(stable)
        if not re.fullmatch('[0-9a-f]{40}',args.sha) or not 1<=args.version_code<=2100000000:raise ValueError('Invalid release identity')
        lock=json.loads(args.collection_lock.read_text())
        result={'schema_version':1,'version':stable,'version_code':args.version_code,'tag':'v'+stable,'source_sha':args.sha,'collection_id':lock['collection_id']}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    else:
        version_tuple(args.version)
        if not os.environ.get("GH_TOKEN"):
            raise ValueError("MILKBEAT_TOKEN is missing; cannot update Milkbeat")
        latest = github_api("repos/johnneerdael/Milkbeat/releases/latest", missing_ok=True)
        if latest and not milkbeat_needs_update(args.version, latest.get("body") or ""):
            print(f"Milkbeat already uses core {args.version} or newer; no rebuild needed.")
            return
        github_api("repos/johnneerdael/Milkbeat/dispatches", "POST", {
            "event_type": "projectm-core-release", "client_payload": {"version": args.version},
        })
        print(f"Triggered Milkbeat rebuild for core {args.version}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"error: {error}")
