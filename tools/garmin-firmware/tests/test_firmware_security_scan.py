import importlib.util
import struct
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "firmware_security_scan.py"
SPEC = importlib.util.spec_from_file_location("firmware_security_scan", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FirmwareSecurityScanTests(unittest.TestCase):
    def test_exact_pointer_and_thumb_literal_load(self):
        base = 0x3000
        data = bytearray(0x100)
        # At 0x3010: LDR r0,[PC,#0x0c] -> literal slot 0x3020.
        struct.pack_into("<H", data, 0x10, 0x4803)
        struct.pack_into("<I", data, 0x20, base + 0x40)
        data[0x40:0x40 + len(b"GUPDATE.GCD")] = b"GUPDATE.GCD"
        report = MODULE.scan(bytes(data), base)
        hit = next(item for item in report["anchors"] if item["text"] == "GUPDATE.GCD")
        self.assertEqual(hit["exact_pointer_slots"], ["0x00003020"])
        self.assertEqual(hit["thumb1_literal_loads"][0]["address"], "0x00003010")

    def test_sha256_constants(self):
        words = MODULE.CONSTANT_SETS["sha256_initial_state"]
        data = b"X" * 8 + b"".join(struct.pack("<I", x) for x in words)
        report = MODULE.scan(data, 0x3000)
        match = next(x for x in report["cryptographic_constant_sets"] if x["name"] == "sha256_initial_state")
        self.assertEqual(match["little_endian_addresses"], ["0x00003008"])


if __name__ == "__main__":
    unittest.main()
