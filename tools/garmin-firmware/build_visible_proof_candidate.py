#!/usr/bin/env python3
"""Build one quarantined, offline-only FR245 visible-proof candidate.

The fixed patch replaces the English About-page label ``Software Version``
with the same-length text ``FLY LIVES 2ALIVE`` whose additive byte sum has the
same low byte.  The unusual suffix is deliberate: it preserves the confirmed
modulo-256 checks without changing a second payload byte.  The output is
analysis material and must never be copied to a watch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import full_image_validator  # noqa: E402
import gcd_inspect  # noqa: E402


SOURCE_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
MAIN_RECORD_ID = 0x02BD
TARGET_OFFSET = 0x43EAA4
ABOUT_OFFSET = 0x442524
EXTERNAL_FILE_OFFSET = 0x1FD000
EXTERNAL_RUNTIME_BASE = 0x04600000
ORIGINAL = b"Software Version"
REPLACEMENT = b"FLY LIVES 2ALIVE"
FIELD_CONTEXT = (
    b"Cancel\x00\x00Software Version\x00\x00\x00\x00Unit ID\x00"
    b"Bluetooth MAC Address\x00"
)
ABOUT_CONTEXT = b"Disable Logging\x00About\x00\x00\x00Smart\x00"
REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _main_stream(data: bytes) -> Any:
    streams = [
        stream
        for stream in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
        if stream.record_id == MAIN_RECORD_ID
    ]
    if len(streams) != 1:
        raise gcd_inspect.GcdFormatError(
            f"expected one type-0x{MAIN_RECORD_ID:04x} stream, found {len(streams)}"
        )
    return streams[0]


def _decoded_to_raw(data: bytes, stream: Any, decoded_offset: int) -> int:
    if stream.xor_key != 0:
        raise ValueError("fixed proof patch requires an un-XORed main stream")
    cursor = 0
    records = {record.offset: record for record in gcd_inspect.parse_gcd(data).records}
    for record_offset in stream.record_offsets:
        record = records[record_offset]
        if decoded_offset < cursor + record.length:
            return record.offset + 4 + decoded_offset - cursor
        cursor += record.length
    raise ValueError("decoded offset is outside the stream records")


def build_candidate(source: bytes) -> tuple[bytes, dict[str, Any]]:
    if _sha256(source) != SOURCE_SHA256:
        raise ValueError("source is not the pinned official non-Music 13.70 GCD")
    stream = _main_stream(source)
    if _sha256(stream.decoded) != MAIN_SHA256:
        raise ValueError("decoded main stream does not match the pinned official image")
    if len(ORIGINAL) != len(REPLACEMENT):
        raise AssertionError("fixed patch changed length")
    if sum(ORIGINAL) & 0xFF != sum(REPLACEMENT) & 0xFF:
        raise AssertionError("fixed patch changed additive byte-sum low byte")
    if stream.decoded.count(ORIGINAL) != 1:
        raise ValueError("Software Version is not unique in the decoded main stream")
    if stream.decoded.find(ORIGINAL) != TARGET_OFFSET:
        raise ValueError("Software Version moved from its pinned decoded offset")
    if stream.decoded.count(FIELD_CONTEXT) != 1:
        raise ValueError("pinned About-field resource context is absent or ambiguous")
    if stream.decoded.count(ABOUT_CONTEXT) != 1:
        raise ValueError("pinned System-menu About resource context is absent or ambiguous")
    if stream.decoded.find(ABOUT_CONTEXT) + len(b"Disable Logging\x00") != ABOUT_OFFSET:
        raise ValueError("System-menu About label moved from its pinned decoded offset")

    raw_offset = _decoded_to_raw(source, stream, TARGET_OFFSET)
    if source[raw_offset : raw_offset + len(ORIGINAL)] != ORIGINAL:
        raise ValueError("raw GCD bytes do not contain the expected un-XORed label")
    candidate = bytearray(source)
    candidate[raw_offset : raw_offset + len(ORIGINAL)] = REPLACEMENT
    candidate = bytes(candidate)

    changed = [
        {"raw_offset": f"0x{index:x}", "old": old, "new": new}
        for index, (old, new) in enumerate(zip(source, candidate))
        if old != new
    ]
    candidate_stream = _main_stream(candidate)
    validation = full_image_validator.validate_bytes(candidate, "quarantined-candidate")
    original_checkpoints = [
        (item.offset, bytes(source[item.offset : item.offset + 5]))
        for item in gcd_inspect.parse_gcd(source).records
        if item.record_id == 0x0001
    ]
    candidate_checkpoints = [
        (item.offset, bytes(candidate[item.offset : item.offset + 5]))
        for item in gcd_inspect.parse_gcd(candidate).records
        if item.record_id == 0x0001
    ]

    checks = {
        "same_file_length": len(candidate) == len(source),
        "bytes_before_target_unchanged": candidate[:raw_offset] == source[:raw_offset],
        "bytes_after_target_unchanged": (
            candidate[raw_offset + len(ORIGINAL) :]
            == source[raw_offset + len(ORIGINAL) :]
        ),
        "checkpoint_records_byte_identical": candidate_checkpoints == original_checkpoints,
        "all_outer_prefix_sums_zero_mod_256": validation["outer_gcd"][
            "all_prefix_sums_zero_mod_256"
        ],
        "non_delta_main_stream": not validation["main_stream"]["gdelta01"],
        "main_stream_byte_sum_mod_256": validation["main_stream"]["byte_sum_mod_256"],
        "confirmed_application_full_image_checks_pass": validation[
            "confirmed_full_image_checks_pass"
        ],
        "replacement_unique": candidate_stream.decoded.count(REPLACEMENT) == 1,
        "original_label_absent": candidate_stream.decoded.count(ORIGINAL) == 0,
        "only_target_allocation_changed": all(
            raw_offset <= int(item["raw_offset"], 16) < raw_offset + len(ORIGINAL)
            for item in changed
        ),
    }
    boolean_checks = [
        value
        for key, value in checks.items()
        if key != "main_stream_byte_sum_mod_256"
    ]
    if checks["main_stream_byte_sum_mod_256"] != 0 or not all(boolean_checks):
        raise AssertionError(f"candidate validation failed: {checks}")

    report = {
        "purpose": "offline visible-proof candidate; prohibited from watch transfer",
        "source": {
            "sha256": SOURCE_SHA256,
            "size": len(source),
            "main_stream_sha256": MAIN_SHA256,
            "effective_version_fields": "unchanged from official 13.70 package",
        },
        "patch": {
            "record_id": "0x02bd",
            "decoded_offset": f"0x{TARGET_OFFSET:x}",
            "raw_file_offset": f"0x{raw_offset:x}",
            "old_ascii": ORIGINAL.decode("ascii"),
            "new_ascii": REPLACEMENT.decode("ascii"),
            "length": len(ORIGINAL),
            "old_byte_sum": sum(ORIGINAL),
            "new_byte_sum": sum(REPLACEMENT),
            "old_and_new_byte_sum_mod_256": sum(ORIGINAL) & 0xFF,
            "changed_byte_count": len(changed),
            "changed_bytes": changed,
        },
        "output": {
            "sha256": _sha256(candidate),
            "size": len(candidate),
            "main_stream_sha256": _sha256(candidate_stream.decoded),
            "recognized_gcd_extension": False,
        },
        "checks": checks,
        "display_evidence": {
            "confidence": "strongly inferred; resource resolver call site unresolved",
            "resource": "unique English Software Version label",
            "resource_decoded_offset": f"0x{TARGET_OFFSET:x}",
            "resource_runtime_address": hex(
                EXTERNAL_RUNTIME_BASE + TARGET_OFFSET - EXTERNAL_FILE_OFFSET
            ),
            "adjacent_resources": ["Unit ID", "Bluetooth MAC Address"],
            "system_menu_about_decoded_offset": f"0x{ABOUT_OFFSET:x}",
            "system_menu_about_runtime_address": hex(
                EXTERNAL_RUNTIME_BASE + ABOUT_OFFSET - EXTERNAL_FILE_OFFSET
            ),
            "source_context_checks": {
                "about_field_cluster_unique": stream.decoded.count(FIELD_CONTEXT) == 1,
                "system_menu_cluster_unique": stream.decoded.count(ABOUT_CONTEXT) == 1,
            },
            "documented_route": "watch face -> hold UP -> System -> About",
            "manual_url": (
                "https://www8.garmin.com/manuals/webhelp/forerunner245/EN-US/"
                "GUID-E131EDC8-BB20-4F2B-AF7B-E6EC45B107E0.html"
            ),
        },
        "limitations": [
            "No watch, loader, or Garmin update application accepted or executed this file.",
            "The indirect localization-resource resolver call site remains unresolved.",
            "Resident-loader authentication, installation, rollback, and recovery are not modeled.",
            "The output filename is intentionally not GUPDATE.GCD and must never be renamed or copied to a watch.",
        ],
    }
    return candidate, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("output must differ from source")
    if "quarantine" not in {part.lower() for part in args.output.parts}:
        parser.error("output must be beneath a directory named quarantine")
    if not args.output.name.endswith(REQUIRED_SUFFIX):
        parser.error(f"output filename must end with {REQUIRED_SUFFIX}")

    candidate, report = build_candidate(args.source.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    report["output"]["path"] = str(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["output"]["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
