# Rogue Trip Recompiled

Rogue Trip: Vacation 2012 for PC, built with [PSXRecomp](https://github.com/mstan/psxrecomp).

Tested only on Linux (Garuda, x86_64). Menus and the first level, XLAX, work;
the rest of the game hasn't been fully tested.

## Play

[Download the Linux AppImage](https://github.com/Wuteva/RogueTripRecomp/releases).

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

## Supported disc

**USA, SLUS-00643**, 17 tracks. Other versions are untested.
Hashes are for the **Track 01 BIN**:

| Field | Value |
| --- | --- |
| Size | `292442976` bytes |
| SHA-1 | `75c180b48bd37ff4045b6c77ab3c295d816142cb` |
| MD5 | `6a950ab677e902dcecebc8f57cb4b7f9` |
| CRC32 | `e9f241dd` |

## Build from source

Requires Git, Python 3.11+, CMake 3.20+, Ninja, a C/C++ compiler and OpenGL
development libraries. SDL3 is fetched if not installed.

```sh
git clone --recurse-submodules https://github.com/Wuteva/RogueTripRecomp.git
cd RogueTripRecomp
./build.sh '/path/to/Rogue Trip - Vacation 2012 (USA).cue'
./launch.sh
```

## License and credits

[PolyForm Noncommercial 1.0.0](LICENSE), following PSXRecomp's license.
Thanks to Matthew Stan and contributors for [PSXRecomp](https://github.com/mstan/psxrecomp),
and to the [recomp-ui](https://github.com/mstan/recomp-ui) and OpenBIOS projects.
The launcher and its patch use MIT. See [third-party notices](THIRD_PARTY_NOTICES.md).
