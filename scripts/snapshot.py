#!/usr/bin/env python3
"""Snapshot metadata, provenance and packaging helpers (Python standard library)."""
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile

SHA = re.compile(r"[0-9a-f]{40}\Z")
REVISION = re.compile(r"[1-9][0-9]{0,3}\Z")
REPOSITORY = "blood72/gureum-personal-snapshots"
SOURCE = Path("source")
DIST = Path("dist")


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def validate_inputs(ref, revision, publish=False, reviewed=False):
    if ref != "main" and not SHA.fullmatch(ref.lower()):
        raise ValueError("upstream_ref must be main or a full 40-character commit SHA")
    if not REVISION.fullmatch(revision):
        raise ValueError("build_revision must be an integer between 1 and 9999, without leading zeros")
    if publish and not reviewed:
        raise ValueError("Release publication requires distribution_reviewed=true after rights/license review")
    if publish and (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
                    or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        raise ValueError("Releases can only be published from the builder repository's main branch")


def identity(sha, revision):
    if not SHA.fullmatch(sha) or not REVISION.fullmatch(revision):
        raise ValueError("Invalid SHA or build revision")
    version = sha if revision == "1" else f"{sha}-r{revision}"
    return {"upstream_sha": sha, "build_revision": int(revision), "version": version,
            "bundle_version": f"1.{int(revision) // 100}.{int(revision) % 100}",
            "tag": f"snapshot-{version}", "stem": f"Gureum-snapshot-{version}-arm64"}


def metadata():
    data = identity(run("git", "rev-parse", "HEAD", cwd=SOURCE), os.environ["BUILD_REVISION"])
    data.update({
        "upstream_repository": "gureum/gureum",
        "upstream_ref": os.environ["UPSTREAM_REF"],
        "builder_repository": os.environ["GITHUB_REPOSITORY"],
        "builder_sha": os.environ["GITHUB_SHA"],
        "run_url": f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "architecture": "arm64", "signing": "ad-hoc", "notarized": False,
        "hardened_runtime": False,
    })
    DIST.mkdir(exist_ok=True)
    (DIST / "metadata.json").write_text(json.dumps(data, indent=2) + "\n")


def load_metadata():
    return json.loads((DIST / "metadata.json").read_text())


def git_repositories():
    """Actual initialized repositories, including nested submodules and SPM sources."""
    repos = [(SOURCE, "gureum")]
    for marker in SOURCE.rglob(".git"):
        if marker.parent != SOURCE:
            repos.append((marker.parent, f"gureum/{marker.parent.relative_to(SOURCE).as_posix()}"))
    packages = Path("build/DerivedData/SourcePackages/checkouts")
    if packages.is_dir():
        repos.extend((p, f"swift-packages/{p.name}") for p in sorted(packages.iterdir())
                     if p.is_dir() and (p / ".git").exists())
    return sorted(repos, key=lambda x: x[1])


def add_git_archive(output, repo, prefix):
    # git archive excludes credentials, the .git database and generated build products.
    proc = subprocess.Popen(["git", "archive", "--format=tar", "HEAD"], cwd=repo, stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                # Directories for submodule gitlinks are filled by their own archives.
                member.name = f"{prefix}/{member.name}"
                if member.islnk():
                    member.linkname = f"{prefix}/{member.linkname}"
                output.addfile(member, archive.extractfile(member) if member.isfile() else None)
    finally:
        proc.stdout.close()
    if proc.wait() != 0:
        raise RuntimeError(f"git archive failed: {repo}")


def provenance(app):
    data = load_metadata()
    with (app / "Contents/Info.plist").open("rb") as file:
        info = plistlib.load(file)
    info["PersonalSnapshotVersion"] = data["version"]
    info["PersonalSnapshotUpstreamSHA"] = data["upstream_sha"]
    resources = app / "Contents/Resources/PersonalSnapshot"
    resources.mkdir(parents=True, exist_ok=True)
    licenses = resources / "licenses"
    licenses.mkdir()
    repos = git_repositories()
    records = []
    for repo, name in repos:
        records.append({"path": name, "commit": run("git", "rev-parse", "HEAD", cwd=repo),
                        "origin": run("git", "remote", "get-url", "origin", cwd=repo)})
        # Keep original notices unmodified and preserve their relative locations.
        files = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).decode().split("\0")
        for filename in filter(None, files):
            basename = Path(filename).name.lower()
            if basename.startswith(("license", "licence", "copying", "copyright", "notice", "authors")):
                item = repo / filename
                if item.is_file() and not item.is_symlink():
                    target = licenses / name / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
    if not (licenses / "gureum/COPYING").is_file():
        raise RuntimeError("Missing upstream COPYING")
    data["components"] = records
    data["minimum_macos"] = inspect_binaries(app, info["LSMinimumSystemVersion"])
    info["LSMinimumSystemVersion"] = data["minimum_macos"]
    with (app / "Contents/Info.plist").open("wb") as file:
        plistlib.dump(info, file)
    data["toolchain"] = Path("diagnostics/toolchain.txt").read_text()
    locks = sorted(SOURCE.glob("Gureum.xcodeproj/**/Package.resolved"))
    if not locks:
        raise RuntimeError("SPM Package.resolved was not generated; cannot record resolved dependencies")
    shutil.copy2(locks[0], DIST / "Package.resolved")
    (DIST / "metadata.json").write_text(json.dumps(data, indent=2) + "\n")
    for name in ("metadata.json", "Package.resolved"):
        shutil.copy2(DIST / name, resources / name)
    shutil.copy2("docs/DISTRIBUTION.md", resources / "DISTRIBUTION.md")
    shutil.copy2("docs/DISTRIBUTION.md", DIST / "DISTRIBUTION.md")
    with tarfile.open(DIST / "licenses.tar.gz", "w:gz") as archive:
        archive.add(licenses, arcname="licenses")
    with tarfile.open(DIST / f'{data["stem"]}.source.tar.gz', "w:gz") as archive:
        for repo, name in repos:
            add_git_archive(archive, repo, name)
        archive.add(DIST / "Package.resolved", arcname="build-info/Package.resolved")
        archive.add(DIST / "metadata.json", arcname="build-info/metadata.json")
        # Includes generated xcconfig changes; source archives themselves are exact HEADs.
        diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=SOURCE)
        info = tarfile.TarInfo("build-info/upstream-build-changes.diff")
        info.size = len(diff)
        archive.addfile(info, io.BytesIO(diff))
    (Path("diagnostics") / "upstream-status.txt").write_text(
        run("git", "status", "--short", cwd=SOURCE) + "\n")


def verify_app(app):
    data = load_metadata()
    with (app / "Contents/Info.plist").open("rb") as file:
        info = plistlib.load(file)
    if info["CFBundleVersion"] != data["bundle_version"] or info["CFBundleShortVersionString"] != data["bundle_version"]:
        raise RuntimeError("Built app numeric version differs from requested build revision")
    if info.get("PersonalSnapshotVersion") != data["version"] or info.get("PersonalSnapshotUpstreamSHA") != data["upstream_sha"]:
        raise RuntimeError("Built app lost snapshot commit metadata")
    if info.get("LSMinimumSystemVersion") != data["minimum_macos"]:
        raise RuntimeError("Built app minimum macOS differs from its dependencies")
    with Path("diagnostics/entitlements.plist").open("rb") as file:
        actual = plistlib.load(file)
    with (SOURCE / "OSX/Gureum.entitlements").open("rb") as file:
        expected = plistlib.load(file)
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Built app lost upstream entitlements")
    signature = Path("diagnostics/codesign-details.txt").read_text()
    if "Signature=adhoc" not in signature or re.search(r"flags=.*\bruntime\b", signature):
        raise RuntimeError("Expected ad-hoc signing without hardened runtime")
    with Path("diagnostics/preferences-entitlements.plist").open("rb") as file:
        preferences_entitlements = plistlib.load(file)
    if any(preferences_entitlements.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Preferences.prefPane lost upstream entitlements")
    preference_signature = Path("diagnostics/preferences-signature.txt").read_text()
    if "Signature=adhoc" not in preference_signature or re.search(r"flags=.*\bruntime\b", preference_signature):
        raise RuntimeError("Expected Preferences.prefPane ad-hoc signing without hardened runtime")


def macos_minimums(load_commands):
    """Read macOS load commands only; zippered binaries also contain Catalyst targets."""
    versions = []
    for block in re.split(r"(?m)^Load command \d+\s*$", load_commands):
        if re.search(r"\bcmd LC_BUILD_VERSION\b", block):
            platform = re.search(r"\bplatform (\w+)", block)
            if platform is None:
                raise RuntimeError("LC_BUILD_VERSION has no platform")
            if platform[1].lower() in ("1", "macos", "platform_macos"):
                minimum = re.search(r"\bminos ([0-9]+(?:\.[0-9]+){0,2})", block)
                if minimum is None:
                    raise RuntimeError("macOS LC_BUILD_VERSION has no minimum version")
                versions.append(minimum[1])
        elif re.search(r"\bcmd LC_VERSION_MIN_MACOSX\b", block):
            minimum = re.search(r"\bversion ([0-9]+(?:\.[0-9]+){0,2})", block)
            if minimum is None:
                raise RuntimeError("LC_VERSION_MIN_MACOSX has no minimum version")
            versions.append(minimum[1])
    return versions


def inspect_binaries(app, declared_minimum):
    architectures = []
    minimums = ["11", declared_minimum]
    for path in sorted(app.rglob("*")):
        if path.is_file() and not path.is_symlink() and "Mach-O" in run("file", "-b", str(path)):
            arch = run("lipo", "-archs", str(path))
            if arch != "arm64":
                raise RuntimeError(f"Expected arm64-only Mach-O: {path}: {arch}")
            architectures.append(f"{path.relative_to(app)}: {arch}")
            # Dependencies can require a newer OS than the top-level Info.plist.
            load_commands = run("otool", "-l", str(path))
            targets = macos_minimums(load_commands)
            if not targets:
                raise RuntimeError(f"No macOS deployment target in Mach-O: {path}")
            minimums.extend(targets)
    if not architectures:
        raise RuntimeError("No Mach-O executables found")
    Path("diagnostics/architectures.txt").write_text("\n".join(architectures) + "\n")
    return max(minimums, key=lambda value: tuple(int(p) for p in value.split(".")))


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def cask(data, checksum):
    # Input is always validated SHA/revision; never interpolate arbitrary dispatch text.
    identity(data["upstream_sha"], str(data["build_revision"]))
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid tarball SHA256")
    minimum = data["minimum_macos"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", minimum):
        raise ValueError("Invalid minimum macOS version")
    # Apple Silicon requires at least macOS 11 even if upstream declares 10.13.
    if int(minimum.split(".")[0]) < 11:
        minimum = "11"
    return f'''# Generated example; usable only after the matching GitHub Release is published.
# Copy manually into a tap after reviewing DISTRIBUTION.md. No tap is updated here.
cask "gureum-snapshot" do
  version "{data['version']}"
  sha256 "{checksum}"

  url "https://github.com/{REPOSITORY}/releases/download/{data['tag']}/{data['stem']}.app.tar.gz"
  name "Gureum personal snapshot (unofficial)"
  desc "Personal arm64 snapshot of the Gureum Korean input method"
  homepage "https://github.com/{REPOSITORY}"

  livecheck do
    skip "Manually pinned to an upstream commit"
  end

  conflicts_with cask: "gureumkim"
  depends_on arch: :arm64
  depends_on macos: ">= {minimum}"

  input_method "Gureum.app", target: "/Library/Input Methods/Gureum.app"

  caveats <<~EOS
    Unofficial, ad-hoc signed and not notarized. This replaces the official Gureum.app.
    Switch to a macOS input source before installing/upgrading, then log out and in.
    Input Monitoring approval may need to be granted again after replacement.
    Do not launch Gureum.app by double-clicking it.
  EOS
end
'''


def finalize():
    data = load_metadata()
    tarball = DIST / f'{data["stem"]}.app.tar.gz'
    required = [tarball, DIST / f'{data["stem"]}.unsigned.pkg', DIST / f'{data["stem"]}.source.tar.gz']
    if any(not path.is_file() or not path.stat().st_size for path in required):
        raise RuntimeError("Missing or empty snapshot payload")
    (DIST / "gureum-snapshot.rb").write_text(cask(data, sha256(tarball)))
    (DIST / "RELEASE_NOTES.md").write_text(f'''# Gureum personal snapshot (unofficial)

- Upstream: https://github.com/gureum/gureum/commit/{data['upstream_sha']}
- Snapshot/cask version: `{data['version']}`
- Numeric Apple bundle/build version: `{data['bundle_version']}` (full SHA in PersonalSnapshotVersion/PersonalSnapshotUpstreamSHA)
- Builder: https://github.com/{data['builder_repository']}/commit/{data['builder_sha']}
- Build logs: {data['run_url']} (attempt {data['run_attempt']})
- arm64 only; ad-hoc signed app, unsigned installer; not notarized; hardened runtime disabled.
- Debug unit tests and static bundle checks are required, but interactive input-method behavior is not tested.

The `.app.tar.gz` preserves the app bundle for manual installation/Homebrew. The unsigned
`.pkg` installs the same app in `/Library/Input Methods`. The cask is an example for a
manual tap update, and its URL only works after this prerelease is published.

`metadata.json`, `Package.resolved`, the source archive and `licenses.tar.gz` record the
exact build inputs and discovered notices. Review `DISTRIBUTION.md`: these files do not
establish that logo/icon permissions or every redistribution obligation have been met.
Source bundles contain tracked upstream, recursive submodules and resolved SPM checkouts;
any vendored binary dependencies require a separate rights/source review.

Switch to a system input source before installing/upgrading. Log out and back in after
installation; Input Monitoring may require re-approval. Do not double-click Gureum.app.
If macOS blocks the app, review the build and use macOS's app-specific security controls;
this workflow does not disable Gatekeeper or clear quarantine automatically.

Artifacts-only runs do not create a Release. Actions artifacts follow repository access
and retention rules and must not be treated as private merely because no Release exists.
''')
    files = sorted(p for p in DIST.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (DIST / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in files))


def main():
    command = sys.argv[1]
    if command == "validate-inputs":
        validate_inputs(os.environ["UPSTREAM_REF"], os.environ["BUILD_REVISION"],
                        os.environ.get("PUBLISH_RELEASE") == "true",
                        os.environ.get("DISTRIBUTION_REVIEWED") == "true")
    elif command == "metadata":
        metadata()
    elif command == "provenance":
        provenance(Path(sys.argv[2]))
    elif command == "verify-app":
        verify_app(Path(sys.argv[2]))
    elif command == "finalize":
        finalize()
    else:
        raise ValueError(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
