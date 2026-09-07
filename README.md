# Rogue Trip Recompiled

Native Linux port of **Rogue Trip: Vacation 2012 (USA), SLUS-00643**, built with
[PSXRecomp](https://github.com/mstan/psxrecomp) and
[recomp-ui](https://github.com/mstan/recomp-ui).

**Tested only on Linux (Garuda Linux, x86_64).** Windows and macOS have not been tested.

## Supported disc

USA release, **SLUS-00643**, boot executable `SLUS_006.43`, 17 tracks.
The hashes below identify **Track 01 BIN**, not the CUE or concatenated disc.
Other regions/revisions have not been tested.

| Field | Value |
| --- | --- |
| Size | `292442976` bytes |
| SHA-1 | `75c180b48bd37ff4045b6c77ab3c295d816142cb` |
| MD5 | `6a950ab677e902dcecebc8f57cb4b7f9` |
| CRC32 | `e9f241dd` |

The generated build checks the disc against the identity in `game.toml`.

## Play

Download the **Linux AppImage** from the
[releases page](https://github.com/Wuteva/RogueTripRecomp/releases),
make it executable, and launch it. See [Linux AppImage](#linux-appimage) below
for system requirements and commands.

On first launch, follow the setup wizard, select or drop your game's `.cue` or
data-track `.bin`, and complete **Generate & rebuild**. Then click **PLAY**.
Reopen the AppImage for later sessions; it reuses your locally compiled game.
Keep the CUE and all 17 BIN tracks together: the framework resolves a dropped BIN
back to its companion CUE to retain the CD audio tracks.

Keyboard defaults: arrows = D-pad; **Enter** = Start; **X** = Cross/confirm;
**S** = Circle; **Z** = Square; **A** = Triangle; **Q/E** = L1/L2;
**W/R** = R1/R2; right Shift = Select. Configure controllers in the launcher.
The bundled OpenBIOS is used by default. No retail BIOS is required for this build.
Memory-card state is stored under `saves/` relative to the game configuration.

## Linux AppImage

The [GitHub release](https://github.com/Wuteva/RogueTripRecomp/releases) provides
an experimental **x86_64 setup AppImage**, tested only on Garuda Linux.
It requires **glibc 2.43 or newer**, GCC 16 runtime libraries, system OpenGL
drivers, and Python 3.11+.
The first-run wizard requires CMake, Ninja and a C/C++ toolchain (it can acquire
PSXRecomp's toolchain). Internet access may be needed for build dependencies.
Older Linux distributions are not supported by this binary; build from source there.

```sh
chmod +x RogueTripRecomp-0.1.0-linux-x86_64.AppImage
./RogueTripRecomp-0.1.0-linux-x86_64.AppImage
```

Drop your supported disc, then follow **Generate & rebuild**. The package contains
no game image or compiled game code. On first run it installs its setup files to
`${XDG_DATA_HOME:-~/.local/share}/RogueTripRecomp/0.1.0`; generated code, the built
game, and saves stay in that writable directory. Later launches reuse the build.
If FUSE is unavailable, use `--appimage-extract-and-run`.

## Build from source

Requirements: Git, Python 3.11+, CMake 3.20+, Ninja, C/C++ compiler, SDL3 and
OpenGL development libraries. SDL3 can also be fetched automatically by the framework when no system package is found.

```sh
git clone --recurse-submodules https://github.com/Wuteva/RogueTripRecomp.git
cd RogueTripRecomp
./build.sh '/path/to/Rogue Trip - Vacation 2012 (USA).cue'
./launch.sh
```

For later sessions from a source checkout, run `./launch.sh`.
`ROGUETRIP_BUILD_JOBS=4 ./build.sh ...` limits compile concurrency.
The output is `build-release/Rogue_Trip_Recompiled`; keep its adjacent assets,
bios, mods and configs. `launch.sh` supplies the root game config explicitly.
Generated game code, disc data, saves and build directories are local artifacts.

Dependency revisions are recorded in `framework_pins.txt`. The framework is
pinned to `953381b` because its newer September 6 lobby interfaces do not compile
against the public launcher master revision used here. Local launcher changes
(file-drop handling, discovery label, scripted drop test) are preserved in
`patches/recomp-ui-disc-drop.patch`. Rewind and netplay are disabled.

## Validation and limits

Initial bring-up reached the intro FMV, menus, rotating vehicle selection and
XLAX gameplay using the supplied US disc and OpenBIOS. Automated controller
input navigated the menus and selected the vehicle. Screenshots are in
`docs/verification/`. Invalid disc drops disable Play; a valid Track 01 BIN is
verified and re-enables it. The native launcher and XLAX gameplay were also verified in an SDL/OpenGL
virtual display.

This is an initial playable build, not a completed all-level compatibility audit.
Long sessions, every level/vehicle, two-player play, save/load round-trips and
audio accuracy have not been fully verified. PSXRecomp statically translates the
boot executable and uses its interpreter/native overlay system for streamed code;
this is not a claim that every overlay is already ahead-of-time compiled.

Release builds default to debug tools off. For development, configure
`-DPSX_DEBUG_TOOLS=ON` to enable diagnostics on localhost port 4370, or OFF
to disable them.

Do not distribute the supplied disc files or generated game-derived code.
Framework and launcher licensing remain in their respective source directories;
OpenBIOS carries its bundled MIT notice.

## License and credits

This project uses **PSXRecomp by Matthew Stan and contributors** and adopts its
**PolyForm Noncommercial License 1.0.0**, including the upstream clarification.
See [LICENSE](LICENSE). The **recomp-ui** launcher and our launcher patch are
MIT-licensed. OpenBIOS and other dependencies retain their own licenses.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for credits and notices.

The dependencies are pinned Git submodules. `build.sh` automatically applies the
launcher patch after checkout; it is safe to run again. For an existing clone,
run `git submodule update --init --recursive` before building. No ROM, extracted
game executable, retail BIOS or generated game code is published here.
