#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
patch="$PWD/patches/recomp-ui-disc-drop.patch"
if git -C recomp-ui apply --reverse --check "$patch" 2>/dev/null; then
    echo 'Launcher patch already applied.'
elif git -C recomp-ui apply --check "$patch"; then
    git -C recomp-ui apply "$patch"
    echo 'Applied launcher disc-drop patch.'
else
    echo 'Launcher patch does not match this checkout; use the pinned submodule revision.' >&2
    exit 1
fi
