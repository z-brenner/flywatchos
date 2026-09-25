import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
RUNNER = TOOLS / "run_k28_reset_contract.ps1"
sys.path.insert(0, str(TOOLS))

import k28_reset_contract as contract  # noqa: E402


def fixture_root():
    return contract.ResetRoot(
        image_sha256=contract.PINNED_IMAGE_SHA256,
        reset_vector=0x31F1,
        reset_handler=0x31F0,
        reset_bytes=contract.EXPECTED_RESET_BYTES,
        stage2_pointer=0x19341,
        stage2_entry=0x19340,
    )


def fixture_inventory():
    return {
        "schema": "flyos.fr245.k28-reset-inventory.v1",
        "program": {
            "name": "stream_01_fw_all_bin.bin",
            "sha256": contract.PINNED_IMAGE_SHA256,
            "base": "0x00003000",
            "end_exclusive": "0x00200000",
        },
        "roots": ["0x000031f0", "0x00019340"],
        "max_depth": 3,
        "analysis_complete": True,
        "cancelled": False,
        "unresolved_seed_count": 0,
        "unresolved_function_count": 0,
        "functions": [
            {
                "entry": "0x00019340",
                "end_inclusive": "0x0001934f",
                "sha256": "11" * 32,
                "depth": 0,
                "direct_calls": [],
                "indirect_control_flow": [],
                "literal_references": [],
                "mmio_references": [],
                "backward_branches": [],
            }
        ],
        "computed_mmio": [],
        "unknown_mmio_widths": [],
        "unknown_mmio_values": [],
        "unbounded_polls": [],
        "unknown_memory_ranges": [],
    }


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


class GhidraInventoryTests(unittest.TestCase):
    def test_runner_defers_script_relative_defaults_until_body(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("[string]$GhidraRoot = ''", source)
        self.assertIn(
            "if ([string]::IsNullOrWhiteSpace($GhidraRoot))", source
        )
        self.assertIn("New-Item -ItemType Directory -Path $project", source)

    def test_inventory_requires_pinned_program_and_stage2(self):
        report = fixture_inventory()
        contract.validate_ghidra_inventory(report, fixture_root())

        wrong_hash = copy.deepcopy(report)
        wrong_hash["program"]["sha256"] = "00" * 32
        with self.assertRaisesRegex(ValueError, "program SHA-256"):
            contract.validate_ghidra_inventory(wrong_hash, fixture_root())

        wrong_roots = copy.deepcopy(report)
        wrong_roots["roots"] = ["0x000031f0"]
        with self.assertRaisesRegex(ValueError, "inventory roots"):
            contract.validate_ghidra_inventory(wrong_roots, fixture_root())

    def test_inventory_requires_every_output_and_rejects_postscript_error(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / "ghidra-inventory.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing evidence output"):
                contract.load_ghidra_run(run, fixture_root())

        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            for name in contract.REQUIRED_GHIDRA_OUTPUTS:
                (run / name).write_text("", encoding="utf-8")
            (run / "ghidra-inventory.json").write_text(
                json.dumps(fixture_inventory()), encoding="utf-8"
            )
            (run / "script.log").write_text(
                "SCRIPT ERROR: post-script failed", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "post-script error"):
                contract.load_ghidra_run(run, fixture_root())

    def test_launcher_refuses_any_existing_run_directory(self):
        self.assertTrue(RUNNER.is_file(), "reset-contract runner must exist")
        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / "run"
            occupied.mkdir()
            sentinel = occupied / "sentinel"
            sentinel.write_bytes(b"preserve")
            result = subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(RUNNER),
                    "-OutputRoot",
                    str(occupied),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(b"preserve", sentinel.read_bytes())


if __name__ == "__main__":
    unittest.main()
