#!/usr/bin/env python3
"""Pinned, offline key-workspace evidence. Unknown alias coverage is a blocker.

This is an evidence inventory, not permission to use the final halfwords. It
does not open a device, execute firmware, or create a target or package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import fr245_runtime_state as runtime

IMAGE_RELATIVE = Path("artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin")
RECORD_BASE = 0x1FFDBBC8
RECORD_STRIDE = 0x38
FINAL_HALFWORD = 0x36
REQUIRED_OWNERS = (0xF7E4, 0xFA18, 0xFA48, 0xFAA4, 0xFB34,
                   0xFCAC, 0xFCD8, 0x8844, 0x8B04)
BASE_LITERALS = (0xF840, 0xFA3C, 0xFA80, 0xFB0C, 0xFCA0, 0xFCD0, 0xFD00)
# Inclusive function extents, independently recovered by Ghidra. No code bytes.
FUNCTIONS = {
    0xF7E4: (0xF839, "048aae03deeddb1f55259c4541368e069935cbcc0c95dce19e533211a9d15c9a"),
    0xFA18: (0xFA3B, "91eb51e22514b8dbdbcfe887f936f789ff0e99c81fdd3584a732e9b03a386d94"),
    0xFA48: (0xFA7F, "edf63660beaa87f573accbecc6c38001b6a755c8e7982eec63acdfad9d324fbc"),
    0xFAA4: (0xFB09, "49597ac42a225c54504cfc303e99400e00005a22a35d5a62569e41519fdb3cac"),
    0xFB34: (0xFC85, "f2f694f9afba86feefa27e93eda37fd2fcc6800d9b8f00cdea5769b87a8657fd"),
    0xFCAC: (0xFCCF, "2557a2c0cec7458eff9e9663a5540d2a32e71b91dc94a1df2bad7201cdf8848a"),
    0xFCD8: (0xFCFF, "c84115d900ddbb2db1118b1a22f55f5f01de988d40ba27f947a16a4637eb458b"),
    0x8844: (0x891D, "a75b44caa458a1a952b437736190215d8917ba380c7eb77750f1d9fc0c24d832"),
    0x8B04: (0x8BA5, "21120af6b8b8029cb4494c4948058b7df34f906a92138c46f4f1d6c301ae5e4f"),
    0x7BDC: (0x7C79, "bb865e989473bfd5810753ae61578eaf923b376702b9a774acc3089e759ceae4"),
}
# Each relation is a reviewed pointer-origin annotation; offsets and widths are
# decoded afresh, and the whole function/image must match before using it.
DIRECT_ACCESS_SITES = (0xF818, 0xFA24, 0xFA26, 0xFA28, 0xFA2A, 0xFA2E,
    0xFA52, 0xFAD2, 0xFADA, 0xFAE4, 0xFB4A, 0xFB70, 0xFB7A, 0xFBB6,
    0xFBE2, 0xFBEC, 0xFBF8, 0xFC22, 0xFC4C)
HELPER_ACCESS_SITES = (0x88B0, 0x88B4, 0x88B8, 0x8B22, 0x8B44,
    0x8B5C, 0x8B66, 0x8B68, 0x8B8E, 0x8B9C, 0x8B9E, 0x7BE2, 0x7C30, 0x7C3A, 0x7C72)


def read_pinned_image(root: Path) -> tuple[bytes | None, dict[str, Any]]:
    try:
        image = (root / IMAGE_RELATIVE).read_bytes()
    except OSError as error:
        return None, {"proved": False, "reason": type(error).__name__, "sha256": None}
    observed = hashlib.sha256(image).hexdigest()
    valid = len(image) == runtime.PINNED_IMAGE_SIZE and observed == runtime.PINNED_IMAGE_SHA256
    evidence = {"proved": valid, "sha256": observed, "size": len(image),
                "expected_sha256": runtime.PINNED_IMAGE_SHA256,
                "expected_size": runtime.PINNED_IMAGE_SIZE}
    return image if valid else None, evidence


def slice_at(image: bytes, address: int, length: int) -> bytes:
    offset = address - runtime.IMAGE_BASE
    if offset < 0 or length < 0 or offset + length > len(image):
        raise ValueError("evidence extent outside pinned image")
    return image[offset:offset + length]


def hash_functions(image: bytes, functions: dict[int, tuple[int, str]]) -> list[dict[str, Any]]:
    result = []
    for start, (end, expected) in functions.items():
        observed = hashlib.sha256(slice_at(image, start, end - start + 1)).hexdigest()
        result.append({"entry": start, "end_inclusive": end, "sha256": observed,
                       "expected_sha256": expected, "proved": observed == expected})
    return result


def literal_sites(image: bytes, value: int) -> list[int]:
    """Search all byte alignments; this does not claim to find computed aliases."""
    needle = struct.pack("<I", value)
    result = []
    at = image.find(needle)
    while at >= 0:
        result.append(at + runtime.IMAGE_BASE)
        at = image.find(needle, at + 1)
    return result


def accesses_exclude_pad(accesses: list[dict[str, Any]]) -> bool:
    return bool(accesses) and all(
        type(item.get("offset")) is int and type(item.get("width")) is int
        and item["width"] > 0 and 0 <= item["offset"]
        and item["offset"] + item["width"] <= FINAL_HALFWORD
        for item in accesses
    )


def _decode_accesses(image: bytes, sites: tuple[int, ...]) -> list[dict[str, Any]]:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    from capstone.arm import ARM_OP_MEM
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    decoder.detail = True
    result = []
    for address in sites:
        instruction = next(decoder.disasm(slice_at(image, address, 4), address), None)
        if instruction is None:
            raise ValueError(f"undecodable memory access at {address:#x}")
        memories = [operand.mem for operand in instruction.operands if operand.type == ARM_OP_MEM]
        mnemonic = instruction.mnemonic.split(".")[0]
        widths = {"ldr": 4, "str": 4, "ldrb": 1, "strb": 1,
                  "ldrh": 2, "strh": 2, "ldrd": 8, "strd": 8}
        if len(memories) != 1 or mnemonic not in widths:
            raise ValueError(f"unrecognized memory access at {address:#x}")
        result.append({"instruction": address, "offset": memories[0].disp,
                       "width": widths[mnemonic], "operation": "read" if mnemonic.startswith("ldr") else "write"})
    return result


def audit_key_workspace(root: Path) -> dict[str, Any]:
    """Return hashes, addresses, decoded offsets, timing, and explicit proof gaps."""
    image, identity = read_pinned_image(root)
    report: dict[str, Any] = {
        "schema": "flyos.fr245.key-workspace.v1", "image": identity, "proved": False,
        "records": [{"address": RECORD_BASE + key * RECORD_STRIDE + FINAL_HALFWORD,
                     "max_stock_offset": None, "max_audited_offset": None, "proved": False}
                    for key in range(5)],
        "workspace_base_literal_vas": [], "functions": [], "accesses": [],
        "scheduled_object_span_excludes_0x36_0x37": False,
        "phase_timing": {"proved": False, "phase4_max_period_ms": None},
        "coverage": {"complete": False}, "unresolved": [],
    }
    if image is None:
        report["unresolved"] = ["Pinned offline firmware is missing or has a different size/hash."]
        return report
    functions = hash_functions(image, FUNCTIONS)
    literals = literal_sites(image, RECORD_BASE)
    report.update(functions=functions, workspace_base_literal_vas=literals)
    if not all(item["proved"] for item in functions) or literals != list(BASE_LITERALS):
        report["unresolved"] = ["Function hashes or exhaustive base-literal inventory differ."]
        return report
    try:
        direct = _decode_accesses(image, DIRECT_ACCESS_SITES)
        helpers = _decode_accesses(image, HELPER_ACCESS_SITES)
    except (ImportError, ValueError) as error:
        report["unresolved"] = [f"Memory decoder unavailable or rejected evidence: {error}"]
        return report
    # Initialization addresses select records 0..4; indexed loads use key*0x38.
    for access in direct:
        access["offset"] %= RECORD_STRIDE
        access["origin"] = "reviewed_key_record"
    projected = [dict(access, offset=access["offset"] + start,
                      origin="reviewed_scheduled_object", object_start=start)
                 for start in (4, 0x1C) for access in helpers]
    accesses = direct + projected
    report["accesses"] = accesses
    report["scheduled_object_span_excludes_0x36_0x37"] = accesses_exclude_pad(projected)
    report["scheduled_objects"] = [{"offset": 4, "end_inclusive": 0x1B},
                                   {"offset": 0x1C, "end_inclusive": 0x33}]
    for record in report["records"]:
        record["max_audited_offset"] = max(item["offset"] + item["width"] - 1 for item in accesses)
    report["phase_timing"] = {
        "proved": True, "phase0": "immediate at 0xFADC",
        "first_deferred_ms": {"LIGHT": 750, "other_keys": 500},
        "phase4_max_period_ms": 200,
        "phase2_elapsed_threshold_ms": {"LIGHT": 1000, "other_keys": 500},
        "phase3_elapsed_threshold_ms": 5000,
        "instruction_vas": [0xFAB4, 0xFAC0, 0xFB5C, 0xFB60, 0xFB98, 0xFBD0, 0xFBDC, 0xFC16],
        "scope": "Requested scheduler periods and elapsed thresholds; not a bound on scheduler latency. Phase 4 may be suppressed by the stock disable byte.",
    }
    report["coverage"].update({"required_owners_hashed": list(REQUIRED_OWNERS),
        "additional_helper_hashed": [0x7BDC], "base_literal_scan_complete": True,
        "reviewed_accesses_exclude_pad": accesses_exclude_pad(accesses),
        "computed_aliases_closed": False, "scheduler_dispatch_closed": False})
    report["unresolved"] = [
        "Direct owners and schedule/cancel/list-insert helpers stop at offset 0x35, but escaped scheduler-object pointers and dispatch consumers have not been closed transitively.",
        "An exhaustive literal scan is not proof that no computed alias, bulk initialization, or callback can access offsets 0x36/0x37; max_stock_offset remains unknown.",
    ]
    return report


def preflight_outputs(paths: list[Path]) -> None:
    """Check the complete set before opening anything, including aliases."""
    resolved = [os.path.normcase(str(path.resolve())) for path in paths]
    if len(set(resolved)) != len(resolved):
        raise FileExistsError("output collision: duplicate or aliased output paths")
    for path in paths:
        if os.path.lexists(path):
            raise FileExistsError(f"output collision: {path}")


def write_new_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    """Reserve every file exclusively before writing; never truncate a file.

    A race or I/O failure can leave newly reserved/partial files, which must be
    retained as a failed run. No existing artifact is removed or replaced.
    """
    preflight_outputs([path for path, _ in outputs])
    with ExitStack() as stack:
        streams = []
        for path, data in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            streams.append((stack.enter_context(path.open("xb")), data))
        for stream, data in streams:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def write_private_reports(reports: list[tuple[Path, dict[str, Any]]], receipt: Path,
                          extra_files: tuple[Path, ...] = ()) -> None:
    outputs = [(path, (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"))
               for path, report in reports]
    preflight_outputs([path for path, _ in outputs] + [receipt])
    if any(path.parent.resolve() != receipt.parent.resolve() for path, _ in outputs):
        raise ValueError("report and checksum outputs must share one run directory")
    checksums = [(path, hashlib.sha256(data).hexdigest()) for path, data in outputs]
    checksums.extend((path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in extra_files)
    receipt_bytes = "".join(f"{digest}  {path.name}\n" for path, digest in checksums).encode("utf-8")
    write_new_outputs(outputs + [(receipt, receipt_bytes)])


def write_private_report(path: Path, report: dict[str, Any]) -> None:
    write_private_reports([(path, report)], path.with_name(path.name + ".sha256"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--write-private-report", type=Path)
    args = parser.parse_args()
    report = audit_key_workspace(args.root)
    if args.write_private_report:
        try:
            write_private_report(args.write_private_report, report)
        except (OSError, ValueError) as error:
            parser.error(str(error))
    print(json.dumps(report, indent=2))
    return 0 if report["proved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
