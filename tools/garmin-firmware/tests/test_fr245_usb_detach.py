import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "garmin-firmware"))
import fr245_usb_detach as usb


class UsbDetachTests(unittest.TestCase):
    def test_pinned_detach_inventory_does_not_claim_unproved_context(self):
        report = usb.analyze_usb_detach(ROOT)
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
        report = usb.analyze_usb_detach(ROOT)
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


if __name__ == "__main__":
    unittest.main()
