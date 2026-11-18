#!/usr/bin/env python3
"""Comprehensive end-to-end automated verification harness for the multi-region
PC port of Rogue Trip: Vacation 2012 (Rogue_Trip_Recompiled.exe).

Suites:
  1. stages_fullrus       — FullRUS (SLUS-00643): Intro FMV, SHELL.BIN, all 12 playable
                            3D arenas (0..11) + Boss phases (Big Daddy, Goliath, Daddy-O)
  2. campaign_save_ending — FullRUS (SLUS-00643): 1P Vacation campaign -> Stage win ->
                            MEMC.BIN Memory Card Save -> Cold Reboot & MEMC.BIN Load ->
                            Final Boss (NUKE Daddy-O) Victory -> BOSSEND.STR -> END*.STR ->
                            CREND*.TIM Ending Credits
  3. rus                  — Rus disc (SLUS-00643): Intro FMV, SHELL.BIN, MEMC.BIN,
                            AIRPORT & NUKE 3D combat
  4. europe               — Europe disc (SLES-01417, PAL 50 Hz): Intro FMV, English SHELL.BIN,
                            MEMC.BIN, AIRPORT / FUN / VEGAS Boss / NUKE Daddy-O 3D combat,
                            and PAL Ending FMV + Credits
  5. opengl_release       — Windowed OpenGL hardware renderer (--renderer opengl, non-headless)
                            3D FBO verification + standalone Release exe clean-PATH smoke test
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BUILD_DBG = REPO / "build-relwithdebinfo"
BUILD_REL = REPO / "build-release"
EXE_DBG = BUILD_DBG / "Rogue_Trip_Recompiled.exe"
EXE_REL = BUILD_REL / "Rogue_Trip_Recompiled.exe"

GAME_FILES = Path(os.environ.get("ROGUETRIP_GAME_FILES", REPO.parent / "_game_files")).resolve()
CUE_FULLRUS = GAME_FILES / "Rogue Trip - Vacation 2012 (FullRUS)" / "Rogue Trip - Vacation 2012 (FullRUS).cue"
CUE_RUS = GAME_FILES / "Rogue Trip - Vacation 2012 (Rus)" / "Rogue Trip - Vacation 2012 (Rus).cue"
CUE_EUROPE = GAME_FILES / "Rogue Trip - Vacation 2012 (Europe)" / "Rogue Trip - Vacation 2012 (Europe).cue"

OUT_DIR = REPO / "analysis" / "verification" / "full_suite"

# PS1 Active-Low Pad Masks
PAD_IDLE = 0xFFFF
PAD_SELECT = 0xFFFE
PAD_START = 0xFFF7
PAD_UP = 0xFFEF
PAD_RIGHT = 0xFFDF
PAD_DOWN = 0xFFBF
PAD_LEFT = 0xFF7F
PAD_L2 = 0xFEFF
PAD_R2 = 0xFDFF
PAD_L1 = 0xFBFF
PAD_R1 = 0xF7FF
PAD_TRIANGLE = 0xEFFF
PAD_CIRCLE = 0xDFFF
PAD_CROSS = 0xBFFF
PAD_SQUARE = 0x7FFF

# Region-specific RAM layout (EU is shifted by -0x1D0 in .sdata/.bss/ovr_base)
REGIONS = {
    "US": {
        "gp": 0x801C3240,
        "game_session": 0x801B3960,
        "options_unlocks": 0x801B399C,
        "lvlsel_idx": 0x801C3470,
        "state_ptr_slot": 0x801C34EC,
        "timer_cnt": 0x801C3370,   # $gp + 0x130
        "timer_arr": 0x801CBB58,   # { int32 countdown_ticks, int32 exit_code }
        "ovr_base": 0x801F5410,
        "movie_base": 0x800201D0,
    },
    "EU": {
        "gp": 0x801C3070,
        "game_session": 0x801B3790,
        "options_unlocks": 0x801B37CC,
        "lvlsel_idx": 0x801C32A0,
        "state_ptr_slot": 0x801C331C,
        "timer_cnt": 0x801C31A0,   # $gp + 0x130
        "timer_arr": 0x801CB988,
        "ovr_base": 0x801F5240,
        "movie_base": 0x800201D0,
    },
}

# All 12 playable arenas in Rogue Trip: Vacation 2012
# (index, short_name, ovr_id or None if resident in main EXE, boss1_flag, boss2_flag, label)
ALL_STAGES = [
    (0,  "AIRPORT", 0x05, 0, 0, "XLAX / Airport"),
    (1,  "HOLLY",   None, 0, 0, "Hollywood / Blowtorch (Main-EXE Resident)"),
    (2,  "DC",      0x04, 0, 0, "The Maul / Washington D.C."),
    (3,  "A51",     0x06, 0, 0, "Area 51"),
    (4,  "FUN",     0x0C, 0, 0, "Funtopia (Bonus Arena)"),
    (5,  "VEGAS",   0x07, 0, 0, "Las Vegas"),
    (5,  "VEGAS_BOSS_BIGDADDY", 0x07, 1, 0, "Las Vegas — Boss 1 (Big Daddy)"),
    (6,  "GREEK",   0x0D, 0, 0, "Metro / Colosseum (Bonus Arena)"),
    (7,  "SOCAL",   0x08, 0, 0, "SoCal"),
    (8,  "PARK",    0x09, 0, 0, "Redwood / Park"),
    (9,  "SANFRAN", 0x0B, 0, 0, "San Francisco / Boss 2 (Goliath)"),
    (10, "GHOST",   0x0A, 0, 0, "Gulch / Ghost Town (Bonus Arena)"),
    (11, "NUKE_PHASE1", 0x0E, 0, 0, "Fallout / Nuke — Boss Duo (Big Daddy + Goliath)"),
    (11, "NUKE_FINAL_DADDYO", 0x0E, 0, 1, "Fallout / Nuke — Final Boss (Daddy-O)"),
]


class DebugClient:
    """Reconnect-per-command TCP client matching psxrecomp debug_server contract."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4375, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.next_id = 1

    def cmd(self, name: str, **params: Any) -> dict[str, Any]:
        req_id = self.next_id
        self.next_id += 1
        payload = {"cmd": name, "id": req_id, **params}
        raw_req = (json.dumps(payload) + "\n").encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.sendall(raw_req)
            buf = bytearray()
            pos = 0
            depth = 0
            in_str = False
            esc = False
            started = False
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf.extend(chunk)
                n = len(buf)
                while pos < n:
                    if in_str:
                        if esc:
                            esc = False
                            pos += 1
                            continue
                        q = buf.find(b'"', pos)
                        bs = buf.find(b"\\", pos)
                        if q == -1 and bs == -1:
                            pos = n
                            break
                        if bs != -1 and (q == -1 or bs < q):
                            esc = True
                            pos = bs + 1
                            continue
                        in_str = False
                        pos = q + 1
                        continue
                    c = buf[pos]
                    if c == 0x22:
                        in_str = True
                    elif c == 0x7B:
                        depth += 1
                        started = True
                    elif c == 0x7D:
                        depth -= 1
                        if started and depth == 0:
                            return json.loads(buf[: pos + 1].decode("utf-8"))
                    pos += 1
            return json.loads(buf.decode("utf-8").strip())

    def frame(self) -> int:
        r = self.cmd("frame")
        if not r.get("ok"):
            raise RuntimeError(f"frame query failed: {r}")
        return int(r["frame"])

    def wait_frames(self, count: int, timeout_s: float = 45.0) -> int:
        start = self.frame()
        target = start + count
        t0 = time.monotonic()
        while True:
            cur = self.frame()
            if cur >= target:
                return cur
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError(f"wait_frames({count}) timed out at frame {cur} (target {target})")
            time.sleep(0.012)

    def press(self, buttons: int, hold_frames: int = 10, wait_after: int = 60) -> None:
        self.cmd("press", buttons=buttons, frames=hold_frames)
        self.wait_frames(hold_frames + wait_after)

    def read_bytes(self, addr: int, length: int) -> bytes:
        r = self.cmd("read_ram", addr=f"0x{addr:08X}", len=length)
        if not r.get("ok"):
            raise RuntimeError(f"read_ram({hex(addr)}, {length}) failed: {r}")
        hex_str = r.get("hex") or r.get("data") or ""
        return bytes.fromhex(hex_str)

    def read_u8(self, addr: int) -> int:
        return self.read_bytes(addr, 1)[0]

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read_bytes(addr, 4))[0]

    def write_bytes(self, addr: int, data: bytes) -> None:
        for i, b in enumerate(data):
            r = self.cmd("write_ram", addr=f"0x{addr + i:08X}", val=f"0x{b:02X}")
            if not r.get("ok"):
                raise RuntimeError(f"write_ram({hex(addr + i)}) failed: {r}")

    def write_u8(self, addr: int, val: int) -> None:
        self.write_bytes(addr, bytes([val & 0xFF]))

    def write_u32(self, addr: int, val: int) -> None:
        self.write_bytes(addr, struct.pack("<I", val & 0xFFFFFFFF))

    def screenshot(self, out_path: Path, hires: bool = False) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd_name = "present_shot" if hires else "screenshot_file"
        r: dict[str, Any] = {}
        for _ in range(12):
            r = self.cmd(cmd_name, path=str(out_path))
            if r.get("ok"):
                return out_path
            if hires:
                r = self.cmd("screenshot_file", path=str(out_path))
                if r.get("ok"):
                    return out_path
            if "display disabled" in str(r.get("error", "")):
                self.wait_frames(20)
                continue
            break
        raise RuntimeError(f"screenshot({out_path}) failed: {r}")


class GameSession:
    def __init__(
        self,
        cue_path: Path,
        port: int = 4375,
        headless: bool = True,
        renderer: str | None = None,
        memcard_dir: Path | None = None,
        log_prefix: str = "run",
    ):
        self.cue_path = cue_path
        self.port = port
        self.headless = headless
        self.renderer = renderer
        self.memcard_dir = memcard_dir
        self.log_prefix = log_prefix
        self.proc: subprocess.Popen[bytes] | None = None
        self.stdout_f = None
        self.stderr_f = None
        self.client = DebugClient(port=port)

    def __enter__(self) -> "GameSession":
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_log = OUT_DIR / f"{self.log_prefix}_stdout.log"
        err_log = OUT_DIR / f"{self.log_prefix}_stderr.log"
        self.stdout_f = open(out_log, "wb")
        self.stderr_f = open(err_log, "wb")
        args = [
            str(EXE_DBG),
            "--disc",
            str(self.cue_path),
            "--debug-port",
            str(self.port),
        ]
        if self.memcard_dir is not None:
            self.memcard_dir.mkdir(parents=True, exist_ok=True)
            args.extend(["--memcard-dir", str(self.memcard_dir)])
        if self.headless:
            args.append("--headless")
        if self.renderer:
            args.extend(["--renderer", self.renderer])

        env = os.environ.copy()
        env["PSX_OVERLAY_CACHE_INVENTORY"] = "1"
        env["PSXRECOMP_NO_FORWARD"] = "1"
        self.proc = subprocess.Popen(
            args,
            cwd=str(BUILD_DBG),
            stdout=self.stdout_f,
            stderr=self.stderr_f,
            env=env,
        )
        # Wait for TCP debug server to accept ping
        t0 = time.monotonic()
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"Game exited early with code {self.proc.returncode}; see {err_log}")
            try:
                r = self.client.cmd("ping")
                if r.get("ok") or r.get("pong"):
                    break
            except OSError:
                pass
            if time.monotonic() - t0 > 20.0:
                raise TimeoutError("Timed out waiting for debug server ping")
            time.sleep(0.1)

        self.client.cmd("turbo", enabled=1)
        self.client.cmd("turbo_loads", n=1)
        self.client.cmd("turbo_audio_sink", n=1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.client.cmd("quit")
            except Exception:
                pass
            try:
                self.proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        if self.stdout_f:
            self.stdout_f.close()
        if self.stderr_f:
            self.stderr_f.close()


def collect_telemetry(c: DebugClient, reg: dict[str, int]) -> dict[str, Any]:
    ols = c.cmd("overlay_loader_status")
    drs = c.cmd("dirty_ram_stats")
    spu = c.cmd("spu_status")
    aud = c.cmd("audio_stats")
    ovr_id = c.read_u32(reg["ovr_base"])
    lvl_idx = c.read_u8(reg["game_session"] + 0x04)

    non_kernel_interp_pcs = []
    overlay_interp_pcs = []
    game_code_interp_pcs = []
    for entry in drs.get("per_pc", []):
        pc_str = entry.get("pc", "0x0")
        pc_val = int(pc_str, 16)
        phys = pc_val & 0x1FFFFFFF
        hits = int(entry.get("hits", 0))
        if phys >= 0x10000:
            non_kernel_interp_pcs.append(entry)
            if (0x00020000 <= phys < 0x00035000) or (0x001F5000 <= phys < 0x00200000):
                overlay_interp_pcs.append(entry)
            elif not (0x00180170 <= phys <= 0x001801C0 and hits <= 1):
                # OpenBIOS runs 9 one-shot instructions in 0x180174..0x1801BC prior to EXE load;
                # any other non-kernel PC (or hits > 1) is genuine game code hitting dirty_ram!
                game_code_interp_pcs.append(entry)

    return {
        "frame": c.frame(),
        "ovr_id_ram": f"0x{ovr_id:08X}",
        "level_index_ram": lvl_idx,
        "dispatch_native": int(ols.get("dispatch_native", 0)),
        "dispatch_interp_fallback": int(ols.get("dispatch_interp_fallback", 0)),
        "overlay_registered": int(ols.get("registered", 0)),
        "overlay_last_crc": ols.get("last_crc"),
        "overlay_interp_pcs": overlay_interp_pcs,
        "game_code_interp_pcs": game_code_interp_pcs,
        "non_kernel_interp_pcs": non_kernel_interp_pcs,
        "spu_render_frames": int(spu.get("render_frames", 0)),
        "spu_nonzero_frames": int(spu.get("nonzero_frames", 0)),
        "spu_key_on_count": int(spu.get("key_on_count", 0)),
        "spu_peak": int(spu.get("peak", 0)),
        "spu_cd_push_frames": int(spu.get("cd_push_frames", 0)),
        "audio_pump_calls": int(aud.get("pump_calls", 0)),
    }


def assert_zero_overlay_interp(tel: dict[str, Any], context: str) -> None:
    if tel["overlay_interp_pcs"]:
        raise AssertionError(f"[{context}] Found interpreted OVERLAY PCs (expected 0!): {tel['overlay_interp_pcs']}")
    if tel["game_code_interp_pcs"]:
        raise AssertionError(f"[{context}] Found interpreted GAME EXE PCs (expected 0!): {tel['game_code_interp_pcs']}")


def boot_to_1p_submenu(
    c: DebugClient,
    reg: dict[str, int],
    intro_shot: Path | None = None,
    menu_shot: Path | None = None,
) -> None:
    """Deterministically boot past BIOS + Publisher logos + Intro FMV into 1 PLAYER submenu."""
    # Wait until MOVIE.BIN (@ 0x800201D0) or SHELL.BIN (@ ovr_base == 0x0F) loads
    for _ in range(30):
        if c.read_u32(reg["ovr_base"]) == 0x0F or c.read_u32(reg["movie_base"]) != 0:
            break
        c.wait_frames(30)

    # Let MOVIE.BIN decode active FMV frames natively before capturing intro_shot
    if c.read_u32(reg["ovr_base"]) != 0x0F:
        c.wait_frames(130)
        if intro_shot is not None:
            c.screenshot(intro_shot)

    # Skip remaining publisher logos / Intro FMV ONLY until SHELL.BIN (0x0F) loads
    for _ in range(10):
        if c.read_u32(reg["ovr_base"]) == 0x0F:
            break
        c.press(PAD_START, hold_frames=8, wait_after=170)

    ovr_id = c.read_u32(reg["ovr_base"])
    if ovr_id != 0x0F:
        raise RuntimeError(f"Expected SHELL.BIN (0x0F) at {hex(reg['ovr_base'])}, got {hex(ovr_id)}")

    # Normalize onto Top Menu ([0] 1 PLAYER) via TRIANGLE (no-op if already on Top Menu),
    # then press CROSS once to deterministically enter 1 PLAYER Submenu in all regions.
    c.wait_frames(180)
    c.press(PAD_TRIANGLE, hold_frames=10, wait_after=100)
    c.press(PAD_CROSS, hold_frames=10, wait_after=140)

    if menu_shot is not None:
        c.screenshot(menu_shot)


def force_stage_selection(
    c: DebugClient,
    reg: dict[str, int],
    lvl_idx: int,
    boss1: int = 0,
    boss2: int = 0,
) -> None:
    """Set the 3 stage-selection globals written by SHELL.BIN's LVLSEL right before Car Select."""
    state_ptr = c.read_u32(reg["state_ptr_slot"])
    c.write_u32(reg["lvlsel_idx"], lvl_idx)
    if 0x80000000 <= state_ptr < 0x80200000:
        c.write_u32(state_ptr + 0x12688, lvl_idx)
    c.write_u8(reg["game_session"] + 0x04, lvl_idx)
    c.write_u8(reg["game_session"] + 0x0A, boss1)
    c.write_u8(reg["game_session"] + 0x0B, boss2)


def trigger_match_exit(c: DebugClient, reg: dict[str, int], exit_code: int) -> None:
    """Schedule the game's native match-end timer (func_80132DA0 / func_80132AE4).
    exit_code = 3 -> Quit to Main Menu (SHELL.BIN)
    exit_code = 4 -> Player Won Stage
    """
    c.write_u32(reg["timer_arr"] + 0x00, 0)  # 0 ticks -> 0 - delta < 0 triggers immediately
    c.write_u32(reg["timer_arr"] + 0x04, exit_code)
    c.write_u32(reg["timer_cnt"], 1)


def soak_3d_combat(c: DebugClient, frames: int = 240) -> None:
    """Drive, steer, accelerate, and fire weapons in 3D arena for `frames` frames."""
    # Accelerate + fire machine gun / weapons + slight turn so camera & physics work actively
    c.press(PAD_SQUARE & PAD_R2 & PAD_RIGHT, hold_frames=frames // 3, wait_after=5)
    c.press(PAD_SQUARE & PAD_L2 & PAD_CROSS, hold_frames=frames // 3, wait_after=5)
    c.press(PAD_SQUARE & PAD_R1, hold_frames=frames // 3, wait_after=10)


def run_suite_stages_fullrus() -> dict[str, Any]:
    print("=== [Suite 1] FullRUS: All 12 Arenas + Boss Phases ===")
    reg = REGIONS["US"]
    suite_out = OUT_DIR / "suite1_stages_fullrus"
    suite_out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"suite": "stages_fullrus", "disc": str(CUE_FULLRUS), "stages": []}

    with GameSession(CUE_FULLRUS, port=4375, headless=True, log_prefix="suite1_fullrus") as gs:
        c = gs.client
        boot_to_1p_submenu(
            c,
            reg,
            intro_shot=suite_out / "00_intro_fmv.png",
            menu_shot=suite_out / "01_menu_1p.png",
        )
        tel_boot = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_boot, "FullRUS boot + SHELL.BIN")
        results["boot_telemetry"] = tel_boot

        # Enter Challenge Mode (ПОБЕГ): DOWN -> CROSS -> opens LVLSEL.TMS
        c.press(PAD_DOWN, hold_frames=10, wait_after=80)
        c.press(PAD_CROSS, hold_frames=10, wait_after=240)
        c.screenshot(suite_out / "02_challenge_lvlsel.png")

        for idx_num, (lvl_idx, name, expected_ovr, boss1, boss2, desc) in enumerate(ALL_STAGES):
            print(f"  -> [{idx_num+1:02d}/{len(ALL_STAGES)}] Stage {lvl_idx:02d} {name} ({desc})...")
            # Currently on LVLSEL. Press CROSS to enter Car Select
            c.press(PAD_CROSS, hold_frames=10, wait_after=260)

            # Set exact target stage (0..11) + boss phase flags on Car Select
            force_stage_selection(c, reg, lvl_idx, boss1=boss1, boss2=boss2)
            if idx_num == 0:
                c.screenshot(suite_out / "03_car_select.png")

            # Pick P1 car + enemy setup + launch 3D arena (CROSS, CROSS, START)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            tel_before = collect_telemetry(c, reg)
            c.press(PAD_START, hold_frames=10, wait_after=650)

            # Active 3D combat soak (240 frames)
            soak_3d_combat(c, frames=240)
            shot_path = suite_out / f"stage_{lvl_idx:02d}_{name}.png"
            c.screenshot(shot_path)

            tel_after = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_after, f"FullRUS {name}")

            actual_ovr = int(tel_after["ovr_id_ram"], 16)
            if expected_ovr is not None and actual_ovr != expected_ovr:
                raise AssertionError(
                    f"[{name}] Expected OVR ID 0x{expected_ovr:02X}, got 0x{actual_ovr:08X}"
                )
            native_delta = tel_after["dispatch_native"] - tel_before["dispatch_native"]
            if expected_ovr is not None and native_delta <= 0:
                raise AssertionError(f"[{name}] Expected dispatch_native to grow, delta={native_delta}")

            stage_rec = {
                "stage_index": lvl_idx,
                "name": name,
                "description": desc,
                "expected_ovr_id": f"0x{expected_ovr:02X}" if expected_ovr is not None else "RESIDENT_MAIN_EXE",
                "actual_ovr_id": tel_after["ovr_id_ram"],
                "dispatch_native_delta": native_delta,
                "screenshot": str(shot_path),
                "telemetry": tel_after,
            }
            results["stages"].append(stage_rec)
            print(
                f"     OK: ovr={tel_after['ovr_id_ram']} native_delta=+{native_delta:,} "
                f"spu_nonzero={tel_after['spu_nonzero_frames']:,}"
            )

            # On Stage 0, exercise and screenshot the Pause Menu (START -> ПРОДОЛЖИТЬ)
            if idx_num == 0:
                c.press(PAD_START, hold_frames=10, wait_after=90)
                c.screenshot(suite_out / "04_pause_menu.png")
                c.press(PAD_CROSS, hold_frames=10, wait_after=60)

            # Exit 3D arena cleanly via native match-quit code (exit_code = 3 -> Top Menu SHELL.BIN)
            trigger_match_exit(c, reg, exit_code=3)
            c.wait_frames(380)

            # Wait/verify SHELL.BIN (0x0F) is back at Top Menu ([0] 1 PLAYER)!
            for _ in range(12):
                if c.read_u32(reg["ovr_base"]) == 0x0F:
                    break
                c.wait_frames(120)
            if c.read_u32(reg["ovr_base"]) != 0x0F:
                raise RuntimeError(f"Did not return to SHELL.BIN after {name}")

            # From Top Menu ([0] 1 PLAYER): enter 1 PLAYER -> DOWN (ПОБЕГ) -> CROSS (LVLSEL)
            if idx_num + 1 < len(ALL_STAGES):
                c.wait_frames(150)
                c.press(PAD_CROSS, hold_frames=10, wait_after=140)   # Enter 1 PLAYER
                c.press(PAD_DOWN, hold_frames=10, wait_after=80)     # Highlight ПОБЕГ
                c.press(PAD_CROSS, hold_frames=10, wait_after=240)   # Enter LVLSEL

    out_json = OUT_DIR / "report_stages_fullrus.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"=== [Suite 1] PASSED ({len(results['stages'])} arenas verified) -> {out_json} ===")
    return results


def backup_saves(saves_dir: Path, backup_dir: Path) -> None:
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    if saves_dir.exists():
        shutil.copytree(saves_dir, backup_dir)
        shutil.rmtree(saves_dir)
    saves_dir.mkdir(parents=True, exist_ok=True)


def restore_saves(saves_dir: Path, backup_dir: Path) -> None:
    if saves_dir.exists():
        shutil.rmtree(saves_dir)
    if backup_dir.exists():
        shutil.copytree(backup_dir, saves_dir)
        shutil.rmtree(backup_dir)


def run_suite_campaign_save_ending() -> dict[str, Any]:
    print("=== [Suite 2] FullRUS: Vacation Campaign + MEMC.BIN Save/Load + Final Boss Ending & Credits ===")
    reg = REGIONS["US"]
    suite_out = OUT_DIR / "suite2_campaign_save_ending"
    suite_out.mkdir(parents=True, exist_ok=True)
    memcard_dir = suite_out / "memcards"
    if memcard_dir.exists():
        shutil.rmtree(memcard_dir)
    memcard_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, Any] = {"suite": "campaign_save_ending", "disc": str(CUE_FULLRUS)}
    if True:
        # Part A: Start 1P Vacation (НАЕМНИКИ), beat Stage 0 (AIRPORT), Save to Memory Card (MEMC.BIN)
        with GameSession(
            CUE_FULLRUS,
            port=4375,
            headless=True,
            memcard_dir=memcard_dir,
            log_prefix="suite2_partA_save",
        ) as gs:
            c = gs.client
            boot_to_1p_submenu(c, reg)
            # [0] НАЕМНИКИ (VACATION) is already highlighted! Press CROSS -> Car Select
            c.press(PAD_CROSS, hold_frames=10, wait_after=360)
            c.screenshot(suite_out / "01_vacation_car_select.png")
            # Pick Car: CROSS -> plays Vacation Intro FMV (MERCONOMICS 101), press START to skip into Stage 0 AIRPORT
            c.press(PAD_CROSS, hold_frames=12, wait_after=380)
            c.screenshot(suite_out / "02_vacation_intro_movie_or_load.png")
            for _ in range(5):
                if c.read_u32(reg["ovr_base"]) == 0x05:
                    break
                c.press(PAD_CROSS, hold_frames=10, wait_after=120)
                c.press(PAD_START, hold_frames=10, wait_after=450)

            assert c.read_u32(reg["ovr_base"]) == 0x05, (
                f"Expected AIRPORT (0x05), got {hex(c.read_u32(reg['ovr_base']))}"
            )
            soak_3d_combat(c, frames=180)
            c.screenshot(suite_out / "03_vacation_stage0_airport.png")

            # Win Stage 0 (exit_code = 4) -> Post-Stage Victory Tally (func_80138F8C)
            trigger_match_exit(c, reg, exit_code=4)
            c.wait_frames(420)
            c.screenshot(suite_out / "04_vacation_stage0_victory_tally.png")

            # Advance past Victory Tally into Vacation Between-Stage Hub (func_80136EA4)
            for _ in range(4):
                c.press(PAD_CROSS, hold_frames=10, wait_after=160)
            c.screenshot(suite_out / "05_vacation_between_stage_hub.png")

            # Check if we are in Vacation Hub or already in MEMC / next stage; explore Hub menu to hit MEMC.BIN (0x10)
            # Let's probe Hub options: in func_80136EA4, options include NEXT STAGE / SAVE GAME (СОХР) / QUIT
            entered_memc = False
            for step_i in range(6):
                if c.read_u32(reg["ovr_base"]) == 0x10:
                    entered_memc = True
                    break
                c.press(PAD_DOWN, hold_frames=10, wait_after=70)
                c.screenshot(suite_out / f"05b_hub_opt_{step_i}.png")
                c.press(PAD_CROSS, hold_frames=10, wait_after=280)
                if c.read_u32(reg["ovr_base"]) == 0x10:
                    entered_memc = True
                    break

            results["entered_memc_from_hub"] = entered_memc
            if entered_memc:
                c.screenshot(suite_out / "06_memc_save_loaded.png")
                tel_memc = collect_telemetry(c, reg)
                assert_zero_overlay_interp(tel_memc, "FullRUS MEMC.BIN Save")
                results["memc_save_telemetry"] = tel_memc
                # Perform Save in MEMC.BIN (select card 1 -> slot -> confirm)
                c.press(PAD_CROSS, hold_frames=10, wait_after=180)
                c.screenshot(suite_out / "06b_memc_save_slot.png")
                c.press(PAD_CROSS, hold_frames=10, wait_after=180)
                c.screenshot(suite_out / "06c_memc_save_confirm.png")
                c.press(PAD_UP, hold_frames=10, wait_after=70)
                c.press(PAD_CROSS, hold_frames=10, wait_after=350)
                c.screenshot(suite_out / "06d_memc_after_save.png")

            card_writes = c.cmd("card_data_writes")
            results["card_data_writes"] = card_writes

        # Check .mcd files on disk
        mcd_files = [
            {"name": str(p.relative_to(memcard_dir)), "size": p.stat().st_size}
            for p in sorted(memcard_dir.rglob("*"))
            if p.is_file()
        ]
        results["mcd_files_after_partA"] = mcd_files

        # Part B: Cold Reboot -> Top Menu Load Game (ПРОЧИТАТЬ -> MEMC.BIN) -> Verify Campaign Resumes at Stage 2 (DADDYWOOD)!
        with GameSession(
            CUE_FULLRUS,
            port=4375,
            headless=True,
            memcard_dir=memcard_dir,
            log_prefix="suite2_partB_load",
        ) as gs:
            c = gs.client
            boot_to_1p_submenu(c, reg)
            # Back out from 1P Submenu to Top Menu via TRIANGLE
            c.press(PAD_TRIANGLE, hold_frames=10, wait_after=120)
            c.screenshot(suite_out / "07_top_menu.png")
            # Top Menu: [0] 1 ИГРОК, [1] 2-4 ИГРОКА, [2] ПРОЧИТАТЬ (LOAD GAME -> MEMC.BIN!)
            c.press(PAD_DOWN, hold_frames=10, wait_after=70)
            c.press(PAD_DOWN, hold_frames=10, wait_after=70)
            c.screenshot(suite_out / "07b_top_menu_load_hi.png")
            c.press(PAD_CROSS, hold_frames=10, wait_after=320)

            ovr_memc = c.read_u32(reg["ovr_base"])
            if ovr_memc != 0x10:
                raise AssertionError(f"Expected MEMC.BIN (0x10) on ПРОЧИТАТЬ, got {hex(ovr_memc)}")
            c.screenshot(suite_out / "08_memc_load_screen.png")
            tel_memc_load = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_memc_load, "FullRUS MEMC.BIN Load")
            results["memc_load_telemetry"] = tel_memc_load

            # Select Slot 1 ("ЯТ 1P ДАДДИВУД") -> Confirm Load -> Wait for load bar -> Resumes at Stage 2 DADDYWOOD (lvl_idx == 1)!
            c.press(PAD_CROSS, hold_frames=10, wait_after=180)
            c.screenshot(suite_out / "08b_memc_load_card1.png")
            c.wait_frames(550)
            c.screenshot(suite_out / "08c_resumed_campaign_hub_stage2.png")
            resumed_lvl = c.read_u8(reg["game_session"] + 0x04)
            if resumed_lvl != 1:
                raise AssertionError(f"Expected loaded save to resume at level_index=1 (DADDYWOOD), got {resumed_lvl}")
            soak_3d_combat(c, frames=180)
            c.screenshot(suite_out / "08d_resumed_daddywood_3d.png")
            tel_resumed = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_resumed, "FullRUS Resumed Save DADDYWOOD 3D")
            results["resumed_save_level_index"] = resumed_lvl
            results["resumed_save_telemetry"] = tel_resumed

            # Advance the resumed 1P Vacation campaign to Stage 12 (NUKE, index 11) Final Boss Daddy-O (+0x0B = 1):
            # Set current stage to 9 (SANFRAN, non-bonus so func_80138F8C runs standard tally) -> win -> Hub [0] Continue -> increments to 10;
            # even simpler: set stage to 8 (PARK) before winning, then right on the Between-Stage Hub BEFORE pressing [0] Continue,
            # set game_session[+0x04] = 10 and [+0x0B] = 1 so [0] Continue (80135870: level_index += 1) increments 10 -> 11 (NUKE Daddy-O)!
            trigger_match_exit(c, reg, exit_code=4)
            c.wait_frames(420)
            for _ in range(4):
                c.press(PAD_CROSS, hold_frames=10, wait_after=160)
            # Now inside ЗАПИСАТЬ ИГРУ (MEMC.BIN) because 4th CROSS selected [0] СОХР on the 3-item Hub ([0] СОХР, [1] ПРОДОЛЖИТЬ, [2] ВЫХОД).
            # Press TRIANGLE (НАЗАД) to return to the 3-item Hub, set stage=10 & boss2=1, press DOWN ([1] ПРОДОЛЖИТЬ), and press CROSS -> loads Stage 11 NUKE (0x0E)!
            if c.read_u32(reg["ovr_base"]) == 0x10:
                c.press(PAD_TRIANGLE, hold_frames=10, wait_after=280)
            c.write_u8(reg["game_session"] + 0x04, 10)
            c.write_u8(reg["game_session"] + 0x0B, 1)
            c.press(PAD_DOWN, hold_frames=10, wait_after=80)
            c.screenshot(suite_out / "08e_hub_before_final_boss.png")
            c.press(PAD_CROSS, hold_frames=10, wait_after=900)
            if c.read_u32(reg["ovr_base"]) != 0x0E:
                c.press(PAD_CROSS, hold_frames=10, wait_after=750)

            assert c.read_u32(reg["ovr_base"]) == 0x0E, (
                f"Expected NUKE.BIN (0x0E) for Final Boss, got {hex(c.read_u32(reg['ovr_base']))}"
            )
            # Ensure final_boss_flag (+0x0B) is 1 and level_index (+0x04) is 11
            c.write_u8(reg["game_session"] + 0x04, 11)
            c.write_u8(reg["game_session"] + 0x0B, 1)

            soak_3d_combat(c, frames=240)
            c.screenshot(suite_out / "09_vacation_nuke_daddyo_combat.png")
            tel_boss = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_boss, "FullRUS Vacation Final Boss Daddy-O")
            results["final_boss_telemetry"] = tel_boss

            # Defeat Daddy-O (exit_code = 4) -> triggers func_80138DB8 -> func_8013AFF8:
            # 1) \MOVIES\BOSSEND.STR;1
            # 2) \MOVIES\END%d.STR;1
            # 3) SHELL\CR\CREND1..8.TIM Ending Credits!
            trigger_match_exit(c, reg, exit_code=4)
            c.wait_frames(320)
            c.screenshot(suite_out / "10_ending_fmv_bossend.png")
            tel_end1 = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_end1, "FullRUS BOSSEND.STR FMV")

            # Skip BOSSEND.STR via PAD_CROSS (0x40 in func_8013B100) into Character END*.STR FMV
            c.press(PAD_CROSS, hold_frames=14, wait_after=260)
            c.screenshot(suite_out / "11_ending_fmv_character.png")
            tel_end2 = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_end2, "FullRUS Character END.STR FMV")

            # Skip Character END*.STR via PAD_CROSS into CREND1..8.TIM Ending Credits!
            c.press(PAD_CROSS, hold_frames=14, wait_after=320)
            c.screenshot(suite_out / "12_ending_credits_page1.png")
            # Wait 620 frames (each CREND page displays for 0x258 = 600 frames!) to capture page 2 of Credits too!
            c.wait_frames(620)
            c.screenshot(suite_out / "13_ending_credits_page2.png")
            tel_cred = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_cred, "FullRUS Ending Credits")
            results["ending_credits_telemetry"] = tel_cred

    out_json = OUT_DIR / "report_campaign_save_ending.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"=== [Suite 2] PASSED -> {out_json} ===")
    return results


def run_suite_rus() -> dict[str, Any]:
    print("=== [Suite 3] Rus Disc (SLUS-00643): Intro, SHELL, MEMC, AIRPORT & NUKE 3D ===")
    reg = REGIONS["US"]
    suite_out = OUT_DIR / "suite3_rus"
    suite_out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"suite": "rus", "disc": str(CUE_RUS), "arenas": []}

    with GameSession(CUE_RUS, port=4375, headless=True, log_prefix="suite3_rus") as gs:
        c = gs.client
        boot_to_1p_submenu(
            c,
            reg,
            intro_shot=suite_out / "01_rus_intro.png",
            menu_shot=suite_out / "02_rus_menu_1p.png",
        )
        # Verify MEMC.BIN via Top Menu -> Load
        c.press(PAD_TRIANGLE, hold_frames=10, wait_after=100)
        c.press(PAD_DOWN, hold_frames=10, wait_after=60)
        c.press(PAD_DOWN, hold_frames=10, wait_after=60)
        c.press(PAD_CROSS, hold_frames=10, wait_after=300)
        assert c.read_u32(reg["ovr_base"]) == 0x10, "Rus MEMC.BIN failed to load"
        c.screenshot(suite_out / "03_rus_memc.png")
        tel_memc = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_memc, "Rus MEMC.BIN")
        results["memc_telemetry"] = tel_memc

        # Back to Top Menu (SHELL.BIN resets cursor to [0] 1P) -> 1P -> Challenge -> AIRPORT & NUKE
        c.press(PAD_TRIANGLE, hold_frames=10, wait_after=340)
        for _ in range(10):
            if c.read_u32(reg["ovr_base"]) == 0x0F:
                break
            c.wait_frames(100)
        assert c.read_u32(reg["ovr_base"]) == 0x0F, "Rus SHELL.BIN failed to reload after MEMC.BIN"
        c.wait_frames(120)
        c.press(PAD_CROSS, hold_frames=10, wait_after=140)
        c.press(PAD_DOWN, hold_frames=10, wait_after=80)
        c.press(PAD_CROSS, hold_frames=10, wait_after=240)

        for i, (lvl_idx, name, ovr_id, b1, b2) in enumerate([(0, "AIRPORT", 0x05, 0, 0), (11, "NUKE_DADDYO", 0x0E, 0, 1)]):
            c.press(PAD_CROSS, hold_frames=10, wait_after=260)
            force_stage_selection(c, reg, lvl_idx, boss1=b1, boss2=b2)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            tel_b = collect_telemetry(c, reg)
            c.press(PAD_START, hold_frames=10, wait_after=650)
            soak_3d_combat(c, frames=240)
            shot = suite_out / f"04_rus_{name}.png"
            c.screenshot(shot)
            tel_a = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_a, f"Rus {name}")
            assert int(tel_a["ovr_id_ram"], 16) == ovr_id
            results["arenas"].append({
                "name": name,
                "dispatch_native_delta": tel_a["dispatch_native"] - tel_b["dispatch_native"],
                "screenshot": str(shot),
                "telemetry": tel_a,
            })
            if i == 0:
                trigger_match_exit(c, reg, exit_code=3)
                c.wait_frames(380)
                for _ in range(12):
                    if c.read_u32(reg["ovr_base"]) == 0x0F:
                        break
                    c.wait_frames(120)
                c.wait_frames(150)
                c.press(PAD_CROSS, hold_frames=10, wait_after=140)
                c.press(PAD_DOWN, hold_frames=10, wait_after=80)
                c.press(PAD_CROSS, hold_frames=10, wait_after=240)

    out_json = OUT_DIR / "report_rus.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"=== [Suite 3] PASSED -> {out_json} ===")
    return results


def run_suite_europe() -> dict[str, Any]:
    print("=== [Suite 4] Europe Disc (SLES-01417, PAL 50 Hz): Intro, SHELL, MEMC, Arenas, Final Boss & Ending ===")
    reg = REGIONS["EU"]
    suite_out = OUT_DIR / "suite4_europe"
    suite_out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"suite": "europe", "disc": str(CUE_EUROPE), "arenas": []}

    with GameSession(CUE_EUROPE, port=4375, headless=True, log_prefix="suite4_europe") as gs:
        c = gs.client
        boot_to_1p_submenu(
            c,
            reg,
            intro_shot=suite_out / "01_eu_intro_fmv.png",
            menu_shot=suite_out / "02_eu_menu_1p.png",
        )
        tel_boot = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_boot, "Europe boot + SHELL.BIN")
        results["boot_telemetry"] = tel_boot

        # Test MEMC.BIN (Load Game on English Top Menu)
        c.press(PAD_TRIANGLE, hold_frames=10, wait_after=100)
        c.screenshot(suite_out / "03_eu_top_menu.png")
        c.press(PAD_DOWN, hold_frames=10, wait_after=60)
        c.press(PAD_DOWN, hold_frames=10, wait_after=60)
        c.press(PAD_CROSS, hold_frames=10, wait_after=300)
        assert c.read_u32(reg["ovr_base"]) == 0x10, (
            f"Europe MEMC.BIN failed to load, got {hex(c.read_u32(reg['ovr_base']))}"
        )
        c.screenshot(suite_out / "04_eu_memc_load.png")
        tel_memc = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_memc, "Europe MEMC.BIN")
        results["memc_telemetry"] = tel_memc

        # Back to Top Menu (SHELL.BIN resets cursor to [0] 1 PLAYER) -> Challenge Mode
        c.press(PAD_TRIANGLE, hold_frames=10, wait_after=340)
        for _ in range(10):
            if c.read_u32(reg["ovr_base"]) == 0x0F:
                break
            c.wait_frames(100)
        assert c.read_u32(reg["ovr_base"]) == 0x0F, "Europe SHELL.BIN failed to reload after MEMC.BIN"
        c.wait_frames(120)
        c.press(PAD_CROSS, hold_frames=10, wait_after=140)
        c.press(PAD_DOWN, hold_frames=10, wait_after=80)
        c.press(PAD_CROSS, hold_frames=10, wait_after=240)

        eu_stages = [
            (0, "AIRPORT", 0x05, 0, 0),
            (4, "FUN", 0x0C, 0, 0),
            (5, "VEGAS_BIGDADDY", 0x07, 1, 0),
        ]
        for i, (lvl_idx, name, ovr_id, b1, b2) in enumerate(eu_stages):
            c.press(PAD_CROSS, hold_frames=10, wait_after=260)
            force_stage_selection(c, reg, lvl_idx, boss1=b1, boss2=b2)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            c.press(PAD_CROSS, hold_frames=10, wait_after=110)
            tel_b = collect_telemetry(c, reg)
            c.press(PAD_START, hold_frames=10, wait_after=650)
            soak_3d_combat(c, frames=240)
            shot = suite_out / f"05_eu_{name}.png"
            c.screenshot(shot)
            tel_a = collect_telemetry(c, reg)
            assert_zero_overlay_interp(tel_a, f"Europe {name}")
            assert int(tel_a["ovr_id_ram"], 16) == ovr_id
            results["arenas"].append({
                "name": name,
                "dispatch_native_delta": tel_a["dispatch_native"] - tel_b["dispatch_native"],
                "screenshot": str(shot),
                "telemetry": tel_a,
            })
            trigger_match_exit(c, reg, exit_code=3)
            c.wait_frames(380)
            for _ in range(12):
                if c.read_u32(reg["ovr_base"]) == 0x0F:
                    break
                c.wait_frames(120)
            if i + 1 < len(eu_stages):
                c.wait_frames(150)
                c.press(PAD_CROSS, hold_frames=10, wait_after=140)
                c.press(PAD_DOWN, hold_frames=10, wait_after=80)
                c.press(PAD_CROSS, hold_frames=10, wait_after=240)

        # Now enter 1P Vacation Mode -> Stage 0 AIRPORT -> Hub [0] Continue -> NUKE Final Boss (Daddy-O) -> PAL Ending FMVs & English Credits!
        c.wait_frames(150)
        c.press(PAD_CROSS, hold_frames=10, wait_after=140)   # Enter 1 PLAYER
        c.press(PAD_CROSS, hold_frames=10, wait_after=360)   # Enter VACATION -> Car Select
        c.press(PAD_CROSS, hold_frames=12, wait_after=380)
        for _ in range(5):
            if c.read_u32(reg["ovr_base"]) == 0x05:
                break
            c.press(PAD_CROSS, hold_frames=10, wait_after=120)
            c.press(PAD_START, hold_frames=10, wait_after=450)
        assert c.read_u32(reg["ovr_base"]) == 0x05
        # Win Stage 0 -> Victory Tally -> Hub ([0] SAVE, [1] CONTINUE, [2] QUIT) -> set stage=10, boss2=1 -> [1] CONTINUE -> loads Stage 11 NUKE (0x0E) Daddy-O!
        trigger_match_exit(c, reg, exit_code=4)
        c.wait_frames(420)
        for _ in range(4):
            c.press(PAD_CROSS, hold_frames=10, wait_after=160)
        if c.read_u32(reg["ovr_base"]) == 0x10:
            c.press(PAD_TRIANGLE, hold_frames=10, wait_after=280)
        c.write_u8(reg["game_session"] + 0x04, 10)
        c.write_u8(reg["game_session"] + 0x0B, 1)
        c.press(PAD_DOWN, hold_frames=10, wait_after=80)
        c.press(PAD_CROSS, hold_frames=10, wait_after=900)
        if c.read_u32(reg["ovr_base"]) != 0x0E:
            c.press(PAD_CROSS, hold_frames=10, wait_after=750)
        assert c.read_u32(reg["ovr_base"]) == 0x0E
        c.write_u8(reg["game_session"] + 0x04, 11)
        c.write_u8(reg["game_session"] + 0x0B, 1)
        soak_3d_combat(c, frames=240)
        c.screenshot(suite_out / "06_eu_nuke_daddyo_combat.png")
        tel_boss = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_boss, "Europe NUKE Final Boss Daddy-O")
        results["final_boss_telemetry"] = tel_boss

        trigger_match_exit(c, reg, exit_code=4)
        c.wait_frames(300)
        c.screenshot(suite_out / "07_eu_ending_fmv_bossend.png")
        c.press(PAD_CROSS, hold_frames=14, wait_after=260)
        c.screenshot(suite_out / "08_eu_ending_fmv_character.png")
        c.press(PAD_CROSS, hold_frames=14, wait_after=320)
        c.screenshot(suite_out / "09_eu_ending_credits.png")
        tel_cred = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_cred, "Europe Ending Credits")
        results["ending_credits_telemetry"] = tel_cred

    out_json = OUT_DIR / "report_europe.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"=== [Suite 4] PASSED -> {out_json} ===")
    return results


def run_suite_opengl_release() -> dict[str, Any]:
    print("=== [Suite 5] Windowed OpenGL Hardware Renderer + Standalone Release EXE Smoke Test ===")
    reg = REGIONS["US"]
    suite_out = OUT_DIR / "suite5_opengl_release"
    suite_out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {"suite": "opengl_release"}

    # Part A: Windowed OpenGL Renderer (NO --headless!)
    with GameSession(
        CUE_FULLRUS,
        port=4375,
        headless=False,
        renderer="opengl",
        log_prefix="suite5_opengl_windowed",
    ) as gs:
        c = gs.client
        boot_to_1p_submenu(c, reg, menu_shot=suite_out / "01_opengl_menu.png")
        c.press(PAD_DOWN, hold_frames=10, wait_after=80)
        c.press(PAD_CROSS, hold_frames=10, wait_after=240)
        c.press(PAD_CROSS, hold_frames=10, wait_after=260)
        force_stage_selection(c, reg, lvl_idx=0)
        c.press(PAD_CROSS, hold_frames=10, wait_after=110)
        c.press(PAD_CROSS, hold_frames=10, wait_after=110)
        c.press(PAD_START, hold_frames=10, wait_after=650)
        soak_3d_combat(c, frames=240)

        fbo = c.cmd("gl_fbo_peek", x=120, y=100, w=16, h=4)
        if not fbo.get("ok"):
            raise AssertionError(f"gl_fbo_peek failed in windowed OpenGL mode: {fbo}")
        hex_px = fbo.get("hex", "")
        if not hex_px or all(ch == "0" for ch in hex_px):
            raise AssertionError(f"gl_fbo_peek returned all-zero pixels: {fbo}")

        c.screenshot(suite_out / "02_opengl_airport_present.png", hires=True)
        c.screenshot(suite_out / "03_opengl_airport_vram.png", hires=False)
        tel_gl = collect_telemetry(c, reg)
        assert_zero_overlay_interp(tel_gl, "Windowed OpenGL 3D")
        results["opengl_fbo_peek"] = fbo
        results["opengl_telemetry"] = tel_gl

    # Part B: Production build-release\Rogue_Trip_Recompiled.exe standalone clean-PATH smoke test
    rel_out = OUT_DIR / "suite5_release_stdout.log"
    rel_err = OUT_DIR / "suite5_release_stderr.log"
    clean_env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
        "PATH": r"C:\Windows\System32;C:\Windows",
        "TEMP": os.environ.get("TEMP", r"C:\Windows\Temp"),
        "TMP": os.environ.get("TMP", r"C:\Windows\Temp"),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
        "APPDATA": os.environ.get("APPDATA", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "PSX_OVERLAY_CACHE_INVENTORY": "1",
    }
    with open(rel_out, "wb") as fo, open(rel_err, "wb") as fe:
        proc = subprocess.Popen(
            [str(EXE_REL), "--disc", str(CUE_FULLRUS), "--headless"],
            cwd=str(BUILD_REL),
            env=clean_env,
            stdout=fo,
            stderr=fe,
        )
        time.sleep(8.0)
        alive_after_8s = proc.poll() is None
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()

    stdout_txt = rel_out.read_text(encoding="utf-8", errors="replace")
    stderr_txt = rel_err.read_text(encoding="utf-8", errors="replace")
    if not alive_after_8s:
        raise AssertionError(
            f"Release exe exited prematurely under clean PATH!\nSTDOUT:\n{stdout_txt}\nSTDERR:\n{stderr_txt}"
        )
    import re
    m_sh = re.search(r"(\d+)\s+shared library file\(s\) indexed", stdout_txt + "\n" + stderr_txt)
    shard_cnt = int(m_sh.group(1)) if m_sh else 0
    if shard_cnt < 90:
        raise AssertionError(
            f"Release exe indexed {shard_cnt} overlay shards (expected >= 90)!\nSTDOUT:\n{stdout_txt}\nSTDERR:\n{stderr_txt}"
        )

    results["release_clean_path_smoke"] = {
        "exe": str(EXE_REL),
        "alive_after_8s": alive_after_8s,
        "indexed_shards": shard_cnt,
    }
    out_json = OUT_DIR / "report_opengl_release.json"
    out_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"=== [Suite 5] PASSED -> {out_json} ===")
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--suite",
        choices=["stages_fullrus", "campaign_save_ending", "rus", "europe", "opengl_release", "all"],
        default="all",
    )
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {}
    if args.suite in ("stages_fullrus", "all"):
        summary["stages_fullrus"] = run_suite_stages_fullrus()
    if args.suite in ("campaign_save_ending", "all"):
        summary["campaign_save_ending"] = run_suite_campaign_save_ending()
    if args.suite in ("rus", "all"):
        summary["rus"] = run_suite_rus()
    if args.suite in ("europe", "all"):
        summary["europe"] = run_suite_europe()
    if args.suite in ("opengl_release", "all"):
        summary["opengl_release"] = run_suite_opengl_release()

    if args.suite == "all":
        merged = OUT_DIR / "report_full_suite.json"
        merged.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"ALL 5 SUITES PASSED -> {merged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
