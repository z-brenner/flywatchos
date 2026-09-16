#!/usr/bin/env python3
"""Unicorn harness proving the Task-5 Gate-1 trace stub is PASSIVE.

Offline only. Emulates the hand-assembled Gate-1 capture stub (trace_stubs.py)
and proves, within the model, that it:

  * captures the four spec'd values (current TCB, IPSR/exception number, USB
    mutex recursion depth, USB mutex owner TCB) into the ring buffer;
  * preserves r0 (=USB mutex base, consumed by the displaced unlock), lr, and
    sp exactly, and restores r1/r2/r3/r12;
  * confines every store to the ring buffer region;
  * NEVER reaches the queue-send (0x67D8), any lock (0x8500/0x8734), the display
    owner (0x9A10/0xE1A4), or the reschedule primitive (0x5D2C); it reaches only
    the mandatory displaced original unlock at 0x874C, where the stub's
    responsibility ends;
  * behaves identically in thread context (IPSR==0) and a modelled exception
    context (IPSR!=0) — the context the investigation proved is undeterminable.

WHAT THIS HARNESS CANNOT MODEL (documented, not hand-waved):
  * real NVIC preemption / interrupt priorities (the ISR-vs-thread question);
  * whether 0x20A8A executes before USB enumerates (boot-time ordering);
  * ownership of the ring-buffer RAM (Round 4 proved none is provable);
  * the external-region veneers under the USB mutex (do not decode);
  * the flash controller and real timing/latency.
Model-passivity is necessary but NOT sufficient for flash safety. See
docs/atlas-shell-usb-detach-trace.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from trace_stubs import (  # noqa: E402
    PAYLOAD_BASE,
    RING_BASE,
    RING_HEAD,
    RING_MASK,
    RING_RECORD_BYTES,
    TCB_PTR,
    UNLOCK_VA,
    USB_MUTEX,
    gate1_stub,
    gate1_stub_null,
)

from unicorn import (  # noqa: E402
    UC_ARCH_ARM,
    UC_HOOK_CODE,
    UC_HOOK_MEM_READ_UNMAPPED,
    UC_HOOK_MEM_WRITE,
    UC_HOOK_MEM_WRITE_UNMAPPED,
    UC_MODE_THUMB,
    Uc,
    UcError,
)
from unicorn.arm_const import (  # noqa: E402
    UC_CPU_ARM_CORTEX_M4,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_R12,
    UC_ARM_REG_SP,
)

# primitives a passive probe must never enter (0x874C is the ALLOWED displaced
# original and is the stop boundary, not a violation).
FORBIDDEN = {
    0x67D8: "queue_send",
    0x8500: "mutex_lock_timeout",
    0x8734: "blocking_lock",
    0x9A10: "display_owner_lock",
    0xE1A4: "display_submit",
    0x5D2C: "reschedule_yield",
    0x6224: "queue_notify",
}

LR_SENTINEL = 0xABCDEF01  # scheduler return address; must be preserved verbatim


def _mrs_next_offset() -> int:
    """Offset of the instruction AFTER `mrs ip, ipsr`, for IPSR injection."""
    import capstone

    asm = gate1_stub()
    md = capstone.Cs(
        capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS
    )
    for ins in md.disasm(asm.code, PAYLOAD_BASE):
        if ins.mnemonic == "mrs":
            return (ins.address - PAYLOAD_BASE) + ins.size
    raise RuntimeError("mrs not found in stub")


def emulate_gate1(
    *, tcb: int, owner: int, recursion: int, ipsr: int, head: int = 0, stub_factory=None
) -> dict:
    """Run the Gate-1 stub once. Returns a dict of proof facts.

    stub_factory lets a test swap in the RED null stub (gate1_stub_null) to
    prove the capture-correctness assertions are non-vacuous.
    """
    factory = stub_factory or gate1_stub
    asm = factory()
    mrs_next_va = PAYLOAD_BASE + _mrs_next_offset()

    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    mu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)

    # memory map
    mu.mem_map(0x001FA000, 0x1000)                    # code cave
    mu.mem_map(0x1FFC0000, 0x00010000)                # RTOS fixed RAM (mutex, TCB)
    mu.mem_map(0x20010000, 0x00010000)                # probe stack
    mu.mem_map(0x2003F000, 0x1000)                    # ring buffer region
    mu.mem_write(PAYLOAD_BASE, asm.code)

    # seed the values the stub will read
    mu.mem_write(TCB_PTR, tcb.to_bytes(4, "little"))
    mu.mem_write(USB_MUTEX + 8, owner.to_bytes(4, "little"))
    mu.mem_write(USB_MUTEX + 0x18, (recursion & 0xFFFF).to_bytes(2, "little"))
    mu.mem_write(RING_HEAD, head.to_bytes(4, "little"))

    sp_top = 0x20018000
    mu.reg_write(UC_ARM_REG_SP, sp_top)
    mu.reg_write(UC_ARM_REG_R0, USB_MUTEX)            # r0 must survive verbatim
    mu.reg_write(UC_ARM_REG_LR, LR_SENTINEL)          # lr must survive verbatim
    # poison the scratch regs so "restored" is meaningful
    for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R12):
        mu.reg_write(reg, 0xBAD00000 | reg)
    poisoned = {
        UC_ARM_REG_R1: mu.reg_read(UC_ARM_REG_R1),
        UC_ARM_REG_R2: mu.reg_read(UC_ARM_REG_R2),
        UC_ARM_REG_R3: mu.reg_read(UC_ARM_REG_R3),
        UC_ARM_REG_R12: mu.reg_read(UC_ARM_REG_R12),
    }

    state = {
        "reached_unlock": False,
        "violation": None,
        "writes": [],
        "unmapped": None,
        "instr_count": 0,
    }

    def hook_code(uc, address, size, _user):
        state["instr_count"] += 1
        if address == UNLOCK_VA:
            state["reached_unlock"] = True
            uc.emu_stop()
            return
        if address in FORBIDDEN:
            state["violation"] = (address, FORBIDDEN[address])
            uc.emu_stop()
            return
        if address == mrs_next_va:
            # model the execution context: inject the tested IPSR value
            uc.reg_write(UC_ARM_REG_R12, ipsr & 0x1FF)
        if state["instr_count"] > 5000:
            state["violation"] = (address, "runaway")
            uc.emu_stop()

    def hook_write(_uc, _access, address, size, value, _user):
        state["writes"].append((address, size, value & ((1 << (size * 8)) - 1)))

    def hook_unmapped(_uc, _access, address, size, _value, _user):
        state["unmapped"] = (address, size)
        return False

    mu.hook_add(UC_HOOK_CODE, hook_code)
    mu.hook_add(UC_HOOK_MEM_WRITE, hook_write)
    mu.hook_add(
        UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED, hook_unmapped
    )

    try:
        mu.emu_start(PAYLOAD_BASE | 1, UNLOCK_VA, count=5000)
    except UcError as exc:
        state["uc_error"] = str(exc)
    # emu_start(until=UNLOCK_VA) stops with PC==UNLOCK_VA *before* the code hook
    # fires for that address, so confirm arrival by the final PC.
    if mu.reg_read(UC_ARM_REG_PC) == UNLOCK_VA:
        state["reached_unlock"] = True

    # read back the record that was written
    slot_index = head & RING_MASK
    slot = RING_BASE + slot_index * RING_RECORD_BYTES
    rec = mu.mem_read(slot, RING_RECORD_BYTES)
    w = [int.from_bytes(rec[i : i + 4], "little") for i in range(0, 16, 4)]
    new_head = int.from_bytes(mu.mem_read(RING_HEAD, 4), "little")

    regs = {
        "r0": mu.reg_read(UC_ARM_REG_R0),
        "lr": mu.reg_read(UC_ARM_REG_LR),
        "sp": mu.reg_read(UC_ARM_REG_SP),
        "r1": mu.reg_read(UC_ARM_REG_R1),
        "r2": mu.reg_read(UC_ARM_REG_R2),
        "r3": mu.reg_read(UC_ARM_REG_R3),
        "r12": mu.reg_read(UC_ARM_REG_R12),
    }

    # a passive probe may write only its own stack (push/pop) and the ring buffer
    ring_lo, ring_hi = 0x2003F000, 0x2003F000 + 0x1000
    stack_lo, stack_hi = 0x20010000, 0x20020000

    def _region(a: int) -> str:
        if ring_lo <= a < ring_hi:
            return "ring"
        if stack_lo <= a < stack_hi:
            return "stack"
        return "other"

    write_regions = [_region(a) for (a, _s, _v) in state["writes"]]
    writes_confined = all(r != "other" for r in write_regions)
    ring_writes = [wr for wr, reg in zip(state["writes"], write_regions) if reg == "ring"]
    stack_writes = [wr for wr, reg in zip(state["writes"], write_regions) if reg == "stack"]

    record = {
        "captured_tcb": w[0],
        "captured_owner": w[1],
        "captured_recursion": w[2] & 0xFFFF,
        "captured_ipsr": (w[2] >> 16) & 0xFFFF,
        "captured_marker": w[3],
    }
    return {
        "inputs": {
            "tcb": tcb,
            "owner": owner,
            "recursion": recursion,
            "ipsr": ipsr,
            "head": head,
        },
        "record": record,
        "record_correct": (
            record["captured_tcb"] == tcb
            and record["captured_owner"] == owner
            and record["captured_recursion"] == (recursion & 0xFFFF)
            and record["captured_ipsr"] == (ipsr & 0x1FF)
            and record["captured_marker"] == 0x0A8A
        ),
        "reached_unlock": state["reached_unlock"],
        "violation": state["violation"],
        "unmapped": state["unmapped"],
        "uc_error": state.get("uc_error"),
        "regs": regs,
        "r0_preserved": regs["r0"] == USB_MUTEX,
        "lr_preserved": regs["lr"] == LR_SENTINEL,
        "sp_balanced": regs["sp"] == sp_top,
        "scratch_restored": all(
            regs[name] == poisoned[reg]
            for name, reg in (
                ("r1", UC_ARM_REG_R1),
                ("r2", UC_ARM_REG_R2),
                ("r3", UC_ARM_REG_R3),
                ("r12", UC_ARM_REG_R12),
            )
        ),
        "writes": state["writes"],
        "writes_confined": writes_confined,
        "ring_write_count": len(ring_writes),
        "stack_write_count": len(stack_writes),
        "head_advanced": new_head == head + 1,
        "instr_count": state["instr_count"],
    }


UNMODELLED = [
    "real NVIC preemption / interrupt priority (thread-vs-ISR at 0x20A8A)",
    "whether 0x20A8A executes before USB enumerates (boot-time ordering)",
    "ring-buffer RAM ownership (Round 4: no statically-exclusive store exists)",
    "external-region veneers run under the USB mutex (do not decode)",
    "flash controller behaviour and real execution latency",
    "concurrent writers to the ring buffer under true preemption",
]


if __name__ == "__main__":
    import json

    cases = [
        dict(tcb=0x1FFCA000, owner=0x1FFCA000, recursion=0, ipsr=0x000, head=0),
        dict(tcb=0x1FFCA000, owner=0, recursion=1, ipsr=0x00B, head=5),
        dict(tcb=0x20001234, owner=0x20005678, recursion=3, ipsr=0x0F0, head=63),
    ]
    for c in cases:
        r = emulate_gate1(**c)
        ok = (
            r["record_correct"]
            and r["reached_unlock"]
            and r["violation"] is None
            and r["r0_preserved"]
            and r["lr_preserved"]
            and r["sp_balanced"]
            and r["scratch_restored"]
            and r["writes_confined"]
            and r["head_advanced"]
        )
        print(("PASS" if ok else "FAIL"), json.dumps(c), "instr=", r["instr_count"])
        if not ok:
            print(json.dumps(r, indent=2, default=str))
    print("\nUNMODELLED (offline validation cannot reach these):")
    for u in UNMODELLED:
        print("  -", u)
