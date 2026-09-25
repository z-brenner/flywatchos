import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
RUN = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "standalone-reset-contract-2026-09-24-b"
)
INVENTORY_PATH = RUN / "ghidra-inventory.json"
sys.path.insert(0, str(TOOLS))

import k28_mmio_widths as widths  # noqa: E402
import k28_reset_contract as contract  # noqa: E402


class MmioWidthProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = contract.pinned_image_path(ROOT).read_bytes()
        cls.inventory_bytes = INVENTORY_PATH.read_bytes()
        cls.inventory = json.loads(cls.inventory_bytes)
        cls.proof = widths.build_mmio_width_proof(
            cls.image, cls.inventory, cls.inventory_bytes
        )

    def test_exact_access_universe_is_classified(self):
        proof = self.proof
        self.assertEqual("flyos.fr245.k28-mmio-widths.v1", proof["schema"])
        self.assertEqual(contract.PINNED_IMAGE_SHA256, proof["source_sha256"])
        self.assertEqual(widths.PINNED_INVENTORY_SHA256, proof["inventory_sha256"])
        self.assertEqual(
            {
                "computed_rows": 1065,
                "computed_unique_instructions": 966,
                "direct_reference_rows": 598,
                "direct_unique_instructions": 595,
                "materialization_rows": 31,
                "overlapping_access_instructions": 554,
                "unique_access_instructions": 1007,
            },
            proof["evidence_counts"],
        )
        self.assertTrue(all(proof["gates"].values()))
        self.assertTrue(proof["mmio_widths_closed"])

    def test_width_direction_and_beat_counts_are_exact(self):
        self.assertEqual(
            {"byte": 268, "halfword": 30, "word": 681, "paired_words": 28},
            self.proof["transfer_classes"],
        )
        self.assertEqual(
            {"read": 408, "write": 599}, self.proof["direction_counts"]
        )
        self.assertEqual(
            {"one": 979, "two": 28}, self.proof["beat_counts"]
        )
        self.assertEqual(
            {
                "ldr": 217,
                "ldrb": 178,
                "ldrd": 5,
                "ldrh": 5,
                "ldrsb": 2,
                "str": 463,
                "strb": 88,
                "strd": 23,
                "strh": 25,
                "vldr_s": 1,
            },
            self.proof["instruction_classes"],
        )

    def test_address_materializations_are_not_counted_as_mmio_transactions(self):
        self.assertEqual(
            {"ldr_literal": 28, "register_move": 3},
            self.proof["materialization_classes"],
        )

    def test_data_reference_literal_load_is_a_materialization(self):
        reference = next(
            row
            for row in self.inventory["unknown_mmio_widths"]
            if row["from"] == "0x0001806e"
        )
        self.assertEqual("DATA", reference["type"])
        instruction = widths._instruction(
            self.image, widths._decoder(), 0x0001806E
        )
        classification = widths._classify_materialization(
            self.image, instruction, reference
        )
        self.assertEqual("ldr_literal", classification["materialization_class"])
        self.assertEqual("0x000182c0", classification["literal_address"])
        self.assertEqual("0x4004d000", classification["target"])

    def test_inventory_digest_cannot_be_reused_for_altered_inventory(self):
        altered = copy.deepcopy(self.inventory)
        altered["attacker_note"] = "same claimed digest, different inventory"
        with self.assertRaisesRegex(ValueError, "inventory snapshot"):
            widths.build_mmio_width_proof(
                self.image, altered, self.inventory_bytes
            )

    def test_unpinned_inventory_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "snapshot SHA-256"):
            widths.build_mmio_width_proof(
                self.image, self.inventory, self.inventory_bytes + b"\n"
            )

    def test_each_proof_component_mutation_is_rejected(self):
        mutations = (
            lambda p: p.__setitem__("inventory_sha256", "00" * 32),
            lambda p: p["evidence_counts"].__setitem__(
                "unique_access_instructions", 1006
            ),
            lambda p: p["transfer_classes"].__setitem__("word", 680),
            lambda p: p["direction_counts"].__setitem__("write", 598),
            lambda p: p["beat_counts"].__setitem__("two", 27),
            lambda p: p["instruction_classes"].__setitem__("strd", 22),
            lambda p: p["materialization_classes"].__setitem__(
                "ldr_literal", 26
            ),
            lambda p: p.__setitem__("classified_rows_sha256", "00" * 32),
            lambda p: p["gates"].__setitem__(
                "computed_accesses_classified", False
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(self.proof)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, "proof mismatch"):
                    widths.validate_mmio_width_proof(
                        self.image,
                        self.inventory,
                        self.inventory_bytes,
                        changed,
                    )

    def test_source_mutation_is_rejected(self):
        changed = bytearray(self.image)
        changed[0x8DDA - contract.APP_BASE] ^= 1
        with self.assertRaisesRegex(ValueError, "source SHA-256"):
            widths.build_mmio_width_proof(
                bytes(changed), self.inventory, self.inventory_bytes
            )

    def test_cli_writes_fresh_proof_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "widths.json"
            command = [
                sys.executable,
                "-B",
                str(TOOLS / "k28_mmio_widths.py"),
                "--run",
                str(RUN),
                "--output",
                str(output),
            ]
            first = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True
            )
            self.assertEqual(0, first.returncode, first.stdout + first.stderr)
            generated = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(self.proof, generated)
            before = output.read_bytes()
            second = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True
            )
            self.assertEqual(2, second.returncode, second.stdout + second.stderr)
            self.assertEqual(before, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
