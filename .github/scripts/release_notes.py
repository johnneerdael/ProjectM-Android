#!/usr/bin/env python3
"""Validate PR release notes and assemble source-grounded GitHub release bodies."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str


PullRequest = dict[str, object]
PullLookup = Callable[[str], list[PullRequest]]


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?(?:-->|\Z)", "", text, flags=re.DOTALL)


def markdown_lines(text: str) -> list[tuple[str, int, str]]:
    """Return lines with ATX heading metadata, ignoring headings in fenced code."""
    result = []
    fence = ""
    for line in strip_comments(text).splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            result.append((line, 0, ""))
            continue
        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line) if not fence else None
        result.append((line, len(heading.group(1)) if heading else 0,
                       heading.group(2).strip("*_ ") if heading else ""))
    return result


def release_section(body: str) -> str | None:
    lines = markdown_lines(body)
    start = next((index for index, (_, depth, title) in enumerate(lines)
                  if depth and re.fullmatch(r"release[ -]+notes\s*:?", title, re.IGNORECASE)), None)
    if start is None:
        return None
    level = lines[start][1]
    end = next((index for index in range(start + 1, len(lines))
                if lines[index][1] and lines[index][1] <= level), len(lines))
    return "\n".join(line for line, _, _ in lines[start + 1:end]).strip()


def plain_content(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*+] |\d+[.)] )", "", line)
    line = re.sub(r"^\[[ xX]\]\s*", "", line)
    line = line.replace("**", "").replace("__", "")
    return line.strip(" \t*_`[]:.!-").casefold()


def is_vague(content: str) -> bool:
    return bool(re.fullmatch(
        r"(?:no user[ -]visible changes?|no changes?|none|n/?a|not applicable|"
        r"maintenance|internal changes?|updates?|bug fixes?|miscellaneous(?: changes)?|"
        r"todo|tbd|coming soon)", content))


def validate_release_notes(body: str) -> str:
    section = release_section(body)
    if section is None:
        raise ValueError("PR body must include a ## Release notes section.")
    content = []
    internal = []
    in_internal = False
    internal_level = 0
    for line, depth, title in markdown_lines(section):
        if re.search(r"\b(?:TODO|TBD)\b", line, re.IGNORECASE):
            raise ValueError("Release notes must replace TODO/TBD placeholders with actual changes.")
        if re.search(r"(?:\[|<)\s*(?:describe|explain|insert|add|replace|write)\b", line, re.IGNORECASE):
            raise ValueError("Release notes must replace template placeholders with actual changes.")
        if depth:
            if internal_level and depth <= internal_level:
                in_internal = False
                internal_level = 0
            if re.match(r"internal\b", title, re.IGNORECASE):
                in_internal = True
                internal_level = depth
            continue
        value = plain_content(line)
        if not value or re.fullmatch(r"[-*+\s]+", value):
            continue
        label = re.match(r"internal(?: changes?)?\s*:\s*(.*)", value)
        if label:
            in_internal = True
            value = label.group(1).strip()
        if re.fullmatch(r"n/?a|not applicable", value):
            raise ValueError("Release notes must replace N/A placeholders with actual changes.")
        if value:
            content.append(value)
            if in_internal:
                internal.append(value)
    if not content or all(is_vague(value) for value in content):
        raise ValueError("Release notes must describe a concrete change, including internal changes when applicable.")
    if any(re.fullmatch(r"no user[ -]visible changes?", value) for value in content):
        if not any(not is_vague(value) for value in internal):
            raise ValueError("No user-visible changes requires an Internal explanation of the actual change.")
    return section


def historical_description(body: str) -> str:
    """Keep historical change descriptions, excluding review-only sections."""
    kept = []
    skipped_level = 0
    skipped_label = False
    review_section = re.compile(r"\b(?:validation|tests?|testing|checklist|test\s*plan|screenshots?|review|verification|not changed)\b", re.IGNORECASE)
    for line, depth, title in markdown_lines(body):
        if re.search(r"(?:generated (?:with|by)|co-authored-by:|\b(?:claude|codex) (?:code|agent)\b)", line, re.IGNORECASE):
            break
        if re.search(r"!\[|<img\b|img\.shields\.io/", line, re.IGNORECASE):
            continue
        if depth:
            if skipped_level and depth > skipped_level:
                continue
            skipped_level = 0
            skipped_label = False
            if review_section.search(title):
                skipped_level = depth
                continue
            if title.casefold() in {"summary", "description", "changes", "what changed"}:
                continue
        if skipped_level:
            continue
        label_text = line.strip().replace("**", "").replace("__", "")
        label = re.fullmatch(r"([A-Za-z][A-Za-z /-]{0,60}):\s*(.*)", label_text)
        if label:
            skipped_label = bool(review_section.search(label.group(1)))
        if skipped_label:
            continue
        if re.match(r"\s*[-*+]\s+\[[ xX]\]", line) or re.match(r"\s*(?:---+|___+|\*\*\*+)\s*$", line):
            continue
        kept.append(line)
    result = "\n".join(kept).strip()
    return result if any(not is_vague(plain_content(line)) for line in kept if plain_content(line)) else ""


def nested_markdown(text: str) -> str:
    lines = markdown_lines(text)
    levels = [depth for _, depth, _ in lines if depth]
    offset = 4 - min(levels) if levels else 0
    return "\n".join(re.sub(r"^(\s{0,3})#{1,6}", lambda match: match.group(1) + "#" * min(6, depth + offset), line)
                     if depth else line for line, depth, _ in lines)


def downloader_code(readme: str) -> str:
    match = re.search(r"^>\s*\*\*Install on your TV with the Downloader app:\s*code\s+`(\d+)`\*\*\s*$", readme, re.MULTILINE)
    if not match:
        raise ValueError("README.md must contain the canonical Downloader install blockquote and code.")
    return match.group(1)


def android_downloader_code(readme: str, required: bool = False) -> str | None:
    # Historical README revisions contain only the TV code; keep their footer usable.
    match = re.search(r"^>\s*\*\*Install on your phone or tablet with the Downloader app:\s*code\s+`(\d+)`\*\*\s*$", readme, re.MULTILINE)
    if match:
        return match.group(1)
    if required or "Install on your phone or tablet with the Downloader app" in readme:
        raise ValueError("README.md must contain a valid canonical Android Downloader blockquote and code.")
    return None


def install_footer(repo: str, version: str, previous_tag: str | None, readme: str, *, with_fdroid: bool = False) -> str:
    base = f"https://github.com/{repo}"
    release = f"{base}/releases/download/v{version}"
    latest = f"{base}/releases/latest/download"
    changelog = f"{base}/compare/{previous_tag}...v{version}" if previous_tag else f"{base}/commits/v{version}"
    # v2.3.37 shipped before the Android Downloader code was added to the README.
    # Later releases must not silently lose the phone install instructions.
    android_code = android_downloader_code(readme, required=tuple(map(int, version.split("."))) >= (2, 3, 38))
    phone_install = (
        f"\n\nInstall on your phone or tablet with the Downloader app: code `{android_code}`. "
        "Get [Downloader by AFTVnews from Google Play]"
        "(https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en). "
        "This code downloads the newest stable touchscreen APK."
    ) if android_code else ""
    fdroid_downloads = (
        f"\n- F-Droid editions: [TV APK]({release}/projectM-TV-FDroid-{version}.apk) · "
        f"[Phone/tablet APK]({release}/projectM-Android-FDroid-{version}.apk)\n"
        f"- Latest F-Droid editions: [TV APK]({latest}/projectM-TV-FDroid.apk) · "
        f"[Phone/tablet APK]({latest}/projectM-Android-FDroid.apk)\n"
        f"- [Optional Cream of the Crop collection]({release}/cream-of-the-crop-{version}.zip)"
    ) if with_fdroid else ""
    return f"""## Install and downloads

Install on your TV with the Downloader app: code `{downloader_code(readme)}`. The code downloads the newest stable TV APK.{phone_install}

- Latest: [Android TV APK]({latest}/projectM-TV.apk) · [Touchscreen Android APK]({latest}/projectM-Android.apk) · [Native core AAR]({latest}/projectM-TV-core.aar)
- Version {version}: [Android TV APK]({release}/projectM-TV-{version}.apk) · [Touchscreen Android APK]({release}/projectM-Android-{version}.apk) · [Native core AAR]({release}/projectM-TV-core-{version}.aar){fdroid_downloads}
- [SHA-256 checksums]({release}/checksums.txt)
- [User guide](https://johnneerdael.github.io/ProjectM-Android/)
- [Full changelog]({changelog})

The canonical core AAR includes Native rendering for Milkbeat and existing integrations."""


def render_release_notes(repo: str, version: str, previous_tag: str | None, readme: str,
                         commits: list[Commit], pull_requests: PullLookup,
                         required_shas: set[str] | None = None, *, with_fdroid: bool = False) -> str:
    parts = [f"# ProjectM TV {version}", "## Changes"]
    seen = set()
    for commit in commits:
        merged = [pr for pr in pull_requests(commit.sha) if pr.get("merged_at")]
        if merged:
            for pr in merged:
                number = int(pr["number"])
                body = str(pr.get("body") or "")
                section = release_section(body)
                if commit.sha in (required_shas or set()) and section is None:
                    raise ValueError(f"Merged PR #{number} must include a ## Release notes section.")
                if number in seen:
                    continue
                seen.add(number)
                text = validate_release_notes(body) if section is not None else historical_description(body)
                title = " ".join(str(pr["title"]).splitlines())
                parts.append(f"### {title} ([#{number}](https://github.com/{repo}/pull/{number}))")
                if text:
                    parts.append(nested_markdown(text))
        else:
            parts.append(f"### {commit.subject} ([{commit.sha[:7]}](https://github.com/{repo}/commit/{commit.sha}))")
            body = historical_description(commit.body)
            if body:
                parts.append(nested_markdown(body))
    if not commits:
        parts.append("No commits in this release range.")
    parts.append(install_footer(repo, version, previous_tag, readme, with_fdroid=with_fdroid))
    return "\n\n".join(parts) + "\n"


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(checkout), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def collect_commits(checkout: Path, sha: str, previous_tag: str | None) -> list[Commit]:
    current = git(checkout, "rev-parse", "--verify", "--end-of-options", f"{sha}^{{commit}}")
    revision = current
    if previous_tag:
        try:
            previous = git(checkout, "rev-parse", "--verify", "--end-of-options", f"refs/tags/{previous_tag}^{{commit}}")
        except subprocess.CalledProcessError as error:
            raise ValueError(f"Previous tag does not exist: {previous_tag}") from error
        parents = git(checkout, "rev-list", "--first-parent", current, "--").splitlines()
        if previous not in parents:
            raise ValueError(f"Previous tag is not on the release's first-parent history: {previous_tag}")
        revision = f"{previous}..{current}"
    hashes = git(checkout, "rev-list", "--first-parent", "--reverse", revision, "--").splitlines()
    commits = []
    for commit_sha in hashes:
        subject, _, body = git(checkout, "show", "-s", "--format=%s%n%b", commit_sha, "--").partition("\n")
        commits.append(Commit(commit_sha, subject, body.strip()))
    return commits


def required_note_commits(checkout: Path, sha: str) -> set[str]:
    """Require dedicated PR notes strictly after the declared automation baseline."""
    gradle = checkout / "app/build.gradle"
    if not gradle.exists():
        return set()
    source = gradle.read_text(encoding="utf-8")
    if "baseVersionCommit" not in source:
        return set()
    declarations = re.findall(r"^\s*def\s+baseVersionCommit\s*=\s*['\"]([0-9a-fA-F]{40})['\"]\s*;?\s*$",
                              source, flags=re.MULTILINE)
    if len(declarations) != 1:
        raise ValueError("app/build.gradle must declare one literal baseVersionCommit SHA.")
    baseline = declarations[0].lower()
    current = git(checkout, "rev-parse", "--verify", "--end-of-options", f"{sha}^{{commit}}")
    history = git(checkout, "rev-list", "--first-parent", "--reverse", current, "--").splitlines()
    if baseline not in history:
        raise ValueError("baseVersionCommit is not on the release's first-parent history.")
    return set(history[history.index(baseline) + 1:])


def github_items(endpoint: str) -> list[dict[str, object]]:
    output = subprocess.run(["gh", "api", "--method", "GET", "--paginate", "--slurp",
                             "-H", "Accept: application/vnd.github+json",
                             endpoint],
                            check=True, capture_output=True, text=True).stdout
    pages = json.loads(output)
    return [item for page in pages for item in page]


def associated_pull_requests(repo: str, sha: str) -> list[PullRequest]:
    return github_items(f"repos/{repo}/commits/{sha}/pulls?per_page=100")


def previous_release_tag(checkout: Path, sha: str, version: str, hint: str | None,
                         releases: list[dict[str, object]]) -> str | None:
    """Select a published lower-version release on this first-parent history."""
    current_version = tuple(map(int, version.split(".")))
    current = git(checkout, "rev-parse", "--verify", "--end-of-options", f"{sha}^{{commit}}")
    history = set(git(checkout, "rev-list", "--first-parent", current, "--").splitlines())
    candidates = {}
    for release in releases:
        if release.get("draft") or release.get("prerelease") or not release.get("published_at"):
            continue
        tag = str(release.get("tag_name") or "")
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
        if not match:
            continue
        release_version = tuple(map(int, match.groups()))
        if release_version >= current_version:
            continue
        try:
            commit = git(checkout, "rev-parse", "--verify", "--end-of-options", f"refs/tags/{tag}^{{commit}}")
        except subprocess.CalledProcessError:
            continue
        if commit in history:
            candidates[tag] = release_version
    if hint in candidates:
        return hint
    return max(candidates, key=candidates.get) if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate a PR event's Release notes section")
    validate.add_argument("--event-file", type=Path, required=True)
    generate = commands.add_parser("generate", help="Generate release Markdown without publishing")
    generate.add_argument("--checkout", type=Path, required=True)
    generate.add_argument("--repo", required=True)
    generate.add_argument("--sha", required=True)
    generate.add_argument("--version", required=True)
    generate.add_argument("--previous-tag", help="Previous-release hint; verify publication and first-parent ancestry")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--with-fdroid", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            event = json.loads(args.event_file.read_text(encoding="utf-8"))
            validate_release_notes(str(event.get("pull_request", {}).get("body") or ""))
            print("PR release notes are valid.")
        else:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
                raise ValueError("--repo must be an owner/repository name.")
            if not re.fullmatch(r"[0-9a-fA-F]{7,40}", args.sha):
                raise ValueError("--sha must be a hexadecimal commit SHA.")
            if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
                raise ValueError("--version must have the form major.minor.patch.")
            releases = github_items(f"repos/{args.repo}/releases?per_page=100")
            previous_tag = previous_release_tag(args.checkout, args.sha, args.version, args.previous_tag, releases)
            commits = collect_commits(args.checkout, args.sha, previous_tag)
            required_shas = required_note_commits(args.checkout, args.sha)
            readme = (args.checkout / "README.md").read_text(encoding="utf-8")
            result = render_release_notes(args.repo, args.version, previous_tag, readme, commits,
                                          lambda sha: associated_pull_requests(args.repo, sha), required_shas,
                                          with_fdroid=args.with_fdroid)
            args.output.write_text(result, encoding="utf-8")
            print(f"Release notes written to {args.output}")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Release notes error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
