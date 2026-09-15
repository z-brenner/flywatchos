#!/usr/bin/env python3
"""Model and offline-oracle checks for the FR245 display row converter.

The model is limited to the converter's observed caller contract: a 240 by 240
one-byte source image and non-negative, in-bounds rectangles.  It does not
model FLEXIO, DMA, panel commands, or the meaning of an eight-bit pixel.

With ``--verify``, the script runs preserved converter instructions in Unicorn.
Firmware inputs are read into emulator memory and are never opened for writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


WIDTH = 240
HEIGHT = 240
SOURCE_SIZE = WIDTH * HEIGHT
ROW_STRIDE = 244
STAGING_SIZE = ROW_STRIDE * HEIGHT
PLANE_STRIDE = 122


@dataclass(frozen=True)
class FirmwareConverter:
    name: str
    path: Path
    entry: int
    gate_ptrs: tuple[int, int, int]
    reverse_ptr: int


VERSIONS = {
    "3.10": FirmwareConverter(
        "3.10",
        Path("artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin"),
        0x000BF54C,
        (0x001C0A03, 0x001C0A02, 0x001C0A01),
        0x2001005D,
    ),
    "13.70": FirmwareConverter(
        "13.70",
        Path(
            "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/"
            "stream_01_fw_all_bin.bin"
        ),
        0x0000E8FC,
        (0x00024FD8, 0x00024FD8, 0x00024FD8),
        0x1FFF2203,
    ),
}


def _pair_primary(first: int, second: int) -> int:
    """Apply the firmware's 0xea mask to two adjacent pixels."""
    return ((first & 0xEA) >> 1) | (second & 0xEA)


def _pair_secondary(first: int, second: int) -> int:
    """Apply the firmware's 0x15 mask to two adjacent pixels."""
    return (first & 0x15) | ((second & 0x15) << 1)


def _write_source_word(
    source: bytes,
    staging: bytearray,
    source_row: int,
    source_word: int,
    output_row: int,
    output_byte: int,
    reverse_pixels: bool,
) -> None:
    source_offset = source_row * WIDTH + source_word * 4
    pixels = source[source_offset : source_offset + 4]
    if reverse_pixels:
        pixels = pixels[::-1]
    staging_offset = output_row * ROW_STRIDE + output_byte
    staging[staging_offset] = _pair_primary(pixels[0], pixels[1])
    staging[staging_offset + 1] = _pair_primary(pixels[2], pixels[3])
    staging[staging_offset + PLANE_STRIDE] = _pair_secondary(pixels[0], pixels[1])
    staging[staging_offset + PLANE_STRIDE + 1] = _pair_secondary(pixels[2], pixels[3])


def _dispatch(
    y: int,
    rows: int,
    x: int,
    columns: int,
    gates: tuple[int, int, int],
) -> tuple[str, int, int, int, int]:
    """Transcribe the entry dispatch shared by the two firmware versions."""
    gate0, gate1, gate2 = (bool(value) for value in gates)
    if not gate0:
        if gate1:
            return "wide", 0, HEIGHT, x, columns
        if gate2 or columns >= 180:
            return "wide", y, rows, x, columns
        return "partial", y, rows, x, columns

    # The other layout always uses the partial-body addressing convention.
    if gate1:
        return "partial", 0, HEIGHT, 0, WIDTH
    if rows == HEIGHT and columns >= 180:
        return "partial", 0, HEIGHT, 0, WIDTH
    if gate2 or columns >= 180:
        return "partial", y, rows, 0, WIDTH
    return "partial", y, rows, x, columns


def convert(
    source: bytes,
    initial_staging: bytes,
    y: int,
    rows: int,
    x: int,
    columns: int,
    gates: tuple[int, int, int] = (0, 0, 0),
    reverse: bool = False,
) -> bytes:
    """Transcribe the observed converter behavior within its caller contract."""
    if len(source) != SOURCE_SIZE:
        raise ValueError(f"source must contain exactly {SOURCE_SIZE} bytes")
    if len(initial_staging) != STAGING_SIZE:
        raise ValueError(f"staging must contain exactly {STAGING_SIZE} bytes")
    if not (0 <= y <= HEIGHT and 0 <= rows and y + rows <= HEIGHT):
        raise ValueError("row rectangle is outside the 240-row source")
    if not (0 <= x <= WIDTH and 0 <= columns and x + columns <= WIDTH):
        raise ValueError("column rectangle is outside the 240-column source")
    if any(value not in (0, 1) for value in gates):
        raise ValueError("gates must contain three zero/one values")

    family, y, rows, x, columns = _dispatch(y, rows, x, columns, gates)
    staging = bytearray(initial_staging)

    if family == "wide":
        # This body always converts all 60 source words in each selected row.
        for source_row in range(y, y + rows):
            output_row = HEIGHT - 1 - source_row if reverse else source_row
            row_base = output_row * ROW_STRIDE
            if reverse:
                staging[row_base] = 0
                staging[row_base + 121] = 0
                staging[row_base + 122] = 0
                staging[row_base + 243] = 0
                for source_word in range(60):
                    output_byte = 1 + 2 * (59 - source_word)
                    _write_source_word(
                        source,
                        staging,
                        source_row,
                        source_word,
                        output_row,
                        output_byte,
                        True,
                    )
            else:
                staging[row_base] = 0
                staging[row_base + 121] = 0
                staging[row_base + 122] = 0
                staging[row_base + 243] = 0
                for source_word in range(60):
                    _write_source_word(
                        source,
                        staging,
                        source_row,
                        source_word,
                        output_row,
                        1 + 2 * source_word,
                        False,
                    )
        return bytes(staging)

    first_word = x // 4
    end_word = (x + columns + 3) // 4
    for source_row in range(y, y + rows):
        output_row = HEIGHT - 1 - source_row if reverse else source_row
        for source_word in range(first_word, end_word):
            output_byte = (
                1 + 2 * (59 - source_word) if reverse else 1 + 2 * source_word
            )
            _write_source_word(
                source,
                staging,
                source_row,
                source_word,
                output_row,
                output_byte,
                reverse,
            )
    return bytes(staging)


def emulate(
    firmware: FirmwareConverter,
    source: bytes,
    initial_staging: bytes,
    y: int,
    rows: int,
    x: int,
    columns: int,
    gates: tuple[int, int, int],
    reverse: bool,
) -> bytes:
    """Run the original Thumb converter bytes in an isolated Unicorn VM."""
    try:
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_MCLASS, UC_MODE_THUMB
        from unicorn.arm_const import (
            UC_ARM_REG_LR,
            UC_ARM_REG_PC,
            UC_ARM_REG_R0,
            UC_ARM_REG_R1,
            UC_ARM_REG_R2,
            UC_ARM_REG_R3,
            UC_ARM_REG_SP,
        )
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("--verify requires: python -m pip install unicorn==2.1.4") from exc

    if len(set(firmware.gate_ptrs)) != len(set(zip(firmware.gate_ptrs, gates))):
        raise ValueError(
            f"{firmware.name} aliases gate bytes; conflicting requested values are impossible"
        )

    image = firmware.path.read_bytes()
    vm = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    vm.mem_map(0x00000000, 0x00800000)
    vm.mem_write(0x00003000, image)
    vm.mem_map(0x1FFF0000, 0x00050000)
    vm.mem_map(0x21000000, 0x00020000)

    for pointer, value in zip(firmware.gate_ptrs, gates):
        vm.mem_write(pointer, bytes((value,)))
    vm.mem_write(firmware.reverse_ptr, bytes((int(reverse),)))

    source_address = 0x21000000
    staging_address = 0x21010000
    stack_pointer = 0x20030000
    return_address = 0x00001001
    vm.mem_write(source_address, source)
    vm.mem_write(staging_address, initial_staging)
    vm.mem_write(stack_pointer, struct.pack("<II", x, columns))
    vm.reg_write(UC_ARM_REG_R0, source_address)
    vm.reg_write(UC_ARM_REG_R1, staging_address)
    vm.reg_write(UC_ARM_REG_R2, y)
    vm.reg_write(UC_ARM_REG_R3, rows)
    vm.reg_write(UC_ARM_REG_SP, stack_pointer)
    vm.reg_write(UC_ARM_REG_LR, return_address)
    vm.emu_start(firmware.entry | 1, return_address & ~1, count=1_000_000)
    if vm.reg_read(UC_ARM_REG_PC) != (return_address & ~1):
        raise RuntimeError(f"{firmware.name} converter did not return before instruction limit")
    return bytes(vm.mem_read(staging_address, STAGING_SIZE))


def _vectors() -> Iterable[tuple[str, bytes]]:
    yield "zero", bytes(SOURCE_SIZE)
    yield "ramp", bytes(range(256)) * (SOURCE_SIZE // 256)
    state = 0x2451370
    randomish = bytearray()
    for _ in range(SOURCE_SIZE):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        randomish.append(state >> 24)
    yield "lcg", bytes(randomish)


def verify(root: Path) -> dict[str, object]:
    cases = [
        ("full", 0, 240, 0, 240),
        ("aligned-partial", 8, 16, 16, 24),
        ("rounded-word", 5, 3, 3, 5),
        ("wide-threshold-low", 10, 4, 0, 179),
        ("wide-threshold-high", 10, 4, 0, 180),
    ]
    versions = {
        key: FirmwareConverter(
            item.name, root / item.path, item.entry, item.gate_ptrs, item.reverse_ptr
        )
        for key, item in VERSIONS.items()
    }
    initial = bytes((0xCC,)) * STAGING_SIZE
    comparisons = 0
    cross_version_comparisons = 0
    case_hashes: dict[str, str] = {}

    for vector_name, source in _vectors():
        for case_name, y, rows, x, columns in cases:
            for reverse in (False, True):
                # These are the only gate states representable by both images:
                # 13.70 deliberately aliases its three gate pointers.
                cross_outputs = []
                for gates in ((0, 0, 0), (1, 1, 1)):
                    expected = convert(
                        source, initial, y, rows, x, columns, gates, reverse
                    )
                    outputs = []
                    for firmware in versions.values():
                        observed = emulate(
                            firmware,
                            source,
                            initial,
                            y,
                            rows,
                            x,
                            columns,
                            gates,
                            reverse,
                        )
                        if observed != expected:
                            mismatch = next(
                                index
                                for index, pair in enumerate(zip(observed, expected))
                                if pair[0] != pair[1]
                            )
                            raise AssertionError(
                                f"{firmware.name} {vector_name}/{case_name} "
                                f"gates={gates} reverse={reverse}: mismatch at {mismatch:#x}"
                            )
                        comparisons += 1
                        outputs.append(observed)
                    if outputs[0] != outputs[1]:
                        raise AssertionError(
                            f"cross-version mismatch for {vector_name}/{case_name}, "
                            f"gates={gates}, reverse={reverse}"
                        )
                    cross_version_comparisons += 1
                    cross_outputs.append(outputs[0])
                digest_input = b"".join(cross_outputs)
                case_hashes[
                    f"{vector_name}/{case_name}/reverse={int(reverse)}"
                ] = hashlib.sha256(digest_input).hexdigest()

    # 3.10 stores its gates separately, so exercise the remaining six states
    # across every rectangle shape (the shared loop already covers 000/111).
    firmware = versions["3.10"]
    source = dict(_vectors())["lcg"]
    for gate_bits in range(1, 7):
        gates = tuple((gate_bits >> bit) & 1 for bit in range(3))
        for _, y, rows, x, columns in cases:
            for reverse in (False, True):
                expected = convert(
                    source, initial, y, rows, x, columns, gates, reverse
                )
                observed = emulate(
                    firmware,
                    source,
                    initial,
                    y,
                    rows,
                    x,
                    columns,
                    gates,
                    reverse,
                )
                if observed != expected:
                    raise AssertionError(
                        f"3.10 gate sweep mismatch gates={gates}, reverse={reverse}"
                    )
                comparisons += 1

    # Exhaust every ordered input-pixel pair through the full-row path.  One
    # frame holds 28,800 pairs, so three emulator runs cover all 65,536 pairs.
    pair_index = 0
    while pair_index < 65536:
        exhaustive = bytearray(SOURCE_SIZE)
        for offset in range(0, SOURCE_SIZE, 2):
            if pair_index >= 65536:
                break
            exhaustive[offset] = pair_index >> 8
            exhaustive[offset + 1] = pair_index & 0xFF
            pair_index += 1
        expected = convert(
            bytes(exhaustive), initial, 0, HEIGHT, 0, WIDTH, (0, 0, 0), False
        )
        outputs = []
        for version in versions.values():
            observed = emulate(
                version,
                bytes(exhaustive),
                initial,
                0,
                HEIGHT,
                0,
                WIDTH,
                (0, 0, 0),
                False,
            )
            if observed != expected:
                raise AssertionError(f"{version.name} exhaustive pair mismatch")
            comparisons += 1
            outputs.append(observed)
        if outputs[0] != outputs[1]:
            raise AssertionError("cross-version exhaustive pair mismatch")
        cross_version_comparisons += 1

    return {
        "status": "pass",
        "model_vs_emulator_comparisons": comparisons,
        "cross_version_comparisons": cross_version_comparisons,
        "ordered_pixel_pairs_checked": 65536,
        "firmware_sha256": {
            key: hashlib.sha256(item.path.read_bytes()).hexdigest()
            for key, item in versions.items()
        },
        "case_sha256": case_hashes,
        "limitations": [
            "Only non-negative in-bounds rectangles from the observed caller contract are modeled.",
            "The checks validate byte conversion and staging offsets, not panel color semantics or wire protocol.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="compare the host model with both preserved Thumb routines",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    if not args.verify:
        parser.error("select --verify")
    report = verify(args.root.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
