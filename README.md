# Rogue Trip: Vacation 2012 Recompiled

Windows-first static recompilation of the PlayStation game Rogue Trip: Vacation 2012,
built with [PSXRecomp](https://github.com/mstan/psxrecomp). The Windows build launches
and includes native backends for NTSC-U (`SLUS-00643`) and PAL (`SLES-01417`).

Windows verification includes all 12 FullRUS arenas and a scripted campaign
save, reload and ending. See the [verification reports and screenshots](docs/verification/windows/README.md)
for coverage by disc variant.

## Windows

Build from source on Windows x64 using PowerShell 7, Git for Windows, Python 3.11+
and the cmake-clang-v1 toolchain. The unified build uses your own NTSC-U and PAL
CUE/BIN dumps to generate code locally.

```powershell
git -c core.autocrlf=false clone --recurse-submodules https://github.com/Vadson159/Rogue-Trip-Vacation-2012-Recomp.git
cd Rogue-Trip-Vacation-2012-Recomp
python -m pip install rabbitizer
$env:PSXRECOMP_TOOLCHAIN_DIR = 'C:\toolchains\cmake-clang-v1'
.\build.ps1 -UsDisc 'D:\discs\Rogue Trip (USA).cue' -EuropeDisc 'D:\discs\Rogue Trip (Europe).cue'
.\launch.ps1 -Disc 'D:\discs\Rogue Trip (USA).cue'
```

See the [developer guide](docs/DEVELOPING.md) for the toolchain, supported disc layouts,
debug builds, static analysis and test reproduction.

## Linux

The [original upstream Linux AppImage](https://github.com/Wuteva/RogueTripRecomp/releases)
uses the stock USA disc. The upstream project tested the menus and XLAX on Garuda x86-64.

```sh
chmod +x RogueTripRecomp-0.1.0-linux-x86_64.AppImage
./RogueTripRecomp-0.1.0-linux-x86_64.AppImage
```

Drop your `.cue` or Track 01 `.bin` into the launcher. Complete **Generate & rebuild**
once, then click **PLAY**. Keep the CUE and all 17 BIN tracks together for music.
You need your own game disc; OpenBIOS is included.

Requires glibc 2.43+, GCC 16 runtime libraries, OpenGL drivers and Python 3.11+.
The first build also needs CMake, Ninja and a C/C++ compiler; the wizard can download
the toolchain. For older Linux distributions, build from source.
If FUSE is unavailable, launch with `--appimage-extract-and-run`.

The AppImage stores the game and saves in
`~/.local/share/RogueTripRecomp/0.1.0` (or under `$XDG_DATA_HOME` if set).

## Controls

| Keyboard | PlayStation |
| --- | --- |
| Arrow keys | D-pad |
| Enter / Right Shift | Start / Select |
| X / S / Z / A | Cross / Circle / Square / Triangle |
| Q / E | L1 / L2 |
| W / R | R1 / R2 |

Controllers and key bindings can be configured in the launcher.

## Stock USA disc

The stock **USA, SLUS-00643** dump has 17 tracks. The table describes
the **Track 01 BIN**. See the [disc inventories](analysis/README.md) for the tested
FullRUS and Europe layouts.

| Field | Value |
| --- | --- |
| Size | `292442976` bytes |
| SHA-1 | `75c180b48bd37ff4045b6c77ab3c295d816142cb` |
| MD5 | `6a950ab677e902dcecebc8f57cb4b7f9` |
| CRC32 | `e9f241dd` |

## Linux build from source

Requires Git, Python 3.11+, CMake 3.20+, Ninja, a C/C++ compiler and OpenGL
development libraries. SDL3 is fetched if not installed.

```sh
git clone --recurse-submodules https://github.com/Vadson159/Rogue-Trip-Vacation-2012-Recomp.git
cd Rogue-Trip-Vacation-2012-Recomp
./build.sh '/path/to/Rogue Trip - Vacation 2012 (USA).cue'
./launch.sh '/path/to/Rogue Trip - Vacation 2012 (USA).cue'
```

## License and credits

[PolyForm Noncommercial 1.0.0](LICENSE), following PSXRecomp's license.
This project builds on [Wuteva's RogueTripRecomp](https://github.com/Wuteva/RogueTripRecomp).
Thanks to Matthew Stan and contributors for [PSXRecomp](https://github.com/mstan/psxrecomp),
and to the [recomp-ui](https://github.com/mstan/recomp-ui) and OpenBIOS projects.
The launcher and its patch use MIT. See [third-party notices](THIRD_PARTY_NOTICES.md).
