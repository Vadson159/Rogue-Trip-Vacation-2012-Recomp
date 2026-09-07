#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $# -ne 1 ]]; then
    echo 'Usage: ./build.sh /path/to/Rogue Trip.cue (or data-track .bin)' >&2
    exit 2
fi
bash scripts/apply-patches.sh
disc_path=$(realpath -- "$1")
jobs=${ROGUETRIP_BUILD_JOBS:-8}
bash psxrecomp/tools/ci/build_emitters.sh --jobs "$jobs"
python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root . --disc "$disc_path" --no-toolchain-download
cmake -S . -B build-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-release --target psx-runtime -j "$jobs"
echo 'Built. Run ./launch.sh to open Rogue Trip Recompiled.'
