#!/bin/bash
set -euo pipefail

[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]]
[[ -d "$DEVELOPER_DIR" ]]
mkdir -p diagnostics dist
{
  sw_vers
  xcodebuild -version
  xcrun --sdk macosx --show-sdk-version
  printf 'Runner image: %s %s\n' "${ImageOS:-unknown}" "${ImageVersion:-unknown}"
} | tee diagnostics/toolchain.txt

version=$(python3 -c 'import json; print(json.load(open("dist/metadata.json"))["bundle_version"])')
root="$PWD"
common=(
  -project "$root/source/Gureum.xcodeproj" -scheme OSX -sdk macosx
  -derivedDataPath "$root/build/DerivedData"
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES
  # Upstream's 10.13 target embeds pre-Apple-Silicon, Intel-only Swift runtimes.
  MACOSX_DEPLOYMENT_TARGET=11.0
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY=- DEVELOPMENT_TEAM=
  ENABLE_HARDENED_RUNTIME=NO
  "VERSION=$version" "CURRENT_PROJECT_VERSION=$version" "MARKETING_VERSION=$version"
)

# Resolve once, then require that same lockfile during both configurations.
xcodebuild "${common[@]}" -resolvePackageDependencies \
  | tee diagnostics/resolve.log
xcodebuild "${common[@]}" -disableAutomaticPackageResolution \
  -configuration Debug -destination 'platform=macOS,arch=arm64' \
  -resultBundlePath "$root/diagnostics/DebugTests.xcresult" test \
  | tee diagnostics/test.log

# Upstream's version build phase writes this file, including a Debug suffix.
git -C source restore -- OSX/Version.xcconfig
# Do not archive: upstream's archive post-action requires its own Developer ID.
xcodebuild "${common[@]}" -disableAutomaticPackageResolution \
  -configuration Release -destination 'generic/platform=macOS' build \
  | tee diagnostics/build.log

app="$root/build/DerivedData/Build/Products/Release/Gureum.app"
[[ -d "$app" ]]
python3 scripts/snapshot.py provenance "$app"
# Adding provenance/resources changes the outer seal. Preserve upstream entitlements.
codesign --force --sign - --timestamp=none \
  --entitlements source/OSX/Gureum.entitlements "$app"
codesign --verify --deep --strict --verbose=2 "$app" 2>&1 \
  | tee diagnostics/codesign-verify.txt
codesign --display --verbose=4 "$app" 2> diagnostics/codesign-details.txt
codesign --display --entitlements :- "$app" > diagnostics/entitlements.plist
# Preferences is inside Resources, so outer --deep verification is not sufficient.
prefs="$app/Contents/Resources/Preferences.prefPane"
[[ -d "$prefs" ]]
codesign --verify --strict --verbose=2 "$prefs" 2>&1 | tee diagnostics/preferences-verify.txt
codesign --display --verbose=4 "$prefs" 2> diagnostics/preferences-signature.txt
codesign --display --entitlements :- "$prefs" > diagnostics/preferences-entitlements.plist
while IFS= read -r -d '' framework; do
  codesign --verify --strict --verbose=2 "$framework"
done < <(find "$app/Contents/Frameworks" -type d -name '*.framework' -print0)
python3 scripts/snapshot.py verify-app "$app"

stem=$(python3 -c 'import json; print(json.load(open("dist/metadata.json"))["stem"])')
# tar preserves app symlinks/modes; never upload the bare .app with upload-artifact.
COPYFILE_DISABLE=1 tar -czf "dist/$stem.app.tar.gz" -C "$(dirname "$app")" Gureum.app
productbuild --component "$app" '/Library/Input Methods' "dist/$stem.unsigned.pkg"
python3 scripts/snapshot.py finalize
python3 scripts/verify-artifacts.py dist "$GITHUB_SHA" | tee diagnostics/artifact-inspection.json
# Expand the installer to ensure productbuild preserved the signed app payload.
pkg_inspection="$root/build/pkg-inspection"
pkgutil --expand-full "dist/$stem.unsigned.pkg" "$pkg_inspection"
packaged_app=$(find "$pkg_inspection" -type d -name Gureum.app)
[[ -n "$packaged_app" && -d "$packaged_app" ]]
cmp "$app/Contents/Info.plist" "$packaged_app/Contents/Info.plist"
cmp "$app/Contents/Resources/PersonalSnapshot/metadata.json" \
  "$packaged_app/Contents/Resources/PersonalSnapshot/metadata.json"
codesign --verify --deep --strict --verbose=2 "$packaged_app" 2>&1 \
  | tee diagnostics/pkg-app-verify.txt
pkg_signature_status=0
pkgutil --check-signature "dist/$stem.unsigned.pkg" > diagnostics/pkg-signature.txt 2>&1 \
  || pkg_signature_status=$?
# The reported status establishes signing; a successful inspection alone does not.
if ! grep -F 'Status: no signature' diagnostics/pkg-signature.txt; then
  cat diagnostics/pkg-signature.txt >&2
  printf 'Expected an unsigned installer (pkgutil exit %s)\n' "$pkg_signature_status" >&2
  exit 1
fi
ruby -c dist/gureum-snapshot.rb
cat dist/RELEASE_NOTES.md >> "$GITHUB_STEP_SUMMARY"
