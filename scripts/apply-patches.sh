#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

apply_patch() {
    local dependency=$1 patch="$PWD/patches/$2"
    if git -C "$dependency" apply --reverse --check "$patch" 2>/dev/null; then
        echo "$2 already applied."
    else
        git -C "$dependency" apply --check "$patch"
        git -C "$dependency" apply "$patch"
        echo "Applied $2."
    fi
}

apply_patch recomp-ui recomp-ui-disc-drop.patch
apply_patch psxrecomp psxrecomp-multi-region.patch
