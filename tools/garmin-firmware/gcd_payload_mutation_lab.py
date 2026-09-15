#!/usr/bin/env python3
"""Create one fixed offline main-payload mutation for checksum research only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import gcd_inspect  # noqa: E402
from gcd_mutation_lab import recompute_checkpoints  # noqa: E402


SOURCE_SHA256 = "8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc"
EXPECTED_STREAM_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
TARGET_TEXT = b"13.70"
TARGET_OFFSET = 3608374


def replace_decoded_stream_byte(data: bytes, stream: Any, decoded_offset: int,
                                old: int, new: int, inspect: Any = gcd_inspect) -> tuple[bytes, int]:
    if stream.xor_key != 0:
        raise ValueError("laboratory byte mapping supports only un-XORed streams")
    if not 0 <= decoded_offset < stream.declared_length:
        raise ValueError("decoded offset outside stream")
    cursor = 0
    for record_offset in stream.record_offsets:
        record = next(r for r in inspect.parse_gcd(data).records if r.offset == record_offset)
        if decoded_offset < cursor + record.length:
            raw_offset = record.offset + 4 + decoded_offset - cursor
            mutable = bytearray(data)
            if mutable[raw_offset] != old:
                raise ValueError("expected original byte is absent")
            mutable[raw_offset] = new
            return recompute_checkpoints(bytes(mutable), inspect), raw_offset
        cursor += record.length
    raise AssertionError("stream record offsets do not cover declared length")


def repair_stream_additive_checksum(data: bytes, stream: Any,
                                    inspect: Any = gcd_inspect) -> tuple[bytes, int, int, int]:
    """Adjust the final decoded byte so the full-stream byte sum is zero."""
    remainder = sum(stream.decoded) & 0xFF
    old = stream.decoded[-1]
    new = (old - remainder) & 0xFF
    result, raw_offset = replace_decoded_stream_byte(
        data, stream, stream.declared_length - 1, old, new, inspect
    )
    repaired = next(
        item for item in inspect.collect_streams(inspect.parse_gcd(result))
        if item.descriptor_index == stream.descriptor_index
    )
    if sum(repaired.decoded) & 0xFF:
        raise ValueError("inner full-image additive checksum did not validate")
    return result, raw_offset, old, new


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("output must be a separate analysis file")
    source = args.source.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        parser.error("source is not the pinned official non-Music 13.70 package")
    gcd = gcd_inspect.parse_gcd(source)
    stream = next(x for x in gcd_inspect.collect_streams(gcd) if x.record_id == 0x02BD)
    if hashlib.sha256(stream.decoded).hexdigest() != EXPECTED_STREAM_SHA256:
        parser.error("main stream does not match the pinned official payload")
    if stream.decoded[TARGET_OFFSET:TARGET_OFFSET + len(TARGET_TEXT)] != TARGET_TEXT:
        parser.error("pinned printable target is absent")
    result, raw_offset = replace_decoded_stream_byte(source, stream, TARGET_OFFSET + 4, ord("0"), ord("1"))
    mutated_stream = next(x for x in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(result)) if x.record_id == 0x02BD)
    result, checksum_raw_offset, old_checksum, new_checksum = repair_stream_additive_checksum(result, mutated_stream)
    mutated_stream = next(x for x in gcd_inspect.collect_streams(gcd_inspect.parse_gcd(result)) if x.record_id == 0x02BD)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    report = {"purpose":"offline main-payload checksum experiment; prohibited from watch transfer", "source_sha256":SOURCE_SHA256,
              "output_sha256":hashlib.sha256(result).hexdigest(), "mutation":{"decoded_stream_offset":f"0x{TARGET_OFFSET+4:x}","raw_file_offset":f"0x{raw_offset:x}","old_text":"13.70","new_text":"13.71"},
              "inner_checksum_repair":{"decoded_stream_offset":f"0x{stream.declared_length-1:x}","raw_file_offset":f"0x{checksum_raw_offset:x}","old_byte":old_checksum,"new_byte":new_checksum,"decoded_stream_sum_mod_256":sum(mutated_stream.decoded)&0xff},
              "original_main_stream_sha256":EXPECTED_STREAM_SHA256,"mutated_main_stream_sha256":hashlib.sha256(mutated_stream.decoded).hexdigest(),
              "all_documented_byte_checkpoints_valid":True,"limitations":["No device acceptance was tested.","The SHA-1 path applies to GDELTA01 delta images; this experiment is a full image.","This does not establish resident-loader authentication or bypass any signature.","The result must never be copied to the watch."]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(report["output_sha256"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
