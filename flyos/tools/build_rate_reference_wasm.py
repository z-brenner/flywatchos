#!/usr/bin/env python3
"""Build the independent, host-only source-equation reference as bounded Wasm.

No source noise/spike-input pipeline, watch target, WASI host or installation.
Reuses the legacy builder's checked paired-file installer, without modifying it.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
_HELPER_SPEC=importlib.util.spec_from_file_location('rate_reference_install_helper',ROOT/'tools/build_live_wasm.py')
_HELPER=importlib.util.module_from_spec(_HELPER_SPEC)
_HELPER_SPEC.loader.exec_module(_HELPER)
InstallationError=_HELPER.InstallationError
destination_identity=_HELPER.destination_identity
install_pair=_HELPER.install_pair
find_zig=_HELPER.find_zig
SOURCES=('sim/rate_reference.c',)
HEADERS=('sim/rate_reference.h','sim/rate_reference_connectivity.inc')
EXPORTS=('reset','set_stimulus','step','state','transfer','unit_count','epoch','time_ms','dt_ms',
         'stimulus_angle','stimulus_cue','stimulus_turn')
PROVENANCE=('sim/rate_reference_model.json','tools/generate_rate_reference.py',
            'tools/generate_cx_data.py','tools/build_rate_reference_wasm.py','tools/build_live_wasm.py',
            'sim/data/pisokas2020/pisokas2020_cx60_provenance.json',
            'sim/data/pisokas2020/pisokas2020_cx60_edges.csv',
            'sim/data/pisokas2020/pisokas2020_cx60_nodes.json',
            'sim/data/pisokas2020/connectivity_matrix_drosophila_mine_case_5_9cols_labels1.mat',
            'sim/data/pisokas2020/collect_stats_long_run.m','sim/data/pisokas2020/PBexperimentModified.m',
            'sim/data/pisokas2020/flyLI2.m','sim/data/pisokas2020/flyLIF2.m','sim/data/pisokas2020/LICENSE')
MEMORY_BYTES=131072
MAX_MODULE_BYTES=4*1024*1024
MAX_MANIFEST_BYTES=128*1024
VALIDATION_TIMEOUT_SECONDS=30
VALIDATOR=r"""
const fs=require('node:fs'),assert=require('node:assert/strict');
const mod=new WebAssembly.Module(fs.readFileSync(process.argv[1]));
assert.deepEqual(WebAssembly.Module.imports(mod),[]);
const names=JSON.parse(process.argv[2]).map(x=>'fly_rate_'+x);
assert.deepEqual(WebAssembly.Module.exports(mod).map(x=>x.name).sort(),[...names,'memory','_initialize'].sort());
const api=new WebAssembly.Instance(mod,{}).exports; api._initialize();
assert.equal(api.memory.buffer.byteLength,Number(process.argv[3]));
assert.throws(()=>api.memory.grow(1));
api.fly_rate_reset(); assert.equal(api.fly_rate_unit_count(),60);
assert.equal(api.fly_rate_dt_ms(),.1); assert.equal(api.fly_rate_epoch(),0);
const pointer=api.fly_rate_state(); assert(pointer>=0 && pointer%8===0 && pointer+480<=api.memory.buffer.byteLength);
let state=()=>Array.from(new Float64Array(api.memory.buffer,pointer,60));
assert(state().every(x=>x===0));
assert.equal(api.fly_rate_set_stimulus(90,200,0),1); assert.equal(api.fly_rate_step(1),1);
assert.equal(api.fly_rate_epoch(),1); assert.equal(api.fly_rate_time_ms(),.1);
assert(Math.abs(state()[36]-.03)<1e-14); assert.equal(state()[0],0);
assert.equal(api.fly_rate_set_stimulus(NaN,0,0),0); assert.equal(api.fly_rate_set_stimulus(0,Infinity,0),0);
assert.equal(api.fly_rate_step(NaN),0); assert.equal(api.fly_rate_step(1001),0);
assert.equal(api.fly_rate_step(1.5),0); assert.equal(api.fly_rate_epoch(),1);
assert.equal(api.fly_rate_step(1000),1); assert(state().every(Number.isFinite));
assert(state().some(x=>x<0)); assert.equal(api.fly_rate_state(),pointer);
api.fly_rate_reset(); assert(state().every(x=>x===0));
"""


def current_source_hashes() -> dict[str, str]:
    """Use the producer's complete allowlist, never paths from a sidecar."""
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (*SOURCES, *HEADERS, *PROVENANCE)}


def verified_artifact(wasm: Path, node: str = "node") -> tuple[bytes, dict, str]:
    """Read one attributed module/manifest snapshot and fail closed on drift.

    This is local provenance consistency, not independent compiler attestation
    or protection against a deliberately forged module plus forged manifest.
    Node validates the exact returned bytes, not a potentially replaced path.
    """
    with wasm.open("rb") as file:
        data = file.read(MAX_MODULE_BYTES + 1)
    if not data.startswith(b"\x00asm\x01\x00\x00\x00") or len(data) > MAX_MODULE_BYTES:
        raise ValueError("invalid WebAssembly module header or size")
    sidecar = wasm.with_suffix(wasm.suffix + ".json")
    instruction = "Rebuild the module and adjacent manifest with build_rate_reference_wasm.py."
    try:
        with sidecar.open("rb") as file:
            manifest_bytes = file.read(MAX_MANIFEST_BYTES + 1)
    except OSError as error:
        raise ValueError(f"Missing or unreadable WebAssembly manifest. {instruction}") from error
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Oversized WebAssembly manifest. {instruction}")

    def unique_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate manifest key")
            value[key] = item
        return value

    def finite_json_only(value):
        raise ValueError(f"non-finite JSON constant in manifest: {value}")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite JSON number in manifest")
        return number

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=unique_keys,
                              parse_constant=finite_json_only, parse_float=finite_float)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError(f"Malformed WebAssembly manifest. {instruction}") from error
    if (not isinstance(manifest, dict) or type(manifest.get("schema")) is not int
            or manifest.get("schema") != 1 or manifest.get("scope") != "host-only-source-equation-reference"
            or manifest.get("hardware_verified") is not False
            or type(manifest.get("module_bytes")) is not int or manifest["module_bytes"] != len(data)
            or manifest.get("sha256") != hashlib.sha256(data).hexdigest()
            or type(manifest.get("memory_bytes")) is not int or manifest["memory_bytes"] != MEMORY_BYTES
            or manifest.get("imports") != []
            or manifest.get("exports") != ["fly_rate_" + name for name in EXPORTS]
            or manifest.get("compiler") != "Zig"
            or not isinstance(manifest.get("compiler_version"), str)
            or not 1 <= len(manifest["compiler_version"]) <= 128
            or not isinstance(manifest.get("build_command"), list)
            or not 1 <= len(manifest["build_command"]) <= 256
            or any(not isinstance(part, str) or not 1 <= len(part) <= 4096 for part in manifest["build_command"])):
        raise ValueError(f"WebAssembly manifest identity mismatch. {instruction}")
    expected_sources = current_source_hashes()
    if manifest.get("source_sha256") != expected_sources:
        raise ValueError(f"WebAssembly manifest source identity is stale or incomplete. {instruction}")
    # Bound execution and validate an owned copy of the bytes later embedded.
    # A source-path swap during validation cannot silently change the artifact.
    with tempfile.TemporaryDirectory(prefix="rate-wasm-identity-") as temporary:
        snapshot = Path(temporary) / "snapshot.wasm"
        snapshot.write_bytes(data)
        subprocess.run([node, "-e", VALIDATOR, str(snapshot), json.dumps(EXPORTS), str(MEMORY_BYTES)],
                       check=True, capture_output=True, text=True, timeout=VALIDATION_TIMEOUT_SECONDS)
    if current_source_hashes() != expected_sources:
        raise ValueError(f"WebAssembly source identity changed during validation. {instruction}")
    return data, manifest, hashlib.sha256(manifest_bytes).hexdigest()



def build(output: Path, zig: str, node: str) -> dict:
    # resolve() would silently follow and overwrite a destination symlink.
    output = Path(os.path.abspath(output))
    destination_identity(output)
    destination_identity(output.with_suffix(output.suffix + ".json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "tools/generate_rate_reference.py"), "--check"],
                   check=True, capture_output=True, text=True)
    source_hashes = current_source_hashes()
    environment = dict(os.environ)
    # Explicit caches keep the isolated compiler away from read-only home dirs.
    environment.setdefault("ZIG_GLOBAL_CACHE_DIR", str(output.parent / ".zig-cache-global"))
    environment.setdefault("ZIG_LOCAL_CACHE_DIR", str(output.parent / ".zig-cache-local"))
    version = subprocess.run([zig, "version"], check=True, capture_output=True,
                             text=True, env=environment).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="rate-wasm-", dir=output.parent) as temporary:
        wasm = Path(temporary) / "flyos-rate-reference.wasm"
        command = [
            zig, "cc", "-target", "wasm32-wasi", "-mexec-model=reactor",
            "-nostdlib", "-lc", "-lm", "-ffp-contract=off", "-std=c11", "-O2", "-Wall", "-Wextra",
            "-Wpedantic", "-Werror", "-DFLY_NEURAL_SPECIMEN_HOST_PREVIEW=1",
            "-I", str(ROOT), *(str(ROOT / path) for path in SOURCES),
            "-Wl,--no-entry", "-Wl,--export-memory", "-Wl,--strip-all",
            "-Wl,-z,stack-size=32768", f"-Wl,--initial-memory={MEMORY_BYTES}",
            f"-Wl,--max-memory={MEMORY_BYTES}",
            *(f"-Wl,--export=fly_rate_{name}" for name in EXPORTS), "-o", str(wasm),
        ]
        subprocess.run(command, check=True, env=environment)
        subprocess.run([node, "-e", VALIDATOR, str(wasm), json.dumps(EXPORTS),
                        str(MEMORY_BYTES)], check=True, timeout=VALIDATION_TIMEOUT_SECONDS)
        data = wasm.read_bytes()
        if current_source_hashes() != source_hashes:
            raise RuntimeError("WebAssembly source identity changed during build; no module or manifest installed")
        manifest = {
            "schema": 1, "scope": "host-only-source-equation-reference", "hardware_verified": False,
            "compiler": "Zig", "compiler_version": version,
            "module_bytes": len(data), "memory_bytes": MEMORY_BYTES, "imports": [],
            "sha256": hashlib.sha256(data).hexdigest(),
            "source_sha256": source_hashes,
            "exports": ["fly_rate_" + name for name in EXPORTS],
            "build_command": ["zig", *command[1:-1], "<output.wasm>"],
        }
        metadata = Path(temporary) / "flyos-rate-reference.wasm.json"
        metadata.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Compile/validation failures never reach installation; installation
        # itself has separate checked rollback and error reporting.
        install_pair(wasm, metadata, output)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "flyos-rate-reference.wasm")
    parser.add_argument("--zig", help="Zig executable (default: PATH or installed ziglang package)")
    parser.add_argument("--node", default="node", help="Node executable used for validation")
    args = parser.parse_args()
    try:
        manifest = build(args.output, find_zig(args.zig), args.node)
    except InstallationError as error:
        parser.exit(1, f"Rate reference Wasm installation failed: {error}\n")
    except (OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Rate reference Wasm build failed: {error}\n")
    print(f"Validated {args.output}: {manifest['module_bytes']} bytes, no imports, "
          f"{MEMORY_BYTES} bytes fixed memory, Zig {manifest['compiler_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
