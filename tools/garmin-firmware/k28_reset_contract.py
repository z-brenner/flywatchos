"""Fail-closed offline reset-contract analysis for the FR245 13.70 image."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs


APP_BASE = 0x00003000
APP_END_EXCLUSIVE = 0x00200000
PINNED_IMAGE_SIZE = 5_079_040
PINNED_IMAGE_SHA256 = (
    "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
)
PINNED_IMAGE_RELATIVE_PATH = Path(
    "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/"
    "stream_01_fw_all_bin.bin"
)
RESET_VECTOR_OFFSET = 4
RESET_HANDLER = 0x000031F0
RESET_HANDLER_OFFSET = RESET_HANDLER - APP_BASE
RESET_HANDLER_SIZE = 22
STAGE2_LITERAL_VA = 0x0000320C
STAGE2_LITERAL_OFFSET = STAGE2_LITERAL_VA - APP_BASE
EXPECTED_RESET_BYTES = bytes.fromhex(
    "72b64ff0000080f31488bff36f8fdff808d002480047"
)
REQUIRED_GHIDRA_OUTPUTS = (
    "ghidra-inventory.json",
    "decompilation.txt",
    "headless.log",
    "script.log",
)
GHIDRA_INVENTORY_SCHEMA = "flyos.fr245.k28-reset-inventory.v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
ADDRESS_PATTERN = re.compile(r"0x[0-9a-f]{8}")


@dataclass(frozen=True)
class ResetRoot:
    image_sha256: str
    reset_vector: int
    reset_handler: int
    reset_bytes: bytes
    stage2_pointer: int
    stage2_entry: int


def pinned_image_path(root: Path) -> Path:
    return root / PINNED_IMAGE_RELATIVE_PATH


def _validate_reset_disassembly(reset_bytes: bytes) -> None:
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    instructions = list(decoder.disasm(reset_bytes, RESET_HANDLER))
    if not instructions:
        raise ValueError("reset handler did not disassemble")
    consumed = sum(instruction.size for instruction in instructions)
    if consumed != len(reset_bytes):
        raise ValueError("reset handler did not disassemble completely")
    last = instructions[-1]
    if last.mnemonic != "bx" or last.op_str != "r0":
        raise ValueError("reset handler does not terminate in bx r0")


def decode_trusted_layout(image: bytes) -> ResetRoot:
    if len(image) != PINNED_IMAGE_SIZE:
        raise ValueError("pinned image size mismatch")
    reset_vector = int.from_bytes(
        image[RESET_VECTOR_OFFSET : RESET_VECTOR_OFFSET + 4], "little"
    )
    reset_bytes = image[
        RESET_HANDLER_OFFSET : RESET_HANDLER_OFFSET + RESET_HANDLER_SIZE
    ]
    stage2_pointer = int.from_bytes(
        image[STAGE2_LITERAL_OFFSET : STAGE2_LITERAL_OFFSET + 4], "little"
    )
    if reset_vector != (RESET_HANDLER | 1):
        raise ValueError("reset vector mismatch")
    if reset_bytes != EXPECTED_RESET_BYTES:
        raise ValueError("reset handler bytes mismatch")
    _validate_reset_disassembly(reset_bytes)
    if stage2_pointer & 1 == 0:
        raise ValueError("stage-two pointer is not Thumb")
    stage2_entry = stage2_pointer & ~1
    if not APP_BASE <= stage2_entry < APP_END_EXCLUSIVE:
        raise ValueError("stage-two entry outside application")
    return ResetRoot(
        image_sha256="",
        reset_vector=reset_vector,
        reset_handler=RESET_HANDLER,
        reset_bytes=reset_bytes,
        stage2_pointer=stage2_pointer,
        stage2_entry=stage2_entry,
    )


def decode_pinned_image(image: bytes) -> ResetRoot:
    digest = hashlib.sha256(image).hexdigest()
    if digest != PINNED_IMAGE_SHA256:
        raise ValueError(
            f"pinned image SHA-256 mismatch: expected {PINNED_IMAGE_SHA256}, "
            f"got {digest}"
        )
    decoded = decode_trusted_layout(image)
    return dataclasses.replace(decoded, image_sha256=digest)


def load_reset_root(root: Path) -> ResetRoot:
    return decode_pinned_image(pinned_image_path(root).read_bytes())


def write_new_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _root_report(root: ResetRoot) -> dict:
    return {
        "schema_version": 1,
        "source_sha256": root.image_sha256,
        "source_size": PINNED_IMAGE_SIZE,
        "reset_vector": f"0x{root.reset_vector:08x}",
        "reset_handler": f"0x{root.reset_handler:08x}",
        "reset_bytes_hex": root.reset_bytes.hex(),
        "stage2_pointer": f"0x{root.stage2_pointer:08x}",
        "stage2_entry": f"0x{root.stage2_entry:08x}",
    }


def _require_list(report: dict, name: str) -> list:
    value = report.get(name)
    if not isinstance(value, list):
        raise ValueError(f"inventory field {name!r} must be a list")
    return value


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical lowercase SHA-256")
    return value


def _require_address(value: object, label: str) -> str:
    if not isinstance(value, str) or ADDRESS_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical 32-bit address")
    return value


def validate_ghidra_inventory(report: dict, root: ResetRoot) -> None:
    if not isinstance(report, dict):
        raise ValueError("Ghidra inventory must be an object")
    if report.get("schema") != GHIDRA_INVENTORY_SCHEMA:
        raise ValueError("Ghidra inventory schema mismatch")
    program = report.get("program")
    if not isinstance(program, dict):
        raise ValueError("Ghidra inventory program must be an object")
    if program.get("sha256") != root.image_sha256:
        raise ValueError("program SHA-256 does not match pinned image")
    if program.get("name") != "stream_01_fw_all_bin.bin":
        raise ValueError("program name mismatch")
    if program.get("base") != f"0x{APP_BASE:08x}":
        raise ValueError("program base mismatch")
    if program.get("end_exclusive") != f"0x{APP_END_EXCLUSIVE:08x}":
        raise ValueError("program end mismatch")
    expected_roots = [
        f"0x{root.reset_handler:08x}",
        f"0x{root.stage2_entry:08x}",
    ]
    if report.get("roots") != expected_roots:
        raise ValueError("inventory roots do not match pinned reset chain")
    if report.get("max_depth") != 3:
        raise ValueError("inventory traversal depth mismatch")
    for name in ("analysis_complete", "cancelled"):
        if not isinstance(report.get(name), bool):
            raise ValueError(f"inventory field {name!r} must be boolean")
    for name in ("unresolved_seed_count", "unresolved_function_count"):
        value = report.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"inventory field {name!r} must be a non-negative integer")
    functions = _require_list(report, "functions")
    entries = []
    functions_by_entry = {}
    required_function_fields = {
        "entry",
        "end_inclusive",
        "sha256",
        "depth",
        "direct_calls",
        "indirect_control_flow",
        "literal_references",
        "mmio_references",
        "backward_branches",
    }
    for function in functions:
        if not isinstance(function, dict) or not required_function_fields <= function.keys():
            raise ValueError("inventory function schema mismatch")
        entry = _require_address(function["entry"], "inventory function entry")
        end = _require_address(
            function["end_inclusive"], "inventory function end"
        )
        if int(end, 16) < int(entry, 16):
            raise ValueError("inventory function end precedes its entry")
        entries.append(int(entry, 16))
        functions_by_entry[entry] = function
        _require_sha256(function["sha256"], "inventory function SHA-256")
        if (
            not isinstance(function["depth"], int)
            or isinstance(function["depth"], bool)
            or not 0 <= function["depth"] <= report["max_depth"]
        ):
            raise ValueError("inventory function depth mismatch")
        for name in (
            "direct_calls",
            "indirect_control_flow",
            "literal_references",
            "mmio_references",
            "backward_branches",
        ):
            if not isinstance(function[name], list):
                raise ValueError(f"inventory function field {name!r} must be a list")
        for callee in function["direct_calls"]:
            _require_address(callee, "inventory direct-call target")
    if entries != sorted(entries) or len(entries) != len(set(entries)):
        raise ValueError("inventory functions must be unique and address-sorted")
    for name in (
        "computed_mmio",
        "unknown_mmio_widths",
        "unknown_mmio_values",
        "unbounded_polls",
        "unknown_memory_ranges",
    ):
        _require_list(report, name)

    for root_entry in expected_roots:
        root_function = functions_by_entry.get(root_entry)
        if root_function is None or root_function["depth"] != 0:
            raise ValueError(f"missing depth-zero root function: {root_entry}")

    if report["analysis_complete"]:
        if report["cancelled"]:
            raise ValueError("complete inventory cannot be cancelled")
        if report["unresolved_seed_count"] or report["unresolved_function_count"]:
            raise ValueError("complete inventory cannot report unresolved functions")
        for function in functions:
            if function["depth"] >= report["max_depth"]:
                continue
            for callee in function["direct_calls"]:
                value = int(callee, 16)
                if APP_BASE <= value < APP_END_EXCLUSIVE:
                    covered = functions_by_entry.get(callee)
                    if covered is None or covered["depth"] > function["depth"] + 1:
                        raise ValueError(
                            f"missing direct-call coverage for {callee}"
                        )

    mmio_references = [
        reference
        for function in functions
        for reference in function["mmio_references"]
    ]
    if any(
        reference not in report["unknown_mmio_widths"]
        for reference in mmio_references
    ):
        raise ValueError("MMIO-width summary contradicts function evidence")
    if any(
        reference not in report["unknown_mmio_values"]
        for reference in mmio_references
    ):
        raise ValueError("MMIO-value summary contradicts function evidence")
    expected_polls = [
        {
            "function": function["entry"],
            "from": branch["from"],
            "to": branch["to"],
        }
        for function in functions
        for branch in function["backward_branches"]
    ]
    if any(poll not in report["unbounded_polls"] for poll in expected_polls):
        raise ValueError("poll summary contradicts function evidence")


def load_ghidra_run(run: Path, root: ResetRoot) -> dict:
    missing = [name for name in REQUIRED_GHIDRA_OUTPUTS if not (run / name).is_file()]
    if missing:
        raise ValueError(f"missing evidence output: {missing}")
    logs = "\n".join(
        (run / name).read_text(encoding="utf-8", errors="replace")
        for name in ("headless.log", "script.log")
    )
    lowered = logs.lower()
    if "script error" in lowered or "post-script" in lowered:
        raise ValueError("Ghidra post-script error")
    if "output collision" in lowered:
        raise ValueError("Ghidra evidence output collision")
    try:
        report = json.loads(
            (run / "ghidra-inventory.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid Ghidra inventory: {error}") from error
    validate_ghidra_inventory(report, root)
    return report


def build_contract(
    root: ResetRoot,
    inventory: dict,
    *,
    control_flow_proof: dict | None = None,
    mmio_width_proof: dict | None = None,
    inventory_bytes: bytes | None = None,
    image: bytes | None = None,
) -> dict:
    validate_ghidra_inventory(inventory, root)
    functions = inventory["functions"]
    has_indirect_control_flow = any(
        function["indirect_control_flow"] for function in functions
    )
    control_flow_proof_sha256 = None
    mmio_width_proof_sha256 = None
    if control_flow_proof is not None or mmio_width_proof is not None:
        if inventory_bytes is None or image is None:
            raise ValueError(
                "evidence proofs require source image and inventory bytes"
            )
    if control_flow_proof is not None:
        import k28_control_flow

        k28_control_flow.validate_control_flow_proof(
            image, inventory, inventory_bytes, control_flow_proof
        )
        control_flow_proof_sha256 = k28_control_flow.proof_sha256(
            control_flow_proof
        )
    if mmio_width_proof is not None:
        import k28_mmio_widths

        k28_mmio_widths.validate_mmio_width_proof(
            image, inventory, inventory_bytes, mmio_width_proof
        )
        mmio_width_proof_sha256 = k28_mmio_widths.proof_sha256(
            mmio_width_proof
        )
    gates = {
        "pinned_source": inventory["program"]["sha256"] == root.image_sha256,
        "reset_root_exact": inventory["roots"]
        == [
            f"0x{root.reset_handler:08x}",
            f"0x{root.stage2_entry:08x}",
        ],
        "analysis_complete": bool(inventory["analysis_complete"])
        and not inventory["cancelled"]
        and inventory["unresolved_seed_count"] == 0
        and inventory["unresolved_function_count"] == 0,
        "control_flow_closed": not has_indirect_control_flow
        or control_flow_proof_sha256 is not None,
        "mmio_addresses_closed": not inventory["computed_mmio"],
        "mmio_widths_closed": mmio_width_proof_sha256 is not None
        or (
            not inventory["computed_mmio"]
            and not inventory["unknown_mmio_widths"]
            and not any(function["mmio_references"] for function in functions)
        ),
        "mmio_values_closed": not inventory["unknown_mmio_values"]
        and not any(function["mmio_references"] for function in functions),
        "polls_bounded": not inventory["unbounded_polls"]
        and not any(function["backward_branches"] for function in functions),
        "memory_ranges_closed": not inventory["unknown_memory_ranges"],
    }
    report = {
        "schema_version": 1,
        "source_sha256": root.image_sha256,
        "reset_handler": f"0x{root.reset_handler:08x}",
        "stage2_entry": f"0x{root.stage2_entry:08x}",
        "functions": functions,
        "inventory_counts": {
            "unresolved_seed_count": inventory["unresolved_seed_count"],
            "unresolved_function_count": inventory["unresolved_function_count"],
            "computed_mmio_count": len(inventory["computed_mmio"]),
            "unknown_mmio_width_count": len(inventory["unknown_mmio_widths"]),
            "unknown_mmio_value_count": len(inventory["unknown_mmio_values"]),
            "unbounded_poll_count": len(inventory["unbounded_polls"]),
            "unknown_memory_range_count": len(inventory["unknown_memory_ranges"]),
        },
        "gates": gates,
        "go": all(gates.values()),
    }
    if control_flow_proof_sha256 is not None:
        report["control_flow_proof_sha256"] = control_flow_proof_sha256
    if mmio_width_proof_sha256 is not None:
        report["mmio_width_proof_sha256"] = mmio_width_proof_sha256
    return report


def sanitize_contract(contract: dict) -> dict:
    _require_sha256(contract.get("source_sha256"), "contract source SHA-256")
    if not isinstance(contract.get("functions"), list):
        raise ValueError("contract functions must be a list")
    gates = contract.get("gates")
    if not isinstance(gates, dict) or not gates or not all(
        isinstance(value, bool) for value in gates.values()
    ):
        raise ValueError("contract gates must be a non-empty boolean object")
    if not isinstance(contract.get("go"), bool) or contract["go"] != all(
        gates.values()
    ):
        raise ValueError("contract go value contradicts its gates")
    public_functions = []
    has_indirect_control_flow = False
    for function in contract["functions"]:
        if not isinstance(function, dict):
            raise ValueError("contract function must be an object")
        _require_address(function.get("entry"), "contract function entry")
        _require_sha256(function.get("sha256"), "contract function SHA-256")
        if (
            not isinstance(function.get("depth"), int)
            or isinstance(function.get("depth"), bool)
            or not 0 <= function["depth"] <= 3
        ):
            raise ValueError("contract function depth mismatch")
        for name in (
            "direct_calls",
            "indirect_control_flow",
            "literal_references",
            "mmio_references",
            "backward_branches",
        ):
            if not isinstance(function.get(name), list):
                raise ValueError(f"contract function field {name!r} must be a list")
        has_indirect_control_flow = has_indirect_control_flow or bool(
            function["indirect_control_flow"]
        )
        public_functions.append(
            {
                "entry": function["entry"],
                "sha256": function["sha256"],
                "depth": function["depth"],
                "direct_call_count": len(function["direct_calls"]),
                "indirect_control_flow_count": len(
                    function["indirect_control_flow"]
                ),
                "literal_reference_count": len(function["literal_references"]),
                "mmio_reference_count": len(function["mmio_references"]),
                "backward_branch_count": len(function["backward_branches"]),
            }
        )
    proof_digest = contract.get("control_flow_proof_sha256")
    if gates.get("control_flow_closed") and has_indirect_control_flow:
        if proof_digest is None:
            raise ValueError(
                "closed indirect sites require a control-flow proof digest"
            )
    if proof_digest is not None and not gates.get("control_flow_closed"):
        raise ValueError("control-flow proof digest contradicts an open gate")

    inventory_counts = contract.get("inventory_counts")
    if not isinstance(inventory_counts, dict):
        raise ValueError("contract inventory counts must be an object")
    width_evidence = bool(
        inventory_counts.get("computed_mmio_count")
        or inventory_counts.get("unknown_mmio_width_count")
        or any(function["mmio_references"] for function in contract["functions"])
    )
    width_proof_digest = contract.get("mmio_width_proof_sha256")
    if gates.get("mmio_widths_closed") and width_evidence:
        if width_proof_digest is None:
            raise ValueError(
                "closed MMIO widths require an MMIO-width proof digest"
            )
    if width_proof_digest is not None and not gates.get("mmio_widths_closed"):
        raise ValueError("MMIO-width proof digest contradicts an open gate")

    receipt = {
        "schema": "flyos.fr245.k28-reset-contract.v1",
        "source_sha256": contract["source_sha256"],
        "reset_handler": contract["reset_handler"],
        "stage2_entry": contract["stage2_entry"],
        "evidence_grades": {
            "source_identity": "statically-confirmed",
            "reset_root": "statically-confirmed",
            "bounded_inventory": "statically-confirmed",
            "hardware_semantics": "unknown-until-each-false-gate-is-closed",
        },
        "inventory_counts": dict(contract["inventory_counts"]),
        "function_count": len(public_functions),
        "functions": public_functions,
        "gates": dict(contract["gates"]),
        "go": bool(contract["go"]),
    }
    if proof_digest is not None:
        receipt["control_flow_proof_sha256"] = _require_sha256(
            proof_digest,
            "control-flow proof SHA-256",
        )
    if width_proof_digest is not None:
        receipt["mmio_width_proof_sha256"] = _require_sha256(
            width_proof_digest,
            "MMIO-width proof SHA-256",
        )
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    root = commands.add_parser("root", help="write the pinned reset-root report")
    root.add_argument("--output", required=True, type=Path)
    inventory = commands.add_parser(
        "inventory", help="validate a private Ghidra evidence run"
    )
    inventory.add_argument("--run", required=True, type=Path)
    contract = commands.add_parser(
        "contract", help="write a sanitized reset-contract receipt"
    )
    contract.add_argument("--run", required=True, type=Path)
    contract.add_argument("--control-flow-proof", type=Path)
    contract.add_argument("--mmio-width-proof", type=Path)
    contract.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    try:
        if arguments.command == "root":
            write_new_json(arguments.output, _root_report(load_reset_root(repository)))
            print(arguments.output)
            return 0
        if arguments.command == "inventory":
            report = load_ghidra_run(arguments.run, load_reset_root(repository))
            print(
                json.dumps(
                    {
                        "source_sha256": report["program"]["sha256"],
                        "roots": report["roots"],
                        "function_count": len(report["functions"]),
                        "analysis_complete": report["analysis_complete"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.command == "contract":
            root = load_reset_root(repository)
            inventory = load_ghidra_run(arguments.run, root)
            proof = None
            width_proof = None
            inventory_bytes = None
            image = None
            if arguments.control_flow_proof is not None:
                try:
                    proof = json.loads(
                        arguments.control_flow_proof.read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"invalid control-flow proof: {error}"
                    ) from error
                inventory_bytes = (
                    arguments.run / "ghidra-inventory.json"
                ).read_bytes()
                image = pinned_image_path(repository).read_bytes()
            if arguments.mmio_width_proof is not None:
                try:
                    width_proof = json.loads(
                        arguments.mmio_width_proof.read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"invalid MMIO-width proof: {error}"
                    ) from error
                if inventory_bytes is None:
                    inventory_bytes = (
                        arguments.run / "ghidra-inventory.json"
                    ).read_bytes()
                    image = pinned_image_path(repository).read_bytes()
            report = build_contract(
                root,
                inventory,
                control_flow_proof=proof,
                mmio_width_proof=width_proof,
                inventory_bytes=inventory_bytes,
                image=image,
            )
            receipt = sanitize_contract(report)
            write_new_json(arguments.output, receipt)
            false_gates = [
                name for name, passed in receipt["gates"].items() if not passed
            ]
            print(
                f"go={str(receipt['go']).lower()} "
                f"false_gates={','.join(false_gates)} output={arguments.output}"
            )
            return 0 if receipt["go"] else 1
    except (FileExistsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {arguments.command}")


if __name__ == "__main__":
    raise SystemExit(main())
