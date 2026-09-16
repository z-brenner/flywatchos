import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
sys.path.insert(0, str(TOOLS))
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

    def test_cli_preserves_existing_report_and_checksum(self):
        for collision in ("report.json", "report.json.sha256"):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                sentinel = folder / collision
                sentinel.write_bytes(b"original evidence\x00\xff")
                result = subprocess.run([sys.executable, "-B", str(TOOLS / "fr245_key_workspace_audit.py"),
                    "--root", directory, "--write-private-report", str(folder / "report.json")],
                    capture_output=True, text=True)
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn("output collision", result.stderr.lower())
                self.assertEqual(b"original evidence\x00\xff", sentinel.read_bytes())
                self.assertEqual([collision], [path.name for path in folder.iterdir()])


if __name__ == "__main__":
    unittest.main()
