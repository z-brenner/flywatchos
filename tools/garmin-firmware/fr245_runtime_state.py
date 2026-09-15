#!/usr/bin/env python3
"""Build the read-only FR245 13.70 runtime-state evidence allowlist.

This tool reads one pinned offline firmware image.  It never opens a device,
calls Garmin routines, reads live RAM/MMIO, or emits a firmware package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "Forerunner245_1370_GUPDATE"
    / "stream_01_fw_all_bin.bin"
)
SCHEMA = "flyos.fr245.runtime-state.v1"
FIRMWARE_VERSION = "13.70"
IMAGE_BASE = 0x00003000
PINNED_IMAGE_SIZE = 5_079_040
PINNED_IMAGE_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"

REQUIRED_SIGNALS = (
    "watch_face_active",
    "back_button_pass_through",
    "usb_mass_storage",
    "usb_attached",
    "charging",
    "battery_percent",
    "heart_rate_bpm",
    "motion",
    "update_pending",
    "raw_framebuffer_color_mapping",
)

PROHIBITED_OPERATIONS = [
    "callbacks",
    "getters_with_fallbacks",
    "locks",
    "peripheral_transactions",
    "writes",
]

CHANNEL_COMPONENTS = (0x00, 0x55, 0xAA, 0xFF)
CHANNEL_LEVELS = {component: level for level, component in enumerate(CHANNEL_COMPONENTS)}


class EvidenceMismatch(ValueError):
    """Raised when the input is not the exact audited firmware image."""


def rgb_to_native(red: int, green: int, blue: int) -> int:
    """Convert one exact four-level RGB cube point to the native RGB222 byte."""
    try:
        red_level = CHANNEL_LEVELS[red]
        green_level = CHANNEL_LEVELS[green]
        blue_level = CHANNEL_LEVELS[blue]
    except (KeyError, TypeError) as error:
        raise ValueError("RGB components must be one of 0x00, 0x55, 0xAA, or 0xFF") from error
    return (red_level << 4) | (green_level << 2) | blue_level


def native_to_rgb(native: int) -> tuple[int, int, int]:
    """Convert one canonical six-bit native RGB222 byte to exact RGB components."""
    if type(native) is not int or not 0 <= native < 64:
        raise ValueError("native RGB222 byte must be an integer from 0x00 through 0x3F")
    return (
        CHANNEL_COMPONENTS[(native >> 4) & 3],
        CHANNEL_COMPONENTS[(native >> 2) & 3],
        CHANNEL_COMPONENTS[native & 3],
    )


def _hex_address(value: int) -> str:
    return f"0x{value:08x}"


def _slice_at(image: bytes, virtual_address: int, length: int) -> bytes:
    offset = virtual_address - IMAGE_BASE
    if offset < 0 or offset + length > len(image):
        raise EvidenceMismatch(
            f"evidence range {_hex_address(virtual_address)}+{length} is outside the image"
        )
    return image[offset : offset + length]


def _hash_assertion(
    image: bytes,
    name: str,
    virtual_address: int,
    length: int,
    expected_sha256: str,
    description: str,
) -> dict[str, Any]:
    observed = hashlib.sha256(_slice_at(image, virtual_address, length)).hexdigest()
    return {
        "name": name,
        "kind": "sha256",
        "virtual_address": _hex_address(virtual_address),
        "length": length,
        "expected": expected_sha256,
        "observed": observed,
        "passed": observed == expected_sha256,
        "description": description,
    }


def _u32_assertion(
    image: bytes,
    name: str,
    virtual_address: int,
    expected: int,
    description: str,
) -> dict[str, Any]:
    observed = struct.unpack("<I", _slice_at(image, virtual_address, 4))[0]
    return {
        "name": name,
        "kind": "little_endian_u32",
        "virtual_address": _hex_address(virtual_address),
        "length": 4,
        "expected": _hex_address(expected),
        "observed": _hex_address(observed),
        "passed": observed == expected,
        "description": description,
    }


def _ascii_z_assertion(
    image: bytes,
    name: str,
    virtual_address: int,
    expected: str,
    description: str,
) -> dict[str, Any]:
    raw = _slice_at(image, virtual_address, len(expected.encode("ascii")) + 1)
    expected_raw = expected.encode("ascii") + b"\0"
    observed = raw[:-1].decode("ascii", errors="replace") if raw.endswith(b"\0") else raw.hex()
    return {
        "name": name,
        "kind": "ascii_z",
        "virtual_address": _hex_address(virtual_address),
        "length": len(expected_raw),
        "expected": expected,
        "observed": observed,
        "passed": raw == expected_raw,
        "description": description,
    }


def _evidence_assertions(image: bytes) -> list[dict[str, Any]]:
    return [
        _hash_assertion(
            image,
            "watch_face_finder_function",
            0x0005306C,
            22,
            "5ab36cc5d4dcdda7caeb4b6f78febb14e3d47196a480449069aae0c6688a842a",
            "Pure Thumb list walk; loads node +4/+8, compares callback identity, and returns.",
        ),
        _hash_assertion(
            image,
            "watch_face_first_visible_function",
            0x000530CC,
            28,
            "6b9074290056fd1f38bb1655d17fa81f8a91bf19a633fea98ce38f612b406b30",
            "Pure Thumb list walk; skips nodes with flags +0x50 bit 1 and compares node identity.",
        ),
        _hash_assertion(
            image,
            "watch_face_update_condition_callsite",
            0x0006BFEC,
            16,
            "37ba8789670c3625b79ab9a7ae56e3a817e2ae8ca5129ca6d7b29313f8f939a3",
            "Loads callback identity, calls the predicate pair, and branches to the not-watch-face log.",
        ),
        _u32_assertion(
            image,
            "watch_face_callback_literal",
            0x0006C0A8,
            0x0005ADF5,
            "Thumb callback identity supplied to the view-list finder.",
        ),
        _u32_assertion(
            image,
            "watch_face_list_root_literal",
            0x00053084,
            0x20003E84,
            "RAM root dereferenced by the first view-list function.",
        ),
        _u32_assertion(
            image,
            "watch_face_failure_string_pointer",
            0x0006C0E4,
            0x0006BE90,
            "Callsite literal points at the not-watch-face diagnostic string.",
        ),
        _ascii_z_assertion(
            image,
            "watch_face_failure_string",
            0x0006BE90,
            "software update condition not met, not on watch face",
            "The branch after the predicate pair is semantically tied to watch-face state.",
        ),
        _hash_assertion(
            image,
            "usb_mass_storage_mapper_function",
            0x00020578,
            48,
            "4149dd90c244cb40acb050a3e0f8122a7fe8a2272edd522c454260a55d76b184",
            "Locked official mapper reads the cached byte and maps enum states 3/4 together.",
        ),
        _u32_assertion(
            image,
            "usb_state_cache_literal",
            0x000205AC,
            0x1FFC6F25,
            "Address literal used by the official mass-storage enum mapper.",
        ),
        _hash_assertion(
            image,
            "battery_percentage_getter_a",
            0x0000BF68,
            36,
            "a21588e0883485d2d38df69a88ca2ed0d66794c175752cae5e7e5c4822016fb6",
            "Getter front end loads cache +0xc8 and falls back only for the -1.0 sentinel.",
        ),
        _hash_assertion(
            image,
            "battery_percentage_getter_b",
            0x0000BFB8,
            36,
            "1da977df4c95662467683ea2e9b1c2900a63c5ad0f9435772555d687fe62e1cc",
            "Independent identical cache front end confirms the field but is not called by FlyOS.",
        ),
        _u32_assertion(
            image,
            "battery_base_literal",
            0x0000BFDC,
            0x1FFCCC10,
            "Battery object base; the safe direct cache is base +0xc8 = 0x1ffcccd8.",
        ),
        _hash_assertion(
            image,
            "button_table",
            0x0000F9BC,
            40,
            "1486a780aafeed85e210e33b5dcd76a247229429bc8a94685ffc487004908626",
            "Five key rows; the third row is encoded pin 0x61 (GPIOD bit 1 / BACK).",
        ),
        _hash_assertion(
            image,
            "framebuffer_converter_masks",
            0x0000E3EE,
            56,
            "5d73aa977dd38b9e796105d74cdb1a06b50780a3a37b2c61bffcf9d0209302ca",
            "Converter uses complementary 0xea/0x15 masks but does not establish hue semantics.",
        ),
        _hash_assertion(
            image,
            "color_native_to_rgb_function",
            0x00063020,
            0x32,
            "96a9d40ac0e8277d634c16c4cc43bece9bb2f98295f8fb34d7e439a2e8cd1651",
            "Pinned Thumb body maps native bits 5:4, 3:2, and 1:0 to red, green, and blue levels times 85.",
        ),
        _hash_assertion(
            image,
            "color_rgb_to_native_function",
            0x00063054,
            0x4C,
            "a9fe98122781c77f9b06b35eb05f1fc7d3547f1035f3b00af36eec8b61ecba05",
            "Pinned Thumb body and magic literal quantize RGB components and pack canonical RGB222.",
        ),
        _hash_assertion(
            image,
            "color_callback_table",
            0x00064554,
            0x48,
            "4bdaeb1c029ba0ef4c6d90a1b4d77040475fa48334dd75471a8bf091cc8a1ca7",
            "Static callback table places RGB-to-native at +0x0c and native-to-RGB at +0x2c.",
        ),
        _hash_assertion(
            image,
            "color_table_setup_function",
            0x00063F1C,
            0x2A,
            "9d87b588e18b3106af96bf63e67333f243e60c79593dab528451d96ac3334985",
            "Setup copies exactly 0x48 table bytes from the pinned static source before registration.",
        ),
        _u32_assertion(
            image,
            "color_table_source_literal",
            0x00063F48,
            0x00064554,
            "Literal loaded by setup as the source of the 0x48-byte callback-table copy.",
        ),
        _u32_assertion(
            image,
            "color_rgb_to_native_table_slot",
            0x00064560,
            0x00063055,
            "Callback table +0x0c contains the odd Thumb pointer for RGB-to-native.",
        ),
        _u32_assertion(
            image,
            "color_native_to_rgb_table_slot",
            0x00064580,
            0x00063021,
            "Callback table +0x2c contains the odd Thumb pointer for native-to-RGB.",
        ),
        _ascii_z_assertion(
            image,
            "install_now_resource_string",
            0x00442A64,
            "Install Now",
            "Resource text exists, but it is not a pending-update state getter.",
        ),
        _ascii_z_assertion(
            image,
            "install_later_resource_string",
            0x00442A70,
            "Install Later",
            "Resource text exists, but it is not a pending-update state getter.",
        ),
        _ascii_z_assertion(
            image,
            "charging_resource_string",
            0x00444E64,
            "Charging",
            "Resource text exists, but it is not a side-effect-free charging-state cache.",
        ),
    ]


def _available_signal(
    source: dict[str, Any], validity_semantics: str, evidence: list[str]
) -> dict[str, Any]:
    return {
        "status": "available",
        "source": source,
        "validity_semantics": validity_semantics,
        "side_effect_free": {"proved": True, "evidence": evidence},
        "fallback": "zero_or_dash",
        "prohibited_operations": list(PROHIBITED_OPERATIONS),
    }


def _unavailable_signal(reason: str, evidence: list[str]) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "source": {},
        "validity_semantics": "No valid runtime value is defined; contribute zero and display --.",
        "side_effect_free": {"proved": False, "evidence": evidence},
        "fallback": "zero_or_dash",
        "prohibited_operations": list(PROHIBITED_OPERATIONS),
        "reason": reason,
    }


def _signals() -> dict[str, dict[str, Any]]:
    return {
        "watch_face_active": _available_signal(
            {
                "kind": "pure_function_pair",
                "image_addresses": ["0x0005306c", "0x000530cc"],
                "callable_addresses": ["0x0005306d", "0x000530cd"],
                "instruction_set": "thumb",
                "thumb": True,
                "callback_identity": "0x0005adf5",
                "list_root": "0x20003e84",
                "allowed_node_offsets": ["0x04", "0x08", "0x50"],
                "runtime_emulation_required_before_integration": True,
            },
            "Call Thumb address 0x0005306d with callback 0x0005adf5; its node must be nonzero, then call Thumb address 0x000530cd with that node. The second result must be a value that equals 1. Never call the even image addresses. Empty, malformed, unexpected, or false results fail closed to no overlay.",
            [
                "Pinned function bodies contain loads, compares, branches, moves, CLZ, and return only; no call or store.",
                "Pinned update-condition callsite and failure string bind the pair to watch-face state.",
                "Task 4 must bound every list read and control-flow target before target integration.",
            ],
        ),
        "back_button_pass_through": _available_signal(
            {
                "kind": "direct_mmio_word_bit",
                "pinned_addresses": ["0x400ff0d0"],
                "bit": 1,
                "button_table_address": "0x0000f9bc",
            },
            "BACK is active-low GPIOD PDIR bit 1: a zero bit means held and suppresses all overlay framebuffer writes.",
            [
                "The pinned five-row key table assigns encoded pin 0x61 to the third key.",
                "A single PDIR load is read-only and performs no callback, lock, store, or bus transaction.",
            ],
        ),
        "usb_mass_storage": _available_signal(
            {
                "kind": "direct_ram_byte",
                "pinned_addresses": ["0x1ffc6f25"],
                "true_values": [3, 4],
                "width_bits": 8,
            },
            "Only cached enum byte values 3 or 4 mean USB mass-storage mode. Every other value is false for this narrow signal and must not imply cable attach or charging.",
            [
                "The pinned official mapper reads this byte and groups only states 3 and 4.",
                "The FlyOS adapter performs one atomic byte load and never calls the lock-taking official mapper.",
            ],
        ),
        "usb_attached": _unavailable_signal(
            "No nearby USB-manager byte has been semantically tied to generic cable-present state.",
            ["Mass-storage states 3/4 are narrower than cable attachment and cannot be relabeled."],
        ),
        "charging": _unavailable_signal(
            "The charger accessor dispatches through a callback; PMIC alternatives perform bus I/O.",
            ["The pinned Charging resource string supplies UI text only, not a runtime cache."],
        ),
        "battery_percent": _available_signal(
            {
                "kind": "direct_ram_float32",
                "pinned_addresses": ["0x1ffcccd8"],
                "encoding": "IEEE-754 binary32 little-endian",
                "sentinel": -1.0,
                "accepted_range": [0.0, 100.0],
            },
            "Read the cache directly. -1.0 is invalid; accept only finite values in [0, 100]. Any NaN, infinity, out-of-range value, or sentinel contributes zero and displays --.",
            [
                "Two pinned getter front ends independently load object base +0xc8.",
                "Direct cache access avoids their -1.0 fallback callback and performs one RAM load only.",
            ],
        ),
        "heart_rate_bpm": _unavailable_signal(
            "No stable BPM cache/getter with freshness and off-wrist validity is pinned.",
            ["A broadcasting-HR boolean and heartRateBeatsPerMin resource text do not expose BPM."],
        ),
        "motion": _unavailable_signal(
            "No pure normalized motion snapshot with freshness semantics is pinned.",
            ["Apollo2 transport and activity bookkeeping require unproved protocol/list access."],
        ),
        "update_pending": _unavailable_signal(
            "Update eligibility is not update presence, and no stable pending-update RAM bit is pinned.",
            ["Install Now/Install Later are resource strings only; Garmin's stock modal must pass through."],
        ),
        "raw_framebuffer_color_mapping": _unavailable_signal(
            "This entry is reserved for a live runtime state source; the resolved static RGB222 mapping is exposed in target_palette instead.",
            ["No runtime read is needed. Pinned inverse conversion functions and callback-table evidence define the static target palette."],
        ),
    }


def _rgb_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02X}{green:02X}{blue:02X}"


def _palette_role(red: int, green: int, blue: int) -> dict[str, str]:
    return {
        "native_byte": f"0x{rgb_to_native(red, green, blue):02x}",
        "rgb": _rgb_hex(red, green, blue),
    }


def _target_palette() -> dict[str, Any]:
    return {
        "encoding": "RGB222",
        "formula": "native=(R_level<<4)|(G_level<<2)|B_level",
        "channel_levels": [
            {"level": level, "component": f"0x{component:02X}"}
            for level, component in enumerate(CHANNEL_COMPONENTS)
        ],
        "roles": {
            "background": _palette_role(0x00, 0x00, 0x00),
            "scaffold": _palette_role(0xAA, 0xAA, 0xAA),
            "text": _palette_role(0xFF, 0xFF, 0xFF),
            "excitatory": _palette_role(0x00, 0xFF, 0x00),
            "inhibitory": _palette_role(0xFF, 0x00, 0xFF),
            "saturated": _palette_role(0xFF, 0xAA, 0x00),
        },
    }


def _roundtrip_evidence() -> dict[str, Any]:
    rgb_points = set()
    for native in range(64):
        rgb = native_to_rgb(native)
        if rgb_to_native(*rgb) != native:
            raise EvidenceMismatch(f"RGB222 round-trip failed for native 0x{native:02x}")
        rgb_points.add(rgb)
    if len(rgb_points) != 64:
        raise EvidenceMismatch("RGB222 conversion did not produce 64 unique cube points")
    return {"native_values": 64, "rgb_cube_points": 64, "all_passed": True}


def _target_palette_evidence() -> dict[str, Any]:
    return {
        "mapping_proved": True,
        "source_audit": {
            "path": ".superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-3-color-scout.md",
            "sha256": "3c8f643f08d92de5682803a1e883ad1048bef36d97d471ad8eea9676fc6daad2",
        },
        "functions": {
            "native_to_rgb": {
                "image_address": "0x00063020",
                "callable_address": "0x00063021",
                "instruction_set": "thumb",
                "thumb": True,
                "length": 50,
                "evidence_assertion": "color_native_to_rgb_function",
            },
            "rgb_to_native": {
                "image_address": "0x00063054",
                "callable_address": "0x00063055",
                "instruction_set": "thumb",
                "thumb": True,
                "length": 76,
                "evidence_assertion": "color_rgb_to_native_function",
            },
        },
        "callback_table": {
            "image_address": "0x00064554",
            "length": 72,
            "rgb_to_native_slot_offset": "0x0c",
            "rgb_to_native_pointer": "0x00063055",
            "native_to_rgb_slot_offset": "0x2c",
            "native_to_rgb_pointer": "0x00063021",
            "evidence_assertion": "color_callback_table",
        },
        "setup_copy": {
            "image_address": "0x00063f1c",
            "callable_address": "0x00063f1d",
            "instruction_set": "thumb",
            "thumb": True,
            "source_address": "0x00064554",
            "source_literal_address": "0x00063f48",
            "byte_count": 72,
            "evidence_assertion": "color_table_setup_function",
        },
        "roundtrip": _roundtrip_evidence(),
    }


def _build_report(image_sha256: str, assertions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "device": "Garmin Forerunner 245 non-Music",
        "firmware_version": FIRMWARE_VERSION,
        "image": {
            "path": "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin",
            "base_address": _hex_address(IMAGE_BASE),
            "size": PINNED_IMAGE_SIZE,
            "sha256": image_sha256,
        },
        "analysis_mode": "offline_read_only",
        "signals": _signals(),
        "target_palette_status": "available",
        "target_palette": _target_palette(),
        "target_palette_evidence": _target_palette_evidence(),
        "evidence_assertions": assertions,
        "integration_gate": {
            "watch_face_predicate_requires_task4_emulation": True,
            "false_or_invalid_home_result": "leave framebuffer byte-identical",
            "back_held": "leave framebuffer byte-identical",
            "stock_update_modal": "Garmin-owned; START remains Garmin confirmation",
        },
        "tool": "tools/garmin-firmware/fr245_runtime_state.py",
    }


def _verified_report(image_path: Path | str) -> dict[str, Any]:
    image_path = Path(image_path)
    image = image_path.read_bytes()
    image_sha256 = hashlib.sha256(image).hexdigest()
    if len(image) != PINNED_IMAGE_SIZE:
        raise EvidenceMismatch(
            f"image size mismatch: expected {PINNED_IMAGE_SIZE}, observed {len(image)}"
        )
    if image_sha256 != PINNED_IMAGE_SHA256:
        raise EvidenceMismatch(
            f"image SHA-256 mismatch: expected {PINNED_IMAGE_SHA256}, observed {image_sha256}"
        )

    assertions = _evidence_assertions(image)
    failures = [item["name"] for item in assertions if not item["passed"]]
    if failures:
        raise EvidenceMismatch("pinned evidence mismatch: " + ", ".join(failures))
    return _build_report(image_sha256, assertions)


def _first_difference(actual: Any, expected: Any, path: str = "$") -> str | None:
    """Return the first exact canonical mismatch, including unknown content."""
    if type(actual) is not type(expected):
        return f"{path}: type {type(actual).__name__} != {type(expected).__name__}"
    if isinstance(expected, dict):
        actual_keys = set(actual)
        expected_keys = set(expected)
        if actual_keys != expected_keys:
            added = sorted(actual_keys - expected_keys)
            removed = sorted(expected_keys - actual_keys)
            return f"{path}: added keys={added}, missing keys={removed}"
        for key in expected:
            difference = _first_difference(actual[key], expected[key], f"{path}.{key}")
            if difference is not None:
                return difference
        return None
    if isinstance(expected, list):
        if len(actual) != len(expected):
            return f"{path}: length {len(actual)} != {len(expected)}"
        for index, expected_item in enumerate(expected):
            difference = _first_difference(actual[index], expected_item, f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    if actual != expected:
        return f"{path}: {actual!r} != {expected!r}"
    return None


def validate_report(report: dict[str, Any]) -> None:
    """Accept only the exact image-derived canonical allowlist."""
    canonical = _verified_report(DEFAULT_IMAGE)
    difference = _first_difference(report, canonical)
    if difference is not None:
        raise ValueError(f"canonical allowlist mismatch: {difference}")


def analyze(image_path: Path | str) -> dict[str, Any]:
    report = _verified_report(image_path)
    validate_report(report)
    return report

def serialize_report(report: dict[str, Any]) -> str:
    validate_report(report)
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    args = parser.parse_args()
    sys.stdout.buffer.write(serialize_report(analyze(args.image)).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
