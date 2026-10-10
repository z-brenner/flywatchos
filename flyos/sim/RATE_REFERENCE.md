# Source-equation rate reference

The **Rate reference** lens compares the existing fixed-point CX60 adaptation
with an independent implementation of the deterministic rate-equation core in
Pisokas, Heinze and Webb's published source. Both remain available. The measured
ER4m↔EPG anatomy lens remains static and does not supply these dynamics.

This reference preserves the source equation, fitted weights and integration
step. It deliberately disables noise and injects declared synthetic current.
It is not the publication's full experimental pipeline, a spiking model,
measured neuronal physiology, a complete fly brain or validated fly behavior.

## What comes from the source

The pinned [flyLI2.m](https://github.com/johnpi/eLife_Pisokas_Heinze_Webb_2019/blob/dfb95dfeaad0da2df0f7f687846d4df44079a483/Kakaria_deBivort_2017/KakariaPBSimulationCode.v2/flyLI2.m)
uses membrane capacitance 2×10⁻⁸ F, resistance 10⁶ Ω, zero initial voltage and
current scale 3×10⁻¹⁰ A. Thus the time constant is 20 ms. Each synchronous
explicit Euler update advances 0.1 ms and uses only the previous state.

With dimensionless signed state `u = 100(V − V0)`, the implemented update is:

```
u_next[i] = u[i] + 0.005 * (
    -u[i] + 0.03 * sum(W[i,j] * tanh(u[j])) + 0.03 * input[i]
)
```

`W[target,source]` retains all 326 directed connections and full-precision
fitted strengths across the 60 connected representative units. The two
unconnected source slots are omitted; with noise disabled, their removal has
no effect on these 60 states. Signed state is never rectified or clipped in
this equation. `u` is not Hz, and signed `tanh(u)` is a normalized current
transfer, not a spike rate.

The original fixed-point CX60 still uses its own nonnegative, clipped rate
relaxation with a different recurrent gain and an abstract timestep. Its C
implementation and original Wasm module are unchanged by this comparison.

## What is intentionally different

The source wrapper generates random stimulus spikes. `flyLI2.m` applies a
centered 100 ms moving sum, then normalizes by the maximum over the entire
planned input array. Future inputs therefore affect that offline preprocessing.
The source also adds Gaussian current noise at every unit and update. Its
all-zero normalization has an undefined zero denominator.

This lab does not silently translate that pipeline into a streaming input.
Instead, it uses explicitly controlled direct rate-equivalent input, bounded
from 0 to 200. The cue is a chosen triangular profile of 90° half-width at the
existing E-PG cue bins. Signed drive selects nonnegative input to P-EN A or B;
it is not calibrated yaw, angular velocity or a second visual landmark.
Neither input nor output is labeled measured Hz. Noise is absent.

Reference time starts at zero and counts actual completed updates. The original
MATLAB source stores N state rows but executes N−1 updates; the new API does not
copy that display ambiguity. No publication experiment or MATLAB runtime is
claimed to have been rerun merely because the deterministic equation matches.

## Reading the comparison

Each model has its own isolated control and treatment instances. Their states
start equal within that model, then differ only in the selected intervention.
The reference defaults to 750 ms warm-up, 3250 ms intervention and 750 ms
recovery, sampled every 5 ms. Fixed-point CX60 retains 32/96/32 abstract steps.
Phase-jump buttons select corresponding phase endpoints, not equivalent times.

The default cue angle is 90°, deliberately exposing directional drift rather
than choosing only a symmetric zero-drift case. Shift and A/B-drive protocols
use the same declared input convention. Completed runs remain separate from
unrun control edits; cancellation never publishes a partial result.

The cards have separate axes and units. There is no cross-model raw L1/RMS
“accuracy” score or implied calibration between reference input 200 and baseline
cue strength 768. Look at each control/treatment comparison on its own scale.

The reference displays signed E-PG sector means and raw signed unit states.
Its optional **positive E-PG profile direction** is a separate analysis, not
the paper's decoder or a validated heading:

1. Rectify each E-PG state individually: `max(u, 0)`.
2. Average by the eight cue bins. The duplicate 0° bin has four units; others
   have two. This avoids counting duplicates twice in the diagnostic.
3. Form a circular vector at 0°, 45°, …, 315°. Concentration is vector magnitude
   divided by positive profile mass; it is not confidence.
4. Suppress direction when positive mass is at most 10⁻¹² or concentration is
   at most 10⁻⁹. Exact silence, tiny activity and angular ambiguity are distinct.

Rectification before averaging differs from rectifying signed sector means.
A mixed-sign fixture tests this distinction. Signed profiles are always
preserved, and the main plot never clips away negative states.

## What the untuned probe shows

An independent source-MAT/SI-equation probe applied a 90° cue of strength 200
for 750 ms, then removed it through 4000 ms. Without tuning, nonzero activity
remained, but the positive E-PG profile direction moved from approximately
90.217° to 155.564°. Peak state changed from about 6.725 to 0.715.

This is retained model activity with substantial directional drift. It does not
establish accurate continuous heading memory. Initial 0° and 180° probes are
more symmetric and behave differently; a single favorable example would hide
that limitation. The live comparison reports the actual completed trajectory,
not a preset claim that every cue or protocol has the same outcome.

For the same 90° cue-loss probe, halving the independent integrator timestep
from 100 to 50 μs, then 50 to 25 μs, reduced final all-state maximum differences
from approximately 2.76×10⁻⁷ to 1.38×10⁻⁷. Across all 801 common samples, maximum differences are larger during
transients: approximately 0.006295 and 0.003132, respectively. The post-cue-loss
transient differences similarly halve (0.002767 to 0.001382). This tests
numerical consistency for that probe, not biological accuracy. Exact implementation receipts come from
running the tests below; source claims do not substitute for those tests.

## Reproduction and limits

The reference is a separate C/Wasm module with no imports and a fixed memory
bound. Reset clears all state and inputs. Nonfinite/out-of-range inputs and
invalid update counts fail without modifying state. Each step call permits at
most 1000 updates; the protocol runner limits total reference time to 6000 ms
and samples every 5 ms. The C state remains analytically bounded without adding
clipping: with these inputs, a conservative zero-start bound is `|u| ≤ 33.061`.

Build manifests bind exact module bytes to the complete current source and
provenance set. The bundle requires separate verified manifests for both
engines and exports their identities with the applied protocol and raw states.
This prevents accidental stale attribution; it is not attestation against a
maliciously forged local build and manifest.

The independent oracle reads the original MAT and integrates the SI-voltage
form, rather than importing production C, its generated table or its update
function. Tests compare every unit at selected endpoints, signed initial
states, zero forcing and A/B drive. Native/Wasm floating-point agreement uses
an explicit numeric tolerance; it is not claimed bit-identical. Original
Brain64/CX60 native/Wasm snapshots remain exact.

Run the complete public checks through `ci/README.md`. DOM/state tests do not
establish browser layout, mobile/touch behavior or target hardware safety.
All firmware feasibility gates and the 13.80 NO-GO remain unchanged.

## Provenance

- [Pisokas, Heinze and Webb (2020)](https://doi.org/10.7554/eLife.53985)
- Source commit: `dfb95dfeaad0da2df0f7f687846d4df44079a483`
- `flyLI2.m` SHA256: `92adf312cab38bd012fa7d68a8aca1d38ff9639c8f095a6f9df755a7b488d0b0`
- Original source bytes and full MIT notice: `data/pisokas2020/`
- Equations, source hashes, assumptions and resource bounds: `rate_reference_model.json`
- Existing topology contract: [`CX60.md`](CX60.md)

Matching the source's anatomy-constrained representative circuit is a bounded
fidelity improvement. Its optimized strengths are not measured EM synapse
counts, and matching its numerical equations is not biological validation.
