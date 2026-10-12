#!/usr/bin/env python3
"""Allocate stable release versions from Gradle floors and first-parent history.

This reads history and emits build metadata; it never creates tags or releases.
Main release workflows must serialize allocation through publication.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Collection, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_commit import source_of  # noqa: E402


ANDROID_CODE_LIMIT = 2100000000
VERSION_PATTERN = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"


def parse_version(version: str) -> tuple[int, int, int]:
    """Accept only canonical three-part stable versions, safe for Actions files."""
    match = re.fullmatch(VERSION_PATTERN, version)
    if not match:
        raise ValueError(f"Invalid stable version: {version!r}; expected X.Y.Z")
    return tuple(int(part) for part in match.groups())


def validate_code(code: int) -> None:
    if type(code) is not int or not 1 <= code <= ANDROID_CODE_LIMIT:
        raise ValueError(f"Android versionCode must be an integer from 1 to {ANDROID_CODE_LIMIT}")


def literal_declaration(content: str, name: str, value_pattern: str) -> str:
    """Read one literal declaration, including a value on the following line."""
    declaration = rf"^[ \t]*def[ \t]+{name}[ \t]*="
    if len(re.findall(declaration, content, re.MULTILINE)) != 1:
        raise ValueError(f"Expected exactly one literal {name} declaration in app/build.gradle")
    match = re.search(
        declaration + rf"\s*({value_pattern})[ \t]*;?[ \t]*(?://[^\r\n]*)?$",
        content, re.MULTILINE,
    )
    if not match:
        raise ValueError(f"Expected a literal {name} value in app/build.gradle")
    return match.group(1)


def parse_base_versions(content: str) -> tuple[str, int]:
    version = literal_declaration(
        content, "baseVersionName", r'''(?P<quote>["'])[^"'\r\n]+(?P=quote)''',
    )[1:-1]
    code = int(literal_declaration(content, "baseVersionCode", r"[0-9]+"))
    parse_version(version)
    validate_code(code)
    return version, code


def parse_base_commit(content: str) -> str:
    return literal_declaration(
        content, "baseVersionCommit", r'''(?P<quote>["'])(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})(?P=quote)''',
    )[1:-1].lower()


def first_parent_ordinal(history: list[str], anchor: str) -> int:
    if anchor not in history:
        raise ValueError("baseVersionCommit must be in the source commit's first-parent history; "
                         "fetch complete history and check the configured anchor")
    ordinal = history.index(anchor)
    if ordinal < 1:
        raise ValueError("Source commit must follow baseVersionCommit on first-parent history")
    return ordinal


def stable_tags(tags: Mapping[str, str]) -> dict[str, tuple[int, int, int]]:
    return {name: parse_version(name[1:]) for name in tags
            if re.fullmatch("v" + VERSION_PATTERN, name)}


def code_for_version(base: str, base_code: int, version: str) -> int:
    base_parts = parse_version(base)
    parts = parse_version(version)
    validate_code(base_code)
    if parts[:2] != base_parts[:2] or parts[2] < base_parts[2]:
        raise ValueError(f"Version {version} is inconsistent with baseVersionName {base}")
    code = base_code + parts[2] - base_parts[2]
    validate_code(code)
    return code


def allocate_version(base: str, base_code: int, tags: Mapping[str, str], sha: str,
                     event: str, ref: str, run_number: int, ordinal: int | None = None,
                     ancestry: Collection[str] | None = None) -> dict:
    """Choose a candidate without changing Git; reuse an already tagged commit."""
    base_parts = parse_version(base)
    validate_code(base_code)
    if type(run_number) is not int or run_number < 1:
        raise ValueError("run-number must be a positive integer")
    if event not in {"push", "pull_request", "workflow_dispatch"}:
        raise ValueError(f"Unsupported event: {event!r}")
    if ordinal is not None and (type(ordinal) is not int or ordinal < 1):
        raise ValueError("First-parent ordinal must be a positive integer")
    versions = stable_tags(tags)
    latest = max(versions.values(), default=base_parts)
    current_tags = [tag for tag in versions if tags[tag] == sha]
    if len(current_tags) > 1:
        raise ValueError("Commit has multiple stable release tags; resolve the ambiguity before releasing")
    if not current_tags and base_parts[:2] < latest[:2]:
        raise ValueError("baseVersionName release line is older than the latest stable tag")
    if ordinal is not None:
        version = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2] + ordinal - 1}"
        tag = "v" + version
        if current_tags and current_tags[0] != tag:
            raise ValueError("Existing stable tag disagrees with baseVersionCommit's first-parent ordinal")
        if tag in tags and tags[tag] != sha:
            raise ValueError(f"Candidate tag {tag} already belongs to a different commit")
    elif current_tags:
        tag = current_tags[0]
        version = tag[1:]
    else:
        line_patches = [parts[2] for parts in versions.values() if parts[:2] == base_parts[:2]]
        patch = max(base_parts[2], max(line_patches, default=-1) + 1)
        version = f"{base_parts[0]}.{base_parts[1]}.{patch}"
        tag = "v" + version
    code = code_for_version(base, base_code, version)
    previous_tags = [name for name, parts in versions.items()
                     if parts < parse_version(version) and tags[name] != sha
                     and (ancestry is None or tags[name] in ancestry)]
    previous = max(previous_tags, key=versions.get, default="")
    release = ref == "refs/heads/main" and event in {"push", "workflow_dispatch"}
    return {"version": version, "version_code": code, "tag": tag,
            "release": release, "previous_tag": previous,
            "suffix": "" if release else f"-ci.{run_number}",
            "reused_tag": bool(current_tags), "ordinal": ordinal}


def version_code_at_tag(content: str, tag: str) -> int:
    """Resolve historical Android codes from new floors or legacy constants."""
    version = tag[1:]
    parse_version(version)
    if re.search(r"^[ \t]*def[ \t]+baseVersion(?:Name|Code)[ \t]*=", content, re.MULTILINE):
        base, base_code = parse_base_versions(content)
        return code_for_version(base, base_code, version)
    names = re.findall(r'''^[ \t]*versionName[ \t]+["']([^"'\r\n]+)["']''',
                       content, re.MULTILINE)
    codes = re.findall(r"^[ \t]*versionCode[ \t]+([0-9]+)[ \t]*;?[ \t]*(?://[^\r\n]*)?$",
                       content, re.MULTILINE)
    if len(names) != 1 or names[0] != version or len(codes) != 1:
        raise ValueError("Cannot resolve matching legacy versionName/versionCode constants")
    code = int(codes[0])
    validate_code(code)
    return code


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f"Git command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def historical_code(repo: Path, tag: str) -> int:
    try:
        content = git(repo, "show", f"refs/tags/{tag}:app/build.gradle")
        return version_code_at_tag(content, tag)
    except ValueError as error:
        raise ValueError(f"Cannot verify Android versionCode for {tag}: {error}. "
                         "Fetch complete tag history and check that tag's app/build.gradle.") from error


def resolve_version(repo: Path, sha: str, event: str, ref: str, run_number: int) -> dict:
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", sha + "^{commit}")
    names = git(repo, "for-each-ref", "--format=%(refname:strip=2)", "refs/tags").splitlines()
    # Release tags point at a version-declaring commit on top of the main commit they release.
    tags = {name: source_of(repo, git(repo, "rev-parse", "--verify", f"refs/tags/{name}^{{commit}}"))
            for name in names if re.fullmatch("v" + VERSION_PATTERN, name)}
    content = (repo / "app/build.gradle").read_text(encoding="utf-8")
    base, base_code = parse_base_versions(content)
    anchor = parse_base_commit(content)
    history = git(repo, "rev-list", "--first-parent", commit).splitlines()
    publishing = ref == "refs/heads/main" and event in {"push", "workflow_dispatch"}
    if publishing:
        ordinal = first_parent_ordinal(history, anchor)
    else:
        # Feature fixups must not advance Android codes ahead of the eventual
        # main merge, and older branches can lack the baseline on first parent.
        ordinal = None
    metadata = allocate_version(base, base_code, tags, commit, event, ref, run_number,
                                ordinal=ordinal, ancestry=set(history))
    versions = stable_tags(tags)
    if metadata["reused_tag"]:
        recorded_code = historical_code(repo, metadata["tag"])
        if metadata["version_code"] != recorded_code:
            raise ValueError("Computed versionCode differs from the existing tag; restore consistent base floors")
    previous = metadata["previous_tag"]
    if previous:
        previous_code = historical_code(repo, previous)
        if metadata["version_code"] <= previous_code:
            raise ValueError(f"Candidate versionCode {metadata['version_code']} must exceed "
                             f"{previous}'s versionCode {previous_code}; raise baseVersionCode")
    future_tags = [name for name, parts in versions.items() if parts > parse_version(metadata["version"])]
    if future_tags:
        latest_tag = max(future_tags, key=versions.get)
        latest_code = historical_code(repo, latest_tag)
        if versions[latest_tag][:2] == parse_version(base)[:2]:
            expected_code = code_for_version(base, base_code, latest_tag[1:])
            if latest_code != expected_code:
                raise ValueError(f"Future tag {latest_tag}'s versionCode disagrees with configured base floors")
        elif latest_code <= metadata["version_code"]:
            raise ValueError(f"Later release {latest_tag} must have a higher Android versionCode")
    if ordinal is None and versions and not metadata["reused_tag"]:
        latest_tag = max(versions, key=versions.get)
        latest_code = historical_code(repo, latest_tag)
        if metadata["version_code"] <= latest_code:
            raise ValueError(f"CI candidate versionCode {metadata['version_code']} must exceed "
                             f"{latest_tag}'s versionCode {latest_code}; raise baseVersionCode")
    return metadata


def write_actions_files(metadata: dict, output: Path, env: Path) -> None:
    outputs = {key: metadata[key] for key in
               ("version", "version_code", "tag", "release", "previous_tag")}
    outputs["release"] = str(outputs["release"]).lower()
    environment = {"PROJECTM_RELEASE_VERSION": metadata["version"],
                   "PROJECTM_RELEASE_VERSION_CODE": metadata["version_code"],
                   "VERSION_SUFFIX": metadata["suffix"]}
    for path, values in [(output, outputs), (env, environment)]:
        with path.open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--sha", required=True)
    parser.add_argument("--event", choices=("push", "pull_request", "workflow_dispatch"), required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    args = parser.parse_args()
    try:
        metadata = resolve_version(args.repo, args.sha, args.event, args.ref, args.run_number)
        write_actions_files(metadata, args.output, args.env)
    except (ValueError, OSError) as error:
        print(f"release_version: {error}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
