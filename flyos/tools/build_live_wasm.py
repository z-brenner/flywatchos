#!/usr/bin/env python3
"""Build/validate the offline HOST-ONLY C laboratory as import-free WebAssembly.

Tested toolchain, installed separately (never installed by this script):
  python -m venv /tmp/flywatchos-venv
  /tmp/flywatchos-venv/bin/python -m pip install ziglang==0.14.1
  /tmp/flywatchos-venv/bin/python flyos/tools/build_live_wasm.py

Alternatively pass --zig /path/to/zig. Node is required to validate the actual
module, exports, memory bound and execution before publishing any output.
The wasm32-wasi reactor ABI supplies static C runtime helpers, but the emitted
module MUST have no imports: no WASI host, filesystem, clock or network exists.
No firmware tooling, device path, target payload or packaging is involved.

Installation checks both destinations and rolls back the module if installing
its manifest fails. The pair is NOT atomic for concurrent readers; do not run
concurrent writers, and readers must verify the manifest's module hash.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "sim/live_bridge.c", "sim/host_policy.c", "sim/cx_circuit.c", "fly/brain64.c",
    "display/neural_specimen.c",
)
HEADERS = (
    "sim/live_bridge.h", "sim/host_policy.h", "sim/cx_circuit.h", "sim/cx_connectivity.inc", "fly/brain64.h",
    "display/neural_specimen.h",
)
EXPORTS = (
    "reset", "event", "set_context", "set_sensors", "step", "pixels",
    "activations", "pixel_count", "neuron_count", "route", "held", "active",
    "owner", "pulse", "delivered_pulse", "buttons", "state", "epoch",
    "view", "usb", "ready", "valid_mask", "rendered", "reset_model", "model",
    "model_node_count", "set_stimulus", "stimulus_angle", "stimulus_strength",
    "stimulus_turn", "readout_heading", "readout_strength", "edge_count",
    "edge_source", "edge_target", "edge_raw_weight", "edge_denominator",
    "edge_sign", "edge_weight_q",
)
PROVENANCE = ("sim/circuit_models.json", "sim/data/pisokas2020/pisokas2020_cx60_provenance.json",
              "sim/data/pisokas2020/pisokas2020_cx60_edges.csv",
              "sim/data/pisokas2020/pisokas2020_cx60_nodes.json",
              "sim/data/pisokas2020/connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat",
              "sim/data/pisokas2020/LICENSE")
MEMORY_BYTES = 131072


class InstallationError(RuntimeError):
    """Destination preflight or installation failed, separately from validation."""


def destination_identity(path: Path) -> tuple | None:
    """Accept only absent paths or ordinary files, never follow a final symlink."""
    try:
        value = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(value.st_mode):
        raise InstallationError(f"Destination is not a regular file: {path}; left unchanged")
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_mode)


def install_pair(wasm: Path, metadata: Path, output: Path) -> None:
    """Install a validated pair with rollback, not two-file reader atomicity."""
    manifest = output.with_suffix(output.suffix + ".json")
    previous = (destination_identity(output), destination_identity(manifest))
    new_identity = destination_identity(wasm)
    if new_identity is None or destination_identity(metadata) is None:
        raise InstallationError("Validated installation sources are missing")
    recovery = Path(tempfile.mkdtemp(prefix="live-wasm-recovery-", dir=output.parent))
    preserve_recovery = False
    module_installed = False
    try:
        # Copies preserve both prior files while installation is attempted.
        for path, identity in zip((output, manifest), previous):
            if identity is not None:
                shutil.copy2(path, recovery / path.name, follow_symlinks=False)
        if (destination_identity(output), destination_identity(manifest)) != previous:
            raise InstallationError("Destinations changed during staging; no files installed")
        try:
            os.replace(wasm, output)
            module_installed = True
            # A newly introduced unrelated file/symlink is not ours to replace.
            if destination_identity(manifest) != previous[1]:
                raise InstallationError("Manifest destination changed during installation")
            os.replace(metadata, manifest)
        except (OSError, InstallationError) as error:
            if module_installed:
                try:
                    # Do not remove or overwrite an unrelated concurrent change.
                    if destination_identity(output) != new_identity:
                        raise InstallationError("Module destination changed before rollback")
                    if previous[0] is None:
                        output.unlink()
                    else:
                        os.replace(recovery / output.name, output)
                except (OSError, InstallationError) as rollback_error:
                    preserve_recovery = True
                    raise InstallationError(
                        f"Validated module installation failed: {error}; rollback failed: "
                        f"{rollback_error}. Prior files retained at {recovery}") from error
            raise InstallationError(
                f"Validated module installation failed: {error}; prior output restored "
                "(or newly created module removed)") from error
    except OSError as error:
        raise InstallationError(f"Could not stage installation backups: {error}") from error
    finally:
        if not preserve_recovery:
            try:
                shutil.rmtree(recovery)
            except OSError as error:
                raise InstallationError(
                    f"Backup cleanup failed after installation attempt: {error}; "
                    f"inspect output pair and recovery directory {recovery}") from error

VALIDATOR = r"""
const fs = require('node:fs');
const assert = require('node:assert/strict');
const module_ = new WebAssembly.Module(fs.readFileSync(process.argv[1]));
assert.deepEqual(WebAssembly.Module.imports(module_), [], 'unexpected host imports');
const api = new WebAssembly.Instance(module_).exports;
for (const name of JSON.parse(process.argv[2]))
  assert.equal(typeof api['fly_lab_' + name], 'function', 'missing export: ' + name);
assert.equal(api.memory.buffer.byteLength, Number(process.argv[3]));
assert.throws(() => api.memory.grow(1), RangeError, 'memory must have a fixed maximum');
api.fly_lab_reset(0x245f1a5);
assert.equal(api.fly_lab_pixel_count(), 57600);
assert.equal(api.fly_lab_neuron_count(), 64);
const pixels = api.fly_lab_pixels(), neurons = api.fly_lab_activations();
assert(pixels >= 0 && pixels + 57600 <= api.memory.buffer.byteLength);
assert(neurons >= 0 && neurons % 2 === 0 && neurons + 128 <= api.memory.buffer.byteLength);
assert.equal(api.fly_lab_epoch(), 0);
api.fly_lab_step();
assert.equal(api.fly_lab_epoch(), 1);
assert.equal(api.fly_lab_view(), 1);
assert.equal(api.fly_lab_rendered(), 1);
assert([...new Uint8Array(api.memory.buffer, pixels, 57600)].every(n => n <= 5));
assert.equal(api.fly_lab_reset_model(1, 123), 1);
assert.equal(api.fly_lab_model_node_count(), 60);
assert.equal(api.fly_lab_edge_count(), 326);
assert.equal(api.fly_lab_edge_source(0), 34);
assert.equal(api.fly_lab_edge_target(0), 0);
assert.equal(api.fly_lab_edge_raw_weight(0), 99.9680554605268);
assert.equal(api.fly_lab_edge_weight_q(0), 1024);
assert.equal(api.fly_lab_set_stimulus(90, 1024, 0), 1);
api.fly_lab_step();
assert.equal(api.fly_lab_readout_heading(), 90);
assert.equal(api.fly_lab_readout_strength(), 2048);
assert.equal(api.fly_lab_pixels(), pixels);
assert.equal(api.fly_lab_activations(), neurons);
assert([...new Int16Array(api.memory.buffer, neurons, 64)].slice(60).every(n => n === 0));
assert.equal(api.fly_lab_reset_model(2, 0), 0);
assert.equal(api.fly_lab_model(), 1);
api.fly_lab_reset(123);
assert.equal(api.fly_lab_model(), 0);
"""


def find_zig(explicit: str | None) -> str:
    if explicit:
        return explicit
    executable = shutil.which("zig")
    if executable:
        return executable
    spec = importlib.util.find_spec("ziglang")
    if spec and spec.origin:
        executable = Path(spec.origin).parent / ("zig.exe" if os.name == "nt" else "zig")
        if executable.is_file():
            return str(executable)
    raise RuntimeError("Zig not found; install ziglang==0.14.1 in a separate venv or pass --zig")


def build(output: Path, zig: str, node: str) -> dict:
    # resolve() would silently follow and overwrite a destination symlink.
    output = Path(os.path.abspath(output))
    destination_identity(output)
    destination_identity(output.with_suffix(output.suffix + ".json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "tools/generate_cx_data.py"), "--check"],
                   check=True, capture_output=True, text=True)
    environment = dict(os.environ)
    # Explicit caches keep the isolated compiler away from read-only home dirs.
    environment.setdefault("ZIG_GLOBAL_CACHE_DIR", str(output.parent / ".zig-cache-global"))
    environment.setdefault("ZIG_LOCAL_CACHE_DIR", str(output.parent / ".zig-cache-local"))
    version = subprocess.run([zig, "version"], check=True, capture_output=True,
                             text=True, env=environment).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="live-wasm-", dir=output.parent) as temporary:
        wasm = Path(temporary) / "flyos-live.wasm"
        command = [
            zig, "cc", "-target", "wasm32-wasi", "-mexec-model=reactor",
            "-nostdlib", "-lc", "-std=c11", "-O2", "-Wall", "-Wextra",
            "-Wpedantic", "-Werror", "-DFLY_NEURAL_SPECIMEN_HOST_PREVIEW=1",
            "-I", str(ROOT), *(str(ROOT / path) for path in SOURCES),
            "-Wl,--no-entry", "-Wl,--export-memory", "-Wl,--strip-all",
            "-Wl,-z,stack-size=32768", f"-Wl,--initial-memory={MEMORY_BYTES}",
            f"-Wl,--max-memory={MEMORY_BYTES}",
            *(f"-Wl,--export=fly_lab_{name}" for name in EXPORTS), "-o", str(wasm),
        ]
        subprocess.run(command, check=True, env=environment)
        subprocess.run([node, "-e", VALIDATOR, str(wasm), json.dumps(EXPORTS),
                        str(MEMORY_BYTES)], check=True)
        data = wasm.read_bytes()
        manifest = {
            "schema": 1, "scope": "host-only-synthetic", "hardware_verified": False,
            "compiler": "Zig", "compiler_version": version,
            "module_bytes": len(data), "memory_bytes": MEMORY_BYTES, "imports": [],
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                              for p in (*SOURCES, *HEADERS, *PROVENANCE)},
            "exports": ["fly_lab_" + name for name in EXPORTS],
            "build_command": ["zig", *command[1:-1], "<output.wasm>"],
        }
        metadata = Path(temporary) / "flyos-live.wasm.json"
        metadata.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Compile/validation failures never reach installation; installation
        # itself has separate checked rollback and error reporting.
        install_pair(wasm, metadata, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "flyos-live.wasm")
    parser.add_argument("--zig", help="Zig executable (default: PATH or installed ziglang package)")
    parser.add_argument("--node", default="node", help="Node executable used for validation")
    args = parser.parse_args()
    try:
        manifest = build(args.output, find_zig(args.zig), args.node)
    except InstallationError as error:
        parser.exit(1, f"Live Wasm installation failed: {error}\n")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Live Wasm build failed: {error}\n")
    print(f"Validated {args.output}: {manifest['module_bytes']} bytes, no imports, "
          f"{MEMORY_BYTES} bytes fixed memory, Zig {manifest['compiler_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
