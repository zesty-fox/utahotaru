#!/usr/bin/env bash
set -euo pipefail

APP=${1:?application bundle required}
DMG=${2:?DMG required}
while IFS= read -r -d '' candidate; do
  if file "${candidate}" | grep -q 'Mach-O'; then
    archs=$(lipo -archs "${candidate}")
    [[ " ${archs} " == *" arm64 "* && " ${archs} " == *" x86_64 "* ]]
  fi
done < <(find "${APP}" -type f -print0)
codesign --verify --deep --strict --verbose=2 "${APP}"
xcrun stapler validate "${DMG}"
spctl --assess --type open --context context:primary-signature --verbose=2 "${DMG}"
