#!/usr/bin/env python3
"""Compile the C renderer, then encode its exact 240x240 bytes as a grayscale PNG.

The default fixture deliberately exercises all four glyph levels. No display
logic is implemented here. --raw may instead consume a C-produced framebuffer.
"""

import argparse
import binascii
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib


HARNESS = r'''
#include "display/brain_ascii.h"
#include <stdio.h>
int main(int argc, char **argv) {
    FlyBrain32 brain = {0};
    uint8_t framebuffer[57600];
    const int16_t levels[4] = {64, 192, 384, 768};
    if (argc != 2) return 2;
    brain.epoch = 0x552u;
    brain.state = FLY_BRAIN_STATE_AROUSAL;
    for (unsigned i = 0; i < 32; ++i) {
        int16_t activation = levels[(i * 13u + (i >> 3)) & 3u];
        brain.activation[i] = (i & 1u) ? (int16_t)-activation : activation;
    }
    brain.activation[30] = 768; /* Arousal is the dominant action channel. */
    fly_brain_ascii_render(framebuffer, &brain, 0x00002a91u, 2u);
    FILE *out = fopen(argv[1], "wb");
    if (!out) return 3;
    int ok = fwrite(framebuffer, 1, sizeof(framebuffer), out) == sizeof(framebuffer);
    if (fclose(out) != 0) return 4;
    return ok ? 0 : 5;
}
'''


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=root.parent / "artifacts/previews/flyos-ascii-brain.png")
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"),
                        help="C11 compiler executable (GCC/Clang CLI)")
    parser.add_argument("--raw", type=Path, help="Read a C-rendered 57,600-byte frame")
    args = parser.parse_args()
    if args.raw:
        pixels = args.raw.read_bytes()
    else:
        compiler = shutil.which(args.cc)
        if compiler is None:
            parser.error(f"C compiler not found: {args.cc}; set --cc or use --raw")
        with tempfile.TemporaryDirectory(prefix="flyos-brain-preview-") as directory:
            temporary = Path(directory)
            source = temporary / "preview.c"
            source.write_text(HARNESS, encoding="utf-8")
            executable = temporary / ("preview.exe" if os.name == "nt" else "preview")
            raw = temporary / "framebuffer.raw"
            command = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                       "-I", str(root), str(source), str(root / "display/brain_ascii.c"),
                       str(root / "fly/brain32.c"), "-o", str(executable)]
            print("Compile:", subprocess.list2cmdline(command))
            subprocess.run(command, check=True)
            subprocess.run([str(executable), str(raw)], check=True)
            pixels = raw.read_bytes()
    if len(pixels) != 57600 or any(value not in (0, 255) for value in pixels):
        parser.error("C framebuffer must contain exactly 57,600 bytes, each 0x00 or 0xff")
    # PNG filter 0 preserves every source byte; color type 0 is 8-bit grayscale.
    scanlines = b"".join(b"\0" + pixels[y * 240:(y + 1) * 240] for y in range(240))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", 240, 240, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(scanlines, level=9))
           + chunk(b"IEND", b""))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(png)
    print(f"Wrote {args.output} (240x240, exact binary C framebuffer)")


if __name__ == "__main__":
    main()
