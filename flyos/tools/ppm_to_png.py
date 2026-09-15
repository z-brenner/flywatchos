#!/usr/bin/env python3
"""Convert the FlyOS binary PPM preview to PNG without third-party packages."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def convert(source: Path, destination: Path) -> None:
    with source.open("rb") as stream:
        if stream.readline().strip() != b"P6":
            raise ValueError("input is not a binary P6 PPM")
        dimensions = stream.readline().split()
        if len(dimensions) != 2:
            raise ValueError("unsupported PPM dimensions line")
        width, height = map(int, dimensions)
        if stream.readline().strip() != b"255":
            raise ValueError("unsupported PPM sample depth")
        pixels = stream.read()

    expected = width * height * 3
    if len(pixels) != expected:
        raise ValueError(f"expected {expected} pixel bytes, found {len(pixels)}")

    rows = b"".join(
        b"\x00" + pixels[offset : offset + width * 3]
        for offset in range(0, len(pixels), width * 3)
    )
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(rows, level=9))
    png += _chunk(b"IEND", b"")
    destination.write_bytes(png)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
