import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import snapshot

spec = importlib.util.spec_from_file_location("publish_release", ROOT / "scripts/publish-release.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class Inputs(unittest.TestCase):
    def test_valid_refs(self):
        for ref in ("main", "a" * 40, "A" * 40):
            snapshot.validate_inputs(ref, "1")

    def test_reject_ref_injection_and_other_refs(self):
        for ref in ("HEAD", "refs/heads/main", "v1.0", "a" * 39, "a" * 41, "main\n", "$(id)", "--help"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                snapshot.validate_inputs(ref, "1")

    def test_bad_revisions(self):
        for value in ("0", "01", "-1", "1.0", "10000", "2\n", "$(id)", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                snapshot.validate_inputs("main", value)

    def test_review_and_repository_gates(self):
        with self.assertRaises(ValueError):
            snapshot.validate_inputs("main", "1", True, False)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": snapshot.REPOSITORY, "GITHUB_REF": "refs/heads/main"}):
            snapshot.validate_inputs("main", "1", True, True)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "other/repo", "GITHUB_REF": "refs/heads/main"}):
            with self.assertRaises(ValueError):
                snapshot.validate_inputs("main", "1", True, True)

    def test_revision_identity(self):
        sha = "a" * 40
        self.assertEqual(snapshot.identity(sha, "1")["version"], sha)
        self.assertEqual(snapshot.identity(sha, "9999")["bundle_version"], "1.99.99")
        self.assertEqual(snapshot.identity(sha, "2")["tag"], f"snapshot-{sha}-r2")

    def test_cask(self):
        data = snapshot.identity("a" * 40, "2") | {"minimum_macos": "10.13"}
        cask = snapshot.cask(data, "b" * 64)
        self.assertIn('version "' + "a" * 40 + '-r2"', cask)
        self.assertIn('depends_on macos: ">= 11"', cask)
        self.assertIn('conflicts_with cask: "gureumkim"', cask)
        self.assertIn('input_method "Gureum.app"', cask)
        self.assertNotIn("--no-quarantine", cask)


class Packaging(unittest.TestCase):
    def test_tracked_archive_excludes_git_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "COPYING").write_text("test notice")
            subprocess.run(["git", "add", "COPYING"], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "fixture"], cwd=repo, check=True)
            (repo / "not-source.secret").write_text("excluded")
            output = Path(temporary) / "source.tar.gz"
            with tarfile.open(output, "w:gz") as archive:
                snapshot.add_git_archive(archive, repo, "gureum")
            with tarfile.open(output) as archive:
                self.assertEqual(archive.getnames(), ["gureum/COPYING"])
                self.assertEqual(archive.extractfile("gureum/COPYING").read(), b"test notice")

    def test_payload_and_checksum_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = snapshot.identity("a" * 40, "1") | {
                "builder_repository": snapshot.REPOSITORY, "builder_sha": "b" * 40,
                "run_url": "https://github.com/test/run", "run_attempt": "1", "minimum_macos": "11"}
            (directory / "metadata.json").write_text(json.dumps(data))
            for suffix in ("app.tar.gz", "unsigned.pkg", "source.tar.gz"):
                (directory / f'{data["stem"]}.{suffix}').write_bytes(b"test fixture, not a real app")
            for name in ("Package.resolved", "licenses.tar.gz", "DISTRIBUTION.md"):
                (directory / name).write_text("fixture")
            with patch.object(snapshot, "DIST", directory):
                snapshot.finalize()
            verified, files = publish.verify_payload(directory, "b" * 40)
            self.assertEqual(verified["tag"], data["tag"])
            self.assertEqual(len(files), 10)
            (directory / "DISTRIBUTION.md").write_text("tampered")
            with self.assertRaises(ValueError):
                publish.verify_payload(directory, "b" * 40)

    def test_api_errors_fail_closed(self):
        failure = subprocess.CompletedProcess([], 1, stdout="", stderr="gh: Forbidden (HTTP 403)")
        with patch.object(subprocess, "run", return_value=failure), self.assertRaises(RuntimeError):
            publish.api_get("test")
        missing = subprocess.CompletedProcess([], 1, stdout="", stderr="gh: Not Found (HTTP 404)")
        with patch.object(subprocess, "run", return_value=missing):
            self.assertIsNone(publish.api_get("test"))


if __name__ == "__main__":
    unittest.main()
