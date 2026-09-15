import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INSPECT_PATH = ROOT / "gcd_inspect.py"
LAB_PATH = ROOT / "gcd_mutation_lab.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def record(record_id: int, body: bytes) -> bytes:
    return struct.pack("<HH", record_id, len(body)) + body


class GcdMutationLabTests(unittest.TestCase):
    def test_mutation_is_metadata_only_and_recomputes_checkpoints(self):
        inspect = load_module("gcd_inspect_for_lab", INSPECT_PATH)
        lab = load_module("gcd_mutation_lab", LAB_PATH)
        source = b"GARMIN" + struct.pack("<H", 100)
        source += record(0x0001, b"\x00")
        source += record(0x0005, b"Copyright test.")
        source += record(0x0001, b"\x00") + record(0xFFFF, b"")
        source = lab.recompute_checkpoints(source, inspect)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "original.gcd"
            output_path = root / "analysis-copy.gcd"
            input_path.write_bytes(source)

            report = lab.mutate_copyright_metadata(input_path, output_path, inspect)

            result = output_path.read_bytes()
            self.assertEqual(input_path.read_bytes(), source)
            self.assertEqual(len(result), len(source))
            self.assertEqual(report["mutation"]["old_byte_ascii"], ".")
            self.assertEqual(report["mutation"]["new_byte_ascii"], "!")
            self.assertTrue(inspect._checkpoint_results(inspect.parse_gcd(result))[0]["valid"])
            self.assertTrue(all(item["valid"] for item in inspect._checkpoint_results(inspect.parse_gcd(result))))

            before = inspect.parse_gcd(source)
            after = inspect.parse_gcd(result)
            before_copyright = next(r.body for r in before.records if r.record_id == 0x0005)
            after_copyright = next(r.body for r in after.records if r.record_id == 0x0005)
            self.assertEqual(before_copyright[:-1], after_copyright[:-1])
            self.assertEqual(after_copyright[-1:], b"!")

    def test_payload_byte_mapping_preserves_structure_and_checkpoints(self):
        inspect = load_module("gcd_inspect_for_payload_lab", INSPECT_PATH)
        lab = load_module("gcd_payload_mutation_lab", ROOT / "gcd_payload_mutation_lab.py")
        types = bytes([0x0A, 0x00, 0x0A, 0x10, 0x15, 0x20, 0x03, 0x50])
        descriptor = b"\x00" + struct.pack("<H", 0x02BD) + struct.pack("<I", 6)
        source = b"GARMIN" + struct.pack("<H", 100)
        source += record(0x0006, types) + record(0x0007, descriptor)
        source += record(0x02BD, b"ABC") + record(0x02BD, b"DEF")
        source += record(0x0001, b"\x00") + record(0xFFFF, b"")
        source = lab.recompute_checkpoints(source, inspect)
        parsed = inspect.parse_gcd(source)
        stream = inspect.collect_streams(parsed)[0]

        result, raw_offset = lab.replace_decoded_stream_byte(source, stream, 4, ord("E"), ord("e"), inspect)

        self.assertEqual(raw_offset, stream.record_offsets[1] + 5)
        self.assertEqual(inspect.collect_streams(inspect.parse_gcd(result))[0].decoded, b"ABCDeF")
        self.assertTrue(all(item["valid"] for item in inspect._checkpoint_results(inspect.parse_gcd(result))))

        changed_stream = inspect.collect_streams(inspect.parse_gcd(result))[0]
        repaired, _, old, new = lab.repair_stream_additive_checksum(result, changed_stream, inspect)
        repaired_stream = inspect.collect_streams(inspect.parse_gcd(repaired))[0]
        self.assertEqual(old, ord("F"))
        self.assertEqual(new, (ord("F") - (sum(b"ABCDeF") & 0xFF)) & 0xFF)
        self.assertEqual(sum(repaired_stream.decoded) & 0xFF, 0)
        self.assertTrue(all(item["valid"] for item in inspect._checkpoint_results(inspect.parse_gcd(repaired))))


if __name__ == "__main__":
    unittest.main()
