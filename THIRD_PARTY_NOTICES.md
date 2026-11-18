# Licensing and attribution

This project uses **PSXRecomp**, by Matthew Stan and contributors, to translate
PlayStation MIPS code into native C and provide the PS1 hardware runtime.
PSXRecomp is distributed under **PolyForm Noncommercial License 1.0.0**, including
its upstream clarification and commercial contact. The root `LICENSE` preserves
that text and notice and applies the same terms to this project's contributions,
including [the PSXRecomp multi-region patch](patches/psxrecomp-multi-region.patch).
The launcher patch uses the MIT License.

- Source: https://github.com/mstan/psxrecomp
- License: [psxrecomp/LICENSE](psxrecomp/LICENSE)
- Additional dependencies: [psxrecomp/THIRD_PARTY_ATTRIBUTION.md](psxrecomp/THIRD_PARTY_ATTRIBUTION.md)

The launcher uses **recomp-ui**, copyright 2026 Matthew Stanley and contributors,
under the **MIT License**. The local disc-drop patch and test-hook additions in
`patches/recomp-ui-disc-drop.patch` are also MIT-licensed; the complete notice
is preserved in [patches/LICENSE](patches/LICENSE).

- Source: https://github.com/mstan/recomp-ui
- License: [recomp-ui/LICENSE](recomp-ui/LICENSE)

The framework bundles **PCSX-Redux OpenBIOS**, a separate MIT-licensed BIOS by the
PCSX-Redux authors. Its notice is retained in
[psxrecomp/bios/OpenBIOS.LICENSE](psxrecomp/bios/OpenBIOS.LICENSE) and staged by the
framework beside the built application. Other third-party components retain their
own licenses and notices in the pinned dependency trees.

Rogue Trip: Vacation 2012 and its game assets belong to their respective rights
holders. This project is unofficial and does not grant rights to the original
game. No disc image, extracted game executable, or generated game code is included
in this repository. Verification screenshots document local compatibility tests.

The Linux AppImage also bundles SDL3 and zlib under their zlib licenses.
Their notices are included in `packaging/licenses/` and the AppImage payload.
System OpenGL drivers, glibc, and GCC runtime libraries are not bundled.
