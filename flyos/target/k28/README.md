# K28 target skeleton

This directory produces a freestanding Cortex-M4 ELF and flat binary linked at
the observed Forerunner 245 application base `0x3000`. Its 124-entry vector
table occupies `0x3000` through `0x31ef`, placing the reset code at `0x31f0`,
consistent with the official reset vector `0x31f1`.

The image initializes `.data` and `.bss`, runs the 64-neuron fixed-point fly,
and renders `FLY LIVES` into a RAM-only 240x240 logical framebuffer. Its
57,600-byte size now matches both analyzed official display buffers. The target
build also runs one row through the byte-exact 244-byte Garmin staging-row
converter and retains the result in RAM for inspection. It has no
clock, watchdog, power, display-transport, button, storage, or update wrapper
driver. It is therefore an offline structural proof and is not safe to install.

The provisional SRAM region and stack are constrained to the area suggested by
official application initial-stack values. They must be replaced with a proven
board memory map before live use.

Build from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File flyos/target/k28/build.ps1
```

Outputs remain in the ignored `flyos/target/k28/build/` directory.
