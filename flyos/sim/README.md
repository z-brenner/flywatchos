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
semantic-palette renderer. Its nine scenarios are deterministic executable
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

## Bounded synthetic view classifier

`view_classifier.c` is a new public executable specification of the documented
list shape. It uses an injected reader of logical 32-bit words. The documented
addresses are integer fixture keys, never dereferenced as pointers. No native
reader or target adapter exists.

It captures at most eight aligned nodes twice, reading the root before and
after each capture and validating predecessor/successor consistency, cycles,
range and alignment. All four fields of all nodes, including hidden nodes,
must match across captures. The maximum is 68 reader calls, including failed
calls. A ninth node or invalid address is rejected without reading that node.
The upper address constant is an inclusive node base; its last flags word ends
at the documented RAM boundary. Only flag bit 0x2 controls visibility; other
bits are opaque and compared in full. Empty or all-hidden lists are INVALID.

A valid first visible HOME identity selects HOME; every other stable visible
identity selects NON_HOME. An arbitrary synthetic non-HOME value is not proof
of the historical update prompt. Missing readers, unreadable/unknown/partial
words, malformed lists, root changes and differing captures fail to INVALID.
The caller must return false for unknown or malformed logical words.

Two equal snapshots do not prove atomicity. Complete ABA changes restored
between samples, changes after the final sample, and adversarial repeated torn
observations can remain invisible. The explicit ABA replay intentionally
returns HOME and displays that limitation. This model does not reproduce
inaccessible private proof receipts, establish object allocation/lifetime,
prove target concurrency, or change any firmware feasibility gate.

## Persistent live C bridge

`live_bridge.c` is a single host-only bounded instance of the real Brain64,
semantic-palette renderer and conservative key policy. Native tests and the
WebAssembly build compile the same source. There is no JavaScript copy of the
neural equations. Compilation requires the host-preview definition; no target
hooks or storage assignments are provided.

The bridge has no dynamic allocation, I/O, clock, native callback or redraw
queue. Inputs and view context are supplied fixtures, validated before
mutation. The live selector does not invoke the classifier. Optional sensors
are cleared when unavailable, and values are bounded even when unavailable.
Held ownership survives context changes. Pending release pulses are delivered
only by one eligible HOME step; native/invalid/USB steps leave the framebuffer
and pulse untouched. Reset deliberately begins a new specimen and clears all
held input state.

The browser reads indexed pixels and signed activations from fixed WebAssembly
memory. It keeps at most 128 display snapshots and 16,384 recorded commands.
The complete command sequence, seed and recent snapshots are included in live
trace export. The command limit pauses the session and requires reset. Pausing stops automatic stepping while preserving held input for manual
steps. Hiding or leaving the sandbox releases controls; pointer-held chords survive
focus movement, while keyboard-held controls release on focus loss. Each
network step is abstract model time, not a measured watch or sensor interval.

Node/native differential tests compare every activation, framebuffer byte and
state field. DOM tests exercise the real Wasm but stub canvas rendering; they
are not browser layout, real-pointer-device or visual QA. The included preview
images/animation are generated from real C frames, not browser screenshots.

For a live or experiment bundle, `build_interaction_lab.py --wasm module.wasm`
requires the adjacent `module.wasm.json` produced by `build_live_wasm.py`.
The bundler checks the module byte count and SHA-256, the complete current
C/header/data/metadata source-hash set, and the host-only ABI contract. It then
runs the existing Node validator against the exact bytes it embeds, with a
30-second timeout. Use `--node /path/to/node` if Node is not on `PATH`.
Missing, stale, malformed or mismatched pairs fail before any bundle output;
rebuild and keep the module and sidecar together. Replay-only builds need
neither the pair nor Node. The verified manifest and its original byte hash
travel with the embedded artifact. These checks establish local provenance
consistency, not cryptographic attestation against a deliberately forged pair.

## Alternate published-topology model

The bridge now supports model 1, CX60, beside unchanged model 0 Brain64. Model
selection begins a fresh isolated host session and clears held input/history.
CX60 uses all 60 connected representative units and 326 edges of a pinned
published heading-circuit model, with explicit new fixed-point rate dynamics.
Watch keys/sensors retain policy telemetry but do not drive CX60; the separate
landmark/P-EN input API does not drive Brain64. Both expose the same stable
64-slot activation and 57,600-byte pixel buffers. Extra CX60 slots stay zero.

Connectivity getters expose the actual C graph and source strengths. JavaScript
only lays out and inspects those values; it does not reimplement the dynamics
or fabricate links. [`CX60.md`](CX60.md) documents every biological assumption,
source, equation, coefficient, input range and readout limitation.

## Measured anatomy lens

The page also embeds a static ER4m↔EPG cross-class projection from the Hulse
2021 hemibrain analysis tables. It contains 56 actual body IDs, 762 directed
supplied pairs and 16,774 EB synapses. It is separate from both C models:
entering the lens pauses playback and releases held controls, and cell search
or pair filtering never steps a network. It works without WebAssembly.

Arrows show supplied direction; counts are unsigned ROI synapse counts, not
fitted weights or efficacy. All-cell rings are schematic rather than physical
geometry. Within-class and external connections are not supplied. A missing
or filtered-out pair must not be interpreted as an anatomical zero. The
static export retains exact string body IDs, source attribution and explicit
filter scope, with no activation frames. Read the [source data contract](data/hulse2021/README.md)
for byte hashes, extraction rules, CC BY 4.0 attribution and limitations.

## Paired perturbation experiments

The experiment lens runs two isolated instances of the same real C/Wasm
module, with identical reset and fixed warm-up. A constant-input control is
paired with a bounded cue-shift, cue-loss or cue-plus-P-EN-drive intervention,
then both return to the original inputs. It does not modify CX60 dynamics or
advance the live specimen. Raw states, exact commands and descriptive metrics
travel in the export. All phases use abstract C steps, not measured time.

The [experiment contract](EXPERIMENTS.md) explains duplicate-normalized sector
profiles, coarse-peak ties, residual activity below the readout's integer
resolution, exact silence and fixed-point recovery differences. The comparison
is against the evolving same-time control, not an assumed equilibrium. This
is an implementation assay, not independent fly data or biological validation.
