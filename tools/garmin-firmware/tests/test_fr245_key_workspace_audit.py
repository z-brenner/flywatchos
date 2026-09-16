import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "garmin-firmware"))
import fr245_key_workspace_audit as audit


class KeyWorkspaceTests(unittest.TestCase):
    def test_audited_accesses_do_not_promote_unknown_stock_aliases_to_proof(self):
        report = audit.audit_key_workspace(ROOT)
        self.assertEqual(
            [0x1FFDBBFE, 0x1FFDBC36, 0x1FFDBC6E, 0x1FFDBCA6, 0x1FFDBCDE],
            [item["address"] for item in report["records"]],
        )
        self.assertFalse(report["proved"])
        self.assertTrue(all(item["max_stock_offset"] is None for item in report["records"]))
        self.assertEqual([0x35] * 5, [item["max_audited_offset"] for item in report["records"]])
        self.assertEqual(
            [0xF840, 0xFA3C, 0xFA80, 0xFB0C, 0xFCA0, 0xFCD0, 0xFD00],
            report["workspace_base_literal_vas"],
        )
        self.assertTrue(report["scheduled_object_span_excludes_0x36_0x37"])
        self.assertTrue(report["phase_timing"]["phase4_max_period_ms"] <= 200)
        self.assertTrue(report["phase_timing"]["proved"])
        self.assertTrue(all(item["proved"] for item in report["functions"]))
        self.assertFalse(report["coverage"]["complete"])
        self.assertTrue(report["unresolved"])

    def test_missing_firmware_does_not_claim_free_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            report = audit.audit_key_workspace(Path(directory))
        self.assertFalse(report["proved"])
        self.assertFalse(report["phase_timing"]["proved"])
        self.assertTrue(report["unresolved"])

    def test_access_width_and_unknown_offsets_fail_closed(self):
        self.assertTrue(audit.accesses_exclude_pad([{"offset": 0x34, "width": 2}]))
        self.assertFalse(audit.accesses_exclude_pad([{"offset": 0x34, "width": 4}]))
        self.assertFalse(audit.accesses_exclude_pad([{"offset": None, "width": 1}]))
        self.assertFalse(audit.accesses_exclude_pad([]))


if __name__ == "__main__":
    unittest.main()
