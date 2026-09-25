"""Fail-closed offline reset-contract analysis for the FR245 13.70 image."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
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
        entry = function["entry"]
        if not isinstance(entry, str) or not entry.startswith("0x"):
            raise ValueError("inventory function entry mismatch")
        entries.append(int(entry, 16))
        if not isinstance(function["sha256"], str) or len(function["sha256"]) != 64:
            raise ValueError("inventory function SHA-256 mismatch")
        if not isinstance(function["depth"], int) or function["depth"] < 0:
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    root = commands.add_parser("root", help="write the pinned reset-root report")
    root.add_argument("--output", required=True, type=Path)
    inventory = commands.add_parser(
        "inventory", help="validate a private Ghidra evidence run"
    )
    inventory.add_argument("--run", required=True, type=Path)
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
    except (FileExistsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {arguments.command}")


if __name__ == "__main__":
    raise SystemExit(main())
