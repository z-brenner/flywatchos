#!/usr/bin/env python3
"""Build one quarantined 13.69-header restore hypothesis, offline only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gcd_inspect  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


SOURCE_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
HEADER_VERSION_OFFSET = 0x22C
VISIBLE_OFFSET = 0x43EAA4
VISIBLE_ORIGINAL = b"Software Version"
VISIBLE_REPLACEMENT = b"FLY LIVES 2ALIVE"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stream(gcd: Any, record_id: int) -> Any:
    matches = [x for x in gcd_inspect.collect_streams(gcd) if x.record_id == record_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one 0x{record_id:04x} stream")
    return matches[0]


def _decoded_raw_map(gcd: Any, stream: Any) -> list[int]:
    records = {x.offset: x for x in gcd.records}
    offsets: list[int] = []
    for record_offset in stream.record_offsets:
        record = records[record_offset]
        offsets.extend(range(record.offset + 4, record.offset + 4 + record.length))
    if len(offsets) != stream.declared_length:
        raise ValueError("stream mapping length mismatch")
    return offsets


def _software_version_raw_offset(gcd: Any, target_record_id: int) -> int:
    field_types: list[tuple[int, int]] | None = None
    for record in gcd.records:
        if record.record_id == 0x0006:
            field_types = gcd_inspect._parse_field_types(record.body)
            continue
        if record.record_id != 0x0007 or field_types is None:
            continue
        fields = gcd_inspect._parse_descriptor(field_types, record.body)
        if gcd_inspect._field(fields, "record_id") != target_record_id:
            continue
        cursor = 0
        for field_id, field_type in field_types:
            size = gcd_inspect.FIELD_SIZES[field_type]
            if (field_id, field_type) == (0x0D, 0x10):
                return record.offset + 4 + cursor
            cursor += size
    raise ValueError(f"software-version field for 0x{target_record_id:04x} not found")


def build_candidate(
    source_path: Path, output_path: Path, *, match_main_descriptor: bool = False
) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("output must be a separate analysis file")
    source = source_path.read_bytes()
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("source is not the pinned official non-Music 13.70 package")
    gcd = gcd_inspect.parse_gcd(source)
    helper = _stream(gcd, 0x0505)
    main = _stream(gcd, 0x02BD)
    if sha256(main.decoded) != MAIN_SHA256:
        raise ValueError("main stream does not match the pinned official payload")
    if main.xor_key != 0:
        raise ValueError("expected un-XORed main stream")
    if main.decoded[HEADER_VERSION_OFFSET : HEADER_VERSION_OFFSET + 2] != b"\x5a\x05":
        raise ValueError("official 13.70 main header version is absent")
    visible_end = VISIBLE_OFFSET + len(VISIBLE_ORIGINAL)
    if main.decoded[VISIBLE_OFFSET:visible_end] != VISIBLE_ORIGINAL:
        raise ValueError("pinned visible label is absent")
    if len(VISIBLE_ORIGINAL) != len(VISIBLE_REPLACEMENT):
        raise AssertionError("visible replacement changes stream length")

    raw_map = _decoded_raw_map(gcd, main)
    mutable = bytearray(source)
    mutable[raw_map[HEADER_VERSION_OFFSET]] = 0x59
    for index, value in enumerate(VISIBLE_REPLACEMENT):
        mutable[raw_map[VISIBLE_OFFSET + index]] = value
    descriptor_version_offset = _software_version_raw_offset(gcd, 0x02BD)
    if match_main_descriptor:
        if mutable[descriptor_version_offset : descriptor_version_offset + 2] != b"\x5a\x05":
            raise ValueError("official main descriptor version is absent")
        mutable[descriptor_version_offset] = 0x59

    interim = _stream(gcd_inspect.parse_gcd(bytes(mutable)), 0x02BD)
    remainder = sum(interim.decoded) & 0xFF
    checksum_offset = main.declared_length - 1
    old_checksum = mutable[raw_map[checksum_offset]]
    mutable[raw_map[checksum_offset]] = (old_checksum - remainder) & 0xFF
    result = recompute_checkpoints(bytes(mutable))
    result_gcd = gcd_inspect.parse_gcd(result)
    result_helper = _stream(result_gcd, 0x0505)
    result_main = _stream(result_gcd, 0x02BD)
    if result_helper.decoded != helper.decoded or result_helper.fields != helper.fields:
        raise AssertionError("helper changed")
    if not match_main_descriptor and result_main.fields != main.fields:
        raise AssertionError("main descriptor changed")
    if match_main_descriptor and result_main.software_version != 1369:
        raise AssertionError("main descriptor did not change to 13.69")
    if sum(result_main.decoded) & 0xFF:
        raise AssertionError("main additive checksum is nonzero")
    if not all(x["valid"] for x in gcd_inspect._checkpoint_results(result_gcd)):
        raise AssertionError("outer checkpoint validation failed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result)
    return {
        "tool": "tools/garmin-firmware/gcd_restore_candidate_lab.py",
        "purpose": "offline restore-oriented hypothesis; prohibited from watch transfer",
        "source_sha256": SOURCE_SHA256,
        "output_sha256": sha256(result),
        "official_helper_sha256": sha256(helper.decoded),
        "candidate_helper_sha256": sha256(result_helper.decoded),
        "official_main_sha256": MAIN_SHA256,
        "candidate_main_sha256": sha256(result_main.decoded),
        "helper_byte_identical": True,
        "main_descriptor_byte_identical": not match_main_descriptor,
        "main_descriptor_software_version": result_main.software_version,
        "main_descriptor_raw_offset": f"0x{descriptor_version_offset:x}",
        "candidate_main_header_version": 1369,
        "candidate_main_descriptor_version": result_main.software_version,
        "changed_decoded_offsets": [
            "0x22c",
            "0x43eaa4..0x43eab3",
            f"0x{checksum_offset:x}",
        ],
        "checksum_repair": {
            "decoded_offset": f"0x{checksum_offset:x}",
            "old_byte": old_checksum,
            "new_byte": result_main.decoded[checksum_offset],
            "main_sum_mod_256": sum(result_main.decoded) & 0xFF,
            "outer_checkpoints_valid": True,
        },
        "limitations": [
            "No device acceptance or execution was tested.",
            "The installed-version reader has not been proven to source main header offset 0x22c.",
            (
                "The resident loader may reject the altered 13.69 main descriptor or enforce an unobserved signature."
                if match_main_descriptor
                else "The resident loader may reject a 13.70 descriptor paired with a 13.69 main header."
            ),
            "The artifact is analysis-only and must not be copied to the watch.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--match-main-descriptor",
        action="store_true",
        help="also set only the main descriptor software version to 13.69",
    )
    args = parser.parse_args()
    try:
        report = build_candidate(
            args.source, args.output, match_main_descriptor=args.match_main_descriptor
        )
    except (OSError, ValueError, gcd_inspect.GcdFormatError) as error:
        parser.error(str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["output_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
