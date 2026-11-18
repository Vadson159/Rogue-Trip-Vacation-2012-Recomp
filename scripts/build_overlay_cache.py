#!/usr/bin/env python3
"""Build 100% AOT-compiled native overlay shard cache (.dll + .ranges) for
Rogue Trip: Vacation 2012 Recompiled across ALL regions:
  - SLUS-00643 (FullRUS, Rus, USA): MOVIE.BIN @ 0x800201D0 + 13 OVR/*.BIN @ 0x801F5410
  - SLES-01417 (Europe):            MOVIE.BIN @ 0x800201D0 + 13 OVR/*.BIN @ 0x801F5240

Compiles all 28 overlays with GCC (--compiler gcc --cps) into the unified
SLUS-00643 cache namespace used by Rogue_Trip_Recompiled.exe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PSX_TOOLS = REPO / "psxrecomp" / "tools"
sys.path.insert(0, str(PSX_TOOLS))
sys.path.insert(0, str(PSX_TOOLS / "aot_overlay_spike"))

import compile_overlays as co  # type: ignore
import extract_generic as eg  # type: ignore
import extract_overlays as eo  # type: ignore
import rabbitizer  # type: ignore


def read_psx_exe_body(exe_path: Path) -> tuple[int, int, bytes]:
    raw = exe_path.read_bytes()
    assert raw[:8] == b"PS-X EXE", f"Invalid PS-X EXE header: {exe_path}"
    entry_pc = struct.unpack_from("<I", raw, 0x10)[0]
    load_addr = struct.unpack_from("<I", raw, 0x18)[0]
    text_size = struct.unpack_from("<I", raw, 0x1C)[0]
    return load_addr, entry_pc, raw[0x800 : 0x800 + text_size]


def find_main_code_end(dispatch_c: Path, base: int, body: bytes) -> int:
    text = dispatch_c.read_text(encoding="utf-8", errors="replace")
    addrs = {int(m, 16) for m in re.findall(r"\{\s*0x([0-9A-Fa-f]{8})u?\s*,", text)}
    hi = max(addrs)
    off = hi - base
    for step in range(0, min(0x2000, len(body) - off - 4), 4):
        if struct.unpack_from("<I", body, off + step)[0] == 0x03E00008:
            return base + off + step + 8
    return hi + 0x100


def is_single_first_fn(d: bytes, b: int, t: int, lo_fn: int, lo_code: int) -> bool:
    """Detect the very first frameless function immediately following .rdata."""
    if not (lo_code <= t < lo_fn) or (lo_fn - t) > 0x200:
        return False
    w_start = eg._word(d, t - b)
    if w_start is None or w_start == 0 or (0x8000 <= (w_start >> 16) <= 0x8020):
        return False
    jr_pc = None
    for pad in range(7):
        cand_jr = lo_fn - 8 - 4 * pad
        if cand_jr < t:
            break
        if eg._word(d, cand_jr - b) == 0x03E00008 and all(
            eg._word(d, p - b) == 0 for p in range(cand_jr + 8, lo_fn, 4)
        ):
            jr_pc = cand_jr
            break
    if jr_pc is None:
        return False
    for pc in range(t, jr_pc + 8, 4):
        w = struct.unpack_from("<I", d, pc - b)[0]
        if pc < jr_pc and w == 0x03E00008:
            return False
        if 0x8000 <= (w >> 16) <= 0x8020:
            return False
        if not rabbitizer.Instruction(w, vram=pc).isValid():
            return False
    return bool(co.plausible_callable_target(d, b, len(d), t, lo_fn))


def extract_disc_overlays(cue_path: Path) -> list[tuple[str, bytes]]:
    bin_path, is_raw = eg.parse_cue_datatrack(str(cue_path))
    dr = eo.DiscReader(bin_path, raw=is_raw)
    out: list[tuple[str, bytes]] = []
    for iso_path, lba, size in sorted(eo.enumerate_files(dr)):
        norm = iso_path.upper().lstrip("/\\")
        if norm == "MOVIE.BIN" or (norm.startswith("OVR/") and norm.endswith(".BIN")):
            out.append((norm, dr.read_file_bytes(lba, size)))
    return out


def build_region_records(
    region_tag: str,
    cue_path: Path,
    exe_path: Path,
    dispatch_c: Path,
    ovr_base: int,
    recompiler: Path,
    tmp_dir: Path,
) -> list[dict]:
    base, _, body = read_psx_exe_body(exe_path)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    code_end = find_main_code_end(dispatch_c, base, body)
    main_jals = eg.jal_targets(body[: code_end - base])

    overlays = extract_disc_overlays(cue_path)
    assert len(overlays) == 14, f"Expected 14 overlays on {cue_path}, got {len(overlays)}"

    records: list[dict] = []
    covered_ovr_jals: set[int] = set()
    expected_ovr_jals = {t for t in main_jals if t >= ovr_base}

    print(f"\n[{region_tag}] Building AOT recipes from {cue_path.name} ({len(overlays)} overlays):")
    for iso_name, raw_bytes in overlays:
        is_movie = iso_name == "MOVIE.BIN"
        load_base = 0x800201D0 if is_movie else ovr_base
        lo_code = load_base if is_movie else load_base + 4
        # Word-align trailing bytes (e.g., OVR/SOCAL.BIN is 19,942 bytes)
        data = raw_bytes + b"\x00" * ((-len(raw_bytes)) & 3)
        hi = load_base + len(data)

        prols = {
            p
            for p in eg.prologues(data, load_base)
            if p >= lo_code and co.plausible_callable_target(data, load_base, len(data), p, hi)
        }
        leaves = {p for p in eg.frameless_leaf_entries(data, load_base) if p >= lo_code}
        int_jals = {
            p
            for p in eg.direct_jal_roots(data, load_base)
            if p >= lo_code and co.plausible_callable_target(data, load_base, len(data), p, hi)
        }
        ext_jals = {
            t
            for t in main_jals
            if lo_code <= t < hi
            and (eg._callable_boundary(data, t - load_base) or t == lo_code)
            and not eg._dense_local_pointer_table(data, load_base, t - load_base)
            and co.plausible_callable_target(data, load_base, len(data), t, hi)
        }

        core_seeds = sorted(prols | leaves | int_jals | ext_jals)

        # Recover any frameless first function immediately following .rdata before resolving jump tables
        changed = True
        while changed and core_seeds:
            changed = False
            lo_fn = core_seeds[0]
            cands = sorted(
                t
                for t in (main_jals | eg.jal_targets(data))
                if is_single_first_fn(data, load_base, t, lo_fn, lo_code)
            )
            if cands and cands[0] not in core_seeds:
                core_seeds.insert(0, cands[0])
                changed = True

        # Resolve proven switch jump tables on core function entries FIRST so
        # switch-case targets in .rdata jump tables are never misclassified as
        # standalone function seeds (which would split switch functions in half).
        core_disp = eg.reachable_static_dispatches(data, load_base, core_seeds)
        jt_case_targets = {
            t for pr in core_disp["jump_table_proofs"] for t in pr["targets"]
        }

        ptrs = {
            p
            for p in eg.pointer_table_targets(data, load_base)
            if p >= lo_code
            and p not in jt_case_targets
            and co.plausible_callable_target(data, load_base, len(data), p, hi)
        }

        seeds = sorted(set(core_seeds) | ptrs)

        # Recover any frameless first function immediately following .rdata
        changed = True
        while changed and seeds:
            changed = False
            lo_fn = seeds[0]
            cands = sorted(
                t
                for t in (main_jals | eg.jal_targets(data))
                if is_single_first_fn(data, load_base, t, lo_fn, lo_code)
            )
            if cands and cands[0] not in seeds:
                seeds.insert(0, cands[0])
                changed = True

        direct = sorted(set(int_jals) | (set(seeds) & main_jals))
        member = {
            "id": 0,
            "file_offset": 0,
            "data": data,
            "base": load_base,
            "direct_seeds": direct if direct else seeds[:1],
            "seeds": seeds,
        }
        member = eg.enrich_positioned_member(member, str(recompiler), str(tmp_dir))
        final_seeds = sorted(
            p for p in member["seeds"] if p >= lo_code and p not in jt_case_targets
        )
        static_disp = eg.reachable_static_dispatches(data, load_base, final_seeds)

        page_base, region = eg.page_aligned_region(load_base, data)
        rec = eg.rec(
            page_base,
            region,
            final_seeds,
            dispatch_extra=static_disp["dispatch_pcs"],
            producer_ranges=((lo_code, hi),),
            static_discovery=direct,
            static_alias_ranges=member.get("static_alias_ranges"),
            jump_table_proofs=static_disp["jump_table_proofs"],
            call_continuations=static_disp["call_continuation_pcs"],
        )
        eg.add_consensus_fallback(rec, member)
        rec["producer_name"] = f"{region_tag}:{iso_name}"
        records.append(rec)

        if not is_movie:
            covered_ovr_jals.update(final_seeds)

        print(
            f"  {iso_name:15s} @ 0x{load_base:08X} (page 0x{page_base:08X}, {len(raw_bytes):5d}B): "
            f"seeds={len(final_seeds):3d}, jtables={len(static_disp['jump_table_proofs'])}, "
            f"conts={len(static_disp['call_continuation_pcs'])}"
        )

    uncovered = sorted(expected_ovr_jals - covered_ovr_jals)
    if uncovered:
        raise RuntimeError(
            f"[{region_tag}] {len(uncovered)} main-EXE JALs uncovered: {[hex(x) for x in uncovered]}"
        )
    print(f"[{region_tag}] Verified 100% main-EXE JAL coverage ({len(expected_ovr_jals)}/{len(expected_ovr_jals)} targets)!")
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Force rebuild of all cached shards")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--us-disc", type=Path)
    ap.add_argument("--europe-disc", type=Path)
    ap.add_argument("--build-dir", type=Path, default=REPO / "build-release")
    args = ap.parse_args()

    tc_dir = Path(os.environ.get("PSXRECOMP_TOOLCHAIN_DIR", str(REPO.parent / "tools" / "cmake-clang-v1" / "latest")))
    gcc_exe = tc_dir / "bin" / "gcc.exe"
    recompiler = REPO / "psxrecomp" / "recompiler" / "build" / "psxrecomp-game.exe"
    runtime_inc = REPO / "psxrecomp" / "runtime" / "include"
    game_toml = REPO / "game.toml"

    # Ensure toolchain bin is on PATH so psxrecomp-game.exe finds libc++.dll/libunwind.dll
    env = os.environ.copy()
    tc_bin = str(tc_dir / "bin")
    if tc_bin not in env.get("PATH", ""):
        env["PATH"] = f"{tc_bin};{env.get('PATH', '')}"
    os.environ["PATH"] = env["PATH"]

    gf = Path(os.environ.get("ROGUETRIP_GAME_FILES", REPO.parent / "_game_files"))
    us_cue = gf / "Rogue Trip - Vacation 2012 (FullRUS)" / "Rogue Trip - Vacation 2012 (FullRUS).cue"
    if not us_cue.is_file():
        us_cue = gf / "Rogue Trip - Vacation 2012 (Rus)" / "Rogue Trip - Vacation 2012 (Rus).cue"
    eu_cue = gf / "Rogue Trip - Vacation 2012 (Europe)" / "Rogue Trip - Vacation 2012 (Europe).cue"

    us_cue = (args.us_disc or us_cue).resolve(strict=True)
    eu_cue = (args.europe_disc or eu_cue).resolve(strict=True)

    out_captures = REPO / "analysis" / "overlays" / "aot_captures_all.json"
    out_captures.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rt_aot_") as tmp_s:
        tmp_dir = Path(tmp_s)
        records = []
        records.extend(
            build_region_records(
                "SLUS-00643",
                us_cue,
                REPO / "disc" / "SLUS_006.43",
                REPO / "generated" / "us" / "SLUS_006.43_dispatch.c",
                0x801F5410,
                recompiler,
                tmp_dir / "us",
            )
        )
        records.extend(
            build_region_records(
                "SLES-01417",
                eu_cue,
                REPO / "disc" / "SLES_014.17",
                REPO / "generated" / "eu" / "SLES_014.17_dispatch.c",
                0x801F5240,
                recompiler,
                tmp_dir / "eu",
            )
        )

    out_captures.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nWrote {len(records)} overlay capture recipes -> {out_captures}")

    rel_cache = args.build_dir.resolve() / "cache"
    rel_cache.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(PSX_TOOLS / "compile_overlays.py"),
        "--captures",
        str(out_captures),
        "--game-toml",
        str(game_toml),
        "--recompiler",
        str(recompiler),
        "--runtime-include",
        str(runtime_inc),
        "--project-root",
        str(REPO / "psxrecomp"),
        "--out-dir",
        str(rel_cache),
        "--compiler",
        "gcc",
        "--gcc",
        str(gcc_exe),
        "--cps",
        "--jobs",
        str(args.jobs),
    ]
    if args.force:
        cmd.append("--force")

    print(f"\nCompiling {len(records)} native overlay shards with GCC (--cps)...")
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    dll_count = len(list(rel_cache.rglob("*.dll")))
    print(f"\nSUCCESS: {dll_count} native overlay DLL shards staged in {rel_cache}!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
