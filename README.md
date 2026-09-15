# FlyWatchOS

Reverse engineering and experimental firmware work for the Garmin Forerunner 245
(non-Music, HWID 3076). The current live result is a GarminOS-resident overlay
with a deterministic 64-neuron fruit-fly-inspired network and a full-screen
scientific display.

The project has **not** demonstrated a replacement bootloader, secure-boot
bypass, or standalone custom operating system. The present code executes inside
the official Garmin 13.70 application image through a researched overlay hook.
Recovery still depends on GarminOS booting and exposing USB mass storage, so
standalone firmware feasibility remains **YELLOW**.

## Repository map

- `flyos/` — host model, display renderer, persistence design, and FR245 target overlays
- `tools/garmin-firmware/` — GCD inspection, validation, emulation, allocation, and packaging tools
- `tools/live-proof/` — guarded live staging tool; write mode requires deliberate enablement
- `tools/device-backup/` — read-only backup helper
- `docs/` — device inventory, hardware research, firmware format, boot-chain, recovery, and live experiment reports

Private device backups, activity/GPS data, identifiers, official Garmin firmware,
modified GCD packages, analysis-custody artifacts, Ghidra projects, and locally
built binaries are intentionally excluded from Git.

## Current interface

The installed N64 experiment maps 64 simulated neurons directly to 64 rendered
cells. It uses a limited RGB222 palette and samples the five watch buttons, RTC,
cached battery percentage, and a narrow USB storage-state observation. Heart-rate,
motion, ambient-light, and charging telemetry are not yet bound to safe runtime
sources. Garmin screens can still appear because system/update/charging UI is
currently passed through by design.

See [the session report](docs/session-report.md), [N64 design](docs/superpowers/specs/2026-09-14-flyos-neural-specimen-n64-design.md),
and [recovery analysis](docs/recovery.md) for the evidence and limits.

## Host build

```powershell
cmake -S flyos -B flyos/build
cmake --build flyos/build
ctest --test-dir flyos/build --output-on-failure
```

The target builds require a local ARM toolchain and byte-pinned firmware evidence
that is deliberately absent from this public repository. Do not stage an update
image without reviewing the exact image, flash ranges, brick risk, and recovery
path for the connected device.

Garmin and Forerunner are trademarks of Garmin Ltd. This project is unaffiliated
with and unsupported by Garmin.
