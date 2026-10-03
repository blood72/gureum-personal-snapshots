import importlib.util
import io
import json
import os
import plistlib
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

spec = importlib.util.spec_from_file_location("verify_artifacts", ROOT / "scripts/verify-artifacts.py")
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


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
    def test_packaged_metadata_must_match_even_with_valid_checksums(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = snapshot.identity("a" * 40, "1") | {
                "builder_repository": snapshot.REPOSITORY, "builder_sha": "b" * 40,
                "run_url": "https://github.com/test/run", "run_attempt": "1", "minimum_macos": "11"}
            (directory / "metadata.json").write_text(json.dumps(data))
            (directory / "Package.resolved").write_bytes(b"lockfile fixture")
            (directory / "DISTRIBUTION.md").write_text("fixture")
            (directory / f'{data["stem"]}.unsigned.pkg').write_bytes(b"xar!fixture")

            def write_archive(name, members):
                with tarfile.open(directory / name, "w:gz") as archive:
                    for path, contents in members.items():
                        member = tarfile.TarInfo(path)
                        member.size = len(contents)
                        archive.addfile(member, io.BytesIO(contents))

            info = {"CFBundleVersion": data["bundle_version"],
                    "CFBundleShortVersionString": data["bundle_version"],
                    "PersonalSnapshotVersion": data["version"],
                    "PersonalSnapshotUpstreamSHA": data["upstream_sha"]}
            resources = "Gureum.app/Contents/Resources/PersonalSnapshot"
            app_members = {"Gureum.app/Contents/Info.plist": plistlib.dumps(info),
                           f"{resources}/metadata.json": json.dumps(data).encode(),
                           f"{resources}/Package.resolved": b"lockfile fixture"}
            write_archive(f'{data["stem"]}.app.tar.gz', app_members)
            write_archive(f'{data["stem"]}.source.tar.gz', {
                "build-info/metadata.json": json.dumps(data).encode(),
                "build-info/Package.resolved": b"lockfile fixture",
                "build-info/upstream-build-changes.diff": b"",
                "gureum/COPYING": b"notice fixture"})
            write_archive("licenses.tar.gz", {"licenses/gureum/COPYING": b"notice fixture"})
            with patch.object(snapshot, "DIST", directory):
                snapshot.finalize()
            self.assertEqual(artifacts.verify(directory, "b" * 40)["checksums_verified"], 9)
            # A freshly recalculated checksum must not mask conflicting embedded SHA.
            info["PersonalSnapshotUpstreamSHA"] = "c" * 40
            app_members["Gureum.app/Contents/Info.plist"] = plistlib.dumps(info)
            write_archive(f'{data["stem"]}.app.tar.gz', app_members)
            with patch.object(snapshot, "DIST", directory):
                snapshot.finalize()
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                artifacts.verify(directory, "b" * 40)

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
