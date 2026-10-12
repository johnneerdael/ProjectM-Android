"""Exercise deterministic tagged release sources against real temporary Git repositories."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "release_commit.py"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}).stdout.strip()


class Repository:
    """A main branch with gradle.properties, app/build.gradle and a bare remote."""

    def __init__(self, root: Path):
        self.root = root
        self.remote = root / "remote.git"
        self.repo = root / "work"
        git(root, "init", "--quiet", "--bare", str(self.remote))
        git(root, "init", "--quiet", "-b", "main", str(self.repo))
        for key, value in [("user.name", "Test"), ("user.email", "test@example.org"), ("commit.gpgSign", "false")]:
            git(self.repo, "config", key, value)
        git(self.repo, "remote", "add", "origin", str(self.remote))
        (self.repo / "app").mkdir()
        (self.repo / "gradle.properties").write_text("org.gradle.jvmargs=-Xmx2g\n")
        self.commit("baseline", "app/build.gradle", "def baseVersionName = \"2.3.0\"\n")

    def commit(self, subject, path="notes.txt", content=None):
        target = self.repo / path
        target.write_text(content if content is not None else subject + "\n")
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "--quiet", "-m", subject,
            env={"GIT_COMMITTER_DATE": "1791800000 +0200", "GIT_AUTHOR_DATE": "1791800000 +0200"})
        return git(self.repo, "rev-parse", "HEAD")


class ReleaseCommitTests(unittest.TestCase):
    def setUp(self):
        self.module = load("release_commit")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = Repository(Path(self.directory.name))
        self.repo = self.fixture.repo
        self.source = git(self.repo, "rev-parse", "HEAD")

    def test_release_commit_only_declares_the_version_on_top_of_its_source(self):
        commit = self.module.create(self.repo, self.source, "2.3.42", 91)
        self.assertEqual(git(self.repo, "rev-parse", f"{commit}^"), self.source)
        self.assertEqual(git(self.repo, "diff-tree", "--no-commit-id", "--name-only", "-r", self.source, commit),
                         "gradle.properties")
        properties = git(self.repo, "show", f"{commit}:gradle.properties")
        self.assertTrue(properties.startswith("org.gradle.jvmargs=-Xmx2g\n"))
        self.assertIn("\nprojectmReleaseVersion=2.3.42\nprojectmReleaseVersionCode=91", properties)
        self.assertEqual(self.module.declared_release(properties), ("2.3.42", 91))
        self.assertEqual(git(self.repo, "show", "-s", "--format=%s%n%an <%ae>%n%ct", commit).splitlines(),
                         ["Release v2.3.42", "ProjectM release <41898282+github-actions[bot]@users.noreply.github.com>",
                          "1791800000"])
        # Only an object was written: no ref, no index or working-tree change.
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.source)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "tag"), "")

    def test_same_inputs_rebuild_the_same_sha_in_another_clone(self):
        commit = self.module.create(self.repo, self.source, "2.3.42", 91)
        git(self.repo, "push", "--quiet", "origin", "main")
        clone = Path(self.directory.name) / "clone"
        git(Path(self.directory.name), "clone", "--quiet", str(self.fixture.remote), str(clone))
        git(clone, "config", "user.name", "Someone else")
        self.assertEqual(self.module.create(clone, self.source, "2.3.42", 91), commit)
        self.assertNotEqual(self.module.create(clone, self.source, "2.3.42", 92), commit)

    def test_inspect_maps_release_tags_to_their_source_and_keeps_older_tags(self):
        commit = self.module.create(self.repo, self.source, "2.3.42", 91)
        self.assertEqual(self.module.inspect(self.repo, commit),
                         {"commit": commit, "source": self.source, "version": "2.3.42", "version_code": 91})
        self.assertEqual(self.module.source_of(self.repo, commit), self.source)
        self.assertIsNone(self.module.inspect(self.repo, self.source))
        self.assertEqual(self.module.source_of(self.repo, self.source), self.source)

    def test_malformed_release_commits_are_rejected(self):
        git(self.repo, "checkout", "--quiet", "--detach")
        (self.repo / "gradle.properties").write_text(
            "org.gradle.jvmargs=-Xmx2g\n\nprojectmReleaseVersion=2.3.42\nprojectmReleaseVersionCode=91\n")
        (self.repo / "notes.txt").write_text("smuggled\n")
        git(self.repo, "add", "--all")
        git(self.repo, "commit", "--quiet", "-m",
            f"Release v2.3.42\n\nVersion-Code: 91\nSource-Commit: {self.source}\n")
        with self.assertRaisesRegex(ValueError, "more than"):
            self.module.inspect(self.repo, "HEAD")
        git(self.repo, "commit", "--quiet", "--amend", "-m", "Release v2.3.42\n\nVersion-Code: 91\nSource-Commit: " + "0" * 40)
        with self.assertRaisesRegex(ValueError, "single source parent"):
            self.module.inspect(self.repo, "HEAD")

    def test_main_must_not_declare_a_release_identity(self):
        self.fixture.commit("declare", "gradle.properties", "projectmReleaseVersionCode = 3\n")
        with self.assertRaisesRegex(ValueError, "must not declare"):
            self.module.create(self.repo, "HEAD", "2.3.42", 91)
        for version, code in [("2.3", 91), ("2.3.42-ci.1", 91), ("2.3.42", 0), ("2.3.42", True)]:
            with self.subTest(version=version, code=code), self.assertRaises(ValueError):
                self.module.release_properties("", version, code)

    def test_declared_release_parsing(self):
        self.assertIsNone(self.module.declared_release("org.gradle.jvmargs=-Xmx2g\n"))
        for text in ["projectmReleaseVersion=2.3.42\n",
                     "projectmReleaseVersion=2.3.42\nprojectmReleaseVersionCode=091\n",
                     "projectmReleaseVersion=2.3.42\nprojectmReleaseVersionCode=91\nprojectmReleaseVersionCode=92\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.module.declared_release(text)

    def test_publish_tag_pushes_once_and_never_moves_a_tag(self):
        commit = self.module.create(self.repo, self.source, "2.3.42", 91)
        with self.assertRaisesRegex(ValueError, "differs from the built source"):
            self.module.publish_tag(self.repo, "origin", self.source, "2.3.42", 91, "f" * 40)
        self.assertEqual(self.module.publish_tag(self.repo, "origin", self.source, "2.3.42", 91, commit), "created")
        self.assertEqual(git(self.fixture.remote, "rev-parse", "refs/tags/v2.3.42"), commit)
        self.assertEqual(self.module.publish_tag(self.repo, "origin", self.source, "2.3.42", 91, commit), "existing")
        later = self.fixture.commit("later")
        moved = self.module.create(self.repo, later, "2.3.42", 91)
        with self.assertRaisesRegex(ValueError, "refusing to move"):
            self.module.publish_tag(self.repo, "origin", later, "2.3.42", 91, moved)

    def test_cli_checkout_builds_the_release_tree_and_writes_outputs(self):
        output = Path(self.directory.name) / "outputs"
        result = subprocess.run([sys.executable, str(SCRIPT), "create", "--repo", str(self.repo),
                                 "--source", self.source, "--version", "2.3.42", "--version-code", "91",
                                 "--checkout", "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        commit = result.stdout.strip()
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), commit)
        self.assertIn("projectmReleaseVersionCode=91", (self.repo / "gradle.properties").read_text())
        self.assertEqual(output.read_text(), f"release_sha={commit}\nsource_sha={self.source}\n")


class TaggedHistoryTests(unittest.TestCase):
    """Version allocation and release notes follow a release tag back to main."""

    def setUp(self):
        self.commit_module = load("release_commit")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = Repository(Path(self.directory.name))
        self.repo = self.fixture.repo
        gradle = ('def baseVersionName = "2.3.0"\ndef baseVersionCode = 49\n'
                  'def baseVersionCommit = "{anchor}"\n')
        self.anchor = self.fixture.commit("anchor", "app/build.gradle", gradle.format(anchor="0" * 40))
        self.fixture.commit("configure", "app/build.gradle", gradle.format(anchor=self.anchor))
        self.first = git(self.repo, "rev-parse", "HEAD")
        released = self.commit_module.create(self.repo, self.first, "2.3.0", 49)
        git(self.repo, "tag", "v2.3.0", released)
        self.second = self.fixture.commit("second")

    def test_release_version_reuses_and_skips_past_tagged_release_commits(self):
        version = load("release_version")
        rerun = version.resolve_version(self.repo, self.first, "workflow_dispatch", "refs/heads/main", 7)
        self.assertEqual((rerun["version"], rerun["reused_tag"]), ("2.3.0", True))
        nxt = version.resolve_version(self.repo, self.second, "push", "refs/heads/main", 8)
        self.assertEqual((nxt["version"], nxt["version_code"], nxt["previous_tag"]), ("2.3.1", 50, "v2.3.0"))

    def test_release_notes_follow_the_previous_release_source(self):
        notes = load("release_notes")
        releases = [{"tag_name": "v2.3.0", "published_at": "2026-10-12T00:00:00Z"}]
        self.assertEqual(notes.previous_release_tag(self.repo, self.second, "2.3.1", None, releases), "v2.3.0")
        commits = notes.collect_commits(self.repo, self.second, "v2.3.0")
        self.assertEqual([commit.sha for commit in commits], [self.second])


if __name__ == "__main__":
    unittest.main()
