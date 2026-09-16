#!/usr/bin/env python3
"""Compose the offline atlas-shell gate. False or unknown stops implementation."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import fr245_key_workspace_audit as workspace
import fr245_usb_detach as usb

REQUIRED_GATES = (
    "five_key_halfwords",
    "phase_timing",
    "tri_state_view_classifier",
    "observed_update_prompt_non_home",
    "usb_3_and_4_detach_convergence",
    "post_unlock_hook_site",
    "bounded_retry_context",
    "modal_outcome_or_native_refresh",
    "atomic_storage_map",
    "projected_flash_fit",
)
SECTION_LIMITS = {"primary": 1023, "secondary": 2048}
SECTION_STARTS = {"primary": 0x1F6000, "secondary": 0x1FA400}
REPAIR_BYTE = 0x1F63FF
PROJECTION_GROUPS = {
    "display_entry_trampoline", "key_event_trampoline", "usb_teardown_trampoline",
    "usb_unlock_trampoline", "bounded_view_classifier", "ownership_and_state_codec",
    "system_chord_and_session", "detach_and_retry", "packed_model",
    "atlas_renderer", "font_table", "model_tables", "renderer_tables", "literal_pools",
}


def failed_gates(gates: dict[str, Any]) -> list[str]:
    """Only literal True is proof; missing, unknown, and truthy strings fail."""
    return [name for name in REQUIRED_GATES if gates.get(name) is not True]


def projected_fit(rows: list[dict[str, Any]], required: set[str]) -> bool:
    """Check exact upper-bound intervals; require no arbitrary spare-byte margin.

    Caller supplies measured/reviewed replacement groups, including literals
    and alignment. This geometry check cannot establish measurement provenance.
    """
    if not rows or {row.get("name") for row in rows} != required or len(rows) != len(required):
        return False
    intervals = []
    for row in rows:
        section = row.get("section")
        start, size = row.get("start"), row.get("upper_bound")
        if (section not in SECTION_LIMITS or type(start) is not int
                or type(size) is not int or size <= 0):
            return False
        end = start + size
        if not SECTION_STARTS[section] <= start < end <= SECTION_STARTS[section] + SECTION_LIMITS[section]:
            return False
        if start <= REPAIR_BYTE < end:
            return False
        intervals.append((start, end))
    intervals.sort()
    return all(previous[1] <= current[0] for previous, current in zip(intervals, intervals[1:]))


def _storage(key_report: dict[str, Any]) -> dict[str, Any]:
    modes = [
        {"NORMAL": 0, "CHORD_HOLD": 1, "SYSTEM_PENDING": 2, "SYSTEM_HOME": 3, "SYSTEM_EXCURSION": 4},
        {"DETACH_NONE": 0, "PENDING": 1, "RETRY1": 2, "RETRY2": 3, "RETRY3": 4, "QUEUED": 5, "EXHAUSTED": 6},
        {"NORMAL": 0}, {"NORMAL": 0}, {"NORMAL": 0},
    ]
    names = ("LIGHT", "START", "BACK", "DOWN", "UP")
    words = [{"key": key, "address": workspace.RECORD_BASE + index * workspace.RECORD_STRIDE + 0x36,
              "width": 2, "modes": modes[index]}
             for index, key in enumerate(names)]
    return {
        "words": words, "bytes_required": 10, "capacity_in_five_halfwords": True,
        "local_states": {"IDLE": 0, "FLY_HELD": 1, "FLY_PULSE": 2, "GARMIN_HELD": 3},
        "encoding": "local | ((local ^ 15) << 4) | (mode << 8) | ((mode ^ 15) << 12)",
        "nibbles_low_to_high": ["local", "local_xor_15", "mode", "mode_xor_15"],
        "aligned_and_disjoint": all(word["address"] % 2 == 0 for word in words)
                                and len({word["address"] for word in words}) == 5,
        "required_transition": "Aligned 16-bit compare/exchange preserving the other subsystem's byte; invalid complement or mode selects Garmin.",
        "workspace_proved": key_report["proved"], "atomic_protocol_proved": False,
        "five_key_words_and_modes_fit": False,
        "reason": "Bit capacity and alignment are exact, but exclusive workspace use and concurrent CAS transitions are not proved.",
    }


def evaluate_feasibility(root: Path, *, evidence_dir: Path | None = None) -> dict[str, Any]:
    """Return go=false with all named failed gates; never infer missing evidence."""
    key_report = workspace.audit_key_workspace(root)
    usb_report = usb.analyze_usb_detach(root, evidence_dir=evidence_dir)
    image, identity = workspace.read_pinned_image(root)
    view_functions = workspace.hash_functions(image, {
        0x5306C: (0x53081, "5ab36cc5d4dcdda7caeb4b6f78febb14e3d47196a480449069aae0c6688a842a"),
        0x530CC: (0x530E7, "6b9074290056fd1f38bb1655d17fa81f8a91bf19a633fea98ce38f612b406b30"),
    }) if image is not None else []
    classifier = {
        "proved": False, "foundation_functions": view_functions,
        "list_root": 0x20003E84, "home_callback": 0x5ADF5,
        "node_offsets": [4, 8, 0x50], "required_max_nodes": 8,
        "reason": "Stock finder and visibility predicate are pinned but unbounded. No completed proof covers the proposed HOME/NON_HOME/INVALID classifier under malformed, changing, and cyclic lists.",
    }
    update_prompt = {
        "proved_non_home": False, "observed_callback": None, "observed_view_fixture_sha256": None,
        "reason": "Update eligibility and Install Now/Install Later resources do not identify the observed update prompt's first-visible node. No pinned offline modal fixture or callback trace is available.",
    }
    storage = _storage(key_report)
    projection = {
        "kind": "replacement", "measured": False,
        "groups": [{"name": name, "section": None, "start": None, "upper_bound": None}
                   for name in sorted(PROJECTION_GROUPS)],
        "hook_patches": [
            {"name": "display", "address": 0x9A20, "replacement_bytes_required": 4},
            {"name": "key", "address": 0xFA48, "replacement_bytes_required": 6},
            {"name": "usb_teardown", "address": 0x2093E, "replacement_bytes_required": 4},
            {"name": "usb_unlock", "address": 0x20A8A, "replacement_bytes_required": 4},
        ],
        "repair_byte": REPAIR_BYTE, "fit_without_repair_byte": False,
        "reason": "Replacement code, all trampolines, renderer tables, literals, and alignment lack measured upper bounds. No sum with the existing 996/2044-byte target is substituted for a replacement projection.",
    }
    projection["fit_without_repair_byte"] = projection["measured"] and projected_fit(projection["groups"], PROJECTION_GROUPS)
    gates = {
        "five_key_halfwords": key_report["proved"],
        "phase_timing": key_report["phase_timing"]["proved"],
        "tri_state_view_classifier": classifier["proved"],
        "observed_update_prompt_non_home": update_prompt["proved_non_home"],
        "usb_3_and_4_detach_convergence": usb_report["cache_accesses"]["complete"]
            and all(usb_report["edges"][name]["proved"] for name in ("3_to_detach", "4_to_detach"))
            and usb_report["teardown"]["calls_per_detach_epoch"] == 1,
        "post_unlock_hook_site": usb_report["queue_site"]["proved"],
        "bounded_retry_context": usb_report["retry_context"]["bounded"],
        "modal_outcome_or_native_refresh": usb_report["modal_outcome"]["kind"] in {"home_after_observers", "proved_native_refresh"},
        "atomic_storage_map": storage["five_key_words_and_modes_fit"],
        "projected_flash_fit": projection["fit_without_repair_byte"],
    }
    failed = failed_gates(gates)
    return {
        "schema": "flyos.fr245.atlas-shell-feasibility.v1", "image": identity,
        "go": not failed, "failed_gates": failed, "gates": gates,
        "section_limits": dict(SECTION_LIMITS), "key_workspace": key_report,
        "usb_detach": usb_report, "view_classifier": classifier, "update_prompt": update_prompt,
        "storage": storage, "projected_sections": projection,
        "implementation_allowed": not failed,
    }


def report_outputs(path: Path, report: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, report),
            (path.parent / "fr245-1370-key-workspace.json", report["key_workspace"]),
            (path.parent / "fr245-1370-usb-detach.json", report["usb_detach"])]


def run_private_analysis(root: Path, run_directory: Path) -> dict[str, Any]:
    """Claim an explicit fresh directory, then collect all evidence without clobbering."""
    workspace.preflight_outputs([run_directory])
    run_directory.parent.mkdir(parents=True, exist_ok=True)
    run_directory.mkdir()  # Atomic directory claim; concurrent/repeated runs fail.
    run_directory = run_directory.resolve()
    root = root.resolve()
    names = ("fr245-1370-usb-detach-ghidra.json", "fr245-1370-usb-detach-decompilation.txt",
             "fr245-1370-usb-detach-ghidra.log", "headless.log", "script.log")
    inventory, decompilation, console, headless_log, script_log = [run_directory / name for name in names]
    report_path = run_directory / "fr245-1370-atlas-shell-feasibility.json"
    receipt = run_directory / "SHA256SUMS"
    workspace.preflight_outputs([run_directory / name for name in names] + [report_path, receipt,
        run_directory / "fr245-1370-key-workspace.json", run_directory / "fr245-1370-usb-detach.json"])
    launcher = root / "tools/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat"
    project = (root / "artifacts/firmware/ghidra-code").resolve()
    arguments = [str(launcher), str(project), "FR245_1370_CODE", "-process", "stream_01_fw_all_bin.bin",
                 "-readOnly", "-noanalysis", "-log", str(headless_log), "-scriptlog", str(script_log),
                 "-scriptPath", str(root / "tools/garmin-firmware/ghidra_scripts"),
                 "-postScript", "UsbDetachReport.java", str(inventory), str(decompilation)]
    if os.name == "nt" and any(any(character in argument for character in '&|<>^%!\r\n') for argument in arguments):
        raise ValueError("batch launcher paths must not contain shell metacharacters")
    if not launcher.is_file():
        raise FileNotFoundError(f"Ghidra launcher unavailable: {launcher}")
    with console.open("xb") as output:
        result = subprocess.run(arguments, cwd=root, stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Ghidra failed with exit {result.returncode}; retain the failed run directory")
    report = evaluate_feasibility(root, evidence_dir=run_directory)
    if not report["usb_detach"].get("ghidra", {}).get("verified", False):
        raise RuntimeError("Ghidra completion/identity verification failed; retain the failed run directory")
    workspace.write_private_reports(report_outputs(report_path, report), receipt,
                                    tuple(run_directory / name for name in names))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    outputs = parser.add_mutually_exclusive_group()
    outputs.add_argument("--write-private-report", type=Path)
    outputs.add_argument("--run-directory", type=Path, help="new, explicit directory for a complete Ghidra/report run")
    parser.add_argument("--evidence-dir", type=Path, help="read Ghidra evidence from a previous private run")
    args = parser.parse_args()
    if args.run_directory and args.evidence_dir:
        parser.error("--run-directory collects new evidence and cannot use --evidence-dir")
    try:
        if args.run_directory:
            report = run_private_analysis(args.root, args.run_directory)
        else:
            report = evaluate_feasibility(args.root, evidence_dir=args.evidence_dir)
            if args.write_private_report:
                workspace.write_private_reports(report_outputs(args.write_private_report, report),
                    args.write_private_report.with_name(args.write_private_report.name + ".sha256"))
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps({key: report[key] for key in ("go", "failed_gates", "section_limits")}, indent=2))
    return 0 if report["go"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
