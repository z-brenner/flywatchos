"""Fail-closed MMIO access-width proof for the FR245 K28 reset closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_MCLASS, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC

import k28_reset_contract as reset_contract


SCHEMA = "flyos.fr245.k28-mmio-widths.v1"
INVENTORY_NAME = "ghidra-inventory.json"
PINNED_INVENTORY_SHA256 = (
    "afd7c6ecb339e52d4af37af9d6c46825d4cd4d8a6c0718a7662022940c27b0e9"
)

ACCESS_CLASSES = {
    "ldrb": ("read", 1, 1, "ldrb", "byte"),
    "ldrsb": ("read", 1, 1, "ldrsb", "byte"),
    "strb": ("write", 1, 1, "strb", "byte"),
    "ldrh": ("read", 2, 1, "ldrh", "halfword"),
    "strh": ("write", 2, 1, "strh", "halfword"),
    "ldr": ("read", 4, 1, "ldr", "word"),
    "str": ("write", 4, 1, "str", "word"),
    "ldrd": ("read", 4, 2, "ldrd", "paired_words"),
    "strd": ("write", 4, 2, "strd", "paired_words"),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def proof_sha256(proof: dict) -> str:
    encoded = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(encoded)


def _address(value: int) -> str:
    return f"0x{value:08x}"


def _validate_inventory_snapshot(inventory: dict, inventory_bytes: bytes) -> str:
    try:
        decoded = json.loads(inventory_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid MMIO-width inventory snapshot: {error}") from error
    if decoded != inventory:
        raise ValueError("MMIO-width inventory snapshot mismatch")
    digest = _sha256(inventory_bytes)
    if digest != PINNED_INVENTORY_SHA256:
        raise ValueError("MMIO-width inventory snapshot SHA-256 mismatch")
    return digest


def _decoder() -> Cs:
    decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
    decoder.detail = True
    return decoder


def _instruction(image: bytes, decoder: Cs, address: int):
    offset = address - reset_contract.APP_BASE
    if offset < 0 or offset + 2 > len(image):
        raise ValueError(f"MMIO-width instruction outside image: {_address(address)}")
    instructions = list(decoder.disasm(image[offset : offset + 4], address, count=1))
    if not instructions or instructions[0].address != address:
        raise ValueError(f"MMIO-width instruction did not decode: {_address(address)}")
    return instructions[0]


def _classify_access(instruction) -> dict:
    mnemonic = instruction.mnemonic.split(".", 1)[0]
    if mnemonic == "vldr":
        destination = instruction.op_str.split(",", 1)[0].strip().lower()
        if not destination.startswith("s"):
            raise ValueError(
                f"unsupported VFP access width at {_address(instruction.address)}"
            )
        direction, beat_width, beat_count = "read", 4, 1
        instruction_class, transfer_class = "vldr_s", "word"
    else:
        classification = ACCESS_CLASSES.get(mnemonic)
        if classification is None:
            raise ValueError(
                f"unknown MMIO access width at {_address(instruction.address)}: "
                f"{instruction.mnemonic}"
            )
        (
            direction,
            beat_width,
            beat_count,
            instruction_class,
            transfer_class,
        ) = classification
    return {
        "instruction": _address(instruction.address),
        "direction": direction,
        "beat_width_bytes": beat_width,
        "beat_count": beat_count,
        "transfer_span_bytes": beat_width * beat_count,
        "instruction_class": instruction_class,
        "transfer_class": transfer_class,
    }


def _is_literal_load(instruction) -> bool:
    mnemonic = instruction.mnemonic.split(".", 1)[0]
    return (
        mnemonic == "ldr"
        and len(instruction.operands) >= 2
        and instruction.operands[1].type == ARM_OP_MEM
        and instruction.operands[1].mem.base == ARM_REG_PC
    )


def _classify_materialization(
    image: bytes, instruction, reference: dict
) -> dict:
    mnemonic = instruction.mnemonic.split(".", 1)[0]
    result = {
        "instruction": _address(instruction.address),
        "target": reference["address"],
    }
    if _is_literal_load(instruction):
        literal_address = (
            (instruction.address + 4) & ~3
        ) + instruction.operands[1].mem.disp
        offset = literal_address - reset_contract.APP_BASE
        if offset < 0 or offset + 4 > len(image):
            raise ValueError(
                f"MMIO address literal outside image at "
                f"{_address(instruction.address)}"
            )
        literal_value = int.from_bytes(image[offset : offset + 4], "little")
        if literal_value != int(reference["address"], 16):
            raise ValueError(
                f"MMIO address literal contradicts reference at "
                f"{_address(instruction.address)}"
            )
        materialization_class = "ldr_literal"
        result["literal_address"] = _address(literal_address)
    elif mnemonic == "mov" and "[" not in instruction.op_str:
        materialization_class = "register_move"
    else:
        raise ValueError(
            f"PARAM reference is not a pure address materialization at "
            f"{_address(instruction.address)}"
        )
    result["materialization_class"] = materialization_class
    return result


def _canonical_digest(accesses: list[dict], materializations: list[dict]) -> str:
    encoded = json.dumps(
        {"accesses": accesses, "materializations": materializations},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256(encoded)


def build_mmio_width_proof(
    image: bytes, inventory: dict, inventory_bytes: bytes
) -> dict:
    source_sha256 = _sha256(image)
    if source_sha256 != reset_contract.PINNED_IMAGE_SHA256:
        raise ValueError("MMIO-width source SHA-256 mismatch")
    root = reset_contract.decode_pinned_image(image)
    reset_contract.validate_ghidra_inventory(inventory, root)
    inventory_sha256 = _validate_inventory_snapshot(inventory, inventory_bytes)

    decoder = _decoder()
    direct_addresses: set[int] = set()
    materializations = []
    direct_rows = inventory["unknown_mmio_widths"]
    for reference in direct_rows:
        address = int(reference["from"], 16)
        instruction = _instruction(image, decoder, address)
        reference_type = reference["type"]
        if reference_type not in ("READ", "WRITE", "DATA", "PARAM"):
            raise ValueError(f"unknown MMIO reference type: {reference_type}")
        if reference_type == "PARAM" or _is_literal_load(instruction):
            materializations.append(
                _classify_materialization(image, instruction, reference)
            )
            continue
        classification = _classify_access(instruction)
        if reference_type == "READ" and classification["direction"] != "read":
            raise ValueError(f"READ reference uses a store at {_address(address)}")
        if reference_type == "WRITE" and classification["direction"] != "write":
            raise ValueError(f"WRITE reference uses a load at {_address(address)}")
        direct_addresses.add(address)

    computed_addresses: set[int] = set()
    for row in inventory["computed_mmio"]:
        address = int(row["instruction"], 16)
        classification = _classify_access(_instruction(image, decoder, address))
        expected_operation = (
            "LOAD" if classification["direction"] == "read" else "STORE"
        )
        if row["operation"] != expected_operation:
            raise ValueError(
                f"computed operation contradicts instruction at {_address(address)}"
            )
        computed_addresses.add(address)

    access_addresses = sorted(direct_addresses | computed_addresses)
    accesses = [
        _classify_access(_instruction(image, decoder, address))
        for address in access_addresses
    ]
    materializations.sort(key=lambda row: (row["instruction"], row["target"]))

    instruction_classes = Counter(
        row["instruction_class"] for row in accesses
    )
    transfer_classes = Counter(row["transfer_class"] for row in accesses)
    direction_counts = Counter(row["direction"] for row in accesses)
    beat_counts = Counter(
        "one" if row["beat_count"] == 1 else "two" for row in accesses
    )
    materialization_classes = Counter(
        row["materialization_class"] for row in materializations
    )

    return {
        "schema": SCHEMA,
        "source_sha256": source_sha256,
        "inventory_sha256": inventory_sha256,
        "evidence_counts": {
            "computed_rows": len(inventory["computed_mmio"]),
            "computed_unique_instructions": len(computed_addresses),
            "direct_reference_rows": len(direct_rows) - len(materializations),
            "direct_unique_instructions": len(direct_addresses),
            "materialization_rows": len(materializations),
            "overlapping_access_instructions": len(
                direct_addresses & computed_addresses
            ),
            "unique_access_instructions": len(accesses),
        },
        "transfer_classes": dict(sorted(transfer_classes.items())),
        "direction_counts": dict(sorted(direction_counts.items())),
        "beat_counts": dict(sorted(beat_counts.items())),
        "instruction_classes": dict(sorted(instruction_classes.items())),
        "materialization_classes": dict(
            sorted(materialization_classes.items())
        ),
        "classified_rows_sha256": _canonical_digest(
            accesses, materializations
        ),
        "gates": {
            "source_exact": True,
            "inventory_snapshot_exact": True,
            "direct_references_classified": True,
            "computed_accesses_classified": True,
            "address_materializations_excluded": True,
        },
        "mmio_widths_closed": True,
    }


def validate_mmio_width_proof(
    image: bytes, inventory: dict, inventory_bytes: bytes, proof: dict
) -> None:
    expected = build_mmio_width_proof(image, inventory, inventory_bytes)
    if proof != expected:
        raise ValueError("MMIO-width proof mismatch")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    try:
        root = reset_contract.load_reset_root(repository)
        inventory = reset_contract.load_ghidra_run(arguments.run, root)
        inventory_bytes = (arguments.run / INVENTORY_NAME).read_bytes()
        proof = build_mmio_width_proof(
            reset_contract.pinned_image_path(repository).read_bytes(),
            inventory,
            inventory_bytes,
        )
        reset_contract.write_new_json(arguments.output, proof)
        print(
            f"mmio_widths_closed=true "
            f"accesses={proof['evidence_counts']['unique_access_instructions']} "
            f"output={arguments.output}"
        )
        return 0
    except (FileExistsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
