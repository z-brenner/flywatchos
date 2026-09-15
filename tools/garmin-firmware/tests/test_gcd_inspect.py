import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "gcd_inspect.py"


def load_module():
    spec = importlib.util.spec_from_file_location("gcd_inspect", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def record(record_id: int, body: bytes) -> bytes:
    return struct.pack("<HH", record_id, len(body)) + body


class GcdInspectTests(unittest.TestCase):
    def test_parses_flat_records_without_treating_payload_bytes_as_headers(self):
        module = load_module()
        payload = b"inside\x01\x00\x01\x00\x64\x06\x00\x12\x00payload"
        blob = b"GARMIN" + struct.pack("<H", 100)
        blob += record(0x02BD, payload) + record(0xFFFF, b"")

        parsed = module.parse_gcd(blob)

        self.assertEqual(parsed.format_version, 100)
        self.assertEqual(
            [(item.record_id, item.length) for item in parsed.records],
            [(0x02BD, 22), (0xFFFF, 0)],
        )

    def test_rejects_a_record_that_extends_past_end_of_file(self):
        module = load_module()
        blob = b"GARMIN" + struct.pack("<H", 100)
        blob += struct.pack("<HH", 0x02BD, 8) + b"short"

        with self.assertRaisesRegex(module.GcdFormatError, "extends past end"):
            module.parse_gcd(blob)

    def test_decodes_descriptor_and_extracts_xored_stream(self):
        module = load_module()
        descriptor_type = bytes(
            [0x0B, 0x00, 0x0A, 0x00, 0x0A, 0x10, 0x15, 0x20, 0x09, 0x10, 0x0D, 0x10, 0x03, 0x50]
        )
        descriptor = (
            b"\x01"
            + b"\x5a"
            + struct.pack("<H", 0x02BD)
            + struct.pack("<I", 5)
            + struct.pack("<H", 3076)
            + struct.pack("<H", 310)
        )
        encoded = bytes(value ^ 0x5A for value in b"HELLO")
        blob = b"GARMIN" + struct.pack("<H", 100)
        blob += record(0x0006, descriptor_type)
        blob += record(0x0007, descriptor)
        blob += record(0x02BD, encoded[:2])
        blob += record(0x02BD, encoded[2:])
        blob += record(0xFFFF, b"")

        parsed = module.parse_gcd(blob)
        streams = module.collect_streams(parsed)

        self.assertEqual(len(streams), 1)
        self.assertEqual(streams[0].record_id, 0x02BD)
        self.assertEqual(streams[0].declared_length, 5)
        self.assertEqual(streams[0].hwid, 3076)
        self.assertEqual(streams[0].software_version, 310)
        self.assertEqual(streams[0].decoded, b"HELLO")

    def test_write_analysis_never_changes_the_input(self):
        module = load_module()
        blob = b"GARMIN" + struct.pack("<H", 100)
        blob += record(0x02BD, b"firmware") + record(0xFFFF, b"")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.gcd"
            output = root / "analysis"
            source.write_bytes(blob)

            module.analyze_file(source, output, extract=True)

            self.assertEqual(source.read_bytes(), blob)
            self.assertTrue((output / "analysis.json").is_file())

    def test_maps_reset_vector_to_the_expected_file_offset(self):
        module = load_module()
        image = struct.pack("<II", 0x20010000, 0x000031F1) + bytes(0x200)

        location = module.reset_handler_location(image, load_address=0x3000)

        self.assertEqual(location, 0x1F0)


if __name__ == "__main__":
    unittest.main()
