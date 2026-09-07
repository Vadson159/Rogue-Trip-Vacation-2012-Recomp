# AppImage build tooling

The initial Linux x86_64 package used the official AppImage tools below:

- appimagetool continuous, git `8c8c91f`, build 295
  - https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  - SHA-256: `a6d71e2b6cd66f8e8d16c37ad164658985e0cf5fcaa950c90a482890cb9d13e0`
- type2-runtime continuous, `runtime-x86_64`
  - https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64
  - SHA-256: `1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf`

Download them to `build-tools/appimagetool.AppImage` and
`build-tools/runtime-x86_64`, make appimagetool executable, build the emitters,
then run `scripts/package-appimage.sh`. These upstream continuous URLs can change;
compare hashes when reproducing this release. The script uses the shared PSXRecomp
setup-host packager and follows the AppDir layout documented at
https://docs.appimage.org/packaging-guide/manual.html.
