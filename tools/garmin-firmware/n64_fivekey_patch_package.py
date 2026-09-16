#!/usr/bin/env python3
"""Construct an offline-only, exact-byte FR245 five-key package pair."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import build_overlay_candidate  # noqa: E402
import full_image_validator  # noqa: E402
import overlay_version_strategy  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402

OFFICIAL_RELATIVE = Path("artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD")
INSTALLED_CANDIDATE_RELATIVE = Path(
    "artifacts/firmware/quarantine/"
    "Forerunner245_1376-flyos-neural-specimen-n64-controls.gcd.analysis-only.DO_NOT_INSTALL"
)

FLASH_BASE = 0x3000
PRIMARY_OFFSET = 0x1F6000 - FLASH_BASE
KEY_FILTER_OFFSET = 0x1F61F4 - FLASH_BASE
BACK_GUARD_OFFSET = 0x1F622C - FLASH_BASE
PRIMARY_REPAIR_OFFSET = 0x1F63FF - FLASH_BASE
MAIN_HEADER_VERSION_OFFSET = 0x22C
FINAL_MAIN_REPAIR_OFFSET = 0x4D7FFF
MAIN_VERSION_RAW_OFFSET = 0xA160
MAIN_RECORD_ID = 0x02BD
OFFICIAL_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
PRIOR_SHA256 = "9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de"
PRIOR_PRIMARY_SHA256 = "dd7d514119118467bf65f6151bd6d98ee1479640a7e651ac752342a11ac09677"
PATCHED_PRIMARY_SHA256 = "035a3f1ff0eaa9dc8d052b467d6286479539c79497f399eecea631ad8ea90e37"
ORIGINAL_FILTER = bytes.fromhex("0128f8b506460f4602d0c31e012b30d8")
PATCHED_FILTER = bytes.fromhex("0428f8b506460f4633d800bf00bf00bf")
ORIGINAL_BACK_GUARD = bytes.fromhex("1bd5")
PATCHED_BACK_GUARD = bytes.fromhex("00bf")
CANDIDATE_VERSION = 1380
RESTORE_VERSION = 1381
REPO_ROOT = Path(__file__).resolve().parents[2]
QUARANTINE_RELATIVE = Path("artifacts/firmware/quarantine")
CANDIDATE_NAME = "Forerunner245_1380-flyos-n64-fivekey.gcd.analysis-only.DO_NOT_INSTALL"
RESTORE_NAME = "Forerunner245_1381-official-code-restore-fivekey.gcd.analysis-only.DO_NOT_INSTALL"
REPORT_NAME = "n64-fivekey-package-1380-1381.json"
EVIDENCE_RELATIVE = Path("artifacts/firmware/analysis/atlas-shell-runs/fivekey-spike/inplace-emulator-report.json")
EVIDENCE_SHA256 = "561eccc2fe18d2c1f77ce062428bc0416846c5607addd80d025e8a4774904af1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stream(data: bytes):
    _helper, main = build_overlay_candidate._streams(data)
    return main


def set_version(source: bytes, expected_old: int, new: int) -> bytes:
    main = stream(source)
    old_bytes = expected_old.to_bytes(2, "little")
    if source[MAIN_VERSION_RAW_OFFSET:MAIN_VERSION_RAW_OFFSET + 2] != old_bytes:
        raise ValueError("raw descriptor version mismatch")
    if main.software_version != expected_old:
        raise ValueError("decoded descriptor version mismatch")
    if main.decoded[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2] != old_bytes:
        raise ValueError("decoded header version mismatch")
    raw = bytearray(source)
    raw[MAIN_VERSION_RAW_OFFSET:MAIN_VERSION_RAW_OFFSET + 2] = new.to_bytes(2, "little")
    changed = build_overlay_candidate._replace_decoded_slice(
        bytes(raw), main, MAIN_HEADER_VERSION_OFFSET, new.to_bytes(2, "little")
    )
    intermediate = stream(changed)
    old_repair = intermediate.decoded[FINAL_MAIN_REPAIR_OFFSET]
    replacement = (old_repair - (sum(intermediate.decoded) & 0xFF)) & 0xFF
    changed = build_overlay_candidate._replace_decoded_slice(
        changed, intermediate, FINAL_MAIN_REPAIR_OFFSET, bytes([replacement])
    )
    changed = recompute_checkpoints(changed)
    final = stream(changed)
    if final.software_version != new or (sum(final.decoded) & 0xFF):
        raise AssertionError("version/additive repair failed")
    return changed


def construct_pair(official: bytes, installed: bytes) -> tuple[bytes, bytes, dict]:
    if sha256(official) != OFFICIAL_SHA256 or sha256(installed) != PRIOR_SHA256:
        raise ValueError("input is not pinned official 13.70 and prior 13.76 pair")
    official_helper, official_main = build_overlay_candidate._streams(official)
    prior_helper, prior_main = build_overlay_candidate._streams(installed)
    if official_helper.decoded != prior_helper.decoded or official_helper.fields != prior_helper.fields:
        raise ValueError("prior package changed official update helper")
    if len(official) != len(installed) or len(official_main.decoded) != len(prior_main.decoded):
        raise ValueError("package or main length changed")
    primary = prior_main.decoded[PRIMARY_OFFSET:PRIMARY_REPAIR_OFFSET + 1]
    if sha256(primary[:996]) != PRIOR_PRIMARY_SHA256:
        raise ValueError("prior primary payload differs from tested binary")
    if prior_main.decoded[KEY_FILTER_OFFSET:KEY_FILTER_OFFSET + 16] != ORIGINAL_FILTER:
        raise ValueError("prior key filter changed")
    if prior_main.decoded[BACK_GUARD_OFFSET:BACK_GUARD_OFFSET + 2] != ORIGINAL_BACK_GUARD:
        raise ValueError("prior BACK chord guard changed")

    changed = build_overlay_candidate._replace_decoded_slice(
        installed, prior_main, KEY_FILTER_OFFSET, PATCHED_FILTER
    )
    changed = build_overlay_candidate._replace_decoded_slice(
        changed, stream(changed), BACK_GUARD_OFFSET, PATCHED_BACK_GUARD
    )
    main = stream(changed)
    old_repair = main.decoded[PRIMARY_REPAIR_OFFSET]
    repair = (old_repair - (sum(main.decoded) & 0xFF)) & 0xFF
    changed = build_overlay_candidate._replace_decoded_slice(
        changed, main, PRIMARY_REPAIR_OFFSET, bytes([repair])
    )
    candidate = set_version(recompute_checkpoints(changed), 1376, CANDIDATE_VERSION)
    restore, _ = overlay_version_strategy._set_main_version(official, RESTORE_VERSION)

    new_helper, new_main = build_overlay_candidate._streams(candidate)
    restore_helper, restore_main = build_overlay_candidate._streams(restore)
    if new_helper.decoded != official_helper.decoded or restore_helper.decoded != official_helper.decoded:
        raise AssertionError("helper payload changed")
    if new_helper.fields != official_helper.fields or restore_helper.fields != official_helper.fields:
        raise AssertionError("helper descriptor changed")
    patched_primary = new_main.decoded[PRIMARY_OFFSET:PRIMARY_OFFSET + 996]
    # The primary additive repair occupies its last byte; compare the 995 code/padding bytes.
    expected_primary = bytearray(primary[:996])
    expected_primary[KEY_FILTER_OFFSET - PRIMARY_OFFSET:KEY_FILTER_OFFSET - PRIMARY_OFFSET + 16] = PATCHED_FILTER
    expected_primary[BACK_GUARD_OFFSET - PRIMARY_OFFSET:BACK_GUARD_OFFSET - PRIMARY_OFFSET + 2] = PATCHED_BACK_GUARD
    expected_primary[-1] = patched_primary[-1]
    if patched_primary != bytes(expected_primary):
        raise AssertionError("primary differs outside exact key patch and additive repair")
    patched_code = bytearray(patched_primary)
    patched_code[-1] = primary[995]
    if sha256(bytes(patched_code)) != PATCHED_PRIMARY_SHA256:
        raise AssertionError("patched primary no longer matches instruction evidence")
    candidate_validation = full_image_validator.validate_bytes(candidate)
    restore_validation = full_image_validator.validate_bytes(restore)
    if not candidate_validation["confirmed_full_image_checks_pass"]:
        raise AssertionError("candidate failed application-side full-image checks")
    if not restore_validation["confirmed_full_image_checks_pass"]:
        raise AssertionError("restore failed application-side full-image checks")
    expected_restore = bytearray(official_main.decoded)
    expected_restore[MAIN_HEADER_VERSION_OFFSET:MAIN_HEADER_VERSION_OFFSET + 2] = RESTORE_VERSION.to_bytes(2, "little")
    expected_restore[FINAL_MAIN_REPAIR_OFFSET] = restore_main.decoded[FINAL_MAIN_REPAIR_OFFSET]
    if restore_main.decoded != bytes(expected_restore):
        raise AssertionError("restore is not official code/resources with version repair")
    report = {
        "status": "quarantined_offline_only",
        "official_sha256": OFFICIAL_SHA256,
        "prior_1376_sha256": PRIOR_SHA256,
        "candidate_sha256": sha256(candidate),
        "restore_sha256": sha256(restore),
        "candidate_size": len(candidate),
        "restore_size": len(restore),
        "candidate_main_sha256": sha256(new_main.decoded),
        "restore_main_sha256": sha256(restore_main.decoded),
        "candidate_version": CANDIDATE_VERSION,
        "restore_version": RESTORE_VERSION,
        "primary_repair_old": old_repair,
        "primary_repair_new": repair,
        "helper_byte_exact": True,
        "candidate_full_image_valid": True,
        "restore_full_image_valid": True,
        "limitations": [
            "No resident-loader admission, installation, or nonboot recovery proof.",
            "This patch captures LIGHT/BACK on stable HOME but does not fix delayed USB detach redraw.",
            "LIGHT's Garmin backlight action is unavailable on FlyOS HOME.",
        ],
    }
    return candidate, restore, report


def build() -> dict:
    evidence_bytes = (REPO_ROOT / EVIDENCE_RELATIVE).read_bytes()
    if sha256(evidence_bytes) != EVIDENCE_SHA256:
        raise ValueError("instruction-level evidence receipt changed")
    evidence = json.loads(evidence_bytes)
    if evidence.get("key_case_count") != 34 or evidence.get("frame_stack") != 384:
        raise ValueError("instruction-level evidence gate failed")
    official = (REPO_ROOT / OFFICIAL_RELATIVE).read_bytes()
    prior = (REPO_ROOT / INSTALLED_CANDIDATE_RELATIVE).read_bytes()
    candidate, restore, report = construct_pair(official, prior)
    root = (REPO_ROOT / QUARANTINE_RELATIVE).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("quarantine root is not a directory")
    paths = [root / CANDIDATE_NAME, root / RESTORE_NAME, root / REPORT_NAME]
    if any(path.exists() for path in paths):
        raise FileExistsError("create-new quarantine outputs already exist")
    payloads = [candidate, restore, (json.dumps(report, indent=2) + "\n").encode()]
    created = []
    try:
        for path, payload in zip(paths, payloads):
            with path.open("xb") as f:
                created.append(path)
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            if path.read_bytes() != payload:
                raise IOError("quarantine readback differs from constructed bytes")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    args = parser.parse_args()
    if args.command == "build":
        report = build()
    else:
        candidate, restore, report = construct_pair(
            (REPO_ROOT / OFFICIAL_RELATIVE).read_bytes(),
            (REPO_ROOT / INSTALLED_CANDIDATE_RELATIVE).read_bytes(),
        )
        root = (REPO_ROOT / QUARANTINE_RELATIVE).resolve(strict=True)
        if (root / CANDIDATE_NAME).read_bytes() != candidate or (root / RESTORE_NAME).read_bytes() != restore:
            raise ValueError("quarantine package bytes differ from reconstruction")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
