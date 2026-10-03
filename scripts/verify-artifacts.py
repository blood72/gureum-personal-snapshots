#!/usr/bin/env python3
"""Inspect downloaded artifacts without extracting or executing upstream files."""
import importlib.util
import json
from pathlib import Path
import plistlib
import sys
import tarfile

from snapshot import cask, verify_flat_pkg

spec = importlib.util.spec_from_file_location(
    "publish_release", Path(__file__).with_name("publish-release.py"))
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


def archive_file(archive, name):
    matches = [member for member in archive.getmembers() if member.name == name]
    if len(matches) != 1 or not matches[0].isfile():
        raise ValueError(f"Expected one regular archive entry: {name}")
    return archive.extractfile(matches[0]).read()


def verify(directory, builder_sha):
    data, names = publish.verify_payload(directory, builder_sha)
    stem = data["stem"]
    with tarfile.open(directory / f"{stem}.app.tar.gz") as archive:
        info = plistlib.loads(archive_file(archive, "Gureum.app/Contents/Info.plist"))
        expected = {
            "CFBundleVersion": data["bundle_version"],
            "CFBundleShortVersionString": data["short_version"],
            "PersonalSnapshotVersion": data["version"],
            "PersonalSnapshotUpstreamSHA": data["upstream_sha"],
            "LSMinimumSystemVersion": data["minimum_macos"],
        }
        if any(info.get(key) != value for key, value in expected.items()):
            raise ValueError("Packaged app version/provenance mismatch")
        preferences = plistlib.loads(archive_file(
            archive, "Gureum.app/Contents/Resources/Preferences.prefPane/Contents/Info.plist"))
        if any(preferences.get(key) != value for key, value in expected.items() if key != "LSMinimumSystemVersion"):
            raise ValueError("Packaged Preferences version/provenance mismatch")
        resources = "Gureum.app/Contents/Resources/PersonalSnapshot"
        if json.loads(archive_file(archive, f"{resources}/metadata.json")) != data:
            raise ValueError("Packaged app metadata mismatch")
        if archive_file(archive, f"{resources}/Package.resolved") != (directory / "Package.resolved").read_bytes():
            raise ValueError("Packaged app dependency lockfile mismatch")
    with tarfile.open(directory / f"{stem}.source.tar.gz") as archive:
        if json.loads(archive_file(archive, "build-info/metadata.json")) != data:
            raise ValueError("Source archive metadata mismatch")
        if archive_file(archive, "build-info/Package.resolved") != (directory / "Package.resolved").read_bytes():
            raise ValueError("Source archive dependency lockfile mismatch")
        archive_file(archive, "gureum/COPYING")
        archive_file(archive, "build-info/upstream-build-changes.diff")
    with tarfile.open(directory / "licenses.tar.gz") as archive:
        archive_file(archive, "licenses/gureum/COPYING")
    verify_flat_pkg(directory / f"{stem}.unsigned.pkg", data)
    checksum = publish.sha256(directory / f"{stem}.app.tar.gz")
    if (directory / "gureum-snapshot.rb").read_text() != cask(data, checksum):
        raise ValueError("Cask does not match packaged app")
    return {"upstream_sha": data["upstream_sha"], "builder_sha": builder_sha,
            "display_version": data["version"], "short_version": data["short_version"],
            "bundle_version": data["bundle_version"], "pkg_version": data["pkg_version"],
            "files": names, "checksums_verified": len(names) - 1}


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1]), sys.argv[2]), indent=2))
