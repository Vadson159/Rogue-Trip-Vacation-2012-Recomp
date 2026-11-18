"""Extract the two PS-X boot executables needed for a unified build."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "psxrecomp" / "tools" / "new_project_layout"))
from probe_disc import probe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--us-disc", type=Path, required=True)
    parser.add_argument("--europe-disc", type=Path, required=True)
    args = parser.parse_args()

    output = ROOT / "disc"
    output.mkdir(exist_ok=True)
    for cue, serial, name, entry in (
        (args.us_disc, "SLUS-00643", "SLUS_006.43", 0x801549B0),
        (args.europe_disc, "SLES-01417", "SLES_014.17", 0x801547B4),
    ):
        result = probe(cue.resolve(strict=True))
        if (result.serial != serial or not result.boot_exe_bytes
                or int(result.entry_pc, 16) != entry):
            parser.error(f"{cue} does not contain a boot EXE matching {serial} at {entry:#x}")
        path = output / name
        path.write_bytes(result.boot_exe_bytes)
        print(f"Extracted {name} ({len(result.boot_exe_bytes)} bytes)")


if __name__ == "__main__":
    main()
