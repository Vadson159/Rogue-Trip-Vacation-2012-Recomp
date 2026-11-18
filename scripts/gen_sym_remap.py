#!/usr/bin/env python3
"""Generate C preprocessor symbol-remap headers (-include) so multiple regional
PSXRecomp game codegen trees (e.g. SLUS_006.43 + SLES_014.17) link cleanly into
one unified native executable without modifying any generated .c/.h shard.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SYM_RE = re.compile(r"\b((?:func|psx_alias_body)_[0-9A-Fa-f]{8})\b")

PUBLIC_API = (
    "psx_game_address_in_text",
    "psx_game_text_native_ok",
    "psx_game_text_native_ok_full",
    "psx_dispatch_game_compiled",
    "psx_game_is_function_entry",
)


def generate_remap(gen_dir: Path, prefix: str, out_header: Path) -> int:
    syms: set[str] = set()
    for pat in ("*_decls.h", "*_dispatch.c"):
        for p in sorted(gen_dir.glob(pat)):
            text = p.read_text(encoding="utf-8", errors="replace")
            syms.update(SYM_RE.findall(text))

    lines = [
        "/* Auto-generated symbol namespace header for multi-region PSXRecomp link. */",
        "#pragma once",
        "",
    ]
    for api in PUBLIC_API:
        lines.append(f"#define {api} {prefix}{api}")
    lines.append("")
    for sym in sorted(syms):
        lines.append(f"#define {sym} {prefix}{sym}")
    lines.append("")

    out_header.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    if not out_header.is_file() or out_header.read_text(encoding="utf-8") != content:
        out_header.write_text(content, encoding="utf-8")
    return len(syms)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gen-dir", type=Path, required=True)
    ap.add_argument("--prefix", type=str, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    n = generate_remap(args.gen_dir, args.prefix, args.out)
    print(f"Wrote {args.out} ({n} symbols prefixed with '{args.prefix}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
