#!/usr/bin/env python3
"""Reproduce the pinned USB detach inventory without promoting gaps to proof."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fr245_key_workspace_audit import (hash_functions, literal_sites, read_pinned_image,
                                      slice_at, write_private_report)

USB_STATE_MACHINE = (0x20858, 0x20A3F)
USB_WORKER = (0x20A64, 0x20AB7)
TEARDOWN_CALL = 0x2093E
UNSCHEDULED_TAIL = 0x20A8A
USB_CACHE = 0x1FFC6F25
USB_OBSERVERS = 0x1FFC8AA0
USB_MUTEX = 0x1FFC6EEC
FUNCTIONS = {
    0x20858: (0x20A3F, "2f9c2ca2710dae634ce952ba48ae34789e83fb902106e39869c0d9d36f93020a"),
    0x20A64: (0x20AB7, "c7020aac2675270f9f96d7283e9d6ae8780730cf977ec818e8b2234b177bcd5c"),
    0x207B0: (0x207FF, "af9b817ec108e68efa2de0facd06ace9dff0ba557b3a4034230ea6bd3e2bffc9"),
    0x206E0: (0x207A1, "e7c09f778986268ced21d0b2459671181547560768a955036a2d6999d1541120"),
    0x20578: (0x205A7, "4149dd90c244cb40acb050a3e0f8122a7fe8a2272edd522c454260a55d76b184"),
    0x20B20: (0x20B53, "fc19bfed054b77e766ab84cb7609e693532116b02b66325ff77ab1b2010688df"),
    0x20B6C: (0x20BBB, "7fb0584cae3a14ad23c81164488c0675c1da923baa7e050a017c43600808f63d"),
    0x8734: (0x873B, "69d30ad7ddaff3eab8abfc98a553cf3c8a9446dcad3297c19c4cb7947a1c3436"),
    0x874C: (0x87ED, "ccb199effa91ae3d30b1678c7dd3ac4add3efc53a057c3ae9d1e5c93c1e8dfee"),
    0x7720: (0x774B, "2e1d739902913844dec04172724761a66a75c8bc5ce454c0935d9e0d413e154a"),
    0x1EF1C: (0x1EF23, "7627dcc45436b2764bd825f557d85267951485f9ae2287f29208f80d1b13fcdd"),
    0x67D8: (0x6979, "238e2504645eae2470bac1a2000fea2fd9b93360f2c55dfbc5411bfe25cc5fd8"),
    0x5325C: (0x532B1, "7974314a584ed1e7d4ff805ac93d0605acf1012fccc3b0f1945f35d839196339"),
    0x5330C: (0x53349, "3c52abc6704884863ca34b3d47091f7667577eed61c28a00b2bc8eafc08235bd"),
    0x53B10: (0x53C63, "7f6a4322f775351f9124fc9145518cba9c8e874bb42adeeff70b99acdad538c3"),
}


def _ghidra_inventory(root: Path, image: bytes, image_sha: str) -> dict[str, Any]:
    analysis = root / "artifacts/firmware/analysis"
    path = analysis / "fr245-1370-usb-detach-ghidra.json"
    log_path = analysis / "fr245-1370-usb-detach-ghidra.log"
    receipt: dict[str, Any] = {"verified": False}
    try:
        raw = path.read_bytes()
        report = json.loads(raw)
        log_raw = log_path.read_bytes()
        # Windows PowerShell redirects native output to UTF-16LE by default.
        log = log_raw.decode("utf-16" if log_raw.startswith(b"\xff\xfe") else "utf-8")
        sha = hashlib.sha256(raw).hexdigest()
        if (report["schema"] != "flyos.fr245.usb-ghidra-inventory.v1"
                or report["program"] != "stream_01_fw_all_bin.bin"
                or report["executable_sha256"] != image_sha
                or f"USB_DETACH_REPORT_COMPLETE json_sha256={sha}" not in log):
            raise ValueError("Ghidra identity or completion receipt differs")
        if not report["functions"] or not report["state_machine_blocks"]:
            raise ValueError("Ghidra inventory is empty")
        # Check every extracted function against the pinned input, including
        # discontiguous bodies. A receipt alone is never evidence of identity.
        for function in report["functions"]:
            digest = hashlib.sha256()
            for extent in function["ranges"]:
                data = slice_at(image, extent["start"], extent["end_inclusive"] - extent["start"] + 1)
                if hashlib.sha256(data).hexdigest() != extent["sha256"]:
                    raise ValueError("Ghidra function extent hash differs")
                digest.update(data)
            if digest.hexdigest() != function["sha256"]:
                raise ValueError("Ghidra function body hash differs")
        receipt.update(verified=True, json_sha256=sha,
                       console_sha256=hashlib.sha256(log_raw).hexdigest(),
                       function_count=len(report["functions"]),
                       block_count=len(report["state_machine_blocks"]),
                       functions=report["functions"],
                       state_machine_blocks=report["state_machine_blocks"],
                       cache_references=[item for item in report["usb_references"] if item["to"] == USB_CACHE],
                       computed_memory_candidates=report["memory_operations"])
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        receipt["reason"] = f"Ghidra inventory unavailable or rejected: {error}"
    return receipt


def _state_graph() -> list[dict[str, Any]]:
    """Reviewed local graph, bound to the full state-machine hash above.

    'guard' summarizes branch semantics; it is not a substitute for proving
    the guards' external callees or their eventual outcomes.
    """
    rows = [
        (0, 0, "input != 0", -1, 0x208EC),
        (0, 1, "input == 0; initialize and notify", 0, 0x20910),
        (1, 0, "input == 2; common teardown", -1, TEARDOWN_CALL),
        (1, 2, "input == 1; notify", -1, 0x209F8),
        (1, 1, "input neither 1 nor 2", -1, 0x20936),
        (2, 0, "input == 2; common teardown", -1, TEARDOWN_CALL),
        (2, 2, "input != 2 and (active == 3 or desired == active)", -1, 0x20936),
        (2, 5, "input != 2 and active != 3 and desired != active", 0, 0x2088A),
        (3, 3, "any readiness guard waits; detach input is not tested", 100, 0x2089A),
        (3, 4, "all external readiness guards allow transition", 0, 0x20910),
        (4, 0, "input == 2; common teardown", -1, TEARDOWN_CALL),
        (4, 4, "input != 2 and (active == 3 or desired == active)", -1, 0x20936),
        (4, 5, "input != 2 and active != 3 and desired != active", 0, 0x2088A),
        (5, 0, "input == 2; common teardown", -1, TEARDOWN_CALL),
        (5, 5, "busy, removal guard waits, or unexpected desired mode", 100, 0x2089A),
        (5, 3, "input != 2, not busy, desired == 1", 100, 0x20A36),
        (5, 2, "input != 2, not busy, desired == 0 and removal allowed", -1, 0x208DA),
        ("other", 0, "default", 0, 0x20A3C),
    ]
    return [dict(zip(("from", "to", "guard", "return_delay_ms", "instruction"), row)) for row in rows]


def analyze_usb_detach(root: Path) -> dict[str, Any]:
    """Fail unless 3/4 paths, observers, hook context, retry, and modal are proved."""
    image, identity = read_pinned_image(root)
    report: dict[str, Any] = {
        "schema": "flyos.fr245.usb-detach.v1", "image": identity, "proved": False,
        "state_machine": {"range_inclusive": list(USB_STATE_MACHINE), "sha256": None},
        "functions": [], "edges": {"3_to_detach": {"proved": False}, "4_to_detach": {"proved": False}},
        "teardown": {"calls_per_detach_epoch": None, "cache_after_local_path": None},
        "queue_site": {"proved": False, "mutex_state": "unproved", "ordering": "unproved"},
        "retry_context": {"bounded": False, "callback": None, "max_period_ms": None},
        "modal_outcome": {"kind": "unproved"}, "hook_sites": [],
        "cache_accesses": {"complete": False}, "observers": {"complete": False}, "unresolved": [],
    }
    if image is None:
        report["unresolved"] = ["Pinned offline firmware is missing or has a different size/hash."]
        return report
    functions = hash_functions(image, FUNCTIONS)
    report["functions"] = functions
    report["state_machine"]["sha256"] = functions[0]["sha256"]
    if not all(item["proved"] for item in functions):
        report["unresolved"] = ["Pinned function hash differs."]
        return report
    inventory = _ghidra_inventory(root, image, identity["sha256"])
    report["ghidra"] = inventory
    report["state_machine"].update(local_graph=_state_graph(),
        local_graph_pinned=True, full_transition_semantics_proved=False,
        cache=USB_CACHE, input=0x1FFC6F24, active=0x1FFC6F10, desired=0x1FFC6F26)
    report["cache_accesses"].update(literal_vas=literal_sites(image, USB_CACHE),
        direct_references=inventory.get("cache_references", []),
        unresolved_computed_accesses=sum(item["unresolved_computed_pointer"]
                                        for item in inventory.get("computed_memory_candidates", [])),
        reason="Known references and seeded P-code are enumerated; arbitrary computed aliases and external code remain open.")
    report["edges"] = {
        "3_to_detach": {"proved": False, "conditional_path": [3, 4, 0],
            "counterexample_path": [0x20892, 0x2089A],
            "counterexample_kind": "symbolic_guard_result; external guard/input relationship unproved",
            "reason": "A false result from external readiness veneer 0x1F1458 repeats state 3 with return 100, even when input is 2. No eventual-readiness proof exists."},
        "4_to_detach": {"proved": True, "path": [0x20870, 0x20876, TEARDOWN_CALL, 0x207E4],
            "condition": "input byte 0x1FFC6F24 == 2; local path assuming callees return", "cache_after": 0},
    }
    report["teardown"].update(call=TEARDOWN_CALL, callee=0x207B0,
        cache_store=0x207E4, cache_after_local_path=0, calls_per_local_path=1,
        reason="One local common call is not a proof of once-per-epoch behavior through dynamic observers and reentry.")
    report["hook_sites"] = [
        {"address": TEARDOWN_CALL, "length": 4, "target": 0x207B0,
         "sha256": hashlib.sha256(slice_at(image, TEARDOWN_CALL, 4)).hexdigest(),
         "mutex_state": "held_before_and_after_teardown", "queue_allowed_here": False},
        {"address": UNSCHEDULED_TAIL, "length": 4, "target": 0x874C,
         "sha256": hashlib.sha256(slice_at(image, UNSCHEDULED_TAIL, 4)).hexdigest(),
         "mutex_state": "held_before_replayed_unlock", "queue_allowed_here": False,
         "abi": "r0=USB mutex; worker stack and callee-saved registers already restored; lr=worker caller",
         "requirement": "Replay unlock before queue; preserve caller return and validate recursion depth/calling context."},
    ]
    report["queue_site"].update(candidate_after_replayed_unlock=UNSCHEDULED_TAIL,
        primitive=0x67D8, required_flags=0, required_timeout=0,
        requested_ordering="back", usb_mutex=USB_MUTEX,
        reason="Tail is identified, but callback caller context, mutex recursion depth, and queue integration are not proved.")
    report["observers"].update(root=USB_OBSERVERS, publish=0x1EF1C, dispatch=0x7720,
        literal_vas=literal_sites(image, USB_OBSERVERS), next_offset=0, callback_offset=8,
        context_offset=12, synchronous=True, dispatch_mutex=USB_OBSERVERS + 4,
        reason="Dispatcher walks RAM registrations and invokes callback+8; registrations and all modal outcomes are not closed.")
    report["retry_context"].update(candidates_rejected=[
        {"address": 0x20A64, "reason": "Worker does not reschedule after return -1; no bounded post-detach cadence."},
        {"address": 0x5325C, "reason": "UI-thread-only allocation/scheduling API, not an existing recurring callback."},
        {"address": 0x5330C, "reason": "Requires an existing scheduled object and UI thread; no free object or cadence proved."},
        {"address": 0x53B10, "reason": "Registration allocates storage; callback existence and lifecycle not proved."},
    ])
    report["unresolved"] = [
        "Computed USB-cache alias inventory is incomplete.",
        "State 3 detach convergence depends on unproved external readiness guards.",
        "Dynamic observer registrations, reentry, and surviving-modal refresh are unproved.",
        "Both candidate hooks enter with the USB mutex held; safe post-unlock queue calling context is unproved.",
        "No pinned post-unlock UI callback with bounded retry cadence is proved.",
    ]
    if not inventory["verified"]:
        report["unresolved"].append(inventory["reason"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--write-private-report", type=Path)
    args = parser.parse_args()
    report = analyze_usb_detach(args.root)
    if args.write_private_report:
        write_private_report(args.write_private_report, report)
    print(json.dumps({key: report[key] for key in ("proved", "edges", "queue_site", "retry_context", "unresolved")}, indent=2))
    return 0 if report["proved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
