#!/usr/bin/env bash
set -euo pipefail

PAYLOAD=${1:?PyInstaller payload directory required}
VERSION=${2:?version required}
OUTPUT_DIR=${3:?output directory required}
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
STAGE=$(mktemp -d)
trap 'rm -rf "${STAGE}"' EXIT

mkdir -p "${STAGE}/DEBIAN" "${STAGE}/opt/strangeutagame" \
  "${STAGE}/usr/share/applications" "${STAGE}/usr/share/metainfo" \
  "${STAGE}/usr/share/icons/hicolor/256x256/apps" "${STAGE}/usr/bin"
cp -a "${PAYLOAD}/." "${STAGE}/opt/strangeutagame/"
sed "s/^Version:.*/Version: ${VERSION}/" "${ROOT}/packaging/linux/debian/control" > "${STAGE}/DEBIAN/control"
install -m755 "${ROOT}/packaging/linux/debian/postinst" "${STAGE}/DEBIAN/postinst"
install -m644 "${ROOT}/packaging/linux/strangeutagame.desktop" "${STAGE}/usr/share/applications/io.github.karaoke_studio.StrangeUtaGame.desktop"
install -m644 "${ROOT}/packaging/linux/io.github.karaoke_studio.StrangeUtaGame.metainfo.xml" "${STAGE}/usr/share/metainfo/"
install -m644 "${ROOT}/src/strange_uta_game/resource/mascot.png" "${STAGE}/usr/share/icons/hicolor/256x256/apps/io.github.karaoke_studio.StrangeUtaGame.png"
ln -s /opt/strangeutagame/StrangeUtaGame "${STAGE}/usr/bin/strangeutagame"
mkdir -p "${OUTPUT_DIR}"
dpkg-deb --root-owner-group --build "${STAGE}" "${OUTPUT_DIR}/strangeutagame_${VERSION}_amd64.deb"
