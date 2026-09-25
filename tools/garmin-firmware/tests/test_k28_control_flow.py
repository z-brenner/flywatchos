import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
INVENTORY_PATH = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "standalone-reset-contract-2026-09-24-b"
    / "ghidra-inventory.json"
)
sys.path.insert(0, str(TOOLS))

import k28_control_flow as flow  # noqa: E402
import k28_reset_contract as contract  # noqa: E402


EXPECTED_SITES = [
    "0x00003204",
    "0x00018e08",
    "0x00018f5e",
    "0x0001a522",
    "0x0001a85a",
    "0x0001a8d0",
    "0x0001a930",
    "0x0001a9a0",
    "0x0001aa88",
]


class ControlFlowProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = contract.pinned_image_path(ROOT).read_bytes()
        cls.inventory_bytes = INVENTORY_PATH.read_bytes()
        cls.inventory = json.loads(cls.inventory_bytes)
        cls.proof = flow.build_control_flow_proof(
            cls.image, cls.inventory, cls.inventory_bytes
        )

    def test_exact_nine_site_closure_is_reproducible(self):
        proof = self.proof
        self.assertEqual("flyos.fr245.k28-control-flow.v1", proof["schema"])
        self.assertEqual(contract.PINNED_IMAGE_SHA256, proof["source_sha256"])
        self.assertEqual(EXPECTED_SITES, proof["indirect_sites"])
        self.assertEqual(4, len(proof["switches"]))
        self.assertEqual(4, len(proof["callbacks"]["functions"]))
        self.assertTrue(all(proof["gates"].values()))
        self.assertTrue(proof["control_flow_closed"])
        flow.validate_control_flow_proof(
            self.image, self.inventory, self.inventory_bytes, proof
        )

    def test_switch_bounds_and_targets_are_exact(self):
        switches = {item["site"]: item for item in self.proof["switches"]}
        expected = {
            "0x0001a522": (
                "tbb",
                21,
                16,
                "0x0001a53c",
                "0x0001a60e",
                "d341e25c012927f2382f2c7a0f55e788c7925231f151186bf259091844da927b",
            ),
            "0x0001aa88": (
                "tbb",
                8,
                7,
                "0x0001aa94",
                "0x0001ab16",
                "85761cd06803342d7516d3e69c55343ae9e4973194a974acfeec114a1bd03078",
            ),
            "0x00018e08": (
                "tbh",
                143,
                27,
                "0x00018f2a",
                "0x000190be",
                "354973fe5ae31e61a3508344203a61ce886b5dc014f0c8fcc6d7d61c2be270d5",
            ),
            "0x00018f5e": (
                "tbb",
                5,
                3,
                "0x00018f68",
                "0x00018f96",
                "273b28aef864dd83fc5d68c156ca953bebb451ad5a98648b378c55358ea271b7",
            ),
        }
        for site, values in expected.items():
            with self.subTest(site=site):
                item = switches[site]
                actual = (
                    item["kind"],
                    item["entry_count"],
                    item["unique_target_count"],
                    item["target_min"],
                    item["target_max"],
                    item["targets_sha256"],
                )
                self.assertEqual(values, actual)

    def test_reset_and_callback_targets_are_exact(self):
        self.assertEqual("0x00019341", self.proof["reset_transfer"]["pointer"])
        self.assertEqual("0x00019340", self.proof["reset_transfer"]["target"])
        callbacks = self.proof["callbacks"]
        self.assertEqual("0x0001a299", callbacks["literal_pointer"])
        self.assertEqual("0x0001a298", callbacks["resolved_target"])
        self.assertEqual(6, len(callbacks["call_sites"]))
        self.assertEqual(3, sum(call["value"] == "null" for call in callbacks["call_sites"]))
        self.assertEqual(
            3,
            sum(call["value"] == "0x0001a298" for call in callbacks["call_sites"]),
        )

    def test_missing_extra_or_moved_inventory_site_is_rejected(self):
        for replacement in ([], ["0x00003204", "0x00003206"]):
            with self.subTest(replacement=replacement):
                inventory = copy.deepcopy(self.inventory)
                inventory["functions"][0]["indirect_control_flow"] = replacement
                with self.assertRaisesRegex(ValueError, "indirect-site set"):
                    flow._validate_inventory(inventory)

    def test_inventory_callers_for_callback_functions_are_exact(self):
        inventory = copy.deepcopy(self.inventory)
        inventory["functions"].append(
            {
                "entry": "0x00019998",
                "direct_calls": ["0x0001a810"],
                "indirect_control_flow": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "callback caller set"):
            flow._validate_inventory(inventory)

    def test_inventory_digest_cannot_be_reused_for_altered_inventory(self):
        altered = copy.deepcopy(self.inventory)
        altered["computed_mmio"] = []
        with self.assertRaisesRegex(ValueError, "inventory snapshot"):
            flow.build_control_flow_proof(
                self.image, altered, self.inventory_bytes
            )

    def test_unpinned_inventory_snapshot_is_rejected(self):
        changed_bytes = self.inventory_bytes + b"\n"
        with self.assertRaisesRegex(ValueError, "snapshot SHA-256"):
            flow.build_control_flow_proof(
                self.image, self.inventory, changed_bytes
            )

    def test_each_proof_component_mutation_is_rejected(self):
        mutations = (
            ("inventory hash", lambda p: p.__setitem__("inventory_sha256", "00" * 32)),
            ("site set", lambda p: p["indirect_sites"].pop()),
            ("reset", lambda p: p["reset_transfer"].__setitem__("target", "0x00019342")),
            ("switch table", lambda p: p["switches"][0].__setitem__("entry_count", 20)),
            ("dispatcher", lambda p: p["callbacks"]["dispatcher_window"].__setitem__("sha256", "00" * 32)),
            ("callback", lambda p: p["callbacks"]["functions"][0].__setitem__("sha256", "00" * 32)),
            ("literal", lambda p: p["callbacks"].__setitem__("literal_pointer", "0x00000001")),
            ("delay target", lambda p: p["callbacks"]["target_window"].__setitem__("sha256", "00" * 32)),
            ("gate", lambda p: p["gates"].__setitem__("callbacks_resolved", False)),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = copy.deepcopy(self.proof)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, "proof mismatch"):
                    flow.validate_control_flow_proof(
                        self.image,
                        self.inventory,
                        self.inventory_bytes,
                        changed,
                    )

    def test_source_mutation_in_each_evidence_class_is_rejected(self):
        for label, address in (
            ("reset", 0x3204),
            ("switch", 0x1A522),
            ("dispatcher", 0x1AA34),
            ("callback", 0x1A85A),
            ("literal", 0x1AB78),
            ("delay target", 0x1A298),
        ):
            with self.subTest(label=label):
                damaged = bytearray(self.image)
                damaged[address - contract.APP_BASE] ^= 1
                with self.assertRaisesRegex(ValueError, "source SHA-256"):
                    flow.build_control_flow_proof(
                        bytes(damaged), self.inventory, self.inventory_bytes
                    )


if __name__ == "__main__":
    unittest.main()
