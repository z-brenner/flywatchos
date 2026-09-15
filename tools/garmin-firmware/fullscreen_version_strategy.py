#!/usr/bin/env python3
"""Build and strictly verify the offline FR245 full-screen overlay pair.

The normal-forward pair uses coherent synthetic main versions 13.72 and 13.73.
The tool accepts only pinned local inputs, writes only analysis-only artifacts
under a quarantine directory, and never accesses a mounted device.
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
import overlay_version_strategy  # noqa: E402


OFFICIAL_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
OFFICIAL_MAIN_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
OFFICIAL_HELPER_SHA256 = "f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46"
HOOK_SHA256 = "49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362"

PAYLOAD_SHA256 = "358d71190321f7dd9d51de8ac3c913e370b0fc23a25e7541d072d2ac83941ffb"
PLAIN_OVERLAY_SHA256 = "a7713db8049f672d84bec374819cda37e8e6bb595f8dc0f702c568e90f93b88a"
PLAIN_OVERLAY_MAIN_SHA256 = "8b70dabae294249aa07c0e707c63808f02f85a5a3edfdd670f8b02e05abb6717"
OVERLAY_1372_SHA256 = "6394fd73cc3e7a5660a6fe9cde3cc0b6617c21f8a24f2b6319b328882d662713"
OVERLAY_1372_MAIN_SHA256 = "6e2108d1091c2e017ea284e90aca46466c0b39ea8767efbc21b9c89f0b3ab4cf"
RESTORE_1373_SHA256 = "869d62ab829ac7b75a079effd4d7d0b1e71a5e8a0d1c7d2c94fa686d907aa4e6"
RESTORE_1373_MAIN_SHA256 = "532d4a161ef8455f853cc4bd3d6f5e329e2985eb905658defaf532e3d6bfe957"

MAIN_RECORD_ID = 0x02BD
HELPER_RECORD_ID = 0x0505
OVERLAY_VERSION = 1372
RESTORE_VERSION = 1373
MAIN_HEADER_VERSION_OFFSET = 0x22C
REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stream(data: bytes, record_id: int) -> Any:
    matches = [
        stream
        for stream in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(data))
        if stream.record_id == record_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one 0x{record_id:04x} stream")
    return matches[0]


def _changed_offsets(before: bytes, after: bytes) -> list[int]:
    if len(before) != len(after):
        raise ValueError("candidate changed package length")
    return [index for index, (old, new) in enumerate(zip(before, after)) if old != new]


def _runtime_identity_is_official(main: Any) -> bool:
    return all(
        main.decoded[start:end] == expected
        for start, end, expected in (
            (0x370F06, 0x370F08, b"\x5a\x05"),
            (0x370F34, 0x370F3C, b" V13.70\x00"),
            (0x384398, 0x38439C, b"1370"),
            (0x1CA6BC, 0x1CA6C0, bytes.fromhex("40f25a52")),
        )
    )


def _known_checks(candidate: bytes) -> dict[str, bool]:
    main = _stream(candidate, MAIN_RECORD_ID)
    validation = full_image_validator.validate_bytes(candidate, "fullscreen-version-pair")
    return {
        "main_sum_mod_256_zero": (sum(main.decoded) & 0xFF) == 0,
        "outer_checkpoints_valid": validation["outer_gcd"][
            "all_prefix_sums_zero_mod_256"
        ],
        "confirmed_full_image_checks_pass": validation[
            "confirmed_full_image_checks_pass"
        ],
    }


def build_overlay(
    official: bytes, hook: bytes, payload: bytes, cave_xref_report: str
) -> tuple[bytes, dict[str, Any]]:
    if sha256(official) != OFFICIAL_SHA256:
        raise ValueError("source is not pinned official non-Music 13.70")
    if sha256(hook) != HOOK_SHA256:
        raise ValueError("hook is not the pinned four-byte display hook")
    if sha256(payload) != PAYLOAD_SHA256:
        raise ValueError("payload is not the pinned button-enabled full-screen payload")

    plain, plain_report = build_overlay_candidate.build_candidate(
        official, hook, payload, cave_xref_report
    )
    candidate, version_patch = overlay_version_strategy._set_main_version(
        plain, OVERLAY_VERSION
    )
    official_main = _stream(official, MAIN_RECORD_ID)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    official_helper = _stream(official, HELPER_RECORD_ID)
    candidate_helper = _stream(candidate, HELPER_RECORD_ID)
    decoded_changes = _changed_offsets(official_main.decoded, candidate_main.decoded)
    raw_changes = _changed_offsets(official, candidate)
    allowed = lambda offset: (
        offset == MAIN_HEADER_VERSION_OFFSET
        or build_overlay_candidate.HOOK_OFFSET
        <= offset
        < build_overlay_candidate.HOOK_OFFSET + 4
        or build_overlay_candidate.OVERLAY_OFFSET
        <= offset
        < build_overlay_candidate.OVERLAY_OFFSET
        + build_overlay_candidate.OVERLAY_ALLOCATION
        or offset == official_main.declared_length - 1
    )
    checks = {
        "official_main_pinned": sha256(official_main.decoded) == OFFICIAL_MAIN_SHA256,
        "plain_overlay_package_pinned": sha256(plain) == PLAIN_OVERLAY_SHA256,
        "plain_overlay_main_pinned": sha256(_stream(plain, MAIN_RECORD_ID).decoded)
        == PLAIN_OVERLAY_MAIN_SHA256,
        "descriptor_and_header_coherent_1372": (
            candidate_main.software_version == OVERLAY_VERSION
            and int.from_bytes(
                candidate_main.decoded[
                    MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
                ],
                "little",
            )
            == OVERLAY_VERSION
        ),
        "descriptor_field_0x0b_is_zero": candidate_main.erase_flag == 0,
        "normal_forward_from_13_71": candidate_main.software_version > 1371,
        "runtime_identity_mirrors_official_13_70": _runtime_identity_is_official(
            candidate_main
        ),
        "helper_payload_exact_official": candidate_helper.decoded
        == official_helper.decoded,
        "helper_descriptor_exact_official": candidate_helper.fields
        == official_helper.fields,
        "hook_exact": candidate_main.decoded[
            build_overlay_candidate.HOOK_OFFSET : build_overlay_candidate.HOOK_OFFSET
            + len(hook)
        ]
        == hook,
        "payload_exact": candidate_main.decoded[
            build_overlay_candidate.OVERLAY_OFFSET : build_overlay_candidate.OVERLAY_OFFSET
            + len(payload)
        ]
        == payload,
        "decoded_changes_confined": all(allowed(offset) for offset in decoded_changes),
        **_known_checks(candidate),
    }
    if not all(checks.values()):
        raise AssertionError(f"full-screen overlay checks failed: {checks}")

    patch = dict(plain_report["patch"])
    patch["payload"] = {
        **patch["payload"],
        "draw_region": {"x": 0, "y": 0, "width": 240, "height": 240},
        "behavior": (
            "deterministically repaint the entire 240x240 logical framebuffer, "
            "draw the FlyOS scientific face and button-state markers, call "
            "dirty_add(0,0,240,240), then tail-dispatch the original flush"
        ),
    }
    return candidate, {
        "purpose": "normal-forward 13.72 button-enabled full-screen FlyOS overlay",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "plain_overlay_sha256": sha256(plain),
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(candidate_helper.decoded),
        "version_patch": version_patch,
        "raw_changed_byte_count": len(raw_changes),
        "decoded_main_changed_byte_count": len(decoded_changes),
        "overlay": patch,
        "checks": checks,
    }


def build_restore(official: bytes) -> tuple[bytes, dict[str, Any]]:
    if sha256(official) != OFFICIAL_SHA256:
        raise ValueError("source is not pinned official non-Music 13.70")
    candidate, version_patch = overlay_version_strategy._set_main_version(
        official, RESTORE_VERSION
    )
    official_main = _stream(official, MAIN_RECORD_ID)
    candidate_main = _stream(candidate, MAIN_RECORD_ID)
    official_helper = _stream(official, HELPER_RECORD_ID)
    candidate_helper = _stream(candidate, HELPER_RECORD_ID)
    expected_main = bytearray(official_main.decoded)
    expected_main[
        MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
    ] = RESTORE_VERSION.to_bytes(2, "little")
    expected_main[-1] = candidate_main.decoded[-1]
    raw_changes = _changed_offsets(official, candidate)
    checks = {
        "descriptor_and_header_coherent_1373": (
            candidate_main.software_version == RESTORE_VERSION
            and int.from_bytes(
                candidate_main.decoded[
                    MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
                ],
                "little",
            )
            == RESTORE_VERSION
        ),
        "descriptor_field_0x0b_is_zero": candidate_main.erase_flag == 0,
        "normal_forward_from_13_72": candidate_main.software_version > OVERLAY_VERSION,
        "runtime_identity_mirrors_official_13_70": _runtime_identity_is_official(
            candidate_main
        ),
        "main_exact_except_header_and_final_additive_repair": candidate_main.decoded
        == bytes(expected_main),
        "official_hook_restored": candidate_main.decoded[
            build_overlay_candidate.HOOK_OFFSET : build_overlay_candidate.HOOK_OFFSET + 4
        ]
        == official_main.decoded[
            build_overlay_candidate.HOOK_OFFSET : build_overlay_candidate.HOOK_OFFSET + 4
        ],
        "official_cave_restored": candidate_main.decoded[
            build_overlay_candidate.OVERLAY_OFFSET : build_overlay_candidate.OVERLAY_OFFSET
            + build_overlay_candidate.OVERLAY_ALLOCATION
        ]
        == official_main.decoded[
            build_overlay_candidate.OVERLAY_OFFSET : build_overlay_candidate.OVERLAY_OFFSET
            + build_overlay_candidate.OVERLAY_ALLOCATION
        ],
        "helper_payload_exact_official": candidate_helper.decoded
        == official_helper.decoded,
        "helper_descriptor_exact_official": candidate_helper.fields
        == official_helper.fields,
        "raw_changes_exact": raw_changes == [0xA160, 0xA392, 0x4E2299, 0x4E229E],
        **_known_checks(candidate),
    }
    if not all(checks.values()):
        raise AssertionError(f"13.73 restore checks failed: {checks}")
    return candidate, {
        "purpose": "forward 13.73 wrapper carrying official 13.70 executable code and resources",
        "install_status": "quarantined; offline only; not approved for device transfer",
        "source_sha256": OFFICIAL_SHA256,
        "output_sha256": sha256(candidate),
        "size": len(candidate),
        "main_payload_sha256": sha256(candidate_main.decoded),
        "helper_payload_sha256": sha256(candidate_helper.decoded),
        "version_patch": version_patch,
        "raw_changed_offsets": [f"0x{offset:x}" for offset in raw_changes],
        "checks": checks,
    }


def verify_exact(
    official: bytes,
    overlay: bytes,
    restore: bytes,
    hook: bytes,
    payload: bytes,
    cave_xref_report: str,
) -> dict[str, Any]:
    expected_overlay, overlay_report = build_overlay(
        official, hook, payload, cave_xref_report
    )
    expected_restore, restore_report = build_restore(official)
    checks = {
        "official_sha256_pinned": sha256(official) == OFFICIAL_SHA256,
        "overlay_byte_exact_reconstruction": overlay == expected_overlay,
        "overlay_package_sha256_pinned": sha256(overlay) == OVERLAY_1372_SHA256,
        "overlay_main_sha256_pinned": sha256(_stream(overlay, MAIN_RECORD_ID).decoded)
        == OVERLAY_1372_MAIN_SHA256,
        "restore_byte_exact_reconstruction": restore == expected_restore,
        "restore_package_sha256_pinned": sha256(restore) == RESTORE_1373_SHA256,
        "restore_main_sha256_pinned": sha256(_stream(restore, MAIN_RECORD_ID).decoded)
        == RESTORE_1373_MAIN_SHA256,
    }
    return {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "artifacts": {"overlay": overlay_report, "restore": restore_report},
        "limitations": [
            "Versions 13.72 and 13.73 are synthetic metadata, not Garmin releases.",
            "The full-screen payload and button reads have not executed on hardware.",
            "The restore wrapper requires a booting GarminOS updater and normal USB service.",
            "No package here provides recovery from a nonbooting application.",
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
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    verify = subparsers.add_parser("verify")
    for command in (build, verify):
        command.add_argument("--official", required=True, type=Path)
        command.add_argument("--hook", required=True, type=Path)
        command.add_argument("--payload", required=True, type=Path)
        command.add_argument("--xref-report", required=True, type=Path)
        command.add_argument("--overlay", required=True, type=Path)
        command.add_argument("--restore", required=True, type=Path)
        command.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    official = args.official.read_bytes()
    hook = args.hook.read_bytes()
    payload = args.payload.read_bytes()
    xrefs = args.xref_report.read_text(encoding="utf-8")
    if args.command == "build":
        _check_output_path(args.overlay)
        _check_output_path(args.restore)
        overlay, overlay_report = build_overlay(official, hook, payload, xrefs)
        restore, restore_report = build_restore(official)
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        args.restore.parent.mkdir(parents=True, exist_ok=True)
        args.overlay.write_bytes(overlay)
        args.restore.write_bytes(restore)
        report = {"overlay": overlay_report, "restore": restore_report}
    else:
        report = verify_exact(
            official,
            args.overlay.read_bytes(),
            args.restore.read_bytes(),
            hook,
            payload,
            xrefs,
        )
    _write_json(args.report, report)
    print(
        json.dumps(
            {
                "overlay_sha256": report.get("overlay", {}).get("output_sha256")
                or report.get("artifacts", {}).get("overlay", {}).get("output_sha256"),
                "restore_sha256": report.get("restore", {}).get("output_sha256")
                or report.get("artifacts", {}).get("restore", {}).get("output_sha256"),
                "verdict": report.get("verdict"),
            }
        )
    )
    return 0 if report.get("verdict", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
