# Watch readiness: button redraw and USB return

## What this milestone establishes

The public host controller now retains button-dirty work after a rejected
submission, coalesces newer input without replenishing a bounded retry budget,
and refuses to acknowledge newer input with an older displayed-frame token.
It has six reproducible fault traces and adversarial C tests. **This controller
is a proposal running in ordinary host memory, not an installed-watch fix.**
No target files, firmware safety gates, packaging or on-watch behavior change.
The historical reported installation was synthetic 13.76; the present build
is unknown unless independently established. A restore filename is not proof
of what is installed.

## Distinguish four boundaries

| Boundary | Documented target source | What the host tests can establish |
|---|---|---|
| Initial key ownership | START/DOWN/UP require stable HOME, USB cache outside 3/4, and BACK not held. LIGHT/BACK pass through. | Native and rejected routes do not create proposed FlyOS dirty work. |
| Queue submission | Ownership is set before `request_redraw`; unavailable queue or ignored send result does not roll ownership back. | A rejected synthetic submission leaves work pending, spends one bounded attempt and is never a display acknowledgment. |
| Later rendering | Release can leave one pulse if HOME still qualifies; rendering clears pulses before physical presentation is known. | Newer input invalidates older tokens; eligible retry opportunities must be supplied explicitly. |
| Visible presentation | A queued message or renderer call alone does not prove pixels reached the screen. | Only an explicitly supplied current HOME-display acknowledgment completes modeled work. |

These source facts are inspectable in
[`overlay.c`](../flyos/target/fr245_1370_neural_specimen_n64_controls/overlay.c)
(`flyos_key_event`, `request_redraw`, `n64_overlay_then_flush`) and
[`renderer.c`](../flyos/target/fr245_1370_neural_specimen_n64_controls/renderer.c)
(`footer`). No private firmware is needed for the host tests or this guide.
The controller does not emulate the native queue or its message ABI. Rejection
is an injected fault, not a measured queue occupancy or a diagnosis of the
reported USB delay. The target does not currently retain a redraw retry job.

## Reproduce the fault report

From the repository root, using the toolchain in [CI instructions](../ci/README.md):

```sh
cmake -S flyos -B flyos/build/watch-readiness -DCMAKE_BUILD_TYPE=Debug
cmake --build flyos/build/watch-readiness --parallel 2
ctest --test-dir flyos/build/watch-readiness --output-on-failure
flyos/build/watch-readiness/flyos-redraw-fault-trace > flyos/build/watch-readiness/redraw-faults.json
python flyos/tests/test_redraw_fault_trace.py flyos/build/watch-readiness/flyos-redraw-fault-trace
```

On Windows, the executable may be under `Debug/` and have an `.exe` suffix.
The JSON records ordered operations, routing, generations, attempt counts,
pending/exhausted flags, enqueue acceptance and display acknowledgment. It has
no watch addresses, elapsed-time claims or personal data. The six scenarios are:

1. Owned button: reject, accept on a later eligible opportunity, then display.
2. Native press: no FlyOS dirty work or submission.
3. Newer input: an older displayed token cannot complete the new work.
4. USB return: cached USB, native view and unsafe callback each block attempts;
   only a later eligible callback submits.
5. Permanent rejection: bounded attempts leave unfinished work visible.
6. Acceptance without presentation: the same bound applies; acceptance is not success.

Additional C tests cover all budgets 0–8, 18,000 repeated dirty requests with
both queue outcomes, route rejection, lifecycle cancellation, missing retry
opportunities, mutex/snapshot guards and generation overflow. The tests are
sequential specifications. They do not establish target concurrency, timing,
atomic storage, callback lifetime or eventual delivery. No automatic retry
runs without a modeled eligible callback; button input cannot defeat that rule.

## Minimal observation during ordinary use

This checklist only observes the already installed watch. It does not require
an update, files, debug mode, or a specially repeated USB cycle.

1. Note the visible face and current version if already known; otherwise write
   **unknown**. Use the next ordinary safe USB disconnect, or an issue already
   occurring. Do not interrupt a transfer/update or reconnect just to reproduce.
2. Note disconnect time and whether the screen shows FlyOS, a native charging
   or status image, or another view. If an update/confirmation/recovery screen
   or active workout appears, stop this checklist.
3. On an ordinary status/home screen only, optionally tap bottom-left **DOWN**
   once and release fully, leaving BACK untouched. Record the tap/release time.
   Avoid START here because it can confirm a native prompt. A native DOWN action
   is possible; this is not a guaranteed passive diagnostic.
4. Watch without more presses for about 20–30 seconds. Note when FlyOS appears
   and its first readable footer. This is an observation window, not a claimed
   recovery deadline. No repeat tap is needed if nothing changes.
5. After that window, on an ordinary status/home view only, an optional brief
   top-left **LIGHT** tap can distinguish brightness from changed content.
   Record those separately. Do not hold buttons or try recovery combinations.

A watch-only video kept locally may catch a brief footer. No upload, logs,
activity files, device identifiers or serial numbers are needed.

### Interpreting the observation

- `DOWN>CALM` appearing after DOWN was fully released, before another DOWN press,
  supports accepted input with delayed feedback **if the documented source is
  installed**. A footer while held is weaker evidence: raw physical button
  sampling also drives the renderer. Preexisting pulse/history ambiguity remains.
- An immediate native Garmin action supports pass-through; it does not identify
  which initial gate failed.
- No visible response is inconclusive. HOME could fail at release, a new press
  could erase a pulse, another footer could mask it, or rendering/presentation
  might never occur. A screenshot is not an internal event trace.
- LIGHT changing brightness on the same image demonstrates backlight response
  only. LIGHT's footer has higher priority than DOWN, and that render can still
  clear DOWN's pulse. This is why LIGHT comes after the initial observation.
- Eventual visible recovery establishes only that the display recovered. It
  does not reveal USB cache state, queue result, native first-visible view,
  callback scheduling, or the cause of a delay.

Optional local note: build known/unknown; initial screen; disconnect time;
DOWN press/release times; first changed screen time; first footer; LIGHT time
and brightness/content change separately. Omit any identifier or personal content.

## What would be needed for an actual target fix

A retry needs proven retained-state ownership plus a safe, independently
scheduled callback and a valid queue-message contract. A completion token would
also need a defensible presentation acknowledgment; simply clearing a pulse
inside the renderer is not that proof. These are unresolved target conditions,
not supplied by the host model. This milestone does not establish those proofs.

The source-only change justified here is better host rejection handling and
more accurate diagnostic documentation. The watch's initial USB-return cause
remains unknown. Existing target NO-GO decisions stay in force; this guide is
not permission to flash a diagnostic or restoration image. See the
[installed-overlay diagnosis](installed-overlay-ux-diagnosis.md) and
[static follow-up](atlas-shell-static-followup.md) for existing boundaries.
