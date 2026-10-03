#!/bin/bash
set -euo pipefail

[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]]
[[ -d "$DEVELOPER_DIR" ]]
mkdir -p diagnostics dist build
{
  sw_vers
  xcodebuild -version
  xcrun --sdk macosx --show-sdk-version
  printf 'Runner image: %s %s\n' "${ImageOS:-unknown}" "${ImageVersion:-unknown}"
} | tee diagnostics/toolchain.txt

# Check the actual tool's handling of non-executable Mach-O entitlements early.
# macOS 15+ requires an explicit option for library/bundle entitlements.
printf 'int signing_probe(void) { return 0; }\n' > build/signing-probe.c
xcrun clang -arch arm64 -bundle build/signing-probe.c -o build/signing-probe.bundle
codesign --force --sign - --timestamp=none --generate-entitlement-der \
  --force-library-entitlements --entitlements source/OSX/Gureum.entitlements \
  build/signing-probe.bundle
codesign --verify --strict --verbose=2 build/signing-probe.bundle
codesign --display --entitlements :- build/signing-probe.bundle \
  > diagnostics/signing-probe-entitlements.plist
python3 - <<'PY'
import plistlib
from pathlib import Path
expected = plistlib.loads(Path('source/OSX/Gureum.entitlements').read_bytes())
actual = plistlib.loads(Path('diagnostics/signing-probe-entitlements.plist').read_bytes())
if any(actual.get(key) != value for key, value in expected.items()):
    raise SystemExit('Mach-O bundle signing probe lost required entitlements')
print('Mach-O bundle signing/entitlements probe: passed')
PY

python3 scripts/snapshot.py prepare-source
version=$(python3 -c 'import json; print(json.load(open("dist/metadata.json"))["bundle_version"])')
short_version=$(python3 -c 'import json; print(json.load(open("dist/metadata.json"))["short_version"])')
pkg_version=$(python3 -c 'import json; print(json.load(open("dist/metadata.json"))["pkg_version"])')
root="$PWD"
common=(
  -project "$root/source/Gureum.xcodeproj" -scheme OSX -sdk macosx
  -derivedDataPath "$root/build/DerivedData"
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES
  # Upstream's 10.13 target embeds pre-Apple-Silicon, Intel-only Swift runtimes.
  MACOSX_DEPLOYMENT_TARGET=11.0
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY=- DEVELOPMENT_TEAM=
  ENABLE_HARDENED_RUNTIME=NO
  "VERSION=$version" "CURRENT_PROJECT_VERSION=$version" "MARKETING_VERSION=$short_version"
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
# Xcode's Swift concurrency back-deployment runtime contains Intel and arm64 slices.
# Keep only the verified arm64 slice of top-level Swift runtimes, then re-sign them.
# Other Mach-O files still have to pass the strict arm64 check without alteration.
for runtime in "$app"/Contents/Frameworks/libswift*.dylib; do
  [[ -f "$runtime" ]] || continue
  [[ ! -L "$runtime" ]]
  runtime_archs=$(lipo -archs "$runtime")
  printf '%s: %s\n' "$(basename "$runtime")" "$runtime_archs" \
    | tee -a diagnostics/swift-runtime-slices.txt
  if [[ "$runtime_archs" != arm64 ]]; then
    lipo "$runtime" -verify_arch arm64
    lipo "$runtime" -thin arm64 -output "$runtime.arm64"
    chmod "$(stat -f '%Lp' "$runtime")" "$runtime.arm64"
    mv "$runtime.arm64" "$runtime"
    codesign --force --sign - --timestamp=none "$runtime"
    codesign --verify --strict --verbose=2 "$runtime"
  fi
done
python3 scripts/snapshot.py provenance "$app"
# Preferences is a Mach-O library bundle, requiring explicit library entitlements.
# Sign the copied bundle first so the outer app seal covers its final signature.
prefs="$app/Contents/Resources/Preferences.prefPane"
[[ -d "$prefs" ]]
codesign --force --sign - --timestamp=none --generate-entitlement-der \
  --force-library-entitlements --entitlements source/OSX/Gureum.entitlements "$prefs"
# Adding provenance/resources changes the outer seal. Preserve upstream entitlements.
codesign --force --sign - --timestamp=none --generate-entitlement-der \
  --entitlements source/OSX/Gureum.entitlements "$app"
codesign --verify --deep --strict --verbose=2 "$app" 2>&1 \
  | tee diagnostics/codesign-verify.txt
codesign --display --verbose=4 "$app" 2> diagnostics/codesign-details.txt
codesign --display --entitlements :- "$app" > diagnostics/entitlements.plist
# Preferences is inside Resources, so outer --deep verification is not sufficient.
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
productbuild --version "$pkg_version" --component "$app" '/Library/Input Methods' "dist/$stem.unsigned.pkg"
python3 scripts/snapshot.py finalize
python3 scripts/verify-artifacts.py dist "$GITHUB_SHA" | tee diagnostics/artifact-inspection.json
# Expand the installer to ensure productbuild preserved the signed app payload.
pkg_inspection="$root/build/pkg-inspection"
pkgutil --expand-full "dist/$stem.unsigned.pkg" "$pkg_inspection"
python3 scripts/snapshot.py verify-pkg "$pkg_inspection" | tee diagnostics/pkg-versions.txt
# Record installed tool documentation and ensure official update logic stayed intact.
MANWIDTH=100 man pkgbuild | col -b > diagnostics/pkgbuild-man.txt
git -C source diff --exit-code -- OSX/UpdateManager.swift OSXCore/BundleVersion.swift \
  OSXCore/Configuration.swift Preferences/PreferenceViewController.swift
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
