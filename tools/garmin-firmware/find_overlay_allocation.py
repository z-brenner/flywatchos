#!/usr/bin/env python3
"""Fail-closed, offline-only evaluation of explicit overlay candidate intervals.

Addresses and ranges are integers, and range endpoints are inclusive. Evidence
blocks must identify the exact image, declare completeness, and cover every raw
image byte using base-relative addresses. Appended resources are scanned too;
this coordinate convention does not claim they execute at the raw load address.
All supplied intervals are evaluated; no rejected interval is silently dropped.
Even successful static selection NEVER authorizes target packaging: linked target
and execution verification are separate obligations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


def _uint(value: Any, maximum: int = 0xFFFFFFFF) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _ranges(value: Any) -> list[tuple[int, int]]:
    if not isinstance(value, list):
        raise ValueError("ranges must be a list")
    output = []
    for pair in value:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(_uint(item) for item in pair) or pair[0] > pair[1]):
            raise ValueError("invalid inclusive range")
        output.append((pair[0], pair[1]))
    return sorted(set(output))


def _addresses(value: Any) -> list[int]:
    if not isinstance(value, list) or not all(_uint(item) for item in value):
        raise ValueError("addresses must be a list of unsigned integers")
    return sorted(set(value))


def _full_coverage(ranges: list[tuple[int, int]], base: int, end: int,
                   *, disjoint: bool = False) -> bool:
    cursor = base
    for start, stop in ranges:
        if start < base or stop > end or start > cursor:
            return False
        if disjoint and start != cursor:
            return False
        cursor = max(cursor, stop + 1)
    return cursor == end + 1


def thumb_bl_reachable(source: int, target: int) -> bool:
    """Thumb-2 BL signed 25-bit even displacement, without address wraparound."""
    if (not _uint(source) or not _uint(target) or source & 1 or target & 1
            or source > 0xFFFFFFFB):
        return False
    displacement = target - (source + 4)
    return -(1 << 24) <= displacement <= (1 << 24) - 2


def _evidence(name: str, block: Any, image: bytes, base: int,
              fields: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    empty = {key: [] for key in fields}
    if block is None:
        return empty, ["missing_evidence:" + name]
    if not isinstance(block, dict):
        return empty, ["evidence:" + name + ":invalid_block"]
    reasons = []
    prefix = "evidence:" + name + ":"
    expected = {"image_sha256": hashlib.sha256(image).hexdigest(),
                "image_base": base, "image_length": len(image)}
    for key, value in expected.items():
        if type(block.get(key)) is not type(value) or block.get(key) != value:
            reasons.append(prefix + key + "_mismatch_or_missing")
    if block.get("complete") is not True:
        reasons.append(prefix + "not_complete")
    if not isinstance(block.get("source"), str) or not block["source"].strip():
        reasons.append(prefix + "source_missing")
    try:
        coverage = _ranges(block.get("coverage"))
        if not _full_coverage(coverage, base, base + len(image) - 1):
            reasons.append(prefix + "incomplete_image_coverage")
    except ValueError:
        reasons.append(prefix + "invalid_or_missing_coverage")
    normalized = {}
    for key in fields:
        try:
            normalized[key] = (_addresses(block.get(key)) if key in ("targets", "boundaries")
                               else _ranges(block.get(key)))
        except ValueError:
            reasons.append(prefix + "invalid_or_missing_" + key)
            normalized[key] = []
    if name == "section_metadata" and not _full_coverage(
            normalized["sections"], base, base + len(image) - 1, disjoint=True):
        reasons.append(prefix + "section_map_incomplete_or_overlapping")
    return normalized, reasons


def _interval(start: int, end: int, fill_byte: int) -> dict[str, Any]:
    return {"start": f"0x{start:08x}", "end": f"0x{end:08x}",
            "length": end - start + 1, "fill_byte": f"0x{fill_byte:02x}"}


def scan_allocation(*, image: bytes, base: int, minimum_length: int,
                    candidate_ranges: list, fill_byte: int,
                    protected_ranges: dict | None = None,
                    reference_targets: dict | None = None,
                    decoded_ranges: dict | None = None,
                    section_metadata: dict | None = None,
                    branch_anchors: list[int] | None = None) -> dict[str, Any]:
    """Evaluate all candidates using independent, explicitly supplied evidence.

    Each evidence block requires image_sha256, image_base, image_length,
    coverage, complete (literal true), source, and the following payload:
      protected_ranges: ranges (every existing allocation/hook/checksum byte)
      reference_targets: targets (complete Ghidra/direct/literal references)
      decoded_ranges: ranges (every occupied instruction and literal/data unit)
      section_metadata: ranges (reserved metadata), boundaries, sections
    Coverage describes the audit extent, including bytes with no findings.
    Empty findings are valid only with a complete, image-bound audit.

    The extra sliding little-endian pointer scan examines every byte offset,
    including unaligned and final words; false positives are deliberate. Odd
    pointer values also protect their even Thumb target. Branch anchors are
    even instruction addresses; both directions to interval extremes must fit.
    """
    if (not isinstance(image, bytes) or not image or not _uint(base)
            or base + len(image) > 1 << 32 or not _uint(fill_byte, 255)
            or not _uint(minimum_length) or minimum_length == 0):
        raise ValueError("invalid image, base, minimum length, or fill byte")
    candidates = _ranges(candidate_ranges)
    if not candidates:
        raise ValueError("at least one explicit candidate interval is required")
    schemas = {"protected_ranges": ("ranges",), "reference_targets": ("targets",),
               "decoded_ranges": ("ranges",),
               "section_metadata": ("ranges", "boundaries", "sections")}
    blocks = {"protected_ranges": protected_ranges, "reference_targets": reference_targets,
              "decoded_ranges": decoded_ranges, "section_metadata": section_metadata}
    evidence, global_reasons = {}, []
    for name, fields in schemas.items():
        evidence[name], reasons = _evidence(name, blocks[name], image, base, fields)
        global_reasons.extend(reasons)
    try:
        anchors = _addresses(branch_anchors)
        if not anchors:
            global_reasons.append("branch_evidence:missing_anchors")
    except ValueError:
        anchors = []
        global_reasons.append("branch_evidence:invalid_or_missing_anchors")
    # Scan once, across the complete input, then filter each exact interval.
    # Retain source byte offsets: resource data has a different runtime mapping.
    raw_pointers = []
    low, high = candidates[0][0], max(end for _, end in candidates)
    for offset in range(len(image) - 3):
        target = struct.unpack_from("<I", image, offset)[0]
        if low <= target <= high or low <= (target & ~1) <= high:
            raw_pointers.append((offset, target))
    accepted, rejected = [], []
    for start, end in candidates:
        reasons = list(global_reasons)
        observation = {"interval": _interval(start, end, fill_byte)}
        if start < base or end >= base + len(image):
            reasons.append("candidate:outside_image")
        else:
            chunk = image[start - base:end - base + 1]
            bad = [start + offset for offset, value in enumerate(chunk) if value != fill_byte]
            observation["fill_verified"] = not bad
            if bad:
                observation["non_fill_count"] = len(bad)
                reasons.append(f"non_fill_byte:first=0x{bad[0]:08x}:count={len(bad)}")
        if end - start + 1 < minimum_length:
            reasons.append("candidate:too_short")
        if start & 1:
            reasons.append("candidate:unaligned_start")
        for name in ("protected_ranges", "decoded_ranges", "section_metadata"):
            for lower, upper in evidence[name]["ranges"]:
                if start <= upper and lower <= end:
                    reasons.append(f"{name}_overlap:0x{lower:08x}..0x{upper:08x}")
        for boundary in evidence["section_metadata"]["boundaries"]:
            if start <= boundary <= end:
                reasons.append(f"section_boundary:0x{boundary:08x}")
        containing = [(lower, upper) for lower, upper in evidence["section_metadata"]["sections"]
                      if lower <= start and end <= upper]
        if len(containing) != 1:
            reasons.append("section_metadata:candidate_not_in_one_section")
        reference_hits = [target for target in evidence["reference_targets"]["targets"]
                          if start <= target <= end or start <= (target & ~1) <= end]
        observation["reference_targets"] = [f"0x{target:08x}" for target in reference_hits]
        for target in reference_hits:
            reasons.append(f"reference_target:0x{target:08x}")
        pointer_hits = [(offset, target) for offset, target in raw_pointers
                        if start <= target <= end or start <= (target & ~1) <= end]
        observation["raw_pointer_hits"] = [
            {"source_file_offset": f"0x{offset:08x}", "value": f"0x{target:08x}"}
            for offset, target in pointer_hits]
        for offset, target in pointer_hits:
            reasons.append(f"raw_pointer:offset=0x{offset:08x}:value=0x{target:08x}")
        # Last possible 4-byte Thumb BL instruction wholly contained in interval.
        last_source = (end - 3) & ~1
        last_target = end & ~1
        branch_checks = []
        if end - start + 1 < 4 or not (start <= last_source and last_source + 3 <= end):
            reasons.append("candidate:cannot_fit_thumb_bl")
        else:
            for anchor in anchors:
                for source, target in sorted(set([(anchor, start), (anchor, last_target),
                                                 (start, anchor), (last_source, anchor)])):
                    reachable = thumb_bl_reachable(source, target)
                    branch_checks.append({"source": f"0x{source:08x}", "target": f"0x{target:08x}",
                                          "reachable": reachable})
                    if not reachable:
                        reasons.append(f"branch_unusable:0x{source:08x}->0x{target:08x}")
        observation["branch_checks"] = branch_checks
        observation["reasons"] = sorted(set(reasons))
        (rejected if reasons else accepted).append(observation)
    return {
        "schema_version": 1,
        "image": {"base": f"0x{base:08x}", "length": len(image),
                  "sha256": hashlib.sha256(image).hexdigest()},
        "minimum_length": minimum_length,
        "evidence_errors": sorted(set(global_reasons)),
        "accepted_candidates": accepted, "rejected_candidates": rejected,
        "selected_interval": accepted[0]["interval"] if accepted else None,
        "packaging_allowed": False,
        "packaging_blockers": ["Static selection cannot authorize packaging; exact linker bounds, "
                               "RTC audit, full-image validation, and Unicorn execution of every "
                               "inter-allocation branch require separate verified artifacts."],
    }


def json_text(report: dict[str, Any]) -> str:
    """Stable JSON: no timestamps, platform paths, or unordered output sets."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--base", required=True, type=lambda text: int(text, 0))
    parser.add_argument("--minimum-length", required=True, type=lambda text: int(text, 0))
    parser.add_argument("--fill-byte", required=True, type=lambda text: int(text, 0))
    parser.add_argument("--candidate", required=True, action="append", help="Inclusive START:END")
    parser.add_argument("--branch-anchor", required=True, action="append", type=lambda text: int(text, 0))
    parser.add_argument("--evidence", required=True, type=Path,
                        help="JSON containing the four evidence blocks documented by scan_allocation")
    parser.add_argument("--output", type=Path, help="JSON only; this tool never produces firmware")
    args = parser.parse_args(argv)
    # Keep scanner outputs from replacing its evidence or firmware inputs.
    try:
        if args.output:
            if (args.output.suffix.lower() != ".json" or
                    args.output.resolve() in (args.image.resolve(), args.evidence.resolve())):
                raise ValueError("output must be a distinct .json file, never an image or evidence input")
            if args.output.exists() and any(args.output.samefile(path) for path in (args.image, args.evidence)):
                raise ValueError("output is a hard-link alias of an image or evidence input")
    except (OSError, ValueError) as error:
        sys.stdout.write(json_text({
            "schema_version": 1, "selected_interval": None, "packaging_allowed": False,
            "input_error": str(error),
        }))
        return 2
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
        if not isinstance(evidence, dict):
            raise ValueError("evidence manifest must be an object")
        report = scan_allocation(
            image=args.image.read_bytes(), base=args.base, minimum_length=args.minimum_length,
            fill_byte=args.fill_byte,
            candidate_ranges=[[int(part, 0) for part in item.split(":")] for item in args.candidate],
            branch_anchors=args.branch_anchor,
            **{key: evidence.get(key) for key in ("protected_ranges", "reference_targets",
                                                "decoded_ranges", "section_metadata")})
    except (OSError, ValueError, TypeError) as error:
        report = {"schema_version": 1, "selected_interval": None, "packaging_allowed": False,
                  "input_error": str(error)}
    rendered = json_text(report)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered)
    return 0 if report.get("selected_interval") is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
