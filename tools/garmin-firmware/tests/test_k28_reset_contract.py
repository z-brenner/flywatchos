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
CONTROL_FLOW_RECEIPT = ROOT / "flyos" / "target" / "k28" / "contracts" / "fr245_1370_control_flow.json"
MMIO_WIDTH_RECEIPT = ROOT / "flyos" / "target" / "k28" / "contracts" / "fr245_1370_mmio_widths.json"
RESET_DOC = ROOT / "docs" / "standalone-reset-contract.md"
K28_README = ROOT / "flyos" / "target" / "k28" / "README.md"
ACTUAL_RUN = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "standalone-reset-contract-2026-09-24-b"
)
sys.path.insert(0, str(TOOLS))

import k28_reset_contract as contract  # noqa: E402
import k28_control_flow as flow  # noqa: E402
import k28_mmio_widths as widths  # noqa: E402


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
    def function(entry, depth):
        return {
            "entry": entry,
            "end_inclusive": entry,
            "sha256": "11" * 32,
            "depth": depth,
            "direct_calls": [],
            "indirect_control_flow": [],
            "literal_references": [],
            "mmio_references": [],
            "backward_branches": [],
        }

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
            function("0x000031f0", 0),
            function("0x00019340", 0),
        ],
        "computed_mmio": [],
        "unknown_mmio_widths": [],
        "unknown_mmio_values": [],
        "unbounded_polls": [],
        "unknown_memory_ranges": [],
    }


def fixture_indirect_inventory():
    inventory = fixture_inventory()
    by_entry = {item["entry"]: item for item in inventory["functions"]}
    for entry, (function_sha256, sites) in flow.EXPECTED_OWNERS.items():
        function = by_entry.get(entry)
        if function is None:
            function = {
                "entry": entry,
                "end_inclusive": entry,
                "sha256": function_sha256,
                "depth": 2,
                "direct_calls": [],
                "indirect_control_flow": list(sites),
                "literal_references": [],
                "mmio_references": [],
                "backward_branches": [],
            }
            inventory["functions"].append(function)
        else:
            function["sha256"] = function_sha256
            function["indirect_control_flow"] = list(sites)
        if entry == "0x0001aa34":
            function["direct_calls"] = [
                "0x0001a810",
                "0x0001a868",
                "0x0001a8dc",
                "0x0001a940",
            ]
    inventory["functions"].sort(key=lambda item: item["entry"])
    return inventory


def actual_inventory():
    inventory_bytes = (ACTUAL_RUN / "ghidra-inventory.json").read_bytes()
    return json.loads(inventory_bytes), inventory_bytes


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

    def test_contract_cli_consumes_a_hash_bound_control_flow_proof(self):
        inventory, inventory_bytes = actual_inventory()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            image = contract.pinned_image_path(ROOT).read_bytes()
            proof = flow.build_control_flow_proof(
                image, inventory, inventory_bytes
            )
            proof_path = base / "proof.json"
            proof_path.write_text(
                json.dumps(proof, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            output = base / "contract.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(TOOLS / "k28_reset_contract.py"),
                    "contract",
                    "--run",
                    str(ACTUAL_RUN),
                    "--control-flow-proof",
                    str(proof_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(receipt["gates"]["control_flow_closed"])
            self.assertEqual(
                flow.proof_sha256(proof), receipt["control_flow_proof_sha256"]
            )
            self.assertFalse(receipt["go"])

    def test_contract_cli_consumes_both_hash_bound_proofs(self):
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        control_proof = flow.build_control_flow_proof(
            image, inventory, inventory_bytes
        )
        width_proof = widths.build_mmio_width_proof(
            image, inventory, inventory_bytes
        )
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            control_path = base / "control.json"
            width_path = base / "widths.json"
            output = base / "contract.json"
            control_path.write_text(
                json.dumps(control_proof, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            width_path.write_text(
                json.dumps(width_proof, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(TOOLS / "k28_reset_contract.py"),
                    "contract",
                    "--run",
                    str(ACTUAL_RUN),
                    "--control-flow-proof",
                    str(control_path),
                    "--mmio-width-proof",
                    str(width_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(receipt["gates"]["control_flow_closed"])
            self.assertTrue(receipt["gates"]["mmio_widths_closed"])
            self.assertEqual(
                widths.proof_sha256(width_proof),
                receipt["mmio_width_proof_sha256"],
            )
            self.assertFalse(receipt["go"])


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

    def test_exact_control_flow_proof_closes_only_its_gate(self):
        root = contract.load_reset_root(ROOT)
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        proof = flow.build_control_flow_proof(image, inventory, inventory_bytes)
        report = contract.build_contract(
            root,
            inventory,
            control_flow_proof=proof,
            inventory_bytes=inventory_bytes,
            image=image,
        )
        self.assertTrue(report["gates"]["control_flow_closed"])
        for gate in (
            "mmio_addresses_closed",
            "mmio_widths_closed",
            "mmio_values_closed",
            "polls_bounded",
            "memory_ranges_closed",
        ):
            self.assertFalse(report["gates"][gate])
        self.assertEqual(flow.proof_sha256(proof), report["control_flow_proof_sha256"])
        self.assertFalse(report["go"])

    def test_exact_width_proof_closes_only_width_gate(self):
        root = contract.load_reset_root(ROOT)
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        control_proof = flow.build_control_flow_proof(
            image, inventory, inventory_bytes
        )
        width_proof = widths.build_mmio_width_proof(
            image, inventory, inventory_bytes
        )
        report = contract.build_contract(
            root,
            inventory,
            control_flow_proof=control_proof,
            mmio_width_proof=width_proof,
            inventory_bytes=inventory_bytes,
            image=image,
        )
        self.assertTrue(report["gates"]["control_flow_closed"])
        self.assertTrue(report["gates"]["mmio_widths_closed"])
        for gate in (
            "mmio_addresses_closed",
            "mmio_values_closed",
            "polls_bounded",
            "memory_ranges_closed",
        ):
            self.assertFalse(report["gates"][gate])
        self.assertEqual(
            widths.proof_sha256(width_proof),
            report["mmio_width_proof_sha256"],
        )
        self.assertFalse(report["go"])

    def test_control_flow_proof_requires_matching_image_and_inventory(self):
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        proof = flow.build_control_flow_proof(image, inventory, inventory_bytes)
        for label, kwargs in (
            ("missing image", {"inventory_bytes": inventory_bytes}),
            ("missing inventory bytes", {"image": image}),
            (
                "wrong inventory bytes",
                {"image": image, "inventory_bytes": inventory_bytes + b"\n"},
            ),
        ):
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    contract.build_contract(
                        fixture_root(),
                        inventory,
                        control_flow_proof=proof,
                        **kwargs,
                    )

    def test_original_proof_cannot_close_a_sanitized_inventory_copy(self):
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        proof = flow.build_control_flow_proof(image, inventory, inventory_bytes)
        altered = copy.deepcopy(inventory)
        for name in (
            "computed_mmio",
            "unknown_mmio_widths",
            "unknown_mmio_values",
            "unbounded_polls",
            "unknown_memory_ranges",
        ):
            altered[name] = []
        for function in altered["functions"]:
            function["mmio_references"] = []
            function["backward_branches"] = []
        with self.assertRaisesRegex(ValueError, "inventory snapshot"):
            contract.build_contract(
                contract.load_reset_root(ROOT),
                altered,
                control_flow_proof=proof,
                inventory_bytes=inventory_bytes,
                image=image,
            )

    def test_complete_gate_requires_root_records_and_in_bound_callee_coverage(self):
        empty = fixture_inventory()
        empty["functions"] = []
        with self.assertRaisesRegex(ValueError, "root function"):
            contract.build_contract(fixture_root(), empty)

        missing_root = fixture_inventory()
        missing_root["functions"] = missing_root["functions"][1:]
        with self.assertRaisesRegex(ValueError, "root function"):
            contract.build_contract(fixture_root(), missing_root)

        missing_callee = fixture_inventory()
        missing_callee["functions"][1]["direct_calls"] = ["0x00019400"]
        with self.assertRaisesRegex(ValueError, "direct-call coverage"):
            contract.build_contract(fixture_root(), missing_callee)

    def test_function_evidence_cannot_contradict_unresolved_summaries(self):
        mmio = fixture_inventory()
        mmio["functions"][1]["mmio_references"] = [
            {
                "from": "0x00019344",
                "address": "0x40048000",
                "type": "DATA",
            }
        ]
        with self.assertRaisesRegex(ValueError, "MMIO-width summary"):
            contract.build_contract(fixture_root(), mmio)

        branch = fixture_inventory()
        branch["functions"][1]["backward_branches"] = [
            {
                "from": "0x0001934c",
                "to": "0x00019344",
                "type": "CONDITIONAL_JUMP",
            }
        ]
        with self.assertRaisesRegex(ValueError, "poll summary"):
            contract.build_contract(fixture_root(), branch)

    def test_computed_mmio_and_unbounded_polling_fail_independently(self):
        for field, value, false_gates in (
            (
                "computed_mmio",
                ["0x40000000+r3"],
                {"mmio_addresses_closed", "mmio_widths_closed"},
            ),
            ("unbounded_polls", ["0x000191f0"], {"polls_bounded"}),
        ):
            with self.subTest(field=field):
                inventory = fixture_inventory()
                inventory[field] = value
                report = contract.build_contract(fixture_root(), inventory)
                self.assertFalse(report["go"])
                self.assertEqual(
                    false_gates,
                    {
                        name
                        for name, result in report["gates"].items()
                        if not result
                    },
                )

    def test_computed_only_inventory_sanitizes_without_width_proof(self):
        inventory = fixture_inventory()
        inventory["computed_mmio"] = ["0x40000000+r3"]
        report = contract.build_contract(fixture_root(), inventory)
        self.assertFalse(report["gates"]["mmio_widths_closed"])
        receipt = contract.sanitize_contract(report)
        self.assertFalse(receipt["gates"]["mmio_widths_closed"])
        self.assertFalse(receipt["go"])

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

    def test_public_receipt_exposes_only_control_flow_proof_digest(self):
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        proof = flow.build_control_flow_proof(image, inventory, inventory_bytes)
        complete = contract.build_contract(
            contract.load_reset_root(ROOT),
            inventory,
            control_flow_proof=proof,
            inventory_bytes=inventory_bytes,
            image=image,
        )
        receipt = contract.sanitize_contract(complete)
        self.assertEqual(flow.proof_sha256(proof), receipt["control_flow_proof_sha256"])
        self.assertNotIn("control_flow_proof", receipt)

    def test_public_receipt_exposes_only_mmio_width_proof_digest(self):
        inventory, inventory_bytes = actual_inventory()
        image = contract.pinned_image_path(ROOT).read_bytes()
        width_proof = widths.build_mmio_width_proof(
            image, inventory, inventory_bytes
        )
        complete = contract.build_contract(
            contract.load_reset_root(ROOT),
            inventory,
            mmio_width_proof=width_proof,
            inventory_bytes=inventory_bytes,
            image=image,
        )
        receipt = contract.sanitize_contract(complete)
        self.assertEqual(
            widths.proof_sha256(width_proof),
            receipt["mmio_width_proof_sha256"],
        )
        self.assertNotIn("mmio_width_proof", receipt)

    def test_public_sanitizer_requires_width_digest_for_closed_width_evidence(self):
        inventory, _ = actual_inventory()
        complete = contract.build_contract(
            contract.load_reset_root(ROOT), inventory
        )
        complete["gates"]["mmio_widths_closed"] = True
        with self.assertRaisesRegex(ValueError, "MMIO-width proof digest"):
            contract.sanitize_contract(complete)

    def test_public_sanitizer_requires_proof_digest_for_closed_indirect_sites(self):
        inventory = fixture_indirect_inventory()
        complete = contract.build_contract(fixture_root(), inventory)
        complete["gates"]["control_flow_closed"] = True
        complete["go"] = True
        with self.assertRaisesRegex(ValueError, "control-flow proof digest"):
            contract.sanitize_contract(complete)

    def test_public_sanitizer_rejects_private_text_in_hash_field(self):
        complete = contract.build_contract(fixture_root(), fixture_inventory())
        private_text = r"C:\Users\zgbre\private\decompilation"
        complete["functions"][0]["sha256"] = private_text.ljust(64, "x")
        with self.assertRaisesRegex(ValueError, "function SHA-256"):
            contract.sanitize_contract(complete)


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
            + CONTROL_FLOW_RECEIPT.read_text(encoding="utf-8")
            + MMIO_WIDTH_RECEIPT.read_text(encoding="utf-8")
        ).lower()
        self.assertNotIn("c:\\\\users", combined)
        self.assertNotIn("artifacts/firmware", combined)
        self.assertNotIn("decompilation.txt", combined)

    def test_committed_control_flow_receipt_is_bound_to_reset_receipt(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        proof = json.loads(CONTROL_FLOW_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(flow.SCHEMA, proof["schema"])
        self.assertEqual(receipt["source_sha256"], proof["source_sha256"])
        self.assertEqual(
            receipt["control_flow_proof_sha256"], flow.proof_sha256(proof)
        )
        self.assertTrue(receipt["gates"]["control_flow_closed"])
        self.assertFalse(receipt["go"])

    def test_committed_mmio_width_receipt_is_bound_to_reset_receipt(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        proof = json.loads(MMIO_WIDTH_RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(widths.SCHEMA, proof["schema"])
        self.assertEqual(receipt["source_sha256"], proof["source_sha256"])
        self.assertEqual(
            receipt["mmio_width_proof_sha256"], widths.proof_sha256(proof)
        )
        self.assertTrue(receipt["gates"]["mmio_widths_closed"])
        self.assertFalse(receipt["go"])

    def test_k28_readme_links_the_reset_contract_and_keeps_install_blocked(self):
        readme = K28_README.read_text(encoding="utf-8")
        self.assertIn("../../../docs/standalone-reset-contract.md", readme)
        self.assertIn("`go=false`", readme)
        self.assertIn("not safe to install", readme)


if __name__ == "__main__":
    unittest.main()
