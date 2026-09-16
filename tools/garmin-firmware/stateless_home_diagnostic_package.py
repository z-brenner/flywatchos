#!/usr/bin/env python3
"""Construct/verify an OFFLINE-ONLY FR245 13.78/13.79 diagnostic pair.

This is GarminOS-resident instrumentation, not replacement firmware. Outputs
are fixed, create-new, analysis-only files under the local quarantine. No
device, Garmin updater, or staging interface is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_overlay_candidate as overlay_build  # noqa: E402
import full_image_validator  # noqa: E402
import gcd_inspect  # noqa: E402
import neural_specimen_n64_version_strategy as custody  # noqa: E402
import overlay_version_strategy as versioning  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUN = Path("artifacts/firmware/analysis/atlas-shell-runs/round6-home-only-diagnostic")
SRC = Path("tools/garmin-firmware/stateless_home_diagnostic")
OFFICIAL = Path("artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD")
PRIOR = Path("artifacts/firmware/quarantine/Forerunner245_1376-flyos-neural-specimen-n64-controls.gcd.analysis-only.DO_NOT_INSTALL")
STAGE = Path("tools/live-proof/stage-gupdate.ps1")
PINNED = {
    OFFICIAL: (5120675, "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"),
    PRIOR: (5120675, "9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de"),
    STAGE: (None, "8ffae26cd24d83755186a33cd9c6d779887564da4622594c0a8b0305c4ec65b3"),
    SRC / "probe.c": (7836, "b94533b210e72c074616d7f3d1a777fc18eeacfa1d9bfbe4c9bbf4601207b688"),
    SRC / "probe.S": (258, "952d886e2bc79383cabd36fdc85a6a6ce4dcb96a8611d8d5b43322b95c6b5f5a"),
    SRC / "probe.ld": (536, "a1bae3cf747084621a87e519b23a8cbca9b26beac1b9f4e90bf9a4c5d17b5606"),
    RUN / "probe.c": (7836, "b94533b210e72c074616d7f3d1a777fc18eeacfa1d9bfbe4c9bbf4601207b688"),
    RUN / "probe.S": (258, "952d886e2bc79383cabd36fdc85a6a6ce4dcb96a8611d8d5b43322b95c6b5f5a"),
    RUN / "probe.ld": (536, "a1bae3cf747084621a87e519b23a8cbca9b26beac1b9f4e90bf9a4c5d17b5606"),
    RUN / "unicorn_test.py": (14064, "2507873ad13824a91bf9bd21a6da16272d0cf4a36e40331910111913b281d80b"),
    RUN / "unicorn-results-home-seeded.json": (11947, "b323e10de231c19cf6b505ebd04a64ef231618d7dce32adfd1572b414b5e03ae"),
    RUN / "build-3/hook-display.bin": (4, "e121cf4022946627b5e0f510bb3a51c26b560e6bf6d0d0c2110981ada161b170"),
    RUN / "build-3/payload.bin": (1066, "38ec0e691aaa24e28e3eac734eed7051eb6f599305696410346c608bb1e62a94"),
}
SUFFIX = ".gcd.analysis-only.DO_NOT_INSTALL"
CANDIDATE_NAME = "Forerunner245_1378-home-only-stateless-diagnostic" + SUFFIX
RESTORE_NAME = "Forerunner245_1379-official-code-restore-diagnostic" + SUFFIX
REPORT_NAME = "stateless-home-diagnostic-package-1378-1379.json"
VERIFY_NAME = "stateless-home-diagnostic-strict-verification-1378-1379.json"
SHA_NAME = "stateless-home-diagnostic-1378-1379-SHA256SUMS.txt"
FLASH_BASE = 0x3000
HOOK_VA = 0x9A20
HOOK = HOOK_VA - FLASH_BASE
KEY = 0xFA48 - FLASH_BASE
PRIMARY = 0x1F6000 - FLASH_BASE
PRIMARY_SIZE = 0x400
REPAIR = 0x1F63FF - FLASH_BASE
SECONDARY = 0x1FA400 - FLASH_BASE
SECONDARY_SIZE = 0x800
HEADER_VERSION = 0x22C
FINAL_REPAIR = 0x4D7FFF


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Inputs:
    official: bytes
    prior: bytes
    hook: bytes
    payload: bytes
    manifest: dict[str, dict[str, object]]


def _snapshot(root: Path, relative: Path) -> bytes:
    size, digest = PINNED[relative]
    # This worktree has an intentional ignored junction to the original,
    # immutable private artifact store. Resolve it before custody's reparse
    # check; constrain the result to that exact store.
    path = (root / relative).resolve(strict=True)
    if relative.parts[:2] == ("artifacts", "firmware"):
        private_root = (root / "artifacts/firmware").resolve(strict=True)
        if not path.is_relative_to(private_root):
            raise ValueError("private input escaped the fixed local artifact store")
    return custody.load_pinned_snapshot(path, expected_sha256=digest, expected_size=size).data


def _stream(data: bytes, record_id: int):
    return versioning._stream(data, record_id)


def _compile_exact(root: Path, hook: bytes, payload: bytes) -> None:
    """Rebuild from public sources and compare the emitted flash sections."""
    bin_dir = root / "tools/arm-toolchain/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi/bin"
    gcc = bin_dir / "arm-none-eabi-gcc.exe"
    objcopy = bin_dir / "arm-none-eabi-objcopy.exe"
    if not gcc.is_file() or not objcopy.is_file():
        raise ValueError("pinned Arm toolchain is absent")
    version = subprocess.run([str(gcc), "--version"], capture_output=True, text=True, check=True).stdout
    if "15.2.1" not in version:
        raise ValueError("Arm toolchain version changed")
    common = ["-mcpu=cortex-m4", "-mthumb", "-mfloat-abi=soft", "-Os", "-ffreestanding",
              "-fno-builtin", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
              "-ffunction-sections", "-fdata-sections", "-fstack-usage", "-Wall", "-Wextra", "-Werror"]
    with tempfile.TemporaryDirectory(dir=root / RUN, prefix="rebuild-") as temporary:
        out = Path(temporary)
        asm, cobj, elf = out / "probe_asm.o", out / "probe_c.o", out / "probe.elf"
        for command in (
            [str(gcc), *common, "-c", str(root / SRC / "probe.S"), "-o", str(asm)],
            [str(gcc), *common, "-c", str(root / SRC / "probe.c"), "-o", str(cobj)],
            [str(gcc), *common, str(asm), str(cobj), "-nostdlib", "-Wl,--gc-sections",
             "-Wl,--no-undefined", "-T" + str(root / SRC / "probe.ld"), "-o", str(elf)],
            [str(objcopy), "--dump-section", ".hook_display=" + str(out / "hook.bin"),
             "--dump-section", ".payload=" + str(out / "payload.bin"), str(elf)],
        ):
            subprocess.run(command, check=True, capture_output=True, text=True)
        if (out / "hook.bin").read_bytes() != hook or (out / "payload.bin").read_bytes() != payload:
            raise ValueError("public source rebuild differs from pinned flash sections")


def load_inputs(root: Path = ROOT, *, rebuild: bool = True) -> Inputs:
    root = root.resolve(strict=True)
    if root != ROOT.resolve(strict=True):
        raise ValueError("repository root changed")
    snapshots = {str(path): {"size": len(_snapshot(root, path)), "sha256": digest}
                 for path, (_size, digest) in PINNED.items()}
    official = _snapshot(root, OFFICIAL)
    prior = _snapshot(root, PRIOR)
    hook = _snapshot(root, RUN / "build-3/hook-display.bin")
    payload = _snapshot(root, RUN / "build-3/payload.bin")
    evidence = json.loads(_snapshot(root, RUN / "unicorn-results-home-seeded.json"))
    results = evidence.get("results", [])
    if evidence.get("cases") != 49 or evidence.get("all_passed") is not True or len(results) != 49:
        raise ValueError("49-case emulator receipt missing")
    native = [r for r in results if r.get("class") in ("N", "I")]
    if len(native) < 10 or any(r.get("fb_writes") != 0 or r.get("flush_calls") != 1 for r in native):
        raise ValueError("native/invalid framebuffer pass-through receipt missing")
    if not any(r.get("name") == "null_framebuffer" and r.get("fb_writes") == 0 for r in results):
        raise ValueError("null framebuffer pass-through receipt missing")
    if len(hook) != 4 or overlay_build.decode_thumb_bl(HOOK_VA, hook) != 0x1FA400:
        raise ValueError("diagnostic hook does not branch to secondary entry")
    if not 0 < len(payload) <= SECONDARY_SIZE:
        raise ValueError("diagnostic payload does not fit secondary allocation")
    stage = _snapshot(root, STAGE).decode("utf-8")
    if any(name in stage for name in (CANDIDATE_NAME, RESTORE_NAME)):
        raise ValueError("staging script references diagnostic package")
    if not re.search(r"\[ValidateSet\('Candidate1369'.*\)\]", stage):
        raise ValueError("staging mode lock could not be established")
    if rebuild:
        _compile_exact(root, hook, payload)
    return Inputs(official, prior, hook, payload, snapshots)


def _construct_candidate(inputs: Inputs) -> tuple[bytes, dict[str, object]]:
    official = inputs.official
    main = _stream(official, 0x02BD)
    prior = _stream(inputs.prior, 0x02BD)
    if sha(main.decoded) != versioning.OFFICIAL_MAIN_SHA256:
        raise ValueError("official main image changed")
    if main.decoded[HOOK:HOOK + 4] != bytes.fromhex("04f0c0fb"):
        raise ValueError("official display call changed")
    if main.decoded[KEY:KEY + 6] != bytes.fromhex("30b5c0ebc002"):
        raise ValueError("official key prologue changed")
    if main.decoded[PRIMARY:PRIMARY + PRIMARY_SIZE] != b"\xff" * PRIMARY_SIZE:
        raise ValueError("official primary allocation changed")
    if main.decoded[SECONDARY:SECONDARY + SECONDARY_SIZE] != b"\xff" * SECONDARY_SIZE:
        raise ValueError("official secondary allocation changed")
    if prior.decoded[KEY:KEY + 6] == main.decoded[KEY:KEY + 6] or prior.decoded[PRIMARY:PRIMARY + PRIMARY_SIZE] == main.decoded[PRIMARY:PRIMARY + PRIMARY_SIZE]:
        raise ValueError("prior package is not the expected hooked 13.76 baseline")
    candidate = official
    for offset, blob in ((HOOK, inputs.hook), (SECONDARY, inputs.payload)):
        candidate = overlay_build._replace_decoded_slice(candidate, _stream(candidate, 0x02BD), offset, blob)
    intermediate = _stream(candidate, 0x02BD)
    original_repair = intermediate.decoded[REPAIR]
    new_repair = (original_repair - sum(intermediate.decoded)) & 0xff
    candidate = overlay_build._replace_decoded_slice(candidate, intermediate, REPAIR, bytes((new_repair,)))
    candidate, version_repair = versioning._set_main_version(recompute_checkpoints(candidate), 1378)
    return candidate, {"additive_repair_address": "0x001f63ff", "old": original_repair,
                       "new": new_repair, "coherent_version": version_repair}


def _allowed_decoded(offset: int, candidate: bool) -> bool:
    return (HEADER_VERSION <= offset < HEADER_VERSION + 2 or offset == FINAL_REPAIR or
            (candidate and (HOOK <= offset < HOOK + 4 or offset == REPAIR or
                            SECONDARY <= offset < SECONDARY + SECONDARY_SIZE)))


def _validate_output(label: str, official: bytes, output: bytes, version: int,
                     *, candidate: bool, hook: bytes = b"", payload: bytes = b"") -> dict[str, object]:
    original_main, main = _stream(official, 0x02BD), _stream(output, 0x02BD)
    original_helper, helper = _stream(official, 0x0505), _stream(output, 0x0505)
    decoded_changes = custody._changed_offsets(original_main.decoded, main.decoded)
    raw_changes = custody._changed_offsets(official, output)
    raw_map = custody._main_raw_locations(official, original_main)
    checkpoint_bytes = custody._checkpoint_body_offsets(official)
    descriptor = versioning._descriptor_field_raw_offset(official, 0x02BD, (0x0D, 0x10))
    expected = bytearray(original_main.decoded)
    expected[HEADER_VERSION:HEADER_VERSION + 2] = version.to_bytes(2, "little")
    expected[FINAL_REPAIR] = main.decoded[FINAL_REPAIR]
    if candidate:
        expected[HOOK:HOOK + 4] = hook
        expected[SECONDARY:SECONDARY + len(payload)] = payload
        expected[REPAIR] = main.decoded[REPAIR]
    validation = full_image_validator.validate_bytes(output, label)
    checks = {
        "same_package_size": len(output) == len(official),
        "same_record_layout": custody._record_layout(output) == custody._record_layout(official),
        "helper_bytes_and_descriptor_official": helper.decoded == original_helper.decoded and helper.fields == original_helper.fields,
        "hardware_id_3076": gcd_inspect._field(main.fields, "hwid") == 3076,
        "coherent_version": main.software_version == version and int.from_bytes(main.decoded[HEADER_VERSION:HEADER_VERSION + 2], "little") == version,
        "normal_update_field": main.erase_flag == 0,
        "decoded_exact_reconstruction": main.decoded == bytes(expected),
        "decoded_diff_allowlisted": all(_allowed_decoded(o, candidate) for o in decoded_changes),
        "raw_diff_allowlisted": all(o == descriptor or o in checkpoint_bytes or
                                    (o in raw_map and _allowed_decoded(raw_map[o], candidate)) for o in raw_changes),
        "key_hook_official": main.decoded[KEY:KEY + 6] == original_main.decoded[KEY:KEY + 6],
        "primary_official_except_additive_repair": main.decoded[PRIMARY:REPAIR] == original_main.decoded[PRIMARY:REPAIR],
        "secondary_tail_official": main.decoded[SECONDARY + len(payload):SECONDARY + SECONDARY_SIZE] == original_main.decoded[SECONDARY + len(payload):SECONDARY + SECONDARY_SIZE],
        "full_image_validator": validation["confirmed_full_image_checks_pass"],
    }
    if not all(checks.values()):
        raise ValueError(f"{label} failed exhaustive validation: {checks}")
    return {"size": len(output), "sha256": sha(output), "main_sha256": sha(main.decoded),
            "version": version, "checks": checks,
            "decoded_diff_ranges": custody._diff_ranges(original_main.decoded, main.decoded),
            "raw_diff_ranges": custody._diff_ranges(official, output), "full_image": validation}


def construct_pair(root: Path = ROOT, *, rebuild: bool = True) -> tuple[bytes, bytes, dict[str, object]]:
    inputs = load_inputs(root, rebuild=rebuild)
    candidate, repairs = _construct_candidate(inputs)
    restore, restore_repairs = versioning._set_main_version(inputs.official, 1379)
    if not (1370 < 1376 < 1377 < 1378 < 1379):
        raise ValueError("version chain changed")
    candidate_report = _validate_output("candidate", inputs.official, candidate, 1378,
                                        candidate=True, hook=inputs.hook, payload=inputs.payload)
    restore_report = _validate_output("restore", inputs.official, restore, 1379, candidate=False)
    return candidate, restore, {
        "schema": "flyos.fr245.stateless-home-diagnostic-package.v1",
        "verdict": "PASS_OFFLINE_ONLY",
        "policy": {"live_staging_allowed": False, "device_ready_proposal": False},
        "description": "GarminOS-resident HOME-only diagnostic; not FlyOS replacement or evidence of update acceptance",
        "version_chain": [1370, 1376, 1377, 1378, 1379],
        "pinned_sources": inputs.manifest,
        "candidate": {**candidate_report, "repairs": repairs, "hook_sha256": sha(inputs.hook),
                      "payload_size": len(inputs.payload), "payload_sha256": sha(inputs.payload)},
        "restore": {**restore_report, "repairs": restore_repairs},
        "limitations": ["NON_HOME/INVALID pass through unchanged, so no native-view class appears on glass.",
                        "A frozen HOME panel cannot distinguish no flush from native occlusion.",
                        "Resident-loader acceptance and nonboot recovery are unknown."],
    }


def verify_exact(candidate: bytes, restore: bytes, root: Path = ROOT, *, rebuild: bool = True) -> dict[str, object]:
    expected_candidate, expected_restore, report = construct_pair(root, rebuild=rebuild)
    checks = {"candidate_byte_exact": candidate == expected_candidate,
              "restore_byte_exact": restore == expected_restore,
              "candidate_full_image": full_image_validator.validate_bytes(candidate)["confirmed_full_image_checks_pass"],
              "restore_full_image": full_image_validator.validate_bytes(restore)["confirmed_full_image_checks_pass"],
              "staging_locked": report["policy"]["live_staging_allowed"] is False}
    return {"verdict": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "candidate_sha256": sha(candidate), "restore_sha256": sha(restore)}


def _output_paths(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    quarantine, analysis = custody._validate_exact_roots(root.resolve(strict=True))
    paths = (quarantine / CANDIDATE_NAME, quarantine / RESTORE_NAME,
             analysis / REPORT_NAME, analysis / VERIFY_NAME, analysis / SHA_NAME)
    for path in paths:
        _require_new_output(path, quarantine if path.parent == quarantine else analysis)
    if not CANDIDATE_NAME.endswith(SUFFIX) or not RESTORE_NAME.endswith(SUFFIX):
        raise ValueError("output suffix changed")
    return paths


def _require_new_output(path: Path, expected_root: Path) -> None:
    custody._reject_lexical_traversal(path)
    custody._reject_remote_device_or_d(path)
    custody._reject_reparse_chain(path)
    if path.resolve(strict=False).parent != expected_root.resolve(strict=True):
        raise ValueError("output escaped exact local quarantine/analysis root")
    if path.exists():
        raise ValueError(f"create-new output collision: {path}")


def build_to_quarantine(root: Path = ROOT) -> dict[str, object]:
    paths = _output_paths(root)
    candidate, restore, report = construct_pair(root)
    verified = verify_exact(candidate, restore, root, rebuild=False)
    if verified["verdict"] != "PASS":
        raise ValueError("in-memory strict verification failed")
    blobs = [(paths[0], candidate), (paths[1], restore),
             (paths[2], (json.dumps(report, indent=2) + "\n").encode()),
             (paths[3], (json.dumps(verified, indent=2) + "\n").encode())]
    ledger = "".join(f"{sha(data)}  {path.name}\n" for path, data in blobs).encode("ascii")
    custody.write_transaction([*blobs, (paths[4], ledger)])
    try:
        for relative in PINNED:
            _snapshot(root, relative)
        for path, data in [*blobs, (paths[4], ledger)]:
            if path.read_bytes() != data:
                raise ValueError(f"post-write output changed: {path}")
    except BaseException:
        for path in reversed(paths):
            if path.exists():
                path.unlink()
        raise
    return {"verdict": "PASS_OFFLINE_ONLY", "candidate_sha256": sha(candidate),
            "restore_sha256": sha(restore), "report_sha256": sha(blobs[2][1]),
            "verification_sha256": sha(blobs[3][1]), "ledger_sha256": sha(ledger)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("construct-report", "build", "verify"))
    args = parser.parse_args()
    if args.command == "build":
        output = build_to_quarantine()
    elif args.command == "verify":
        q, *_ = custody._validate_exact_roots(ROOT)
        output = verify_exact((q / CANDIDATE_NAME).read_bytes(), (q / RESTORE_NAME).read_bytes())
    else:
        candidate, restore, report = construct_pair()
        output = {"verdict": report["verdict"], "candidate_sha256": sha(candidate),
                  "restore_sha256": sha(restore)}
    print(json.dumps(output, indent=2))
    return 0 if output["verdict"] in ("PASS", "PASS_OFFLINE_ONLY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
