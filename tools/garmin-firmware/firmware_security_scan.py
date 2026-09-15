#!/usr/bin/env python3
"""Offline security-anchor scanner for a raw Cortex-M Garmin fw_all image.

The scanner is deliberately conservative.  It reports byte offsets, virtual
addresses under a caller-supplied flat base, exact 32-bit pointer slots, and
Thumb-1 PC-relative literal loads.  It does not claim that a printable string
or a cryptographic constant is part of the system-update trust decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


DEFAULT_ANCHORS = (
    "0:/Garmin/GUPDATE.GCD",
    "GUPDATE.GCD",
    "UpdateFile",
    "hwm_system_update.c",
    "hwm_update.c: 169",
    "Signature check failed on file:",
    "CIQSTORE.PUB",
    "CIQTEST.PUB",
    "checksum read from the file is 0",
    "checksum calc",
)

CONSTANT_SETS = {
    "sha1_initial_state": (
        0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0
    ),
    "sha256_initial_state": (
        0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
        0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
    ),
    # The first four words also prefix SHA-1, so overlapping hits are expected
    # and must not be counted as independent proof of MD5.
    "md5_initial_state": (0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476),
}


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    return [match.start() for match in re.finditer(re.escape(needle), data)]


def thumb1_literal_loads(data: bytes, base: int, slots: set[int]) -> list[dict]:
    """Find 16-bit Thumb LDR (literal) instructions targeting pointer slots."""
    result = []
    for offset in range(0, len(data) - 1, 2):
        halfword = struct.unpack_from("<H", data, offset)[0]
        if halfword & 0xF800 != 0x4800:
            continue
        address = base + offset
        literal = ((address + 4) & ~3) + (halfword & 0xFF) * 4
        if literal in slots:
            result.append({
                "address": f"0x{address:08x}",
                "register": f"r{(halfword >> 8) & 7}",
                "literal_slot": f"0x{literal:08x}",
            })
    return result


def scan(data: bytes, base: int) -> dict:
    anchors = []
    for text in DEFAULT_ANCHORS:
        for offset in all_offsets(data, text.encode("ascii")):
            address = base + offset
            pointer_slots: set[int] = set()
            for pointer in (address, address | 1):
                pointer_slots.update(base + item for item in all_offsets(
                    data, struct.pack("<I", pointer)
                ))
            anchors.append({
                "text": text,
                "file_offset": f"0x{offset:08x}",
                "address": f"0x{address:08x}",
                "exact_pointer_slots": [f"0x{x:08x}" for x in sorted(pointer_slots)],
                "thumb1_literal_loads": thumb1_literal_loads(data, base, pointer_slots),
            })

    constants = []
    for name, words in CONSTANT_SETS.items():
        needle = b"".join(struct.pack("<I", word) for word in words)
        constants.append({
            "name": name,
            "little_endian_addresses": [
                f"0x{base + offset:08x}" for offset in all_offsets(data, needle)
            ],
        })

    pem_markers = {}
    for marker in (b"-----BEGIN CERTIFICATE-----", b"-----BEGIN PUBLIC KEY-----"):
        pem_markers[marker.decode("ascii")] = [
            f"0x{base + offset:08x}" for offset in all_offsets(data, marker)
        ]

    vector = None
    if len(data) >= 8:
        sp, reset = struct.unpack_from("<II", data)
        vector = {
            "initial_sp": f"0x{sp:08x}",
            "reset_handler": f"0x{reset:08x}",
        }
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "flat_base_assumption": f"0x{base:08x}",
        "vector": vector,
        "anchors": anchors,
        "cryptographic_constant_sets": constants,
        "pem_markers": pem_markers,
        "limitations": [
            "Exact pointers and Thumb-1 literal loads are evidence of a reference, not its purpose.",
            "No MOVW/MOVT, computed, indexed-resource, or separately mapped-region references are resolved.",
            "Cryptographic constants establish bundled primitives only; they do not connect them to update validation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x3000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = scan(args.image.read_bytes(), args.base)
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
