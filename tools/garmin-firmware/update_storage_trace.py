#!/usr/bin/env python3
"""Reproduce the static GarminOS update-storage anchors for FR245 images.

This tool is deliberately narrow.  It reads an already extracted ``fw_all``
stream, checks the exact image hash, and emits the addresses and table values
used by the offline Ghidra trace.  It never opens a device or mutates its input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from update_region_map import find_tables, runtime_to_offset


PRESETS = {
    "3.10": {
        "sha256": "3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba",
        "ufs_source_va": 0x000D365C,
        "backend_initializer_va": 0x000D30F0,
        "backend_object_literal_va": 0x000D3110,
        "backend_object": 0x2000DF4C,
        "region_table": 0x000D3178,
        "vtable": 0x000D3150,
        "generic_erase": 0x000D29E8,
        "generic_finish": 0x000D2A10,
        "generic_write": 0x000D2B50,
        "ufs_erase": 0x000D2F8C,
        "ufs_finish": 0x000D306C,
        "ufs_write": 0x000D30B0,
        "blank_check": 0x000C646C,
        "erase_4k": 0x000C6504,
        "erase_64k": 0x000C64FC,
        "program": 0x000C6570,
        "qspi_base_literal_va": 0x000C6464,
        "status_offset_literal_vas": [0x000CBF88, 0x000CBF98],
        "record_writer": 0x000A0494,
        "orchestrator": 0x000CE3C8,
        "restart_request": 0x001AC074,
    },
    "13.70": {
        "sha256": "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6",
        "ufs_source_va": 0x00023208,
        "backend_initializer_va": 0x00022CB4,
        "backend_object_literal_va": 0x00022CC8,
        "backend_object": 0x1FFEEF84,
        "region_table": 0x00022D28,
        "vtable": 0x00022D00,
        "generic_erase": 0x00022578,
        "generic_finish": 0x000225A4,
        "generic_write": 0x000226E4,
        "ufs_erase": 0x00022B30,
        "ufs_finish": 0x00022C38,
        "ufs_write": 0x00022C78,
        "blank_check": 0x0001989C,
        "erase_4k": 0x0001992C,
        "erase_64k": 0x00019924,
        "program": 0x00019998,
        "qspi_base_literal_va": 0x00019BB0,
        "status_offset_literal_vas": [0x001CB508, 0x001CB518],
        "record_writer": 0x047623B4,
        "orchestrator": None,
        "restart_request": None,
    },
}

QSPI_PERIPHERAL_BASE = 0x400DA000
QSPI_AMBA_BASE = 0x68000000
STATUS_OFFSET = 0x4FD000


def u32_at_va(data: bytes, va: int) -> int:
    offset = runtime_to_offset(va, 4, len(data))
    if offset is None:
        raise ValueError(f"unmapped VA 0x{va:08x}")
    return struct.unpack_from("<I", data, offset)[0]


def bytes_at_va(data: bytes, va: int, length: int) -> bytes:
    offset = runtime_to_offset(va, length, len(data))
    if offset is None:
        raise ValueError(f"unmapped VA 0x{va:08x}")
    return data[offset : offset + length]


def hx(value: int | None) -> str | None:
    return None if value is None else f"0x{value:08x}"


def slice_digest(data: bytes, start: int, length: int) -> dict[str, object]:
    chunk = bytes_at_va(data, start, length)
    return {
        "address": hx(start),
        "length": length,
        "sha256": hashlib.sha256(chunk).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--version", required=True, choices=PRESETS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = args.image.read_bytes()
    preset = PRESETS[args.version]
    image_hash = hashlib.sha256(data).hexdigest()
    if image_hash != preset["sha256"]:
        raise SystemExit(
            f"unexpected {args.version} image SHA-256: {image_hash}; "
            f"expected {preset['sha256']}"
        )

    tables = [
        table for table in find_tables(data)
        if table["table_address"] == preset["region_table"]
    ]
    if len(tables) != 1:
        raise SystemExit("expected update-region table was not found exactly once")
    type_0e = next(row for row in tables[0]["rows"] if row["type"] == 0x0E)

    source = bytes_at_va(data, preset["ufs_source_va"], 96).split(b"\0", 1)[0]
    if b"HWM\\region\\hwm_rgn_ufs.c: 40" not in source:
        raise SystemExit("expected hwm_rgn_ufs.c source anchor is absent")

    object_words = [
        u32_at_va(data, preset["backend_object_literal_va"] + i * 4)
        for i in range(3)
    ]
    expected_words = [preset["backend_object"], preset["region_table"], preset["vtable"]]
    if object_words != expected_words:
        raise SystemExit(
            "backend initializer literals changed: "
            f"got {[hx(x) for x in object_words]}, expected {[hx(x) for x in expected_words]}"
        )

    qspi_base = u32_at_va(data, preset["qspi_base_literal_va"])
    if qspi_base != QSPI_PERIPHERAL_BASE:
        raise SystemExit(f"unexpected QuadSPI base literal: {hx(qspi_base)}")

    status_offsets = [u32_at_va(data, va) for va in preset["status_offset_literal_vas"]]
    if status_offsets != [STATUS_OFFSET, STATUS_OFFSET]:
        raise SystemExit(f"unexpected status offsets: {[hx(x) for x in status_offsets]}")

    logical_base = int(type_0e["logical_address"])
    capacity = int(type_0e["capacity"])
    report = {
        "image": str(args.image),
        "version": args.version,
        "bytes": len(data),
        "sha256": image_hash,
        "backend": {
            "source_anchor": source.decode("ascii"),
            "source_anchor_address": hx(preset["ufs_source_va"]),
            "initializer": hx(preset["backend_initializer_va"]),
            "object": hx(preset["backend_object"]),
            "region_table": hx(preset["region_table"]),
            "vtable": hx(preset["vtable"]),
            "methods": {
                "generic_erase": hx(preset["generic_erase"]),
                "generic_finish": hx(preset["generic_finish"]),
                "generic_write": hx(preset["generic_write"]),
                "ufs_erase": hx(preset["ufs_erase"]),
                "ufs_finish": hx(preset["ufs_finish"]),
                "ufs_write": hx(preset["ufs_write"]),
                "blank_check": hx(preset["blank_check"]),
                "erase_4k": hx(preset["erase_4k"]),
                "erase_64k": hx(preset["erase_64k"]),
                "program": hx(preset["program"]),
            },
        },
        "type_0e": {
            "logical_base": hx(logical_base),
            "capacity": hx(capacity),
            "exclusive_end": hx(logical_base + capacity),
            "status_offset": hx(STATUS_OFFSET),
            "status_address": hx(logical_base + STATUS_OFFSET),
            "status_offset_literal_addresses": [
                hx(va) for va in preset["status_offset_literal_vas"]
            ],
        },
        "qspi": {
            "peripheral_base": hx(qspi_base),
            "peripheral_base_literal_address": hx(preset["qspi_base_literal_va"]),
            "amba_base": hx(QSPI_AMBA_BASE),
            "erase_sector": hx(0x1000),
            "erase_block": hx(0x10000),
            "program_page_boundary": hx(0x100),
        },
        "update_flow": {
            "record_writer": hx(preset["record_writer"]),
            "orchestrator": hx(preset["orchestrator"]),
            "restart_request": hx(preset["restart_request"]),
        },
        "evidence_slices": {
            "backend_initializer": slice_digest(data, preset["backend_initializer_va"], 0x20),
            "ufs_erase": slice_digest(data, preset["ufs_erase"], 0x80),
            "ufs_write": slice_digest(data, preset["ufs_write"], 0x2E),
            "record_writer_prefix": slice_digest(data, preset["record_writer"], 0x100),
        },
        "limitations": [
            "Method meanings come from the cited offline Ghidra reports; this anchor tool does not decompile code.",
            "The image contains no resident Garmin loader, so loader authentication and final copy behavior remain unknown.",
            "The exact external flash chip part number is not established by these anchors.",
        ],
    }

    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
