#!/usr/bin/env python3
"""Publish verified outputs; never overwrite an existing tag, draft, or release."""
import json
import os
from pathlib import Path
import subprocess

from snapshot import REPOSITORY, SHA, identity, sha256


def api_get(endpoint):
    result = subprocess.run(["gh", "api", endpoint], text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)
    # A network error, permission failure or rate limit must not mean 'not found'.
    if "(HTTP 404)" in result.stderr:
        return None
    raise RuntimeError(f"GitHub lookup failed: {result.stderr.strip()}")


def verify_payload(directory, builder_sha):
    data = json.loads((directory / "metadata.json").read_text())
    expected = identity(data["upstream_sha"], str(data["build_revision"]), data["source_version"])
    if any(data[key] != value for key, value in expected.items()):
        raise ValueError("Inconsistent snapshot identity")
    if data["builder_repository"] != REPOSITORY or data["builder_sha"] != builder_sha:
        raise ValueError("Artifacts do not belong to this builder commit")
    stem = data["stem"]
    expected_files = {f"{stem}.app.tar.gz", f"{stem}.unsigned.pkg", f"{stem}.source.tar.gz",
                      "metadata.json", "Package.resolved", "licenses.tar.gz", "DISTRIBUTION.md",
                      "RELEASE_NOTES.md", "gureum-snapshot.rb", "SHA256SUMS"}
    actual_files = {p.name for p in directory.iterdir()}
    if actual_files != expected_files:
        raise ValueError("Artifact file list differs from expected release assets")
    if any(p.is_symlink() or not p.is_file() for p in directory.iterdir()):
        raise ValueError("Release assets must be regular files")
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if name in checksums or name not in expected_files - {"SHA256SUMS"}:
            raise ValueError("Duplicate or unexpected checksum entry")
        if sha256(directory / name) != digest:
            raise ValueError(f"Checksum mismatch: {name}")
        checksums[name] = digest
    if set(checksums) != expected_files - {"SHA256SUMS"}:
        raise ValueError("Incomplete checksum manifest")
    return data, sorted(expected_files)


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    builder_sha = os.environ["GITHUB_SHA"]
    if repo != REPOSITORY or not SHA.fullmatch(builder_sha) or os.environ["GITHUB_REF"] != "refs/heads/main":
        raise ValueError("Publication is restricted to this repository's main branch")
    directory = Path("dist")
    data, names = verify_payload(directory, builder_sha)
    tag = data["tag"]
    for endpoint in (f"repos/{repo}/releases/tags/{tag}", f"repos/{repo}/git/ref/tags/{tag}"):
        if api_get(endpoint) is not None:
            raise RuntimeError(f"{tag} already exists. Nothing was changed. Keep the existing release or increment build_revision.")
    # gh creates/uploads as a draft first. A partial upload remains a draft for review;
    # reruns never overwrite or automatically delete it.
    subprocess.run([
        "gh", "release", "create", tag, *[str(directory / name) for name in names],
        "--repo", repo, "--target", builder_sha, "--draft", "--prerelease", "--latest=false",
        "--title", f"Gureum personal snapshot {data['version']}",
        "--notes-file", str(directory / "RELEASE_NOTES.md"),
    ], check=True)
    release = api_get(f"repos/{repo}/releases/tags/{tag}")
    uploaded = {asset["name"]: asset for asset in release["assets"]}
    if not release["draft"] or set(uploaded) != set(names):
        raise RuntimeError("Draft asset verification failed; draft left unpublished")
    for name in names:
        asset = uploaded[name]
        if asset["state"] != "uploaded" or asset["size"] != (directory / name).stat().st_size:
            raise RuntimeError("Incomplete upload; draft left unpublished")
        digest = asset.get("digest")
        if digest and digest != f"sha256:{sha256(directory / name)}":
            raise RuntimeError("Uploaded digest mismatch; draft left unpublished")
    subprocess.run(["gh", "release", "edit", tag, "--repo", repo, "--draft=false",
                    "--prerelease", "--latest=false"], check=True)
    release = api_get(f"repos/{repo}/releases/tags/{tag}")
    if release["draft"] or not release["prerelease"]:
        raise RuntimeError("Release publication was not verified")
    print(release["html_url"])
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(f"\nPublished prerelease: {release['html_url']}\n")


if __name__ == "__main__":
    main()
