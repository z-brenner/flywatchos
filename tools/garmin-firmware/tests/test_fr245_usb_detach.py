import sys
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "garmin-firmware"))
import fr245_usb_detach as usb
EVIDENCE_DIR = Path(os.environ.get("FLYOS_ATLAS_EVIDENCE_DIR", ROOT / "artifacts/firmware/analysis"))


class UsbDetachTests(unittest.TestCase):
    def test_pinned_detach_inventory_does_not_claim_unproved_context(self):
        report = usb.analyze_usb_detach(ROOT, evidence_dir=EVIDENCE_DIR)
        self.assertEqual("2f9c2ca2710dae634ce952ba48ae34789e83fb902106e39869c0d9d36f93020a",
                         report["state_machine"]["sha256"])
        self.assertFalse(report["edges"]["3_to_detach"]["proved"])
        self.assertTrue(report["edges"]["4_to_detach"]["proved"])
        self.assertEqual(1, report["teardown"]["calls_per_local_path"])
        self.assertIsNone(report["teardown"]["calls_per_detach_epoch"])
        self.assertEqual("unproved", report["queue_site"]["mutex_state"])
        self.assertEqual("back", report["queue_site"]["requested_ordering"])
        self.assertFalse(report["queue_site"]["proved"])
        self.assertFalse(report["retry_context"]["bounded"])
        self.assertEqual("unproved", report["modal_outcome"]["kind"])
        self.assertTrue(report["ghidra"]["verified"], report["ghidra"])
        self.assertGreater(report["ghidra"]["function_count"], 0)
        self.assertGreater(report["ghidra"]["block_count"], 0)

    def test_missing_firmware_keeps_every_dependent_proof_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            report = usb.analyze_usb_detach(Path(directory))
        self.assertFalse(report["proved"])
        self.assertFalse(report["edges"]["3_to_detach"]["proved"])
        self.assertFalse(report["edges"]["4_to_detach"]["proved"])
        self.assertFalse(report["retry_context"]["bounded"])
        self.assertEqual("unproved", report["modal_outcome"]["kind"])

    def test_state_three_wait_is_not_a_bounded_detach_proof(self):
        report = usb.analyze_usb_detach(ROOT, evidence_dir=EVIDENCE_DIR)
        self.assertEqual(0, report["teardown"]["cache_after_local_path"])
        self.assertEqual([0x20892, 0x2089A], report["edges"]["3_to_detach"]["counterexample_path"])
        self.assertFalse(report["edges"]["3_to_detach"]["proved"])
        self.assertFalse(report["retry_context"]["bounded"])
        self.assertIsNone(report["retry_context"]["callback"])
        self.assertFalse(report["cache_accesses"]["complete"])
        self.assertEqual(0x20A8A, report["hook_sites"][1]["address"])
        self.assertEqual("held_before_replayed_unlock", report["hook_sites"][1]["mutex_state"])

    def test_wrong_image_is_rejected_before_any_transition_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"untrusted firmware")
            report = usb.analyze_usb_detach(root)
        self.assertFalse(report["image"]["proved"])
        self.assertFalse(report["edges"]["4_to_detach"]["proved"])
        self.assertEqual([], report["functions"])

    def test_cli_preserves_existing_report_and_checksum(self):
        for collision in ("report.json", "report.json.sha256"):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                sentinel = folder / collision
                sentinel.write_bytes(b"original evidence\x00\xff")
                result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/garmin-firmware/fr245_usb_detach.py"),
                    "--root", directory, "--write-private-report", str(folder / "report.json")],
                    capture_output=True, text=True)
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn("output collision", result.stderr.lower())
                self.assertEqual(b"original evidence\x00\xff", sentinel.read_bytes())
                self.assertEqual([collision], [path.name for path in folder.iterdir()])

    def test_malformed_memory_rows_return_complete_failed_gate_report(self):
        import atlas_shell_feasibility as feasibility
        original = json.loads((EVIDENCE_DIR / "fr245-1370-usb-detach-ghidra.json").read_bytes())
        valid_row = original["memory_operations"][0]
        invalid = [None, {}, [{}], [None], [dict(valid_row, unresolved_computed_pointer="true")],
                   [dict(valid_row, width=None)], [dict(valid_row, instruction="address")]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin"
            image.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / image.relative_to(root), image)
            analysis = image.parent.parent
            for rows in invalid:
                with self.subTest(rows=rows):
                    inventory = dict(original, memory_operations=rows)
                    raw = json.dumps(inventory).encode()
                    (analysis / "fr245-1370-usb-detach-ghidra.json").write_bytes(raw)
                    (analysis / "fr245-1370-usb-detach-ghidra.log").write_text(
                        "USB_DETACH_REPORT_COMPLETE json_sha256=" + hashlib.sha256(raw).hexdigest())
                    report = feasibility.evaluate_feasibility(root)
                    self.assertFalse(report["go"])
                    self.assertEqual(9, len(report["failed_gates"]))
                    self.assertFalse(report["usb_detach"]["ghidra"]["verified"])
                    self.assertIn("memory_operations", report["usb_detach"]["ghidra"]["reason"])

    def test_ghidra_rejects_either_output_collision_without_creating_its_sibling(self):
        launcher = ROOT / "tools/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat"
        project = (ROOT / "artifacts/firmware/ghidra-code").resolve()
        for collision in ("inventory.json", "decompilation.txt"):
            with self.subTest(collision=collision), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                sentinel = folder / collision
                sentinel.write_bytes(b"original ghidra evidence\x00\xff")
                result = subprocess.run([str(launcher), str(project), "FR245_1370_CODE",
                    "-process", "stream_01_fw_all_bin.bin", "-readOnly", "-noanalysis",
                    "-log", str(folder / "headless.log"), "-scriptlog", str(folder / "script.log"),
                    "-scriptPath", str(ROOT / "tools/garmin-firmware/ghidra_scripts"),
                    "-postScript", "UsbDetachReport.java", str(folder / "inventory.json"),
                    str(folder / "decompilation.txt")], capture_output=True, text=True, timeout=180)
                # Ghidra may exit zero for a failed post-script, so check its error and files.
                self.assertIn("output collision", (result.stdout + result.stderr).lower())
                self.assertEqual(b"original ghidra evidence\x00\xff", sentinel.read_bytes())
                other = "decompilation.txt" if collision == "inventory.json" else "inventory.json"
                self.assertFalse((folder / other).exists())


if __name__ == "__main__":
    unittest.main()
