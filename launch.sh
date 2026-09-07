#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exe="$PWD/build-release/Rogue_Trip_Recompiled"
if [[ ! -x "$exe" ]]; then
    echo 'Build first with ./build.sh /path/to/game.cue' >&2
    exit 1
fi
args=(--game "$PWD/game.toml" --launcher)
if [[ $# -gt 0 ]]; then
    args+=(--disc "$1")
    shift
fi
exec "$exe" "${args[@]}" "$@"
