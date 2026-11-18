#!/usr/bin/env python3
"""Audit SLUS_006.43 (US/RUS) and SLES_014.17 (Europe) function entry coverage.

Checks:
1. Psy-Q pre-frame hoisted prologues (1 or 2 instructions between previous
   jr $ra + delay slot [+ alignment NOPs] and addiu $sp, $sp, -N) where the
   hoisted entry is NOT yet in the generated dispatch table.
2. Frameless leaf functions inside .text missing from the dispatch table.
3. Pointer-table function references (in main EXE .rodata/.data and in all 14
   overlays) pointing to callable boundaries in main EXE .text that are missing
   from the dispatch table.
4. Cross-module JAL calls from verified code blocks of MOVIE.BIN + 13 OVR/*.BIN
   into main EXE .text that are missing from the dispatch table.
"""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PSX_TOOLS = REPO / "psxrecomp" / "tools"
sys.path.insert(0, str(PSX_TOOLS))
sys.path.insert(0, str(PSX_TOOLS / "aot_overlay_spike"))

import compile_overlays as co  # type: ignore
import extract_generic as eg  # type: ignore
import rabbitizer  # type: ignore


def read_psx_exe_body(exe_path: Path) -> tuple[int, int, bytes]:
    raw = exe_path.read_bytes()
    assert raw[:8] == b"PS-X EXE", f"Bad magic in {exe_path}"
    entry_pc = struct.unpack_from("<I", raw, 0x10)[0]
    load_addr = struct.unpack_from("<I", raw, 0x18)[0]
    text_size = struct.unpack_from("<I", raw, 0x1C)[0]
    body = raw[0x800 : 0x800 + text_size]
    return load_addr, entry_pc, body


def parse_dispatch_entries(dispatch_c: Path) -> set[int]:
    text = dispatch_c.read_text(encoding="utf-8", errors="replace")
    # Match `{ 0x80123456u, ... }` or `{ 0x80123456, ... }` in dispatch table
    addrs = {int(m, 16) for m in re.findall(r"\{\s*0x([0-9A-Fa-f]{8})u?\s*,", text)}
    return addrs


def parse_seed_file(seed_txt: Path) -> set[int]:
    addrs: set[int] = set()
    for line in seed_txt.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            addrs.add(int(s, 16))
    return addrs


def disasm_range(body: bytes, base: int, addr: int, count: int = 6) -> str:
    parts = []
    for i in range(count):
        pc = addr + i * 4
        off = pc - base
        if off < 0 or off + 4 > len(body):
            break
        w = struct.unpack_from("<I", body, off)[0]
        ins = rabbitizer.Instruction(w, vram=pc)
        parts.append(f"0x{pc:08X}: {w:08X}  {ins.disassemble()}")
    return "\n      ".join(parts)


def is_safe_preframe_insn(w: int, pc: int) -> bool:
    if w == 0:
        return False
    ins = rabbitizer.Instruction(w, vram=pc)
    if not ins.isValid():
        return False
    if ins.isBranch() or ins.isJump() or ins.isTrap():
        return False
    # Exclude cop0/syscall/break/eret
    op = w >> 26
    if op == 0 and (w & 0x3F) in (0x0C, 0x0D):
        return False
    if op == 0x10:
        return False
    # Must write or read standard GPR ($gp, $a0-$a3, $v0-$v1, $t0-$t9, $sp)
    return True


def find_code_end(dispatch_addrs: set[int], base: int, body: bytes) -> int:
    """Find highest true compiled function address in .text."""
    # Look at sorted dispatch entries; find where dense code ends
    hi = max(dispatch_addrs)
    # Walk forward from highest dispatch entry to next jr $ra + delay slot
    off = hi - base
    for step in range(0, min(0x2000, len(body) - off - 4), 4):
        w = struct.unpack_from("<I", body, off + step)[0]
        if w == 0x03E00008:
            return base + off + step + 8
    return hi + 0x100


def collect_verified_overlay_code_words(ovr_bytes: bytes, ovr_base: int) -> list[tuple[int, int]]:
    """Return (pc, word) ONLY from verified callable functions inside an overlay."""
    words_out: list[tuple[int, int]] = []
    prols = set(eg.prologues(ovr_bytes, ovr_base))
    leaves = eg.frameless_leaf_entries(ovr_bytes, ovr_base)
    roots = sorted(prols | leaves)
    hi = ovr_base + len(ovr_bytes)
    for idx, start_pc in enumerate(roots):
        if not co.plausible_callable_target(ovr_bytes, ovr_base, len(ovr_bytes), start_pc, hi):
            continue
        # Walk forward until next root or jr $ra + delay slot (for leaf) or reasonable bound
        end_pc = roots[idx + 1] if idx + 1 < len(roots) else min(hi, start_pc + 0x2000)
        pc = start_pc
        while pc + 4 <= end_pc:
            w = struct.unpack_from("<I", ovr_bytes, pc - ovr_base)[0]
            ins = rabbitizer.Instruction(w, vram=pc)
            if not ins.isValid():
                break
            words_out.append((pc, w))
            pc += 4
    return words_out


def audit_region(
    label: str,
    exe_path: Path,
    seed_path: Path,
    dispatch_path: Path,
    ovr_dir: Path,
    ovr_base: int,
    indirect_json: Path,
) -> list[int]:
    print(f"\n{'=' * 78}")
    print(f"AUDITING {label}: {exe_path.name}")
    print(f"{'=' * 78}")

    base, entry_pc, body = read_psx_exe_body(exe_path)
    seeds = parse_seed_file(seed_path)
    dispatch = parse_dispatch_entries(dispatch_path)
    code_end = find_code_end(dispatch, base, body)

    print(f"Load: 0x{base:08X}  Entry: 0x{entry_pc:08X}  Size: 0x{len(body):X}")
    print(f"Seeds: {len(seeds)}  Dispatch entries: {len(dispatch)}  Code end: 0x{code_end:08X}")

    code_len = code_end - base
    code_body = body[:code_len]

    # 1. Psy-Q pre-frame hoisted prologues (1 or 2 instructions before addiu $sp,$sp,-N)
    preframe_1: list[int] = []
    preframe_2: list[int] = []
    for off in eg.prologue_offsets(code_body):
        sp_pc = base + off
        # Check 1-insn pre-frame: jr $ra at off-12 (or earlier with NOP padding)
        for pad in range(7):
            jr_off = off - 12 - pad * 4
            if jr_off < 0:
                break
            if eg._word(code_body, jr_off) == 0x03E00008 and all(
                eg._word(code_body, p) == 0 for p in range(jr_off + 8, off - 4, 4)
            ):
                w1 = eg._word(code_body, off - 4)
                cand = base + off - 4
                if w1 is not None and is_safe_preframe_insn(w1, cand):
                    if cand not in dispatch:
                        preframe_1.append(cand)
                break

        # Check 2-insn pre-frame: jr $ra at off-16 (or earlier with NOP padding)
        for pad in range(7):
            jr_off = off - 16 - pad * 4
            if jr_off < 0:
                break
            if eg._word(code_body, jr_off) == 0x03E00008 and all(
                eg._word(code_body, p) == 0 for p in range(jr_off + 8, off - 8, 4)
            ):
                w1 = eg._word(code_body, off - 8)
                w2 = eg._word(code_body, off - 4)
                cand = base + off - 8
                if (
                    w1 is not None
                    and w2 is not None
                    and is_safe_preframe_insn(w1, cand)
                    and is_safe_preframe_insn(w2, cand + 4)
                ):
                    if cand not in dispatch:
                        preframe_2.append(cand)
                break

    print(f"\n[1] Missing 1-insn Psy-Q pre-frame prologues: {len(preframe_1)}")
    for c in preframe_1:
        print(f"  * 0x{c:08X} (sp prologue at 0x{c+4:08X} in_dispatch={c+4 in dispatch}):")
        print(f"      {disasm_range(body, base, c - 8, 6)}")

    print(f"\n[2] Missing 2-insn Psy-Q pre-frame prologues: {len(preframe_2)}")
    for c in preframe_2:
        print(f"  * 0x{c:08X} (sp prologue at 0x{c+8:08X} in_dispatch={c+8 in dispatch}):")
        print(f"      {disasm_range(body, base, c - 8, 7)}")

    # 2. Frameless leaf functions inside code_body missing from dispatch
    leaves = sorted(eg.frameless_leaf_entries(code_body, base))
    missing_leaves = [addr for addr in leaves if addr not in dispatch]
    print(f"\n[3] Frameless leaf candidates in .text not in dispatch: {len(missing_leaves)}")
    for c in missing_leaves[:25]:
        print(f"  * 0x{c:08X}:")
        print(f"      {disasm_range(body, base, c - 8, 7)}")

    # 3. Pointer-table references to [base, code_end) in full EXE + overlays
    ptr_missing: dict[int, list[str]] = {}
    all_blobs: list[tuple[str, bytes, int]] = [(exe_path.name, body, base)]
    for ovr_file in sorted(ovr_dir.glob("*.BIN")):
        ob = 0x800201D0 if ovr_file.name.upper() == "MOVIE.BIN" else ovr_base
        all_blobs.append((ovr_file.name, ovr_file.read_bytes(), ob))

    text_lo = min((a for a in dispatch if a >= 0x800F5700), default=base)
    text_lo_off = text_lo - base

    for bname, bdata, bbase in all_blobs:
        for off in range(0, len(bdata) - 3, 4):
            # Skip scanning .text instructions [text_lo_off, code_len) of main EXE as pointer words;
            # DO scan .rdata [0, text_lo_off) and .data [code_len, end)!
            if bname == exe_path.name and text_lo_off <= off < code_len:
                continue
            val = struct.unpack_from("<I", bdata, off)[0]
            if (val & 3) == 0 and text_lo <= val < code_end and val not in dispatch:
                toff = val - base
                w_target = eg._word(code_body, toff)
                w_prev8 = eg._word(code_body, toff - 8) if toff >= 8 else None
                is_after_tailjump = w_prev8 is not None and ((w_prev8 >> 26) & 0x3F) == 0x02
                is_shared_jr_ra = w_target == 0x03E00008 and eg._word(code_body, toff + 4) == 0
                if (
                    eg._callable_boundary(code_body, toff)
                    or is_after_tailjump
                    or is_shared_jr_ra
                    or val in preframe_1
                    or val in preframe_2
                ):
                    ptr_missing.setdefault(val, []).append(f"{bname}+0x{off:X}")

    # Also scan lui + addiu function address materializations in .text and overlays!
    lui_missing: dict[int, list[str]] = {}
    for bname, bdata, bbase in all_blobs:
        limit = code_len if bname == exe_path.name else len(bdata)
        reg_hi: dict[int, tuple[int, int]] = {}
        for off in range(0, limit - 3, 4):
            w = struct.unpack_from("<I", bdata, off)[0]
            op = w >> 26
            if op == 0x0F:  # lui rt, imm
                rt = (w >> 16) & 0x1F
                imm = w & 0xFFFF
                if 0x800E <= imm <= 0x801D:
                    reg_hi[rt] = (imm << 16, off)
                else:
                    reg_hi.pop(rt, None)
            elif op == 0x09:  # addiu rt, rs, simm
                rs = (w >> 21) & 0x1F
                rt = (w >> 16) & 0x1F
                simm = struct.unpack("<h", struct.pack("<H", w & 0xFFFF))[0]
                if rs in reg_hi and off - reg_hi[rs][1] <= 32:
                    val = (reg_hi[rs][0] + simm) & 0xFFFFFFFF
                    if (val & 3) == 0 and base <= val < code_end and val not in dispatch:
                        toff = val - base
                        if (
                            eg._callable_boundary(code_body, toff)
                            or val in preframe_1
                            or val in preframe_2
                        ):
                            lui_missing.setdefault(val, []).append(f"{bname}@0x{bbase+off:08X}")
                if rt != rs:
                    reg_hi.pop(rt, None)

    print(f"\n[4] Data-pointer callable targets missing from dispatch: {len(ptr_missing)}")
    for val, refs in sorted(ptr_missing.items()):
        print(f"  * 0x{val:08X} referenced by {refs[:4]}:")
        print(f"      {disasm_range(body, base, val - 8, 6)}")

    print(f"\n[5] LUI+ADDIU callable targets missing from dispatch: {len(lui_missing)}")
    for val, refs in sorted(lui_missing.items()):
        print(f"  * 0x{val:08X} materialized at {refs[:4]}:")
        print(f"      {disasm_range(body, base, val - 8, 6)}")

    # 4. Verified code JALs from overlays into main EXE [base, code_end)
    ovr_jal_missing: dict[int, list[str]] = {}
    for ovr_file in sorted(ovr_dir.glob("*.BIN")):
        ob = 0x800201D0 if ovr_file.name.upper() == "MOVIE.BIN" else ovr_base
        odata = ovr_file.read_bytes()
        for pc, w in collect_verified_overlay_code_words(odata, ob):
            if (w >> 26) == 0x03:  # JAL
                target = 0x80000000 | ((w & 0x03FFFFFF) << 2)
                if base <= target < code_end and target not in dispatch:
                    ovr_jal_missing.setdefault(target, []).append(f"{ovr_file.name}@0x{pc:08X}")

    print(f"\n[6] Verified overlay JAL targets into main EXE missing from dispatch: {len(ovr_jal_missing)}")
    for val, refs in sorted(ovr_jal_missing.items()):
        print(f"  * 0x{val:08X} called by {refs[:6]}:")
        print(f"      {disasm_range(body, base, val - 8, 6)}")

    # 5. Summary of indirect.json
    if indirect_json.is_file():
        ind = json.loads(indirect_json.read_text(encoding="utf-8"))
        sites = ind if isinstance(ind, list) else ind.get("indirect_branches", ind.get("sites", []))
        print(f"\n[7] indirect.json entries: {len(sites)}")

    # Collect high-confidence verified missing seeds
    verified = sorted(
        set(preframe_1)
        | set(preframe_2)
        | set(ptr_missing.keys())
        | set(lui_missing.keys())
        | set(ovr_jal_missing.keys())
    )
    return verified


def main() -> int:
    if not all((REPO / "analysis" / "overlays" / region).is_dir() for region in ("us", "eu")):
        raise SystemExit("Extract both overlay sets first. See docs/DEVELOPING.md.")
    us_verified = audit_region(
        "US/RUS (SLUS-00643)",
        REPO / "disc" / "SLUS_006.43",
        REPO / "seeds" / "ghidra_funcs.txt",
        REPO / "generated" / "us" / "SLUS_006.43_dispatch.c",
        REPO / "analysis" / "overlays" / "us",
        0x801F5410,
        REPO / "analysis" / "ntsc-u-slus-00643" / "indirect.json",
    )
    eu_verified = audit_region(
        "EUROPE (SLES-01417)",
        REPO / "disc" / "SLES_014.17",
        REPO / "seeds" / "ghidra_funcs_eu.txt",
        REPO / "generated" / "eu" / "SLES_014.17_dispatch.c",
        REPO / "analysis" / "overlays" / "eu",
        0x801F5240,
        REPO / "analysis" / "pal-sles-01417" / "indirect.json",
    )
    print(f"\nTOTAL high-confidence missing seeds: US={len(us_verified)}, EU={len(eu_verified)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
