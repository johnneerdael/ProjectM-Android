import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "release_notes.py"
spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
notes = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = notes
spec.loader.exec_module(notes)


README = "> **Install on your TV with the Downloader app: code `7654321`**\n"


class ValidationTests(unittest.TestCase):
    def test_extracts_notes_and_preserves_nested_markdown(self):
        body = """## Summary
Other PR material.
## RELEASE NOTES
<!-- Describe the impact here. -->
### Fixed
- Keeps music playing during preset switches.
  - Retains the cached audio session.
## Validation
Tests passed.
"""
        self.assertEqual(notes.validate_release_notes(body), "### Fixed\n- Keeps music playing during preset switches.\n  - Retains the cached audio session.")

    def test_rejects_missing_empty_and_placeholder_sections(self):
        for body in (
            "## Summary\nFix the audio session.",
            "## Release notes\n<!-- Explain changes -->\n- ",
            "## Release notes\n- TODO: describe the change",
            "## Release notes\nTBD",
            "## Release notes\nN/A",
            "## Release notes\n- N/A\n- Fix audio.",
            "## Release notes\n[Describe the user-visible changes]",
            "## Release notes\nNo user-visible changes.",
            "## Release notes\nNo user-visible changes.\n### Internal\nTBD",
            "## Release notes\nNo user-visible changes.\n### Internal\n- Maintenance",
        ):
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    notes.validate_release_notes(body)

    def test_accepts_concrete_internal_changes_without_word_count(self):
        body = "## Release notes\nNo user-visible changes.\n### Internal\n- Pin Gradle."
        self.assertIn("Pin Gradle.", notes.validate_release_notes(body))

    def test_accepts_internal_subheadings_and_emphasized_inline_labels(self):
        for body in (
            "## Release notes\nNo user-visible changes.\n### Internal\n#### Build tools\n- Pin Gradle.",
            "## Release notes\nNo user-visible changes.\n**Internal:** Pin Gradle.",
        ):
            with self.subTest(body=body):
                self.assertIn("Pin Gradle.", notes.validate_release_notes(body))

    def test_ignores_fake_headings_inside_code_fences(self):
        body = "```markdown\n## Release notes\nFixed audio.\n```"
        with self.assertRaises(ValueError):
            notes.validate_release_notes(body)

    def test_validation_cli_reads_event_and_reports_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            for body, expected in (("## Release notes\nFix audio.", 0), ("## Summary\nFix audio.", 1)):
                event.write_text(json.dumps({"pull_request": {"body": body}}))
                result = subprocess.run([sys.executable, str(SCRIPT), "validate", "--event-file", str(event)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)


class GenerationTests(unittest.TestCase):
    def test_historical_pr15_plain_validation_and_ai_badges_do_not_leak(self):
        body = """Prevents freezes while loading shaders with self-referencing macros and crashes from custom waveform audio reads while retaining the projectM 4.1.7 pin.

Adds real-engine macro and waveform regressions to the native test runner, covering extreme separation values and 512-point waveforms.

Validation:
- Reproduced the original macro timeout and waveform invalid read before applying the fixes.
- Android release core built for arm64-v8a and armeabi-v7a; all 33 JVM tests passed.

---

[![Compound Engineering](https://img.shields.io/badge/Built_with-Compound_Engineering-6366f1)](https://github.com/EveryInc/compound-engineering-plugin)
![Codex](https://img.shields.io/badge/Codex-GPT_6-000000)
"""
        cleaned = notes.historical_description(body)
        self.assertIn("Prevents freezes", cleaned)
        self.assertIn("Adds real-engine macro and waveform regressions", cleaned)
        for unwanted in ("Validation", "Reproduced", "JVM tests", "---", "Compound Engineering", "Codex", "shields.io"):
            self.assertNotIn(unwanted, cleaned)

    def test_historical_plain_and_bold_review_labels_stop_at_next_change_section(self):
        for label in ("Validation:", "**Validation:**", "**Tests**:", "Test plan:", "**Testplan:**", "Checklist:", "**Not changed:**"):
            body = f"Keep the cached audio session.\n\n{label}\n- Review-only or unchanged material.\n\n## Fixed\n- Repair the resume handler."
            with self.subTest(label=label):
                cleaned = notes.historical_description(body)
                self.assertIn("Keep the cached audio session.", cleaned)
                self.assertIn("Repair the resume handler.", cleaned)
                self.assertNotIn("Review-only", cleaned)
                self.assertNotIn(label, cleaned)

    def test_historical_unchanged_sections_and_all_image_lines_are_omitted(self):
        body = """![Codex](https://img.shields.io/badge/Codex-GPT_6-000000)
![Screenshot](screenshot.png)
<img src="badge.png" alt="Agent badge">
## Summary
Retain the audio session.
## Not changed
- Preset assets stay the same.
### Details
More unchanged details.
## Changes
- Repair the resume handler.
"""
        cleaned = notes.historical_description(body)
        self.assertIn("Retain the audio session.", cleaned)
        self.assertIn("Repair the resume handler.", cleaned)
        for unwanted in ("Codex", "Screenshot", "<img", "Not changed", "assets stay", "unchanged details"):
            self.assertNotIn(unwanted, cleaned)

    def test_explicit_release_notes_keep_images_and_validation_markdown(self):
        body = "## Release notes\nFix the resume handler.\n\n![Screenshot](screenshot.png)\n\n### Validation\n- Report the new diagnostics field.\n<!-- Private template comment -->\n## Tests\nReview-only tests."
        pr = {"number": 23, "title": "Fix resume", "body": body, "merged_at": "2026-10-03T10:00:00Z"}
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [notes.Commit("a" * 40, "Merge", "")], lambda sha: [pr])
        self.assertIn("![Screenshot](screenshot.png)", result)
        self.assertIn("#### Validation\n- Report the new diagnostics field.", result)
        self.assertNotIn("Private template comment", result)
        self.assertNotIn("Review-only tests", result)

    def test_new_merged_pr_without_release_notes_fails(self):
        commit = notes.Commit("a" * 40, "Merge new PR", "")
        pr = {"number": 22, "title": "Fix audio", "body": "## Summary\nRetain the audio session.", "merged_at": "2026-10-03T10:00:00Z"}
        with self.assertRaisesRegex(ValueError, "#22.*Release notes"):
            notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [commit], lambda sha: [pr], required_shas={commit.sha})

    def test_required_direct_commit_still_uses_commit_message(self):
        commit = notes.Commit("a" * 40, "fix: retain audio session", "Keep the last working audio source.")
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [commit], lambda sha: [], required_shas={commit.sha})
        self.assertIn("Keep the last working audio source.", result)

    def test_deduplicates_merged_prs_and_preserves_source_markdown(self):
        commits = [notes.Commit("a" * 40, "Merge audio fix", ""), notes.Commit("b" * 40, "Merge audio fix again", "")]
        pr = {"number": 17, "title": "Restore audio", "merged_at": "2026-10-03T10:00:00Z", "body": "## Release notes\n### Fixed\n- Retains **audio** after resume.\n  - Preserves the session.\n\nExample: `$(touch dangerous)` and `literal`.\n## Tests\nChecked on TV."}
        unmerged = dict(pr, number=18, merged_at=None)
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", "v2.1.4", README, commits, lambda sha: [pr, unmerged])
        self.assertEqual(result.count("### Restore audio"), 1)
        self.assertIn("[#17](https://github.com/johnneerdael/ProjectM-TV/pull/17)", result)
        self.assertIn("#### Fixed\n- Retains **audio** after resume.\n  - Preserves the session.", result)
        self.assertIn("`$(touch dangerous)`", result)
        self.assertNotIn("Checked on TV", result)
        self.assertNotIn("#18", result)

    def test_old_pr_falls_back_to_description_without_test_checklist_or_footer(self):
        body = """[![CI](badge.svg)](https://example.org)
## Summary
Keep the renderer alive after an audio app resumes.

- Cache the last working session.
## Validation
- [x] Unit tests pass.
## Checklist
- [x] Ready to ship
---
Generated with [Claude Code](https://example.org)
Co-Authored-By: Agent <agent@example.org>
"""
        pr = {"number": 19, "title": "Repair audio", "body": body, "merged_at": "2026-10-03T10:00:00Z"}
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [notes.Commit("a" * 40, "Merge", "")], lambda sha: [pr])
        self.assertIn("Keep the renderer alive", result)
        self.assertIn("- Cache the last working session.", result)
        for unwanted in ("badge.svg", "Unit tests", "Ready to ship", "Generated with", "Co-Authored"):
            self.assertNotIn(unwanted, result)

    def test_description_without_change_content_falls_back_to_actual_title(self):
        pr = {"number": 20, "title": "Pin the Android build tools", "body": "## Tests\nAll pass.", "merged_at": "2026-10-03T10:00:00Z"}
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [notes.Commit("a" * 40, "Merge", "")], lambda sha: [pr])
        self.assertIn("Pin the Android build tools", result)
        self.assertNotIn("All pass", result)

    def test_direct_commit_keeps_actual_subject_body_and_source_link(self):
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, README, [notes.Commit("c" * 40, "fix: cache audio", "Retain the last session.\n\nLiteral: `$(false)`\n\nCo-Authored-By: Agent <agent@example.org>")], lambda sha: [])
        self.assertIn("fix: cache audio", result)
        self.assertIn("Retain the last session.", result)
        self.assertIn("`$(false)`", result)
        self.assertIn("/commit/" + "c" * 40, result)
        self.assertNotIn("Co-Authored", result)

    def test_install_footer_uses_readme_and_versioned_and_latest_assets(self):
        result = notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", "v2.1.4", README, [], lambda sha: [])
        self.assertIn("Downloader app: code `7654321`", result)
        for url in (
            "releases/latest/download/projectM-TV.apk",
            "releases/latest/download/projectM-TV-core.aar",
            "releases/download/v2.1.5/projectM-TV-2.1.5.apk",
            "releases/download/v2.1.5/projectM-TV-core-2.1.5.aar",
            "releases/download/v2.1.5/checksums.txt",
            "https://johnneerdael.github.io/ProjectM-TV/",
            "compare/v2.1.4...v2.1.5",
        ):
            self.assertIn(url, result)
        self.assertNotIn("4821216", result)
        self.assertNotIn("capped", result.lower())
        self.assertNotIn("core-native", result)
        self.assertIn("Native core AAR", result)

    def test_install_footer_uses_separate_readme_codes_for_android_and_tv(self):
        readme = README + "> **Install on your phone or tablet with the Downloader app: code `1234567`**\n"
        result = notes.install_footer("johnneerdael/ProjectM-TV", "2.3.38", "v2.3.37", readme)
        self.assertIn("Install on your TV with the Downloader app: code `7654321`", result)
        self.assertIn("Install on your phone or tablet with the Downloader app: code `1234567`", result)
        self.assertIn("https://play.google.com/store/apps/details?id=com.esaba.downloader&hl=en", result)
        self.assertNotIn("6565691", result)

    def test_malformed_android_code_is_not_silently_omitted(self):
        readme = README + "> **Install on your phone or tablet with the Downloader app: code `TBD`**\n"
        with self.assertRaisesRegex(ValueError, "Android Downloader"):
            notes.install_footer("johnneerdael/ProjectM-TV", "2.3.38", None, readme)

    def test_legacy_readme_does_not_invent_an_android_downloader_code(self):
        result = notes.install_footer("johnneerdael/ProjectM-TV", "2.3.38", None, README)
        self.assertNotIn("Install on your phone or tablet with the Downloader app", result)
        self.assertIn("projectM-Android.apk", result)

    def test_missing_canonical_downloader_code_fails_instead_of_stale_fallback(self):
        with self.assertRaises(ValueError):
            notes.render_release_notes("johnneerdael/ProjectM-TV", "2.1.5", None, "No install code.", [], lambda sha: [])


class GitTests(unittest.TestCase):
    def test_previous_release_ignores_drafts_future_versions_and_unreachable_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            for version in ("2.1.4", "2.1.5", "2.1.6"):
                git("commit", "--allow-empty", "-m", f"Changes for {version}")
                git("tag", f"v{version}")
            current = git("rev-parse", "HEAD")
            git("checkout", "-b", "other")
            git("commit", "--allow-empty", "-m", "Unreachable release")
            git("tag", "v2.1.7")
            git("checkout", "main")
            published4 = {"tag_name": "v2.1.4", "draft": False, "prerelease": False, "published_at": "2026-10-01T10:00:00Z"}
            draft5 = {"tag_name": "v2.1.5", "draft": True, "prerelease": False, "published_at": None}
            releases = [published4, draft5, dict(published4, tag_name="v2.1.6"), dict(published4, tag_name="v2.1.7")]
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.6", "v2.1.5", releases), "v2.1.4")
            older_retry = git("rev-parse", "v2.1.5^{commit}")
            self.assertEqual(notes.previous_release_tag(checkout, older_retry, "2.1.5", "v2.1.6", releases), "v2.1.4")
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.8", None, releases), "v2.1.6")
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.8", "v2.1.4", releases), "v2.1.4")
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.6", "v2.1.5", [draft5]), None)
            unpublished5 = dict(draft5, draft=False)
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.6", "v2.1.5", [published4, unpublished5]), "v2.1.4")
            prerelease = dict(published4, prerelease=True)
            self.assertEqual(notes.previous_release_tag(checkout, current, "2.1.6", "v2.1.4", [prerelease]), None)
            self.assertEqual(len(notes.collect_commits(checkout, current, None)), 3)

    def test_generate_cli_covers_unpublished_tag_changes_since_last_actual_release(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            git("commit", "--allow-empty", "-m", "Published release")
            git("tag", "v2.1.4")
            git("commit", "--allow-empty", "-m", "Fix missing audio after resume")
            git("tag", "v2.1.5")
            git("commit", "--allow-empty", "-m", "Fix preset loading freeze")
            (checkout / "README.md").write_text(README)
            fake_bin = checkout / "bin"
            fake_bin.mkdir()
            releases = [{"tag_name": "v2.1.4", "draft": False, "prerelease": False, "published_at": "2026-10-01T10:00:00Z"}, {"tag_name": "v2.1.5", "draft": True, "prerelease": False, "published_at": None}]
            gh = fake_bin / "gh"
            gh.write_text(f"#!{sys.executable}\nimport sys\nprint({json.dumps([releases])!r} if '/releases?' in sys.argv[-1] else '[[]]')\n")
            gh.chmod(0o755)
            output = checkout / "notes.md"
            result = subprocess.run([sys.executable, str(SCRIPT), "generate", "--checkout", str(checkout), "--repo", "johnneerdael/ProjectM-TV", "--sha", git("rev-parse", "HEAD"), "--version", "2.1.6", "--previous-tag", "v2.1.5", "--output", str(output)], env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = output.read_text()
            self.assertIn("Fix missing audio after resume", rendered)
            self.assertIn("Fix preset loading freeze", rendered)
            self.assertNotIn("Published release", rendered)
            self.assertIn("compare/v2.1.4...v2.1.6", rendered)

    def test_baseline_is_historical_and_only_later_first_parent_commits_require_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            git("commit", "--allow-empty", "-m", "Before automation")
            historical = git("rev-parse", "HEAD")
            git("commit", "--allow-empty", "-m", "Automation baseline")
            baseline = git("rev-parse", "HEAD")
            (checkout / "app").mkdir()
            (checkout / "app/build.gradle").write_text(f'def baseVersionCommit = "{baseline}"\n')
            self.assertEqual(notes.required_note_commits(checkout, baseline), set())
            git("checkout", "-b", "feature")
            git("commit", "--allow-empty", "-m", "Feature-only commit")
            feature = git("rev-parse", "HEAD")
            git("checkout", "main")
            git("merge", "--no-ff", "feature", "-m", "Post-baseline PR")
            newest = git("rev-parse", "HEAD")
            required = notes.required_note_commits(checkout, newest)
            self.assertEqual(required, {newest})
            self.assertNotIn(historical, required)
            self.assertNotIn(baseline, required)
            self.assertNotIn(feature, required)

    def test_generation_cli_enforces_declared_baseline_without_breaking_baseline_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            git("commit", "--allow-empty", "-m", "Automation baseline")
            baseline = git("rev-parse", "HEAD")
            (checkout / "app").mkdir()
            (checkout / "app/build.gradle").write_text(f'def baseVersionCommit = "{baseline}"\n')
            (checkout / "README.md").write_text(README)
            fake_bin = checkout / "bin"
            fake_bin.mkdir()
            pr = {"number": 15, "title": "Historical renderer fix", "body": "## Summary\nFix preset rendering.", "merged_at": "2026-10-03T10:00:00Z"}
            gh = fake_bin / "gh"
            gh.write_text(f"#!{sys.executable}\nimport sys\nprint('[[]]' if '/releases?' in sys.argv[-1] else {json.dumps([[pr]])!r})\n")
            gh.chmod(0o755)
            environment = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
            def generate(sha, output):
                return subprocess.run([sys.executable, str(SCRIPT), "generate", "--checkout", str(checkout), "--repo", "johnneerdael/ProjectM-TV", "--sha", sha, "--version", "2.1.5", "--output", str(output)], env=environment, capture_output=True, text=True)
            historical_output = checkout / "historical.md"
            result = generate(baseline, historical_output)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Fix preset rendering.", historical_output.read_text())
            git("commit", "--allow-empty", "-m", "New merge")
            new_output = checkout / "new.md"
            result = generate(git("rev-parse", "HEAD"), new_output)
            self.assertEqual(result.returncode, 1)
            self.assertIn("#15", result.stderr)
            self.assertIn("Release notes", result.stderr)
            self.assertFalse(new_output.exists())

    def test_generation_cli_reads_git_and_github_json_without_executing_pr_text(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            git("commit", "--allow-empty", "-m", "Initial")
            git("tag", "v2.1.4")
            git("commit", "--allow-empty", "-m", "Merge PR")
            (checkout / "README.md").write_text(README)
            marker = checkout / "must-not-exist"
            pr = {"number": 21, "title": "Fix audio", "body": f"## Release notes\n- Preserve the literal `$(touch {marker})` in examples.", "merged_at": "2026-10-03T10:00:00Z"}
            fake_bin = checkout / "bin"
            fake_bin.mkdir()
            # Only the external GitHub boundary is replaced; real CLI and Git run.
            gh = fake_bin / "gh"
            releases = [[{"tag_name": "v2.1.4", "draft": False, "prerelease": False, "published_at": "2026-10-01T10:00:00Z"}]]
            gh.write_text(f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\nPath({str(checkout / 'gh-args.json')!r}).write_text(json.dumps(sys.argv[1:]))\nprint({json.dumps(releases)!r} if '/releases?' in sys.argv[-1] else {json.dumps([[pr]])!r})\n")
            gh.chmod(0o755)
            output = checkout / "notes.md"
            result = subprocess.run([sys.executable, str(SCRIPT), "generate", "--checkout", str(checkout), "--repo", "johnneerdael/ProjectM-TV", "--sha", git("rev-parse", "HEAD"), "--version", "2.1.5", "--previous-tag", "v2.1.4", "--output", str(output)], env={**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rendered = output.read_text()
            self.assertIn("# ProjectM TV 2.1.5", rendered)
            self.assertIn(f"`$(touch {marker})`", rendered)
            self.assertFalse(marker.exists())
            arguments = json.loads((checkout / "gh-args.json").read_text())
            self.assertEqual(arguments[:3], ["api", "--method", "GET"])
            self.assertIn("--paginate", arguments)
            self.assertIn("--slurp", arguments)
            self.assertIn("/commits/", arguments[-1])

    def test_range_collects_first_parent_only_in_chronological_order(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            def git(*args):
                return subprocess.run(["git", "-C", str(checkout), *args], check=True, text=True, capture_output=True).stdout.strip()
            git("init", "-b", "main")
            git("config", "user.email", "test@example.org")
            git("config", "user.name", "Release test")
            git("commit", "--allow-empty", "-m", "Initial")
            git("tag", "v2.1.4")
            git("checkout", "-b", "feature")
            git("commit", "--allow-empty", "-m", "Feature detail")
            git("checkout", "main")
            git("commit", "--allow-empty", "-m", "Direct fix", "-m", "Actual explanation.")
            git("merge", "--no-ff", "feature", "-m", "Merge feature")
            commits = notes.collect_commits(checkout, git("rev-parse", "HEAD"), "v2.1.4")
            self.assertEqual([commit.subject for commit in commits], ["Direct fix", "Merge feature"])
            self.assertEqual(commits[0].body, "Actual explanation.")
            with self.assertRaises(ValueError):
                notes.collect_commits(checkout, git("rev-parse", "HEAD"), "feature")


if __name__ == "__main__":
    unittest.main()
