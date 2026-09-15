#!/usr/bin/env python3
"""Decode the FR245 SRAM updater's compound destination type 0xaf.

This is an offline, read-only structural decoder for two SHA-256-pinned type
0x0505 helper images.  It validates the backend objects, type tables, child
order, descriptors, and vtable pointers used by the focused Ghidra exports.
It neither executes firmware nor accesses a device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


LOAD_ADDRESS = 0x1FFC0000

EXPECTED = {
    "3.10": {
        "sha256": "80a075972f46fefe7df47052c81ce73fb2032f6d31eeb3d1bd5f73c79c1d568e",
        "length": 39424,
        "internal_object": 0x7298,
        "compound_init": 0x7300,
        "compound_vtable": 0x7364,
        "compound_dispatch": 0x738C,
        "compound_context": 0x20005B90,
        "compound_sizes": 0x20005BA0,
        "child_types": 0x9980,
        "ufs_vtable": 0x73F4,
        "ufs_dispatch": 0x741C,
        "compound_ops": [
            0x1FFC9571, 0x1FFC94D5, 0x1FFC9833, 0x1FFC961B,
            0x1FFC94C7, 0x1FFC9633, 0x1FFC983F, 0x1FFC9843,
            0x1FFC9847, 0x1FFC94F7,
        ],
        "internal_ops": [
            0x1FFC93F9, 0x1FFC984B, 0x1FFC9833, 0x1FFC9499,
            0x1FFC9391, 0x1FFC9433, 0x1FFC93D1, 0x1FFC93A5,
            0x1FFC9489, 0x1FFC939D,
        ],
        "ufs_ops": [
            0x1FFC96E3, 0x1FFC97B3, 0x1FFC964D, 0x1FFC97C5,
            0x1FFC9673, 0x1FFC97F3, 0x1FFC96A9, 0x1FFC9681,
            0x1FFC9821, 0x1FFC966B,
        ],
        "semantic_functions": {
            "compound_initialize": 0x1FFC9534,
            "compound_erase": 0x1FFC9570,
            "compound_read_split": 0x1FFC961A,
            "compound_write_split": 0x1FFC9632,
            "internal_erase": 0x1FFC93F8,
            "internal_write": 0x1FFC9432,
            "internal_sector_erase": 0x1FFC93D0,
            "internal_program_low_level": 0x1FFC4ED0,
            "external_erase": 0x1FFC96E2,
            "external_write": 0x1FFC97F2,
            "copy_length": 0x1FFC64EC,
            "update_main": 0x1FFC6700,
        },
    },
    "13.70": {
        "sha256": "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46",
        "length": 37120,
        "internal_object": 0x68AC,
        "compound_init": 0x6914,
        "compound_vtable": 0x6978,
        "compound_dispatch": 0x69A0,
        "compound_context": 0x1FFEABE0,
        "compound_sizes": 0x1FFEABF0,
        "child_types": 0x9078,
        "ufs_vtable": 0x6A00,
        "ufs_dispatch": 0x6A28,
        "compound_ops": [
            0x1FFC8C65, 0x1FFC8BCB, 0x1FFC8F0D, 0x1FFC8D03,
            0x1FFC8BBD, 0x1FFC8D1B, 0x1FFC8F19, 0x1FFC8F1D,
            0x1FFC8F21, 0x1FFC8BED,
        ],
        "internal_ops": [
            0x1FFC8AF3, 0x1FFC8F25, 0x1FFC8F0D, 0x1FFC8B8F,
            0x1FFC8A87, 0x1FFC8B2D, 0x1FFC8ACB, 0x1FFC8A9B,
            0x1FFC8B7F, 0x1FFC8A93,
        ],
        "ufs_ops": [
            0x1FFC8DCD, 0x1FFC8E8D, 0x1FFC8D35, 0x1FFC8E9F,
            0x1FFC8D5B, 0x1FFC8ECD, 0x1FFC8D91, 0x1FFC8D69,
            0x1FFC8EFB, 0x1FFC8D53,
        ],
        "semantic_functions": {
            "compound_initialize": 0x1FFC8C2A,
            "compound_erase": 0x1FFC8C64,
            "compound_read_split": 0x1FFC8D02,
            "compound_write_split": 0x1FFC8D1A,
            "internal_erase": 0x1FFC8AF2,
            "internal_write": 0x1FFC8B2C,
            "internal_sector_erase": 0x1FFC8ACA,
            "external_erase": 0x1FFC8DCC,
            "external_write": 0x1FFC8ECC,
        },
    },
}


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def runtime(offset: int) -> int:
    return LOAD_ADDRESS + offset


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def parse_type_table(data: bytes, offset: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    while True:
        kind = u32(data, offset)
        descriptor = u32(data, offset + 4)
        offset += 8
        if kind == 0xFF:
            return result
        result.append((kind, descriptor))


def descriptor(data: bytes, address: int) -> tuple[int, int]:
    offset = address - LOAD_ADDRESS
    if not 0 <= offset <= len(data) - 8:
        raise ValueError(f"descriptor {hex32(address)} is outside helper image")
    return u32(data, offset), u32(data, offset + 4)


def require(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def trace(data: bytes, version: str) -> dict[str, object]:
    expected = EXPECTED[version]
    digest = hashlib.sha256(data).hexdigest()
    require(digest, expected["sha256"], "SHA-256")
    require(len(data), expected["length"], "file length")

    # Internal-flash backend object: <registry id, type table, vtable, context>.
    io = expected["internal_object"]
    internal_id, internal_table_ptr, internal_vtable_ptr, internal_context_ptr = (
        u32(data, io + index * 4) for index in range(4)
    )
    require(internal_id, 1, "internal backend registry id")
    require(internal_vtable_ptr, runtime(io + 0x40), "internal vtable pointer")
    require(internal_context_ptr, runtime(io + 0x10), "internal context pointer")
    require(
        [u32(data, io + 0x40 + index * 4) for index in range(10)],
        expected["internal_ops"],
        "internal backend vtable",
    )
    flash_base, flash_capacity = descriptor(data, internal_context_ptr)
    require((flash_base, flash_capacity), (0, 0x200000), "internal flash geometry")

    internal_table = parse_type_table(data, internal_table_ptr - LOAD_ADDRESS)
    internal_regions: dict[int, tuple[int, int, int]] = {}
    for kind, descriptor_ptr in internal_table:
        base, capacity = descriptor(data, descriptor_ptr)
        internal_regions[kind] = (descriptor_ptr, base, capacity)
    require(
        {kind: values[1:] for kind, values in internal_regions.items()},
        {0x2B: (0x00000000, 0x3000), 0xAB: (0x00003000, 0x1FD000)},
        "internal type map",
    )

    # UFS / QuadSPI logical-region backend.
    require(
        [u32(data, expected["ufs_vtable"] + index * 4) for index in range(10)],
        expected["ufs_ops"],
        "external backend vtable",
    )
    ufs_table = parse_type_table(data, expected["ufs_dispatch"])
    ufs_regions: dict[int, tuple[int, int, int]] = {}
    for kind, descriptor_ptr in ufs_table:
        base, capacity = descriptor(data, descriptor_ptr)
        ufs_regions[kind] = (descriptor_ptr, base, capacity)
    require(ufs_regions[0xAC][1:], (0x68617000, 0x300000), "type 0xac region")
    require(ufs_regions[0x0E][1:], (0x68118000, 0x4FF000), "type 0x0e region")

    # Compound object and dispatch entry.  The context itself is built in RAM;
    # its immutable child type bytes and vtable live in this helper image.
    require(data[expected["child_types"] : expected["child_types"] + 2], b"\xab\xac", "0xaf child order")
    compound_table = parse_type_table(data, expected["compound_dispatch"])
    compound_map = dict(compound_table)
    require(compound_map.get(0xAF), expected["compound_context"], "0xaf context")
    require(
        [u32(data, expected["compound_vtable"] + index * 4) for index in range(10)],
        expected["compound_ops"],
        "compound backend vtable",
    )

    child_specs = []
    logical_offset = 0
    for kind in (0xAB, 0xAC):
        if kind in internal_regions:
            descriptor_ptr, physical_base, capacity = internal_regions[kind]
            backend = "internal_flash"
        else:
            descriptor_ptr, physical_base, capacity = ufs_regions[kind]
            backend = "external_ufs_quadspi"
        child_specs.append(
            {
                "order": len(child_specs),
                "type": f"0x{kind:02x}",
                "backend": backend,
                "descriptor": hex32(descriptor_ptr),
                "compound_offset_start": hex32(logical_offset),
                "compound_offset_end_exclusive": hex32(logical_offset + capacity),
                "backend_address_start": hex32(physical_base),
                "backend_address_end_exclusive": hex32(physical_base + capacity),
                "capacity": capacity,
                "capacity_hex": f"0x{capacity:x}",
            }
        )
        logical_offset += capacity
    require(logical_offset, 0x4FD000, "0xaf total capacity")

    internal_sectors = internal_regions[0xAB][2] // 0x1000
    external_start = ufs_regions[0xAC][1]
    external_end = external_start + ufs_regions[0xAC][2]
    leading_4k = ((-external_start) & 0xFFFF) // 0x1000
    middle_start = external_start + leading_4k * 0x1000
    middle_64k = (external_end - middle_start) // 0x10000
    trailing_4k = (external_end - (middle_start + middle_64k * 0x10000)) // 0x1000

    semantic_functions = {
        name: hex32(address) for name, address in expected["semantic_functions"].items()
    }
    return {
        "tool": "update_af_trace.py",
        "version": version,
        "input_sha256": digest,
        "input_bytes": len(data),
        "helper_load_address": hex32(LOAD_ADDRESS),
        "compound_destination": {
            "type": "0xaf",
            "initializer": hex32(runtime(expected["compound_init"])),
            "dispatch_table": hex32(runtime(expected["compound_dispatch"])),
            "runtime_context": hex32(expected["compound_context"]),
            "runtime_child_sizes": hex32(expected["compound_sizes"]),
            "child_type_bytes": hex32(runtime(expected["child_types"])),
            "children": child_specs,
            "total_capacity": logical_offset,
            "total_capacity_hex": f"0x{logical_offset:x}",
        },
        "separate_internal_prefix": {
            "type": "0x2b",
            "address_start": "0x00000000",
            "address_end_exclusive": "0x00003000",
            "capacity_hex": "0x3000",
            "included_in_0xaf": False,
        },
        "source_staging_region": {
            "type": "0x0e",
            "logical_address_start": "0x68118000",
            "logical_address_end_exclusive": "0x68617000",
            "capacity_hex": "0x4ff000",
            "capacity_minus_0xaf": "0x2000",
            "copy_length_note": (
                "The update loop derives its runtime copy length from an embedded "
                "record header; it does not blindly copy this descriptor capacity."
            ),
        },
        "operation_order": [
            "On the rewrite branch, call the full-erase method for type 0xaf.",
            "The compound erase method accepts only a whole-object request and dispatches child 0xab before child 0xac.",
            "Read type 0x0e and write type 0xaf in chunks no larger than 0x1e000 bytes, increasing the compound offset monotonically.",
            "The compound splitter divides a boundary-crossing transfer: offsets below 0x1fd000 use 0xab; later offsets use 0xac with a rebased child offset.",
            "Checksum the written type 0xaf destination after the copy.",
        ],
        "erase_write_behavior": {
            "internal_0xab": {
                "erase": (
                    f"Whole-region erase: {internal_sectors} consecutive 0x1000-byte "
                    "FTFE sectors from 0x00003000 through 0x001fffff; each erase is blank-verified."
                ),
                "write": (
                    "Writes exact internal-flash address 0x00003000 + child offset, "
                    "split at 0x1000-byte boundaries; low-level Program Section "
                    "operations stage at most 0x400 bytes in FlexRAM."
                ),
            },
            "external_0xac": {
                "erase": (
                    f"Whole-region erase from 0x68617000 through 0x68916fff: "
                    f"{leading_4k} leading 4 KiB sectors, {middle_64k} aligned 64 KiB "
                    f"blocks, then {trailing_4k} trailing 4 KiB sectors. Already-blank "
                    "units are skipped."
                ),
                "write": (
                    "Writes external address 0x68617000 + child offset through the "
                    "QuadSPI path, respecting 0x100-byte page boundaries and feeding "
                    "the controller in chunks of at most 0x40 bytes."
                ),
            },
        },
        "vtable_addresses": {
            "compound": hex32(runtime(expected["compound_vtable"])),
            "internal_flash": hex32(internal_vtable_ptr),
            "external_ufs_quadspi": hex32(runtime(expected["ufs_vtable"])),
        },
        "semantic_function_addresses": semantic_functions,
        "boot_prefix_result": (
            "Neither 0xaf child reaches internal addresses below 0x00003000. "
            "The copy target can replace all internal flash from 0x00003000 through "
            "0x001fffff plus the 3 MiB external 0xac region. A separate type 0x2b "
            "backend exposes 0x00000000 through 0x00002fff, but it is not an 0xaf child."
        ),
        "limitations": [
            "The static label 'resident boot prefix' is inferred from the application's 0x3000 base and the separate 0x2b mapping; the helper contains no symbol naming it a bootloader.",
            "This proves the 0xaf backend's addressing and methods, not the omitted resident loader's signature policy or recovery behavior.",
            "The presence of the separate 0x2b backend means this report does not claim that every possible helper call path is incapable of addressing the boot prefix.",
            "No firmware was executed and no device was accessed.",
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
