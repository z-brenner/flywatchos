#!/usr/bin/env python3
"""Offline model of the FR245 13.70 five-button GPIO snapshot.

The constants come from the five-row key table at runtime address 0x0000F9BC
and the GPIOx_PDIR address calculation in the interrupt handler at 0x0000F688.
This module never opens a device or performs memory-mapped I/O.
"""

from __future__ import annotations

from collections.abc import Callable


GPIOA_PDIR = 0x400FF010
GPIOC_PDIR = 0x400FF090
GPIOD_PDIR = 0x400FF0D0

# Internal key index, PDIR address, pin mask.  Only index zero has a supported
# physical-label inference (LIGHT/power); retain numeric names for the rest.
BUTTONS = (
    (0, GPIOC_PDIR, 1 << 11),
    (1, GPIOD_PDIR, 1 << 10),
    (2, GPIOD_PDIR, 1 << 1),
    (3, GPIOA_PDIR, 1 << 20),
    (4, GPIOA_PDIR, 1 << 22),
)


def decode_snapshot(gpioa_pdir: int, gpioc_pdir: int, gpiod_pdir: int) -> int:
    """Return a five-bit active-low state from one snapshot of each port."""
    ports = {
        GPIOA_PDIR: gpioa_pdir,
        GPIOC_PDIR: gpioc_pdir,
        GPIOD_PDIR: gpiod_pdir,
    }
    state = 0
    for index, address, mask in BUTTONS:
        if ports[address] & mask == 0:
            state |= 1 << index
    return state


def read_snapshot(read32: Callable[[int], int]) -> int:
    """Read each required PDIR once, then decode without any write callback."""
    gpioa = read32(GPIOA_PDIR)
    gpioc = read32(GPIOC_PDIR)
    gpiod = read32(GPIOD_PDIR)
    return decode_snapshot(gpioa, gpioc, gpiod)

