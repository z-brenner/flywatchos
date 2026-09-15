"""Run the compiled N64 C renderer and hash its golden PPM outputs."""
import argparse
import hashlib
import subprocess
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exporter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(args.exporter), "--output", str(args.output)], check=True)
    outputs = sorted(args.output.glob("*.ppm"))
    (args.output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in outputs),
        encoding="ascii")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
