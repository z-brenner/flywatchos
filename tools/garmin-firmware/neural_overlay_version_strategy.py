#!/usr/bin/env python3
"""Construct and exactly verify the offline-only FR245 neural package pair.

This tool is deliberately narrower than the generic GCD builders.  It accepts
one byte-pinned decision and one byte-pinned set of inputs, emits only the two
named analysis artifacts under the fixed local quarantine root, and never
accesses a device or updater-visible directory.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).parent))
import build_overlay_candidate  # noqa: E402
import full_image_validator  # noqa: E402
import gcd_inspect  # noqa: E402
import overlay_version_strategy  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXACT_QUARANTINE_ROOT = REPOSITORY_ROOT / "artifacts/firmware/quarantine"
EXACT_ANALYSIS_ROOT = REPOSITORY_ROOT / "artifacts/firmware/analysis"
DECISION_RELATIVE_PATH = Path(
    "artifacts/analysis/fr245-1370-neural-offline-construction-decision.json"
)
DECISION_SHA256 = "1179e1caded279c30ea21ff6403c11072b2bb937b01dc846590a7217f2e06dfa"
REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"
CANDIDATE_FILENAME = (
    "Forerunner245_1373-flyos-neural-overlay.gcd.analysis-only.DO_NOT_INSTALL"
)
RESTORE_FILENAME = (
    "Forerunner245_1374-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL"
)
BUILD_REPORT_FILENAME = "neural-overlay-package-build-1373-1374.json"
STRICT_REPORT_FILENAME = "neural-overlay-package-strict-verification-1373-1374.json"

MAIN_RECORD_ID = 0x02BD
HELPER_RECORD_ID = 0x0505
FLASH_BASE = 0x00003000
HOOK_VA = 0x00009A20
HOOK_OFFSET = HOOK_VA - FLASH_BASE
PRIMARY_VA = 0x001F6000
PRIMARY_OFFSET = PRIMARY_VA - FLASH_BASE
PRIMARY_ALLOCATION = 0x400
PRIMARY_REPAIR_VA = 0x001F63FF
PRIMARY_REPAIR_OFFSET = PRIMARY_REPAIR_VA - FLASH_BASE
SECONDARY_VA = 0x001FA400
SECONDARY_OFFSET = SECONDARY_VA - FLASH_BASE
SECONDARY_ALLOCATION = 0x800
MAIN_HEADER_VERSION_OFFSET = 0x22C
CANDIDATE_VERSION = 1373
RESTORE_VERSION = 1374
EXPECTED_HWID = 3076


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False))).replace("\\", "/")


def _reject_remote_device_or_d(path: Path) -> None:
    raw = str(path).replace("/", "\\")
    lowered = raw.lower()
    if lowered.startswith(("\\\\", "\\\\?\\", "\\\\.\\")):
        raise ValueError("remote and device paths are forbidden")
    resolved = path.resolve(strict=False)
    if resolved.drive.lower() == "d:":
        raise ValueError("D: and every path aliasing D: are forbidden")
    if os.name == "nt" and resolved.drive:
        drive_root = resolved.drive + "\\"
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
        if drive_type != 3:  # DRIVE_FIXED
            raise ValueError("outputs and inputs must remain on a fixed local volume")


def _reject_reparse_chain(path: Path) -> None:
    current = path if path.exists() else path.parent
    while True:
        if current.exists():
            stat = current.lstat()
            attributes = getattr(stat, "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise ValueError(f"reparse points and symlinks are forbidden: {current}")
        if current.parent == current:
            break
        current = current.parent


def _reject_hardlink(path: Path) -> None:
    if path.exists() and path.is_file() and path.stat().st_nlink != 1:
        raise ValueError(f"hardlinked files are forbidden: {path}")


def validate_pinned_file(
    path: Path, *, expected_sha256: str, expected_size: int | None = None
) -> dict[str, Any]:
    _reject_remote_device_or_d(path)
    _reject_reparse_chain(path)
    if not path.is_file():
        raise ValueError(f"pinned input is absent: {path}")
    _reject_hardlink(path)
    data = path.read_bytes()
    if expected_size is not None and len(data) != expected_size:
        raise ValueError(f"pinned input size mismatch: {path}")
    digest = sha256(data)
    if digest != expected_sha256:
        raise ValueError(f"pinned input SHA-256 mismatch: {path}")
    return {"path": str(path), "size": len(data), "sha256": digest}


def _require_exact_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise ValueError(f"{label} fields do not match the pinned schema")


def validate_decision_document(decision: dict[str, Any]) -> None:
    _require_exact_keys(
        decision,
        {
            "schema_version",
            "decision",
            "offline_quarantine_construction_allowed",
            "packaging_allowed",
            "live_staging_allowed",
            "semantic_inventory_complete",
            "known_structure_overlap",
            "device",
            "containment",
            "inputs",
            "review_evidence",
            "target_segments",
            "restrictions",
        },
        "decision",
    )
    expected_scalars = {
        "schema_version": 1,
        "decision": "OFFLINE_QUARANTINE_CONSTRUCTION_ALLOWED",
        "offline_quarantine_construction_allowed": True,
        "packaging_allowed": False,
        "live_staging_allowed": False,
        "semantic_inventory_complete": False,
        "known_structure_overlap": "none_observed",
    }
    if any(decision[key] != value for key, value in expected_scalars.items()):
        raise ValueError("offline construction policy does not match the pinned decision")
    if decision["device"] != {
        "model": "Garmin Forerunner 245 non-Music",
        "hwid": EXPECTED_HWID,
        "official_version": 1370,
        "candidate_version": CANDIDATE_VERSION,
        "restore_version": RESTORE_VERSION,
    }:
        raise ValueError("device, HWID, or version ordering does not match the decision")
    containment = decision["containment"]
    _require_exact_keys(
        containment,
        {"resolved_output_root", "required_suffix", "forbidden_destinations"},
        "containment",
    )
    if (
        Path(containment["resolved_output_root"]).resolve()
        != EXACT_QUARANTINE_ROOT.resolve()
        or containment["required_suffix"] != REQUIRED_SUFFIX
        or containment["forbidden_destinations"]
        != [
            "removable volumes",
            "device paths",
            "remote paths",
            "Garmin software directories",
            "updater-visible directories",
        ]
    ):
        raise ValueError("decision containment does not match the exact local quarantine")
    if set(decision["inputs"]) != {
        "official_gcd",
        "official_main",
        "official_helper",
        "placement",
        "target_manifest",
        "emulator_source",
        "emulator_test",
        "emulation_report",
    }:
        raise ValueError("decision input inventory is incomplete or unexpected")
    if set(decision["review_evidence"]) != {
        "design_spec",
        "offline_addendum",
        "task_3_review",
        "independent_allocation_review",
        "metadata_overlap_review",
        "cross_version_interval_review",
        "target_report",
        "target_review",
        "offline_package_gate_review",
    }:
        raise ValueError("decision review inventory is incomplete or unexpected")
    if set(decision["target_segments"]) != {"hook", "primary", "secondary"}:
        raise ValueError("decision target segment inventory is incomplete or unexpected")
    expected_segments = {
        "hook": (HOOK_VA, 4, None),
        "primary": (PRIMARY_VA, 794, PRIMARY_ALLOCATION),
        "secondary": (SECONDARY_VA, 2044, SECONDARY_ALLOCATION),
    }
    for name, (start, size, allocation) in expected_segments.items():
        item = decision["target_segments"][name]
        if item.get("runtime_start") != start or item.get("sha256") is None:
            raise ValueError(f"{name} segment address or hash is not pinned")
        actual_size = item.get("size", item.get("compiled_size"))
        if actual_size != size:
            raise ValueError(f"{name} segment size does not match the decision")
        if allocation is not None and item.get("allocation_size") != allocation:
            raise ValueError(f"{name} allocation size does not match the decision")
    if not isinstance(decision["restrictions"], list) or len(decision["restrictions"]) != 4:
        raise ValueError("decision restrictions are incomplete")


def _repo_path(repo_root: Path, relative: str) -> Path:
    path = repo_root / relative
    _reject_remote_device_or_d(path)
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(repo_root.resolve(strict=True))
    except ValueError as error:
        raise ValueError(f"pinned path escapes repository: {relative}") from error
    return resolved


def load_and_validate_decision(repo_root: Path, decision_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    if _normalized(repo_root) != _normalized(REPOSITORY_ROOT):
        raise ValueError("repository root is not the exact approved local root")
    _reject_remote_device_or_d(decision_path)
    _reject_reparse_chain(decision_path)
    _reject_hardlink(decision_path)
    raw = decision_path.read_bytes()
    digest = sha256(raw)
    if digest != DECISION_SHA256:
        raise ValueError("decision SHA-256 does not match the exact approved decision")
    expected_decision = (repo_root / DECISION_RELATIVE_PATH).resolve(strict=True)
    if decision_path.resolve(strict=True) != expected_decision:
        raise ValueError("decision path is not the exact approved decision artifact")
    decision = json.loads(raw)
    validate_decision_document(decision)

    validated_files: dict[str, dict[str, Any]] = {}
    groups = ("inputs", "review_evidence", "target_segments")
    for group in groups:
        for name, item in decision[group].items():
            if set(item) - {
                "path",
                "size",
                "compiled_size",
                "allocation_size",
                "runtime_start",
                "sha256",
            }:
                raise ValueError(f"unexpected fields in {group}.{name}")
            if "path" not in item or "sha256" not in item:
                raise ValueError(f"{group}.{name} lacks a pinned path or hash")
            expected_size = item.get("size", item.get("compiled_size"))
            validated_files[f"{group}.{name}"] = validate_pinned_file(
                _repo_path(repo_root, item["path"]),
                expected_sha256=item["sha256"],
                expected_size=expected_size,
            )

    official = _repo_path(repo_root, decision["inputs"]["official_gcd"]["path"]).read_bytes()
    helper, main = build_overlay_candidate._streams(official)
    if sha256(main.decoded) != decision["inputs"]["official_main"]["sha256"]:
        raise ValueError("official GCD main stream does not match the pinned extracted main")
    if sha256(helper.decoded) != decision["inputs"]["official_helper"]["sha256"]:
        raise ValueError("official GCD helper stream does not match the pinned extracted helper")
    if main.decoded != _repo_path(repo_root, decision["inputs"]["official_main"]["path"]).read_bytes():
        raise ValueError("official extracted main is not byte-identical to the GCD stream")
    if helper.decoded != _repo_path(repo_root, decision["inputs"]["official_helper"]["path"]).read_bytes():
        raise ValueError("official extracted helper is not byte-identical to the GCD stream")
    if gcd_inspect._field(main.fields, "hwid") != EXPECTED_HWID:
        raise ValueError("official main HWID is not 3076")

    placement = json.loads(
        _repo_path(repo_root, decision["inputs"]["placement"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        placement.get("link_and_emulate_allowed") is not True
        or placement.get("packaging_allowed") is not False
        or placement.get("offline_interval")
        != {
            "start": "0x001fa400",
            "end": "0x001fabff",
            "length": SECONDARY_ALLOCATION,
            "fill_byte": "0xff",
        }
    ):
        raise ValueError("placement evidence does not preserve the offline-only gate")
    manifest_path = _repo_path(
        repo_root, decision["inputs"]["target_manifest"]["path"]
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("placement_sha256")
        != decision["inputs"]["placement"]["sha256"]
        or manifest.get("link_and_emulate_allowed") is not True
        or manifest.get("packaging_allowed") is not False
    ):
        raise ValueError("target manifest does not match the placement gate")
    for name in ("hook", "primary", "secondary"):
        segment = decision["target_segments"][name]
        manifest_segment = manifest["segments"][name]
        expected_size = segment.get("size", segment.get("compiled_size"))
        if (
            manifest_segment.get("start") != segment["runtime_start"]
            or manifest_segment.get("size") != expected_size
            or manifest_segment.get("sha256") != segment["sha256"]
        ):
            raise ValueError(f"target manifest {name} does not match the decision")
    for manifest_group in ("files", "sources"):
        entries = manifest.get(manifest_group)
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"target manifest {manifest_group} hash inventory is absent")
        for relative, expected_hash in entries.items():
            referenced_path = (
                manifest_path.parent / relative
                if manifest_group == "files"
                else _repo_path(repo_root, relative)
            )
            validated_files[f"target_manifest.{manifest_group}.{relative}"] = (
                validate_pinned_file(
                    referenced_path,
                    expected_sha256=expected_hash,
                )
            )
    emulation = json.loads(
        _repo_path(repo_root, decision["inputs"]["emulation_report"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        emulation.get("status") != "PASS_OFFLINE_ONLY"
        or emulation.get("link_and_emulate_allowed") is not True
        or emulation.get("packaging_allowed") is not False
        or emulation.get("placement_sha256")
        != decision["inputs"]["placement"]["sha256"]
        or emulation.get("cross_segment_branches_all_executed") is not True
    ):
        raise ValueError("emulation report does not satisfy the pinned offline gate")
    return {
        "decision": decision,
        "decision_sha256": digest,
        "validated_files": validated_files,
    }


def _stream(data: bytes, record_id: int) -> Any:
    matches = [
        stream
        for stream in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
        if stream.record_id == record_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one 0x{record_id:04x} stream")
    return matches[0]


def _record_layout(data: bytes) -> list[dict[str, Any]]:
    return [
        {"raw_offset": f"0x{record.offset:x}", "record_id": f"0x{record.record_id:04x}", "length": record.length}
        for record in gcd_inspect.parse_gcd(data).records
    ]


def _diff_ranges(before: bytes, after: bytes) -> list[dict[str, Any]]:
    if len(before) != len(after):
        raise ValueError("compared byte strings have different lengths")
    ranges: list[dict[str, Any]] = []
    index = 0
    while index < len(before):
        if before[index] == after[index]:
            index += 1
            continue
        start = index
        while index < len(before) and before[index] != after[index]:
            index += 1
        ranges.append(
            {"start": f"0x{start:x}", "end": f"0x{index - 1:x}", "length": index - start}
        )
    return ranges


def _changed_offsets(before: bytes, after: bytes) -> set[int]:
    if len(before) != len(after):
        raise ValueError("compared byte strings have different lengths")
    return {index for index, (old, new) in enumerate(zip(before, after)) if old != new}


def _main_raw_locations(data: bytes, stream: Any) -> dict[int, int]:
    locations: dict[int, int] = {}
    records = {record.offset: record for record in gcd_inspect.parse_gcd(data).records}
    decoded_cursor = 0
    for record_offset in stream.record_offsets:
        record = records[record_offset]
        for body_offset in range(record.length):
            locations[record.offset + 4 + body_offset] = decoded_cursor + body_offset
        decoded_cursor += record.length
    return locations


def _checkpoint_body_offsets(data: bytes) -> set[int]:
    return {
        record.offset + 4
        for record in gcd_inspect.parse_gcd(data).records
        if record.record_id == 0x0001 and record.length == 1
    }


def _decoded_raw_offset(data: bytes, stream: Any, decoded_offset: int) -> int:
    records = {record.offset: record for record in gcd_inspect.parse_gcd(data).records}
    cursor = 0
    for record_offset in stream.record_offsets:
        record = records[record_offset]
        if cursor <= decoded_offset < cursor + record.length:
            return record.offset + 4 + decoded_offset - cursor
        cursor += record.length
    raise ValueError(f"decoded offset 0x{decoded_offset:x} is outside the stream")


def _allowed_decoded(offset: int) -> bool:
    return (
        MAIN_HEADER_VERSION_OFFSET <= offset < MAIN_HEADER_VERSION_OFFSET + 2
        or HOOK_OFFSET <= offset < HOOK_OFFSET + 4
        or PRIMARY_OFFSET <= offset < PRIMARY_OFFSET + PRIMARY_ALLOCATION
        or SECONDARY_OFFSET <= offset < SECONDARY_OFFSET + SECONDARY_ALLOCATION
        or offset == 0x4D7FFF
    )


def _construct_candidate(official: bytes, hook: bytes, primary: bytes, secondary: bytes) -> tuple[bytes, dict[str, Any]]:
    official_helper, official_main = build_overlay_candidate._streams(official)
    if len(hook) != 4 or build_overlay_candidate.decode_thumb_bl(HOOK_VA, hook) != PRIMARY_VA:
        raise ValueError("pinned hook does not branch to the primary allocation")
    if len(primary) != 794 or len(secondary) != 2044:
        raise ValueError("compiled target segment lengths do not match the decision")
    official_primary = official_main.decoded[PRIMARY_OFFSET : PRIMARY_OFFSET + PRIMARY_ALLOCATION]
    official_secondary = official_main.decoded[SECONDARY_OFFSET : SECONDARY_OFFSET + SECONDARY_ALLOCATION]
    if official_primary != b"\xff" * PRIMARY_ALLOCATION:
        raise ValueError("official primary allocation is not all 0xff")
    if official_secondary != b"\xff" * SECONDARY_ALLOCATION:
        raise ValueError("official secondary allocation is not all 0xff")

    primary_allocation = bytearray(official_primary)
    primary_allocation[: len(primary)] = primary
    secondary_allocation = bytearray(official_secondary)
    secondary_allocation[: len(secondary)] = secondary
    mutated = build_overlay_candidate._replace_decoded_slice(official, official_main, HOOK_OFFSET, hook)
    mutated_main = _stream(mutated, MAIN_RECORD_ID)
    mutated = build_overlay_candidate._replace_decoded_slice(mutated, mutated_main, PRIMARY_OFFSET, primary_allocation)
    mutated_main = _stream(mutated, MAIN_RECORD_ID)
    mutated = build_overlay_candidate._replace_decoded_slice(mutated, mutated_main, SECONDARY_OFFSET, secondary_allocation)
    mutated_main = _stream(mutated, MAIN_RECORD_ID)
    remainder = sum(mutated_main.decoded) & 0xFF
    old_primary_repair = mutated_main.decoded[PRIMARY_REPAIR_OFFSET]
    new_primary_repair = (old_primary_repair - remainder) & 0xFF
    mutated = build_overlay_candidate._replace_decoded_slice(
        mutated, mutated_main, PRIMARY_REPAIR_OFFSET, bytes([new_primary_repair])
    )
    pre_version = recompute_checkpoints(mutated)
    candidate, version_patch = overlay_version_strategy._set_main_version(
        pre_version, CANDIDATE_VERSION
    )
    return candidate, {
        "primary_additive": {
            "runtime_address": f"0x{PRIMARY_REPAIR_VA:08x}",
            "decoded_offset": f"0x{PRIMARY_REPAIR_OFFSET:x}",
            "old_byte": old_primary_repair,
            "new_byte": new_primary_repair,
        },
        "coherent_version": version_patch,
    }


def _construct_restore(official: bytes) -> tuple[bytes, dict[str, Any]]:
    return overlay_version_strategy._set_main_version(official, RESTORE_VERSION)


def _artifact_report(
    label: str,
    official: bytes,
    output: bytes,
    expected_version: int,
    hook: bytes,
    primary: bytes,
    secondary: bytes,
    repairs: dict[str, Any],
) -> dict[str, Any]:
    official_gcd = gcd_inspect.parse_gcd(official)
    output_gcd = gcd_inspect.parse_gcd(output)
    official_main = _stream(official, MAIN_RECORD_ID)
    output_main = _stream(output, MAIN_RECORD_ID)
    official_helper = _stream(official, HELPER_RECORD_ID)
    output_helper = _stream(output, HELPER_RECORD_ID)
    decoded_changes = _changed_offsets(official_main.decoded, output_main.decoded)
    raw_changes = _changed_offsets(official, output)
    raw_to_decoded = _main_raw_locations(official, official_main)
    checkpoints = _checkpoint_body_offsets(official)
    descriptor_version_offset = overlay_version_strategy._descriptor_field_raw_offset(
        official, MAIN_RECORD_ID, (0x0D, 0x10)
    )
    raw_allowed = all(
        offset == descriptor_version_offset
        or offset in checkpoints
        or (offset in raw_to_decoded and _allowed_decoded(raw_to_decoded[offset]))
        for offset in raw_changes
    )
    validation = full_image_validator.validate_bytes(output, label)
    layout = _record_layout(official)
    output_layout = _record_layout(output)
    is_candidate = label == "candidate"
    expected_restore_main = bytearray(official_main.decoded)
    expected_restore_main[MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2] = expected_version.to_bytes(2, "little")
    expected_restore_main[-1] = output_main.decoded[-1]
    checks = {
        "same_output_size": len(output) == len(official),
        "record_layout_exact_official": output_layout == layout,
        "main_stream_length_exact_official": output_main.declared_length == official_main.declared_length,
        "helper_stream_exact_official": output_helper.decoded == official_helper.decoded,
        "helper_descriptor_exact_official": output_helper.fields == official_helper.fields,
        "hwid_3076": gcd_inspect._field(output_main.fields, "hwid") == EXPECTED_HWID,
        "descriptor_header_version_coherent": (
            output_main.software_version == expected_version
            and int.from_bytes(output_main.decoded[MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2], "little") == expected_version
        ),
        "descriptor_force_field_zero": output_main.erase_flag == 0,
        "decoded_changes_confined_to_exact_allowlist": all(_allowed_decoded(offset) for offset in decoded_changes),
        "raw_changes_confined_to_exact_allowlist": raw_allowed,
        "main_additive_sum_zero": (sum(output_main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": validation["outer_gcd"]["all_prefix_sums_zero_mod_256"],
        "full_image_validator_pass": validation["confirmed_full_image_checks_pass"],
        "hook_exact": (
            output_main.decoded[HOOK_OFFSET : HOOK_OFFSET + 4] == hook
            if is_candidate
            else output_main.decoded[HOOK_OFFSET : HOOK_OFFSET + 4]
            == official_main.decoded[HOOK_OFFSET : HOOK_OFFSET + 4]
        ),
        "primary_segment_or_restore_exact": (
            output_main.decoded[PRIMARY_OFFSET : PRIMARY_OFFSET + len(primary)] == primary
            if is_candidate
            else output_main.decoded[PRIMARY_OFFSET : PRIMARY_OFFSET + PRIMARY_ALLOCATION]
            == official_main.decoded[PRIMARY_OFFSET : PRIMARY_OFFSET + PRIMARY_ALLOCATION]
        ),
        "primary_additive_repair_exact": (
            output_main.decoded[PRIMARY_REPAIR_OFFSET]
            == repairs["primary_additive"]["new_byte"]
            if is_candidate
            else output_main.decoded[PRIMARY_REPAIR_OFFSET]
            == official_main.decoded[PRIMARY_REPAIR_OFFSET]
        ),
        "secondary_segment_or_restore_exact": (
            output_main.decoded[SECONDARY_OFFSET : SECONDARY_OFFSET + len(secondary)] == secondary
            if is_candidate
            else output_main.decoded[SECONDARY_OFFSET : SECONDARY_OFFSET + SECONDARY_ALLOCATION]
            == official_main.decoded[SECONDARY_OFFSET : SECONDARY_OFFSET + SECONDARY_ALLOCATION]
        ),
        "official_padding_or_restore_exact": (
            output_main.decoded[PRIMARY_OFFSET + len(primary) : PRIMARY_REPAIR_OFFSET]
            == official_main.decoded[PRIMARY_OFFSET + len(primary) : PRIMARY_REPAIR_OFFSET]
            and output_main.decoded[SECONDARY_OFFSET + len(secondary) : SECONDARY_OFFSET + SECONDARY_ALLOCATION]
            == official_main.decoded[SECONDARY_OFFSET + len(secondary) : SECONDARY_OFFSET + SECONDARY_ALLOCATION]
            if is_candidate
            else output_main.decoded == bytes(expected_restore_main)
        ),
    }
    return {
        "purpose": (
            "offline-only synthetic 13.73 neural overlay"
            if is_candidate
            else "offline-only synthetic 13.74 wrapper carrying official 13.70 code/resources"
        ),
        "filename": CANDIDATE_FILENAME if is_candidate else RESTORE_FILENAME,
        "size": len(output),
        "sha256": sha256(output),
        "main_stream": {
            "size": len(output_main.decoded),
            "sha256": sha256(output_main.decoded),
            "sum_mod_256": sum(output_main.decoded) & 0xFF,
        },
        "main_descriptor": {
            "hwid": gcd_inspect._field(output_main.fields, "hwid"),
            "software_version": output_main.software_version,
            "header_version": int.from_bytes(
                output_main.decoded[
                    MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
                ],
                "little",
            ),
            "erase_flag": output_main.erase_flag,
        },
        "helper_stream": {
            "size": len(output_helper.decoded),
            "sha256": sha256(output_helper.decoded),
            "byte_exact_official": output_helper.decoded == official_helper.decoded,
            "descriptor_exact_official": output_helper.fields == official_helper.fields,
        },
        "record_layout": output_layout,
        "declared_runtime_regions": [
            {"name": "hook", "start": "0x00009a20", "end": "0x00009a23", "size": 4},
            {"name": "primary", "start": "0x001f6000", "end": "0x001f63ff", "size": 1024},
            {"name": "secondary", "start": "0x001fa400", "end": "0x001fabff", "size": 2048},
        ],
        "changed_range_allowlists": {
            "decoded_main": [
                {"name": "header_version", "start": "0x22c", "end": "0x22d"},
                {"name": "hook", "start": f"0x{HOOK_OFFSET:x}", "end": f"0x{HOOK_OFFSET + 3:x}"},
                {"name": "primary_allocation", "start": f"0x{PRIMARY_OFFSET:x}", "end": f"0x{PRIMARY_OFFSET + PRIMARY_ALLOCATION - 1:x}"},
                {"name": "secondary_allocation", "start": f"0x{SECONDARY_OFFSET:x}", "end": f"0x{SECONDARY_OFFSET + SECONDARY_ALLOCATION - 1:x}"},
                {"name": "final_main_additive_repair", "start": "0x4d7fff", "end": "0x4d7fff"},
            ],
            "raw_gcd": [
                {"name": "descriptor_version", "start": f"0x{descriptor_version_offset:x}", "end": f"0x{descriptor_version_offset + 1:x}"},
                {"name": "header_version", "start": f"0x{_decoded_raw_offset(official, official_main, MAIN_HEADER_VERSION_OFFSET):x}", "end": f"0x{_decoded_raw_offset(official, official_main, MAIN_HEADER_VERSION_OFFSET + 1):x}"},
                {"name": "hook", "start": f"0x{_decoded_raw_offset(official, official_main, HOOK_OFFSET):x}", "end": f"0x{_decoded_raw_offset(official, official_main, HOOK_OFFSET + 3):x}"},
                {"name": "primary_allocation", "start": f"0x{_decoded_raw_offset(official, official_main, PRIMARY_OFFSET):x}", "end": f"0x{_decoded_raw_offset(official, official_main, PRIMARY_OFFSET + PRIMARY_ALLOCATION - 1):x}"},
                {"name": "secondary_allocation", "start": f"0x{_decoded_raw_offset(official, official_main, SECONDARY_OFFSET):x}", "end": f"0x{_decoded_raw_offset(official, official_main, SECONDARY_OFFSET + SECONDARY_ALLOCATION - 1):x}"},
                {"name": "final_main_additive_repair", "start": f"0x{_decoded_raw_offset(official, official_main, 0x4D7FFF):x}", "end": f"0x{_decoded_raw_offset(official, official_main, 0x4D7FFF):x}"},
                *[
                    {"name": "outer_checkpoint", "start": f"0x{offset:x}", "end": f"0x{offset:x}"}
                    for offset in sorted(checkpoints)
                ],
            ],
        },
        "segments": {
            "hook": {"size": len(hook), "sha256": sha256(hook), "exact": checks["hook_exact"]},
            "primary": {"compiled_size": len(primary), "allocation_size": PRIMARY_ALLOCATION, "sha256": sha256(primary), "exact": checks["primary_segment_or_restore_exact"]},
            "secondary": {"compiled_size": len(secondary), "allocation_size": SECONDARY_ALLOCATION, "sha256": sha256(secondary), "exact": checks["secondary_segment_or_restore_exact"]},
        },
        "repairs": repairs,
        "decoded_changed_byte_count": len(decoded_changes),
        "decoded_changed_ranges": _diff_ranges(official_main.decoded, output_main.decoded),
        "raw_changed_byte_count": len(raw_changes),
        "raw_changed_ranges": _diff_ranges(official, output),
        "outer_checkpoint_repair_offsets": [
            f"0x{offset:x}" for offset in sorted(raw_changes & checkpoints)
        ],
        "full_image_validation": validation,
        "checks": checks,
    }


def construct_pair(repo_root: Path, decision_path: Path) -> tuple[bytes, bytes, dict[str, Any]]:
    validated = load_and_validate_decision(repo_root, decision_path)
    decision = validated["decision"]
    official = _repo_path(repo_root, decision["inputs"]["official_gcd"]["path"]).read_bytes()
    hook = _repo_path(repo_root, decision["target_segments"]["hook"]["path"]).read_bytes()
    primary = _repo_path(repo_root, decision["target_segments"]["primary"]["path"]).read_bytes()
    secondary = _repo_path(repo_root, decision["target_segments"]["secondary"]["path"]).read_bytes()
    candidate, candidate_repairs = _construct_candidate(official, hook, primary, secondary)
    restore, restore_version_patch = _construct_restore(official)
    candidate_report = _artifact_report(
        "candidate", official, candidate, CANDIDATE_VERSION, hook, primary, secondary, candidate_repairs
    )
    restore_report = _artifact_report(
        "restore",
        official,
        restore,
        RESTORE_VERSION,
        hook,
        primary,
        secondary,
        {"coherent_version": restore_version_patch},
    )
    if not all(candidate_report["checks"].values()):
        raise AssertionError(f"candidate strict checks failed: {candidate_report['checks']}")
    if not all(restore_report["checks"].values()):
        raise AssertionError(f"restore strict checks failed: {restore_report['checks']}")
    report = {
        "schema_version": 1,
        "tool": "tools/garmin-firmware/neural_overlay_version_strategy.py",
        "verdict": "PASS_OFFLINE_CONSTRUCTION",
        "decision_sha256": validated["decision_sha256"],
        "validated_inputs": validated["validated_files"],
        "policy": {
            "offline_quarantine_construction_allowed": True,
            "packaging_allowed": False,
            "live_staging_allowed": False,
            "semantic_inventory_complete": False,
            "feasibility": "YELLOW",
        },
        "candidate": candidate_report,
        "restore": restore_report,
        "limitations": [
            "Successful construction proves only exact offline bytes for this experiment.",
            "The synthetic versions are not Garmin releases and do not authorize staging or installation.",
            "The restore depends on GarminOS and normal USB update service still booting.",
            "No Forerunner 245 nonboot recovery path is known.",
        ],
    }
    return candidate, restore, report


def verify_exact(
    repo_root: Path, decision_path: Path, candidate: bytes, restore: bytes
) -> dict[str, Any]:
    expected_candidate, expected_restore, build_report = construct_pair(repo_root, decision_path)
    checks = {
        "candidate_byte_exact_reconstruction": candidate == expected_candidate,
        "restore_byte_exact_reconstruction": restore == expected_restore,
        "candidate_sha256_exact_reconstruction": sha256(candidate) == sha256(expected_candidate),
        "restore_sha256_exact_reconstruction": sha256(restore) == sha256(expected_restore),
        "candidate_full_image_validator_pass": full_image_validator.validate_bytes(candidate, CANDIDATE_FILENAME)["confirmed_full_image_checks_pass"],
        "restore_full_image_validator_pass": full_image_validator.validate_bytes(restore, RESTORE_FILENAME)["confirmed_full_image_checks_pass"],
        "packaging_allowed_remains_false": build_report["policy"]["packaging_allowed"] is False,
        "live_staging_allowed_remains_false": build_report["policy"]["live_staging_allowed"] is False,
    }
    return {
        "schema_version": 1,
        "profile": "flyos-neural-overlay-exact-1373-restore-1374",
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "expected": {
            "candidate": {"filename": CANDIDATE_FILENAME, "size": len(expected_candidate), "sha256": sha256(expected_candidate)},
            "restore": {"filename": RESTORE_FILENAME, "size": len(expected_restore), "sha256": sha256(expected_restore)},
        },
        "actual": {
            "candidate": {"size": len(candidate), "sha256": sha256(candidate)},
            "restore": {"size": len(restore), "sha256": sha256(restore)},
        },
        "build_evidence": build_report,
        "live_staging_allowed": False,
    }


def validate_output_target(path: Path, root: Path, input_paths: Iterable[Path]) -> None:
    _reject_remote_device_or_d(path)
    _reject_remote_device_or_d(root)
    _reject_reparse_chain(root)
    _reject_reparse_chain(path)
    resolved_root = root.resolve(strict=True)
    resolved_path = path.resolve(strict=False)
    if resolved_path.parent != resolved_root:
        raise ValueError("output must be directly beneath the exact quarantine root")
    if path.name not in {CANDIDATE_FILENAME, RESTORE_FILENAME}:
        raise ValueError("output filename is not one of the exact approved artifacts")
    if not path.name.endswith(REQUIRED_SUFFIX):
        raise ValueError(f"output must end with {REQUIRED_SUFFIX}")
    if path.exists():
        _reject_hardlink(path)
        raise ValueError(f"output already exists; overwrite is forbidden: {path}")
    for input_path in input_paths:
        if resolved_path == input_path.resolve(strict=False):
            raise ValueError("output aliases an input path")
        if input_path.exists() and path.exists() and os.path.samefile(path, input_path):
            raise ValueError("output has input-output file identity")


def _validate_exact_roots(repo_root: Path) -> tuple[Path, Path]:
    quarantine = (repo_root / "artifacts/firmware/quarantine").resolve(strict=True)
    analysis = (repo_root / "artifacts/firmware/analysis").resolve(strict=True)
    if _normalized(quarantine) != _normalized(EXACT_QUARANTINE_ROOT):
        raise ValueError("resolved quarantine root is not the exact approved root")
    if _normalized(analysis) != _normalized(EXACT_ANALYSIS_ROOT):
        raise ValueError("resolved analysis root is not the exact approved root")
    _reject_reparse_chain(quarantine)
    _reject_reparse_chain(analysis)
    return quarantine, analysis


def write_transaction(
    outputs: Iterable[tuple[Path, bytes]],
    *,
    _open_file: Any | None = None,
    _fsync: Any | None = None,
    _unlink: Any | None = None,
) -> None:
    """Create every output exclusively, removing all files created on failure."""
    open_file = _open_file or (lambda path: path.open("xb"))
    fsync = _fsync or os.fsync
    unlink = _unlink or (lambda path: path.unlink())
    created: list[Path] = []
    try:
        for path, data in outputs:
            handle = open_file(path)
            created.append(path)
            with handle:
                written = handle.write(data)
                if written != len(data):
                    raise OSError(
                        f"short write for {path}: wrote {written} of {len(data)} bytes"
                    )
                handle.flush()
                fsync(handle.fileno())
    except BaseException as original_error:
        cleanup_errors: list[str] = []
        for path in reversed(created):
            try:
                unlink(path)
            except OSError as cleanup_error:
                cleanup_errors.append(f"{path}: {cleanup_error}")
        remaining = [str(path) for path in created if path.exists()]
        if cleanup_errors or remaining:
            details = "; ".join(cleanup_errors + [f"still exists: {path}" for path in remaining])
            raise RuntimeError(f"transaction cleanup could not be confirmed: {details}") from original_error
        raise


def _write_new(path: Path, data: bytes) -> None:
    write_transaction(((path, data),))


def replace_reports_transaction(outputs: Iterable[tuple[Path, bytes]]) -> None:
    """Replace report files with rollback, without touching package artifacts."""
    materialized = list(outputs)
    temporary = [
        (path.with_name(f".{path.name}.refresh.tmp"), data)
        for path, data in materialized
    ]
    backups = [
        (path, path.with_name(f".{path.name}.refresh.backup"))
        for path, _data in materialized
    ]
    for temporary_path, _data in temporary:
        if temporary_path.exists():
            raise ValueError(f"stale refresh temporary file exists: {temporary_path}")
    for _path, backup_path in backups:
        if backup_path.exists():
            raise ValueError(f"stale refresh backup file exists: {backup_path}")

    write_transaction(temporary)
    moved_backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for path, backup_path in backups:
            if path.exists():
                _reject_reparse_chain(path)
                _reject_hardlink(path)
                os.replace(path, backup_path)
                moved_backups.append((path, backup_path))
        for (temporary_path, _data), (path, _backup_path) in zip(
            temporary, backups, strict=True
        ):
            os.replace(temporary_path, path)
            installed.append(path)
    except BaseException as original_error:
        cleanup_errors: list[str] = []
        for path in reversed(installed):
            try:
                path.unlink()
            except OSError as cleanup_error:
                cleanup_errors.append(f"{path}: {cleanup_error}")
        for path, backup_path in reversed(moved_backups):
            try:
                os.replace(backup_path, path)
            except OSError as cleanup_error:
                cleanup_errors.append(f"{backup_path}: {cleanup_error}")
        for temporary_path, _data in temporary:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError as cleanup_error:
                    cleanup_errors.append(f"{temporary_path}: {cleanup_error}")
        if cleanup_errors:
            raise RuntimeError(
                "report refresh rollback could not be confirmed: "
                + "; ".join(cleanup_errors)
            ) from original_error
        raise
    else:
        cleanup_errors = []
        for _path, backup_path in moved_backups:
            try:
                backup_path.unlink()
            except OSError as cleanup_error:
                cleanup_errors.append(f"{backup_path}: {cleanup_error}")
        if cleanup_errors:
            raise RuntimeError(
                "report refresh backup cleanup could not be confirmed: "
                + "; ".join(cleanup_errors)
            )


def refresh_attestation_reports(repo_root: Path, decision_path: Path) -> dict[str, Any]:
    """Regenerate build and strict reports from existing immutable packages."""
    repo_root = repo_root.resolve(strict=True)
    quarantine, analysis = _validate_exact_roots(repo_root)
    candidate_path = quarantine / CANDIDATE_FILENAME
    restore_path = quarantine / RESTORE_FILENAME
    report_paths = (
        analysis / BUILD_REPORT_FILENAME,
        analysis / STRICT_REPORT_FILENAME,
    )
    package_paths = (candidate_path, restore_path)
    package_before: dict[str, dict[str, Any]] = {}
    package_bytes: list[bytes] = []
    for path in package_paths:
        _reject_remote_device_or_d(path)
        _reject_reparse_chain(path)
        _reject_hardlink(path)
        if not path.is_file():
            raise ValueError(f"expected package is absent: {path}")
        data = path.read_bytes()
        stat = path.stat()
        package_bytes.append(data)
        package_before[path.name] = {
            "size": len(data),
            "sha256": sha256(data),
            "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns,
        }

    expected_candidate, expected_restore, build_report = construct_pair(
        repo_root, decision_path
    )
    candidate, restore = package_bytes
    if candidate != expected_candidate or restore != expected_restore:
        raise ValueError("existing packages do not exactly match amended decision")
    strict_report = verify_exact(repo_root, decision_path, candidate, restore)
    if strict_report["verdict"] != "PASS":
        raise AssertionError("existing packages fail amended exact verification")

    package_after = {}
    for path, original in zip(package_paths, package_bytes, strict=True):
        current = path.read_bytes()
        stat = path.stat()
        package_after[path.name] = {
            "size": len(current),
            "sha256": sha256(current),
            "mtime_ns": stat.st_mtime_ns,
            "ctime_ns": stat.st_ctime_ns,
        }
        if current != original or package_after[path.name] != package_before[path.name]:
            raise RuntimeError("package bytes or metadata changed during report refresh")

    attestation = {
        "mode": "existing-package-report-only-refresh",
        "package_files_opened_read_only": True,
        "package_bytes_and_metadata_unchanged": True,
        "package_snapshots": {
            name: {"size": item["size"], "sha256": item["sha256"]}
            for name, item in package_after.items()
        },
    }
    build_report["outputs"] = {
        "candidate": str(candidate_path),
        "restore": str(restore_path),
        "report": str(report_paths[0]),
    }
    build_report["attestation_refresh"] = attestation
    strict_report["build_evidence"] = build_report
    strict_report["attestation_refresh"] = attestation
    replace_reports_transaction(
        (
            (report_paths[0], (json.dumps(build_report, indent=2) + "\n").encode("utf-8")),
            (report_paths[1], (json.dumps(strict_report, indent=2) + "\n").encode("utf-8")),
        )
    )
    return {
        "verdict": "PASS",
        "candidate_sha256": package_after[CANDIDATE_FILENAME]["sha256"],
        "restore_sha256": package_after[RESTORE_FILENAME]["sha256"],
        "package_bytes_and_metadata_unchanged": True,
        "build_report_sha256": sha256(report_paths[0].read_bytes()),
        "strict_report_sha256": sha256(report_paths[1].read_bytes()),
    }


def build_to_quarantine(repo_root: Path, decision_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    quarantine, analysis = _validate_exact_roots(repo_root)
    candidate_path = quarantine / CANDIDATE_FILENAME
    restore_path = quarantine / RESTORE_FILENAME
    report_path = analysis / BUILD_REPORT_FILENAME
    validated = load_and_validate_decision(repo_root, decision_path)
    input_paths = [
        _repo_path(repo_root, item["path"])
        for group in ("inputs", "review_evidence", "target_segments")
        for item in validated["decision"][group].values()
    ]
    validate_output_target(candidate_path, quarantine, input_paths)
    validate_output_target(restore_path, quarantine, input_paths)
    if report_path.exists():
        raise ValueError("build report already exists; overwrite is forbidden")
    candidate, restore, report = construct_pair(repo_root, decision_path)
    exact = verify_exact(repo_root, decision_path, candidate, restore)
    if exact["verdict"] != "PASS":
        raise AssertionError("in-memory exact verification failed before output creation")
    report["outputs"] = {
        "candidate": str(candidate_path),
        "restore": str(restore_path),
        "report": str(report_path),
    }
    write_transaction(
        (
            (candidate_path, candidate),
            (restore_path, restore),
            (report_path, (json.dumps(report, indent=2) + "\n").encode("utf-8")),
        )
    )
    return report


def verify_written_pair(repo_root: Path, decision_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    quarantine, analysis = _validate_exact_roots(repo_root)
    candidate_path = quarantine / CANDIDATE_FILENAME
    restore_path = quarantine / RESTORE_FILENAME
    report_path = analysis / STRICT_REPORT_FILENAME
    for path in (candidate_path, restore_path):
        _reject_remote_device_or_d(path)
        _reject_reparse_chain(path)
        _reject_hardlink(path)
        if not path.is_file():
            raise ValueError(f"expected package is absent: {path}")
    candidate = candidate_path.read_bytes()
    restore = restore_path.read_bytes()
    report = verify_exact(repo_root, decision_path, candidate, restore)
    if report_path.exists():
        raise ValueError("strict report already exists; overwrite is forbidden")
    _write_new(report_path, (json.dumps(report, indent=2) + "\n").encode("utf-8"))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify", "refresh"))
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--decision", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    decision_path = args.decision or repo_root / DECISION_RELATIVE_PATH
    try:
        if args.command == "build":
            report = build_to_quarantine(repo_root, decision_path)
            result = {
                "verdict": report["verdict"],
                "candidate_sha256": report["candidate"]["sha256"],
                "restore_sha256": report["restore"]["sha256"],
            }
        elif args.command == "verify":
            report = verify_written_pair(repo_root, decision_path)
            result = {
                "verdict": report["verdict"],
                "candidate_sha256": report["actual"]["candidate"]["sha256"],
                "restore_sha256": report["actual"]["restore"]["sha256"],
            }
        else:
            result = refresh_attestation_reports(repo_root, decision_path)
            report = result
    except (OSError, ValueError, KeyError, AssertionError, json.JSONDecodeError, gcd_inspect.GcdFormatError) as error:
        parser.error(str(error))
    print(json.dumps(result, sort_keys=True))
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
