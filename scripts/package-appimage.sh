#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
root=$PWD
version=$(cat VERSION)
: "${APPIMAGETOOL:=$root/build-tools/appimagetool.AppImage}"
cmake -S . -B build-setup -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DPSXRECOMP_FORCE_SETUP_HOST=ON -DPSXRECOMP_ALLOW_NO_BIOS=ON \
    -DPSX_SETUP_WIZARD=ON -DPSX_DEBUG_TOOLS=OFF
cmake --build build-setup --target psx-runtime -j "${ROGUETRIP_BUILD_JOBS:-8}"
bash psxrecomp/tools/package_setup_host.sh \
    --build-dir build-setup --artifact linux-x64 --zip-prefix roguetrip \
    --exe-name Rogue_Trip_Recompiled --display-name 'Rogue Trip Recompiled' \
    --recompiler-build build-recompiler --exclude-dev-mods \
    --project-file CMakeLists.txt --project-file game.toml --project-file VERSION \
    --project-file codegen_setup.c --project-file codegen_setup.h \
    --project-file README.md --project-file LICENSE --project-file THIRD_PARTY_NOTICES.md \
    --project-file catalog_identity.json --project-file framework_pins.txt \
    --project-dir seeds --project-dir patches
appdir="$root/dist/RogueTripRecomp.AppDir"
rm -rf -- "$appdir"
mkdir -p "$appdir/usr/share/roguetrip" "$appdir/usr/lib"
cp -a dist/stage-setup-linux-x64/. "$appdir/usr/share/roguetrip/"
# Bundle non-driver runtime libraries; keep OpenGL and the C runtime system-owned.
for soname in libSDL3.so.0 libz.so.1; do
    library=$(ldd build-setup/Rogue_Trip_Recompiled | awk -v n="$soname" '$1 == n {print $3}')
    test -f "$library"
    cp -L "$library" "$appdir/usr/lib/$soname"
done
mkdir -p "$appdir/usr/share/roguetrip/licenses"
cp packaging/licenses/* "$appdir/usr/share/roguetrip/licenses/"
cp packaging/AppRun "$appdir/AppRun"
cp packaging/roguetrip.desktop "$appdir/roguetrip.desktop"
cp psxrecomp/assets/psxrecomp.png "$appdir/roguetrip.png"
cp psxrecomp/assets/psxrecomp.png "$appdir/.DirIcon"
cp VERSION "$appdir/VERSION"
chmod +x "$appdir/AppRun"
desktop-file-validate "$appdir/roguetrip.desktop"
# Game-derived code and original images must never enter a release.
test ! -e "$appdir/usr/share/roguetrip/generated"
test ! -e "$appdir/usr/share/roguetrip/disc"
if nm build-setup/Rogue_Trip_Recompiled | grep -q 'psx_game_dispatch'; then
    echo 'Refusing to package a game-linked executable.' >&2
    exit 1
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --no-appstream --runtime-file "$root/build-tools/runtime-x86_64" \
    "$appdir" "$root/dist/RogueTripRecomp-$version-linux-x86_64.AppImage"
(cd dist && sha256sum "RogueTripRecomp-$version-linux-x86_64.AppImage" > SHA256SUMS)
