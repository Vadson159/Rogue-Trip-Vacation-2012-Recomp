# Developing Rogue Trip Recompiled

## Windows x64

1. Install Git for Windows, PowerShell 7 and Python 3.11 or later. Clone with
   `--recurse-submodules` and `core.autocrlf=false` for Git Bash compatibility.
2. Extract the Windows x64 cmake-clang-v1 pack from the
   [RetComM 1.0.14 release](https://github.com/TechnicallyComputers/retcomm-toolchains/releases/tag/v1.0.14).
   Set `PSXRECOMP_TOOLCHAIN_DIR` to the directory containing `bin\cmake.exe`.
   The scripts also look in the RetComM toolchain cache under `%LOCALAPPDATA%`.
3. Install the overlay analysis dependency with `python -m pip install rabbitizer`.
   Set `ROGUETRIP_PYTHON` to a virtual environment's Python if needed. Optionally
   point `ROGUETRIP_TCC_DIR` to a local TinyCC installation for runtime overlay
   autocompilation. The build compiles its ahead-of-time cache with the toolchain's GCC driver.
4. Keep each CUE beside its referenced BIN files. Provide a `SLUS-00643` CUE and a
   `SLES-01417` CUE to build both backends. FullRUS is the NTSC-U input used for the
   recorded Windows tests. With the standard directory names used in `game.toml`,
   the scripts also look for discs under a sibling `_game_files` directory or
   the directory set in `ROGUETRIP_GAME_FILES`.

```powershell
.\build.ps1 -UsDisc 'D:\discs\US.cue' -EuropeDisc 'D:\discs\Europe.cue'
.\launch.ps1 -Disc 'D:\discs\Europe.cue'
.\launch.ps1 -Disc 'D:\discs\Europe.cue' -DirectBoot
```

Use `-BuildType RelWithDebInfo` for a build with the local debug server. The
runtime is written to `build-release` or `build-relwithdebinfo` depending on
the build type. `-SetupHost` builds the setup launcher into `build-setup`.
Add `-Jobs N` to adjust build concurrency.

## What the build does

- Applies [the PSXRecomp patch](../patches/psxrecomp-multi-region.patch) and
  [the launcher patch](../patches/recomp-ui-disc-drop.patch) to pinned commits.
  The runtime uses the mounted boot executable's identity and entry point to
  choose the region. The recompiler and overlay compiler changes are in the same
  PSXRecomp patch so other developers can reproduce the build or review them independently.
- Extracts each boot EXE into `disc/`, emits native code from the corresponding
  [function seeds](../seeds/), and generates symbol remaps so both backends can link
  into one binary. [multi_region_dispatch.c](../multi_region_dispatch.c) selects
  the native dispatch table.
- Reads the disc overlays locally and compiles the ahead-of-time cache for the
  selected build. This is repeatable with `scripts/build_overlay_cache.py` and
  its `--us-disc`, `--europe-disc`, and `--build-dir` options.

## Inspect the analysis and reproduce tests

- [Static analysis and disc inventories](../analysis/README.md) include per-region
  function maps, edges, references, indirect jumps and widescreen candidates.
  `python scripts/inspect_disc.py <disc.cue> --out <inventory.json>` regenerates
  a disc inventory. `scripts/audit_main_seeds.py` audits dispatch coverage with
  local EXEs, generated dispatch files and extracted overlays.
- To prepare the seed audit, extract `MOVIE.BIN` and the `OVR/*.BIN` members
  from the corresponding discs into `analysis/overlays/us` and
  `analysis/overlays/eu`. The build script's `extract_disc_overlays()`
  routine shows which files the cache builder reads.
- The [Windows verification index](verification/windows/README.md) links to
  historical telemetry, logs and screenshots. The harness writes new output
  to the ignored `analysis/verification/full_suite` directory.

Run the analyzer on a boot EXE extracted by the build. For example, with the
NTSC-U executable:

```powershell
$analyzer = '.\psxrecomp\recompiler\build\psxrecomp-analyze.exe'
$out = 'build-analysis/ntsc-u'
& $analyzer 'disc/SLUS_006.43' --out $out --emit-tsv "$out/functions.tsv" --scan-widescreen --emit-ws-sites "$out/widescreen_candidates.toml"
```

For the scripted Windows verification:

```powershell
$env:ROGUETRIP_GAME_FILES = 'D:\discs'
python scripts/verify_full_game.py --suite stages_fullrus
python scripts/verify_full_game.py --suite campaign_save_ending
```

Use the original variant folder and file names from `game.toml` for the harness.
It runs scripted inputs and debug-assisted state transitions through a local
`RelWithDebInfo` build. The OpenGL suite also expects a Release executable.
