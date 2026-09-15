#!/usr/bin/env python3
"""Validate and execute the split FR245 shared-C overlay, entirely offline.

Only the two Garmin calls are intercepted. Brain reconstruction and rendering
execute as compiled Thumb instructions; the Python checks never simulate neurons.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from typing import Any

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import (
    Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_LITTLE_ENDIAN,
    UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
)
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD = ROOT / "flyos/target/fr245_1370_neural_overlay/build"
PLACEMENT = ROOT / "artifacts/analysis/fr245-1370-second-allocation.json"
IMAGE_SHA256 = "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6"
ELF_NAME = "fr245-1370-neural-overlay.elf"
PRIMARY = 0x001F6000
SECONDARY = 0x001FA400
HOOK = 0x00009A20
DIRTY_ADD = 0x0000F2E8
DISPATCH = 0x0000E1A4
FRAMEBUFFER = 0x1FFDE6E8
FRAMEBUFFER_SIZE = 57600
ACTIVE_BACKEND = 0x1FFDB754
STARTUP_COMPLETE = 0x1FFF223C
STACK_BASE = 0x20017000
STACK_POINTER = 0x20018000
GUARD_SIZE = 64
GPIOA_PDIR = 0x400FF010
GPIOC_PDIR = 0x400FF090
GPIOD_PDIR = 0x400FF0D0
RTC_SECONDS = 0x4003D000
RTC_PRESCALER = 0x4003D004
INSTRUCTION_CAP = 1_000_000
STACK_LIMIT = 384
BUTTONS = ((GPIOC_PDIR, 0x800), (GPIOD_PDIR, 0x400),
           (GPIOD_PDIR, 2), (GPIOA_PDIR, 0x100000), (GPIOA_PDIR, 0x400000))
CALLEE_REGISTERS = (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                   UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
                   UC_ARM_REG_R10, UC_ARM_REG_R11)
ARG_REGISTERS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
# Hand-audited 5x7 glyph raster contract, independent of the network code.
GLYPHS = ((0, 0, 0, 0, 0, 4, 0), (0, 0, 14, 10, 14, 0, 0),
          (14, 17, 17, 17, 17, 17, 14), (14, 17, 23, 21, 23, 16, 15))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_elf(path: Path) -> tuple[dict, dict]:
    """Read ELF32 ARM section/symbol records without an optional ELF dependency."""
    data = path.read_bytes()
    require(data[:7] == b"\x7fELF\x01\x01\x01", "Expected little-endian ELF32")
    header = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    require(header[0] == 2 and header[1] == 40, "Expected ARM executable ELF")
    section_offset, section_size, section_count, string_index = header[5], *header[10:13]
    raw = [struct.unpack_from("<10I", data, section_offset + i * section_size)
           for i in range(section_count)]
    string_section = raw[string_index]
    names = data[string_section[4]:string_section[4] + string_section[5]]

    def cstring(table: bytes, index: int) -> str:
        return table[index:table.index(0, index)].decode("ascii")

    sections = {}
    for item in raw:
        name = cstring(names, item[0])
        sections[name] = dict(type=item[1], flags=item[2], address=item[3],
                              size=item[5], data=data[item[4]:item[4] + item[5]])
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
            symbol_name = cstring(strings, name)
            require(index != 0, f"Undefined ELF symbol: {symbol_name}")
            symbols[symbol_name] = dict(address=value & ~1 if info & 15 == 2 else value,
                                        size=size, kind=info & 15, section=index)
    return sections, symbols


def decode_hook(hook: bytes) -> int:
    instructions = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(hook, HOOK))
    require(len(hook) == 4 and len(instructions) == 1 and
            instructions[0].mnemonic == "bl", "Hook must be exactly one four-byte Thumb BL")
    return int(instructions[0].op_str.lstrip("#"), 0)


def placement_gate(path: Path = PLACEMENT, expected_sha256: str | None = None) -> dict:
    data = path.read_bytes()
    if expected_sha256 is not None:
        require(sha256(data) == expected_sha256, "Placement evidence SHA256 mismatch")
    evidence = json.loads(data)
    require(evidence.get("link_and_emulate_allowed") is True, "Offline link/emulation not permitted")
    interval = evidence.get("offline_interval", {})
    require(interval.get("start") == "0x001fa400" and interval.get("end") == "0x001fabff"
            and interval.get("length") == 2048, "Offline interval must be exact")
    require(evidence["image"]["sha256"] == IMAGE_SHA256, "Wrong pinned firmware image")
    require(evidence["rtc_audit"]["read_audit_pass"] is True, "RTC reads lack evidence")
    return {**evidence, "current_sha256": sha256(data)}


def stack_audit(build: Path, symbols: dict) -> dict:
    """Conservatively sum compiler frames on the linked, nonrecursive call graph.

    Tail branches also add the caller's complete frame, an overestimate. Stock
    dirty/dispatch frames are excluded: this bound covers target-owned frames.
    """
    frames = {"flyos_hook_patch": 0}
    for path in sorted(build.glob("*.su")):
        for line in path.read_text().splitlines():
            location, count, kind = line.split("\t")
            require(kind == "static", f"Unbounded/dynamic stack usage: {line}")
            frames[location.rsplit(":", 1)[1]] = int(count)
    functions = {name: item for name, item in symbols.items() if item["kind"] == 2}
    require(set(functions) <= set(frames), "Missing compiler stack usage for a linked function")
    graph = {name: set() for name in functions}
    starts = {item["address"]: name for name, item in functions.items()}
    indirect = []
    cross_branches = []
    current = None
    listing = (build / "fr245-1370-neural-overlay.disassembly.txt").read_text()
    for line in listing.splitlines():
        label = re.match(r"^([0-9a-f]+) <([^>]+)>:", line)
        if label:
            current = label[2] if label[2] in functions else None
            continue
        instruction = re.match(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4,8}\s+)+([a-z][a-z0-9.]*)\s+(.+)", line)
        if not current or not instruction:
            continue
        address, mnemonic, operands = int(instruction[1], 16), instruction[2], instruction[3]
        if mnemonic in ("blx", "bx") and not operands.startswith("lr"):
            require(current == "overlay_then_flush" and (mnemonic, operands.strip()) in (("blx", "r4"), ("bx", "r3")),
                    f"Unresolved target call/branch: {line}")
            indirect.append(dict(address=address, function=current, instruction=mnemonic + " " + operands))
        target = re.match(r"([0-9a-f]+) <", operands)
        if mnemonic.startswith("b") and target:
            destination = int(target[1], 16)
            if destination in starts and starts[destination] != current:
                graph[current].add(starts[destination])
                if (PRIMARY <= address < PRIMARY + 0x400 and SECONDARY <= destination < SECONDARY + 0x800) or (
                    SECONDARY <= address < SECONDARY + 0x800 and PRIMARY <= destination < PRIMARY + 0x400):
                    cross_branches.append([address, destination])
            elif mnemonic == "bl":
                require(destination in starts, f"Unknown direct callee: {line}")

    def bound(name: str, active: tuple = ()) -> tuple[int, list[str]]:
        require(name not in active, "Recursive target call graph")
        children = [bound(child, active + (name,)) for child in graph[name]]
        deepest, chain = max(children, default=(0, []), key=lambda pair: pair[0])
        return frames[name] + deepest, [name] + chain

    maximum, chain = bound("flyos_hook_patch")
    require(maximum <= STACK_LIMIT, f"Target stack bound {maximum} exceeds {STACK_LIMIT}")
    require(len(indirect) == 2, "Expected only dirty-call and dispatch-tail indirect transfers")
    return dict(stack_bound_bytes=maximum, maximum_allowed_bytes=STACK_LIMIT,
                maximum_chain=chain, frames=frames,
                call_graph={key: sorted(value) for key, value in graph.items()},
                external_transfers=indirect, cross_segment_branches=cross_branches,
                scope="Target-owned frames only; stock dirty/dispatch and interrupt frames excluded")


def check_build(build: Path, placement: Path = PLACEMENT, expected_sha256: str | None = None) -> dict:
    evidence = placement_gate(placement, expected_sha256)
    sections, symbols = read_elf(build / ELF_NAME)
    expected = {".hook": (HOOK, 4), ".primary": (PRIMARY, 0x3FF), ".secondary": (SECONDARY, 0x800)}
    segments = {}
    for name, (address, maximum) in expected.items():
        section = sections[name]
        require(section["address"] == address and 0 < section["size"] <= maximum,
                f"Wrong linked address/size for {name}")
        binary = build / (name[1:] + ".bin")
        require(binary.read_bytes() == section["data"], f"Extracted bytes differ from ELF: {binary.name}")
        segments[name[1:]] = dict(start=address, end=address + section["size"] - 1,
                                  size=section["size"], sha256=sha256(section["data"]))
    allocated = [name for name, section in sections.items() if section["flags"] & 2 and section["size"]]
    require(set(allocated) == set(expected), f"Unexpected allocated ELF sections: {allocated}")
    require(symbols["overlay_then_flush"]["address"] == PRIMARY, "Wrong overlay entry address")
    require(decode_hook(sections[".hook"]["data"]) == PRIMARY, "Wrong BL hook target")
    require(segments["primary"]["end"] <= 0x1F63FE and segments["secondary"]["start"] > 0x1F63FF,
            "Overlap or reserved checksum byte consumed")
    audit = stack_audit(build, symbols)
    retained_oracle = host_oracle(build, 0x003DA005, 0, retained=True)
    files = [build / ELF_NAME, build / "fr245-1370-neural-overlay.map",
             build / "fr245-1370-neural-overlay.disassembly.txt", build / "symbols.txt",
             build / "hook.bin", build / "primary.bin", build / "secondary.bin"]
    files += sorted(build.glob("*.su")) + sorted(build.glob("*.o"))
    files += [ROOT / name for name in retained_oracle["artifacts"]]
    sources = [ROOT / "flyos/fly/brain32.c", ROOT / "flyos/fly/brain32.h",
               ROOT / "flyos/display/brain_ascii.c", ROOT / "flyos/display/brain_ascii.h"]
    sources += [build.parent / name for name in ("overlay.c", "hook.S", "linker.ld", "build.ps1")]
    manifest = dict(schema_version=1, placement_sha256=evidence["current_sha256"],
                    firmware_image_sha256=IMAGE_SHA256,
                    link_and_emulate_allowed=evidence["link_and_emulate_allowed"],
                    packaging_allowed=evidence["packaging_allowed"], segments=segments,
                    checksum_repair_byte=0x1F63FF, stack_bound_bytes=audit["stack_bound_bytes"],
                    stack_audit=audit, symbols=symbols,
                    retained_oracle=public_result(retained_oracle),
                    files={path.relative_to(build).as_posix(): sha256(path.read_bytes()) for path in files},
                    sources={str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path.read_bytes()) for path in sources})
    manifest_path = build / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    hashes = {**manifest["files"], "manifest.json": sha256(manifest_path.read_bytes())}
    (build / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())), encoding="ascii")
    return manifest


@dataclass(frozen=True)
class Bundle:
    primary: bytes
    secondary: bytes
    hook: bytes
    manifest: dict


def load_build(build: Path = DEFAULT_BUILD) -> Bundle:
    manifest = json.loads((build / "manifest.json").read_text())
    placement_gate(expected_sha256=manifest["placement_sha256"])
    for name, digest in manifest["files"].items():
        require(sha256((build / name).read_bytes()) == digest, f"Build hash mismatch: {name}")
    for name, digest in manifest["sources"].items():
        require(sha256((ROOT / name).read_bytes()) == digest, f"Source hash mismatch: {name}; rebuild required")
    sections, _ = read_elf(build / ELF_NAME)
    bundle = Bundle(*( (build / name).read_bytes() for name in ("primary.bin", "secondary.bin", "hook.bin")), manifest)
    for name, data, start, maximum in (("primary", bundle.primary, PRIMARY, 0x3FF),
                                       ("secondary", bundle.secondary, SECONDARY, 0x800),
                                       ("hook", bundle.hook, HOOK, 4)):
        require(0 < len(data) <= maximum and data == sections["." + name]["data"]
                and sections["." + name]["address"] == start, "Invalid split ELF/binary layout")
    require(decode_hook(bundle.hook) == PRIMARY, "Wrong BL hook destination")
    return bundle


def verify_neuron_cells(framebuffer: bytes, activation: list[int], points: list[list[int]]) -> int:
    require(len(activation) == len(points) == 32 and len(set(map(tuple, points))) == 32,
            "Expected 32 unique neuron cells")
    for neuron, (value, (x, y)) in enumerate(zip(activation, points)):
        require(0 <= x <= 231 and 0 <= y <= 233, "Neuron cell/pulse outside framebuffer")
        magnitude = abs(value)
        level = 0 if magnitude < 128 else 1 if magnitude < 256 else 2 if magnitude < 512 else 3
        for row in range(7):
            for column in range(5):
                expected = 0 if GLYPHS[level][row] & (1 << (4 - column)) else 255
                require(framebuffer[(y + row) * 240 + x + column] == expected,
                        f"Neuron {neuron} level {level} glyph mismatch at {column},{row}")
        for offset in (7, 8):
            require(framebuffer[(y + 3) * 240 + x + offset] == (0 if level >= 2 else 255),
                    f"Neuron {neuron} pulse mismatch")
    return 32


def emulate(bundle: Bundle, *, pressed_mask: int = 0, fill: int = 0x2A,
            backend: int = 0xEBFC, startup: int = 1, framebuffer_null: bool = False,
            rtc_samples: list[tuple[int, int, int]] | None = None) -> dict[str, Any]:
    require(0 <= pressed_mask <= 31 and 0 <= fill <= 255, "Invalid buttons/fill")
    require(len(bundle.primary) <= 0x3FF and len(bundle.secondary) <= 0x800,
            "Payload outside allowed allocations")
    samples = rtc_samples if rtc_samples is not None else [(123, 0xA005, 123)]
    require(1 <= len(samples) <= 2 and all(len(sample) == 3 for sample in samples), "Invalid RTC samples")
    rtc_values = [(address, int(value) & 0xFFFFFFFF) for sample in samples
                  for address, value in zip((RTC_SECONDS, RTC_PRESCALER, RTC_SECONDS), sample)]
    eligible = not framebuffer_null and backend == 0xEBFC and startup == 1
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_LITTLE_ENDIAN)
    for base, size in ((0x9000, 0x1000), (0xE000, 0x2000), (PRIMARY, 0x1000),
                       (SECONDARY & ~0xFFF, 0x1000), (ACTIVE_BACKEND & ~0xFFF, 0x1000),
                       (FRAMEBUFFER & ~0xFFF, 0xF000), (STARTUP_COMPLETE & ~0xFFF, 0x1000),
                       (STACK_BASE, STACK_POINTER - STACK_BASE),
                       (0x400FF000, 0x1000), (0x4003D000, 0x1000)):
        machine.mem_map(base, size)
    machine.mem_write(PRIMARY, bundle.primary)
    machine.mem_write(SECONDARY, bundle.secondary)
    machine.mem_write(HOOK, bundle.hook)
    guard_before = bytes((0x31 + i * 17) & 255 for i in range(GUARD_SIZE))
    guard_after = bytes((0xC7 - i * 13) & 255 for i in range(GUARD_SIZE))
    machine.mem_write(FRAMEBUFFER - GUARD_SIZE, guard_before)
    machine.mem_write(FRAMEBUFFER, bytes([fill]) * FRAMEBUFFER_SIZE)
    machine.mem_write(FRAMEBUFFER + FRAMEBUFFER_SIZE, guard_after)
    machine.mem_write(ACTIVE_BACKEND, struct.pack("<I", backend))
    machine.mem_write(STARTUP_COMPLETE, bytes([startup]))
    pdir = {GPIOA_PDIR: 0xFFFFFFFF, GPIOC_PDIR: 0xFFFFFFFF, GPIOD_PDIR: 0xFFFFFFFF}
    for index, (address, mask) in enumerate(BUTTONS):
        if pressed_mask & (1 << index):
            pdir[address] &= ~mask
    for address, value in pdir.items():
        machine.mem_write(address, struct.pack("<I", value))
    initial = {register: 0x44440000 + index * 0x1111 for index, register in enumerate(CALLEE_REGISTERS)}
    for register, value in initial.items():
        machine.reg_write(register, value)
    machine.reg_write(UC_ARM_REG_SP, STACK_POINTER)
    machine.reg_write(UC_ARM_REG_LR, 0x1001)
    machine.reg_write(UC_ARM_REG_R0, 0 if framebuffer_null else FRAMEBUFFER)
    machine.reg_write(UC_ARM_REG_R1, 0x7B)
    dirty_calls, dispatch_calls, peripheral_reads, peripheral_values = [], [], [], []
    peripheral_writes, outside_writes, write_trace = [], [], []
    write_counts = Counter()
    written = bytearray(FRAMEBUFFER_SIZE)
    instruction_count = 0
    framebuffer_accesses = 0
    rtc_index = 0
    minimum_sp = STACK_POINTER
    captured = {}
    executed = set()
    symbols = bundle.manifest["symbols"]
    renderer = symbols["fly_brain_ascii_render"]["address"]
    function_ranges = [(item["address"], item["address"] + item["size"])
                       for item in symbols.values() if item["kind"] == 2]

    def on_code(uc: Uc, address: int, size: int, _: Any) -> None:
        nonlocal instruction_count, minimum_sp
        instruction_count += 1
        executed.add(address)
        minimum_sp = min(minimum_sp, uc.reg_read(UC_ARM_REG_SP))
        require(STACK_POINTER - minimum_sp <= STACK_LIMIT, "Runtime target stack limit exceeded")
        if address == DIRTY_ADD:
            dirty_calls.append([uc.reg_read(register) for register in ARG_REGISTERS])
            require(uc.reg_read(UC_ARM_REG_SP) % 8 == 0, "Unaligned dirty-call SP")
            # Exercise the ABI: the original callee may clobber all caller-saved registers.
            for index, register in enumerate((*ARG_REGISTERS, UC_ARM_REG_R12)):
                uc.reg_write(register, 0xA0A00000 + index)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        elif address == DISPATCH:
            dispatch_calls.append([uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)])
            require(uc.reg_read(UC_ARM_REG_LR) == HOOK + 5, "Dispatch must preserve original BL return")
            uc.emu_stop()
        else:
            require(any(start <= address and address + size <= end for start, end in function_ranges),
                    f"Execution outside linked target functions: {address:#x}")
            if address == renderer:
                require(not captured, "Renderer called more than once")
                pointer = uc.reg_read(UC_ARM_REG_R1)
                require(STACK_BASE <= pointer and pointer + 76 <= STACK_POINTER, "Brain must live on stack")
                require(uc.reg_read(UC_ARM_REG_R0) == FRAMEBUFFER, "Wrong renderer framebuffer")
                brain = bytes(uc.mem_read(pointer, 76))
                captured.update(activation=list(struct.unpack_from("<32h", brain)),
                                brain_hex=brain.hex(), epoch=struct.unpack_from("<I", brain, 68)[0],
                                state=brain[72], captured_tick=uc.reg_read(UC_ARM_REG_R2),
                                captured_buttons=uc.reg_read(UC_ARM_REG_R3))

    def on_read(uc: Uc, _access: int, address: int, size: int, _value: int, _: Any) -> None:
        nonlocal framebuffer_accesses, rtc_index
        if address < FRAMEBUFFER + FRAMEBUFFER_SIZE and address + size > FRAMEBUFFER:
            framebuffer_accesses += 1
        if 0x40000000 <= address < 0x60000000:
            peripheral_reads.append([address, size])
            require(size == 4 and address in (*pdir, RTC_SECONDS, RTC_PRESCALER),
                    f"Unapproved peripheral read: {address:#x}/{size}")
            if address in (RTC_SECONDS, RTC_PRESCALER):
                require(rtc_index < len(rtc_values), "RTC read exceeds supplied bounded samples")
                expected_address, value = rtc_values[rtc_index]
                require(address == expected_address, "RTC sample read order differs")
                rtc_index += 1
                # Harness supplies a read-only peripheral result; this is not a target write.
                uc.mem_write(address, struct.pack("<I", value))
            else:
                value = pdir[address]
            peripheral_values.append([address, value])

    def on_write(uc: Uc, _access: int, address: int, size: int, value: int, _: Any) -> None:
        nonlocal framebuffer_accesses
        write_trace.append([uc.reg_read(UC_ARM_REG_PC), address, size, value])
        if 0x40000000 <= address < 0x60000000:
            peripheral_writes.append([address, size, value])
        if FRAMEBUFFER <= address and address + size <= FRAMEBUFFER + FRAMEBUFFER_SIZE:
            write_counts["framebuffer"] += 1
            framebuffer_accesses += 1
            written[address - FRAMEBUFFER:address - FRAMEBUFFER + size] = b"\x01" * size
        elif STACK_BASE <= address and address + size <= STACK_POINTER:
            write_counts["stack"] += 1
        else:
            outside_writes.append([address, size, value])
            raise ValueError(f"Target write outside framebuffer/stack: {address:#x}/{size}")

    machine.hook_add(UC_HOOK_CODE, on_code)
    machine.hook_add(UC_HOOK_MEM_READ, on_read)
    machine.hook_add(UC_HOOK_MEM_WRITE, on_write)
    machine.emu_start(HOOK | 1, 0, count=INSTRUCTION_CAP)
    require(len(dispatch_calls) == 1, "Instruction cap reached without original dispatch")
    framebuffer = bytes(machine.mem_read(FRAMEBUFFER, FRAMEBUFFER_SIZE))
    points_data = bytes(machine.mem_read(symbols["fly_brain_points"]["address"], 64))
    points = [list(points_data[i:i + 2]) for i in range(0, 64, 2)]
    verified = verify_neuron_cells(framebuffer, captured["activation"], points) if eligible else 0
    result = dict(eligible=eligible, framebuffer_null=framebuffer_null, backend=backend, startup=startup,
                  pressed_mask=pressed_mask, initial_fill=fill, rtc_samples=samples,
                  instruction_count=instruction_count, instruction_cap=INSTRUCTION_CAP,
                  dirty_calls=dirty_calls, dispatch_calls=dispatch_calls,
                  peripheral_reads=peripheral_reads, peripheral_read_values=peripheral_values,
                  peripheral_writes=peripheral_writes, outside_writes=outside_writes,
                  write_counts=dict(write_counts), memory_write_count=len(write_trace),
                  memory_write_trace_sha256=sha256(json.dumps(write_trace, separators=(",", ":")).encode()),
                  framebuffer_bytes_written=sum(written), framebuffer_accesses=framebuffer_accesses,
                  framebuffer=framebuffer, framebuffer_sha256=sha256(framebuffer),
                  input_sentinel_remaining=framebuffer.count(fill),
                  all_pixels_monochrome=all(value in (0, 255) for value in framebuffer),
                  foreground_zero_bytes=framebuffer.count(0), background_ff_bytes=framebuffer.count(255),
                  guard_before_unchanged=bytes(machine.mem_read(FRAMEBUFFER - GUARD_SIZE, GUARD_SIZE)) == guard_before,
                  guard_after_unchanged=bytes(machine.mem_read(FRAMEBUFFER + FRAMEBUFFER_SIZE, GUARD_SIZE)) == guard_after,
                  callee_saved_registers_preserved=all(machine.reg_read(reg) == val for reg, val in initial.items()),
                  stack_pointer_restored=machine.reg_read(UC_ARM_REG_SP) == STACK_POINTER,
                  maximum_runtime_stack_bytes=STACK_POINTER - minimum_sp,
                  verified_neuron_cells=verified, neuron_points=points,
                  executed_cross_segment_branches=[pair for pair in bundle.manifest["stack_audit"]["cross_segment_branches"] if pair[0] in executed],
                  **captured)
    validate_result(result)
    return result


def validate_result(result: dict) -> None:
    for key in ("guard_before_unchanged", "guard_after_unchanged",
                "callee_saved_registers_preserved", "stack_pointer_restored"):
        require(result[key], f"Failed target invariant: {key}")
    require(not result["outside_writes"] and not result["peripheral_writes"], "Forbidden target writes")
    require(result["dispatch_calls"] == [[0 if result["framebuffer_null"] else FRAMEBUFFER, 0]], "Wrong dispatch ABI")
    require(result["maximum_runtime_stack_bytes"] <= STACK_LIMIT, "Runtime stack bound exceeded")
    if result["eligible"]:
        require(result["dirty_calls"] == [[0, 0, 240, 240]], "Wrong full-screen dirty ABI")
        require(result["framebuffer_bytes_written"] == FRAMEBUFFER_SIZE and result["all_pixels_monochrome"],
                "Renderer does not own the full binary-palette framebuffer")
        if result["initial_fill"] not in (0, 255):
            require(result["input_sentinel_remaining"] == 0, "Sentinel framebuffer byte remains")
        samples = result["rtc_samples"]
        attempts = 1 if samples[0][0] == samples[0][2] else 2
        require(len(samples) >= attempts, "Missing retry sample")
        expected_reads = [[GPIOA_PDIR, 4], [GPIOC_PDIR, 4], [GPIOD_PDIR, 4]] + [
            [RTC_SECONDS, 4], [RTC_PRESCALER, 4], [RTC_SECONDS, 4]] * attempts
        require(result["peripheral_reads"] == expected_reads, "Unexpected peripheral sampling count/order")
        before, prescaler, after = samples[attempts - 1]
        expected_tick = (((after << 15) | (prescaler & 0x7FFF)) & 0xFFFFFFFF) if before == after else 0xFFFFFFFF
        require(result["captured_tick"] == expected_tick, "Wrong bounded RTC tick")
        require(result["captured_buttons"] == result["pressed_mask"], "Incorrect active-low GPIO normalization")
        require(result["verified_neuron_cells"] == 32, "Not all neuron cells checked")
    else:
        require(not result["dirty_calls"] and not result["peripheral_reads"] and not result["framebuffer_accesses"],
                "Guard-false path accesses framebuffer or peripherals")


def host_oracle(build: Path, tick: int, buttons: int, *, retained: bool = False) -> dict:
    """Compile an isolated deterministic MinGW oracle for an exact fixture.

    Only target-build validation opts into the retained namespace. Ordinary
    verification always writes under oracle/tests, including identical fixtures.
    """
    require(0 <= tick <= 0xFFFFFFFF and 0 <= buttons <= 31, "Invalid host oracle fixture")
    target = subprocess.run(["gcc", "-dumpmachine"], check=True, capture_output=True, text=True).stdout.strip()
    linker_help = subprocess.run(["gcc", "-Wl,--help"], capture_output=True, text=True)
    help_text = linker_help.stdout + linker_help.stderr
    require("mingw" in target and linker_help.returncode == 0 and
            ("--no-insert-timestamp" in help_text or "--[no-]insert-timestamp" in help_text),
            "Deterministic host oracle requires MinGW GCC/ld with --no-insert-timestamp support")
    fixture = f"tick-{tick:08x}-buttons-{buttons:02x}"
    oracle_root = build.resolve() / "oracle" / ("retained" if retained else "tests") / fixture
    oracle_root.mkdir(parents=True, exist_ok=True)
    source = oracle_root / "host-oracle.c"
    source.write_text('''#include <stdio.h>
#include <stdlib.h>
#include "fly/brain32.h"
#include "display/brain_ascii.h"
int main(int argc, char **argv) {
    FlyBrain32 brain;
    unsigned char fb[57600];
    if (argc != 4) return 2;
    uint32_t tick = (uint32_t)strtoul(argv[1], 0, 0);
    uint8_t buttons = (uint8_t)strtoul(argv[2], 0, 0);
    fly_brain32_reconstruct(&brain, 0x46594f53u, tick, buttons);
    fly_brain_ascii_render(fb, &brain, tick, buttons);
    FILE *output = fopen(argv[3], "wb");
    if (!output) return 3;
    int ok = fwrite(fb, 1, sizeof(fb), output) == sizeof(fb) &&
             fwrite(&brain, 1, sizeof(brain), output) == sizeof(brain);
    return fclose(output) == 0 && ok ? 0 : 4;
}
''', encoding="ascii")
    executable = oracle_root / "host-oracle.exe"
    output = oracle_root / "host-oracle.bin"
    command = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "flyos"),
               str(source), str(ROOT / "flyos/fly/brain32.c"), str(ROOT / "flyos/display/brain_ascii.c"),
               "-Wl,--no-insert-timestamp", "-o", str(executable)]
    compiled = subprocess.run(command, capture_output=True, text=True)
    require(compiled.returncode == 0,
            "Deterministic MinGW oracle compile/link failed with --no-insert-timestamp: " + compiled.stderr)
    pe = executable.read_bytes()
    require(pe[:2] == b"MZ" and len(pe) >= 0x40, "Host oracle is not a MinGW PE executable")
    pe_offset = struct.unpack_from("<I", pe, 0x3C)[0]
    require(pe[pe_offset:pe_offset + 4] == b"PE\0\0" and len(pe) >= pe_offset + 12,
            "Host oracle has an invalid PE header")
    timestamp = struct.unpack_from("<I", pe, pe_offset + 8)[0]
    require(timestamp == 0, "MinGW linker did not honor --no-insert-timestamp")
    subprocess.run([str(executable), str(tick), str(buttons), str(output)], check=True, capture_output=True)
    data = output.read_bytes()
    require(len(data) == FRAMEBUFFER_SIZE + 76, "Wrong host oracle output size")
    return dict(framebuffer=data[:FRAMEBUFFER_SIZE], activation=list(struct.unpack_from("<32h", data, FRAMEBUFFER_SIZE)),
                framebuffer_sha256=sha256(data[:FRAMEBUFFER_SIZE]), command=command,
                compiler_target=target, pe_timestamp=timestamp, tick=tick, buttons=buttons,
                source_path=source.relative_to(ROOT).as_posix(),
                executable_path=executable.relative_to(ROOT).as_posix(),
                output_path=output.relative_to(ROOT).as_posix(),
                source_sha256=sha256(source.read_bytes()), executable_sha256=sha256(pe), output_sha256=sha256(data),
                artifacts={path.relative_to(ROOT).as_posix(): sha256(path.read_bytes())
                           for path in (source, executable, output)})


def public_result(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "framebuffer"}


def generate_report(build: Path, report_path: Path, preview_path: Path | None) -> dict:
    build = build.resolve()
    report_path = report_path.resolve()
    preview_path = preview_path.resolve() if preview_path is not None else None
    bundle = load_build(build)
    cases = {}
    for name, options in (
        ("released", {}), ("light", {"pressed_mask": 1}), ("start", {"pressed_mask": 2}),
        ("back", {"pressed_mask": 4}), ("down", {"pressed_mask": 8}), ("up", {"pressed_mask": 16}),
        ("all_buttons", {"pressed_mask": 31}), ("repeat_other_sentinel", {"fill": 0xA5}),
        ("later_tick", {"rtc_samples": [(123, 0xA006, 123)]}),
        ("rollover", {"rtc_samples": [(100, 0xFFFF, 101), (101, 3, 101)]}),
        ("second_mismatch", {"rtc_samples": [(100, 0xFFFF, 101), (101, 0x8004, 102)]}),
        ("null_framebuffer", {"framebuffer_null": True}), ("wrong_backend", {"backend": 0}),
        ("startup_zero", {"startup": 0}), ("startup_two", {"startup": 2}),
    ):
        cases[name] = emulate(bundle, **options)
    # load_build already validated every retained byte against its manifest.
    # Report generation reads the retained fixture rather than recompiling it.
    oracle = dict(bundle.manifest["retained_oracle"])
    oracle["framebuffer"] = (ROOT / oracle["output_path"]).read_bytes()[:FRAMEBUFFER_SIZE]
    require(oracle["tick"] == cases["released"]["captured_tick"] and oracle["buttons"] == 0,
            "Retained host oracle fixture differs from the report fixture")
    require(oracle["framebuffer"] == cases["released"]["framebuffer"] and
            oracle["activation"] == cases["released"]["activation"], "Host C oracle mismatch")
    require(cases["released"]["framebuffer"] == cases["repeat_other_sentinel"]["framebuffer"], "Nondeterministic framebuffer")
    require(cases["released"]["framebuffer"] != cases["later_tick"]["framebuffer"], "No tick evolution")
    covered = {tuple(pair) for result in cases.values() for pair in result["executed_cross_segment_branches"]}
    required = set(map(tuple, bundle.manifest["stack_audit"]["cross_segment_branches"]))
    require(covered == required, "An inter-allocation branch was not executed")
    report = dict(status="PASS_OFFLINE_ONLY", link_and_emulate_allowed=True,
                  packaging_allowed=bundle.manifest["packaging_allowed"],
                  placement_sha256=bundle.manifest["placement_sha256"], build_manifest=bundle.manifest,
                  cases={name: public_result(result) for name, result in cases.items()},
                  deterministic_framebuffer=True, evolving_framebuffer=True,
                  host_shared_c_oracle={**public_result(oracle), "activation_matches": True, "framebuffer_matches": True},
                  cross_segment_branches_all_executed=True,
                  rtc_second_mismatch_policy="Return 0xffffffff invalid sentinel after exactly six reads; never use a mixed tick",
                  limitations=["External dirty and dispatch implementations are intercepted at function entry.",
                               "Target stack bound excludes stock callees and interrupt frames; live Garmin task headroom remains unknown.",
                               "No hardware scheduling, DMA, FlexIO, LCD, installer, or boot/recovery execution is modeled.",
                               "Placement evidence allows only offline linking/emulation; installable packaging remains prohibited."])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    outputs = [report_path]
    if preview_path is not None:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(b"P5\n240 240\n255\n" + cases["released"]["framebuffer"])
        outputs.append(preview_path)
    outputs += [build / name for name in (ELF_NAME, "manifest.json", "hook.bin", "primary.bin", "secondary.bin")]
    outputs += [ROOT / name for name in oracle["artifacts"]]
    (report_path.parent / "neural-overlay-SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path.read_bytes())}  {path.relative_to(ROOT).as_posix()}\n" for path in outputs), encoding="ascii")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-build", type=Path)
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--placement", type=Path, default=PLACEMENT)
    parser.add_argument("--expected-placement-sha256")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the complete offline report case set using temporary outputs",
    )
    args = parser.parse_args()
    if sum(bool(value) for value in (args.check_build, args.report, args.self_test)) != 1:
        parser.error("Use exactly one of --check-build, --report, or --self-test")
    if args.check_build:
        manifest = check_build(args.check_build, args.placement, args.expected_placement_sha256)
        print(json.dumps({key: manifest[key] for key in ("segments", "stack_bound_bytes", "packaging_allowed")}, indent=2))
    elif args.report:
        report = generate_report(args.build, args.report, args.preview)
        print(json.dumps(dict(status=report["status"], cases=len(report["cases"]),
                              stack_bound_bytes=report["build_manifest"]["stack_bound_bytes"],
                              packaging_allowed=report["packaging_allowed"])))
    elif args.self_test:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            report = generate_report(
                args.build, Path(directory) / "self-test-report.json", None
            )
        print(json.dumps(dict(status=report["status"], cases=len(report["cases"]),
                              stack_bound_bytes=report["build_manifest"]["stack_bound_bytes"],
                              packaging_allowed=report["packaging_allowed"])))
    else:
        raise AssertionError("argument exclusivity was not enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
