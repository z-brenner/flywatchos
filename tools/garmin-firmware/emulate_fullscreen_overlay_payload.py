#!/usr/bin/env python3
"""Instruction-level offline emulator for the compiled full-screen FR245 overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from unicorn import (
    UC_ARCH_ARM,
    UC_HOOK_CODE,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MODE_LITTLE_ENDIAN,
    UC_MODE_THUMB,
    Uc,
)
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
WIDTH = 240
HEIGHT = 240
FRAMEBUFFER_SIZE = WIDTH * HEIGHT
ACTIVE_BACKEND = 0x1FFDB754
STARTUP_COMPLETE = 0x1FFF223C
STACK_POINTER = 0x20018000
RETURN_SENTINEL = 0x00001000
GUARD_SIZE = 64
GPIO_PAGE = 0x400FF000
GPIOA_PDIR = 0x400FF010
GPIOC_PDIR = 0x400FF090
GPIOD_PDIR = 0x400FF0D0
BUTTONS = (
    (GPIOC_PDIR, 0x00000800),
    (GPIOD_PDIR, 0x00000400),
    (GPIOD_PDIR, 0x00000002),
    (GPIOA_PDIR, 0x00100000),
    (GPIOA_PDIR, 0x00400000),
)

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


def emulate(
    payload: bytes,
    initialized: bool = True,
    fill: int = 0x2A,
    pressed_mask: int = 0,
) -> dict[str, Any]:
    if not payload or len(payload) > 0x400:
        raise ValueError("payload is outside the audited 1 KiB overlay allocation")
    if not 0 <= fill <= 0xFF:
        raise ValueError("fill must fit in one byte")
    if pressed_mask & ~0x1F:
        raise ValueError("pressed_mask has unknown button bits")

    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    machine.mem_map(0x00000000, 0x00200000)
    machine.mem_map(0x1FFC0000, 0x00060000)
    machine.mem_map(GPIO_PAGE, 0x1000)
    machine.mem_write(OVERLAY, payload)

    guard_before = bytes((0x31 + index * 17) & 0xFF for index in range(GUARD_SIZE))
    guard_after = bytes((0xC7 - index * 13) & 0xFF for index in range(GUARD_SIZE))
    machine.mem_write(FRAMEBUFFER - GUARD_SIZE, guard_before)
    machine.mem_write(FRAMEBUFFER, bytes([fill]) * FRAMEBUFFER_SIZE)
    machine.mem_write(FRAMEBUFFER + FRAMEBUFFER_SIZE, guard_after)
    machine.mem_write(
        ACTIVE_BACKEND,
        (0x0000EBFC if initialized else 0).to_bytes(4, "little"),
    )
    machine.mem_write(STARTUP_COMPLETE, bytes([1 if initialized else 0]))

    pdir = {GPIOA_PDIR: 0xFFFFFFFF, GPIOC_PDIR: 0xFFFFFFFF, GPIOD_PDIR: 0xFFFFFFFF}
    for index, (address, mask) in enumerate(BUTTONS):
        if pressed_mask & (1 << index):
            pdir[address] &= ~mask
    for address, value in pdir.items():
        machine.mem_write(address, value.to_bytes(4, "little"))

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
    peripheral_reads: list[list[int]] = []
    peripheral_writes: list[list[int]] = []
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
    machine.hook_add(
        UC_HOOK_MEM_READ,
        lambda uc, access, address, size, value, user: peripheral_reads.append(
            [address, size]
        ),
        begin=GPIO_PAGE,
        end=GPIO_PAGE + 0xFFF,
    )
    machine.hook_add(
        UC_HOOK_MEM_WRITE,
        lambda uc, access, address, size, value, user: peripheral_writes.append(
            [address, size, value]
        ),
        begin=GPIO_PAGE,
        end=GPIO_PAGE + 0xFFF,
    )
    machine.emu_start(OVERLAY | 1, 0, count=1_000_000)

    framebuffer = bytes(machine.mem_read(FRAMEBUFFER, FRAMEBUFFER_SIZE))
    before_unchanged = (
        bytes(machine.mem_read(FRAMEBUFFER - GUARD_SIZE, GUARD_SIZE))
        == guard_before
    )
    after_unchanged = (
        bytes(machine.mem_read(FRAMEBUFFER + FRAMEBUFFER_SIZE, GUARD_SIZE))
        == guard_after
    )
    preserved = all(
        machine.reg_read(register) == value
        for register, value in initial_registers.items()
    )
    return {
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "initialized": initialized,
        "initial_fill": fill,
        "pressed_mask": pressed_mask,
        "instruction_count": instruction_count,
        "dirty_calls": dirty_calls,
        "dispatch_calls": dispatch_calls,
        "peripheral_reads": peripheral_reads,
        "peripheral_writes": peripheral_writes,
        "framebuffer_sha256": hashlib.sha256(framebuffer).hexdigest(),
        "framebuffer": framebuffer,
        "input_sentinel_remaining": framebuffer.count(fill),
        "foreground_zero_bytes": framebuffer.count(0x00),
        "background_ff_bytes": framebuffer.count(0xFF),
        "all_pixels_monochrome": all(pixel in (0x00, 0xFF) for pixel in framebuffer),
        "guard_before_unchanged": before_unchanged,
        "guard_after_unchanged": after_unchanged,
        "callee_saved_registers_preserved": preserved,
        "stack_pointer_restored": machine.reg_read(UC_ARM_REG_SP) == STACK_POINTER,
    }


def public_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "framebuffer"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()

    payload = args.payload.read_bytes()
    first = emulate(payload, initialized=True, fill=0x2A)
    second = emulate(payload, initialized=True, fill=0xA5)
    skipped = emulate(payload, initialized=False, fill=0x2A)
    report = {
        "tool": "tools/garmin-firmware/emulate_fullscreen_overlay_payload.py",
        "scope": "compiled Thumb overlay only; external calls intercepted",
        "initialized_fill_2a": public_result(first),
        "initialized_fill_a5": public_result(second),
        "deterministic_across_inputs": first["framebuffer"] == second["framebuffer"],
        "owned_pixel_count": sum(
            one == two and one in (0x00, 0xFF)
            for one, two in zip(first["framebuffer"], second["framebuffer"])
        ),
        "uninitialized_display": public_result(skipped),
        "limitations": [
            "Dirty-list and backend functions are intercepted at their entry points.",
            "The emulator does not model GarminOS scheduling, DMA, FlexIO, or the LCD panel.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.preview is not None:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        args.preview.write_bytes(b"P5\n240 240\n255\n" + first["framebuffer"])
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
