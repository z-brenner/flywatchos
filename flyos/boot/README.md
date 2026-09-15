# K28F boot layer

This directory is intentionally documentation-only. A real vector table, linker script,
clock setup, watchdog policy, and external-memory initialization depend on facts not yet
recovered from the Forerunner 245 firmware. Adding guessed register writes would turn a
host proof of concept into misleading target firmware.

Expected target entry sequence:

1. establish the main stack and vector table;
2. copy initialized data and clear BSS;
3. configure watchdog and clocks using recovered values;
4. initialize only verified buses and memory;
5. enter the cooperative FlyOS loop.
