#!/usr/bin/env python3
"""Find reproducible driver leads in an extracted Forerunner 245 fw_all image.

The script is deliberately conservative: it reports printable strings, aligned
32-bit words in known K28F peripheral ranges, and Thumb PC-relative literal
loads that resolve to those words.  It does not assign function names or claim
that every matching word is executable code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC


STRING_PATTERN = re.compile(rb"[ -~]{5,}")
STRING_TERMS = re.compile(
    r"hwm_key|pmic_|charger|hwm_batt|VBatt|hwm_rtc|HWM_usb|"
    r"usb-manager|hwm_rgn_ufs|HWM_TFS|tfs_fat|backlight|display|framebuffer|lcd|dspl",
    re.IGNORECASE,
)

# Ranges are K28F address-space anchors.  A hit is only elevated to a code lead
# when a decoded PC-relative Thumb load resolves to the aligned literal slot.
PERIPHERAL_RANGES = {
    "DMA": (0x40008000, 0x40009000),
    "DMAMUX": (0x40021000, 0x40022000),
    "RTC": (0x4003D000, 0x4003E000),
    "PORT": (0x40049000, 0x4004E000),
    "GPIO": (0x400FF000, 0x40100000),
    "ADC": (0x4003B000, 0x4003C000),
    "I2C": (0x40066000, 0x40068000),
    "SPI": (0x4002C000, 0x4002F000),
    "SPI2": (0x400AC000, 0x400AD000),
    "USB_FS": (0x40072000, 0x40073000),
    "USB_HS_PHY": (0x400A1000, 0x400A3000),
    "SDHC": (0x400B1000, 0x400B2000),
    "FLEXIO0": (0x400DF000, 0x400E0000),
}


def _pc_literal_slot(instruction) -> int | None:
    for operand in instruction.operands:
        if operand.type == ARM_OP_MEM and operand.mem.base == ARM_REG_PC:
            return ((instruction.address + 4) & ~3) + operand.mem.disp
    return None


def display_framebuffer_clears(data: bytes, base: int, executable_size: int) -> list[dict]:
    """Find display-semaphore-adjacent 57,600-byte framebuffer clears.

    The exact Thumb ``mov.w r2, #0xe100`` encoding occurs elsewhere too, so a
    hit is retained only when it lies within 0x100 bytes of ``&dspl_smphr`` and
    is immediately followed by a direct call. The preceding instruction must
    be a PC-relative ``ldr r0`` whose literal resolves to the candidate buffer.
    """
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    disassembler.detail = True
    dspl_addresses = [
        base + match.start()
        for match in re.finditer(re.escape(b"&dspl_smphr"), data[:executable_size])
    ]
    results = []
    offset = 0
    encoding = b"\x4f\xf4\x61\x42"
    while True:
        offset = data.find(encoding, offset, executable_size)
        if offset < 0:
            break
        address = base + offset
        offset += len(encoding)
        if not any(abs(address - string_address) <= 0x100 for string_address in dspl_addresses):
            continue
        load = next(
            disassembler.disasm(data[offset - len(encoding) - 4 : offset - len(encoding)], address - 4, count=1),
            None,
        )
        call = next(disassembler.disasm(data[offset : offset + 4], address + 4, count=1), None)
        if (
            load is None
            or load.mnemonic != "ldr"
            or not load.op_str.startswith("r0,")
            or call is None
            or call.mnemonic != "bl"
        ):
            continue
        slot = _pc_literal_slot(load)
        if slot is None or not base <= slot <= base + len(data) - 4:
            continue
        buffer_address = struct.unpack_from("<I", data, slot - base)[0]
        results.append(
            {
                "byte_count_load": address,
                "byte_count": 0xE100,
                "buffer_load": load.address,
                "buffer_literal_slot": slot,
                "buffer_address": buffer_address,
                "clear_call_target_text": call.op_str,
                "near_display_semaphore_strings": [
                    value for value in dspl_addresses if abs(address - value) <= 0x100
                ],
            }
        )
    return results


def flexio_display_objects(data: bytes, base: int, executable_size: int) -> list[dict]:
    """Find the cross-version FLEXIO0 base/IRQ object used by display setup."""
    pattern = struct.pack("<II", 0x400DF000, 0x46)
    results = []
    offset = 0
    while True:
        offset = data.find(pattern, offset, executable_size)
        if offset < 0:
            break
        results.append(
            {
                "address": base + offset,
                "peripheral_base": 0x400DF000,
                "irq_number": 0x46,
            }
        )
        offset += 1
    return results


def key_pin_tables(data: bytes, base: int, executable_size: int) -> list[dict]:
    """Find five-row pin/config tables used by the observed key-manager code.

    Each row is two 32-bit words. The second word is the stable key input mode
    value 5. The encoded pin's low five bits select a pin and bits 5..7 select
    GPIO A..E; higher bits are retained as flags rather than interpreted.
    """
    results = []
    for offset in range(0, executable_size - 40 + 1, 4):
        rows = [struct.unpack_from("<II", data, offset + index * 8) for index in range(5)]
        if any(mode != 5 for _, mode in rows):
            continue
        decoded = []
        valid = True
        for encoded, mode in rows:
            port_index = (encoded >> 5) & 0x7
            pin = encoded & 0x1F
            if port_index > 4 or encoded > 0x1FF:
                valid = False
                break
            decoded.append(
                {
                    "encoded": encoded,
                    "mode": mode,
                    "port_index": port_index,
                    "port": chr(ord("A") + port_index),
                    "pin": pin,
                    "flags_above_bit_7": encoded & ~0xFF,
                }
            )
        if valid and len({(row["port"], row["pin"]) for row in decoded}) == 5:
            results.append({"address": base + offset, "rows": decoded})
    return results


def backlight_register_writers(data: bytes, base: int, executable_size: int) -> list[dict]:
    """Find the cross-version PMIC-register sequence used by backlight code.

    This signature deliberately requires writes to both register-number
    constants, in order, through the same direct call target. It reports the
    sequence without assigning a chip or register name.
    """
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    results = []
    seen_first_loads = set()
    # Thumb-1 ``movs r0, #0x2e`` encodes as bytes 2e 20. Searching that exact
    # two-byte prefix first avoids attempting a Capstone decode at every halfword.
    offset = 0
    while True:
        offset = data.find(b"\x2e\x20", offset, executable_size - 0x20)
        if offset < 0:
            break
        if offset & 1:
            offset += 1
            continue
        match_offset = offset
        offset += 2
        address = base + match_offset
        instructions = list(
            disassembler.disasm(data[match_offset : match_offset + 0x20], address)
        )
        if len(instructions) < 6:
            continue
        for first_index, instruction in enumerate(instructions):
            if instruction.mnemonic != "movs" or instruction.op_str != "r0, #0x2e":
                continue
            if first_index + 1 >= len(instructions):
                continue
            first_call = instructions[first_index + 1]
            if first_call.mnemonic != "bl":
                continue
            for second_index in range(first_index + 2, min(first_index + 8, len(instructions))):
                second = instructions[second_index]
                if second.mnemonic != "movs" or second.op_str != "r0, #0x2f":
                    continue
                if second_index + 1 >= len(instructions):
                    continue
                second_call = instructions[second_index + 1]
                if second_call.mnemonic == "bl" and second_call.op_str == first_call.op_str:
                    if instruction.address in seen_first_loads:
                        break
                    seen_first_loads.add(instruction.address)
                    results.append(
                        {
                            "first_register_load": instruction.address,
                            "second_register_load": second.address,
                            "shared_call_target_text": first_call.op_str,
                        }
                    )
                break
            break
    return results


def word_references(data: bytes, value: int, base: int) -> list[int]:
    needle = struct.pack("<I", value)
    refs: list[int] = []
    position = 0
    while True:
        position = data.find(needle, position)
        if position < 0:
            return refs
        refs.append(base + position)
        position += 1


def literal_loads(
    data: bytes, slot_address: int, base: int, executable_end: int, window: int = 0x1000
) -> list[dict]:
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    disassembler.detail = True
    results: list[dict] = []
    start = max(base, slot_address - window) & ~1
    for address in range(start, min(slot_address, executable_end), 2):
        offset = address - base
        instruction = next(disassembler.disasm(data[offset : offset + 4], address, count=1), None)
        if instruction is None or not instruction.mnemonic.startswith("ldr"):
            continue
        for operand in instruction.operands:
            if operand.type != ARM_OP_MEM or operand.mem.base != ARM_REG_PC:
                continue
            resolved = ((address + 4) & ~3) + operand.mem.disp
            if resolved == slot_address:
                results.append(
                    {
                        "address": address,
                        "mnemonic": instruction.mnemonic,
                        "operands": instruction.op_str,
                    }
                )
    return results


def inspect(path: Path, base: int, executable_end: int) -> dict:
    data = path.read_bytes()
    if executable_end <= base:
        raise ValueError("executable end must be above the load base")
    executable_size = min(len(data), executable_end - base)
    strings = []
    for match in STRING_PATTERN.finditer(data):
        text = match.group().decode("ascii")
        if not STRING_TERMS.search(text):
            continue
        address = base + match.start()
        strings.append(
            {
                "address": address,
                "text": text,
                "direct_pointer_slots": word_references(data, address, base),
                "inside_executable_window": address < executable_end,
            }
        )

    clusters = {}
    for name, (low, high) in PERIPHERAL_RANGES.items():
        literals = []
        for offset in range(0, executable_size - 3, 4):
            value = struct.unpack_from("<I", data, offset)[0]
            if not low <= value < high:
                continue
            slot = base + offset
            loads = literal_loads(data, slot, base, executable_end)
            if loads:
                literals.append({"slot": slot, "value": value, "thumb_literal_loads": loads})
        clusters[name] = {
            "range_start": low,
            "range_end_exclusive": high,
            "literals_with_code_loads": literals,
        }

    return {
        "input": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "load_base": base,
        "executable_end_exclusive": executable_end,
        "limitations": [
            "Printable-string and aligned-word matches can occur in data by chance.",
            "A decoded literal load is an instruction-level lead, not a recovered function name.",
            "Peripheral ranges identify K28F blocks; they do not identify board wiring.",
            "The default executable window ends at the K28F 2 MiB internal-flash ceiling; later stream bytes are still searched for strings but not decoded as code.",
        ],
        "strings": strings,
        "peripheral_clusters": clusters,
        "candidate_key_pin_tables": key_pin_tables(data, base, executable_size),
        "candidate_backlight_register_writers": backlight_register_writers(
            data, base, executable_size
        ),
        "candidate_display_framebuffer_clears": display_framebuffer_clears(
            data, base, executable_size
        ),
        "candidate_flexio_display_objects": flexio_display_objects(
            data, base, executable_size
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x3000)
    parser.add_argument(
        "--executable-end",
        type=lambda value: int(value, 0),
        default=0x200000,
        help="exclusive virtual end of the region scanned as executable code",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.image, args.base, args.executable_end)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
