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
RECEIPT = ROOT / "flyos" / "target" / "k28" / "contracts" / "fr245_1370_reset_root.json"
RESET_DOC = ROOT / "docs" / "standalone-reset-contract.md"
K28_README = ROOT / "flyos" / "target" / "k28" / "README.md"
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


class ContractGateTests(unittest.TestCase):
    def test_complete_fixture_passes_every_gate(self):
        report = contract.build_contract(fixture_root(), fixture_inventory())
        self.assertTrue(all(report["gates"].values()))
        self.assertTrue(report["go"])

    def test_unresolved_control_flow_fails_closed(self):
        inventory = fixture_inventory()
        inventory["functions"][0]["indirect_control_flow"] = ["0x0001934c"]
        report = contract.build_contract(fixture_root(), inventory)
        self.assertFalse(report["gates"]["control_flow_closed"])
        self.assertFalse(report["go"])

    def test_computed_mmio_and_unbounded_polling_fail_independently(self):
        for field, value, gate in (
            ("computed_mmio", ["0x40000000+r3"], "mmio_addresses_closed"),
            ("unbounded_polls", ["0x000191f0"], "polls_bounded"),
        ):
            with self.subTest(field=field):
                inventory = fixture_inventory()
                inventory[field] = value
                report = contract.build_contract(fixture_root(), inventory)
                self.assertFalse(report["gates"][gate])
                self.assertFalse(report["go"])
                other_gates = {
                    name: result
                    for name, result in report["gates"].items()
                    if name != gate
                }
                self.assertTrue(all(other_gates.values()))

    def test_incomplete_analysis_and_unknown_mmio_facts_fail_independently(self):
        for field, value, gate in (
            ("analysis_complete", False, "analysis_complete"),
            ("unknown_mmio_widths", ["unknown"], "mmio_widths_closed"),
            ("unknown_mmio_values", ["unknown"], "mmio_values_closed"),
            ("unknown_memory_ranges", ["unknown"], "memory_ranges_closed"),
        ):
            with self.subTest(field=field):
                inventory = fixture_inventory()
                inventory[field] = value
                report = contract.build_contract(fixture_root(), inventory)
                self.assertFalse(report["gates"][gate])
                self.assertFalse(report["go"])

    def test_public_receipt_contains_no_code_or_private_paths(self):
        complete = contract.build_contract(fixture_root(), fixture_inventory())
        complete["private_evidence_path"] = (
            r"C:\Users\zgbre\artifacts\firmware\private\decompilation.txt"
        )
        complete["functions"][0]["instruction_text"] = "str r0, [r1]"
        receipt = contract.sanitize_contract(complete)
        encoded = json.dumps(receipt).lower()
        for forbidden in (
            "decompilation",
            "instruction_text",
            "c:\\\\users",
            "artifacts/firmware",
            "stream_01_fw_all_bin.bin",
            "str r0",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual("11" * 32, receipt["functions"][0]["sha256"])


class ContractDocumentationTests(unittest.TestCase):
    def test_public_docs_match_committed_receipt(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        document = RESET_DOC.read_text(encoding="utf-8")
        self.assertIn(receipt["source_sha256"], document)
        self.assertIn(f"`go={str(receipt['go']).lower()}`", document)
        for name, value in receipt["gates"].items():
            self.assertIn(
                f"| `{name}` | `{str(value).lower()}` |", document
            )

    def test_public_docs_and_receipt_have_no_private_evidence_paths(self):
        combined = (
            RESET_DOC.read_text(encoding="utf-8")
            + RECEIPT.read_text(encoding="utf-8")
        ).lower()
        self.assertNotIn("c:\\\\users", combined)
        self.assertNotIn("artifacts/firmware", combined)
        self.assertNotIn("decompilation.txt", combined)

    def test_k28_readme_links_the_reset_contract_and_keeps_install_blocked(self):
        readme = K28_README.read_text(encoding="utf-8")
        self.assertIn("../../../docs/standalone-reset-contract.md", readme)
        self.assertIn("`go=false`", readme)
        self.assertIn("not safe to install", readme)


if __name__ == "__main__":
    unittest.main()
