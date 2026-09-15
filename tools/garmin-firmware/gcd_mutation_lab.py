#!/usr/bin/env python3
"""Create a metadata-only GCD checksum laboratory copy.

This tool changes only the final printable byte of the copyright metadata
record (``.`` to ``!``) and recomputes documented one-byte GCD checkpoints.
It deliberately has no option to alter a firmware stream, descriptor, version,
or target address. It is for offline format analysis only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gcd_inspect  # noqa: E402


KNOWN_SOURCE_SHA256 = {
    "ffc802fd505cb62fe680dd50935654ef8177c8a0c74d20de3a6b32a4d185ff43": "Forerunner 245 non-Music 3.10",
    "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc": "Forerunner 245 non-Music 13.70",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recompute_checkpoints(data: bytes, inspect: Any = gcd_inspect) -> bytes:
    """Recompute the documented additive checkpoint bytes in record order."""
    mutable = bytearray(data)
    gcd = inspect.parse_gcd(bytes(mutable))
    for record in gcd.records:
        if record.record_id != 0x0001 or record.length != 1:
            continue
        checksum_offset = record.offset + 4
        mutable[checksum_offset] = 0
        mutable[checksum_offset] = (-sum(mutable[: checksum_offset + 1])) & 0xFF
    result = bytes(mutable)
    validated = inspect.parse_gcd(result)
    if not all(item["valid"] for item in inspect._checkpoint_results(validated)):
        raise ValueError("checkpoint recomputation did not validate")
    return result


def mutate_copyright_metadata(
    source: Path, output: Path, inspect: Any = gcd_inspect
) -> dict[str, Any]:
    """Write a same-length metadata-only laboratory copy without touching source."""
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("output must be a separate analysis file")

    original = source.read_bytes()
    gcd = inspect.parse_gcd(original)
    matches = [record for record in gcd.records if record.record_id == 0x0005]
    if len(matches) != 1 or not matches[0].body.endswith(b"."):
        raise ValueError("expected one terminal-period copyright record")
    record = matches[0]
    offset = record.offset + 4 + len(record.body) - 1
    mutated = bytearray(original)
    mutated[offset] = ord("!")
    result = recompute_checkpoints(bytes(mutated), inspect)
    if len(result) != len(original):
        raise AssertionError("metadata mutation unexpectedly changed file length")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    report = {
        "tool": "tools/garmin-firmware/gcd_mutation_lab.py",
        "purpose": "offline metadata-only checksum experiment; never install",
        "source_filename": source.name,
        "source_size": len(original),
        "source_sha256": sha256(original),
        "output_filename": output.name,
        "output_size": len(result),
        "output_sha256": sha256(result),
        "mutation": {
            "record_id": "0x0005",
            "file_offset": f"0x{offset:x}",
            "old_byte_ascii": ".",
            "new_byte_ascii": "!",
            "firmware_stream_changed": False,
        },
        "all_documented_byte_checkpoints_valid": True,
        "limitations": [
            "This proves only the documented package-level additive checkpoint can be recomputed.",
            "It does not test a firmware-stream edit, SHA-1 validation, resident-loader authentication, or device acceptance.",
            "The output is prohibited research material and must never be copied to the watch; device acceptance is untested.",
        ],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="known official non-Music GCD")
    parser.add_argument("output", type=Path, help="new metadata-only laboratory copy")
    parser.add_argument("--report", required=True, type=Path, help="JSON report path")
    args = parser.parse_args()
    source_hash = sha256(args.source.read_bytes())
    if source_hash not in KNOWN_SOURCE_SHA256:
        parser.error("source SHA-256 is not an approved preserved non-Music image")
    report = mutate_copyright_metadata(args.source, args.output)
    report["known_source"] = KNOWN_SOURCE_SHA256[source_hash]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote metadata-only analysis copy: {args.output}")
    print(f"SHA-256: {report['output_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
