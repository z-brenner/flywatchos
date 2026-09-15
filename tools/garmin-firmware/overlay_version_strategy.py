#!/usr/bin/env python3
"""Build and strictly verify offline FR245 overlay/restore force-field packages.

This tool only accepts the pinned official non-Music 13.70 GCD as its source.
Outputs must remain under ``artifacts/firmware/quarantine`` and retain the
analysis-only suffix.  It never accesses a mounted device.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import build_overlay_candidate  # noqa: E402
import full_image_validator  # noqa: E402
import gcd_inspect  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


OFFICIAL_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
OFFICIAL_MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
OFFICIAL_HELPER_SHA256 = "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46"
OVERLAY_PAYLOAD_SHA256 = "62ea46c67c565f571789d1437de318de785d90a2fef0a79d702b6d2ba6b3dee1"
OVERLAY_HOOK_SHA256 = "49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362"

# Filled only with hashes derived from the pinned official GCD and pinned
# overlay build.  The verifier also reconstructs every output byte.
FORCE_RESTORE_SHA256 = "e50edc0f8cd92e61e31fd68287c2ae80860f7c32ab287118e285b57ab7d86429"
FORCE_OVERLAY_SHA256 = "78d01c1e28d305f2e5195ffdb39507ebcd1ddd7f289a3c507772f6de14e0a9e3"
FORCE_OVERLAY_MAIN_SHA256 = "5a96be19bcb96080cab1f47fee57ea663bb93b0ee92197edc49229bcd93950d8"
FORWARD_OVERLAY_SHA256 = "1f7de5ec5ea224ef337c3934e0f7ebc1445f0c6c7b8cb4201180cbeb1772a469"
FORWARD_OVERLAY_MAIN_SHA256 = "5cc69a9045a26996ecabf85cf568d1f46e793ec1aa9a5e2eeb4034a35d39da71"
FORWARD_RESTORE_SHA256 = "f0a6b316cab5f941125cbe896e6e260196bc0ba4a02f5b475fa55de241522eb1"
FORWARD_RESTORE_MAIN_SHA256 = "cc3a416039ebee24af7b77f9af71877d5bb44f6272d1cd75f22695e64c9a1960"

MAIN_RECORD_ID = 0x02BD
HELPER_RECORD_ID = 0x0505
FIELD_0B = (0x0B, 0x00)
EXPECTED_MAIN_FORCE_RAW_OFFSET = 0xA152
EXPECTED_MAIN_VERSION_RAW_OFFSET = 0xA160
MAIN_HEADER_VERSION_OFFSET = 0x22C
REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stream(data: bytes, record_id: int) -> Any:
    matches = [
        item
        for item in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
        if item.record_id == record_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one 0x{record_id:04x} stream")
    return matches[0]


def _descriptor_field_raw_offset(data: bytes, target_record_id: int, field: tuple[int, int]) -> int:
    gcd = gcd_inspect.parse_gcd(data)
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
            if (field_id, field_type) == field:
                return record.offset + 4 + cursor
            cursor += gcd_inspect.FIELD_SIZES[field_type]
    raise ValueError(f"descriptor field {field!r} for 0x{target_record_id:04x} not found")


def _changed_offsets(before: bytes, after: bytes) -> list[int]:
    if len(before) != len(after):
        raise ValueError("candidate changed package length")
    return [i for i, (old, new) in enumerate(zip(before, after)) if old != new]


def _validate_common(official: bytes, candidate: bytes) -> dict[str, Any]:
    official_main = _stream(official, MAIN_RECORD_ID)
    official_helper = _stream(official, HELPER_RECORD_ID)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    candidate_helper = _stream(candidate, HELPER_RECORD_ID)
    validation = full_image_validator.validate_bytes(candidate, "force-field-candidate")
    return {
        "same_size": len(candidate) == len(official),
        "same_record_layout": [
            (r.offset, r.record_id, r.length) for r in gcd_inspect.parse_gcd(candidate).records
        ] == [
            (r.offset, r.record_id, r.length) for r in gcd_inspect.parse_gcd(official).records
        ],
        "helper_payload_exact_official": candidate_helper.decoded == official_helper.decoded,
        "helper_descriptor_exact_official": candidate_helper.fields == official_helper.fields,
        "main_version_descriptor_1370": candidate_main.software_version == 1370,
        "main_version_header_1370": int.from_bytes(candidate_main.decoded[0x22C:0x22E], "little") == 1370,
        "main_field_0x0b_is_one": candidate_main.erase_flag == 1,
        "main_sum_mod_256_zero": (sum(candidate_main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": validation["outer_gcd"]["all_prefix_sums_zero_mod_256"],
        "full_image_checks_pass": validation["confirmed_full_image_checks_pass"],
    }


def _set_main_force_field(source: bytes) -> tuple[bytes, int]:
    raw_offset = _descriptor_field_raw_offset(source, MAIN_RECORD_ID, FIELD_0B)
    if raw_offset != EXPECTED_MAIN_FORCE_RAW_OFFSET:
        raise ValueError(f"unexpected main field 0x0b offset 0x{raw_offset:x}")
    if source[raw_offset] != 0:
        raise ValueError("source main field 0x0b is not zero")
    mutable = bytearray(source)
    mutable[raw_offset] = 1
    return recompute_checkpoints(bytes(mutable)), raw_offset


def _set_main_version(source: bytes, version: int) -> tuple[bytes, dict[str, Any]]:
    """Set coherent descriptor/header versions and repair known additive sums."""
    if not 0 <= version <= 0xFFFF:
        raise ValueError("version is outside uint16 range")
    main = _stream(source, MAIN_RECORD_ID)
    raw_offset = _descriptor_field_raw_offset(source, MAIN_RECORD_ID, (0x0D, 0x10))
    if raw_offset != EXPECTED_MAIN_VERSION_RAW_OFFSET:
        raise ValueError(f"unexpected main version field offset 0x{raw_offset:x}")
    if main.software_version != 1370:
        raise ValueError("source descriptor is not 13.70")
    if int.from_bytes(main.decoded[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2], "little") != 1370:
        raise ValueError("source main header is not 13.70")

    encoded = version.to_bytes(2, "little")
    mutable = bytearray(source)
    mutable[raw_offset:raw_offset + 2] = encoded
    mutated = build_overlay_candidate._replace_decoded_slice(
        bytes(mutable), main, MAIN_HEADER_VERSION_OFFSET, encoded
    )
    interim_main = _stream(mutated, MAIN_RECORD_ID)
    checksum_offset = interim_main.declared_length - 1
    old_checksum = interim_main.decoded[checksum_offset]
    remainder = sum(interim_main.decoded) & 0xFF
    new_checksum = (old_checksum - remainder) & 0xFF
    mutated = build_overlay_candidate._replace_decoded_slice(
        mutated, interim_main, checksum_offset, bytes([new_checksum])
    )
    result = recompute_checkpoints(mutated)
    result_main = _stream(result, MAIN_RECORD_ID)
    if result_main.software_version != version:
        raise AssertionError("descriptor version repair failed")
    if int.from_bytes(result_main.decoded[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2], "little") != version:
        raise AssertionError("header version repair failed")
    if sum(result_main.decoded) & 0xFF:
        raise AssertionError("main additive repair failed")
    return result, {
        "descriptor_raw_offset": f"0x{raw_offset:x}",
        "header_decoded_offset": f"0x{MAIN_HEADER_VERSION_OFFSET:x}",
        "checksum_decoded_offset": f"0x{checksum_offset:x}",
        "old_checksum_byte": old_checksum,
        "new_checksum_byte": new_checksum,
        "version": version,
    }


def _runtime_identity_1370(main: Any) -> dict[str, bool]:
    return {
        "system_tuple_at_0x370f06": main.decoded[0x370F06:0x370F08] == b"\x5a\x05",
        "display_string_at_0x370f34": main.decoded[0x370F34:0x370F3C] == b" V13.70\x00",
        "product_string_at_0x384398": main.decoded[0x384398:0x38439C] == b"1370",
        "event_movw_at_0x1ca6bc": main.decoded[0x1CA6BC:0x1CA6C0] == bytes.fromhex("40f25a52"),
    }


def build_forward_restore(official: bytes) -> tuple[bytes, dict[str, Any]]:
    """Wrap official 13.70 executable bytes in coherent 13.72 admission metadata."""
    if sha256(official) != OFFICIAL_SHA256:
        raise ValueError("source is not pinned official non-Music 13.70")
    candidate, version_patch = _set_main_version(official, 1372)
    original_main = _stream(official, MAIN_RECORD_ID)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    original_helper = _stream(official, HELPER_RECORD_ID)
    candidate_helper = _stream(candidate, HELPER_RECORD_ID)
    expected_main = bytearray(original_main.decoded)
    expected_main[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2] = (1372).to_bytes(2, "little")
    expected_main[-1] = candidate_main.decoded[-1]
    checks = {
        "descriptor_and_header_coherent_1372": (
            candidate_main.software_version == 1372
            and int.from_bytes(candidate_main.decoded[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2], "little") == 1372
        ),
        "official_runtime_identity_mirrors_unchanged": all(_runtime_identity_1370(candidate_main).values()),
        "main_exact_except_header_and_additive_repair": candidate_main.decoded == bytes(expected_main),
        "helper_payload_exact_official": candidate_helper.decoded == original_helper.decoded,
        "helper_descriptor_exact_official": candidate_helper.fields == original_helper.fields,
        "main_sum_mod_256_zero": (sum(candidate_main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": all(
            x["valid"] for x in gcd_inspect._checkpoint_results(gcd_inspect.parse_gcd(candidate))
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"forward-restore checks failed: {checks}")
    return candidate, {
        "purpose": "forward 13.72 wrapper carrying official 13.70 executable payload",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(candidate_helper.decoded),
        "version_patch": version_patch,
        "runtime_identity": _runtime_identity_1370(candidate_main),
        "raw_changed_offsets": [f"0x{x:x}" for x in _changed_offsets(official, candidate)],
        "checks": checks,
    }


def build_forward_overlay(
    official: bytes, hook: bytes, payload: bytes, cave_xref_report: str
) -> tuple[bytes, dict[str, Any]]:
    """Build coherent 13.71 overlay for normal admission from reported 13.70."""
    if sha256(hook) != OVERLAY_HOOK_SHA256:
        raise ValueError("hook is not the pinned overlay hook")
    if sha256(payload) != OVERLAY_PAYLOAD_SHA256:
        raise ValueError("payload is not the pinned overlay payload")
    plain_overlay, plain_report = build_overlay_candidate.build_candidate(
        official, hook, payload, cave_xref_report
    )
    candidate, version_patch = _set_main_version(plain_overlay, 1371)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    candidate_helper = _stream(candidate, HELPER_RECORD_ID)
    checks = {
        "descriptor_and_header_coherent_1371": (
            candidate_main.software_version == 1371
            and int.from_bytes(candidate_main.decoded[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2], "little") == 1371
        ),
        "normal_forward_from_observed_1370": candidate_main.software_version > 1370,
        "official_runtime_identity_mirrors_unchanged": all(_runtime_identity_1370(candidate_main).values()),
        "helper_payload_exact_official": sha256(candidate_helper.decoded) == OFFICIAL_HELPER_SHA256,
        "main_sum_mod_256_zero": (sum(candidate_main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": all(
            x["valid"] for x in gcd_inspect._checkpoint_results(gcd_inspect.parse_gcd(candidate))
        ),
        "hook_exact": candidate_main.decoded[
            build_overlay_candidate.HOOK_OFFSET:build_overlay_candidate.HOOK_OFFSET + len(hook)
        ] == hook,
        "payload_exact": candidate_main.decoded[
            build_overlay_candidate.OVERLAY_OFFSET:build_overlay_candidate.OVERLAY_OFFSET + len(payload)
        ] == payload,
    }
    if not all(checks.values()):
        raise AssertionError(f"forward-overlay checks failed: {checks}")
    return candidate, {
        "purpose": "normal-forward 13.71 FR245 scientific-fly executable overlay",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "plain_overlay_sha256": sha256(plain_overlay),
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(candidate_helper.decoded),
        "version_patch": version_patch,
        "runtime_identity": _runtime_identity_1370(candidate_main),
        "raw_changed_byte_count": len(_changed_offsets(official, candidate)),
        "raw_changed_offsets": [f"0x{x:x}" for x in _changed_offsets(official, candidate)],
        "overlay": plain_report["patch"],
        "checks": checks,
    }


def verify_forward_exact(
    official: bytes,
    forward_restore: bytes,
    forward_overlay: bytes,
    hook: bytes,
    payload: bytes,
    cave_xref_report: str,
) -> dict[str, Any]:
    expected_restore, restore_report = build_forward_restore(official)
    expected_overlay, overlay_report = build_forward_overlay(
        official, hook, payload, cave_xref_report
    )
    checks = {
        "official_sha256_pinned": sha256(official) == OFFICIAL_SHA256,
        "forward_restore_byte_exact_reconstruction": forward_restore == expected_restore,
        "forward_restore_sha256_pinned": sha256(forward_restore) == FORWARD_RESTORE_SHA256,
        "forward_restore_main_sha256_pinned": sha256(_stream(forward_restore, MAIN_RECORD_ID).decoded) == FORWARD_RESTORE_MAIN_SHA256,
        "forward_overlay_byte_exact_reconstruction": forward_overlay == expected_overlay,
        "forward_overlay_sha256_pinned": sha256(forward_overlay) == FORWARD_OVERLAY_SHA256,
        "forward_overlay_main_sha256_pinned": sha256(_stream(forward_overlay, MAIN_RECORD_ID).decoded) == FORWARD_OVERLAY_MAIN_SHA256,
    }
    return {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "artifacts": {"forward_restore": restore_report, "forward_overlay": overlay_report},
        "limitations": [
            "The 13.71 and 13.72 version numbers are synthetic admission metadata, not Garmin releases.",
            "Live evidence proves modified 13.69 descriptor/header acceptance from 10.40, not synthetic forward-version acceptance from 13.70.",
            "The 13.72 wrapper restores official executable bytes except the main image header and additive repair byte; its runtime version mirrors remain official 13.70.",
            "No package can recover a watch whose application updater and normal USB path no longer boot.",
        ],
    }


def build_force_restore(official: bytes) -> tuple[bytes, dict[str, Any]]:
    if sha256(official) != OFFICIAL_SHA256:
        raise ValueError("source is not pinned official non-Music 13.70")
    candidate, field_offset = _set_main_force_field(official)
    changed = _changed_offsets(official, candidate)
    common = _validate_common(official, candidate)
    official_main = _stream(official, MAIN_RECORD_ID)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    checks = {
        **common,
        "main_payload_exact_official": candidate_main.decoded == official_main.decoded,
        "main_payload_sha256_exact_official": sha256(candidate_main.decoded) == OFFICIAL_MAIN_SHA256,
        "changes_are_force_field_and_one_outer_checkpoint_only": changed == [field_offset, 0x4E229E],
    }
    if not all(checks.values()):
        raise AssertionError(f"force-restore checks failed: {checks}")
    return candidate, {
        "purpose": "field-0x0b=1 same-version restore hypothesis around byte-identical official 13.70 payloads",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(_stream(candidate, HELPER_RECORD_ID).decoded),
        "main_field_0x0b_raw_offset": f"0x{field_offset:x}",
        "raw_changed_offsets": [f"0x{x:x}" for x in changed],
        "checks": checks,
    }


def build_force_overlay(
    official: bytes, hook: bytes, payload: bytes, cave_xref_report: str
) -> tuple[bytes, dict[str, Any]]:
    if sha256(hook) != OVERLAY_HOOK_SHA256:
        raise ValueError("hook is not the pinned overlay hook")
    if sha256(payload) != OVERLAY_PAYLOAD_SHA256:
        raise ValueError("payload is not the pinned overlay payload")
    plain_overlay, plain_report = build_overlay_candidate.build_candidate(
        official, hook, payload, cave_xref_report
    )
    candidate, field_offset = _set_main_force_field(plain_overlay)
    changed = _changed_offsets(official, candidate)
    common = _validate_common(official, candidate)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    checks = {
        **common,
        "plain_overlay_checks_pass": all(
            value == 0 if key == "main_stream_byte_sum_mod_256" else bool(value)
            for key, value in plain_report["checks"].items()
        ),
        "hook_exact": candidate_main.decoded[
            build_overlay_candidate.HOOK_OFFSET:build_overlay_candidate.HOOK_OFFSET + len(hook)
        ] == hook,
        "payload_exact": candidate_main.decoded[
            build_overlay_candidate.OVERLAY_OFFSET:
            build_overlay_candidate.OVERLAY_OFFSET + len(payload)
        ] == payload,
        "all_bytes_except_force_metadata_equal_plain_overlay": all(
            (i in (field_offset, 0x4E229E)) or candidate[i] == plain_overlay[i]
            for i in range(len(candidate))
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"force-overlay checks failed: {checks}")
    return candidate, {
        "purpose": "same-version FR245 13.70 scientific-fly overlay with unproven field-0x0b=1 admission hypothesis",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "plain_overlay_sha256": sha256(plain_overlay),
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(_stream(candidate, HELPER_RECORD_ID).decoded),
        "main_field_0x0b_raw_offset": f"0x{field_offset:x}",
        "raw_changed_byte_count": len(changed),
        "raw_changed_offsets": [f"0x{x:x}" for x in changed],
        "overlay": plain_report["patch"],
        "checks": checks,
    }


def verify_exact(
    official: bytes,
    force_restore: bytes,
    force_overlay: bytes,
    hook: bytes,
    payload: bytes,
    cave_xref_report: str,
) -> dict[str, Any]:
    expected_restore, restore_report = build_force_restore(official)
    expected_overlay, overlay_report = build_force_overlay(
        official, hook, payload, cave_xref_report
    )
    checks = {
        "official_sha256_pinned": sha256(official) == OFFICIAL_SHA256,
        "force_restore_byte_exact_reconstruction": force_restore == expected_restore,
        "force_restore_sha256_pinned": sha256(force_restore) == FORCE_RESTORE_SHA256,
        "force_overlay_byte_exact_reconstruction": force_overlay == expected_overlay,
        "force_overlay_sha256_pinned": sha256(force_overlay) == FORCE_OVERLAY_SHA256,
        "force_overlay_main_sha256_pinned": (
            sha256(_stream(force_overlay, MAIN_RECORD_ID).decoded) == FORCE_OVERLAY_MAIN_SHA256
        ),
    }
    return {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "artifacts": {
            "official": {"sha256": sha256(official), "size": len(official)},
            "force_restore": restore_report,
            "force_overlay": overlay_report,
        },
        "limitations": [
            "PASS proves byte identity, known additive checks, and recovered application-side structure only.",
            "It does not prove field 0x0b is honored by the resident loader or that executable code will run safely.",
            "Neither package can restore a watch whose GarminOS updater or normal USB service no longer boots.",
        ],
    }


def _check_output_path(path: Path) -> None:
    if "quarantine" not in {part.lower() for part in path.parts}:
        raise ValueError("candidate output must be under a quarantine directory")
    if not path.name.endswith(REQUIRED_SUFFIX):
        raise ValueError(f"candidate output must end with {REQUIRED_SUFFIX}")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--official", required=True, type=Path)
    build.add_argument("--hook", required=True, type=Path)
    build.add_argument("--payload", required=True, type=Path)
    build.add_argument("--xref-report", required=True, type=Path)
    build.add_argument("--force-restore-output", required=True, type=Path)
    build.add_argument("--force-overlay-output", required=True, type=Path)
    build.add_argument("--report", required=True, type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--official", required=True, type=Path)
    verify.add_argument("--hook", required=True, type=Path)
    verify.add_argument("--payload", required=True, type=Path)
    verify.add_argument("--xref-report", required=True, type=Path)
    verify.add_argument("--force-restore", required=True, type=Path)
    verify.add_argument("--force-overlay", required=True, type=Path)
    verify.add_argument("--report", required=True, type=Path)
    build_forward = sub.add_parser("build-forward")
    build_forward.add_argument("--official", required=True, type=Path)
    build_forward.add_argument("--hook", required=True, type=Path)
    build_forward.add_argument("--payload", required=True, type=Path)
    build_forward.add_argument("--xref-report", required=True, type=Path)
    build_forward.add_argument("--forward-restore-output", required=True, type=Path)
    build_forward.add_argument("--forward-overlay-output", required=True, type=Path)
    build_forward.add_argument("--report", required=True, type=Path)
    verify_forward = sub.add_parser("verify-forward")
    verify_forward.add_argument("--official", required=True, type=Path)
    verify_forward.add_argument("--hook", required=True, type=Path)
    verify_forward.add_argument("--payload", required=True, type=Path)
    verify_forward.add_argument("--xref-report", required=True, type=Path)
    verify_forward.add_argument("--forward-restore", required=True, type=Path)
    verify_forward.add_argument("--forward-overlay", required=True, type=Path)
    verify_forward.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    official = args.official.read_bytes()
    hook = args.hook.read_bytes()
    payload = args.payload.read_bytes()
    xrefs = args.xref_report.read_text(encoding="utf-8")
    if args.command == "build":
        _check_output_path(args.force_restore_output)
        _check_output_path(args.force_overlay_output)
        restore_bytes, restore_report = build_force_restore(official)
        overlay_bytes, overlay_report = build_force_overlay(official, hook, payload, xrefs)
        args.force_restore_output.parent.mkdir(parents=True, exist_ok=True)
        args.force_overlay_output.parent.mkdir(parents=True, exist_ok=True)
        args.force_restore_output.write_bytes(restore_bytes)
        args.force_overlay_output.write_bytes(overlay_bytes)
        report = {"force_restore": restore_report, "force_overlay": overlay_report}
    elif args.command == "verify":
        report = verify_exact(
            official,
            args.force_restore.read_bytes(),
            args.force_overlay.read_bytes(),
            hook,
            payload,
            xrefs,
        )
    elif args.command == "build-forward":
        _check_output_path(args.forward_restore_output)
        _check_output_path(args.forward_overlay_output)
        restore_bytes, restore_report = build_forward_restore(official)
        overlay_bytes, overlay_report = build_forward_overlay(official, hook, payload, xrefs)
        args.forward_restore_output.parent.mkdir(parents=True, exist_ok=True)
        args.forward_overlay_output.parent.mkdir(parents=True, exist_ok=True)
        args.forward_restore_output.write_bytes(restore_bytes)
        args.forward_overlay_output.write_bytes(overlay_bytes)
        report = {"forward_restore": restore_report, "forward_overlay": overlay_report}
    else:
        report = verify_forward_exact(
            official,
            args.forward_restore.read_bytes(),
            args.forward_overlay.read_bytes(),
            hook,
            payload,
            xrefs,
        )
    _write_json(args.report, report)
    print(json.dumps({
        "restore_sha256": report.get("force_restore", {}).get("output_sha256")
        or report.get("forward_restore", {}).get("output_sha256")
        or report.get("artifacts", {}).get("force_restore", {}).get("output_sha256")
        or report.get("artifacts", {}).get("forward_restore", {}).get("output_sha256"),
        "overlay_sha256": report.get("force_overlay", {}).get("output_sha256")
        or report.get("forward_overlay", {}).get("output_sha256")
        or report.get("artifacts", {}).get("force_overlay", {}).get("output_sha256")
        or report.get("artifacts", {}).get("forward_overlay", {}).get("output_sha256"),
        "verdict": report.get("verdict"),
    }))
    return 0 if report.get("verdict", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
