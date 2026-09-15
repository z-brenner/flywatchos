#!/usr/bin/env python3
"""Locate GarminOS update-type tables and decode their logical regions."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

INTERNAL_BASE = 0x3000
INTERNAL_LENGTH = 0x1FD000
EXTERNAL_FILE_OFFSET = 0x1FD000
EXTERNAL_BASE = 0x04600000


def runtime_to_offset(address: int, size: int, image_length: int) -> int | None:
    if INTERNAL_BASE <= address < INTERNAL_BASE + INTERNAL_LENGTH:
        offset = address - INTERNAL_BASE
    elif address >= EXTERNAL_BASE:
        offset = EXTERNAL_FILE_OFFSET + address - EXTERNAL_BASE
    else:
        return None
    if offset < 0 or offset + size > image_length:
        return None
    return offset


def offset_to_runtime(offset: int) -> int:
    if offset < EXTERNAL_FILE_OFFSET:
        return INTERNAL_BASE + offset
    return EXTERNAL_BASE + offset - EXTERNAL_FILE_OFFSET


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def find_tables(data: bytes) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for start in range(0, len(data) - 24, 4):
        rows: list[dict[str, int]] = []
        cursor = start
        for _ in range(32):
            if cursor + 8 > len(data):
                break
            update_type = u32(data, cursor)
            pointer = u32(data, cursor + 4)
            if update_type == 0xFF:
                ids = {row["type"] for row in rows}
                if len(rows) >= 3 and {0x05, 0x0E}.issubset(ids):
                    matches.append({"table_address": offset_to_runtime(start), "rows": rows})
                break
            if update_type > 0xFE:
                break
            descriptor_offset = runtime_to_offset(pointer, 8, len(data))
            if descriptor_offset is None:
                break
            logical_address = u32(data, descriptor_offset)
            capacity = u32(data, descriptor_offset + 4)
            if not (0x68000000 <= logical_address < 0x69000000 and capacity > 0):
                break
            rows.append(
                {
                    "type": update_type,
                    "type_hex": f"0x{update_type:02x}",
                    "descriptor_address": pointer,
                    "descriptor_address_hex": f"0x{pointer:08x}",
                    "logical_address": logical_address,
                    "logical_address_hex": f"0x{logical_address:08x}",
                    "capacity": capacity,
                    "capacity_hex": f"0x{capacity:x}",
                }
            )
            cursor += 8
    # The scanner visits every aligned row; retain maximal tables rather than
    # also returning each suffix that happens to contain both requested IDs.
    maximal: list[dict[str, object]] = []
    for candidate in matches:
        start = int(candidate["table_address"])
        if any(
            int(other["table_address"]) < start
            < int(other["table_address"]) + 8 * len(other["rows"])
            for other in matches
        ):
            continue
        maximal.append(candidate)
    return maximal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = args.image.read_bytes()
    result = {
        "image": str(args.image),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mapping": {
            "internal_base": INTERNAL_BASE,
            "internal_length": INTERNAL_LENGTH,
            "external_file_offset": EXTERNAL_FILE_OFFSET,
            "external_base": EXTERNAL_BASE,
        },
        "tables": find_tables(data),
        "limitations": [
            "Logical 0x68xxxxxx addresses do not identify the physical storage medium.",
            "A region table does not reveal loader authentication or rollback behavior.",
        ],
    }
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if not result["tables"]:
        raise SystemExit("no update region table containing types 0x05 and 0x0e")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
