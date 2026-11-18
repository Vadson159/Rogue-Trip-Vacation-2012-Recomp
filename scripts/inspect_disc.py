#!/usr/bin/env python3
"""Inspect Rogue Trip: Vacation 2012 (SLUS-00643) disc dump, verify hashes,
and inventory all ISO9660 files, SingleTrac containers, and potential code overlays.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

EXPECTED_SIZE = 292442976
EXPECTED_MD5 = "6a950ab677e902dcecebc8f57cb4b7f9"
EXPECTED_SHA1 = "75c180b48bd37ff4045b6c77ab3c295d816142cb"
EXPECTED_CRC32 = "e9f241dd"
EXPECTED_TRACKS = 17


def parse_cue(cue_path: Path) -> tuple[list[Path], int, int | None]:
    text = cue_path.read_text(encoding="utf-8", errors="replace")
    files = [
        (cue_path.parent / m.group(1)).resolve()
        for m in re.finditer(r'FILE\s+"([^"]+)"', text, flags=re.IGNORECASE)
    ]
    tracks = len(re.findall(r"^\s*TRACK\s+\d+", text, flags=re.IGNORECASE | re.MULTILINE))
    # If single-FILE multi-track cue, find TRACK 02 first INDEX to bound Track 01 bytes
    track1_bytes: int | None = None
    if len(files) == 1 and tracks > 1:
        m_t2 = re.search(
            r"TRACK\s+0*2\s+\w+.*?INDEX\s+0*[01]\s+(\d+):(\d+):(\d+)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if m_t2:
            mm, ss, ff = int(m_t2.group(1)), int(m_t2.group(2)), int(m_t2.group(3))
            sectors = (mm * 60 + ss) * 75 + ff
            track1_bytes = sectors * 2352
    return files, tracks, track1_bytes


def hash_file(path: Path, max_bytes: int | None = None) -> dict[str, str | int]:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    crc = 0
    size = 0
    remaining = max_bytes
    with path.open("rb") as f:
        while True:
            to_read = (1 << 20) if remaining is None else min(1 << 20, remaining)
            if to_read <= 0:
                break
            chunk = f.read(to_read)
            if not chunk:
                break
            size += len(chunk)
            if remaining is not None:
                remaining -= len(chunk)
            md5.update(chunk)
            sha1.update(chunk)
            crc = binascii.crc32(chunk, crc)
    return {
        "size": size,
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "crc32": f"{crc & 0xFFFFFFFF:08x}",
    }


def read_mode2_user_sector(f, lba: int) -> bytes:
    f.seek(lba * 2352)
    raw = f.read(2352)
    if len(raw) < 2352:
        return b""
    # Raw 2352-byte PSX Mode 2 Form 1: 12 sync + 4 header + 8 subheader + 2048 user data
    if raw[:12] == b"\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00":
        mode = raw[15]
        if mode == 2:
            submode = raw[18]
            if submode & 0x20:  # Form 2 (XA audio/video, 2324 bytes)
                return raw[24 : 24 + 2048]
            return raw[24 : 24 + 2048]
        return raw[16 : 16 + 2048]
    return raw[:2048]


def walk_iso_dir(f, dir_lba: int, dir_size: int, prefix: str = "") -> list[dict]:
    entries = []
    sectors = (dir_size + 2047) // 2048
    data = b"".join(read_mode2_user_sector(f, dir_lba + i) for i in range(sectors))
    pos = 0
    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:
            next_sec = ((pos // 2048) + 1) * 2048
            if next_sec <= pos:
                break
            pos = next_sec
            continue
        rec = data[pos : pos + rec_len]
        extent_lba = struct.unpack_from("<I", rec, 2)[0]
        data_len = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        raw_name = rec[33 : 33 + name_len]
        pos += rec_len
        if raw_name in (b"\x00", b"\x01"):
            continue
        name = raw_name.decode("ascii", errors="replace").split(";")[0]
        full_path = f"{prefix}/{name}" if prefix else name
        is_dir = bool(flags & 0x02)
        if is_dir:
            entries.extend(walk_iso_dir(f, extent_lba, data_len, full_path))
        else:
            head = read_mode2_user_sector(f, extent_lba)[:32]
            magic = head[:8].decode("ascii", errors="replace")
            entries.append(
                {
                    "path": full_path,
                    "lba": extent_lba,
                    "size": data_len,
                    "magic_hex": head[:16].hex(),
                    "magic_ascii": "".join(c if 32 <= ord(c) < 127 else "." for c in magic),
                    "is_psx_exe": head[:8] == b"PS-X EXE",
                }
            )
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("disc", type=Path, help="Path to .cue or Track 01 .bin")
    ap.add_argument("--out", type=Path, default=Path("analysis/disc_inventory.json"))
    args = ap.parse_args()

    disc = args.disc.resolve()
    track_count = None
    track1_bytes = None
    missing_bins: list[str] = []
    if disc.suffix.lower() == ".cue":
        files, track_count, track1_bytes = parse_cue(disc)
        if not files:
            print(f"ERROR: No FILE entries found in {disc}", file=sys.stderr)
            return 2
        for bf in files:
            if not bf.is_file():
                missing_bins.append(str(bf))
        data_bin = files[0]
    else:
        data_bin = disc

    if not data_bin.is_file():
        print(f"ERROR: Data track file missing: {data_bin}", file=sys.stderr)
        return 2

    print(f"Inspecting Track 01: {data_bin}")
    digests_full = hash_file(data_bin)
    digests_t1 = hash_file(data_bin, max_bytes=track1_bytes) if track1_bytes else digests_full
    matches = {
        "size_ok": digests_t1["size"] == EXPECTED_SIZE,
        "md5_ok": digests_t1["md5"] == EXPECTED_MD5,
        "sha1_ok": digests_t1["sha1"] == EXPECTED_SHA1,
        "crc32_ok": digests_t1["crc32"] == EXPECTED_CRC32,
        "tracks_ok": (track_count == EXPECTED_TRACKS) if track_count is not None else None,
        "missing_bins": missing_bins,
    }

    with data_bin.open("rb") as f:
        pvd = read_mode2_user_sector(f, 16)
        if pvd[1:6] != b"CD001":
            print("WARNING: Sector 16 is not an ISO9660 Primary Volume Descriptor", file=sys.stderr)
            files_list = []
        else:
            root_rec = pvd[156 : 156 + 34]
            root_lba = struct.unpack_from("<I", root_rec, 2)[0]
            root_size = struct.unpack_from("<I", root_rec, 10)[0]
            files_list = walk_iso_dir(f, root_lba, root_size)

    report = {
        "disc_input": str(disc),
        "data_track": str(data_bin),
        "track_count": track_count,
        "digests_full_bin": digests_full,
        "digests_track01": digests_t1,
        "verification_against_stock_usa": matches,
        "file_count": len(files_list),
        "files": files_list,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Verification: {json.dumps(matches, indent=2)}")
    print(f"Discovered {len(files_list)} files on ISO9660 filesystem -> {args.out}")
    for entry in files_list:
        print(f"  LBA {entry['lba']:6d} | {entry['size']:10d} B | {entry['magic_ascii']:8s} | {entry['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
