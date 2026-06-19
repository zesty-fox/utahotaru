#!/usr/bin/env bash
set -euo pipefail

APP=${1:?application bundle required}
DMG=${2:?output DMG required}
APPLE_SIGNING_IDENTITY=${APPLE_SIGNING_IDENTITY:?Apple signing identity required}
APPLE_ID=${APPLE_ID:?Apple ID required}
APPLE_TEAM_ID=${APPLE_TEAM_ID:?Apple team ID required}
APPLE_APP_PASSWORD=${APPLE_APP_PASSWORD:?Apple app-specific password required}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ENTITLEMENTS="${ROOT}/packaging/macos/entitlements.plist"

while IFS= read -r -d '' candidate; do
  if file "${candidate}" | grep -q 'Mach-O'; then
    archs=$(lipo -archs "${candidate}")
    [[ " ${archs} " == *" arm64 "* && " ${archs} " == *" x86_64 "* ]] || {
      echo "Non-universal Mach-O: ${candidate} (${archs})" >&2
      exit 1
    }
  fi
done < <(find "${APP}" -type f -print0)

while IFS= read -r -d '' candidate; do
  if file "${candidate}" | grep -q 'Mach-O'; then
    codesign --force --options runtime --timestamp \
      --sign "${APPLE_SIGNING_IDENTITY}" "${candidate}"
  fi
done < <(find "${APP}/Contents" -depth -type f -print0)

codesign --force --deep --options runtime --timestamp \
  --entitlements "${ENTITLEMENTS}" --sign "${APPLE_SIGNING_IDENTITY}" "${APP}"
codesign --verify --deep --strict --verbose=2 "${APP}"

mkdir -p "$(dirname "${DMG}")"
rm -f "${DMG}"
hdiutil create -volname StrangeUtaGame -srcfolder "${APP}" -ov -format UDZO "${DMG}"
xcrun notarytool submit "${DMG}" --wait \
  --apple-id "${APPLE_ID}" --team-id "${APPLE_TEAM_ID}" --password "${APPLE_APP_PASSWORD}"
xcrun stapler staple "${DMG}"
xcrun stapler validate "${DMG}"
spctl --assess --type open --context context:primary-signature --verbose=2 "${DMG}"
