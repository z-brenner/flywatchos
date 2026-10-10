#!/usr/bin/env python3
"""Build a portable, self-contained replay lab from the real C trace exporter.

The output is offline HTML plus its source trace and hashes. No network access,
firmware inputs, device communication, or third-party Python packages are used.
Existing output directories are rejected to preserve previous captures.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

PALETTE = ((8, 10, 9), (54, 69, 59), (218, 231, 211),
           (135, 184, 122), (184, 122, 135), (242, 210, 94))


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def frame_png(runs: list[list[int]]) -> bytes:
    pixels = bytearray()
    count = 0
    for role, length in runs:
        if type(role) is not int or type(length) is not int or not 0 <= role < len(PALETTE) or length <= 0:
            raise ValueError('invalid semantic framebuffer run')
        count += length
        if count > 240 * 240:
            raise ValueError('framebuffer exceeds 240 x 240')
        pixels.extend(bytes(PALETTE[role]) * length)
    if count != 240 * 240:
        raise ValueError('incomplete framebuffer')
    rows = b''.join(b'\0' + pixels[offset:offset + 720] for offset in range(0, len(pixels), 720))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 240, 240, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def build(exporter: Path, output: Path) -> None:
    # Reserve before invoking the exporter; never overwrite an existing capture.
    output.mkdir(parents=True, exist_ok=False)
    raw = subprocess.run([str(exporter.resolve())], check=True, capture_output=True).stdout
    data = json.loads(raw)
    if data.get('schema') != 1 or data.get('scope') != 'host-only' or data.get('hardware_verified') is not False:
        raise ValueError('unsupported or misleading trace contract')
    (output / 'trace.json').write_bytes(raw)
    for scenario in data['scenarios']:
        for frame in scenario['frames']:
            frame['image'] = 'data:image/png;base64,' + base64.b64encode(frame_png(frame.pop('pixels'))).decode('ascii')
    payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = Path(__file__).with_name('interaction_lab.html').read_text(encoding='utf-8')
    if template.count('/*__LAB_DATA__*/') != 1:
        raise ValueError('lab template must contain one data marker')
    (output / 'index.html').write_text(template.replace('/*__LAB_DATA__*/', payload), encoding='utf-8')
    files = [output / 'index.html', output / 'trace.json']
    (output / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in files), encoding='ascii')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exporter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new directory; existing captures are never replaced')
    args = parser.parse_args()
    try:
        build(args.exporter, args.output)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'lab build failed: {error}\n')
    print(f'Open {args.output / "index.html"} in a browser. Offline host model only.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
