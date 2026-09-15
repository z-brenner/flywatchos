#!/usr/bin/env python3
"""Decode the FR245 display FlexIO configuration tables from preserved firmware.

This is an offline, version-locked extractor.  It accepts only the two known
non-Music firmware streams whose hashes are recorded below and never opens a
device path.  Register construction follows NXP's fsl_flexio.c implementation
at commit 8a289764d763ad06e0c3a05c885644ed98b970af.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


IMAGE_BASE = 0x3000
FLEXIO0_BASE = 0x400DF000

VERSIONS = {
    "3.10": {
        "sha256": "3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba",
        "init_function": 0x000BF84C,
        "timer_configs": {
            0: 0x000BFC90,
            1: 0x000BFBA0,
            2: 0x000BFD30,
            3: 0x000BFC74,
            4: 0x000BFBF0,
            5: 0x000BFC24,
            6: 0x000BFB18,
            7: 0x000BFB4C,
        },
        "shifter_configs": {
            0: 0x000BFB34,
            2: 0x000BFC5C,
            3: 0x000BFBD8,
            4: 0x000BFC0C,
        },
        "runtime_timer2_config": 0x000BFD14,
    },
    "13.70": {
        "sha256": "b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6",
        "init_function": 0x0000EC04,
        "timer_configs": {
            0: 0x0000F048,
            1: 0x0000EF58,
            2: 0x0000F0E8,
            3: 0x0000F02C,
            4: 0x0000EFA8,
            5: 0x0000EFDC,
            6: 0x0000EED0,
            7: 0x0000EF04,
        },
        "shifter_configs": {
            0: 0x0000EEEC,
            2: 0x0000F014,
            3: 0x0000EF90,
            4: 0x0000EFC4,
        },
        "runtime_timer2_config": 0x0000F0CC,
    },
}

TIMER_MODE = {
    0: "disabled",
    1: "dual_8bit_baud_bit",
    2: "dual_8bit_pwm",
    3: "single_16bit",
    6: "dual_8bit_pwm_low",
}
TIMER_OUTPUT = {
    0: "one_not_affected_by_reset",
    1: "zero_not_affected_by_reset",
    2: "one_affected_by_reset",
    3: "zero_affected_by_reset",
}
TIMER_DECREMENT = {
    0: "flexio_clock_shift_timer_output",
    1: "trigger_both_edges_shift_timer_output",
    2: "pin_both_edges_shift_pin_input",
    3: "trigger_both_edges_shift_trigger_input",
}
TIMER_RESET = {
    0: "never",
    2: "pin_equals_output",
    3: "trigger_equals_output",
    4: "pin_rising_edge",
    6: "trigger_rising_edge",
    7: "trigger_both_edges",
}
TIMER_DISABLE = {
    0: "never",
    1: "previous_timer_disable",
    2: "compare",
    3: "compare_and_trigger_low",
    4: "pin_both_edges",
    5: "pin_both_edges_and_trigger_high",
    6: "trigger_falling_edge",
}
TIMER_ENABLE = {
    0: "always",
    1: "previous_timer_enable",
    2: "trigger_high",
    3: "trigger_high_and_pin_high",
    4: "pin_rising_edge",
    5: "pin_rising_edge_and_trigger_high",
    6: "trigger_rising_edge",
    7: "trigger_both_edges",
}
PIN_CONFIG = {
    0: "output_disabled",
    1: "open_drain_or_bidirectional",
    2: "bidirectional_output_data",
    3: "output",
}
SHIFTER_MODE = {
    0: "disabled",
    1: "receive",
    2: "transmit",
    4: "match_store",
    5: "match_continuous",
    6: "state",
    7: "logic",
}


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def enum(value: int, names: dict[int, str]) -> dict[str, int | str]:
    return {"raw": value, "name": names.get(value, "unknown")}


def trigger_name(value: int) -> str:
    if value & 1 == 0:
        return f"pin_input_{value >> 1}"
    if value & 3 == 1:
        return f"shifter_status_{value >> 2}"
    return f"timer_{value >> 2}"


def decode_timer(blob: bytes, va: int) -> dict:
    raw = blob[va - IMAGE_BASE : va - IMAGE_BASE + 28]
    if len(raw) != 28:
        raise ValueError(f"timer config at 0x{va:08x} is truncated")

    values = {
        "trigger_select": u32(raw, 0),
        "trigger_polarity": raw[4],
        "trigger_source": raw[5],
        "pin_config": raw[6],
        "pin_select": u32(raw, 8),
        "pin_polarity": raw[12],
        "timer_mode": raw[13],
        "timer_output": raw[14],
        "timer_decrement": raw[15],
        "timer_reset": raw[16],
        "timer_disable": raw[17],
        "timer_enable": raw[18],
        "timer_stop": raw[19],
        "timer_start": raw[20],
        "timer_compare": u32(raw, 24),
    }

    timctl = (
        ((values["trigger_select"] & 0x3F) << 24)
        | ((values["trigger_polarity"] & 1) << 23)
        | ((values["trigger_source"] & 1) << 22)
        | ((values["pin_config"] & 3) << 16)
        | ((values["pin_select"] & 0x1F) << 8)
        | ((values["pin_polarity"] & 1) << 7)
        | (values["timer_mode"] & 3)
    )
    timcfg = (
        ((values["timer_output"] & 3) << 24)
        | ((values["timer_decrement"] & 3) << 20)
        | ((values["timer_reset"] & 7) << 16)
        | ((values["timer_disable"] & 7) << 12)
        | ((values["timer_enable"] & 7) << 8)
        | ((values["timer_stop"] & 3) << 4)
        | ((values["timer_start"] & 1) << 1)
    )

    return {
        "config_va": f"0x{va:08x}",
        "raw_hex": raw.hex(),
        "registers": {
            "TIMCTL": f"0x{timctl:08x}",
            "TIMCFG": f"0x{timcfg:08x}",
            "TIMCMP": f"0x{values['timer_compare'] & 0xFFFF:04x}",
        },
        "fields": {
            "trigger": {
                "raw": values["trigger_select"],
                "name": trigger_name(values["trigger_select"]),
                "polarity": "active_low" if values["trigger_polarity"] else "active_high",
                "source": "internal" if values["trigger_source"] else "external",
            },
            "pin_config": enum(values["pin_config"], PIN_CONFIG),
            "pin_select": values["pin_select"],
            "pin_polarity": "active_low" if values["pin_polarity"] else "active_high",
            "timer_mode": enum(values["timer_mode"], TIMER_MODE),
            "timer_output": enum(values["timer_output"], TIMER_OUTPUT),
            "timer_decrement": enum(values["timer_decrement"], TIMER_DECREMENT),
            "timer_reset": enum(values["timer_reset"], TIMER_RESET),
            "timer_disable": enum(values["timer_disable"], TIMER_DISABLE),
            "timer_enable": enum(values["timer_enable"], TIMER_ENABLE),
            "timer_stop_raw": values["timer_stop"],
            "timer_start_raw": values["timer_start"],
            "timer_compare": values["timer_compare"] & 0xFFFF,
        },
    }


def decode_shifter(blob: bytes, va: int) -> dict:
    raw = blob[va - IMAGE_BASE : va - IMAGE_BASE + 24]
    if len(raw) != 24:
        raise ValueError(f"shifter config at 0x{va:08x} is truncated")

    values = {
        "timer_select": u32(raw, 0),
        "timer_polarity": raw[4],
        "pin_config": raw[5],
        "pin_select": u32(raw, 8),
        "pin_polarity": raw[12],
        "shifter_mode": raw[13],
        "parallel_width": u32(raw, 16),
        "input_source": raw[20],
        "shifter_stop": raw[21],
        "shifter_start": raw[22],
    }

    shiftctl = (
        ((values["timer_select"] & 7) << 24)
        | ((values["timer_polarity"] & 1) << 23)
        | ((values["pin_config"] & 3) << 16)
        | ((values["pin_select"] & 0x1F) << 8)
        | ((values["pin_polarity"] & 1) << 7)
        | (values["shifter_mode"] & 7)
    )
    shiftcfg = (
        ((values["parallel_width"] & 0x1F) << 16)
        | ((values["input_source"] & 1) << 8)
        | ((values["shifter_stop"] & 3) << 4)
        | (values["shifter_start"] & 3)
    )

    return {
        "config_va": f"0x{va:08x}",
        "raw_hex": raw.hex(),
        "registers": {
            "SHIFTCTL": f"0x{shiftctl:08x}",
            "SHIFTCFG": f"0x{shiftcfg:08x}",
        },
        "fields": {
            "timer_select": values["timer_select"],
            "timer_polarity": "negative" if values["timer_polarity"] else "positive",
            "pin_config": enum(values["pin_config"], PIN_CONFIG),
            "pin_select": values["pin_select"],
            "pin_polarity": "active_low" if values["pin_polarity"] else "active_high",
            "shifter_mode": enum(values["shifter_mode"], SHIFTER_MODE),
            "parallel_width_field": values["parallel_width"],
            "parallel_width_bits": values["parallel_width"] + 1,
            "input_source": "next_shifter_output" if values["input_source"] else "pin",
            "shifter_stop_raw": values["shifter_stop"],
            "shifter_start_raw": values["shifter_start"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--version", choices=sorted(VERSIONS), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    blob = args.image.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    spec = VERSIONS[args.version]
    if digest != spec["sha256"]:
        raise SystemExit(
            f"refusing unknown image: expected {spec['sha256']}, observed {digest}"
        )

    report = {
        "schema": "flyos.fr245.display-flexio-config.v1",
        "version": args.version,
        "image": str(args.image),
        "image_sha256": digest,
        "image_base": f"0x{IMAGE_BASE:08x}",
        "flexio_base": f"0x{FLEXIO0_BASE:08x}",
        "init_function": f"0x{spec['init_function']:08x}",
        "timers": {
            str(index): decode_timer(blob, va)
            for index, va in sorted(spec["timer_configs"].items())
        },
        "shifters": {
            str(index): decode_shifter(blob, va)
            for index, va in sorted(spec["shifter_configs"].items())
        },
        "runtime_timer2": decode_timer(blob, spec["runtime_timer2_config"]),
        "direct_initialization_writes": {
            "SHIFTBUF2": "0x00000002",
            "SHIFTBUF3": "0x55555555",
            "SHIFTBUF4": "0xffffffff",
            "SHIFTERR": "0x000000ff (write-one-to-clear)",
            "TIMSTAT": "0x000000ff (write-one-to-clear)",
        },
        "reference": {
            "sdk_commit": "8a289764d763ad06e0c3a05c885644ed98b970af",
            "driver": "drivers/flexio/fsl_flexio.c",
            "device_header": "devices/MK28FA15/MK28FA15.h",
        },
    }

    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
