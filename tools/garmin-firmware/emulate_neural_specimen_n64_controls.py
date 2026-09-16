#!/usr/bin/env python3
"""Build-gate and Unicorn proof for the offline FR245 13.70 N64 target."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zlib
from typing import Any

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_LITTLE_ENDIAN
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "flyos/target/fr245_1370_neural_specimen_n64_controls"
DEFAULT_BUILD = TARGET / "build"
ALLOCATION = ROOT / "artifacts/analysis/fr245-1370-n64-allocation.json"
RUNTIME_STATE = ROOT / "artifacts/firmware/analysis/fr245-1370-runtime-state.json"
IMAGE = ROOT / "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin"
IMAGE_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
RUNTIME_SHA256 = "53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d"
ELF_NAME = "fr245-1370-neural-specimen-n64-controls.elf"
ARTIFACT_PREFIX = "fr245-1370-n64-controls"
HOOK, KEY_HOOK, PRIMARY, SECONDARY = 0x9A20, 0xFA48, 0x1F6000, 0x1FA400
DIRTY, DISPATCH = 0xF2E8, 0xE1A4
VIEW_FIND, VIEW_FIRST = 0x5306C, 0x530CC
VIEW_CALLBACK, VIEW_ROOT = 0x5ADF5, 0x20003E84
FRAMEBUFFER, FB_SIZE, GUARD = 0x1FFDE6E8, 57600, 64
STACK_BASE, STACK_POINTER, STACK_LIMIT = 0x20017000, 0x20018000, 384
GPIOA, GPIOC, GPIOD = 0x400FF010, 0x400FF090, 0x400FF0D0
RTC_SECONDS, RTC_PRESCALER = 0x4003D000, 0x4003D004
BATTERY, USB_MS = 0x1FFCCCD8, 0x1FFC6F25
KEY_WORKSPACE = 0x1FFDBBC8
KEY_PADS = tuple(KEY_WORKSPACE + key * 0x38 + 0x36 for key in range(5))
KEY_IDLE, KEY_OWNED, KEY_PULSE = 0xFF00, 0x5EA1, 0x5DA2
BUTTONS = ((GPIOC, 0x800), (GPIOD, 0x400), (GPIOD, 2),
           (GPIOA, 0x100000), (GPIOA, 0x400000))
CALLEE = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
          UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)
ARGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
INSTRUCTION_CAP = 3_000_000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_elf(path: Path) -> tuple[dict, dict]:
    data = path.read_bytes()
    require(data[:7] == b"\x7fELF\x01\x01\x01", "expected little-endian ELF32")
    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    require(header[0] == 2 and header[1] == 40, "expected ARM executable")
    section_offset, section_size, section_count, strings_index = header[5], *header[10:13]
    raw = [struct.unpack_from("<10I", data, section_offset + i * section_size)
           for i in range(section_count)]
    strings_section = raw[strings_index]
    names = data[strings_section[4]:strings_section[4] + strings_section[5]]

    def cstring(table: bytes, offset: int) -> str:
        return table[offset:table.index(0, offset)].decode("ascii")

    sections = {}
    for item in raw:
        name = cstring(names, item[0])
        sections[name] = {"type": item[1], "flags": item[2], "address": item[3],
                          "size": item[5], "data": data[item[4]:item[4] + item[5]]}
    symbols = {}
    for section in raw:
        if section[1] != 2:
            continue
        table = raw[section[6]]
        strings = data[table[4]:table[4] + table[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name, value, size, info, _other, index = struct.unpack_from("<IIIBBH", data, offset)
            if not name:
                continue
            symbol = cstring(strings, name)
            require(index != 0, f"undefined ELF symbol: {symbol}")
            symbols[symbol] = {"address": value & ~1 if info & 15 == 2 else value,
                               "size": size, "kind": info & 15, "section": index}
    return sections, symbols


def decode_hook(data: bytes) -> int:
    instructions = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(data, HOOK))
    require(len(data) == 4 and len(instructions) == 1 and instructions[0].mnemonic == "bl",
            "hook must be exactly one four-byte Thumb BL")
    return int(instructions[0].op_str.lstrip("#"), 0)


def decode_key_hook(data: bytes) -> int:
    instructions = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(data, KEY_HOOK))
    require(len(data) == 6 and len(instructions) == 2,
            "key hook must be exactly Thumb B.W plus NOP")
    require(instructions[0].mnemonic in ("b", "b.w") and
            instructions[1].mnemonic == "nop", "wrong key hook instructions")
    return int(instructions[0].op_str.lstrip("#"), 0)


def evidence_gate() -> dict:
    allocation_bytes = ALLOCATION.read_bytes()
    allocation = json.loads(allocation_bytes)
    require(sha256(RUNTIME_STATE.read_bytes()) == RUNTIME_SHA256, "runtime-state hash mismatch")
    runtime = json.loads(RUNTIME_STATE.read_bytes())
    require(sha256(IMAGE.read_bytes()) == IMAGE_SHA256, "firmware image hash mismatch")
    require(allocation == {
        "schema": "flyos.fr245.n64-allocation.v1", "analysis_mode": "offline_only",
        "firmware_image_sha256": IMAGE_SHA256, "runtime_state_sha256": RUNTIME_SHA256,
        "link_and_emulate_allowed": True, "packaging_allowed": False, "live_write_allowed": False,
        "hook": {"start": "0x00009a20", "end": "0x00009a23", "length": 4},
        "primary": {"start": "0x001f6000", "end": "0x001f63fe", "length": 1023},
        "repair_byte": "0x001f63ff",
        "secondary": {"start": "0x001fa400", "end": "0x001fabff", "length": 2048},
        "total_usable_bytes": 3071, "third_allocation_used": False,
        "source_evidence": ["artifacts/analysis/fr245-1370-second-allocation.json",
                            ".superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-4-allocation-scout.md"],
        "constraints": {"stack_bytes_maximum": 384, "pixels": [0, 12, 42, 51, 56, 63],
                        "writable_static_storage": False,
                        "allowed_target_writes": ["framebuffer", "stack"]}},
        "allocation evidence is not canonical")
    signals = runtime["signals"]
    require(runtime["image"]["sha256"] == IMAGE_SHA256, "runtime image mismatch")
    require(signals["watch_face_active"]["source"]["callable_addresses"] ==
            ["0x0005306d", "0x000530cd"], "wrong watch-face callables")
    require(signals["watch_face_active"]["source"]["allowed_node_offsets"] ==
            ["0x04", "0x08", "0x50"], "wrong node allowlist")
    require(signals["battery_percent"]["status"] == "available" and
            signals["usb_mass_storage"]["status"] == "available", "approved inputs unavailable")
    for name in ("usb_attached", "charging", "update_pending", "heart_rate_bpm", "motion",
                 "raw_framebuffer_color_mapping"):
        require(signals[name]["status"] == "unavailable", f"unexpected signal promotion: {name}")
    require(runtime["target_palette_status"] == "available" and
            runtime["target_palette"]["roles"] == {
                "background": {"native_byte": "0x00", "rgb": "#000000"},
                "excitatory": {"native_byte": "0x0c", "rgb": "#00FF00"},
                "inhibitory": {"native_byte": "0x33", "rgb": "#FF00FF"},
                "saturated": {"native_byte": "0x38", "rgb": "#FFAA00"},
                "scaffold": {"native_byte": "0x2a", "rgb": "#AAAAAA"},
                "text": {"native_byte": "0x3f", "rgb": "#FFFFFF"}},
            "reviewed target palette mismatch")
    return {"allocation_sha256": sha256(allocation_bytes), "runtime_state_sha256": RUNTIME_SHA256}


def stack_audit(build: Path, symbols: dict) -> dict:
    frames = {"flyos_hook_patch": 0, "flyos_key_hook_patch": 0,
              "flyos_key_pass": 12}
    for path in sorted(build.glob("*.su")):
        for line in path.read_text().splitlines():
            location, count, kind = line.split("\t")
            require(kind == "static", f"dynamic stack frame: {line}")
            frames[location.rsplit(":", 1)[1]] = int(count)
    functions = {name: item for name, item in symbols.items() if item["kind"] == 2}
    for name in functions:
        if name not in frames and re.sub(r"\.\d+$", "", name) in frames:
            frames[name] = frames[re.sub(r"\.\d+$", "", name)]
    require(set(functions) <= set(frames), "missing .su frame for linked function")
    starts = {item["address"]: name for name, item in functions.items()}
    graph = {name: set() for name in functions}
    external, cross = [], []
    current = None
    listing = (build / "fr245-1370-neural-specimen-n64-controls.disassembly.txt").read_text()
    for line in listing.splitlines():
        label = re.match(r"^([0-9a-f]+) <([^>]+)>:", line)
        if label:
            current = label[2] if label[2] in functions else None
            continue
        ins = re.match(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4,8}\s+)+([a-z][a-z0-9.]*)\s+(.+)", line)
        if not current or not ins:
            continue
        address, mnemonic, operands = int(ins[1], 16), ins[2], ins[3]
        if mnemonic in ("blx", "bx") and not operands.startswith("lr"):
            external.append({"address": address, "function": current,
                             "instruction": f"{mnemonic} {operands.strip()}"})
        target = re.match(r"([0-9a-f]+) <", operands)
        if mnemonic.startswith("b") and target:
            destination = int(target[1], 16)
            if destination in starts and starts[destination] != current:
                graph[current].add(starts[destination])
                if ((PRIMARY <= address < 0x1F63FF and SECONDARY <= destination < 0x1FAC00) or
                    (SECONDARY <= address < 0x1FAC00 and PRIMARY <= destination < 0x1F63FF)):
                    cross.append([address, destination])
            elif mnemonic == "bl":
                require(destination in starts, f"unknown direct callee: {line}")
    require(set(item["function"] for item in external) <=
            {"n64_overlay_then_flush", "flyos_key_event", "flyos_key_pass",
             "request_redraw"},
            "unexpected indirect transfer owner")

    def bound(name: str, active: tuple[str, ...] = ()) -> tuple[int, list[str]]:
        require(name not in active, "recursive target call graph")
        children = [bound(child, active + (name,)) for child in graph[name]]
        deepest, chain = max(children, default=(0, []), key=lambda pair: pair[0])
        return frames[name] + deepest, [name] + chain

    candidates = [bound("flyos_hook_patch"), bound("flyos_key_hook_patch")]
    maximum, chain = max(candidates, key=lambda pair: pair[0])
    require(maximum <= STACK_LIMIT, f"stack bound {maximum} exceeds {STACK_LIMIT}")
    return {"stack_bound_bytes": maximum, "maximum_allowed_bytes": STACK_LIMIT,
            "maximum_chain": chain, "frames": frames,
            "call_graph": {key: sorted(value) for key, value in graph.items()},
            "external_transfers": external, "cross_segment_branches": cross}


def clean_oracle_output(build: Path) -> None:
    """Remove only generated oracle output beneath the selected build root."""
    build = build.resolve()
    oracle = (build / "oracle").resolve()
    require(oracle.parent == build and oracle.name == "oracle", "unsafe oracle cleanup path")
    if not oracle.exists():
        return
    require(not oracle.is_symlink(), "refuse symlinked oracle directory")
    entries = sorted(oracle.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in entries:
        require(oracle in path.resolve().parents, "oracle entry escaped build root")
        require(not path.is_symlink(), "refuse symlinked oracle entry")
        if path.is_dir(): path.rmdir()
        else: path.unlink()
    oracle.rmdir()


def assert_build_clean(build: Path, manifest: dict) -> None:
    expected = set(manifest["files"]) | {"manifest.json", "SHA256SUMS.txt"}
    observed = {str(path.relative_to(build)).replace("\\", "/")
                for path in build.rglob("*") if path.is_file()}
    require(observed == expected,
            f"untracked generated build files: extra={sorted(observed-expected)} missing={sorted(expected-observed)}")
    require(not (build / "oracle/tests").exists(), "legacy shared test-oracle directory exists")


@lru_cache(maxsize=64)
def host_oracle(build: Path, tick: int, buttons: int, battery_valid: int,
                battery: int, usb_ms: int, retained: bool = False) -> dict:
    fixture = f"t{tick:08x}-k{buttons:02x}-b{battery_valid}{battery:03d}-u{usb_ms}"
    context = None
    if retained:
        directory = build / "oracle" / "retained" / fixture
        directory.mkdir(parents=True, exist_ok=True)
    else:
        context = tempfile.TemporaryDirectory(prefix=f"flyos-n64-oracle-{os.getpid()}-")
        directory = Path(context.name)
    try:
        source, executable, output = directory / "oracle.c", directory / "oracle.exe", directory / "oracle.bin"
        source.write_text('''#include <stdio.h>\n#include <stdlib.h>\n#include "fly/brain64.h"\n#include "display/neural_specimen.h"\nvoid n64_render(unsigned char*,const FlyBrain64*,const FlyBrainInputs*,uint32_t,uint8_t);\nint main(int c,char**v){if(c!=7)return 2;uint32_t t=strtoul(v[1],0,0);FlyBrainInputs i={0};i.buttons=strtoul(v[2],0,0);if(strtoul(v[3],0,0)){i.valid_mask=FLY_BRAIN64_VALID_BATTERY;i.battery_percent=strtoul(v[4],0,0);}uint8_t u=strtoul(v[5],0,0);FlyBrain64 b;static unsigned char tf[57600],sf[57600];fly_brain64_reconstruct(&b,0x46594f53u,t,&i);n64_render(tf,&b,&i,t,u);fly_neural_specimen_render(sf,&b,&i,t);FILE*f=fopen(v[6],"wb");if(!f)return 3;int ok=fwrite(tf,1,sizeof(tf),f)==sizeof(tf)&&fwrite(sf,1,sizeof(sf),f)==sizeof(sf)&&fwrite(&b,1,sizeof(b),f)==sizeof(b);return fclose(f)||!ok?4:0;}\n''', encoding="ascii")
        command = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "flyos"),
                   str(source), str(ROOT / "flyos/fly/brain64.c"),
                   str(ROOT / "flyos/display/neural_specimen.c"), str(TARGET / "renderer.c"),
                   "-Wl,--no-insert-timestamp", "-o", str(executable)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        require(compiled.returncode == 0, "host oracle compile failed: " + compiled.stderr)
        subprocess.run([str(executable), str(tick), str(buttons), str(battery_valid), str(battery),
                        str(usb_ms), str(output)], check=True, capture_output=True)
        data = output.read_bytes()
        require(len(data) == FB_SIZE * 2 + 140, "wrong host oracle length")
        brain = data[FB_SIZE * 2:]
        artifacts = ({str(path.relative_to(build)).replace("\\", "/"): sha256(path.read_bytes())
                      for path in (source, executable, output)} if retained else {})
        return {"target_framebuffer": data[:FB_SIZE], "shared_framebuffer": data[FB_SIZE:FB_SIZE*2],
                "brain": brain, "activation": list(struct.unpack_from("<64h", brain)),
                "artifacts": artifacts}
    finally:
        if context is not None:
            context.cleanup()


def check_build(build: Path = DEFAULT_BUILD) -> dict:
    evidence = evidence_gate()
    clean_oracle_output(build)
    sections, symbols = read_elf(build / ELF_NAME)
    expected = {".hook": (HOOK, 4), ".keyhook": (KEY_HOOK, 6),
                ".primary": (PRIMARY, 0x3FF), ".secondary": (SECONDARY, 0x800)}
    segments = {}
    for name, (start, maximum) in expected.items():
        section = sections[name]
        require(section["address"] == start and 0 < section["size"] <= maximum,
                f"section bound failed: {name}")
        binary = build / f"{name[1:]}.bin"
        require(binary.read_bytes() == section["data"], f"ELF/binary mismatch: {name}")
        segments[name[1:]] = {"start": start, "end": start + section["size"] - 1,
                              "size": section["size"], "sha256": sha256(section["data"])}
    allocated = [name for name, section in sections.items() if section["flags"] & 2 and section["size"]]
    require(set(allocated) == set(expected), f"unexpected allocated sections: {allocated}")
    require(symbols["n64_overlay_then_flush"]["address"] == PRIMARY, "wrong entry address")
    require(decode_hook(sections[".hook"]["data"]) == PRIMARY, "wrong hook target")
    require(decode_key_hook(sections[".keyhook"]["data"]) ==
            symbols["flyos_key_event"]["address"], "wrong key hook target")
    image = IMAGE.read_bytes()
    require(image[KEY_HOOK - 0x3000:KEY_HOOK - 0x3000 + 6] == bytes.fromhex("30b5c0ebc002"),
            "pinned key entry bytes changed")
    require(segments["primary"]["end"] <= 0x1F63FE, "repair byte consumed")
    audit = stack_audit(build, symbols)
    oracle = host_oracle(build, 0x003DA005, 0, 1, 73, 0, retained=True)
    files = [build / ELF_NAME, build / "fr245-1370-neural-specimen-n64-controls.map",
             build / "fr245-1370-neural-specimen-n64-controls.disassembly.txt", build / "symbols.txt",
             build / "hook.bin", build / "keyhook.bin", build / "primary.bin", build / "secondary.bin"]
    files += sorted(build.glob("*.su")) + sorted(build.glob("*.o"))
    files += [build / name for name in oracle["artifacts"]]
    sources = [TARGET / name for name in
               ("hook.S", "overlay.c", "renderer.c", "brain64_packed.c", "linker.ld", "build.ps1")]
    sources += [ROOT / "flyos/fly/brain64.c", ROOT / "flyos/fly/brain64.h",
                ROOT / "flyos/display/neural_specimen.c", ROOT / "flyos/display/neural_specimen.h",
                Path(__file__).resolve(), ALLOCATION, RUNTIME_STATE]
    manifest = {"schema": "flyos.fr245.n64-controls-target.v1", **evidence,
                "link_and_emulate_allowed": True, "packaging_allowed": False,
                "segments": segments, "repair_byte": 0x1F63FF, "stack_audit": audit,
                "symbols": symbols,
                "retained_oracle": {"fixture": "tick=0x003da005 buttons=0 battery=73 usb_ms=0",
                                    "activation_sha256": sha256(oracle["brain"][:128]),
                                    "target_framebuffer_sha256": sha256(oracle["target_framebuffer"]),
                                    "shared_framebuffer_sha256": sha256(oracle["shared_framebuffer"])},
                "files": {str(path.relative_to(build)).replace("\\", "/"): sha256(path.read_bytes())
                          for path in files},
                "sources": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path.read_bytes())
                            for path in sources}}
    manifest_path = build / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    hashes = {**manifest["files"], "manifest.json": sha256(manifest_path.read_bytes())}
    (build / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())), encoding="ascii")
    assert_build_clean(build, manifest)
    return manifest


@dataclass(frozen=True)
class Bundle:
    build: Path
    primary: bytes
    secondary: bytes
    hook: bytes
    keyhook: bytes
    manifest: dict


def load_build(build: Path = DEFAULT_BUILD) -> Bundle:
    manifest = json.loads((build / "manifest.json").read_text())
    evidence_gate()
    for name, digest in manifest["files"].items():
        require(sha256((build / name).read_bytes()) == digest, f"build hash mismatch: {name}")
    for name, digest in manifest["sources"].items():
        require(sha256((ROOT / name).read_bytes()) == digest, f"source hash mismatch: {name}")
    assert_build_clean(build, manifest)
    bundle = Bundle(build, *((build / name).read_bytes() for name in
                             ("primary.bin", "secondary.bin", "hook.bin", "keyhook.bin")), manifest)
    require(decode_hook(bundle.hook) == PRIMARY, "wrong hook target")
    require(decode_key_hook(bundle.keyhook) == bundle.manifest["symbols"]["flyos_key_event"]["address"],
            "wrong key hook target")
    return bundle


def expected_cell(level: int, x: int, y: int) -> set[tuple[int, int]]:
    if level == 0:
        return {(x + 2, y + 2), (x + 3, y + 2)}
    if level == 1:
        return {(x + 2, y + n) for n in range(6)} | {(x + n, y + 2) for n in range(6)}
    if level == 2:
        return ({(x + n, y) for n in range(6)} | {(x + n, y + 5) for n in range(6)} |
                {(x, y + n) for n in range(6)} | {(x + 5, y + n) for n in range(6)})
    return {(x + a, y + b) for a in range(6) for b in range(6)}


def verify_cells(framebuffer: bytes, activation: list[int]) -> int:
    require(len(activation) == 64, "expected 64 activations")
    regions = []
    bases = (93, 93, 89, 89, 89, 89, 93, 93)
    gaps = (7, 7, 8, 8, 8, 8, 7, 7)
    for neuron, value in enumerate(activation):
        row = neuron >> 3
        x, y = bases[row] + (neuron & 7) * gaps[row], 76 + row * 9
        region = {(x + a, y + b) for a in range(6) for b in range(6)}
        require(not any(region & prior for prior in regions), "neuron cells overlap")
        regions.append(region)
        magnitude = abs(value)
        level = 0 if magnitude < 128 else 1 if magnitude < 256 else 2 if magnitude < 512 else 3
        lit = expected_cell(level, x, y)
        role = 0x33 if value < 0 else 0x38 if (neuron < 5 or neuron >= 56) and level == 3 else 0x0C
        for point in region:
            require(framebuffer[point[1] * 240 + point[0]] == (role if point in lit else 0),
                    f"neuron {neuron} direct-cell mismatch at {point}")
    return 64


def vendor_view_oracle(home: str) -> dict[str, Any]:
    """Run only the pinned stock 13.70 walkers as an offline comparison oracle."""
    require(home in {"valid", "empty", "malformed", "cycle", "too_long", "not_home",
                     "hidden_match", "multiple"}, "unknown vendor fixture")
    addresses = [0x20001000 + i * 0x100 for i in range(9)]
    nodes: list[tuple[int, int, int, int]] = []
    if home == "valid": nodes = [(addresses[0], 0, VIEW_CALLBACK, 0)]
    elif home == "multiple": nodes = [(addresses[0], addresses[1], VIEW_CALLBACK, 0),
                                        (addresses[1], 0, 0x12345, 0)]
    elif home == "not_home": nodes = [(addresses[0], addresses[1], 0x12345, 0),
                                        (addresses[1], 0, VIEW_CALLBACK, 0)]
    elif home == "hidden_match": nodes = [(addresses[0], addresses[1], VIEW_CALLBACK, 2),
                                            (addresses[1], 0, 0x12345, 0)]
    elif home == "cycle": nodes = [(addresses[0], addresses[1], VIEW_CALLBACK, 0),
                                     (addresses[1], addresses[0], 0x12345, 0)]
    elif home == "too_long":
        nodes = [(address, addresses[i + 1] if i < 8 else 0,
                  VIEW_CALLBACK if i == 0 else 0x12345, 0)
                 for i, address in enumerate(addresses)]
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    uc.mem_map(0x53000, 0x1000); uc.mem_map(0x1FFC0000, 0x80000); uc.mem_map(0x70000, 0x1000)
    image = IMAGE.read_bytes()
    uc.mem_write(0x53000, image[0x53000 - 0x3000:0x54000 - 0x3000])
    root = 0xDEAD0000 if home == "malformed" else (nodes[0][0] if nodes else 0)
    uc.mem_write(VIEW_ROOT, struct.pack("<I", root))
    for address, next_node, callback, flags in nodes:
        uc.mem_write(address + 4, struct.pack("<I", next_node))
        uc.mem_write(address + 8, struct.pack("<I", callback))
        uc.mem_write(address + 0x50, struct.pack("<I", flags))
    returned = False
    def stop_return(machine: Uc, address: int, _size: int, _user: Any) -> None:
        nonlocal returned
        if address == 0x70000:
            returned = True; machine.emu_stop()
    uc.hook_add(UC_HOOK_CODE, stop_return)
    try:
        uc.reg_write(UC_ARM_REG_SP, 0x20018000); uc.reg_write(UC_ARM_REG_LR, 0x70001)
        uc.reg_write(UC_ARM_REG_R0, VIEW_CALLBACK)
        uc.emu_start(VIEW_FIND | 1, 0, count=4096)
        if not returned:
            return {"status": "nonterminating", "eligible": None}
        found = uc.reg_read(UC_ARM_REG_R0)
        if found == 0:
            return {"status": "returned", "found": 0, "first_visible": None, "eligible": False}
        returned = False; uc.reg_write(UC_ARM_REG_LR, 0x70001); uc.reg_write(UC_ARM_REG_R0, found)
        uc.emu_start(VIEW_FIRST | 1, 0, count=4096)
        if not returned:
            return {"status": "nonterminating", "found": found, "eligible": None}
        first = uc.reg_read(UC_ARM_REG_R0)
        return {"status": "returned", "found": found, "first_visible": first,
                "eligible": first == 1}
    except UcError as error:
        return {"status": "memory_fault", "eligible": None, "detail": str(error)}


def emulate(bundle: Bundle, *, home: str = "valid", pressed_mask: int = 0,
            fill: int = 0x2A, framebuffer_null: bool = False,
            battery_bits: int = 0x42920000, usb_state: int = 0,
            rtc_samples: list[tuple[int, int, int]] | None = None,
            forced_activation: tuple[int, int] | None = None,
            key_statuses: dict[int, int] | None = None) -> dict[str, Any]:
    require(home in {"valid", "empty", "malformed", "cycle", "too_long", "not_home", "hidden_match", "multiple",
                     "finder_mismatch", "false_first_visible", "root_mutation"},
            "unknown home fixture")
    require(0 <= pressed_mask <= 31 and 0 <= fill <= 255 and 0 <= usb_state <= 255, "bad fixture")
    samples = rtc_samples or [(123, 0x2005, 123)]
    require(1 <= len(samples) <= 2, "RTC fixture must have one or two attempts")
    rtc_values = [(address, value & 0xFFFFFFFF) for sample in samples
                  for address, value in zip((RTC_SECONDS, RTC_PRESCALER, RTC_SECONDS), sample)]
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    for base, size in ((0x9000, 0x1000), (0xE000, 0x2000),
                       (PRIMARY, 0x1000), (SECONDARY & ~0xFFF, 0x1000),
                       (0x1FFC0000, 0x80000), (0x400FF000, 0x1000), (0x4003D000, 0x1000)):
        machine.mem_map(base, size)
    machine.mem_write(HOOK, bundle.hook); machine.mem_write(KEY_HOOK, bundle.keyhook)
    machine.mem_write(PRIMARY, bundle.primary); machine.mem_write(SECONDARY, bundle.secondary)
    before_guard = bytes((17 * i + 3) & 255 for i in range(GUARD))
    after_guard = bytes((241 - 11 * i) & 255 for i in range(GUARD))
    machine.mem_write(FRAMEBUFFER - GUARD, before_guard)
    machine.mem_write(FRAMEBUFFER, bytes([fill]) * FB_SIZE)
    machine.mem_write(FRAMEBUFFER + FB_SIZE, after_guard)
    pdir = {GPIOA: 0xFFFFFFFF, GPIOC: 0xFFFFFFFF, GPIOD: 0xFFFFFFFF}
    for index, (address, mask) in enumerate(BUTTONS):
        if pressed_mask & (1 << index): pdir[address] &= ~mask
    for address, value in pdir.items(): machine.mem_write(address, struct.pack("<I", value))
    machine.mem_write(BATTERY, struct.pack("<I", battery_bits & 0xFFFFFFFF)); machine.mem_write(USB_MS, bytes([usb_state]))
    for pad in KEY_PADS:
        machine.mem_write(pad, struct.pack("<H", KEY_IDLE))
    for key, status in (key_statuses or {}).items():
        require(key in (1, 3, 4) and status in (KEY_IDLE, KEY_OWNED, KEY_PULSE),
                "bad key padding fixture")
        machine.mem_write(KEY_PADS[key], struct.pack("<H", status))
    node_addresses = [0x20001000 + i * 0x100 for i in range(9)]
    nodes: list[tuple[int, int, int, int]] = []
    if home in ("valid", "finder_mismatch", "false_first_visible", "root_mutation"):
        nodes = [(node_addresses[0], 0, VIEW_CALLBACK, 0)]
    elif home == "multiple": nodes = [(node_addresses[0], node_addresses[1], VIEW_CALLBACK, 0),
                                        (node_addresses[1], 0, 0x12345, 0)]
    elif home == "not_home": nodes = [(node_addresses[0], node_addresses[1], 0x12345, 0),
                                        (node_addresses[1], 0, VIEW_CALLBACK, 0)]
    elif home == "hidden_match": nodes = [(node_addresses[0], node_addresses[1], VIEW_CALLBACK, 2),
                                            (node_addresses[1], 0, 0x12345, 0)]
    elif home == "cycle": nodes = [(node_addresses[0], node_addresses[1], VIEW_CALLBACK, 0),
                                     (node_addresses[1], node_addresses[0], 0x12345, 0)]
    elif home == "too_long":
        nodes = [(address, node_addresses[i + 1] if i < 8 else 0,
                  VIEW_CALLBACK if i == 0 else 0x12345, 0)
                 for i, address in enumerate(node_addresses)]
    if home == "malformed": machine.mem_write(VIEW_ROOT, struct.pack("<I", 0xDEAD0000))
    else: machine.mem_write(VIEW_ROOT, struct.pack("<I", nodes[0][0] if nodes else 0))
    for address, next_node, callback, flags in nodes:
        machine.mem_write(address + 4, struct.pack("<I", next_node))
        machine.mem_write(address + 8, struct.pack("<I", callback))
        machine.mem_write(address + 0x50, struct.pack("<I", flags))
    initial_regs = {reg: 0x45450000 + i * 0x10101 for i, reg in enumerate(CALLEE)}
    for register, value in initial_regs.items(): machine.reg_write(register, value)
    machine.reg_write(UC_ARM_REG_SP, STACK_POINTER); machine.reg_write(UC_ARM_REG_LR, HOOK + 5)
    machine.reg_write(UC_ARM_REG_R0, 0 if framebuffer_null else FRAMEBUFFER); machine.reg_write(UC_ARM_REG_R1, 0x7B)
    dirty_calls, dispatch_calls, external_targets = [], [], []
    data_reads, writes, outside_writes = [], [], []
    write_counts = Counter(); minimum_sp = STACK_POINTER; instructions = 0; rtc_index = 0
    captured: dict[str, Any] = {}; executed = set()
    symbols = bundle.manifest["symbols"]
    ranges = [(item["address"], item["address"] + item["size"])
              for item in symbols.values() if item["kind"] == 2]
    node_set = {item[0] for item in nodes}
    root_reads = 0

    def on_code(uc: Uc, address: int, size: int, _user: Any) -> None:
        nonlocal instructions, minimum_sp
        instructions += 1; executed.add(address); minimum_sp = min(minimum_sp, uc.reg_read(UC_ARM_REG_SP))
        require(STACK_POINTER - minimum_sp <= STACK_LIMIT, "runtime stack exceeded 384 bytes")
        if address == DIRTY:
            external_targets.append(address); dirty_calls.append([uc.reg_read(r) for r in ARGS])
            require(uc.reg_read(UC_ARM_REG_SP) % 8 == 0, "dirty SP not aligned")
            for i, reg in enumerate((*ARGS, UC_ARM_REG_R12)): uc.reg_write(reg, 0xA0A00000 + i)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        if address == DISPATCH:
            external_targets.append(address); dispatch_calls.append([uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)])
            require(uc.reg_read(UC_ARM_REG_LR) == HOOK + 5, "dispatch lost original return")
            uc.emu_stop(); return
        require(any(start <= address and address + size <= end for start, end in ranges),
                f"execution escaped allowlist: {address:#x}")
        if address == symbols["n64_render"]["address"]:
            brain_ptr, inputs_ptr = uc.reg_read(UC_ARM_REG_R1), uc.reg_read(UC_ARM_REG_R2)
            if forced_activation is not None:
                neuron, value = forced_activation
                require(0 <= neuron < 64 and -32768 <= value <= 32767, "bad forced activation")
                uc.mem_write(brain_ptr + neuron * 2, struct.pack("<h", value))
            brain = bytes(uc.mem_read(brain_ptr, 140)); inputs = bytes(uc.mem_read(inputs_ptr, 12))
            captured.update(activation=list(struct.unpack_from("<64h", brain)), brain=brain,
                            state=brain[136],
                            tick=uc.reg_read(UC_ARM_REG_R3), buttons=inputs[0], valid_mask=inputs[1],
                            battery=inputs[8], usb_ms=struct.unpack("<I", uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 4))[0])

    def on_read(uc: Uc, _access: int, address: int, size: int, _value: int, _user: Any) -> None:
        nonlocal rtc_index, root_reads
        if address == VIEW_ROOT:
            root_reads += 1
            if root_reads == 3 and nodes:
                if home == "finder_mismatch":
                    uc.mem_write(nodes[0][0] + 8, struct.pack("<I", 0x12345))
                elif home == "false_first_visible":
                    uc.mem_write(nodes[0][0] + 0x50, struct.pack("<I", 2))
                elif home == "root_mutation":
                    uc.mem_write(VIEW_ROOT, struct.pack("<I", 0xDEAD0000))
        if address in (RTC_SECONDS, RTC_PRESCALER):
            require(rtc_index < len(rtc_values), "RTC read exceeded fixture")
            expected_address, value = rtc_values[rtc_index]; require(address == expected_address, "RTC order mismatch")
            rtc_index += 1; uc.mem_write(address, struct.pack("<I", value))
        allowed_internal = (STACK_BASE <= address and address + size <= STACK_POINTER) or \
            (FRAMEBUFFER <= address and address + size <= FRAMEBUFFER + FB_SIZE) or \
            (PRIMARY <= address and address + size <= 0x1F63FF) or \
            (SECONDARY <= address and address + size <= 0x1FAC00)
        if allowed_internal: return
        allowed_fixed = {VIEW_ROOT, GPIOD, GPIOA, GPIOC, BATTERY, USB_MS,
                         RTC_SECONDS, RTC_PRESCALER, *KEY_PADS}
        allowed_node = any(address == node + offset for node in node_set for offset in (4, 8, 0x50))
        require(address in allowed_fixed or allowed_node, f"read escaped exact allowlist: {address:#x}/{size}")
        data_reads.append([address, size])

    def on_write(uc: Uc, _access: int, address: int, size: int, value: int, _user: Any) -> None:
        writes.append([uc.reg_read(UC_ARM_REG_PC), address, size, value])
        if FRAMEBUFFER <= address and address + size <= FRAMEBUFFER + FB_SIZE: write_counts["framebuffer"] += size
        elif STACK_BASE <= address and address + size <= STACK_POINTER: write_counts["stack"] += size
        elif address in KEY_PADS and size == 2: write_counts["key_padding"] += size
        else:
            outside_writes.append([address, size, value]); raise ValueError(f"write escaped framebuffer/stack: {address:#x}")

    machine.hook_add(UC_HOOK_CODE, on_code); machine.hook_add(UC_HOOK_MEM_READ, on_read); machine.hook_add(UC_HOOK_MEM_WRITE, on_write)
    machine.emu_start(HOOK | 1, 0, count=INSTRUCTION_CAP)
    require(len(dispatch_calls) == 1,
            f"instruction cap reached before dispatch at {machine.reg_read(UC_ARM_REG_PC):#x} "
            f"r0={machine.reg_read(UC_ARM_REG_R0):#x} r1={machine.reg_read(UC_ARM_REG_R1):#x} "
            f"r2={machine.reg_read(UC_ARM_REG_R2):#x} r3={machine.reg_read(UC_ARM_REG_R3):#x} "
            f"r4={machine.reg_read(UC_ARM_REG_R4):#x} r12={machine.reg_read(UC_ARM_REG_R12):#x} "
            f"sp={machine.reg_read(UC_ARM_REG_SP):#x} "
            f"stack={bytes(machine.mem_read(machine.reg_read(UC_ARM_REG_SP),48)).hex()}")
    framebuffer = bytes(machine.mem_read(FRAMEBUFFER, FB_SIZE))
    eligible = bool(dirty_calls)
    battery_valid = int(battery_bits == 0x80000000 or
                        ((battery_bits & 0x80000000) == 0 and battery_bits <= 0x42C80000 and
                         ((battery_bits >> 23) & 0xFF) != 0xFF))
    battery_value = 0 if not battery_valid or battery_bits == 0x80000000 or ((battery_bits >> 23) & 0xFF) < 127 else \
        (((battery_bits & 0x7FFFFF) | 0x800000) >> (150 - ((battery_bits >> 23) & 0xFF)))
    oracle = host_oracle(bundle.build, captured.get("tick", 0), captured.get("buttons", pressed_mask), battery_valid,
                         battery_value, int(usb_state in (3, 4))) if eligible and forced_activation is None else None
    if eligible and forced_activation is None:
        require(captured["brain"] == oracle["brain"], "target brain differs from host Brain64")
        require(framebuffer == oracle["target_framebuffer"], "target renderer differs from host target oracle")
    verified = verify_cells(framebuffer, captured["activation"]) if eligible else 0
    foreground = [(index % 240, index // 240) for index, value in enumerate(framebuffer) if value != 0]
    result = {"eligible": eligible, "home": home, "pressed_mask": pressed_mask,
              "framebuffer_null": framebuffer_null, "initial_fill": fill,
              "forced_activation": forced_activation,
              "framebuffer": framebuffer, "framebuffer_sha256": sha256(framebuffer),
              "framebuffer_unchanged": framebuffer == bytes([fill]) * FB_SIZE,
              "all_pixels_reviewed_palette": all(value in (0x00, 0x2A, 0x3F, 0x0C, 0x33, 0x38)
                                                    for value in framebuffer),
              "safe_radius": all((x - 120) ** 2 + (y - 120) ** 2 <= 100 ** 2 for x, y in foreground),
              "dirty_calls": dirty_calls, "dispatch_calls": dispatch_calls,
              "external_targets": external_targets, "data_reads": data_reads,
              "outside_writes": outside_writes, "write_counts": dict(write_counts),
              "write_trace_sha256": sha256(json.dumps(writes, separators=(",", ":")).encode()),
              "guard_before_unchanged": bytes(machine.mem_read(FRAMEBUFFER-GUARD, GUARD)) == before_guard,
              "guard_after_unchanged": bytes(machine.mem_read(FRAMEBUFFER+FB_SIZE, GUARD)) == after_guard,
              "callee_saved_preserved": all(machine.reg_read(r) == v for r, v in initial_regs.items()),
              "sp_restored": machine.reg_read(UC_ARM_REG_SP) == STACK_POINTER,
              "maximum_runtime_stack_bytes": STACK_POINTER - minimum_sp,
              "key_statuses": [struct.unpack("<H", machine.mem_read(pad, 2))[0]
                               for pad in KEY_PADS],
              "instruction_count": instructions, "rtc_reads": rtc_index,
              "verified_neuron_cells": verified,
              "executed_cross_segment_branches": [pair for pair in bundle.manifest["stack_audit"]["cross_segment_branches"] if pair[0] in executed],
              **captured}
    validate_result(result)
    return result


def emulate_key_sequence(bundle: Bundle, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute the patched FA48 key publisher across a stateful event sequence."""
    require(events, "key sequence must not be empty")
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    for base, size in ((0x6000, 0x2000), (0xF000, 0x1000), (0x1E000, 0x2000),
                       (0x53000, 0x1000), (0x70000, 0x1000),
                       (PRIMARY, 0x1000), (SECONDARY & ~0xFFF, 0x1000),
                       (0x1FFC0000, 0x80000), (0x400FF000, 0x1000)):
        machine.mem_map(base, size)
    image = IMAGE.read_bytes()
    machine.mem_write(0xF000, image[0xF000 - 0x3000:0x10000 - 0x3000])
    machine.mem_write(KEY_HOOK, bundle.keyhook)
    machine.mem_write(PRIMARY, bundle.primary)
    machine.mem_write(SECONDARY, bundle.secondary)
    for key in range(5):
        machine.mem_write(KEY_WORKSPACE + key * 0x38, struct.pack("<I", 0x10203040 + key))
        machine.mem_write(KEY_PADS[key], struct.pack("<H", KEY_IDLE))

    symbols = bundle.manifest["symbols"]
    custom_ranges = [(item["address"], item["address"] + item["size"])
                     for item in symbols.values() if item["kind"] == 2]
    published: list[dict[str, int]] = []
    queue_sends: list[dict[str, int]] = []
    writes: list[list[int]] = []
    reads: list[list[int]] = []
    current_key = 0
    current_event: dict[str, Any] = {}
    root_reads = 0
    stopped = False
    minimum_sp = STACK_POINTER
    instruction_count = 0
    executed: set[int] = set()
    RETURN, TICK, PUBLISH, QUEUE_SEND = 0x70000, 0x7FA4, 0x1EF1C, 0x67D8
    QUEUE_GLOBAL, QUEUE_OBJECT = 0x1FFC7E14, 0x20002000
    node_addresses = tuple(0x20001000 + index * 0x100 for index in range(9))
    node0, node1 = node_addresses[:2]

    def set_home(kind: str) -> None:
        require(kind in {"valid", "empty", "malformed", "cycle", "too_long",
                         "not_home", "hidden_match", "multiple", "finder_mismatch",
                         "false_first_visible", "root_mutation"},
                "unknown key home fixture")
        if kind == "empty": root = 0
        elif kind == "malformed": root = 0xDEAD0000
        else: root = node0
        machine.mem_write(VIEW_ROOT, struct.pack("<I", root))
        for node in node_addresses:
            machine.mem_write(node + 4, b"\0" * 4)
            machine.mem_write(node + 8, b"\0" * 4)
            machine.mem_write(node + 0x50, b"\0" * 4)
        if kind in {"valid", "finder_mismatch", "false_first_visible", "root_mutation"}:
            nodes = ((node0, 0, VIEW_CALLBACK, 0),)
        elif kind == "multiple":
            nodes = ((node0, node1, VIEW_CALLBACK, 0),
                     (node1, 0, 0x12345, 0))
        elif kind == "not_home": nodes = ((node0, node1, 0x12345, 0),
                                             (node1, 0, VIEW_CALLBACK, 0))
        elif kind == "hidden_match": nodes = ((node0, node1, VIEW_CALLBACK, 2),
                                                 (node1, 0, 0x12345, 0))
        elif kind == "cycle": nodes = ((node0, node1, VIEW_CALLBACK, 0),
                                          (node1, node0, 0x12345, 0))
        elif kind == "too_long":
            nodes = tuple((node, node_addresses[index + 1] if index < 8 else 0,
                           VIEW_CALLBACK if index == 0 else 0x12345, 0)
                          for index, node in enumerate(node_addresses))
        else: nodes = ()
        for node, next_node, callback, flags in nodes:
            machine.mem_write(node + 4, struct.pack("<I", next_node))
            machine.mem_write(node + 8, struct.pack("<I", callback))
            machine.mem_write(node + 0x50, struct.pack("<I", flags))

    def on_code(uc: Uc, address: int, size: int, _user: Any) -> None:
        nonlocal stopped, minimum_sp, instruction_count
        instruction_count += 1
        executed.add(address)
        minimum_sp = min(minimum_sp, uc.reg_read(UC_ARM_REG_SP))
        require(STACK_POINTER - minimum_sp <= STACK_LIMIT, "key runtime stack exceeded")
        if address == RETURN:
            stopped = True; uc.emu_stop(); return
        if address == TICK:
            uc.reg_write(UC_ARM_REG_R0, 0x11223344)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        if address == PUBLISH:
            event = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R0), 20))
            published.append({"type": struct.unpack_from("<I", event, 0)[0],
                              "key": struct.unpack_from("<H", event, 16)[0],
                              "state": event[18]})
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        if address == QUEUE_SEND:
            message = bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_R1), 8))
            queue_sends.append({"queue": uc.reg_read(UC_ARM_REG_R0),
                                "node": struct.unpack_from("<I", message, 0)[0],
                                "event": struct.unpack_from("<H", message, 4)[0],
                                "front": uc.reg_read(UC_ARM_REG_R2),
                                "timeout": uc.reg_read(UC_ARM_REG_R3)})
            uc.reg_write(UC_ARM_REG_R0, int(current_event.get("queue_result", 0)))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        allowed = (KEY_HOOK <= address and address + size <= KEY_HOOK + 6) or \
            (0xFA4E <= address and address + size <= 0xFA80) or \
            any(start <= address and address + size <= end for start, end in custom_ranges)
        require(allowed, f"key execution escaped allowlist: {address:#x}")

    def on_read(uc: Uc, _access: int, address: int, size: int, _value: int, _user: Any) -> None:
        nonlocal root_reads
        if address == VIEW_ROOT:
            root_reads += 1
            if root_reads == 3:
                home = str(current_event.get("home", "valid"))
                if home == "finder_mismatch":
                    uc.mem_write(node0 + 8, struct.pack("<I", 0x12345))
                elif home == "false_first_visible":
                    uc.mem_write(node0 + 0x50, struct.pack("<I", 2))
                elif home == "root_mutation":
                    uc.mem_write(VIEW_ROOT, struct.pack("<I", 0xDEAD0000))
        allowed = (STACK_BASE <= address and address + size <= STACK_POINTER) or \
            (PRIMARY <= address and address + size <= 0x1F63FF) or \
            (SECONDARY <= address and address + size <= 0x1FAC00) or \
            (0xF000 <= address and address + size <= 0x10000) or \
            address in {VIEW_ROOT, USB_MS, GPIOD, QUEUE_GLOBAL, *KEY_PADS,
                        KEY_WORKSPACE + current_key * 0x38} or \
            any(address == node + offset for node in node_addresses for offset in (4, 8, 0x50))
        require(allowed, f"key read escaped allowlist: {address:#x}/{size}")
        if not (STACK_BASE <= address and address + size <= STACK_POINTER):
            reads.append([address, size])

    def on_write(uc: Uc, _access: int, address: int, size: int, value: int, _user: Any) -> None:
        writes.append([uc.reg_read(UC_ARM_REG_PC), address, size, value])
        require((STACK_BASE <= address and address + size <= STACK_POINTER) or
                (address in KEY_PADS and size == 2),
                f"key write escaped stack/padding: {address:#x}/{size}")

    machine.hook_add(UC_HOOK_CODE, on_code)
    machine.hook_add(UC_HOOK_MEM_READ, on_read)
    machine.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cases = []
    callee_seed = {reg: 0x51510000 + index * 0x10101
                   for index, reg in enumerate(CALLEE)}
    for item in events:
        current_event = item
        current_key = int(item["key"])
        state = int(item["state"])
        require(0 <= current_key <= 4 and 0 <= state <= 255, "bad key event")
        for key, status in item.get("initial_statuses", {}).items():
            key = int(key)
            status = int(status)
            require(key in (1, 3, 4) and status in (KEY_IDLE, KEY_OWNED, KEY_PULSE),
                    "bad initial key status")
            machine.mem_write(KEY_PADS[key], struct.pack("<H", status))
        root_reads = 0
        set_home(str(item.get("home", "valid")))
        machine.mem_write(USB_MS, bytes([int(item.get("usb", 0)) & 0xFF]))
        machine.mem_write(QUEUE_GLOBAL, struct.pack("<I",
                          0 if item.get("queue_uninitialized", False) else QUEUE_OBJECT))
        d = 0xFFFFFFFF & (~2 if item.get("back_held", False) else 0xFFFFFFFF)
        machine.mem_write(GPIOD, struct.pack("<I", d))
        for reg, value in callee_seed.items(): machine.reg_write(reg, value)
        machine.reg_write(UC_ARM_REG_SP, STACK_POINTER)
        machine.reg_write(UC_ARM_REG_LR, RETURN | 1)
        machine.reg_write(UC_ARM_REG_R0, current_key)
        machine.reg_write(UC_ARM_REG_R1, state)
        stopped = False
        before_publish, before_queue = len(published), len(queue_sends)
        machine.emu_start(KEY_HOOK | 1, 0, count=100_000)
        require(stopped, "key hook did not return")
        require(machine.reg_read(UC_ARM_REG_SP) == STACK_POINTER, "key hook did not restore SP")
        require(all(machine.reg_read(reg) == value for reg, value in callee_seed.items()),
                "key hook changed callee-saved register")
        cases.append({"key": current_key, "state": state,
                      "home": str(item.get("home", "valid")),
                      "usb": int(item.get("usb", 0)) & 0xFF,
                      "back_held": bool(item.get("back_held", False)),
                      "published": published[before_publish:],
                      "queue_sends": queue_sends[before_queue:],
                      "statuses": [struct.unpack("<H", machine.mem_read(pad, 2))[0]
                                   for pad in KEY_PADS]})
    padding_writes = [[address, size, value] for _pc, address, size, value in writes
                      if address in KEY_PADS]
    return {"cases": cases, "published": published, "queue_sends": queue_sends,
            "padding_writes": padding_writes, "reads": reads,
            "maximum_runtime_stack_bytes": STACK_POINTER - minimum_sp,
            "instruction_count": instruction_count,
            "executed_cross_segment_branches": [
                pair for pair in bundle.manifest["stack_audit"]["cross_segment_branches"]
                if pair[0] in executed],
            "final_statuses": cases[-1]["statuses"]}


def validate_result(result: dict) -> None:
    for key in ("guard_before_unchanged", "guard_after_unchanged", "callee_saved_preserved", "sp_restored"):
        require(result[key], f"invariant failed: {key}")
    require(not result["outside_writes"], "write confinement failed")
    require(result["dispatch_calls"] == [[0 if result["framebuffer_null"] else FRAMEBUFFER, 0]], "dispatch ABI failed")
    require(result["maximum_runtime_stack_bytes"] <= STACK_LIMIT, "runtime stack failed")
    if result["eligible"]:
        require(result["dirty_calls"] == [[0, 0, 240, 240]], "dirty ABI failed")
        require(result["all_pixels_reviewed_palette"] and result["safe_radius"], "palette/safe-radius failed")
        require(result["verified_neuron_cells"] == 64, "64-cell mapping failed")
        require(result["external_targets"] == [DIRTY, DISPATCH], "external call order failed")
    else:
        require(result["framebuffer_unchanged"] and not result["dirty_calls"], "pass-through changed frame")
        require(result["external_targets"][-1:] == [DISPATCH], "pass-through must end at dispatch")


def generate_report(build: Path, report_path: Path, preview_path: Path | None) -> dict:
    bundle = load_build(build)
    cases = {}
    for home in ("valid", "empty", "malformed", "cycle", "too_long", "not_home", "hidden_match",
                 "multiple", "finder_mismatch", "false_first_visible", "root_mutation"):
        result = emulate(bundle, home=home)
        cases[home] = {key: value for key, value in result.items() if key not in ("framebuffer", "brain", "activation", "data_reads")}
    saturated = emulate(bundle, forced_activation=(56, 700))
    battery100 = emulate(bundle, battery_bits=0x42C80000)
    controls = {}
    for key in (1, 3, 4):
        controls[str(key)] = emulate_key_sequence(bundle, [
            {"key": key, "state": 0}, {"key": key, "state": 2},
            {"key": key, "state": 1}])
    report = {"schema": "flyos.fr245.n64-controls-emulation.v1", "cases": cases,
              "controls": controls,
              "vendor_oracle": {name: vendor_view_oracle(name) for name in
                                ("valid", "empty", "malformed", "cycle", "too_long", "not_home",
                                 "hidden_match", "multiple")},
              "palette": {"allowed_native_bytes": [0, 12, 42, 51, 56, 63],
                          "saturated_fixture": {"neuron": 56, "activation": 700,
                                                "pixels_present": sorted(set(saturated["framebuffer"]))}},
              "battery_100": {"value": battery100["battery"],
                              "framebuffer_sha256": battery100["framebuffer_sha256"]},
              "manifest_sha256": sha256((build / "manifest.json").read_bytes())}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if preview_path is not None:
        write_ppm(emulate(bundle)["framebuffer"], preview_path)
    return report


RGB = {0x00: b"\x00\x00\x00", 0x2A: b"\xaa\xaa\xaa", 0x3F: b"\xff\xff\xff",
       0x0C: b"\x00\xff\x00", 0x33: b"\xff\x00\xff", 0x38: b"\xff\xaa\x00"}


def rgb_bytes(framebuffer: bytes) -> bytes:
    return b"".join(RGB[value] for value in framebuffer)


def write_ppm(framebuffer: bytes, path: Path) -> None:
    path.write_bytes(b"P6\n240 240\n255\n" + rgb_bytes(framebuffer))


def write_png(framebuffer: bytes, path: Path) -> None:
    raw_rgb = rgb_bytes(framebuffer)
    scanlines = b"".join(b"\0" + raw_rgb[y * 720:(y + 1) * 720] for y in range(240))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 240, 240, 8, 2, 0, 0, 0)) +
                     chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b""))


def publish_evidence(build: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = load_build(build)
    report_path = output_dir / f"{ARTIFACT_PREFIX}-emulator-report.json"
    generate_report(build, report_path, None)
    fixtures = {"preview": emulate(bundle)["framebuffer"],
                "preview-battery100": emulate(bundle, battery_bits=0x42C80000)["framebuffer"],
                "preview-saturated": emulate(bundle, forced_activation=(56, 700))["framebuffer"]}
    paths = [report_path]
    for stem, frame in fixtures.items():
        ppm = output_dir / f"{ARTIFACT_PREFIX}-{stem}.ppm"
        png = output_dir / f"{ARTIFACT_PREFIX}-{stem}.png"
        write_ppm(frame, ppm); write_png(frame, png); paths += [ppm, png]
    build_paths = [build / "manifest.json", build / "SHA256SUMS.txt",
                   build / "hook.bin", build / "keyhook.bin",
                   build / "primary.bin", build / "secondary.bin"]
    manifest = {"schema": "flyos.fr245.n64-controls-evidence.v1",
                "self_hash_policy": "this manifest is intentionally omitted from its own files map",
                "files": {path.name: {"size": len(path.read_bytes()), "sha256": sha256(path.read_bytes())}
                          for path in paths},
                "build_files": {path.name: {"size": len(path.read_bytes()), "sha256": sha256(path.read_bytes())}
                                for path in build_paths}}
    manifest_path = output_dir / f"{ARTIFACT_PREFIX}-evidence-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-evidence", action="store_true")
    parser.add_argument("--check-build", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--publish-evidence", type=Path)
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    args = parser.parse_args()
    if args.check_evidence:
        print(json.dumps(evidence_gate(), sort_keys=True))
    elif args.check_build:
        manifest = check_build(args.check_build)
        print(json.dumps({"primary": manifest["segments"]["primary"]["size"],
                          "secondary": manifest["segments"]["secondary"]["size"],
                          "stack": manifest["stack_audit"]["stack_bound_bytes"]}))
    elif args.publish_evidence:
        print(json.dumps(publish_evidence(args.build, args.publish_evidence), sort_keys=True))
    elif args.report:
        generate_report(args.build, args.report, args.preview)
    else:
        parser.error("use --check-build or --report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
