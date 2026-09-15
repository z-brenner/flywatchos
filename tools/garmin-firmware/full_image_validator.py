#!/usr/bin/env python3
"""Reproduce the confirmed application-side checks for a full GCD image.

This is an offline validator.  It does not model the omitted resident loader and
must not be interpreted as evidence that a package will be accepted by a watch.
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


DELTA_MAGIC = b"GDELTA01"
MAIN_RECORD_ID = 0x02BD


def validate_bytes(data: bytes, filename: str = "<memory>") -> dict[str, Any]:
    gcd = gcd_inspect.parse_gcd(data)
    checkpoints = gcd_inspect._checkpoint_results(gcd)
    streams = [
        stream
        for stream in gcd_inspect.collect_streams(gcd)
        if stream.record_id == MAIN_RECORD_ID
    ]
    if len(streams) != 1:
        raise gcd_inspect.GcdFormatError(
            f"expected one main 0x{MAIN_RECORD_ID:04x} stream, found {len(streams)}"
        )
    stream = streams[0]
    is_delta = stream.decoded.startswith(DELTA_MAGIC)
    outer_valid = bool(checkpoints) and all(item["valid"] for item in checkpoints)
    inner_sum = sum(stream.decoded) & 0xFF
    full_image_branch_valid = not is_delta and inner_sum == 0
    return {
        "tool": "tools/garmin-firmware/full_image_validator.py",
        "scope": "confirmed GarminOS application-side full-image checks only",
        "input_filename": filename,
        "input_size": len(data),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "outer_gcd": {
            "checkpoint_count": len(checkpoints),
            "all_prefix_sums_zero_mod_256": outer_valid,
        },
        "main_stream": {
            "record_id": "0x02bd",
            "decoded_length": len(stream.decoded),
            "decoded_sha256": hashlib.sha256(stream.decoded).hexdigest(),
            "prefix": stream.decoded[:8].hex(),
            "gdelta01": is_delta,
            "byte_sum_mod_256": inner_sum,
        },
        "confirmed_full_image_checks_pass": outer_valid and full_image_branch_valid,
        "limitations": [
            "GDELTA01 packages take a separate delta path that this tool does not validate.",
            "Resident-loader authentication, version policy, installation, rollback, and recovery are not modeled.",
            "A passing report is not evidence of device acceptance or arbitrary code execution.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    data = args.input.read_bytes()
    report = validate_bytes(data, args.input.name)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["confirmed_full_image_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
