# Live-proof staging guard

`stage-gupdate.ps1` validates the exact candidate or official restore artifact,
the selected drive's association to a present Garmin FR245 USB disk and its
VID `091E` / PID `2C04` parent, the connected non-Music Forerunner 245 identity,
the expected currently reported software version, free space, volume health,
and the absence of an existing `GUPDATE.GCD`.

It defaults to a read-only dry run. `-Execute` is the only path that creates a
watch file. That path uses create-new semantics, flushes the file, reads it
back, and requires an exact SHA-256 match. If verification fails while the
watch is still connected, or if copying or flushing fails, it removes only the
newly created staging file and stops. If the volume disappears or cleanup
fails, it reports that cleanup could not be confirmed. The script never
ejects, resets, restarts, or accepts an update prompt.

Forced process termination, an operating-system crash, or a USB/power loss can
bypass the catch block. In those cases a partial `GUPDATE.GCD` may remain and
must be inspected before the watch is disconnected or restarted.

Dry-run candidate check:

```powershell
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1
```

Do not add `-Execute` unless the exact write has received the approval required
by `docs/live-proof-proposal.md`.

Offline-prepared forward-version profiles are also available for the later
executable experiment. Both expect the connected watch to report 13.70:

```powershell
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode ForwardOverlay1371
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode ForwardRestore1372
```

These remain dry runs unless `-Execute` is supplied. Version 13.71/13.72 are
synthetic admission metadata, not Garmin releases. The 13.72 wrapper carries
official 13.70 application code and resources except for its main image header
version and one additive repair byte. Neither profile supplies nonboot recovery.

After a successful 13.71 bounded-overlay experiment, the full-screen pair uses
the next two coherent synthetic main versions. Both profiles still expect the
watch's public report to remain 13.70:

```powershell
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode FullscreenOverlay1372
powershell -ExecutionPolicy Bypass -File tools/live-proof/stage-gupdate.ps1 `
  -Mode FullscreenRestore1373
```

The 13.72 candidate repaints the full 240 by 240 framebuffer and samples five
active-low button GPIOs. The 13.73 wrapper removes all custom executable bytes
and restores official 13.70 code and resources except for the synthetic image
header and additive repair byte. The wrapper requires a booting application,
normal USB mass storage, and a working GarminOS updater.
