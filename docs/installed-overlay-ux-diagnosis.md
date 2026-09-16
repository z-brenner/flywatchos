# Installed 13.76 overlay: button escape and stale USB view

The last user-observed installed build is synthetic 13.76. Its exact candidate
SHA-256 is `9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de`.
The watch has not provided an internal-flash readback. This diagnosis combines
the byte-pinned source and offline control-flow evidence with the user's live
reports; it does not claim a live event trace.

## Button escape is the current policy

`flyos_key_event` in
`flyos/target/fr245_1370_neural_specimen_n64_controls/overlay.c` handles only
key indices 1, 3, and 4: START, DOWN, and UP. LIGHT (index 0) and BACK (index
2) always call `flyos_key_pass`. The three handled keys also pass to Garmin
when USB mass-storage cache is 3/4, the input-ready GPIO guard is false, or
the bounded HOME check fails. The BACK chord intentionally routes a system
session to Garmin. Therefore entering Garmin menus with some buttons is
expected from the installed code, not evidence that the key hook failed.

Capturing all five buttons requires one stable owner for every press, hold,
repeat, and release while native update, recovery, notification, and other
views retain their controls. A per-event HOME check alone can split a sequence
when a view changes between press and release. The proposed five key-record
halfwords are not yet approved storage: startup zeroes them, and a computed
external-XIP bulk writer has an unresolved pointer range. The completed
classifier solves only the view-decision part of this problem. See
`docs/atlas-shell-static-followup.md`.

## The stale charging image is not drawn by the FlyOS renderer

The display hook samples byte `0x1FFC6F25` and passes `true` to `n64_render`
when it equals 3 or 4, but the exact installed renderer explicitly discards
that argument and has no charging graphic. On a stable HOME call it clears all
57,600 framebuffer bytes before drawing the FlyOS face. Therefore the user's
stale charging image cannot be attributed to a FlyOS-drawn charging label.

Static USB analysis identifies the cache byte as a narrow mass-storage state,
not a general power/charging measurement. On disconnect, state 3 can wait
behind an external readiness guard before testing detach; state 4 eventually
reaches teardown in one local path. Teardown does not directly flush the
display. Native UI lifecycle can take a no-render path that skips the FlyOS
hook at `0x9A20`. A previously drawn native charging screen could therefore
remain visible without a later display transfer. A charging modal could also
remain first-visible. Current evidence cannot distinguish those paths or
establish the exact live cause.

The user's additional live observation on 2026-09-16 narrows the symptom:
after USB removal, pressing top-right START made no immediate visible change,
but the FlyOS face returned by itself after **more than ten seconds**. The
charger view therefore is delayed, not permanently stuck. The observation
does not identify whether native view teardown, event scheduling, or display
submission accounts for that delay.

## Current host observation

On 2026-09-16, read-only PowerShell checks found one present Garmin USB
`091e:2c04` mass-storage node and a Healthy FAT `GARMIN` volume at `D:`.
`D:\Garmin` contained `GarminDevice.xml` but neither `GUPDATE.GCD` nor
`force.tmp`. The debug error log was inspected only by a local keyword/count
script: 6,918 bytes, 474 lines, and zero literal matches for `HardFault`,
`assert`, `FlyOS`, or `USB`. The log and its hash remain local; no log contents,
identifiers, or personal files were copied to Git or sent to an external
service. These host facts establish normal enumeration,
not the watch's current on-screen state or update-service recovery under a
broken application.

## Next evidence that would change the decision

The decisive runtime observation is a bounded, privacy-preserving correlation
of physical USB detach, cached USB state, native first-visible view, watch-face
event `0xBF`, and display submission `0x9A20`. Existing HOME-only stateless
diagnostic bytes cannot make that correlation: a frozen panel is compatible
with a hidden native view, a missing UI event, a skipped flush, or a display
transfer issue. Its offline 13.78/13.79 pair remains quarantined and live use
is **NO-GO**. A safe alternative must either use a proven read-only native
telemetry path or close exclusive volatile-storage and redraw-context proofs
before proposing a new on-watch diagnostic.
