import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "garmin-firmware"))
import atlas_shell_feasibility as feasibility


class FeasibilityTests(unittest.TestCase):
    def test_pinned_evidence_blocks_every_unproved_gate(self):
        report = feasibility.evaluate_feasibility(ROOT)
        self.assertEqual([
            "five_key_halfwords", "tri_state_view_classifier", "observed_update_prompt_non_home",
            "usb_3_and_4_detach_convergence", "post_unlock_hook_site", "bounded_retry_context",
            "modal_outcome_or_native_refresh", "atomic_storage_map", "projected_flash_fit",
        ], report["failed_gates"])
        self.assertFalse(report["go"])
        self.assertFalse(report["implementation_allowed"])
        self.assertEqual({"primary": 1023, "secondary": 2048}, report["section_limits"])
        self.assertFalse(report["update_prompt"]["proved_non_home"])
        self.assertFalse(report["storage"]["five_key_words_and_modes_fit"])
        self.assertFalse(report["projected_sections"]["fit_without_repair_byte"])
        self.assertTrue(all(row["upper_bound"] is None for row in report["projected_sections"]["groups"]))
        self.assertEqual({"NORMAL": 0, "CHORD_HOLD": 1, "SYSTEM_PENDING": 2,
                          "SYSTEM_HOME": 3, "SYSTEM_EXCURSION": 4}, report["storage"]["words"][0]["modes"])
        self.assertEqual({"DETACH_NONE": 0, "PENDING": 1, "RETRY1": 2, "RETRY2": 3,
                          "RETRY3": 4, "QUEUED": 5, "EXHAUSTED": 6}, report["storage"]["words"][1]["modes"])

    def test_missing_evidence_returns_every_failed_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            report = feasibility.evaluate_feasibility(Path(directory))
        self.assertFalse(report["go"])
        self.assertEqual(list(feasibility.REQUIRED_GATES), report["failed_gates"])

    def test_unknown_gate_never_becomes_go(self):
        gates = {name: True for name in feasibility.REQUIRED_GATES}
        for gate in feasibility.REQUIRED_GATES:
            candidate = dict(gates)
            candidate[gate] = None
            self.assertEqual([gate], feasibility.failed_gates(candidate))
        self.assertEqual([], feasibility.failed_gates(gates))
        self.assertEqual(list(feasibility.REQUIRED_GATES), feasibility.failed_gates({}))
        self.assertEqual(list(feasibility.REQUIRED_GATES),
                         feasibility.failed_gates({name: "proved" for name in gates}))

    def test_projection_requires_complete_disjoint_measured_intervals(self):
        rows = [
            {"name": "code", "section": "primary", "start": 0x1F6000, "upper_bound": 1023},
            {"name": "tables", "section": "secondary", "start": 0x1FA400, "upper_bound": 2048},
        ]
        self.assertTrue(feasibility.projected_fit(rows, {"code", "tables"}))
        self.assertFalse(feasibility.projected_fit(rows, {"code", "tables", "hook"}))
        for field, value in [("upper_bound", 1024), ("upper_bound", None), ("start", 0x1F6001)]:
            candidate = [dict(row) for row in rows]
            candidate[0][field] = value
            self.assertFalse(feasibility.projected_fit(candidate, {"code", "tables"}))
        self.assertFalse(feasibility.projected_fit(rows + [dict(rows[0], name="overlap")],
                                                 {"code", "tables", "overlap"}))

    def test_no_spare_byte_minimum_and_no_boolean_measurements(self):
        row = {"name": "all", "section": "primary", "start": 0x1F6000, "upper_bound": 1023}
        self.assertTrue(feasibility.projected_fit([row], {"all"}))
        self.assertFalse(feasibility.projected_fit([dict(row, upper_bound=True)], {"all"}))


if __name__ == "__main__":
    unittest.main()
