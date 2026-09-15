#!/usr/bin/env python3
"""Instruction-level offline emulator for the compiled FR245 overlay payload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_LITTLE_ENDIAN, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_R4,
    UC_ARM_REG_R5,
    UC_ARM_REG_R6,
    UC_ARM_REG_R7,
    UC_ARM_REG_R8,
    UC_ARM_REG_R9,
    UC_ARM_REG_R10,
    UC_ARM_REG_R11,
    UC_ARM_REG_SP,
)


OVERLAY = 0x001F6000
DIRTY_ADD = 0x0000F2E8
DISPATCH = 0x0000E1A4
FRAMEBUFFER = 0x1FFDE6E8
FRAMEBUFFER_SIZE = 240 * 240
ACTIVE_BACKEND = 0x1FFDB754
STARTUP_COMPLETE = 0x1FFF223C
STACK_POINTER = 0x20018000
RETURN_SENTINEL = 0x00001000
DRAW_X = 50
DRAW_Y = 102
DRAW_WIDTH = 140
DRAW_HEIGHT = 22
FLY_X = 54
FLY_Y = 105
FLY_WIDTH = 21
FLY_HEIGHT = 16
TEXT_X = 80
TEXT_Y = 106
TEXT_WIDTH = 106
TEXT_HEIGHT = 14

CALLEE_REGISTERS = [
    UC_ARM_REG_R4,
    UC_ARM_REG_R5,
    UC_ARM_REG_R6,
    UC_ARM_REG_R7,
    UC_ARM_REG_R8,
    UC_ARM_REG_R9,
    UC_ARM_REG_R10,
    UC_ARM_REG_R11,
]


def emulate(payload: bytes, initialized: bool = True) -> dict[str, Any]:
    if not payload or len(payload) > 0x400:
        raise ValueError("payload is outside the reserved overlay allocation")
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    machine.mem_map(0x00000000, 0x00200000)
    machine.mem_map(0x1FFC0000, 0x00060000)
    machine.mem_write(OVERLAY, payload)
    machine.mem_write(FRAMEBUFFER, bytes([0x2A]) * FRAMEBUFFER_SIZE)
    machine.mem_write(
        ACTIVE_BACKEND,
        (0x0000EBFC if initialized else 0).to_bytes(4, "little"),
    )
    machine.mem_write(STARTUP_COMPLETE, bytes([1 if initialized else 0]))

    initial_registers = {
        register: 0x44440000 + index * 0x1111
        for index, register in enumerate(CALLEE_REGISTERS)
    }
    for register, value in initial_registers.items():
        machine.reg_write(register, value)
    machine.reg_write(UC_ARM_REG_SP, STACK_POINTER)
    machine.reg_write(UC_ARM_REG_LR, RETURN_SENTINEL | 1)
    machine.reg_write(UC_ARM_REG_R0, FRAMEBUFFER)
    machine.reg_write(UC_ARM_REG_R1, 0)

    dirty_calls: list[list[int]] = []
    dispatch_calls: list[list[int]] = []
    instruction_count = 0

    def on_code(uc: Uc, address: int, size: int, _: Any) -> None:
        nonlocal instruction_count
        instruction_count += 1
        if address == DIRTY_ADD:
            dirty_calls.append(
                [
                    uc.reg_read(UC_ARM_REG_R0),
                    uc.reg_read(UC_ARM_REG_R1),
                    uc.reg_read(UC_ARM_REG_R2),
                    uc.reg_read(UC_ARM_REG_R3),
                ]
            )
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == DISPATCH:
            dispatch_calls.append(
                [uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)]
            )
            uc.emu_stop()

    machine.hook_add(UC_HOOK_CODE, on_code)
    machine.emu_start(OVERLAY | 1, 0, count=1_000_000)

    framebuffer = bytes(machine.mem_read(FRAMEBUFFER, FRAMEBUFFER_SIZE))
    changed = [index for index, byte in enumerate(framebuffer) if byte != 0x2A]
    outside = 0
    for index in changed:
        y, x = divmod(index, 240)
        if not (
            DRAW_X <= x < DRAW_X + DRAW_WIDTH
            and DRAW_Y <= y < DRAW_Y + DRAW_HEIGHT
        ):
            outside += 1
    region = b"".join(
        framebuffer[(DRAW_Y + row) * 240 + DRAW_X : (DRAW_Y + row) * 240 + DRAW_X + DRAW_WIDTH]
        for row in range(DRAW_HEIGHT)
    )
    fly_region = b"".join(
        framebuffer[(FLY_Y + row) * 240 + FLY_X : (FLY_Y + row) * 240 + FLY_X + FLY_WIDTH]
        for row in range(FLY_HEIGHT)
    )
    text_region = b"".join(
        framebuffer[(TEXT_Y + row) * 240 + TEXT_X : (TEXT_Y + row) * 240 + TEXT_X + TEXT_WIDTH]
        for row in range(TEXT_HEIGHT)
    )
    top_border = framebuffer[DRAW_Y * 240 + DRAW_X : DRAW_Y * 240 + DRAW_X + DRAW_WIDTH]
    bottom_border = framebuffer[
        (DRAW_Y + DRAW_HEIGHT - 1) * 240 + DRAW_X :
        (DRAW_Y + DRAW_HEIGHT - 1) * 240 + DRAW_X + DRAW_WIDTH
    ]
    side_border_ok = all(
        framebuffer[(DRAW_Y + row) * 240 + DRAW_X] == 0x00
        and framebuffer[(DRAW_Y + row) * 240 + DRAW_X + DRAW_WIDTH - 1] == 0x00
        for row in range(DRAW_HEIGHT)
    )
    preserved = all(
        machine.reg_read(register) == value
        for register, value in initial_registers.items()
    )
    return {
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "initialized": initialized,
        "instruction_count": instruction_count,
        "dirty_calls": dirty_calls,
        "dispatch_calls": dispatch_calls,
        "framebuffer_changed_bytes": len(changed),
        "outside_draw_region_changed_bytes": outside,
        "foreground_zero_bytes": region.count(0x00),
        "background_ff_bytes": region.count(0xFF),
        "fly_foreground_zero_bytes": fly_region.count(0x00),
        "text_foreground_zero_bytes": text_region.count(0x00),
        "plate_border_complete": (
            top_border == bytes([0x00]) * DRAW_WIDTH
            and bottom_border == bytes([0x00]) * DRAW_WIDTH
            and side_border_ok
        ),
        "draw_region_sha256": hashlib.sha256(region).hexdigest(),
        "callee_saved_registers_preserved": preserved,
        "stack_pointer_restored": machine.reg_read(UC_ARM_REG_SP) == STACK_POINTER,
    }


def render_preview(payload: bytes, output: Path) -> None:
    """Render the initialized compiled payload as a dependency-free PGM image."""
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    machine.mem_map(0x00000000, 0x00200000)
    machine.mem_map(0x1FFC0000, 0x00060000)
    machine.mem_write(OVERLAY, payload)
    machine.mem_write(FRAMEBUFFER, bytes([0xD8]) * FRAMEBUFFER_SIZE)
    machine.mem_write(ACTIVE_BACKEND, (0x0000EBFC).to_bytes(4, "little"))
    machine.mem_write(STARTUP_COMPLETE, b"\x01")
    machine.reg_write(UC_ARM_REG_SP, STACK_POINTER)
    machine.reg_write(UC_ARM_REG_LR, RETURN_SENTINEL | 1)
    machine.reg_write(UC_ARM_REG_R0, FRAMEBUFFER)
    machine.reg_write(UC_ARM_REG_R1, 0)

    def on_code(uc: Uc, address: int, size: int, _: Any) -> None:
        if address == DIRTY_ADD:
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == DISPATCH:
            uc.emu_stop()

    machine.hook_add(UC_HOOK_CODE, on_code)
    machine.emu_start(OVERLAY | 1, 0, count=1_000_000)
    pixels = bytes(machine.mem_read(FRAMEBUFFER, FRAMEBUFFER_SIZE))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"P5\n240 240\n255\n" + pixels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    payload = args.payload.read_bytes()
    report = {
        "tool": "tools/garmin-firmware/emulate_overlay_payload.py",
        "scope": "compiled Thumb overlay only; external calls intercepted",
        "initialized_display": emulate(payload, initialized=True),
        "uninitialized_display": emulate(payload, initialized=False),
        "limitations": [
            "Dirty-list and backend functions are intercepted at their entry points, not emulated.",
            "The emulator does not model GarminOS scheduling, locks, DMA, FlexIO, or the LCD panel.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.preview is not None:
        render_preview(payload, args.preview)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
