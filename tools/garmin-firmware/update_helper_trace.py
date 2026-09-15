#!/usr/bin/env python3
"""Validate static fingerprints of the Forerunner 245 ``0x0505`` update helper.

The helper streams are firmware inputs.  This tool only reads those inputs and
writes an optional JSON report.  It deliberately identifies the helper's
placement and its region table; it does *not* make a claim about the omitted
resident loader's authentication policy or execute the helper.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


LOAD_ADDRESS = 0x1FFC0000
RESET_VECTOR_OFFSET = 0x04
RESET_TRAMPOLINE_OFFSET = 0x1F0
HEADER_MARKER_OFFSET = 0x210
HEADER_MARKERS = (0x389DB9F0, 0xC762460F)

EXPECTED = {
    "3.10": {
        "sha256": "80a075972f46fefe7df47052c81ce73fb2032f6d31eeb3d1bd5f73c79c1d568e",
        "length": 39424,
        "initial_sp": 0x20007B90,
        "reset": 0x1FFC01F1,
        "reset_entry": 0x1FFC3DCD,
        "region_table": 0x741C,
    },
    "13.70": {
        "sha256": "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46",
        "length": 37120,
        "initial_sp": 0x1FFEB080,
        "reset": 0x1FFC01F1,
        "reset_entry": 0x1FFC3231,
        "region_table": 0x6A28,
    },
}


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def parse_region_table(data: bytes, offset: int) -> list[dict[str, int | str]]:
    """Decode the static type -> <logical address, capacity> table."""
    result: list[dict[str, int | str]] = []
    while True:
        kind = u32(data, offset)
        descriptor = u32(data, offset + 4)
        offset += 8
        if kind == 0xFF:
            return result
        descriptor_offset = descriptor - LOAD_ADDRESS
        if not (0 <= descriptor_offset <= len(data) - 8):
            raise ValueError(f"unmapped descriptor 0x{descriptor:08x}")
        address = u32(data, descriptor_offset)
        capacity = u32(data, descriptor_offset + 4)
        result.append(
            {
                "type": kind,
                "type_hex": f"0x{kind:02x}",
                "descriptor": descriptor,
                "descriptor_hex": f"0x{descriptor:08x}",
                "logical_address": address,
                "logical_address_hex": f"0x{address:08x}",
                "capacity": capacity,
                "capacity_hex": f"0x{capacity:x}",
            }
        )


def trace(data: bytes, version: str) -> dict[str, object]:
    expected = EXPECTED[version]
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected["sha256"]:
        raise ValueError(
            f"unexpected {version} helper SHA-256 {digest}; refusing unpinned analysis"
        )
    if len(data) != expected["length"]:
        raise ValueError(f"unexpected {version} helper size {len(data)}")

    initial_sp = u32(data, 0)
    reset = u32(data, RESET_VECTOR_OFFSET)
    reset_entry = u32(data, 0x20C)
    markers = tuple(u32(data, HEADER_MARKER_OFFSET + index * 4) for index in range(2))
    if initial_sp != expected["initial_sp"] or reset != expected["reset"]:
        raise ValueError("helper vector does not match the pinned image")
    if reset_entry != expected["reset_entry"] or markers != HEADER_MARKERS:
        raise ValueError("helper reset/header anchors do not match the pinned image")

    regions = parse_region_table(data, expected["region_table"])
    by_type = {item["type"]: item for item in regions}
    for kind, address, capacity in ((0x05, 0x68103000, 0x15000), (0x0E, 0x68118000, 0x4FF000)):
        item = by_type.get(kind)
        if item is None or item["logical_address"] != address or item["capacity"] != capacity:
            raise ValueError(f"missing or changed type 0x{kind:02x} region")

    return {
        "tool": "update_helper_trace.py",
        "version": version,
        "input_sha256": digest,
        "input_bytes": len(data),
        "load_address": f"0x{LOAD_ADDRESS:08x}",
        "runtime_end_exclusive": f"0x{LOAD_ADDRESS + len(data):08x}",
        "vector": {
            "initial_sp": f"0x{initial_sp:08x}",
            "reset_handler": f"0x{reset:08x}",
            "reset_handler_file_offset": f"0x{(reset & ~1) - LOAD_ADDRESS:x}",
            "reset_entry_literal": f"0x{reset_entry:08x}",
        },
        "header_markers": [f"0x{marker:08x}" for marker in markers],
        "regions": regions,
        "observed_copy_stage": {
            "source_type": "0x0e",
            "destination_type": "0xaf",
            "evidence": (
                "The pinned 3.10 Ghidra export decompiles the helper's main loop "
                "as reads through the type-0x0e backend followed by writes through "
                "the type-0xaf backend."
            ),
        },
        "limitations": [
            "The helper image itself does not prove how the omitted resident loader authenticates or launches it.",
            "Type 0xaf is a compound destination backend; this static table alone does not prove its full physical layout.",
            "This offline evidence does not authorize copying an update package to the watch.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--version", required=True, choices=sorted(EXPECTED))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = trace(args.image.read_bytes(), args.version)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
