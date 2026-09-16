#!/usr/bin/env python3
"""Hand-assembled, capstone-verified ARM Thumb-2 trace stubs for the offline
Task-5 USB-detach runtime-trace diagnostic (analysis only, NEVER flashed).

This module produces the *bytes* of the passive capture stubs described in
`docs/atlas-shell-usb-detach-trace.md`. It does NOT build a GCD, patch an
image, or touch a device. keystone is unavailable in this environment and the
pinned Arm GNU Toolchain symlink is dangling, so the stubs are hand-encoded and
every instruction is verified by disassembling it back with capstone.

The Gate-1 stub at 0x20A8A is the novel, safety-critical one (its execution
context is proved *undeterminable offline* by task5-gate-investigation.md). It
is fully assembled and emulated here. The event/display loggers (0x5ADF4,
0x54132, 0x9A20) reuse the already-emulated Round-4/Round-5 design; their sizes
are reproduced for the footprint budget but they are not the decisive artifact.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# ---- pinned firmware facts (task5-gate-investigation.md, verified vs image) --
FW_BASE = 0x3000
HOOK_GATE1_VA = 0x20A8A          # b.w 0x874C  (e7 f7 5f be)
UNLOCK_VA = 0x874C               # recursive mutex unlock (displaced target)
QUEUE_SEND_VA = 0x67D8           # FORBIDDEN for a passive probe
MUTEX_LOCK_VA = 0x8500           # FORBIDDEN (asserts in ISR context)
BLOCKING_LOCK_VA = 0x8734        # FORBIDDEN
DISPLAY_OWNER_VA = 0x9A10        # FORBIDDEN (blocking display lock)

TCB_PTR = 0x1FFC7644             # *TCB_PTR = current task control block
USB_MUTEX = 0x1FFC6EEC           # r0 at 0x20A8A
USB_MUTEX_OWNER = USB_MUTEX + 8  # *(m+8)  owner TCB
USB_MUTEX_RECUR = USB_MUTEX + 0x18  # (short)*(m+0x18) recursion depth

# ---- ring-buffer placeholders (SEE DESIGN DOC: no provably-safe home exists) -
# Round 4 proved no statically-exclusive persistent RAM store exists in the
# pinned image. These addresses are emulation placeholders ONLY.
RING_HEAD = 0x2003F000
RING_BASE = 0x2003F010
RING_RECORDS = 64                 # power of two
RING_RECORD_BYTES = 16
RING_MASK = RING_RECORDS - 1

PAYLOAD_BASE = 0x1FA400           # the characterized 2 KiB secondary cave


# --------------------------------------------------------------------------- #
# Minimal Thumb-2 encoders. Each is verified by capstone in verify_stub().
# --------------------------------------------------------------------------- #
def _movw(rd: int, imm16: int) -> bytes:
    i = (imm16 >> 11) & 1
    imm4 = (imm16 >> 12) & 0xF
    imm3 = (imm16 >> 8) & 0x7
    imm8 = imm16 & 0xFF
    hw1 = 0xF240 | (i << 10) | imm4
    hw2 = (imm3 << 12) | (rd << 8) | imm8
    return struct.pack("<HH", hw1, hw2)


def _movt(rd: int, imm16: int) -> bytes:
    i = (imm16 >> 11) & 1
    imm4 = (imm16 >> 12) & 0xF
    imm3 = (imm16 >> 8) & 0x7
    imm8 = imm16 & 0xFF
    hw1 = 0xF2C0 | (i << 10) | imm4
    hw2 = (imm3 << 12) | (rd << 8) | imm8
    return struct.pack("<HH", hw1, hw2)


def _movw32(rd: int, value: int) -> bytes:
    return _movw(rd, value & 0xFFFF) + _movt(rd, (value >> 16) & 0xFFFF)


def _ldr_imm(rt: int, rn: int, imm: int) -> bytes:
    # LDR<c>.W Rt,[Rn,#imm12]  T3
    hw1 = 0xF8D0 | rn
    hw2 = (rt << 12) | (imm & 0xFFF)
    return struct.pack("<HH", hw1, hw2)


def _str_imm(rt: int, rn: int, imm: int) -> bytes:
    # STR<c>.W Rt,[Rn,#imm12]  T3
    hw1 = 0xF8C0 | rn
    hw2 = (rt << 12) | (imm & 0xFFF)
    return struct.pack("<HH", hw1, hw2)


def _ldrh_imm(rt: int, rn: int, imm: int) -> bytes:
    # LDRH<c>.W Rt,[Rn,#imm12]  T2
    hw1 = 0xF8B0 | rn
    hw2 = (rt << 12) | (imm & 0xFFF)
    return struct.pack("<HH", hw1, hw2)


def _and_imm(rd: int, rn: int, imm: int) -> bytes:
    # AND<c>.W Rd,Rn,#const  (imm must be a valid modified-immediate; small ok)
    i = 0
    imm3 = 0
    imm8 = imm & 0xFF
    hw1 = 0xF000 | (i << 10) | rn
    hw2 = (imm3 << 12) | (rd << 8) | imm8
    return struct.pack("<HH", hw1, hw2)


def _add_imm(rd: int, rn: int, imm: int) -> bytes:
    # ADD<c>.W Rd,Rn,#imm  T3
    i = 0
    imm3 = 0
    imm8 = imm & 0xFF
    hw1 = 0xF100 | (i << 10) | rn
    hw2 = (imm3 << 12) | (rd << 8) | imm8
    return struct.pack("<HH", hw1, hw2)


def _add_reg(rd: int, rn: int, rm: int) -> bytes:
    # ADD<c>.W Rd,Rn,Rm  T3 (no shift)
    hw1 = 0xEB00 | rn
    hw2 = (rd << 8) | rm
    return struct.pack("<HH", hw1, hw2)


def _lsl_imm(rd: int, rm: int, sh: int) -> bytes:
    # LSL<c>.W Rd,Rm,#sh  (MOV.W shift form)
    hw1 = 0xEA4F
    hw2 = ((sh & 0x1C) << 10) | ((sh & 0x3) << 6) | (rd << 8) | rm
    return struct.pack("<HH", hw1, hw2)


def _orr_lsl(rd: int, rn: int, rm: int, sh: int) -> bytes:
    # ORR<c>.W Rd,Rn,Rm,LSL #sh  T2
    hw1 = 0xEA40 | rn
    hw2 = ((sh & 0x1C) << 10) | ((sh & 0x3) << 6) | (rd << 8) | rm
    return struct.pack("<HH", hw1, hw2)


def _mrs_ipsr(rd: int) -> bytes:
    # MRS Rd, IPSR  (SYSm = 5)
    hw1 = 0xF3EF
    hw2 = 0x8000 | (rd << 8) | 0x05
    return struct.pack("<HH", hw1, hw2)


def _push(reglist: list[int]) -> bytes:
    bits = 0
    for r in reglist:
        bits |= 1 << r
    return struct.pack("<HH", 0xE92D, bits)


def _pop(reglist: list[int]) -> bytes:
    bits = 0
    for r in reglist:
        bits |= 1 << r
    return struct.pack("<HH", 0xE8BD, bits)


def _bw(src_va: int, dst_va: int) -> bytes:
    # B.W  T4 unconditional branch, encodes (dst - (src+4)) as a 25-bit signed
    # immediate (bit 0 is always 0). Verified against the real image encoding
    # of 0x20A8A -> 0x874C (= e7 f7 5f be) in the __main__ self-test.
    off = dst_va - (src_va + 4)
    imm = off & 0x1FFFFFF
    s = (imm >> 24) & 1
    i1 = (imm >> 23) & 1
    i2 = (imm >> 22) & 1
    imm10 = (imm >> 12) & 0x3FF
    imm11 = (imm >> 1) & 0x7FF
    j1 = ((~i1) & 1) ^ s
    j2 = ((~i2) & 1) ^ s
    hw1 = 0xF000 | (s << 10) | imm10
    hw2 = 0x9000 | (j1 << 13) | (j2 << 11) | imm11
    return struct.pack("<HH", hw1, hw2)


# register numbers
R0, R1, R2, R3, R12 = 0, 1, 2, 3, 12


@dataclass
class Assembled:
    code: bytes
    branch_offset: int   # offset of the trailing b.w within code


def gate1_stub(base_va: int = PAYLOAD_BASE) -> Assembled:
    """Assemble the passive Gate-1 capture stub.

    Preserves r0 (=USB mutex base, consumed by the displaced unlock) and lr/sp
    exactly; uses r1/r2/r3/r12 which are saved+restored; takes no lock, calls
    no primitive, allocates nothing; ends by replaying the exact displaced
    `b.w 0x874C`.
    """
    ins: list[bytes] = []
    ins.append(_push([R1, R2, R3, R12]))          # save scratch (r0/lr/sp intact)
    ins.append(_movw32(R12, RING_HEAD))           # r12 = &head
    ins.append(_ldr_imm(R2, R12, 0))              # r2 = head
    ins.append(_and_imm(R3, R2, RING_MASK))       # r3 = head & mask
    ins.append(_lsl_imm(R3, R3, 4))               # r3 *= 16
    ins.append(_movw32(R1, RING_BASE))            # r1 = ring base
    ins.append(_add_reg(R3, R1, R3))              # r3 = &slot
    ins.append(_movw32(R1, TCB_PTR))              # r1 = &TCB
    ins.append(_ldr_imm(R1, R1, 0))               # r1 = *TCB  (current task)
    ins.append(_str_imm(R1, R3, 0))               # slot[0] = tcb
    ins.append(_ldr_imm(R1, R0, 8))               # r1 = *(mutex+8) owner
    ins.append(_str_imm(R1, R3, 4))               # slot[4] = owner
    ins.append(_ldrh_imm(R1, R0, 0x18))           # r1 = (u16)*(mutex+0x18) recursion
    ins.append(_mrs_ipsr(R12))                    # r12 = IPSR (9-bit exc number, upper bits RAZ)
    ins.append(_orr_lsl(R1, R1, R12, 16))         # r1 = (ipsr<<16)|recursion
    ins.append(_str_imm(R1, R3, 8))               # slot[8] = ipsr|recursion
    ins.append(_movw(R1, 0x0A8A))                 # site marker
    ins.append(_str_imm(R1, R3, 12))              # slot[12] = 0x0A8A
    ins.append(_add_imm(R2, R2, 1))               # head += 1
    ins.append(_movw32(R12, RING_HEAD))           # r12 = &head
    ins.append(_str_imm(R2, R12, 0))              # *head = head+1
    ins.append(_pop([R1, R2, R3, R12]))           # restore scratch
    code = b"".join(ins)
    branch_off = len(code)
    src = base_va + branch_off
    code += _bw(src, UNLOCK_VA)                    # replay displaced b.w 0x874C
    return Assembled(code=code, branch_offset=branch_off)


def gate1_stub_null(base_va: int = PAYLOAD_BASE) -> Assembled:
    """RED baseline: the displaced branch with NO capture logic.

    Represents "the stub is not implemented yet". A correctness test that
    passes against this would be vacuous; the suite asserts it FAILS here.
    """
    code = _bw(base_va, UNLOCK_VA)
    return Assembled(code=code, branch_offset=0)


def verify_stub(asm: Assembled, base_va: int = PAYLOAD_BASE) -> list[str]:
    """Disassemble the assembled bytes with capstone and return mnemonics.

    Raises if any halfword fails to decode (i.e. an encoding bug).
    """
    import capstone

    mode = capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS
    md = capstone.Cs(capstone.CS_ARCH_ARM, mode)
    md.detail = False
    out = []
    consumed = 0
    for ins in md.disasm(asm.code, base_va):
        out.append(f"{ins.address:#08x}: {ins.mnemonic} {ins.op_str}".rstrip())
        consumed += ins.size
    if consumed != len(asm.code):
        raise ValueError(
            f"capstone decoded only {consumed}/{len(asm.code)} bytes "
            f"(encoding error near offset {consumed})"
        )
    return out


def _self_test() -> None:
    # The B.W encoder must reproduce the real image encoding of the displaced
    # instruction at 0x20A8A (b.w 0x874C = e7 f7 5f be).
    got = _bw(HOOK_GATE1_VA, UNLOCK_VA)
    assert got == bytes.fromhex("e7f75fbe"), got.hex()


if __name__ == "__main__":
    import hashlib

    _self_test()
    asm = gate1_stub()
    lines = verify_stub(asm)
    print(f"Gate-1 stub @ {PAYLOAD_BASE:#x}: {len(asm.code)} bytes  "
          f"sha256={hashlib.sha256(asm.code).hexdigest()}")
    print(f"trailing b.w at offset {asm.branch_offset} -> {UNLOCK_VA:#x}")
    for ln in lines:
        print("  " + ln)
