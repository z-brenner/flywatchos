#!/usr/bin/env python3
"""Build and exactly verify the offline-only FR245 N64 atlas-shell package pair.

The tool emits only synthetic 13.82/13.83 analysis artifacts beneath the fixed
local quarantine.  It has no device discovery, staging, reset, eject, or
Garmin-software integration path.  It is a faithful successor to
``neural_specimen_n64_controls_version_strategy.py``: the byte-level GCD
construction (segment replacement, additive repair, outer/inner checkpoint
recompute, coherent version) is identical; only the pinned atlas-shell payload,
its decision, and the synthetic version chain differ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import build_overlay_candidate  # noqa: E402
import full_image_validator  # noqa: E402
import gcd_inspect  # noqa: E402
import neural_specimen_n64_version_strategy as base_strategy  # noqa: E402
import overlay_version_strategy  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE_DECISION_RELATIVE_PATH = Path(
    "artifacts/analysis/fr245-1370-n64-offline-construction-decision.json"
)
ATLAS_DECISION_RELATIVE_PATH = Path(
    "artifacts/analysis/fr245-1370-n64-atlas-shell-offline-construction-decision.json"
)
TARGET_BUILD_RELATIVE_PATH = Path("artifacts/analysis/fr245-1370-n64-atlas-shell-build")

# Filled only after the atlas-shell build and emulator evidence are final.  An
# unpinned build is deliberately impossible to package.
TARGET_MANIFEST_SHA256 = "e2a2ff3eab53eb258e42c9ac3a5f7574fd24841cda2144775d2052796426dce2"
ATLAS_DECISION_SHA256 = "56177d2d4b562a9873d1ddd9d120c0459947ffeff0605a1dcb74cba0f3c97f92"

REQUIRED_SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"
CANDIDATE_FILENAME = (
    "Forerunner245_1382-flyos-n64-atlas-shell.gcd.analysis-only.DO_NOT_INSTALL"
)
RESTORE_FILENAME = (
    "Forerunner245_1383-official-code-restore-atlas-shell"
    ".gcd.analysis-only.DO_NOT_INSTALL"
)
BUILD_REPORT_FILENAME = "n64-atlas-shell-package-build-1382-1383.json"
STRICT_REPORT_FILENAME = "n64-atlas-shell-package-strict-verification-1382-1383.json"
SHA_LEDGER_FILENAME = "n64-atlas-shell-package-SHA256SUMS.txt"

MAIN_RECORD_ID = 0x02BD
HELPER_RECORD_ID = 0x0505
EXPECTED_HWID = 3076
OFFICIAL_VERSION = 1370
PRIOR_CANDIDATE_VERSION = 1376
PRIOR_RESTORE_VERSION = 1377
CANDIDATE_VERSION = 1382
RESTORE_VERSION = 1383

FLASH_BASE = 0x00003000
DISPLAY_HOOK_VA = 0x00009A20
DISPLAY_HOOK_OFFSET = DISPLAY_HOOK_VA - FLASH_BASE
DISPLAY_HOOK_SIZE = 4
KEY_HOOK_VA = 0x0000FA48
KEY_HOOK_OFFSET = KEY_HOOK_VA - FLASH_BASE
KEY_HOOK_SIZE = 6
PRIMARY_VA = 0x001F6000
PRIMARY_OFFSET = PRIMARY_VA - FLASH_BASE
PRIMARY_ALLOCATION = 0x400
PRIMARY_REPAIR_VA = 0x001F63FF
PRIMARY_REPAIR_OFFSET = PRIMARY_REPAIR_VA - FLASH_BASE
SECONDARY_VA = 0x001FA400
SECONDARY_OFFSET = SECONDARY_VA - FLASH_BASE
SECONDARY_ALLOCATION = 0x800
MAIN_HEADER_VERSION_OFFSET = 0x22C
FINAL_MAIN_REPAIR_OFFSET = 0x4D7FFF

SEGMENT_LAYOUT = {
    "hook": (DISPLAY_HOOK_VA, DISPLAY_HOOK_SIZE, DISPLAY_HOOK_SIZE),
    "keyhook": (KEY_HOOK_VA, KEY_HOOK_SIZE, KEY_HOOK_SIZE),
    "primary": (PRIMARY_VA, 1, PRIMARY_ALLOCATION - 1),
    "secondary": (SECONDARY_VA, 1, SECONDARY_ALLOCATION),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class AtlasInputs:
    official: bytes
    manifest: dict[str, Any]
    manifest_sha256: str
    segments: dict[str, bytes]
    validated_files: dict[str, dict[str, Any]]


def _stream(data: bytes, record_id: int) -> Any:
    return base_strategy._stream(data, record_id)


def _decode_thumb_bw(site: int, encoded: bytes) -> int:
    """Decode the four-byte Thumb-2 unconditional B.W used by the key hook."""
    if len(encoded) != 4:
        raise ValueError("Thumb B.W must be four bytes")
    first = int.from_bytes(encoded[:2], "little")
    second = int.from_bytes(encoded[2:], "little")
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0x9000:
        raise ValueError("instruction is not an unconditional Thumb B.W")
    s = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = 1 ^ (j1 ^ s)
    i2 = 1 ^ (j2 ^ s)
    immediate = (
        (s << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if s:
        immediate -= 1 << 25
    return (site + 4 + immediate) & 0xFFFFFFFF


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != "flyos.fr245.n64-atlas-shell-target.v1":
        raise ValueError("atlas-shell target manifest schema changed")
    if manifest.get("link_and_emulate_allowed") is not True:
        raise ValueError("atlas-shell target is not approved for offline link/emulation")
    if manifest.get("packaging_allowed") is not False:
        raise ValueError("atlas-shell target must remain blocked from live packaging")
    if manifest.get("repair_byte") != PRIMARY_REPAIR_VA:
        raise ValueError("atlas-shell target repair byte changed")
    segments = manifest.get("segments")
    if not isinstance(segments, dict) or set(segments) != set(SEGMENT_LAYOUT):
        raise ValueError("atlas-shell target segment inventory changed")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("atlas-shell target file inventory is absent")
    for name, (start, minimum, maximum) in SEGMENT_LAYOUT.items():
        item = segments[name]
        if set(item) != {"start", "end", "size", "sha256"}:
            raise ValueError(f"atlas-shell target {name} fields changed")
        if (
            item["start"] != start
            or not minimum <= item["size"] <= maximum
            or item["end"] != start + item["size"] - 1
            or files.get(f"{name}.bin") != item["sha256"]
        ):
            raise ValueError(f"atlas-shell target {name} placement changed")
    symbols = manifest.get("symbols")
    if not isinstance(symbols, dict):
        raise ValueError("atlas-shell target symbol inventory is absent")
    if symbols.get("n64_overlay_then_flush", {}).get("address") != PRIMARY_VA:
        raise ValueError("atlas-shell display entry address changed")
    key_target = symbols.get("flyos_key_event", {}).get("address")
    if not isinstance(key_target, int):
        raise ValueError("atlas-shell key entry address is absent")
    if not (
        PRIMARY_VA <= key_target < PRIMARY_VA + PRIMARY_ALLOCATION
        or SECONDARY_VA <= key_target < SECONDARY_VA + SECONDARY_ALLOCATION
    ):
        raise ValueError("atlas-shell key entry is outside the audited allocations")


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} fields changed")


def _validate_atlas_decision(decision: dict[str, Any]) -> None:
    _require_exact_keys(
        decision,
        {
            "schema_version",
            "decision",
            "offline_quarantine_construction_allowed",
            "packaging_allowed",
            "live_staging_allowed",
            "device",
            "containment",
            "prior_decision",
            "target",
            "verification",
            "static_evidence",
            "restrictions",
        },
        "atlas decision",
    )
    if (
        decision["schema_version"] != 1
        or decision["decision"] != "OFFLINE_QUARANTINE_CONSTRUCTION_ALLOWED"
        or decision["offline_quarantine_construction_allowed"] is not True
        or decision["packaging_allowed"] is not False
        or decision["live_staging_allowed"] is not False
    ):
        raise ValueError("atlas decision policy changed")
    if decision["device"] != {
        "model": "Garmin Forerunner 245 non-Music",
        "hwid": EXPECTED_HWID,
        "official_version": OFFICIAL_VERSION,
        "installed_prior_wrapper_version": PRIOR_CANDIDATE_VERSION,
        "reserved_prior_restore_version": PRIOR_RESTORE_VERSION,
        "candidate_version": CANDIDATE_VERSION,
        "restore_version": RESTORE_VERSION,
    }:
        raise ValueError("atlas decision version chain changed")
    if decision["containment"] != {
        "resolved_output_root": str(base_strategy.EXACT_QUARANTINE_ROOT).replace(
            "\\", "/"
        ),
        "required_suffix": REQUIRED_SUFFIX,
        "direct_local_children_only": True,
    }:
        raise ValueError("atlas decision containment changed")
    if set(decision["target"]) != {"manifest", "hook", "keyhook", "primary", "secondary"}:
        raise ValueError("atlas decision target inventory changed")
    if set(decision["verification"]) != {"emulator_report", "evidence_manifest"}:
        raise ValueError("atlas decision verification inventory changed")
    if set(decision["static_evidence"]) != {
        "button_decompile",
        "button_view_decompile",
        "key_queue_decompile",
    }:
        raise ValueError("atlas decision static evidence inventory changed")
    prior = decision["prior_decision"]
    if (
        prior.get("path") != str(BASE_DECISION_RELATIVE_PATH).replace("\\", "/")
        or prior.get("sha256") != base_strategy.DECISION_SHA256
    ):
        raise ValueError("atlas decision prior-decision pin changed")
    if decision["target"]["manifest"].get("sha256") != TARGET_MANIFEST_SHA256:
        raise ValueError("atlas decision manifest pin changed")
    restrictions = decision["restrictions"]
    if not isinstance(restrictions, list) or not restrictions:
        raise ValueError("atlas decision restrictions are absent")
    joined = " ".join(str(item).lower() for item in restrictions)
    for phrase in ("do not stage", "do not install", "no nonboot recovery"):
        if phrase not in joined:
            raise ValueError(f"atlas decision restriction is absent: {phrase}")


def _decision_snapshot(
    repo_root: Path, item: dict[str, Any], label: str
) -> base_strategy.PinnedSnapshot:
    _require_exact_keys(item, {"path", "size", "sha256"}, label)
    path = base_strategy._repo_path(repo_root, item["path"])
    return base_strategy.load_pinned_snapshot(
        path, expected_sha256=item["sha256"], expected_size=item["size"]
    )


def _load_official_base(
    repo_root: Path, base_decision: dict[str, Any]
) -> tuple[bytes, dict[str, dict[str, Any]]]:
    """Load the SHA-pinned official 13.70 GCD from the base N64 decision.

    Only the official image and its extracted main/helper streams are consumed:
    they are the sole inputs to the atlas construction, and they are the exact
    same pinned artifacts the 13.76 controls pair used.  The base decision's
    deeper neural-prior evidence (a 1373/1374 build directory that is not
    reproducible from the current worktree) is not an input to the atlas bytes
    and is deliberately not re-validated here.
    """
    if (
        base_decision.get("packaging_allowed") is not False
        or base_decision.get("live_staging_allowed") is not False
    ):
        raise ValueError("base decision no longer blocks live packaging")
    inputs = base_decision["inputs"]
    official_snapshot = _decision_snapshot(
        repo_root, inputs["official_gcd"], "base official gcd"
    )
    official = official_snapshot.data
    helper, main = build_overlay_candidate._streams(official)
    if sha256(main.decoded) != inputs["official_main"]["sha256"]:
        raise ValueError("official GCD main stream does not match the pinned base main")
    if sha256(helper.decoded) != inputs["official_helper"]["sha256"]:
        raise ValueError("official GCD helper stream does not match the pinned base helper")
    if gcd_inspect._field(main.fields, "hwid") != EXPECTED_HWID:
        raise ValueError("official main HWID is not 3076")
    return official, {"base.official_gcd": official_snapshot.metadata()}


def load_inputs(repo_root: Path) -> AtlasInputs:
    repo_root = repo_root.resolve(strict=True)
    decision_snapshot = base_strategy.load_pinned_snapshot(
        repo_root / ATLAS_DECISION_RELATIVE_PATH,
        expected_sha256=ATLAS_DECISION_SHA256,
    )
    decision = json.loads(decision_snapshot.data.decode("utf-8"))
    _validate_atlas_decision(decision)
    pinned_prior = _decision_snapshot(
        repo_root, decision["prior_decision"], "prior decision"
    )
    if pinned_prior.sha256 != base_strategy.DECISION_SHA256:
        raise ValueError("prior decision does not match the full N64 decision")
    base_decision = json.loads(pinned_prior.data.decode("utf-8"))
    official, base_files = _load_official_base(repo_root, base_decision)
    build = repo_root / TARGET_BUILD_RELATIVE_PATH
    manifest_snapshot = _decision_snapshot(
        repo_root, decision["target"]["manifest"], "atlas manifest"
    )
    manifest = json.loads(manifest_snapshot.data.decode("utf-8"))
    _validate_manifest(manifest)
    segments: dict[str, bytes] = {}
    validated_files = dict(base_files)
    validated_files["atlas.decision"] = decision_snapshot.metadata()
    validated_files["atlas.prior_decision"] = pinned_prior.metadata()
    validated_files["atlas.manifest"] = manifest_snapshot.metadata()
    for name in SEGMENT_LAYOUT:
        snapshot = _decision_snapshot(
            repo_root, decision["target"][name], f"atlas {name}"
        )
        item = manifest["segments"][name]
        if snapshot.path.resolve() != (build / f"{name}.bin").resolve():
            raise ValueError(f"atlas {name} path changed")
        if snapshot.sha256 != item["sha256"] or snapshot.size != item["size"]:
            raise ValueError(f"atlas {name} decision and manifest disagree")
        segments[name] = snapshot.data
        validated_files[f"atlas.{name}"] = snapshot.metadata()
    for group in ("verification", "static_evidence"):
        for name, item in decision[group].items():
            snapshot = _decision_snapshot(repo_root, item, f"atlas {group}.{name}")
            validated_files[f"atlas.{group}.{name}"] = snapshot.metadata()
    hook_target = build_overlay_candidate.decode_thumb_bl(
        DISPLAY_HOOK_VA, segments["hook"]
    )
    if hook_target != PRIMARY_VA:
        raise ValueError("atlas display hook does not branch to primary")
    keyhook = segments["keyhook"]
    if keyhook[4:] != b"\x00\xbf":
        raise ValueError("atlas key hook does not end in a Thumb NOP")
    if _decode_thumb_bw(KEY_HOOK_VA, keyhook[:4]) != manifest["symbols"]["flyos_key_event"]["address"]:
        raise ValueError("atlas key hook target does not match the manifest")
    return AtlasInputs(
        official=official,
        manifest=manifest,
        manifest_sha256=manifest_snapshot.sha256,
        segments=segments,
        validated_files=validated_files,
    )


def _allowed_decoded(offset: int) -> bool:
    return (
        MAIN_HEADER_VERSION_OFFSET <= offset < MAIN_HEADER_VERSION_OFFSET + 2
        or DISPLAY_HOOK_OFFSET <= offset < DISPLAY_HOOK_OFFSET + DISPLAY_HOOK_SIZE
        or KEY_HOOK_OFFSET <= offset < KEY_HOOK_OFFSET + KEY_HOOK_SIZE
        or PRIMARY_OFFSET <= offset < PRIMARY_OFFSET + PRIMARY_ALLOCATION
        or SECONDARY_OFFSET <= offset < SECONDARY_OFFSET + SECONDARY_ALLOCATION
        or offset == FINAL_MAIN_REPAIR_OFFSET
    )


def _construct_candidate(inputs: AtlasInputs) -> tuple[bytes, dict[str, Any]]:
    official = inputs.official
    official_helper, official_main = build_overlay_candidate._streams(official)
    del official_helper
    if official_main.decoded[
        PRIMARY_OFFSET : PRIMARY_OFFSET + PRIMARY_ALLOCATION
    ] != b"\xff" * PRIMARY_ALLOCATION:
        raise ValueError("official primary allocation is not erased")
    if official_main.decoded[
        SECONDARY_OFFSET : SECONDARY_OFFSET + SECONDARY_ALLOCATION
    ] != b"\xff" * SECONDARY_ALLOCATION:
        raise ValueError("official secondary allocation is not erased")
    if official_main.decoded[DISPLAY_HOOK_OFFSET : DISPLAY_HOOK_OFFSET + 4] != bytes.fromhex(
        "04f0c0fb"
    ):
        raise ValueError("official display hook bytes changed")
    if official_main.decoded[KEY_HOOK_OFFSET : KEY_HOOK_OFFSET + 6] != bytes.fromhex(
        "30b5c0ebc002"
    ):
        raise ValueError("official key hook prologue changed")

    primary = bytearray(official_main.decoded[
        PRIMARY_OFFSET : PRIMARY_OFFSET + PRIMARY_ALLOCATION
    ])
    primary[: len(inputs.segments["primary"])] = inputs.segments["primary"]
    secondary = bytearray(official_main.decoded[
        SECONDARY_OFFSET : SECONDARY_OFFSET + SECONDARY_ALLOCATION
    ])
    secondary[: len(inputs.segments["secondary"])] = inputs.segments["secondary"]

    replacements = (
        (DISPLAY_HOOK_OFFSET, inputs.segments["hook"]),
        (KEY_HOOK_OFFSET, inputs.segments["keyhook"]),
        (PRIMARY_OFFSET, bytes(primary)),
        (SECONDARY_OFFSET, bytes(secondary)),
    )
    mutated = official
    for offset, replacement in replacements:
        mutated_main = _stream(mutated, MAIN_RECORD_ID)
        mutated = build_overlay_candidate._replace_decoded_slice(
            mutated, mutated_main, offset, replacement
        )
    mutated_main = _stream(mutated, MAIN_RECORD_ID)
    remainder = sum(mutated_main.decoded) & 0xFF
    old_repair = mutated_main.decoded[PRIMARY_REPAIR_OFFSET]
    new_repair = (old_repair - remainder) & 0xFF
    mutated = build_overlay_candidate._replace_decoded_slice(
        mutated, mutated_main, PRIMARY_REPAIR_OFFSET, bytes([new_repair])
    )
    candidate, version_patch = overlay_version_strategy._set_main_version(
        recompute_checkpoints(mutated), CANDIDATE_VERSION
    )
    return candidate, {
        "primary_additive": {
            "runtime_address": f"0x{PRIMARY_REPAIR_VA:08x}",
            "old_byte": old_repair,
            "new_byte": new_repair,
        },
        "coherent_version": version_patch,
    }


def _construct_restore(official: bytes) -> tuple[bytes, dict[str, Any]]:
    return overlay_version_strategy._set_main_version(official, RESTORE_VERSION)


def _raw_allowlist(official: bytes, official_main: Any) -> tuple[dict[int, int], set[int], int]:
    return (
        base_strategy._main_raw_locations(official, official_main),
        base_strategy._checkpoint_body_offsets(official),
        overlay_version_strategy._descriptor_field_raw_offset(
            official, MAIN_RECORD_ID, (0x0D, 0x10)
        ),
    )


def _artifact_report(
    label: str,
    inputs: AtlasInputs,
    output: bytes,
    expected_version: int,
    repairs: dict[str, Any],
) -> dict[str, Any]:
    official = inputs.official
    official_main = _stream(official, MAIN_RECORD_ID)
    output_main = _stream(output, MAIN_RECORD_ID)
    official_helper = _stream(official, HELPER_RECORD_ID)
    output_helper = _stream(output, HELPER_RECORD_ID)
    decoded_changes = base_strategy._changed_offsets(
        official_main.decoded, output_main.decoded
    )
    raw_changes = base_strategy._changed_offsets(official, output)
    raw_to_decoded, checkpoints, descriptor_version_offset = _raw_allowlist(
        official, official_main
    )
    raw_allowed = all(
        offset == descriptor_version_offset
        or offset in checkpoints
        or (offset in raw_to_decoded and _allowed_decoded(raw_to_decoded[offset]))
        for offset in raw_changes
    )
    is_candidate = label == "candidate"
    segments = inputs.segments
    expected_restore = bytearray(official_main.decoded)
    expected_restore[
        MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
    ] = expected_version.to_bytes(2, "little")
    expected_restore[-1] = output_main.decoded[-1]
    validation = full_image_validator.validate_bytes(output, label)
    checks = {
        "same_output_size": len(output) == len(official),
        "record_layout_exact_official": base_strategy._record_layout(output)
        == base_strategy._record_layout(official),
        "main_stream_length_exact_official": output_main.declared_length
        == official_main.declared_length,
        "helper_stream_exact_official": output_helper.decoded
        == official_helper.decoded,
        "helper_descriptor_exact_official": output_helper.fields
        == official_helper.fields,
        "hwid_3076": gcd_inspect._field(output_main.fields, "hwid")
        == EXPECTED_HWID,
        "descriptor_header_version_coherent": output_main.software_version
        == expected_version
        and int.from_bytes(
            output_main.decoded[
                MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
            ],
            "little",
        )
        == expected_version,
        "descriptor_force_field_zero": output_main.erase_flag == 0,
        "decoded_changes_confined_to_exact_allowlist": all(
            _allowed_decoded(offset) for offset in decoded_changes
        ),
        "raw_changes_confined_to_exact_allowlist": raw_allowed,
        "main_additive_sum_zero": sum(output_main.decoded) & 0xFF == 0,
        "outer_checkpoints_valid": validation["outer_gcd"][
            "all_prefix_sums_zero_mod_256"
        ],
        "full_image_validator_pass": validation[
            "confirmed_full_image_checks_pass"
        ],
        "display_hook_exact": output_main.decoded[
            DISPLAY_HOOK_OFFSET : DISPLAY_HOOK_OFFSET + DISPLAY_HOOK_SIZE
        ]
        == (segments["hook"] if is_candidate else official_main.decoded[
            DISPLAY_HOOK_OFFSET : DISPLAY_HOOK_OFFSET + DISPLAY_HOOK_SIZE
        ]),
        "key_hook_exact": output_main.decoded[
            KEY_HOOK_OFFSET : KEY_HOOK_OFFSET + KEY_HOOK_SIZE
        ]
        == (segments["keyhook"] if is_candidate else official_main.decoded[
            KEY_HOOK_OFFSET : KEY_HOOK_OFFSET + KEY_HOOK_SIZE
        ]),
        "primary_segment_or_restore_exact": output_main.decoded[
            PRIMARY_OFFSET : PRIMARY_OFFSET + len(segments["primary"])
        ]
        == (segments["primary"] if is_candidate else official_main.decoded[
            PRIMARY_OFFSET : PRIMARY_OFFSET + len(segments["primary"])
        ]),
        "secondary_segment_or_restore_exact": output_main.decoded[
            SECONDARY_OFFSET : SECONDARY_OFFSET + len(segments["secondary"])
        ]
        == (segments["secondary"] if is_candidate else official_main.decoded[
            SECONDARY_OFFSET : SECONDARY_OFFSET + len(segments["secondary"])
        ]),
        "primary_additive_repair_or_restore_exact": output_main.decoded[
            PRIMARY_REPAIR_OFFSET
        ]
        == (
            repairs["primary_additive"]["new_byte"]
            if is_candidate
            else official_main.decoded[PRIMARY_REPAIR_OFFSET]
        ),
        "allocation_padding_or_restore_exact": (
            output_main.decoded[
                PRIMARY_OFFSET + len(segments["primary"]) : PRIMARY_REPAIR_OFFSET
            ]
            == official_main.decoded[
                PRIMARY_OFFSET + len(segments["primary"]) : PRIMARY_REPAIR_OFFSET
            ]
            and output_main.decoded[
                SECONDARY_OFFSET + len(segments["secondary"]) :
                SECONDARY_OFFSET + SECONDARY_ALLOCATION
            ]
            == official_main.decoded[
                SECONDARY_OFFSET + len(segments["secondary"]) :
                SECONDARY_OFFSET + SECONDARY_ALLOCATION
            ]
        ),
        "complete_official_restore": True
        if is_candidate
        else output_main.decoded == bytes(expected_restore),
    }
    if not all(checks.values()):
        raise AssertionError(f"{label} package checks failed: {checks}")
    return {
        "filename": CANDIDATE_FILENAME if is_candidate else RESTORE_FILENAME,
        "purpose": (
            "offline-only synthetic 13.82 N64 atlas-shell overlay"
            if is_candidate
            else "offline-only synthetic 13.83 wrapper carrying official 13.70 application and resources"
        ),
        "size": len(output),
        "sha256": sha256(output),
        "main_sha256": sha256(output_main.decoded),
        "software_version": output_main.software_version,
        "header_version": int.from_bytes(
            output_main.decoded[
                MAIN_HEADER_VERSION_OFFSET : MAIN_HEADER_VERSION_OFFSET + 2
            ],
            "little",
        ),
        "segments": {
            name: {
                "runtime_start": f"0x{SEGMENT_LAYOUT[name][0]:08x}",
                "size": len(data),
                "sha256": sha256(data),
            }
            for name, data in segments.items()
        },
        "repairs": repairs,
        "decoded_changed_ranges": base_strategy._diff_ranges(
            official_main.decoded, output_main.decoded
        ),
        "raw_changed_ranges": base_strategy._diff_ranges(official, output),
        "checks": checks,
        "full_image_validation": validation,
    }


def construct_pair(repo_root: Path) -> tuple[bytes, bytes, dict[str, Any]]:
    inputs = load_inputs(repo_root)
    candidate, candidate_repairs = _construct_candidate(inputs)
    restore, restore_repairs = _construct_restore(inputs.official)
    candidate_report = _artifact_report(
        "candidate", inputs, candidate, CANDIDATE_VERSION, candidate_repairs
    )
    restore_report = _artifact_report(
        "restore", inputs, restore, RESTORE_VERSION, {"coherent_version": restore_repairs}
    )
    report = {
        "schema_version": 1,
        "tool": "tools/garmin-firmware/neural_specimen_n64_atlas_shell_version_strategy.py",
        "verdict": "PASS_OFFLINE_CONSTRUCTION",
        "target_manifest_sha256": inputs.manifest_sha256,
        "validated_inputs": inputs.validated_files,
        "policy": {
            "offline_quarantine_construction_allowed": True,
            "packaging_allowed": False,
            "live_staging_allowed": False,
            "feasibility": "YELLOW",
        },
        "version_chain": {
            "official": OFFICIAL_VERSION,
            "prior_candidate": PRIOR_CANDIDATE_VERSION,
            "prior_reserved_restore": PRIOR_RESTORE_VERSION,
            "candidate": CANDIDATE_VERSION,
            "restore": RESTORE_VERSION,
        },
        "candidate": candidate_report,
        "restore": restore_report,
        "limitations": [
            "The artifacts are offline analysis objects and are explicitly blocked from live staging.",
            "The restore requires GarminOS and normal USB update service to remain bootable.",
            "No Forerunner 245 nonboot recovery path is known.",
        ],
    }
    return candidate, restore, report


def verify_exact(
    repo_root: Path,
    candidate: bytes,
    restore: bytes,
) -> dict[str, Any]:
    expected_candidate, expected_restore, build_report = construct_pair(repo_root)
    checks = {
        "candidate_byte_exact_reconstruction": candidate == expected_candidate,
        "restore_byte_exact_reconstruction": restore == expected_restore,
        "candidate_sha256_exact_reconstruction": sha256(candidate)
        == sha256(expected_candidate),
        "restore_sha256_exact_reconstruction": sha256(restore)
        == sha256(expected_restore),
        "candidate_full_image_validator_pass": full_image_validator.validate_bytes(
            candidate, CANDIDATE_FILENAME
        )["confirmed_full_image_checks_pass"],
        "restore_full_image_validator_pass": full_image_validator.validate_bytes(
            restore, RESTORE_FILENAME
        )["confirmed_full_image_checks_pass"],
        "packaging_allowed_remains_false": build_report["policy"][
            "packaging_allowed"
        ]
        is False,
        "live_staging_allowed_remains_false": build_report["policy"][
            "live_staging_allowed"
        ]
        is False,
    }
    return {
        "schema_version": 1,
        "tool": build_report["tool"],
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "actual": {
            "candidate": {"size": len(candidate), "sha256": sha256(candidate)},
            "restore": {"size": len(restore), "sha256": sha256(restore)},
        },
        "expected": {
            "candidate": {
                "size": len(expected_candidate),
                "sha256": sha256(expected_candidate),
            },
            "restore": {
                "size": len(expected_restore),
                "sha256": sha256(expected_restore),
            },
        },
        "build_evidence": build_report,
    }


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def _exact_roots(repo_root: Path) -> tuple[Path, Path]:
    return base_strategy._validate_exact_roots(repo_root.resolve(strict=True))


def _require_new_fixed_output(path: Path, root: Path, allowed_names: set[str]) -> None:
    base_strategy._reject_lexical_traversal(path)
    base_strategy._reject_remote_device_or_d(path)
    base_strategy._reject_reparse_chain(path)
    if path.resolve(strict=False).parent != root.resolve(strict=True):
        raise ValueError("output is outside the exact offline artifact root")
    if path.name not in allowed_names:
        raise ValueError("unexpected offline artifact filename")
    if path.exists():
        base_strategy._reject_hardlink(path)
        raise ValueError(f"output already exists; overwrite is forbidden: {path}")


def build_to_quarantine(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    quarantine, analysis = _exact_roots(repo_root)
    candidate_path = quarantine / CANDIDATE_FILENAME
    restore_path = quarantine / RESTORE_FILENAME
    build_report_path = analysis / BUILD_REPORT_FILENAME
    strict_report_path = analysis / STRICT_REPORT_FILENAME
    ledger_path = analysis / SHA_LEDGER_FILENAME
    _require_new_fixed_output(
        candidate_path, quarantine, {CANDIDATE_FILENAME, RESTORE_FILENAME}
    )
    _require_new_fixed_output(
        restore_path, quarantine, {CANDIDATE_FILENAME, RESTORE_FILENAME}
    )
    report_names = {
        BUILD_REPORT_FILENAME,
        STRICT_REPORT_FILENAME,
        SHA_LEDGER_FILENAME,
    }
    for path in (build_report_path, strict_report_path, ledger_path):
        _require_new_fixed_output(path, analysis, report_names)
    candidate, restore, build_report = construct_pair(repo_root)
    strict_report = verify_exact(repo_root, candidate, restore)
    if strict_report["verdict"] != "PASS":
        raise AssertionError("in-memory exact verification failed")
    build_report["outputs"] = {
        "candidate": str(candidate_path),
        "restore": str(restore_path),
        "build_report": str(build_report_path),
        "strict_report": str(strict_report_path),
        "sha256_ledger": str(ledger_path),
    }
    build_blob = _json_bytes(build_report)
    strict_blob = _json_bytes(strict_report)
    ledger_blob = "".join(
        f"{sha256(data)}  {name}\n"
        for name, data in sorted(
            {
                CANDIDATE_FILENAME: candidate,
                RESTORE_FILENAME: restore,
                BUILD_REPORT_FILENAME: build_blob,
                STRICT_REPORT_FILENAME: strict_blob,
            }.items()
        )
    ).encode("ascii")
    base_strategy.write_transaction(
        (
            (candidate_path, candidate),
            (restore_path, restore),
            (build_report_path, build_blob),
            (strict_report_path, strict_blob),
            (ledger_path, ledger_blob),
        )
    )
    return {
        "verdict": "PASS_OFFLINE_CONSTRUCTION",
        "candidate": {"path": str(candidate_path), "sha256": sha256(candidate)},
        "restore": {"path": str(restore_path), "sha256": sha256(restore)},
        "reports": {
            BUILD_REPORT_FILENAME: sha256(build_blob),
            STRICT_REPORT_FILENAME: sha256(strict_blob),
            SHA_LEDGER_FILENAME: sha256(ledger_blob),
        },
    }


def verify_written_pair(repo_root: Path) -> dict[str, Any]:
    quarantine, _analysis = _exact_roots(repo_root)
    candidate = (quarantine / CANDIDATE_FILENAME).read_bytes()
    restore = (quarantine / RESTORE_FILENAME).read_bytes()
    return verify_exact(repo_root, candidate, restore)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify", "construct-report"))
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    args = parser.parse_args()
    if args.command == "build":
        result = build_to_quarantine(args.repo_root)
    elif args.command == "verify":
        result = verify_written_pair(args.repo_root)
    else:
        candidate, restore, report = construct_pair(args.repo_root)
        result = {
            "verdict": report["verdict"],
            "candidate_sha256": sha256(candidate),
            "restore_sha256": sha256(restore),
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
