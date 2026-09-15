#!/usr/bin/env python3
"""Fail-closed offline verifier for a patched FR245 non-Music 13.70 GCD.

The verifier never modifies either input.  It accepts only a same-layout copy
of the pinned official package whose changed bytes are confined to 0x02bd data
record bodies, whose 0x0505 helper is byte-identical, and whose visible
additive integrity checks remain valid.  Passing is not device authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gcd_inspect  # noqa: E402


OFFICIAL_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
OFFICIAL_HELPER_SHA256 = "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46"
OFFICIAL_MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
MAIN_IMAGE_VERSION_OFFSET = 0x22C
VISIBLE_PROOF_PROFILE = "flyos-visible-proof-1370"
VISIBLE_PROOF_CANDIDATE_SHA256 = (
    "b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba"
)
VISIBLE_PROOF_MAIN_SHA256 = (
    "f6224af2283bca90ad17cea11366c92ed7b00be567da633f15b50d2432d2346f"
)
VISIBLE_PROOF_DECODED_OFFSET = 0x43EAA4
VISIBLE_PROOF_ORIGINAL = b"Software Version"
VISIBLE_PROOF_REPLACEMENT = b"FLY LIVES 2ALIVE"
RESTORE_HYPOTHESIS_PROFILE = "flyos-visible-proof-restore1369"
RESTORE_HYPOTHESIS_CANDIDATE_SHA256 = (
    "da4e5d5f2d19ae8312cf56937873495547ea3c74142a26ae535c1059aa75b90b"
)
RESTORE_HYPOTHESIS_MAIN_SHA256 = (
    "f63c628af1e3b7df8232dc309d839d09265b9f906f9401e84bbad941e988c478"
)
MATCHED_13_69_PROFILE = "flyos-visible-proof-matched1369"
MATCHED_13_69_CANDIDATE_SHA256 = (
    "d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f"
)
NEURAL_OVERLAY_PROFILE = "flyos-neural-overlay-1373"
NEURAL_RESTORE_PROFILE = "flyos-neural-restore-1374"
N64_OVERLAY_PROFILE = "flyos-neural-specimen-n64-1374"
N64_RESTORE_PROFILE = "flyos-neural-specimen-n64-restore-1375"


def _u16_at(data: bytes, offset: int) -> int | None:
    if offset + 2 > len(data):
        return None
    return int.from_bytes(data[offset : offset + 2], "little")


def _ascii_at(data: bytes, offset: int, length: int) -> str | None:
    if offset + length > len(data):
        return None
    try:
        return data[offset : offset + length].decode("ascii")
    except UnicodeDecodeError:
        return None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stream(gcd: Any, record_id: int) -> Any:
    matches = [item for item in gcd_inspect.collect_streams(gcd) if item.record_id == record_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one 0x{record_id:04x} stream")
    return matches[0]


def _main_body_locations(gcd: Any, stream: Any) -> dict[int, int]:
    locations: dict[int, int] = {}
    decoded_cursor = 0
    records_by_offset = {item.offset: item for item in gcd.records}
    for record_offset in stream.record_offsets:
        record = records_by_offset[record_offset]
        for body_offset in range(record.length):
            locations[record.offset + 4 + body_offset] = decoded_cursor + body_offset
        decoded_cursor += record.length
    return locations


def _record_at(gcd: Any, raw_offset: int) -> tuple[Any | None, str]:
    for record in gcd.records:
        if record.offset <= raw_offset < record.offset + 4:
            return record, "header"
        if record.offset + 4 <= raw_offset < record.offset + 4 + record.length:
            return record, "body"
    return None, "outside"


def verify_packages(
    official_path: Path,
    candidate_path: Path,
    *,
    expected_official_sha256: str = OFFICIAL_SHA256,
    profile: str | None = None,
) -> dict[str, Any]:
    official_path = official_path.resolve()
    candidate_path = candidate_path.resolve()
    official_raw = official_path.read_bytes()
    candidate_raw = candidate_path.read_bytes()
    official_hash = sha256(official_raw)
    if official_hash != expected_official_sha256:
        raise ValueError("official input does not match the pinned restore artifact")

    official_gcd = gcd_inspect.parse_gcd(official_raw)
    candidate_gcd = gcd_inspect.parse_gcd(candidate_raw)
    official_helper = _stream(official_gcd, 0x0505)
    candidate_helper = _stream(candidate_gcd, 0x0505)
    official_main = _stream(official_gcd, 0x02BD)
    candidate_main = _stream(candidate_gcd, 0x02BD)
    main_locations = _main_body_locations(official_gcd, official_main)

    layout_official = [(item.offset, item.record_id, item.length) for item in official_gcd.records]
    layout_candidate = [(item.offset, item.record_id, item.length) for item in candidate_gcd.records]
    changed_bytes: list[dict[str, Any]] = []
    maximum = max(len(official_raw), len(candidate_raw))
    for offset in range(maximum):
        before = official_raw[offset] if offset < len(official_raw) else None
        after = candidate_raw[offset] if offset < len(candidate_raw) else None
        if before == after:
            continue
        record, part = _record_at(official_gcd, offset)
        changed_bytes.append(
            {
                "raw_file_offset": f"0x{offset:x}",
                "official_byte": before,
                "candidate_byte": after,
                "record_id": f"0x{record.record_id:04x}" if record else None,
                "record_part": part,
                "decoded_stream_offset": (
                    f"0x{main_locations[offset]:x}" if offset in main_locations else None
                ),
            }
        )

    official_end = next(item for item in official_gcd.records if item.record_id == 0xFFFF)
    candidate_end = next(item for item in candidate_gcd.records if item.record_id == 0xFFFF)
    candidate_checkpoints = gcd_inspect._checkpoint_results(candidate_gcd)
    gates = {
        "candidate_differs_from_official": len(changed_bytes) > 0,
        "same_file_size": len(candidate_raw) == len(official_raw),
        "same_record_layout": layout_candidate == layout_official,
        "helper_0x0505_byte_identical": candidate_helper.decoded == official_helper.decoded,
        "helper_0x0505_matches_official_hash": (
            sha256(candidate_helper.decoded) == sha256(official_helper.decoded)
        ),
        "changes_only_in_0x02bd_payload": bool(changed_bytes) and all(
            item["record_id"] == "0x02bd" and item["record_part"] == "body"
            for item in changed_bytes
        ),
        "main_descriptor_unchanged": candidate_main.fields == official_main.fields,
        "main_stream_length_unchanged": candidate_main.declared_length == official_main.declared_length,
        "main_stream_sum_mod_256_zero": (sum(candidate_main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": bool(candidate_checkpoints)
        and all(item["valid"] for item in candidate_checkpoints),
        "outer_prefix_before_end_sum_mod_256_zero": (
            sum(candidate_raw[: candidate_end.offset]) & 0xFF
        )
        == 0,
        "remains_full_image_not_gdelta01": candidate_main.decoded[:8] != b"GDELTA01",
    }

    profile_result: dict[str, Any] | None = None
    if profile is not None:
        if profile not in (
            VISIBLE_PROOF_PROFILE,
            RESTORE_HYPOTHESIS_PROFILE,
            MATCHED_13_69_PROFILE,
            NEURAL_OVERLAY_PROFILE,
            NEURAL_RESTORE_PROFILE,
            N64_OVERLAY_PROFILE,
            N64_RESTORE_PROFILE,
        ):
            raise ValueError(f"unknown verification profile: {profile}")
        if profile in (
            NEURAL_OVERLAY_PROFILE,
            NEURAL_RESTORE_PROFILE,
            N64_OVERLAY_PROFILE,
            N64_RESTORE_PROFILE,
        ):
            if profile in (N64_OVERLAY_PROFILE, N64_RESTORE_PROFILE):
                import neural_specimen_n64_version_strategy as neural
                overlay_profile = N64_OVERLAY_PROFILE
            else:
                import neural_overlay_version_strategy as neural
                overlay_profile = NEURAL_OVERLAY_PROFILE

            repo_root = Path(__file__).resolve().parents[2]
            expected_overlay, expected_restore, neural_report = neural.construct_pair(
                repo_root, repo_root / neural.DECISION_RELATIVE_PATH
            )
            expected = (
                expected_overlay
                if profile == overlay_profile
                else expected_restore
            )
            expected_version = (
                neural.CANDIDATE_VERSION
                if profile == overlay_profile
                else neural.RESTORE_VERSION
            )
            profile_checks = {
                "byte_exact_reconstruction": candidate_raw == expected,
                "package_sha256_exact_reconstruction": sha256(candidate_raw)
                == sha256(expected),
                "main_descriptor_and_header_coherent": (
                    candidate_main.software_version == expected_version
                    and _u16_at(candidate_main.decoded, MAIN_IMAGE_VERSION_OFFSET)
                    == expected_version
                ),
                "neural_build_checks_pass": all(
                    neural_report[
                        "candidate"
                        if profile == overlay_profile
                        else "restore"
                    ]["checks"].values()
                ),
                "packaging_allowed_remains_false": neural_report["policy"][
                    "packaging_allowed"
                ]
                is False,
                "live_staging_allowed_remains_false": neural_report["policy"][
                    "live_staging_allowed"
                ]
                is False,
            }
            del gates["changes_only_in_0x02bd_payload"]
            del gates["main_descriptor_unchanged"]
            gates["changes_confined_to_exact_neural_profile"] = profile_checks[
                "byte_exact_reconstruction"
            ]
            gates["main_descriptor_matches_neural_profile"] = profile_checks[
                "main_descriptor_and_header_coherent"
            ]
            gates["profile_exact_match"] = all(profile_checks.values())
            profile_result = {
                "name": profile,
                "expected_candidate_sha256": sha256(expected),
                "checks": profile_checks,
            }
        else:
            start = VISIBLE_PROOF_DECODED_OFFSET
            end = start + len(VISIBLE_PROOF_ORIGINAL)
            common_checks = {
                "pinned_official_package": official_hash == OFFICIAL_SHA256,
                "pinned_official_main": sha256(official_main.decoded) == OFFICIAL_MAIN_SHA256,
                "source_label_exact": official_main.decoded[start:end] == VISIBLE_PROOF_ORIGINAL,
                "replacement_length_unchanged": len(VISIBLE_PROOF_REPLACEMENT) == len(VISIBLE_PROOF_ORIGINAL),
            }
            if profile == VISIBLE_PROOF_PROFILE:
                expected_package_hash = VISIBLE_PROOF_CANDIDATE_SHA256
                expected_candidate_main = (
                    official_main.decoded[:start]
                    + VISIBLE_PROOF_REPLACEMENT
                    + official_main.decoded[end:]
                )
                profile_checks = {
                    **common_checks,
                    "replacement_sum_mod_256_unchanged": (
                        sum(VISIBLE_PROOF_REPLACEMENT) & 0xFF
                    )
                    == (sum(VISIBLE_PROOF_ORIGINAL) & 0xFF),
                    "decoded_main_exact": candidate_main.decoded == expected_candidate_main,
                    "candidate_main_sha256_exact": sha256(candidate_main.decoded) == VISIBLE_PROOF_MAIN_SHA256,
                    "candidate_package_sha256_exact": sha256(candidate_raw) == VISIBLE_PROOF_CANDIDATE_SHA256,
                }
            elif profile == RESTORE_HYPOTHESIS_PROFILE:
                expected_package_hash = RESTORE_HYPOTHESIS_CANDIDATE_SHA256
                expected_candidate_main = bytearray(official_main.decoded)
                expected_candidate_main[MAIN_IMAGE_VERSION_OFFSET] = 0x59
                expected_candidate_main[start:end] = VISIBLE_PROOF_REPLACEMENT
                expected_candidate_main[-1] = (expected_candidate_main[-1] - (sum(expected_candidate_main) & 0xFF)) & 0xFF
                profile_checks = {
                    **common_checks,
                    "main_header_is_13_69": candidate_main.decoded[MAIN_IMAGE_VERSION_OFFSET:MAIN_IMAGE_VERSION_OFFSET + 2] == b"\x59\x05",
                    "decoded_main_exact": candidate_main.decoded == bytes(expected_candidate_main),
                    "candidate_main_sha256_exact": sha256(candidate_main.decoded) == RESTORE_HYPOTHESIS_MAIN_SHA256,
                    "candidate_package_sha256_exact": sha256(candidate_raw) == RESTORE_HYPOTHESIS_CANDIDATE_SHA256,
                }
            else:
                expected_package_hash = MATCHED_13_69_CANDIDATE_SHA256
                expected_candidate_main = bytearray(official_main.decoded)
                expected_candidate_main[MAIN_IMAGE_VERSION_OFFSET] = 0x59
                expected_candidate_main[start:end] = VISIBLE_PROOF_REPLACEMENT
                expected_candidate_main[-1] = (expected_candidate_main[-1] - (sum(expected_candidate_main) & 0xFF)) & 0xFF
                expected_changed_raw_offsets = {
                    0xA160,
                    0xA392,
                    *range(0x448D1A, 0x448D2A),
                    0x4E2299,
                    0x4E229E,
                }
                actual_changed_raw_offsets = {
                    int(item["raw_file_offset"], 16) for item in changed_bytes
                }
                profile_checks = {
                    **common_checks,
                    "main_descriptor_is_13_69": candidate_main.software_version == 1369,
                    "main_header_is_13_69": candidate_main.decoded[MAIN_IMAGE_VERSION_OFFSET:MAIN_IMAGE_VERSION_OFFSET + 2] == b"\x59\x05",
                    "decoded_main_exact": candidate_main.decoded == bytes(expected_candidate_main),
                    "candidate_main_sha256_exact": sha256(candidate_main.decoded) == RESTORE_HYPOTHESIS_MAIN_SHA256,
                    "candidate_package_sha256_exact": sha256(candidate_raw) == MATCHED_13_69_CANDIDATE_SHA256,
                    "changed_raw_offsets_exact": actual_changed_raw_offsets == expected_changed_raw_offsets,
                }
                del gates["changes_only_in_0x02bd_payload"]
                del gates["main_descriptor_unchanged"]
                gates["changes_confined_to_exact_matched_profile"] = profile_checks["changed_raw_offsets_exact"]
                gates["main_descriptor_matches_13_69_header"] = (
                    candidate_main.software_version == 1369
                    and _u16_at(candidate_main.decoded, MAIN_IMAGE_VERSION_OFFSET) == 1369
                )
            gates["profile_exact_match"] = all(profile_checks.values())
            profile_result = {
                "name": profile,
                "decoded_offset": f"0x{start:x}",
                "original_ascii": VISIBLE_PROOF_ORIGINAL.decode("ascii"),
                "replacement_ascii": VISIBLE_PROOF_REPLACEMENT.decode("ascii"),
                "expected_candidate_sha256": expected_package_hash,
                "checks": profile_checks,
            }

    official_header_version = _u16_at(official_main.decoded, MAIN_IMAGE_VERSION_OFFSET)
    candidate_header_version = _u16_at(candidate_main.decoded, MAIN_IMAGE_VERSION_OFFSET)
    official_descriptor_newer = bool(
        official_main.software_version is not None
        and candidate_header_version is not None
        and official_main.software_version > candidate_header_version
    )
    if official_descriptor_newer:
        restore_assessment = "CONDITIONALLY_ELIGIBLE_BY_VISIBLE_VERSION_COMPARISON"
    elif (
        official_main.software_version is not None
        and official_main.software_version == candidate_header_version
        and official_main.erase_flag == 0
    ):
        restore_assessment = "SKIPPED_BY_VISIBLE_VERSION_COMPARISON"
    else:
        restore_assessment = "UNRESOLVED"

    visible_result = "PASS" if all(gates.values()) else "FAIL"
    report = {
        "tool": "tools/garmin-firmware/gcd_candidate_verify.py",
        "purpose": "offline package comparison only; never transfer a candidate to the watch",
        "visible_gate_result": visible_result,
        "official": {
            "path": str(official_path),
            "size": len(official_raw),
            "sha256": official_hash,
            "helper_0x0505_sha256": sha256(official_helper.decoded),
            "main_0x02bd_sha256": sha256(official_main.decoded),
            "prefix_before_end_sum_mod_256": sum(official_raw[: official_end.offset]) & 0xFF,
        },
        "candidate": {
            "path": str(candidate_path),
            "size": len(candidate_raw),
            "sha256": sha256(candidate_raw),
            "helper_0x0505_sha256": sha256(candidate_helper.decoded),
            "main_0x02bd_sha256": sha256(candidate_main.decoded),
            "main_0x02bd_sum_mod_256": sum(candidate_main.decoded) & 0xFF,
            "first_8_main_bytes_hex": candidate_main.decoded[:8].hex(),
        },
        "gates": gates,
        "changed_byte_count": len(changed_bytes),
        "changed_bytes": changed_bytes,
        "outer_checkpoints": candidate_checkpoints,
        "version_policy": {
            "official_helper_descriptor_version": official_helper.software_version,
            "candidate_helper_descriptor_version": candidate_helper.software_version,
            "official_main_descriptor_version": official_main.software_version,
            "candidate_main_descriptor_version": candidate_main.software_version,
            "official_main_descriptor_force_field_0x0b": official_main.erase_flag,
            "candidate_main_descriptor_force_field_0x0b": candidate_main.erase_flag,
            "main_image_header_version_offset": "0x22c",
            "official_main_image_header_version": official_header_version,
            "candidate_main_image_header_version": candidate_header_version,
            "official_descriptor_newer_than_candidate_header": official_descriptor_newer,
            "official_13_70_application_restore_assessment": restore_assessment,
            "known_13_70_identity_mirrors": {
                "system_tuple_u16_at_0x370f06": _u16_at(candidate_main.decoded, 0x370F06),
                "display_string_at_0x370f34": _ascii_at(candidate_main.decoded, 0x370F34, 8),
                "product_string_at_0x384398": _ascii_at(candidate_main.decoded, 0x384398, 4),
                "event_version_movw_at_0x1ca6bc_hex": (
                    candidate_main.decoded[0x1CA6BC : 0x1CA6C0].hex()
                    if len(candidate_main.decoded) >= 0x1CA6C0
                    else None
                ),
            },
            "force_tmp_literal_present": b"force.tmp" in candidate_main.decoded.lower(),
            "interpretation": (
                "The 13.70 application compares an installed/current component version with the incoming "
                "descriptor version and accepts only a numerically newer image unless descriptor field 0x0b "
                "is nonzero. Lowering decoded header 0x22c is a restore hypothesis, not proof that the "
                "installed-version reader uses that field or that the resident loader accepts a mismatch."
            ),
        },
        "target_regions": {
            "helper_stage_type_0x05": {
                "address_start": "0x68103000",
                "address_end_exclusive": "0x68118000",
                "capacity": "0x15000",
            },
            "main_stage_type_0x0e": {
                "address_start": "0x68118000",
                "address_end_exclusive": "0x68617000",
                "capacity": "0x4ff000",
                "failure_marker": "0x68615000",
            },
            "helper_copy_destination_type_0xaf": {
                "internal_child_0xab": "0x00003000..0x001fffff",
                "external_child_0xac": "0x68617000..0x68916fff",
                "capacity": "0x4fd000",
                "boot_prefix_0x00000000_0x00002fff_included": False,
            },
        },
        "known_operation_order": [
            "GarminOS opens/parses the GCD and performs package preflight checks.",
            "GarminOS stages the byte-identical 0x0505 helper through type 0x05.",
            "GarminOS erases type 0x0e before streaming the main 0x02bd payload into it.",
            "A staging failure sets the one-way marker at 0x68615000; successful staging closes the region and requests restart.",
            "The omitted resident loader decides whether and how to authenticate and launch the staged helper.",
            "On the helper rewrite branch, type 0xaf is erased child 0xab first, then child 0xac.",
            "The helper copies type 0x0e to type 0xaf in monotonic chunks no larger than 0x1e000 bytes.",
            "The helper checksums the written type 0xaf destination; its later failure/restart handoff is unresolved.",
        ],
        "restore_artifact": {
            "path": str(official_path),
            "sha256": official_hash,
            "byte_identical_official": True,
            "recovery_status": (
                "The official package is preserved. "
                + (
                    "Its descriptor is numerically newer than the candidate main-image header, so the visible "
                    "application comparison would admit it if header 0x22c supplies the installed version; that "
                    "source linkage and resident-loader acceptance remain unproven."
                    if official_descriptor_newer
                    else "Its zero force field and same version are skipped by the visible application comparison; "
                    "no force.tmp path or recovery-loader acceptance has been established."
                )
            ),
        },
        "limitations": [
            "PASS covers only validators visible in the acquired GarminOS application and offline package structure.",
            "The omitted resident loader may enforce signatures, anti-rollback, device policy, or another digest.",
            "This verifier does not authorize or perform copying, staging, flashing, reset, recovery, or execution.",
        ],
    }
    if profile_result is not None:
        report["profile"] = profile_result
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="offline candidate GCD")
    parser.add_argument(
        "--official",
        type=Path,
        default=Path("artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD"),
        help="pinned official non-Music 13.70 GCD",
    )
    parser.add_argument("--report", required=True, type=Path, help="JSON output report")
    parser.add_argument(
        "--profile",
        choices=[
            VISIBLE_PROOF_PROFILE,
            RESTORE_HYPOTHESIS_PROFILE,
            MATCHED_13_69_PROFILE,
            NEURAL_OVERLAY_PROFILE,
            NEURAL_RESTORE_PROFILE,
            N64_OVERLAY_PROFILE,
            N64_RESTORE_PROFILE,
        ],
        help="require an exact, named candidate byte profile",
    )
    args = parser.parse_args()
    try:
        report = verify_packages(args.official, args.candidate, profile=args.profile)
    except (OSError, ValueError, gcd_inspect.GcdFormatError) as error:
        parser.error(str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["visible_gate_result"])
    print(f"report: {args.report}")
    return 0 if report["visible_gate_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
