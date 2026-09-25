import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))

import k28_reset_contract as contract  # noqa: E402


class ResetRootTests(unittest.TestCase):
    def test_pinned_reset_root(self):
        root = contract.load_reset_root(ROOT)
        self.assertEqual(contract.PINNED_IMAGE_SHA256, root.image_sha256)
        self.assertEqual(0x31F1, root.reset_vector)
        self.assertEqual(0x31F0, root.reset_handler)
        self.assertEqual(0x19341, root.stage2_pointer)
        self.assertEqual(0x19340, root.stage2_entry)
        self.assertEqual(
            "72b64ff0000080f31488bff36f8fdff808d002480047",
            root.reset_bytes.hex(),
        )

    def test_same_size_image_mutation_is_rejected_before_decode(self):
        damaged = bytearray(contract.pinned_image_path(ROOT).read_bytes())
        damaged[0x1F0] ^= 1
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            contract.decode_pinned_image(bytes(damaged))

    def test_stage2_pointer_must_be_thumb_and_inside_application(self):
        image = bytearray(contract.pinned_image_path(ROOT).read_bytes())
        for pointer in (0x19340, 0xFFFFFFFF, 0x00200001):
            with self.subTest(pointer=pointer):
                changed = bytearray(image)
                changed[0x20C:0x210] = pointer.to_bytes(4, "little")
                with self.assertRaises(ValueError):
                    contract.decode_trusted_layout(bytes(changed))

    def test_root_cli_writes_a_fresh_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "root.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(TOOLS / "k28_reset_contract.py"),
                    "root",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(contract.PINNED_IMAGE_SHA256, report["source_sha256"])
            self.assertEqual("0x000031f0", report["reset_handler"])
            self.assertEqual("0x00019340", report["stage2_entry"])
            self.assertNotIn("mmio", json.dumps(report).lower())

    def test_root_cli_refuses_to_overwrite_an_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "root.json"
            output.write_bytes(b"preserve-existing-evidence")
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(TOOLS / "k28_reset_contract.py"),
                    "root",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertEqual(b"preserve-existing-evidence", output.read_bytes())


if __name__ == "__main__":
    unittest.main()
