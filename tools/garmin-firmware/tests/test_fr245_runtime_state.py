import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools" / "garmin-firmware"
ANALYZER = TOOLS / "fr245_runtime_state.py"
IMAGE = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "Forerunner245_1370_GUPDATE"
    / "stream_01_fw_all_bin.bin"
)
EXPECTED_OUTPUT = (
    ROOT
    / "artifacts"
    / "firmware"
    / "analysis"
    / "fr245-1370-runtime-state.json"
)


def load_analyzer():
    if not ANALYZER.exists():
        raise AssertionError("runtime-state analyzer must exist")
    spec = importlib.util.spec_from_file_location("fr245_runtime_state", ANALYZER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RuntimeStateEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = load_analyzer()
        cls.report = cls.analyzer.analyze(IMAGE)

    def test_report_is_bound_to_exact_1370_image(self):
        self.assertEqual(
            self.report["image"]["sha256"],
            "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6",
        )
        self.assertEqual(self.report["image"]["base_address"], "0x00003000")
        self.assertEqual(self.report["image"]["size"], 5_079_040)
        self.assertTrue(all(item["passed"] for item in self.report["evidence_assertions"]))

    def test_only_the_four_audited_runtime_signals_are_available(self):
        signals = self.report["signals"]
        available = {name for name, signal in signals.items() if signal["status"] == "available"}
        self.assertEqual(
            available,
            {
                "watch_face_active",
                "back_button_pass_through",
                "usb_mass_storage",
                "battery_percent",
            },
        )

    def test_requested_but_unproved_signals_fail_closed(self):
        signals = self.report["signals"]
        for name in (
            "usb_attached",
            "charging",
            "update_pending",
            "heart_rate_bpm",
            "motion",
            "raw_framebuffer_color_mapping",
        ):
            with self.subTest(signal=name):
                self.assertEqual(signals[name]["status"], "unavailable")
                self.assertEqual(signals[name]["fallback"], "zero_or_dash")
        self.assertEqual(self.report["target_palette_status"], "available")

    def test_target_palette_roles_are_the_exact_proved_mapping(self):
        palette = self.report["target_palette"]
        self.assertEqual(palette["encoding"], "RGB222")
        self.assertEqual(
            palette["formula"],
            "native=(R_level<<4)|(G_level<<2)|B_level",
        )
        self.assertEqual(
            palette["channel_levels"],
            [
                {"level": 0, "component": "0x00"},
                {"level": 1, "component": "0x55"},
                {"level": 2, "component": "0xAA"},
                {"level": 3, "component": "0xFF"},
            ],
        )
        self.assertEqual(
            palette["roles"],
            {
                "background": {"native_byte": "0x00", "rgb": "#000000"},
                "scaffold": {"native_byte": "0x2a", "rgb": "#AAAAAA"},
                "text": {"native_byte": "0x3f", "rgb": "#FFFFFF"},
                "excitatory": {"native_byte": "0x0c", "rgb": "#00FF00"},
                "inhibitory": {"native_byte": "0x33", "rgb": "#FF00FF"},
                "saturated": {"native_byte": "0x38", "rgb": "#FFAA00"},
            },
        )

    def test_all_64_native_and_rgb_cube_values_round_trip(self):
        components = (0x00, 0x55, 0xAA, 0xFF)
        seen = set()
        for red_level, red in enumerate(components):
            for green_level, green in enumerate(components):
                for blue_level, blue in enumerate(components):
                    expected = (red_level << 4) | (green_level << 2) | blue_level
                    native = self.analyzer.rgb_to_native(red, green, blue)
                    self.assertEqual(native, expected)
                    self.assertEqual(
                        self.analyzer.native_to_rgb(native),
                        (red, green, blue),
                    )
                    seen.add(native)
        self.assertEqual(seen, set(range(64)))

    def test_palette_binary_evidence_addresses_slots_and_hashes_are_exact(self):
        evidence = self.report["target_palette_evidence"]
        self.assertTrue(evidence["mapping_proved"])
        self.assertEqual(
            evidence["source_audit"],
            {
                "path": ".superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-3-color-scout.md",
                "sha256": "3c8f643f08d92de5682803a1e883ad1048bef36d97d471ad8eea9676fc6daad2",
            },
        )
        self.assertEqual(
            evidence["functions"],
            {
                "native_to_rgb": {
                    "image_address": "0x00063020",
                    "callable_address": "0x00063021",
                    "instruction_set": "thumb",
                    "thumb": True,
                    "length": 50,
                    "evidence_assertion": "color_native_to_rgb_function",
                },
                "rgb_to_native": {
                    "image_address": "0x00063054",
                    "callable_address": "0x00063055",
                    "instruction_set": "thumb",
                    "thumb": True,
                    "length": 76,
                    "evidence_assertion": "color_rgb_to_native_function",
                },
            },
        )
        self.assertEqual(evidence["callback_table"]["image_address"], "0x00064554")
        self.assertEqual(evidence["callback_table"]["rgb_to_native_slot_offset"], "0x0c")
        self.assertEqual(evidence["callback_table"]["rgb_to_native_pointer"], "0x00063055")
        self.assertEqual(evidence["callback_table"]["native_to_rgb_slot_offset"], "0x2c")
        self.assertEqual(evidence["callback_table"]["native_to_rgb_pointer"], "0x00063021")
        self.assertEqual(evidence["setup_copy"]["image_address"], "0x00063f1c")
        self.assertEqual(evidence["setup_copy"]["source_address"], "0x00064554")
        self.assertEqual(evidence["setup_copy"]["byte_count"], 72)
        assertions = {item["name"]: item for item in self.report["evidence_assertions"]}
        hashes = {
            "color_native_to_rgb_function": "96a9d40ac0e8277d634c16c4cc43bece9bb2f98295f8fb34d7e439a2e8cd1651",
            "color_rgb_to_native_function": "a9fe98122781c77f9b06b35eb05f1fc7d3547f1035f3b00af36eec8b61ecba05",
            "color_callback_table": "4bdaeb1c029ba0ef4c6d90a1b4d77040475fa48334dd75471a8bf091cc8a1ca7",
            "color_table_setup_function": "9d87b588e18b3106af96bf63e67333f243e60c79593dab528451d96ac3334985",
        }
        for name, expected_hash in hashes.items():
            with self.subTest(assertion=name):
                self.assertEqual(assertions[name]["expected"], expected_hash)
                self.assertEqual(assertions[name]["observed"], expected_hash)
                self.assertTrue(assertions[name]["passed"])

    def test_watch_face_pair_and_fail_closed_list_semantics_are_exact(self):
        signal = self.report["signals"]["watch_face_active"]
        self.assertEqual(
            signal["source"]["image_addresses"],
            ["0x0005306c", "0x000530cc"],
        )
        self.assertEqual(
            signal["source"]["callable_addresses"],
            ["0x0005306d", "0x000530cd"],
        )
        self.assertEqual(signal["source"]["instruction_set"], "thumb")
        self.assertIs(signal["source"]["thumb"], True)
        self.assertEqual(signal["source"]["callback_identity"], "0x0005adf5")
        self.assertEqual(signal["source"]["list_root"], "0x20003e84")
        self.assertEqual(signal["source"]["allowed_node_offsets"], ["0x04", "0x08", "0x50"])
        self.assertIn("nonzero", signal["validity_semantics"])
        self.assertIn("equals 1", signal["validity_semantics"])
        self.assertIn("fail closed", signal["validity_semantics"])

    def test_direct_cache_and_back_sources_are_exact(self):
        signals = self.report["signals"]
        self.assertEqual(
            signals["back_button_pass_through"]["source"]["pinned_addresses"],
            ["0x400ff0d0"],
        )
        self.assertIn("bit 1", signals["back_button_pass_through"]["validity_semantics"])
        self.assertIn("active-low", signals["back_button_pass_through"]["validity_semantics"])
        self.assertEqual(
            signals["usb_mass_storage"]["source"]["pinned_addresses"],
            ["0x1ffc6f25"],
        )
        self.assertEqual(signals["usb_mass_storage"]["source"]["true_values"], [3, 4])
        self.assertEqual(
            signals["battery_percent"]["source"]["pinned_addresses"],
            ["0x1ffcccd8"],
        )
        self.assertIn("-1.0", signals["battery_percent"]["validity_semantics"])
        self.assertIn("finite", signals["battery_percent"]["validity_semantics"])
        self.assertIn("[0, 100]", signals["battery_percent"]["validity_semantics"])

    def test_available_sources_are_side_effect_free_and_call_nothing(self):
        for name, signal in self.report["signals"].items():
            if signal["status"] != "available":
                continue
            with self.subTest(signal=name):
                proof = signal["side_effect_free"]
                self.assertTrue(proof["proved"])
                self.assertTrue(proof["evidence"])
                self.assertEqual(signal["prohibited_operations"], [
                    "callbacks",
                    "getters_with_fallbacks",
                    "locks",
                    "peripheral_transactions",
                    "writes",
                ])

    def assert_report_rejected(self, report):
        with self.assertRaisesRegex(ValueError, "canonical allowlist mismatch"):
            self.analyzer.validate_report(report)

    def test_canonical_validator_rejects_top_level_and_signal_set_mutations(self):
        mutations = []

        bad = copy.deepcopy(self.report)
        bad["invented_top_level"] = True
        mutations.append(("unknown top-level field", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["invented_sensor"] = copy.deepcopy(
            self.report["signals"]["battery_percent"]
        )
        mutations.append(("invented available signal with copied proof", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["invented_unavailable"] = copy.deepcopy(
            self.report["signals"]["charging"]
        )
        mutations.append(("invented unavailable signal", bad))

        bad = copy.deepcopy(self.report)
        del bad["signals"]["motion"]
        mutations.append(("missing canonical signal", bad))

        for name, bad in mutations:
            with self.subTest(mutation=name):
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_source_and_semantic_substitution(self):
        mutations = []

        bad = copy.deepcopy(self.report)
        bad["signals"]["battery_percent"]["source"]["pinned_addresses"] = [
            "0x20000000"
        ]
        mutations.append(("address substitution", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["watch_face_active"]["source"]["callable_addresses"] = [
            "0x0005306c",
            "0x000530cc",
        ]
        mutations.append(("even callable addresses", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["watch_face_active"]["source"]["kind"] = "callback"
        mutations.append(("side-effectful source kind", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["usb_mass_storage"]["validity_semantics"] = "Any value is true."
        mutations.append(("validity substitution", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["watch_face_active"]["side_effect_free"]["evidence"] = [
            "Copied prose is enough."
        ]
        mutations.append(("proof prose substitution", bad))

        bad = copy.deepcopy(self.report)
        bad["signals"]["battery_percent"]["prohibited_operations"].remove("callbacks")
        mutations.append(("callback prohibition removed", bad))

        for name, bad in mutations:
            with self.subTest(mutation=name):
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_promotion_of_every_unavailable_signal(self):
        for name in (
            "usb_attached",
            "charging",
            "update_pending",
            "heart_rate_bpm",
            "motion",
            "raw_framebuffer_color_mapping",
        ):
            with self.subTest(signal=name):
                bad = copy.deepcopy(self.report)
                bad["signals"][name] = copy.deepcopy(
                    self.report["signals"]["battery_percent"]
                )
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_inconsistent_unavailable_blocks(self):
        mutations = []
        for field, value in (
            ("source", {"pinned_addresses": ["0x1ffcccd8"]}),
            ("fallback", "trust_last_value"),
            ("validity_semantics", "Use it anyway."),
            ("side_effect_free", {"proved": True, "evidence": ["copied"]}),
            ("prohibited_operations", []),
        ):
            bad = copy.deepcopy(self.report)
            bad["signals"]["charging"][field] = value
            mutations.append((field, bad))
        for field, bad in mutations:
            with self.subTest(field=field):
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_image_and_evidence_mutations(self):
        mutations = []
        for field, value in (
            ("path", "another/image.bin"),
            ("base_address", "0x00000000"),
            ("size", 1),
            ("sha256", "0" * 64),
        ):
            bad = copy.deepcopy(self.report)
            bad["image"][field] = value
            mutations.append((f"image {field}", bad))

        for field, value in (
            ("passed", False),
            ("expected", "0" * 64),
            ("observed", "0" * 64),
            ("virtual_address", "0x00000000"),
            ("description", "substituted"),
        ):
            bad = copy.deepcopy(self.report)
            bad["evidence_assertions"][0][field] = value
            mutations.append((f"assertion {field}", bad))

        bad = copy.deepcopy(self.report)
        bad["evidence_assertions"].append(copy.deepcopy(bad["evidence_assertions"][0]))
        mutations.append(("extra assertion", bad))

        for name, bad in mutations:
            with self.subTest(mutation=name):
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_every_noncanonical_palette_state(self):
        mutations = []
        for value in ("enabled", "unavailable", None, ""):
            bad = copy.deepcopy(self.report)
            bad["target_palette_status"] = value
            mutations.append((repr(value), bad))

        bad = copy.deepcopy(self.report)
        bad["target_palette"] = {}
        mutations.append(("missing available mapping", bad))

        for name, bad in mutations:
            with self.subTest(palette_status=name):
                self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_every_palette_role_mutation(self):
        roles = self.report["target_palette"]["roles"]
        for role in roles:
            for field, value in (("native_byte", "0x01"), ("rgb", "#010101")):
                with self.subTest(role=role, field=field):
                    bad = copy.deepcopy(self.report)
                    bad["target_palette"]["roles"][role][field] = value
                    self.assert_report_rejected(bad)

    def test_canonical_validator_rejects_palette_formula_and_binary_evidence_mutations(self):
        mutations = []

        bad = copy.deepcopy(self.report)
        bad["target_palette"]["formula"] = "native=(B_level<<4)|(G_level<<2)|R_level"
        mutations.append(("formula", bad))

        bad = copy.deepcopy(self.report)
        bad["target_palette"]["channel_levels"][2]["component"] = "0xAB"
        mutations.append(("channel level", bad))

        for path, value in (
            (("functions", "native_to_rgb", "image_address"), "0x00063022"),
            (("functions", "native_to_rgb", "callable_address"), "0x00063020"),
            (("functions", "rgb_to_native", "image_address"), "0x00063056"),
            (("functions", "rgb_to_native", "callable_address"), "0x00063054"),
            (("functions", "native_to_rgb", "length"), 48),
            (("functions", "rgb_to_native", "thumb"), False),
            (("functions", "rgb_to_native", "evidence_assertion"), "framebuffer_converter_masks"),
            (("callback_table", "image_address"), "0x00064558"),
            (("callback_table", "rgb_to_native_slot_offset"), "0x10"),
            (("callback_table", "rgb_to_native_pointer"), "0x00063021"),
            (("callback_table", "native_to_rgb_pointer"), "0x00063055"),
            (("setup_copy", "image_address"), "0x00063f1e"),
            (("setup_copy", "callable_address"), "0x00063f1c"),
            (("setup_copy", "source_address"), "0x00064558"),
            (("setup_copy", "byte_count"), 64),
            (("roundtrip", "native_values"), 63),
            (("source_audit", "sha256"), "0" * 64),
        ):
            bad = copy.deepcopy(self.report)
            node = bad["target_palette_evidence"]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            mutations.append(("/".join(path), bad))

        bad = copy.deepcopy(self.report)
        bad["target_palette_evidence"]["mapping_proved"] = False
        mutations.append(("mapping proof", bad))

        for assertion_name in (
            "color_native_to_rgb_function",
            "color_rgb_to_native_function",
            "color_callback_table",
            "color_table_setup_function",
            "color_table_source_literal",
            "color_rgb_to_native_table_slot",
            "color_native_to_rgb_table_slot",
        ):
            bad = copy.deepcopy(self.report)
            assertion = next(
                item
                for item in bad["evidence_assertions"]
                if item["name"] == assertion_name
            )
            assertion["passed"] = False
            mutations.append((f"assertion/{assertion_name}", bad))

        for name, bad in mutations:
            with self.subTest(mutation=name):
                self.assert_report_rejected(bad)

    def test_literal_and_function_evidence_is_pinned_by_address(self):
        assertions = {item["name"]: item for item in self.report["evidence_assertions"]}
        expected = {
            "watch_face_finder_function": ("0x0005306c", "sha256"),
            "watch_face_first_visible_function": ("0x000530cc", "sha256"),
            "watch_face_callback_literal": ("0x0006c0a8", "little_endian_u32"),
            "watch_face_list_root_literal": ("0x00053084", "little_endian_u32"),
            "watch_face_failure_string": ("0x0006be90", "ascii_z"),
            "usb_state_cache_literal": ("0x000205ac", "little_endian_u32"),
            "battery_base_literal": ("0x0000bfdc", "little_endian_u32"),
            "button_table": ("0x0000f9bc", "sha256"),
            "framebuffer_converter_masks": ("0x0000e3ee", "sha256"),
            "color_native_to_rgb_function": ("0x00063020", "sha256"),
            "color_rgb_to_native_function": ("0x00063054", "sha256"),
            "color_callback_table": ("0x00064554", "sha256"),
            "color_table_setup_function": ("0x00063f1c", "sha256"),
            "color_table_source_literal": ("0x00063f48", "little_endian_u32"),
            "color_rgb_to_native_table_slot": ("0x00064560", "little_endian_u32"),
            "color_native_to_rgb_table_slot": ("0x00064580", "little_endian_u32"),
        }
        for name, (address, kind) in expected.items():
            with self.subTest(assertion=name):
                self.assertEqual(assertions[name]["virtual_address"], address)
                self.assertEqual(assertions[name]["kind"], kind)
                self.assertTrue(assertions[name]["passed"])

    def test_cli_reproduces_checked_in_json_on_stdout_without_writing(self):
        completed = subprocess.run(
            [sys.executable, str(ANALYZER), "--image", str(IMAGE)],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        self.assertEqual(completed.stdout, EXPECTED_OUTPUT.read_bytes())
        expected = EXPECTED_OUTPUT.read_text(encoding="utf-8")
        stdout_text = completed.stdout.decode("utf-8")
        self.assertEqual(stdout_text, expected)
        self.assertEqual(json.loads(stdout_text), self.report)

    def test_cli_rejects_all_output_destinations_before_writing(self):
        original = IMAGE.read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            cases = [
                ("traversal", temp_root / "nested" / ".." / "escaped.json", False),
                ("alternate root", temp_root / "alternate.json", False),
                ("non-json", temp_root / "report.bin", False),
                ("target", temp_root / "target" / "report.json", False),
                ("quarantine", temp_root / "quarantine" / "report.json", False),
                ("staging", temp_root / "staging" / "report.json", False),
            ]
            if os.name == "nt":
                cases.append(("alternate drive", Path(r"Z:\runtime-state.json"), False))
            else:
                cases.append(("alternate root", Path("/runtime-state.json"), False))

            for index, (name, output, _) in enumerate(cases):
                with self.subTest(destination=name):
                    copied_image = temp_root / f"input-{index}.bin"
                    copied_image.write_bytes(original)
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(ANALYZER),
                            "--image",
                            str(copied_image),
                            "--output",
                            str(output),
                        ],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("unrecognized arguments", completed.stderr)
                    self.assertEqual(copied_image.read_bytes(), original)
                    self.assertFalse(output.exists())

            protected_copy = temp_root / "protected-input.bin"
            protected_copy.write_bytes(original)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZER),
                    "--image",
                    str(protected_copy),
                    "--output",
                    str(protected_copy),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(protected_copy.read_bytes(), original)

            hardlink = temp_root / "input-hardlink.bin"
            hardlink_source = temp_root / "input-hardlink-source.bin"
            hardlink_source.write_bytes(original)
            try:
                os.link(hardlink_source, hardlink)
            except OSError:
                pass
            else:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ANALYZER),
                        "--image",
                        str(hardlink_source),
                        "--output",
                        str(hardlink),
                    ],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(hardlink_source.read_bytes(), original)
                self.assertEqual(hardlink.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
