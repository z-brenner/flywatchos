#!/usr/bin/env python3
"""Build the quarantined FR245 13.70 in-app FLY LIVES overlay candidate."""

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
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


SOURCE_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
HELPER_SHA256 = "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46"
MAIN_RECORD_ID = 0x02BD
HELPER_RECORD_ID = 0x0505
FLASH_BASE = 0x00003000
HOOK_VA = 0x00009A20
HOOK_OFFSET = HOOK_VA - FLASH_BASE
ORIGINAL_HOOK = bytes.fromhex("04f0c0fb")
ERASED_TAIL_START_VA = 0x001F5E0C
ERASED_TAIL_END_VA = 0x001FFFFF
OVERLAY_VA = 0x001F6000
OVERLAY_OFFSET = OVERLAY_VA - FLASH_BASE
OVERLAY_ALLOCATION = 0x400
CAVE_START_VA = OVERLAY_VA
CAVE_END_VA = OVERLAY_VA + OVERLAY_ALLOCATION - 1
CHECKSUM_OFFSET = OVERLAY_OFFSET + OVERLAY_ALLOCATION - 1
REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_thumb_bl(instruction_va: int, encoded: bytes) -> int:
    """Decode one Thumb-2 BL immediate and return its even destination."""
    if len(encoded) != 4:
        raise ValueError("Thumb BL must be exactly four bytes")
    first = int.from_bytes(encoded[:2], "little")
    second = int.from_bytes(encoded[2:], "little")
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
        raise ValueError("hook bytes are not a Thumb-2 BL immediate")
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x07FF
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    displacement = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | (imm10 << 12)
        | (imm11 << 1)
    )
    if sign:
        displacement -= 1 << 25
    return (instruction_va + 4 + displacement) & 0xFFFFFFFF


def _streams(data: bytes) -> tuple[Any, Any]:
    streams = gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
    helper = [item for item in streams if item.record_id == HELPER_RECORD_ID]
    main = [item for item in streams if item.record_id == MAIN_RECORD_ID]
    if len(helper) != 1 or len(main) != 1:
        raise ValueError("expected exactly one helper and one main firmware stream")
    return helper[0], main[0]


def _replace_decoded_slice(
    data: bytes, stream: Any, decoded_offset: int, replacement: bytes
) -> bytes:
    if stream.xor_key != 0:
        raise ValueError("overlay builder requires an un-XORed main stream")
    if decoded_offset < 0 or decoded_offset + len(replacement) > stream.declared_length:
        raise ValueError("decoded replacement is outside the main stream")
    mutable = bytearray(data)
    records_by_offset = {
        record.offset: record for record in gcd_inspect.parse_gcd(data).records
    }
    source_cursor = 0
    written = 0
    replacement_end = decoded_offset + len(replacement)
    for record_offset in stream.record_offsets:
        record = records_by_offset[record_offset]
        record_start = source_cursor
        record_end = source_cursor + record.length
        overlap_start = max(decoded_offset, record_start)
        overlap_end = min(replacement_end, record_end)
        if overlap_start < overlap_end:
            count = overlap_end - overlap_start
            replacement_cursor = overlap_start - decoded_offset
            raw_start = record.offset + 4 + overlap_start - record_start
            mutable[raw_start : raw_start + count] = replacement[
                replacement_cursor : replacement_cursor + count
            ]
            written += count
        source_cursor = record_end
    if written != len(replacement):
        raise AssertionError("stream records did not cover replacement")
    return bytes(mutable)


def _record_bytes(data: bytes, ids: set[int]) -> list[bytes]:
    return [
        data[record.offset : record.offset + 4 + record.length]
        for record in gcd_inspect.parse_gcd(data).records
        if record.record_id in ids
    ]


def _diff_hunks(before: bytes, after: bytes) -> list[dict[str, Any]]:
    hunks: list[dict[str, Any]] = []
    index = 0
    while index < len(before):
        if before[index] == after[index]:
            index += 1
            continue
        start = index
        while index < len(before) and before[index] != after[index]:
            index += 1
        hunks.append(
            {
                "raw_offset": f"0x{start:x}",
                "length": index - start,
                "old_hex": before[start:index].hex(),
                "new_hex": after[start:index].hex(),
            }
        )
    return hunks


def build_candidate(
    source: bytes, hook: bytes, payload: bytes, cave_xref_report: str
) -> tuple[bytes, dict[str, Any]]:
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("source is not the pinned official non-Music 13.70 GCD")
    helper, main = _streams(source)
    if sha256(helper.decoded) != HELPER_SHA256 or sha256(main.decoded) != MAIN_SHA256:
        raise ValueError("pinned official firmware streams do not match")
    if f"range={CAVE_START_VA:08x}..{CAVE_END_VA:08x}" not in cave_xref_report:
        raise ValueError("code-cave reference report covers the wrong address range")
    if "reference_count=0" not in cave_xref_report:
        raise ValueError("code cave has static references")
    if decode_thumb_bl(HOOK_VA, hook) != OVERLAY_VA:
        raise ValueError("linked hook does not branch to the overlay entry")
    if len(payload) == 0 or len(payload) >= OVERLAY_ALLOCATION:
        raise ValueError("overlay payload does not fit the reserved cave allocation")
    if main.decoded[HOOK_OFFSET : HOOK_OFFSET + 4] != ORIGINAL_HOOK:
        raise ValueError("official display hook bytes changed")
    cave_start_offset = CAVE_START_VA - FLASH_BASE
    cave_end_offset = CAVE_END_VA - FLASH_BASE + 1
    if any(byte != 0xFF for byte in main.decoded[cave_start_offset:cave_end_offset]):
        raise ValueError("official code cave is not entirely erased bytes")

    allocation = bytearray(b"\xff" * OVERLAY_ALLOCATION)
    allocation[: len(payload)] = payload
    mutated = _replace_decoded_slice(source, main, HOOK_OFFSET, hook)
    _, mutated_main = _streams(mutated)
    mutated = _replace_decoded_slice(mutated, mutated_main, OVERLAY_OFFSET, allocation)
    _, mutated_main = _streams(mutated)
    remainder = sum(mutated_main.decoded) & 0xFF
    checksum_old = mutated_main.decoded[CHECKSUM_OFFSET]
    checksum_new = (checksum_old - remainder) & 0xFF
    mutated = _replace_decoded_slice(
        mutated, mutated_main, CHECKSUM_OFFSET, bytes([checksum_new])
    )
    candidate = recompute_checkpoints(mutated)

    candidate_helper, candidate_main = _streams(candidate)
    validation = full_image_validator.validate_bytes(candidate, "overlay-candidate")
    main_differences = [
        index
        for index, (old, new) in enumerate(zip(main.decoded, candidate_main.decoded))
        if old != new
    ]
    confined = all(
        HOOK_OFFSET <= index < HOOK_OFFSET + 4
        or OVERLAY_OFFSET <= index < OVERLAY_OFFSET + OVERLAY_ALLOCATION
        for index in main_differences
    )
    descriptor_identical = _record_bytes(source, {0x0006, 0x0007}) == _record_bytes(
        candidate, {0x0006, 0x0007}
    )
    checks = {
        "source_main_stream_pinned": sha256(main.decoded) == MAIN_SHA256,
        "helper_stream_byte_identical": candidate_helper.decoded == helper.decoded,
        "descriptor_records_byte_identical": descriptor_identical,
        "hook_decodes_to_overlay": decode_thumb_bl(HOOK_VA, hook) == OVERLAY_VA,
        "official_cave_all_ff": all(
            byte == 0xFF for byte in main.decoded[cave_start_offset:cave_end_offset]
        ),
        "cave_static_reference_count_zero": "reference_count=0" in cave_xref_report,
        "payload_fits_reserved_allocation": len(payload) < OVERLAY_ALLOCATION,
        "changed_main_bytes_confined": confined,
        "main_stream_byte_sum_mod_256": sum(candidate_main.decoded) & 0xFF,
        "all_outer_prefix_sums_zero_mod_256": validation["outer_gcd"][
            "all_prefix_sums_zero_mod_256"
        ],
        "confirmed_application_full_image_checks_pass": validation[
            "confirmed_full_image_checks_pass"
        ],
    }
    boolean_checks = [
        value
        for key, value in checks.items()
        if key != "main_stream_byte_sum_mod_256"
    ]
    if checks["main_stream_byte_sum_mod_256"] != 0 or not all(boolean_checks):
        raise AssertionError(f"overlay candidate checks failed: {checks}")

    report = {
        "purpose": "offline FR245 13.70 in-app FLY LIVES overlay candidate",
        "install_status": "quarantined; not approved for device transfer",
        "source": {
            "sha256": SOURCE_SHA256,
            "size": len(source),
            "main_stream_sha256": MAIN_SHA256,
            "helper_stream_sha256": HELPER_SHA256,
        },
        "patch": {
            "hook": {
                "va": f"0x{HOOK_VA:08x}",
                "decoded_offset": f"0x{HOOK_OFFSET:x}",
                "old_hex": ORIGINAL_HOOK.hex(),
                "new_hex": hook.hex(),
                "target_va": f"0x{decode_thumb_bl(HOOK_VA, hook):08x}",
            },
            "payload": {
                "va": f"0x{OVERLAY_VA:08x}",
                "decoded_offset": f"0x{OVERLAY_OFFSET:x}",
                "length": len(payload),
                "sha256": sha256(payload),
                "reserved_allocation": OVERLAY_ALLOCATION,
                "draw_region": {"x": 50, "y": 102, "width": 140, "height": 22},
                "behavior": (
                    "draw a framed scientific plate with a 21x16 dorsal fly "
                    "silhouette and black 2x 5x7 text FLY LIVES, mark the "
                    "rectangle dirty, then tail-dispatch the original flush"
                ),
            },
            "inner_additive_repair": {
                "decoded_offset": f"0x{CHECKSUM_OFFSET:x}",
                "old_byte": checksum_old,
                "new_byte": checksum_new,
            },
            "changed_main_byte_count": len(main_differences),
        },
        "cave_evidence": {
            "range_va": f"0x{CAVE_START_VA:08x}..0x{CAVE_END_VA:08x}",
            "length": CAVE_END_VA - CAVE_START_VA + 1,
            "all_bytes_erased_ff": True,
            "ghidra_static_reference_count": 0,
            "ghidra_instruction_and_function_counts": "not measured by the range-reference report",
            "containing_erased_tail_va": (
                f"0x{ERASED_TAIL_START_VA:08x}..0x{ERASED_TAIL_END_VA:08x}"
            ),
            "preceding_table_end_pointer": f"0x{ERASED_TAIL_START_VA:08x}",
        },
        "checks": checks,
        "output": {
            "sha256": sha256(candidate),
            "size": len(candidate),
            "main_stream_sha256": sha256(candidate_main.decoded),
            "raw_changed_byte_count": sum(
                hunk["length"] for hunk in _diff_hunks(source, candidate)
            ),
            "raw_diff_hunks": _diff_hunks(source, candidate),
        },
        "limitations": [
            "The candidate has never been parsed, accepted, installed, or executed by the resident loader.",
            "Static evidence does not prove that 0x00 and 0xff render as black and white on every configured palette.",
            "The interposition executes only when GarminOS calls the exact 13.70 display-update wrapper.",
            "Official 13.70 restoration after a same-version modified install is not established.",
            "A loader rejection, interrupted rewrite, or bad runtime assumption could leave the watch unrecoverable.",
        ],
    }
    return candidate, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("hook", type=Path)
    parser.add_argument("payload", type=Path)
    parser.add_argument("--xref-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("output must differ from source")
    if "quarantine" not in {part.lower() for part in args.output.parts}:
        parser.error("output must be beneath a directory named quarantine")
    if not args.output.name.endswith(REQUIRED_SUFFIX):
        parser.error(f"output filename must end with {REQUIRED_SUFFIX}")

    candidate, report = build_candidate(
        args.source.read_bytes(),
        args.hook.read_bytes(),
        args.payload.read_bytes(),
        args.xref_report.read_text(encoding="utf-8"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    report["output"]["path"] = str(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["output"]["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
