#!/usr/bin/env bash
set -euo pipefail

PAYLOAD=${1:?PyInstaller payload directory required}
OUTPUT_DIR=${2:?output directory required}
LINUXDEPLOY=${LINUXDEPLOY:?path to checksum-pinned linuxdeploy required}
LINUXDEPLOY_SHA256=${LINUXDEPLOY_SHA256:?linuxdeploy SHA-256 required}

echo "${LINUXDEPLOY_SHA256}  ${LINUXDEPLOY}" | sha256sum --check --status
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
APPDIR="${OUTPUT_DIR}/StrangeUtaGame.AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
cp -a "${PAYLOAD}/." "${APPDIR}/usr/bin/"
cp "${ROOT}/packaging/linux/strangeutagame.desktop" "${APPDIR}/usr/share/applications/"
cp "${ROOT}/src/strange_uta_game/resource/mascot.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/io.github.karaoke_studio.StrangeUtaGame.png"
ln -s "usr/bin/StrangeUtaGame" "${APPDIR}/AppRun"
mkdir -p "${OUTPUT_DIR}"
OUTPUT="${OUTPUT_DIR}/StrangeUtaGame-${VERSION:?VERSION required}-linux-x86_64.AppImage" \
  "${LINUXDEPLOY}" --appdir "${APPDIR}" --output appimage
