import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("publish_release", Path(__file__).parents[1] / "publish_release.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeAPI:
    def __init__(self, existing=None, latest=None, tag_commit=None):
        self.existing, self.latest, self.tag_commit = existing, latest, tag_commit
        self.calls = []

    def __call__(self, endpoint, method="GET", payload=None, missing_ok=False):
        self.calls.append((endpoint, method, payload))
        if endpoint.endswith("/releases/tags/v2.1.5"):
            return self.existing
        if endpoint.endswith("/releases/latest"):
            return self.latest
        if "/git/ref/tags/" in endpoint:
            return {"object": {"type": "commit", "sha": self.tag_commit}}
        if method == "POST":
            return {"id": 55, "html_url": "https://github.com/owner/repo/releases/tag/v2.1.5"}
        if method == "PATCH":
            return {"html_url": "https://github.com/owner/repo/releases/tag/v2.1.5"}
        raise AssertionError(endpoint)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.notes = self.root / "notes.md"
        self.notes.write_text("# ProjectM TV 2.1.5\n\nFixed a preset loading freeze.\n")
        for name, data in {"projectM-TV-2.1.5.apk": b"signed apk", "projectM-TV.apk": b"signed apk",
                           "projectM-TV-core-2.1.5.aar": b"native engine", "projectM-TV-core.aar": b"native engine",
                           "projectM-TV-2.1.5-mapping.txt": b"a.b -> x:",
                           "projectM-Android-2.1.5.apk": b"signed touch apk",
                           "projectM-Android.apk": b"signed touch apk",
                           "projectM-Android-2.1.5-mapping.txt": b"c.d -> y:"}.items():
            (self.root / name).write_bytes(data)
        self.commands = []

    def publish(self, api, with_touchscreen=True):
        return module.publish("owner/repo", "2.1.5", "a" * 40, self.notes, self.root, api, self.commands.append, with_touchscreen=with_touchscreen)

    def test_uploads_all_artifacts_before_publishing_the_draft(self):
        api = FakeAPI(latest={"tag_name": "v2.1.4"})
        def upload(command):
            self.commands.append(command)
            writes = [payload for _, method, payload in api.calls if method != "GET"]
            self.assertTrue(writes[-1]["draft"], "release became public before uploads")
        module.publish("owner/repo", "2.1.5", "a" * 40, self.notes, self.root, api, upload, with_touchscreen=True)
        writes = [(method, payload) for _, method, payload in api.calls if method != "GET"]
        self.assertTrue(writes[0][1]["draft"])
        self.assertFalse(writes[1][1]["draft"])
        self.assertEqual(writes[1][1]["make_latest"], "true")
        self.assertEqual(writes[0][1]["target_commitish"], "a" * 40)
        command = self.commands[0]
        self.assertEqual(command[:3], ["gh", "release", "upload"])
        self.assertIn(str(self.root / "checksums.txt"), command)
        self.assertIn(str(self.root / "projectM-TV-2.1.5-mapping.txt"), command)
        checksums = (self.root / "checksums.txt").read_text()
        self.assertEqual(len(checksums.splitlines()), 8)
        for name in ("projectM-TV-core-2.1.5.aar", "projectM-TV-core.aar"):
            self.assertIn(str(self.root / name), command)
            self.assertIn(f"{hashlib.sha256((self.root / name).read_bytes()).hexdigest()}  {name}\n", checksums)

    def test_complete_same_commit_release_is_not_republished(self):
        names = [p.name for p in self.root.iterdir()] + ["checksums.txt"]
        api = FakeAPI(existing={"id": 55, "draft": False, "assets": [{"name": n} for n in names],
                                "html_url": "release url"}, tag_commit="a" * 40)
        self.publish(api)
        self.assertFalse(self.commands)
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))

    def test_retry_finishes_a_draft_without_allocating_another_release(self):
        api = FakeAPI(existing={"id": 55, "draft": True, "target_commitish": "a" * 40},
                      latest={"tag_name": "v2.1.4"})
        self.publish(api)
        self.assertFalse(any(method == "POST" for _, method, _ in api.calls))
        self.assertEqual(api.calls[-1][1], "PATCH")

    def test_older_retry_cannot_replace_a_newer_latest_release(self):
        api = FakeAPI(latest={"tag_name": "v2.1.6"})
        self.publish(api)
        self.assertEqual(api.calls[-1][2]["make_latest"], "false")

    def test_existing_tag_at_another_commit_is_rejected(self):
        api = FakeAPI(existing={"id": 55, "draft": False, "assets": []}, tag_commit="b" * 40)
        with self.assertRaisesRegex(ValueError, "different commit"):
            self.publish(api)
        self.assertFalse(self.commands)

    def test_mismatched_latest_alias_is_rejected_before_network_calls(self):
        (self.root / "projectM-TV.apk").write_bytes(b"old apk")
        api = FakeAPI()
        with self.assertRaisesRegex(ValueError, "alias"):
            self.publish(api)
        self.assertFalse(api.calls)

    def test_missing_touch_apk_is_rejected_before_network_calls(self):
        (self.root / "projectM-Android-2.1.5.apk").unlink()
        api = FakeAPI()
        with self.assertRaises(FileNotFoundError):
            self.publish(api)
        self.assertFalse(api.calls)

    def test_mismatched_touch_alias_is_rejected_before_network_calls(self):
        (self.root / "projectM-Android.apk").write_bytes(b"wrong touch apk")
        api = FakeAPI()
        with self.assertRaisesRegex(ValueError, "alias"):
            self.publish(api)
        self.assertFalse(api.calls)

    def test_missing_core_artifact_is_rejected_before_network_calls(self):
        (self.root / "projectM-TV-core.aar").unlink()
        api = FakeAPI()
        with self.assertRaises(FileNotFoundError):
            self.publish(api)
        self.assertFalse(api.calls)

    def test_failed_upload_keeps_the_release_as_a_draft(self):
        api = FakeAPI()
        def failed_upload(command):
            raise RuntimeError("upload interrupted")
        with self.assertRaisesRegex(RuntimeError, "upload interrupted"):
            module.publish("owner/repo", "2.1.5", "a" * 40, self.notes, self.root, api, failed_upload)
        self.assertFalse(any(method == "PATCH" for _, method, _ in api.calls))

    def test_missing_mapping_is_rejected_before_network_calls(self):
        (self.root / "projectM-TV-2.1.5-mapping.txt").unlink()
        api = FakeAPI()
        with self.assertRaises(FileNotFoundError):
            self.publish(api)
        self.assertFalse(api.calls)

    def test_wrong_version_notes_are_rejected_before_network_calls(self):
        self.notes.write_text("# ProjectM TV 2.1.4\n\nOld notes.\n")
        api = FakeAPI()
        with self.assertRaisesRegex(ValueError, "notes do not match"):
            self.publish(api)
        self.assertFalse(api.calls)

    def historical_dual_assets(self):
        # Explicit immutable historical schema: canonical capped + opt-in Native artifacts.
        (self.root / "projectM-TV-core-2.1.5.aar").write_bytes(b"capped engine")
        (self.root / "projectM-TV-core.aar").write_bytes(b"capped engine")
        (self.root / "projectM-TV-core-native-2.1.5.aar").write_bytes(b"historical native engine")
        (self.root / "projectM-TV-core-native.aar").write_bytes(b"historical native engine")
        return [{"name": p.name, "digest": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in self.root.iterdir() if p.name != "notes.md"] + [{"name": "checksums.txt"}]

    def test_new_release_publishes_only_canonical_native_core_even_with_stale_alias_files(self):
        self.historical_dual_assets()
        for name in ("projectM-TV-core-2.1.5.aar", "projectM-TV-core.aar"):
            (self.root / name).write_bytes(b"native engine")
        self.publish(FakeAPI())
        uploaded = {Path(arg).name for arg in self.commands[0] if arg.endswith((".aar", ".apk", ".txt"))}
        self.assertEqual(uploaded, {"projectM-TV-2.1.5.apk", "projectM-TV.apk",
                                   "projectM-TV-core-2.1.5.aar", "projectM-TV-core.aar",
                                   "projectM-TV-2.1.5-mapping.txt", "projectM-Android-2.1.5.apk",
                                   "projectM-Android.apk", "projectM-Android-2.1.5-mapping.txt", "checksums.txt"})
        self.assertNotIn("core-native", (self.root / "checksums.txt").read_text())

    def test_complete_historical_dual_release_retry_requires_no_retired_local_files_or_mutations(self):
        assets = self.historical_dual_assets()
        for name in ("projectM-TV-core-native-2.1.5.aar", "projectM-TV-core-native.aar"):
            (self.root / name).unlink()
        (self.root / "checksums.txt").write_text("historical checksum bytes\n")
        api = FakeAPI(existing={"id": 55, "draft": False, "assets": assets,
                                "html_url": "historical release"}, tag_commit="a" * 40)
        result = self.publish(api, with_touchscreen=False)
        self.assertEqual(result, {"url": "historical release", "created": False})
        self.assertFalse(self.commands)
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))
        self.assertEqual((self.root / "checksums.txt").read_text(), "historical checksum bytes\n")

    def test_complete_single_core_release_retry_preserves_historical_checksum_bytes(self):
        (self.root / "checksums.txt").write_text("historical checksum bytes\n")
        names = ["projectM-TV-2.1.5.apk", "projectM-TV.apk", "projectM-TV-core-2.1.5.aar",
                 "projectM-TV-core.aar", "projectM-TV-2.1.5-mapping.txt", "checksums.txt"]
        api = FakeAPI(existing={"id": 55, "draft": False, "assets": [{"name": n} for n in names],
                                "html_url": "historical release"}, tag_commit="a" * 40)
        self.publish(api, with_touchscreen=False)
        self.assertFalse(self.commands)
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))
        self.assertEqual((self.root / "checksums.txt").read_text(), "historical checksum bytes\n")

    def test_draft_with_retired_remote_assets_is_rejected_without_writes(self):
        api = FakeAPI(existing={"id": 55, "draft": True, "target_commitish": "a" * 40,
                                "assets": [{"name": "projectM-TV-core-native.aar"}]})
        with self.assertRaisesRegex(ValueError, "retired"):
            self.publish(api)
        self.assertFalse(self.commands)
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))

    def test_partial_native_assets_cannot_be_treated_as_a_complete_legacy_release(self):
        names = ["projectM-TV-2.1.5.apk", "projectM-TV.apk", "projectM-TV-core-2.1.5.aar",
                 "projectM-TV-core.aar", "projectM-TV-2.1.5-mapping.txt", "checksums.txt",
                 "projectM-TV-core-native-2.1.5.aar"]
        api = FakeAPI(existing={"id": 55, "draft": False, "assets": [{"name": n} for n in names],
                                "html_url": "partial release"}, tag_commit="a" * 40)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.publish(api)
        self.assertFalse(self.commands)
        self.assertTrue(all(method == "GET" for _, method, _ in api.calls))

    def test_published_capped_and_native_remote_alias_digests_are_checked_when_available(self):
        for alias in ("projectM-TV-core.aar", "projectM-TV-core-native.aar"):
            with self.subTest(alias=alias):
                assets = self.historical_dual_assets()
                next(a for a in assets if a["name"] == alias)["digest"] = "sha256:" + "0" * 64
                api = FakeAPI(existing={"id": 55, "draft": False, "assets": assets,
                                        "html_url": "release"}, tag_commit="a" * 40)
                with self.assertRaisesRegex(ValueError, "alias"):
                    self.publish(api)
                self.assertFalse(self.commands)
                self.assertTrue(all(method == "GET" for _, method, _ in api.calls))


class MilkbeatTests(unittest.TestCase):
    def test_old_or_missing_core_marker_requires_rebuild(self):
        self.assertTrue(module.milkbeat_needs_update("2.1.5", "core v2.1.4 https://github.com/johnneerdael/ProjectM-TV/releases/tag/v2.1.4"))
        self.assertTrue(module.milkbeat_needs_update("2.1.5", "No previous engine recorded"))

    def test_same_or_newer_core_does_not_trigger_duplicate_rebuild(self):
        for version in ("2.1.5", "2.1.6"):
            self.assertFalse(module.milkbeat_needs_update("2.1.5", f"https://github.com/johnneerdael/ProjectM-TV/releases/tag/v{version}"))


if __name__ == "__main__":
    unittest.main()
