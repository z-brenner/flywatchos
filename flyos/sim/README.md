# Host-only input and redraw policy model

`host_policy.c` is a portable C11 executable specification for conservative
input routing and redraw scheduling. It runs in ordinary host memory, without
watch addresses, target hooks, hardware I/O, dynamic allocation, or threads.
It must not be linked into firmware. Neither this model nor its tests close any
of the target feasibility gates in `docs/atlas-shell-static-followup.md`.

## Input contract

A valid sequence is one press, zero or more repeats, and one release, with a
single owner chosen at the press:

- LIGHT always belongs to Garmin, retaining native backlight handling.
- BACK always belongs to Garmin, retaining the native system escape.
- START, DOWN, and UP belong to FlyOS only when the press observes ready input,
  a valid HOME snapshot, no narrow USB mass-storage state, and no active BACK.
- Invalid, unknown, or missing snapshots select Garmin at a fresh press.
- Later native view, readiness, USB, and BACK transitions cannot change the
  owner of an already active sequence. Releasing BACK does not capture an
  already-native chord member.
- Orphan repeats/releases, duplicate presses, and invalid key/phase values
  return `FLY_SIM_ROUTE_REJECTED` without changing the state or delivering an
  event to either consumer. Forwarding a malformed extra press to Garmin
  during a FlyOS-owned hold would itself introduce a split sequence.

`flyos_held` contains only FlyOS-owned active keys. A caller may use those bits
with the real host Brain64 model; native and rejected events must not be
reinterpreted as FlyOS stimuli. This is a conservative host policy, not an
implementation of the rejected synthetic 13.80 five-key target candidate.

The input context's view classification is supplied by a scenario. This module
does not walk native view memory or prove the snapshot classifier. In
particular, it cannot solve ABA changes or authorize the proposed target key
halfwords. Resetting this host object mid-sequence is outside its lifetime
contract and would discard ownership.

## Redraw contract

An observed physical attached-to-detached edge creates one increasing epoch
with pending work. Merely starting the simulation detached invents no edge.
Repeated observations of detached state do not reset the retry budget.
Reattachment cancels pending work and invalidates all outstanding tokens.
A new detach receives a fresh epoch and budget. Epoch overflow fails closed
without token reuse.

`fly_sim_redraw_step` returns at most one abstract submission per invocation.
It requires all of the following:

- Work is still pending and USB is physically detached.
- The view is valid HOME, with no narrow USB mass-storage state.
- The scenario explicitly identifies a safe callback.
- Both the source-list and USB mutexes are unlocked.
- The bounded total-attempt budget (0 through 8) is not spent.
- After the first attempt, the scenario explicitly provides a retry opportunity.

Every returned submission is marked nonblocking. The model never calls a queue,
waits for a lock, sleeps, or invokes a callback. `queue_accepts` describes the
simulated result of that attempt, not a recovered native queue API. A failed
submission and an accepted submission both spend one attempt. A native modal,
invalid view, stale USB state, unsafe callback, held mutex, or missing retry
opportunity does not spend one. Pending work survives all of those guards.

Enqueue acceptance does not complete the epoch. Only
`fly_sim_redraw_displayed` with the current epoch's latest successfully
accepted request token and an explicit HOME-display acknowledgment clears
pending. Rejected/never-enqueued requests, stale tokens, and native/invalid
displays cannot acknowledge it. A failed later enqueue does not invalidate
an earlier accepted token; a newer accepted enqueue supersedes it. This
latest-accepted-token rule is deliberately conservative. Display completion
is still possible after all attempts are spent. Exhaustion leaves pending
true and requests no more work; it does not claim success.

The acknowledgment is a scenario fact. A call to a renderer, display hook, or
queue does not by itself establish that fact on the watch. Likewise,
`retry_due` asserts a modeled scheduling opportunity with no milliseconds,
latency, timer-lifetime, or eventual-callback guarantee. Repeated accepted
requests may remain physically queued after cancellation; the host model only
rejects their obsolete acknowledgments and does not claim to cancel native
queue contents.

## Run the regression tests

With the CMake host targets registered:

```sh
cmake -S flyos -B /tmp/flyos-build
cmake --build /tmp/flyos-build
ctest --test-dir /tmp/flyos-build --output-on-failure
```

The policy tests can also run without CMake:

```sh
cc -std=c11 -Wall -Wextra -Wpedantic -Werror -Iflyos \
  flyos/tests/test_host_policy.c flyos/sim/host_policy.c \
  -o /tmp/flyos-host-policy-tests
/tmp/flyos-host-policy-tests
```

These tests cover exhaustive valid single-key/context transitions, native
LIGHT/BACK and BACK chords, malformed events, independent held keys, all
redraw guard combinations, retry bounds, modal preservation, cancellation,
queue-versus-display semantics, stale acknowledgments, and epoch overflow.
The assertions are about this host specification only. Target storage,
atomicity, task concurrency, native callback safety, queue semantics, detach
convergence, and actual display visibility remain unproved here.

## Replay exporter and one-shot pulses

`export_interaction_trace.c` combines this model with the existing Brain64 and
semantic-palette renderer. Its seven scenarios are deterministic executable
fixtures. A released FlyOS key retains one pending pulse until an eligible
HOME rendering. Native/invalid/USB frames neither consume that pulse nor
inject it into the neural step. An eligible HOME frame injects and clears it
once; subsequent frames do not repeat it. Multiple releases of the same key
before rendering coalesce into one bit, rather than forming an event queue.

The host network steps once per trace frame, including frames where the native
view prevents FlyOS rendering. Those steps are abstract samples, not elapsed
seconds or measured device scheduler ticks. Native view rendering is left
untouched by the C renderer; the lab places a clearly labeled placeholder over
that preserved framebuffer instead of inventing a Garmin screen. Battery 87%
is synthetic; other unbound sensors remain unavailable.
