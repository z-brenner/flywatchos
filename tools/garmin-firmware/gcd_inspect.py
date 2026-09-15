#!/usr/bin/env python3
"""Read-only Garmin GCD inspector and stream extractor.

The parser implements the flat record stream documented by Herbert Oppmann:
``GARMIN`` + a little-endian format version, followed by records encoded as
``u16 record_id, u16 length, body``.  Inputs are never opened for writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple


class GcdFormatError(ValueError):
    pass


class GcdRecord(NamedTuple):
    offset: int
    record_id: int
    length: int
    body: bytes


class GcdFile(NamedTuple):
    format_version: int
    records: list[GcdRecord]
    raw: bytes


class FirmwareStream(NamedTuple):
    descriptor_index: int
    record_id: int
    declared_length: int
    xor_key: int
    erase_flag: int | None
    hwid: int | None
    software_version: int | None
    fields: list[dict[str, Any]]
    encoded: bytes
    decoded: bytes
    record_offsets: list[int]


FIELD_SIZES = {0x00: 1, 0x10: 2, 0x20: 4, 0x40: 31, 0x50: 0}
FIELD_NAMES = {
    (0x09, 0x10): "hwid",
    (0x0A, 0x00): "xor_key",
    (0x0A, 0x10): "record_id",
    (0x0B, 0x00): "erase_flag",
    (0x0C, 0x10): "minimum_version",
    (0x0D, 0x10): "software_version",
    (0x14, 0x10): "version_20",
    (0x15, 0x10): "remote_software_version",
    (0x15, 0x20): "firmware_length",
    (0x1A, 0x20): "destination_address",
    (0x03, 0x50): "end",
}
RECORD_NAMES = {
    0x0001: "checkpoint",
    0x0002: "filler",
    0x0003: "part_number",
    0x0005: "copyright",
    0x0006: "firmware_descriptor_type",
    0x0007: "firmware_descriptor",
    0x0008: "boot_bin",
    0x02BD: "fw_all_bin",
    0x0401: "external_data_bin",
    0x0505: "firmware_0505_bin",
    0xFFFF: "end",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_gcd(data: bytes) -> GcdFile:
    if len(data) < 8 or data[:6] != b"GARMIN":
        raise GcdFormatError("missing GARMIN signature")
    format_version = struct.unpack_from("<H", data, 6)[0]
    offset = 8
    records: list[GcdRecord] = []
    saw_end = False
    while offset < len(data):
        if len(data) - offset < 4:
            raise GcdFormatError(f"truncated record header at 0x{offset:x}")
        start = offset
        record_id, length = struct.unpack_from("<HH", data, offset)
        offset += 4
        end = offset + length
        if end > len(data):
            raise GcdFormatError(
                f"record 0x{record_id:04x} at 0x{start:x} extends past end of file"
            )
        records.append(GcdRecord(start, record_id, length, data[offset:end]))
        offset = end
        if record_id == 0xFFFF:
            if length != 0:
                raise GcdFormatError("end record has nonzero length")
            saw_end = True
            break
    if not saw_end:
        raise GcdFormatError("missing end record")
    if offset != len(data):
        raise GcdFormatError(f"{len(data) - offset} trailing bytes after end record")
    return GcdFile(format_version, records, data)


def _parse_field_types(body: bytes) -> list[tuple[int, int]]:
    if len(body) % 2:
        raise GcdFormatError("descriptor type record has odd length")
    result = []
    for offset in range(0, len(body), 2):
        field_id, field_type = body[offset], body[offset + 1]
        if field_type not in FIELD_SIZES:
            raise GcdFormatError(f"unknown descriptor field type 0x{field_type:02x}")
        result.append((field_id, field_type))
    return result


def _parse_descriptor(
    field_types: list[tuple[int, int]], body: bytes
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    offset = 0
    for field_id, field_type in field_types:
        size = FIELD_SIZES[field_type]
        if offset + size > len(body):
            raise GcdFormatError("descriptor value is shorter than its type record")
        raw = body[offset : offset + size]
        offset += size
        value: int | str
        if size <= 4:
            value = int.from_bytes(raw, "little")
        else:
            value = raw.hex()
        fields.append(
            {
                "field_id": field_id,
                "field_type": field_type,
                "name": FIELD_NAMES.get((field_id, field_type), "unknown"),
                "value": value,
            }
        )
    if offset != len(body):
        raise GcdFormatError(f"descriptor has {len(body) - offset} unexplained bytes")
    return fields


def _field(fields: list[dict[str, Any]], name: str) -> int | None:
    for field in fields:
        if field["name"] == name:
            value = field["value"]
            return value if isinstance(value, int) else None
    return None


def collect_streams(gcd: GcdFile) -> list[FirmwareStream]:
    streams: list[FirmwareStream] = []
    field_types: list[tuple[int, int]] | None = None
    index = 0
    while index < len(gcd.records):
        record = gcd.records[index]
        if record.record_id == 0x0006:
            field_types = _parse_field_types(record.body)
        elif record.record_id == 0x0007:
            if field_types is None:
                raise GcdFormatError("descriptor appears before descriptor type")
            fields = _parse_descriptor(field_types, record.body)
            record_id = _field(fields, "record_id")
            declared_length = _field(fields, "firmware_length")
            if record_id is None or declared_length is None:
                raise GcdFormatError("descriptor lacks record ID or firmware length")
            chunks: list[bytes] = []
            offsets: list[int] = []
            cursor = index + 1
            collected = 0
            while cursor < len(gcd.records) and collected < declared_length:
                candidate = gcd.records[cursor]
                if candidate.record_id == 0x0001:
                    cursor += 1
                    continue
                if candidate.record_id != record_id:
                    break
                chunks.append(candidate.body)
                offsets.append(candidate.offset)
                collected += candidate.length
                cursor += 1
            if collected != declared_length:
                raise GcdFormatError(
                    f"stream 0x{record_id:04x} declares {declared_length} bytes, found {collected}"
                )
            encoded = b"".join(chunks)
            xor_key = _field(fields, "xor_key") or 0
            decoded = bytes(value ^ xor_key for value in encoded)
            streams.append(
                FirmwareStream(
                    descriptor_index=len(streams),
                    record_id=record_id,
                    declared_length=declared_length,
                    xor_key=xor_key,
                    erase_flag=_field(fields, "erase_flag"),
                    hwid=_field(fields, "hwid"),
                    software_version=_field(fields, "software_version"),
                    fields=fields,
                    encoded=encoded,
                    decoded=decoded,
                    record_offsets=offsets,
                )
            )
        index += 1
    return streams


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _vector_candidate(data: bytes) -> dict[str, Any] | None:
    if len(data) < 8:
        return None
    initial_sp, reset_handler = struct.unpack_from("<II", data)
    if 0x20000000 <= initial_sp < 0x21000000 and reset_handler & 1:
        return {
            "initial_sp": f"0x{initial_sp:08x}",
            "reset_handler": f"0x{reset_handler:08x}",
            "architecture_inference": "Arm Cortex-M little-endian vector table candidate",
        }
    return None


def reset_handler_location(data: bytes, load_address: int) -> int | None:
    """Map a Cortex-M reset vector to an image offset for a proposed base."""
    candidate = _vector_candidate(data)
    if candidate is None:
        return None
    reset_handler = int(candidate["reset_handler"], 16) & ~1
    offset = reset_handler - load_address
    return offset if 0 <= offset < len(data) else None


def _checkpoint_results(gcd: GcdFile) -> list[dict[str, Any]]:
    result = []
    for record in gcd.records:
        if record.record_id == 0x0001 and record.length == 1:
            end = record.offset + 5
            modulo = sum(gcd.raw[:end]) & 0xFF
            result.append(
                {
                    "offset": f"0x{record.offset:x}",
                    "value": record.body[0],
                    "prefix_sum_mod_256": modulo,
                    "valid": modulo == 0,
                }
            )
    return result


def analyze_file(source: Path, output_dir: Path, extract: bool = False) -> dict[str, Any]:
    source = source.resolve()
    output_dir = output_dir.resolve()
    data = source.read_bytes()
    gcd = parse_gcd(data)
    streams = collect_streams(gcd)
    output_dir.mkdir(parents=True, exist_ok=True)
    stream_reports = []
    for stream in streams:
        label = RECORD_NAMES.get(stream.record_id, f"record_{stream.record_id:04x}")
        filename = f"stream_{stream.descriptor_index:02d}_{label}.bin"
        vector = _vector_candidate(stream.decoded)
        reset_offset = reset_handler_location(stream.decoded, load_address=0x3000)
        report = {
            "index": stream.descriptor_index,
            "record_id": f"0x{stream.record_id:04x}",
            "record_name": label,
            "declared_length": stream.declared_length,
            "xor_key": stream.xor_key,
            "erase_flag": stream.erase_flag,
            "hwid": stream.hwid,
            "software_version_raw": stream.software_version,
            "software_version": (
                f"{stream.software_version // 100}.{stream.software_version % 100:02d}"
                if stream.software_version is not None
                else None
            ),
            "source_record_offsets": [f"0x{item:x}" for item in stream.record_offsets],
            "sha256": sha256_bytes(stream.decoded),
            "shannon_entropy_bits_per_byte": round(_entropy(stream.decoded), 6),
            "vector_table_candidate": vector,
            "reset_file_offset_assuming_load_address_0x3000": (
                f"0x{reset_offset:x}" if reset_offset is not None else None
            ),
            "descriptor_fields": stream.fields,
            "extracted_filename": filename if extract else None,
        }
        if extract:
            (output_dir / filename).write_bytes(stream.decoded)
        stream_reports.append(report)
    report = {
        "tool": "tools/garmin-firmware/gcd_inspect.py",
        "input_filename": source.name,
        "input_size": len(data),
        "input_sha256": sha256_bytes(data),
        "signature": gcd.raw[:6].decode("ascii"),
        "format_version_raw": gcd.format_version,
        "format_version": f"{gcd.format_version // 100}.{gcd.format_version % 100:02d}",
        "record_count": len(gcd.records),
        "records": [
            {
                "offset": f"0x{record.offset:x}",
                "record_id": f"0x{record.record_id:04x}",
                "record_name": RECORD_NAMES.get(record.record_id, "firmware_data_or_unknown"),
                "length": record.length,
            }
            for record in gcd.records
        ],
        "checkpoints": _checkpoint_results(gcd),
        "all_byte_checkpoints_valid": all(
            item["valid"] for item in _checkpoint_results(gcd)
        ),
        "streams": stream_reports,
    }
    (output_dir / "analysis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source .GCD file (read-only)")
    parser.add_argument("output_dir", type=Path, help="directory for generated analysis")
    parser.add_argument("--extract", action="store_true", help="extract decoded streams")
    args = parser.parse_args()
    report = analyze_file(args.input, args.output_dir, extract=args.extract)
    print(
        f"{report['input_filename']}: {report['record_count']} records, "
        f"{len(report['streams'])} firmware streams"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
