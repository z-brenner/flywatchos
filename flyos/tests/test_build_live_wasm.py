#!/usr/bin/env python3
"""Fail-closed build regressions; no compiler installation is needed."""
from pathlib import Path
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


BUILDER = Path(__file__).resolve().parents[1] / "tools" / "build_live_wasm.py"
SPEC = importlib.util.spec_from_file_location("fly_live_builder", BUILDER)
BUILDER_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER_MODULE)


class ManifestIdentityTests(unittest.TestCase):
    """Exercise pair/source binding independently of the compiler toolchain.

    The success-path subprocess stub inspects the actual staged byte snapshot;
    real Node rejection and full CI compilation provide execution coverage.
    """
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fly-live-identity-")
        self.directory = Path(self.temporary.name)
        self.wasm = self.directory / "module.wasm"
        self.sidecar = self.wasm.with_suffix(".wasm.json")
        self.module = b"\x00asm\x01\x00\x00\x00"
        self.wasm.write_bytes(self.module)
        self.sources = {name: hashlib.sha256((BUILDER_MODULE.ROOT / name).read_bytes()).hexdigest()
                        for name in (*BUILDER_MODULE.SOURCES, *BUILDER_MODULE.HEADERS, *BUILDER_MODULE.PROVENANCE)}
        self.manifest = {"schema": 1, "scope": "host-only-synthetic", "hardware_verified": False,
            "compiler": "Zig", "compiler_version": "test-fixture", "module_bytes": len(self.module),
            "memory_bytes": 131072, "imports": [], "sha256": hashlib.sha256(self.module).hexdigest(),
            "source_sha256": self.sources, "exports": ["fly_lab_" + name for name in BUILDER_MODULE.EXPORTS],
            "build_command": ["zig", "fixture-only"]}
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def save(self, value=None):
        self.sidecar.write_text(json.dumps(self.manifest if value is None else value, indent=2) + "\n", encoding="utf-8")

    def verify(self, node="node"):
        self.assertTrue(hasattr(BUILDER_MODULE, "verified_artifact"), "manifest/source identity verifier must exist")
        return BUILDER_MODULE.verified_artifact(self.wasm, node)

    def test_exact_snapshot_is_validated_with_timeout_and_original_manifest_digest(self):
        original_manifest = self.sidecar.read_bytes()
        def inspect(command, **kwargs):
            self.assertEqual(Path(command[3]).read_bytes(), self.module)
            self.assertNotEqual(Path(command[3]), self.wasm)
            self.assertGreater(kwargs["timeout"], 0)
            self.assertLessEqual(kwargs["timeout"], 30)
            # The original can change after it is read; never embed this later value.
            self.wasm.write_bytes(b"changed after snapshot")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        with mock.patch.object(BUILDER_MODULE.subprocess, "run", side_effect=inspect):
            data, manifest, digest = self.verify()
        self.assertEqual(data, self.module)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(digest, hashlib.sha256(original_manifest).hexdigest())

    def test_stale_altered_and_incomplete_identity_fail_before_node(self):
        invalid = [None, [], {**self.manifest, "schema": True}, {**self.manifest, "schema": 2},
            {**self.manifest, "scope": "target"}, {**self.manifest, "hardware_verified": True},
            {**self.manifest, "module_bytes": len(self.module) + 1},
            {**self.manifest, "sha256": "0" * 64}, {**self.manifest, "memory_bytes": 65536},
            {**self.manifest, "imports": ["host"]}, {**self.manifest, "exports": []},
            {**self.manifest, "source_sha256": {}},
            {**self.manifest, "source_sha256": {**self.sources, "sim/cx_circuit.c": "0" * 64}},
            {**self.manifest, "source_sha256": {**self.sources, "sim/circuit_models.json": "0" * 64}},
            {**self.manifest, "source_sha256": {key: value for key, value in self.sources.items() if key != "sim/cx_circuit.h"}},
            {**self.manifest, "source_sha256": {**self.sources, "unexpected.c": "0" * 64}}]
        with mock.patch.object(BUILDER_MODULE.subprocess, "run") as process:
            for value in invalid:
                self.sidecar.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "manifest|source|identity"):
                    self.verify()
            process.assert_not_called()

    def test_missing_malformed_oversized_duplicate_and_mismatched_sidecars_fail_closed(self):
        malformed = [b"not json", b"{" + b" " * 131072, b'{"schema":1,"schema":1}', b'\xff',
                     b'[' * 2000 + b']' * 2000,
                     json.dumps({**self.manifest, 'extra': 1}).replace('"extra": 1', '"extra": 1e999').encode('utf-8'),
                     *(json.dumps({**self.manifest, 'extra': value}).encode('utf-8')
                       for value in (float('nan'), float('inf'), float('-inf'))) ]
        with mock.patch.object(BUILDER_MODULE.subprocess, "run") as process:
            for value in malformed:
                self.sidecar.write_bytes(value)
                with self.subTest(value=value[:20]), self.assertRaisesRegex(ValueError, "manifest"):
                    self.verify()
            self.sidecar.unlink()
            with self.assertRaisesRegex(ValueError, "manifest"):
                self.verify()
            self.save()
            self.wasm.write_bytes(self.module + b"changed")
            with self.assertRaisesRegex(ValueError, "identity|manifest"):
                self.verify()
            process.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "requires Node to reject a real incompatible module")
    def test_matching_claims_do_not_bypass_actual_node_abi_validation(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()

    def test_validator_timeout_is_fatal(self):
        with mock.patch.object(BUILDER_MODULE.subprocess, "run", side_effect=subprocess.TimeoutExpired("node", 30)):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.verify()

    def test_current_source_change_during_validation_is_rejected(self):
        source_root = self.directory / "source"
        for name in self.sources:
            target = source_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((BUILDER_MODULE.ROOT / name).read_bytes())
        def mutate_source(command, **kwargs):
            (source_root / "sim/cx_circuit.c").write_bytes(b"changed during validation")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        with mock.patch.object(BUILDER_MODULE, "ROOT", source_root), \
                mock.patch.object(BUILDER_MODULE.subprocess, "run", side_effect=mutate_source):
            with self.assertRaisesRegex(ValueError, "source identity changed"):
                self.verify()


class BuildFailures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fly-live-build-test-")
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "prior.wasm"
        self.manifest = self.directory / "prior.wasm.json"
        self.output.write_bytes(b"previous module")
        self.manifest.write_bytes(b"previous manifest")

    def tearDown(self):
        self.temporary.cleanup()

    def fake_compiler(self, body):
        executable = self.directory / "fake-zig"
        executable.write_text(
            f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
            "if sys.argv[1:] == ['version']:\n"
            "    print('test-fake')\n    raise SystemExit(0)\n" + body,
            encoding="utf-8")
        executable.chmod(executable.stat().st_mode | 0o111)
        return executable

    def run_builder(self, compiler, node="node"):
        result = subprocess.run([sys.executable, str(BUILDER), "--zig", str(compiler),
                                 "--node", node, "--output", str(self.output)],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Validated ", result.stdout)
        self.assertIn("Live Wasm build failed", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"previous module")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")
        self.assertEqual(list(self.directory.glob("live-wasm-*")), [])
        return result

    def test_missing_compiler_preserves_output(self):
        self.run_builder(self.directory / "does-not-exist")

    @unittest.skipIf(os.name == "nt", "fake tool uses a POSIX executable shebang")
    def test_failed_compile_preserves_output(self):
        compiler = self.fake_compiler("raise SystemExit(17)\n")
        result = self.run_builder(compiler)
        self.assertIn("17", result.stderr)

    @unittest.skipUnless(shutil.which("node") and os.name != "nt", "needs Node and POSIX shebang")
    def test_successful_compiler_with_invalid_module_is_not_success(self):
        compiler = self.fake_compiler(
            "Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(b'not wasm')\n")
        result = self.run_builder(compiler)
        self.assertIn("CompileError", result.stderr)

    @unittest.skipIf(os.name == "nt", "fake tool uses a POSIX executable shebang")
    def test_missing_validator_preserves_output(self):
        compiler = self.fake_compiler(
            "Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes(b'not wasm')\n")
        self.run_builder(compiler, str(self.directory / "missing-node"))


class InstallFailures(unittest.TestCase):
    """The compiler/validator are bypassed only to isolate filesystem commit.

    Real compilation and module validation have separate integration coverage.
    These tests inject an actual failed replace, then examine actual files.
    """
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fly-live-install-test-")
        self.directory = Path(self.temporary.name)
        self.output = self.directory / "prior.wasm"
        self.manifest = self.directory / "prior.wasm.json"
        self.output.write_bytes(b"previous module")
        self.manifest.write_bytes(b"previous manifest")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def fake_tool(command, **_kwargs):
        if command[1] == "cc":
            Path(command[command.index("-o") + 1]).write_bytes(b"new validated module")
        return subprocess.CompletedProcess(command, 0, stdout="test-fake\n", stderr="")

    def build(self):
        with mock.patch.object(BUILDER_MODULE.subprocess, "run", side_effect=self.fake_tool):
            return BUILDER_MODULE.build(self.output, "fake-zig", "fake-node")

    def fail_second_replace(self):
        replace = os.replace
        count = 0

        def injected(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("injected second replace failure")
            return replace(source, destination)
        return mock.patch.object(BUILDER_MODULE.os, "replace", side_effect=injected)

    def test_manifest_directory_does_not_replace_prior_module(self):
        self.manifest.unlink()
        self.manifest.mkdir()
        (self.manifest / "unrelated.txt").write_text("keep")
        with self.assertRaises((OSError, RuntimeError)):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"previous module")
        self.assertEqual((self.manifest / "unrelated.txt").read_text(), "keep")

    def test_second_replace_failure_restores_existing_pair(self):
        with self.fail_second_replace(), self.assertRaises(BUILDER_MODULE.InstallationError):
            self.build()
        self.assertEqual(self.output.read_bytes(), b"previous module")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")
        self.assertEqual(list(self.directory.glob("live-wasm-recovery-*")), [])

    def test_second_replace_failure_removes_only_new_module(self):
        self.output.unlink()
        self.manifest.unlink()
        unrelated = self.directory / "unrelated.txt"
        unrelated.write_text("keep")
        with self.fail_second_replace(), self.assertRaises(BUILDER_MODULE.InstallationError):
            self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertEqual(list(self.directory.glob("live-wasm-recovery-*")), [])

    def test_success_replaces_both_files_and_removes_backups(self):
        result = self.build()
        self.assertEqual(self.output.read_bytes(), b"new validated module")
        self.assertEqual(json.loads(self.manifest.read_text()), result)
        self.assertEqual(result["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(list(self.directory.glob("live-wasm-recovery-*")), [])

    def test_source_change_during_compile_cannot_be_labeled_with_new_source_hashes(self):
        source_root = self.directory / "source"
        for name in (*BUILDER_MODULE.SOURCES, *BUILDER_MODULE.HEADERS, *BUILDER_MODULE.PROVENANCE):
            target = source_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((BUILDER_MODULE.ROOT / name).read_bytes())
        def mutate_source(command, **kwargs):
            result = self.fake_tool(command, **kwargs)
            if command[1] == "cc":
                (source_root / "sim/cx_circuit.c").write_bytes(b"changed during compile")
            return result
        with mock.patch.object(BUILDER_MODULE, "ROOT", source_root), \
                mock.patch.object(BUILDER_MODULE.subprocess, "run", side_effect=mutate_source):
            with self.assertRaisesRegex(RuntimeError, "source.*changed"):
                BUILDER_MODULE.build(self.output, "fake-zig", "fake-node")
        self.assertEqual(self.output.read_bytes(), b"previous module")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")

    def test_rollback_failure_keeps_both_prior_files_for_recovery(self):
        replace = os.replace
        count = 0

        def injected(source, destination):
            nonlocal count
            count += 1
            if count >= 2:
                raise OSError("injected install and rollback failures")
            return replace(source, destination)

        with mock.patch.object(BUILDER_MODULE.os, "replace", side_effect=injected):
            with self.assertRaises(BUILDER_MODULE.InstallationError) as failure:
                self.build()
        backups = list(self.directory.glob("live-wasm-recovery-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("rollback failed", str(failure.exception))
        self.assertIn(str(backups[0]), str(failure.exception))
        self.assertEqual((backups[0] / self.output.name).read_bytes(), b"previous module")
        self.assertEqual((backups[0] / self.manifest.name).read_bytes(), b"previous manifest")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")

    def test_cli_identifies_installation_failure_after_validation(self):
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", [str(BUILDER), "--zig", "fake-zig"]):
            with mock.patch.object(BUILDER_MODULE, "build", side_effect=
                                   BUILDER_MODULE.InstallationError("validated; install failed")):
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as failure:
                    BUILDER_MODULE.main()
        self.assertEqual(failure.exception.code, 1)
        self.assertIn("Live Wasm installation failed", stderr.getvalue())
        self.assertNotIn("not validated", stderr.getvalue())

    @unittest.skipIf(os.name == "nt", "requires unprivileged symlink creation")
    def test_output_symlink_is_rejected_without_following_it(self):
        unrelated = self.directory / "unrelated.wasm"
        unrelated.write_bytes(b"unrelated module")
        self.output.unlink()
        self.output.symlink_to(unrelated)
        with self.assertRaises((OSError, RuntimeError)):
            self.build()
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(unrelated.read_bytes(), b"unrelated module")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")

    @unittest.skipIf(os.name == "nt", "requires unprivileged symlink creation")
    def test_manifest_symlink_is_rejected_without_replacing_it(self):
        unrelated = self.directory / "unrelated.json"
        unrelated.write_bytes(b"unrelated manifest")
        self.manifest.unlink()
        self.manifest.symlink_to(unrelated)
        with self.assertRaises((OSError, RuntimeError)):
            self.build()
        self.assertTrue(self.manifest.is_symlink())
        self.assertEqual(unrelated.read_bytes(), b"unrelated manifest")
        self.assertEqual(self.output.read_bytes(), b"previous module")

    @unittest.skipIf(os.name == "nt", "requires unprivileged symlink creation")
    def test_rollback_never_replaces_an_unrelated_new_symlink(self):
        unrelated = self.directory / "unrelated.wasm"
        unrelated.write_bytes(b"unrelated module")
        replace = os.replace
        count = 0

        def injected(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                self.output.unlink()
                self.output.symlink_to(unrelated)
                raise OSError("concurrent path substitution")
            return replace(source, destination)

        with mock.patch.object(BUILDER_MODULE.os, "replace", side_effect=injected):
            with self.assertRaises(BUILDER_MODULE.InstallationError) as failure:
                self.build()
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(unrelated.read_bytes(), b"unrelated module")
        self.assertEqual(self.manifest.read_bytes(), b"previous manifest")
        self.assertIn("rollback failed", str(failure.exception))
        backups = list(self.directory.glob("live-wasm-recovery-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / self.output.name).read_bytes(), b"previous module")


if __name__ == "__main__":
    unittest.main()
