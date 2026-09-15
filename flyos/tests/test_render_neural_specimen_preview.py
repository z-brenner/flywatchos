import hashlib
import pathlib
import subprocess
import sys
import tempfile


EXPECTED = {
    "quiet.ppm",
    "light.ppm",
    "start.ppm",
    "back.ppm",
    "down.ppm",
    "up.ppm",
    "sensors-valid.ppm",
    "sensors-invalid.ppm",
    "charging.ppm",
    "usb-pass-through.ppm",
    "update-pass-through.ppm",
}


def main() -> int:
    script = pathlib.Path(sys.argv[1])
    exporter = pathlib.Path(sys.argv[2])
    with tempfile.TemporaryDirectory() as temporary:
        output = pathlib.Path(temporary)
        subprocess.run([sys.executable, str(script), "--exporter", str(exporter),
                        "--output", str(output)], check=True)
        actual = {path.name for path in output.glob("*.ppm")}
        assert actual == EXPECTED, actual
        for path in output.glob("*.ppm"):
            assert path.read_bytes().startswith(b"P6\n240 240\n255\n"), path
        manifest = output / "SHA256SUMS"
        assert {path.name for path in output.iterdir()} == EXPECTED | {"SHA256SUMS"}
        lines = manifest.read_text(encoding="ascii").splitlines()
        assert len(lines) == len(EXPECTED), lines
        for line in lines:
            digest, filename = line.split("  ", 1)
            assert filename in EXPECTED, filename
            assert digest == hashlib.sha256((output / filename).read_bytes()).hexdigest()
        assert len({line.split("  ", 1)[0] for line in lines}) == len(EXPECTED)
    print("neural specimen preview tests: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
