#!/usr/bin/env python3
"""Create and verify the tagged release source that declares its own version.

Each release tag points to a commit whose only parent is the main commit being
released and whose only change appends the release version and Android
versionCode to gradle.properties. The commit is deterministic: rebuilding it
from the same parent, version and code yields the same SHA, so the build and
publish jobs agree without sharing Git objects. It is pushed only as a tag,
never to a branch, so main's first-parent numbering is unaffected.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PROPERTIES = "gradle.properties"
VERSION_KEY = "projectmReleaseVersion"
CODE_KEY = "projectmReleaseVersionCode"
# Fixed identity and parent-derived date keep the commit SHA reproducible.
AUTHOR = ("ProjectM release", "41898282+github-actions[bot]@users.noreply.github.com")
VERSION_PATTERN = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
CODE_LIMIT = 2100000000
SHA_PATTERN = r"[0-9a-f]{40}"
KEY_LINE = re.compile(rf"^[ \t]*({VERSION_KEY}|{CODE_KEY})[ \t]*[=:\s]", re.MULTILINE)


def validate(version: str, code: int) -> None:
    if not re.fullmatch(VERSION_PATTERN, version):
        raise ValueError(f"Invalid release version: {version!r}; expected X.Y.Z")
    if type(code) is not int or not 1 <= code <= CODE_LIMIT:
        raise ValueError(f"Android versionCode must be an integer from 1 to {CODE_LIMIT}")


def release_properties(original: str, version: str, code: int) -> str:
    """Append the release identity; main itself must never declare one."""
    validate(version, code)
    if KEY_LINE.search(original):
        raise ValueError(f"{PROPERTIES} on main must not declare {VERSION_KEY} or {CODE_KEY}")
    base = original if not original or original.endswith("\n") else original + "\n"
    return (base + f"\n# Release identity of tag v{version}; written by the release workflow.\n"
            f"{VERSION_KEY}={version}\n{CODE_KEY}={code}\n")


def declared_release(text: str) -> tuple[str, int] | None:
    """Return the (version, code) a tagged gradle.properties declares, if any."""
    values = {}
    for key, value in re.findall(rf"^({VERSION_KEY}|{CODE_KEY})=(.*)$", text, re.MULTILINE):
        if key in values:
            raise ValueError(f"{PROPERTIES} declares {key} more than once")
        values[key] = value
    if not values:
        return None
    version, code = values.get(VERSION_KEY, ""), values.get(CODE_KEY, "")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", code):
        raise ValueError(f"{PROPERTIES} declares an invalid {CODE_KEY}")
    validate(version, int(code))
    return version, int(code)


def message(version: str, code: int, source: str) -> str:
    return f"Release v{version}\n\nVersion-Code: {code}\nSource-Commit: {source}\n"


def git(repo: Path, *args: str, stdin: str | None = None, env: dict | None = None, raw: bool = False) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True,
                            text=True, env={**os.environ, **(env or {})})
    if result.returncode:
        raise ValueError(f"Git command failed: {result.stderr.strip()}")
    return result.stdout if raw else result.stdout.strip()


def resolve(repo: Path, revision: str) -> str:
    return git(repo, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}")


def create(repo: Path, source: str, version: str, code: int) -> str:
    """Write the release commit object (no ref, no working-tree change) and return its SHA."""
    source = resolve(repo, source)
    entry = git(repo, "ls-tree", source, "--", PROPERTIES).split()
    if len(entry) != 4 or entry[:2] != ["100644", "blob"]:
        raise ValueError(f"{PROPERTIES} must be a regular file in the released source")
    text = release_properties(git(repo, "cat-file", "blob", entry[2], raw=True), version, code)
    blob = git(repo, "hash-object", "-w", "--stdin", stdin=text)
    with tempfile.TemporaryDirectory() as directory:
        index = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
        git(repo, "read-tree", source, env=index)
        git(repo, "update-index", "--add", "--cacheinfo", f"100644,{blob},{PROPERTIES}", env=index)
        tree = git(repo, "write-tree", env=index)
    date = git(repo, "show", "-s", "--format=%ct", source) + " +0000"
    identity = {"GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1], "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_NAME": AUTHOR[0], "GIT_COMMITTER_EMAIL": AUTHOR[1], "GIT_COMMITTER_DATE": date}
    return git(repo, "-c", "i18n.commitEncoding=UTF-8", "commit-tree", "--no-gpg-sign", tree,
               "-p", source, "-F", "-", stdin=message(version, code, source), env=identity)


def inspect(repo: Path, commit: str) -> dict | None:
    """Describe a release commit, None for an ordinary commit; reject malformed release commits."""
    commit = resolve(repo, commit)
    subject, _, body = git(repo, "show", "-s", "--format=%B", commit).partition("\n")
    match = re.fullmatch(rf"Release v({VERSION_PATTERN})", subject)
    if not match:
        return None
    parents = git(repo, "show", "-s", "--format=%P", commit).split()
    trailers = dict(re.findall(r"^(Version-Code|Source-Commit): (\S+)$", body, re.MULTILINE))
    version = match.group(1)
    if (len(parents) != 1 or trailers.get("Source-Commit") != parents[0] or
            not re.fullmatch(r"[1-9][0-9]{0,9}", trailers.get("Version-Code", ""))):
        raise ValueError(f"Release commit {commit} does not name its single source parent and code")
    code = int(trailers["Version-Code"])
    changed = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", parents[0], commit).splitlines()
    expected = release_properties(git(repo, "show", f"{parents[0]}:{PROPERTIES}", raw=True), version, code)
    if changed != [PROPERTIES] or git(repo, "show", f"{commit}:{PROPERTIES}", raw=True) != expected:
        raise ValueError(f"Release commit {commit} changes more than its declared release identity")
    return {"commit": commit, "source": parents[0], "version": version, "version_code": code}


def source_of(repo: Path, commit: str) -> str:
    """Map a tag target to the main commit it releases (older tags point at it directly)."""
    details = inspect(repo, commit)
    return details["source"] if details else resolve(repo, commit)


def remote_tag(repo: Path, remote: str, tag: str) -> str | None:
    """Return the commit an existing remote tag points to (peeling annotated tags)."""
    refs = {}
    for line in git(repo, "ls-remote", "--tags", remote).splitlines():
        sha, _, name = line.partition("\t")
        refs[name] = sha
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


def publish_tag(repo: Path, remote: str, source: str, version: str, code: int, expected: str) -> str:
    """Push the build's release commit as v<version>; an identical existing tag is reused."""
    commit = create(repo, source, version, code)
    if commit != expected:
        raise ValueError(f"Rebuilt release commit {commit} differs from the built source {expected}")
    tag = "v" + version
    existing = remote_tag(repo, remote, tag)
    if existing == commit:
        return "existing"
    if existing:
        raise ValueError(f"Tag {tag} already belongs to {existing}; refusing to move a release tag")
    git(repo, "push", "--quiet", remote, f"{commit}:refs/tags/{tag}")
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "tag"):
        command = commands.add_parser(name)
        command.add_argument("--repo", type=Path, default=Path("."))
        command.add_argument("--source", required=True)
        command.add_argument("--version", required=True)
        command.add_argument("--version-code", type=int, required=True)
    commands.choices["create"].add_argument("--checkout", action="store_true",
                                            help="Detach the working tree onto the release commit")
    commands.choices["create"].add_argument("--output", type=Path, help="Append GitHub Actions outputs")
    commands.choices["tag"].add_argument("--expected", required=True)
    commands.choices["tag"].add_argument("--remote", default="origin")
    args = parser.parse_args()
    try:
        if args.command == "create":
            source = resolve(args.repo, args.source)
            commit = create(args.repo, source, args.version, args.version_code)
            if args.checkout:
                git(args.repo, "checkout", "--quiet", "--detach", commit)
            if args.output:
                with args.output.open("a", encoding="utf-8") as stream:
                    stream.write(f"release_sha={commit}\nsource_sha={source}\n")
            print(commit)
        else:
            if not re.fullmatch(SHA_PATTERN, args.expected):
                raise ValueError("--expected must be a full commit SHA")
            state = publish_tag(args.repo, args.remote, args.source, args.version, args.version_code, args.expected)
            print(f"v{args.version} {state} at {args.expected}")
    except (ValueError, OSError) as error:
        print(f"release_commit: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
