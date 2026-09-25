"""Hash-bound proof for the FR245 K28 reset closure's indirect control flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import k28_reset_contract as reset_contract


SCHEMA = "flyos.fr245.k28-control-flow.v1"
INVENTORY_NAME = "ghidra-inventory.json"
PINNED_INVENTORY_SHA256 = (
    "afd7c6ecb339e52d4af37af9d6c46825d4cd4d8a6c0718a7662022940c27b0e9"
)

EXPECTED_OWNERS = {
    "0x000031f0": (
        "8b3332257310218f1fc5c4d3687a22214dc781d585cf49ad6908d7ca3d248d63",
        ("0x00003204",),
    ),
    "0x00018dfc": (
        "e1046b2944a7ebc3632e2503b3f65662397dd33175b6148341a877676bf71e58",
        ("0x00018e08", "0x00018f5e"),
    ),
    "0x0001a51c": (
        "0c536bc264782c09274aed518393dec3e7bedf0c79e5bbfe9a8fd7cd90851f78",
        ("0x0001a522",),
    ),
    "0x0001a810": (
        "cf003316b7c4e5ce3f1ba6e2ecc7be08a5fa8d880949498c7ce965135c82f2a6",
        ("0x0001a85a",),
    ),
    "0x0001a868": (
        "7ddb710b2dc4caa5ed487ff1ff835458480e3c45696da4c5c1795252cf17d7d1",
        ("0x0001a8d0",),
    ),
    "0x0001a8dc": (
        "9d75de9b7b0998d77f186ad4218180fc9ed1f9cb6484b1496a5ed88c0e3e79ab",
        ("0x0001a930",),
    ),
    "0x0001a940": (
        "1174e1594ac13cfc8486e5e540d421794be007c3105ffe93c4b60771d2311e03",
        ("0x0001a9a0",),
    ),
    "0x0001aa34": (
        "826aabb5665ad1e5ff0040bdf58c1482db1960770da1f1de2dbdd42095e27a2b",
        ("0x0001aa88",),
    ),
}

SWITCH_SPECS = (
    {
        "site": 0x00018E08,
        "kind": "tbh",
        "entry_count": 143,
        "window_start": 0x00018DFE,
        "window_end_exclusive": 0x00018F2A,
        "window_sha256": "aa97234417cbfe1abda9659fb4536ebcb1b238b3700db37e33c08dc5cb55ecd8",
        "targets_sha256": "354973fe5ae31e61a3508344203a61ce886b5dc014f0c8fcc6d7d61c2be270d5",
    },
    {
        "site": 0x00018F5E,
        "kind": "tbb",
        "entry_count": 5,
        "window_start": 0x00018F54,
        "window_end_exclusive": 0x00018F68,
        "window_sha256": "5372dc51692e24ab4d3ec924b358dbb56f7f0ff947faef7bf1727af0decdf2bc",
        "targets_sha256": "273b28aef864dd83fc5d68c156ca953bebb451ad5a98648b378c55358ea271b7",
    },
    {
        "site": 0x0001A522,
        "kind": "tbb",
        "entry_count": 21,
        "window_start": 0x0001A51E,
        "window_end_exclusive": 0x0001A53B,
        "window_sha256": "669d96434dd0ea1465e7971179a98d387523b66bc7afeb798470c31846310840",
        "targets_sha256": "d341e25c012927f2382f2c7a0f55e788c7925231f151186bf259091844da927b",
    },
    {
        "site": 0x0001AA88,
        "kind": "tbb",
        "entry_count": 8,
        "window_start": 0x0001AA82,
        "window_end_exclusive": 0x0001AA94,
        "window_sha256": "9abaa836ca31e2c25a5d07a3683613e6ae51d67824470bf3d8486512bb56c723",
        "targets_sha256": "85761cd06803342d7516d3e69c55343ae9e4973194a974acfeec114a1bd03078",
    },
)

CALLBACK_WINDOWS = (
    (0x0001A810, 0x0001A864, "cf003316b7c4e5ce3f1ba6e2ecc7be08a5fa8d880949498c7ce965135c82f2a6", 0x0001A85A),
    (0x0001A868, 0x0001A8D8, "bad93d5dcc4654230ef651b608210f544e0190d17bd1add0f607bd2f4a35cd83", 0x0001A8D0),
    (0x0001A8DC, 0x0001A93C, "91edc9a2acbaff4410f84137ba321b0bb530cc44e0ded7fe13b4164c4551b4d4", 0x0001A930),
    (0x0001A940, 0x0001A9A8, "4cfa4ab2d80a868f015ebfdc302cc47fe5ab1e5e8fb31c96df8ada938b61e8b5", 0x0001A9A0),
)

CALL_SITES = (
    (0x0001AAC0, 0x0001A9A0, "r3", "null"),
    (0x0001AAD4, 0x0001A8D0, "r3", "0x0001a298"),
    (0x0001AAF8, 0x0001A930, "r1", "null"),
    (0x0001AB1A, 0x0001A85A, "r1", "0x0001a298"),
    (0x0001AB46, 0x0001A85A, "r1", "null"),
    (0x0001AB5A, 0x0001A85A, "r1", "0x0001a298"),
)


def _address(value: int) -> str:
    return f"0x{value:08x}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def proof_sha256(proof: dict) -> str:
    encoded = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    return _sha256(encoded)


def _window(image: bytes, start: int, end_exclusive: int, expected: str) -> dict:
    first = start - reset_contract.APP_BASE
    last = end_exclusive - reset_contract.APP_BASE
    if first < 0 or last > len(image) or first >= last:
        raise ValueError("control-flow proof window is outside the pinned image")
    actual = _sha256(image[first:last])
    if actual != expected:
        raise ValueError(f"control-flow window SHA-256 mismatch at {_address(start)}")
    return {
        "start": _address(start),
        "end_exclusive": _address(end_exclusive),
        "sha256": actual,
    }


def _validate_inventory(inventory: dict) -> list[str]:
    functions = inventory.get("functions")
    if not isinstance(functions, list):
        raise ValueError("control-flow inventory functions must be a list")
    by_entry = {
        function.get("entry"): function
        for function in functions
        if isinstance(function, dict) and isinstance(function.get("entry"), str)
    }
    actual_sites = sorted(
        site
        for function in functions
        if isinstance(function, dict)
        for site in function.get("indirect_control_flow", [])
    )
    expected_sites = sorted(
        site for _, sites in EXPECTED_OWNERS.values() for site in sites
    )
    if actual_sites != expected_sites:
        raise ValueError("control-flow indirect-site set mismatch")
    for entry, (function_sha256, sites) in EXPECTED_OWNERS.items():
        function = by_entry.get(entry)
        if function is None:
            raise ValueError(f"missing indirect-site owner {entry}")
        if function.get("sha256") != function_sha256:
            raise ValueError(f"indirect-site owner SHA-256 mismatch at {entry}")
        if tuple(function.get("indirect_control_flow", ())) != sites:
            raise ValueError(f"indirect-site owner mismatch at {entry}")

    callback_entries = {entry for entry, _, _, _ in CALLBACK_WINDOWS}
    dispatcher = _address(0x0001AA34)
    for callback_entry in callback_entries:
        target = _address(callback_entry)
        callers = {
            function.get("entry")
            for function in functions
            if target in function.get("direct_calls", [])
        }
        if callers != {dispatcher}:
            raise ValueError(f"callback caller set mismatch for {target}")
    return actual_sites


def _validate_inventory_snapshot(inventory: dict, inventory_bytes: bytes) -> str:
    try:
        decoded = json.loads(inventory_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid control-flow inventory snapshot: {error}") from error
    if decoded != inventory:
        raise ValueError("control-flow inventory snapshot mismatch")
    inventory_sha256 = _sha256(inventory_bytes)
    if inventory_sha256 != PINNED_INVENTORY_SHA256:
        raise ValueError("control-flow inventory snapshot SHA-256 mismatch")
    return inventory_sha256


def _switch_proof(image: bytes, spec: dict) -> dict:
    site = spec["site"]
    kind = spec["kind"]
    width = 1 if kind == "tbb" else 2
    table_start = site + 4
    first = table_start - reset_contract.APP_BASE
    raw = image[first : first + spec["entry_count"] * width]
    if len(raw) != spec["entry_count"] * width:
        raise ValueError(f"truncated switch table at {_address(site)}")
    entries = [
        int.from_bytes(raw[index : index + width], "little")
        for index in range(0, len(raw), width)
    ]
    targets = [table_start + 2 * entry for entry in entries]
    serialized = ",".join(_address(target) for target in targets).encode("ascii")
    targets_sha256 = _sha256(serialized)
    if targets_sha256 != spec["targets_sha256"]:
        raise ValueError(f"switch-target SHA-256 mismatch at {_address(site)}")
    return {
        "site": _address(site),
        "kind": kind,
        "index_max": spec["entry_count"] - 1,
        "entry_count": spec["entry_count"],
        "guard_and_table_window": _window(
            image,
            spec["window_start"],
            spec["window_end_exclusive"],
            spec["window_sha256"],
        ),
        "unique_target_count": len(set(targets)),
        "target_min": _address(min(targets)),
        "target_max": _address(max(targets)),
        "targets_sha256": targets_sha256,
    }


def build_control_flow_proof(
    image: bytes, inventory: dict, inventory_bytes: bytes
) -> dict:
    source_sha256 = _sha256(image)
    if source_sha256 != reset_contract.PINNED_IMAGE_SHA256:
        raise ValueError("control-flow source SHA-256 mismatch")
    inventory_sha256 = _validate_inventory_snapshot(inventory, inventory_bytes)
    indirect_sites = _validate_inventory(inventory)

    reset_window = _window(
        image,
        0x000031F0,
        0x00003206,
        "8b3332257310218f1fc5c4d3687a22214dc781d585cf49ad6908d7ca3d248d63",
    )
    pointer_offset = 0x0000320C - reset_contract.APP_BASE
    pointer = int.from_bytes(image[pointer_offset : pointer_offset + 4], "little")
    if pointer != 0x00019341:
        raise ValueError("reset transfer pointer mismatch")

    switches = [_switch_proof(image, spec) for spec in SWITCH_SPECS]
    callback_functions = []
    for start, end, digest, site in CALLBACK_WINDOWS:
        callback_functions.append(
            {
                "entry": _address(start),
                "indirect_site": _address(site),
                "window": _window(image, start, end, digest),
            }
        )
    literal_offset = 0x0001AB78 - reset_contract.APP_BASE
    literal_pointer = int.from_bytes(
        image[literal_offset : literal_offset + 4], "little"
    )
    if literal_pointer != 0x0001A299:
        raise ValueError("callback literal pointer mismatch")

    return {
        "schema": SCHEMA,
        "source_sha256": source_sha256,
        "inventory_sha256": inventory_sha256,
        "indirect_sites": indirect_sites,
        "reset_transfer": {
            "site": "0x00003204",
            "instruction_window": reset_window,
            "literal_address": "0x0000320c",
            "pointer": _address(pointer),
            "target": _address(pointer & ~1),
        },
        "switches": switches,
        "callbacks": {
            "dispatcher_window": _window(
                image,
                0x0001AA34,
                0x0001AB6E,
                "2565595bdd6daf150bca336654cc8fc0f47a4ab59e9c3a4ac2c617bb9bee820e",
            ),
            "functions": callback_functions,
            "literal_window": _window(
                image,
                0x0001AB78,
                0x0001AB7C,
                "5a57103fac8c89b5ac8456f33a9cf63991ba583f9ea900817d234d7950eb1766",
            ),
            "literal_pointer": _address(literal_pointer),
            "resolved_target": _address(literal_pointer & ~1),
            "target_window": _window(
                image,
                0x0001A298,
                0x0001A2B8,
                "0eab1a743cd901898b069bc86aa2a178089c0598e7c9cf3ae2cc4fa8893c0969",
            ),
            "call_sites": [
                {
                    "site": _address(site),
                    "callback_site": _address(callback_site),
                    "register": register,
                    "value": value,
                }
                for site, callback_site, register, value in CALL_SITES
            ],
        },
        "gates": {
            "inventory_sites_exact": True,
            "reset_transfer_resolved": True,
            "switch_tables_bounded": True,
            "callback_values_resolved": True,
        },
        "control_flow_closed": True,
    }


def validate_control_flow_proof(
    image: bytes, inventory: dict, inventory_bytes: bytes, proof: dict
) -> None:
    expected = build_control_flow_proof(image, inventory, inventory_bytes)
    if proof != expected:
        raise ValueError("control-flow proof mismatch")


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
        proof = build_control_flow_proof(
            reset_contract.pinned_image_path(repository).read_bytes(),
            inventory,
            inventory_bytes,
        )
        reset_contract.write_new_json(arguments.output, proof)
        print(
            f"control_flow_closed=true sites={len(proof['indirect_sites'])} "
            f"output={arguments.output}"
        )
        return 0
    except (FileExistsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
