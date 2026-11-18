# Windows Release boot checks

On 2026-11-18, a fresh checkout of the project sources at
`0122e28a84defe575aa1857db5fd411b0a72142b` built the unified Windows x64 Release
executable with RetComM cmake-clang-v1 1.0.14. The pinned PSXRecomp and recomp-ui
submodules were patched by the build script. It processed 28 overlay recipes
and staged 97 native overlay DLLs, with zero compilation failures.

The Release runtime was started with each disc and `--headless`, with only
Windows system directories on `PATH`. Both runs indexed all 97 overlay DLLs,
selected the intended native backend and reached BIOS execution.

| Disc | Runtime region | Native backend | PS-X entry point |
| --- | --- | --- | --- |
| FullRUS | NTSC-U `SLUS-00643` | `SLUS_006.43` | `0x801549B0` |
| Europe | PAL `SLES-01417` | `SLES_014.17` | `0x801547B4` |

```text
overlay cache scan: 97 shared library file(s) indexed [arch=win-x64]
psxrecomp: disc region NTSC-U (serial SLUS-00643)
roguetrip: selected native backend SLUS_006.43 (US / FullRUS / Rus NTSC, entry=0x801549B0)
psxrecomp runtime: executing from PC=0xBFC00000

overlay cache scan: 97 shared library file(s) indexed [arch=win-x64]
psxrecomp: disc region PAL (serial SLES-01417)
roguetrip: selected native backend SLES_014.17 (Europe PAL, entry=0x801547B4)
psxrecomp runtime: executing from PC=0xBFC00000
```

The framework's `full_function_emitter_test`, `reachable_discovery_test`
and `reachable_discovery_codegen` tests also passed.
