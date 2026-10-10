# Paired CX60 perturbation experiments

The offline lab compares a control and a perturbed CX60 instance starting from
identical state. Both are isolated instances of the **same real C/WebAssembly
module** used by the live circuit. JavaScript supplies commands and calculates
observable summaries; it does not implement neural dynamics.

This is a reproducible assay of the current fixed-point adaptation. It is not a
new biological model, a complete fly brain, an independent biological sample,
or a validation of fly behavior. The static measured ER4m↔EPG anatomy lens is
separate and receives no simulated activations.

## Protocol and sample conventions

Each pair begins with `fly_lab_reset_model(1, 0)` and the same cue/drive inputs.
CX60 is deterministic and ignores the seed. A repeat is a reproducibility
check, not another independent sample and not grounds for statistical error bars.

Default phases are 32 warm-up steps, 96 intervention steps, and 32 recovery
steps. Sample 0 is the initialized state. Each later sample is captured **after**
one real C step. Thus both trials share samples 0–32, intervention samples are
33–128, and recovery samples are 129–160. No sample represents elapsed seconds.
The controls accept bounded integer values and the total is at most 512 steps.
The fixed 32-step warm-up is not an equilibrium claim: the control can continue
evolving after this boundary, so comparisons use its state at the same step.

The control retains the initial cue and zero P-EN drive throughout. During the
intervention, the treatment changes only the selected input:

- **Cue shift:** change cue angle, default 0° → 90°.
- **Cue loss:** set cue strength to zero. P-EN drive remains zero.
- **Cue versus P-EN drive:** add signed, unitless P-EN A/B drive while retaining
  the original cue. Positive stimulates A; negative stimulates B. This supplies
  no second landmark and is not a calibrated physical turning direction.

Recovery restores the initial inputs. This does not promise bit-identical
recovery of state: fixed-point residual differences can remain. Inputs are
synthetic, not watch sensors or observed fly stimuli. Equal initial conditions
and aligned sample indices make the within-model comparison interpretable.

## Measurements and limitations

Every exported frame preserves the 64 raw activation slots, C strongest-sector
readout and C peak strength. The four padding slots remain zero. All activity
units are raw Q10 counts (divide by 1024 for dimensionless model activity), not
Hz, spike counts, confidence, or electrical efficacy.

Eight E-PG sector means use the published cue-sector metadata. Exact arithmetic
means retain fractional raw counts; the C coarse readout separately floors each
sector mean before selecting its maximum. Sector 0 averages four representative
units; the other seven average two. This removes duplicate-count bias in the
readout, not underlying topology or stimulus asymmetry.

- **Strongest E-PG sector** is the C maximum of the eight floored means, in 45° bins.
  Lowest-angle positive ties win. This is not a circular population-vector
  heading or a validated decoded biological heading.
- **No positive sector mean** (`-1`) must not become 0°. It can occur with
  residual raw activity smaller than the integer average. It is not exact silence.
- **Exact E-PG silence** requires the raw sum of E-PG activations to equal zero.
  **Exact network silence** requires all 60 active model units to equal zero.
- **Paired profile difference** is the sum of absolute differences across eight
  duplicate-normalized sector means. It can reveal a response that the coarse
  strongest-sector readout misses. Its normalized value divides this sum by the
  sum of both trials' sector activity; two zero profiles give an unavailable
  normalized value. This measures amplitude and shape differences, not a
  biological distance.
- **Circular peak separation** uses the smaller angular separation only when
  both coarse peaks are unique and positive. Missing or tied peaks remain
  unavailable, not zero error.
- **Relative activity / retention** compares the sum of eight sector means with
  that trial's warm-up endpoint. A zero denominator is unavailable, not 0%.
  It can exceed 100% and does not measure memory or recovery. Equal initial and
  final totals do not imply equality with the evolving paired control.

Read the entire trajectory and activity profile. A sharp or stable coarse peak
alone cannot establish persistent orientation, especially at tiny amplitude or
with nearly uniform sector activity. The plots do not interpolate absent
readouts or turn a 315°→0° wrap into a 315° movement.

### Observed default outcomes

For the exact 32/96/32-step default, baseline cue 0° at strength 768, shifted cue
90°, and drive ±768, the unchanged C implementation produces:

| Intervention | Observed response | Profile L1 at intervention end | Profile L1 after recovery |
|---|---|---:|---:|
| Shift cue to 90° | Strongest sector reaches 90° after four intervention steps | 22273.5 | 140.5 |
| Remove cue, zero drive | E-PG zero at step 48; all 60 units zero at step 52 | 15379.5 | 108 |
| Add P-EN A or B drive | Profile changes while strongest sector remains 0° | 639.5 | 14.5 |

L1 is the summed eight-sector difference in raw Q10 counts, relative to the
same-time control. These are deterministic implementation observations for
these settings, not biological measurements or guarantees for other inputs.
During cue loss, the C readout is already unavailable at intervention step 47
while raw E-PG activity sums to 2; integer averaging explains the distinction.
The control peak rises from 7453 at warm-up end to 7499, so treating warm-up as
an equilibrium or comparing recovery only to the initial total would mislead.

## Comparison with the source publication

The published model of [Pisokas, Heinze and Webb (2020)](https://doi.org/10.7554/eLife.53985)
examines maintained activity after stimulus removal, transitions after stimulus
relocation, and shifting activity under one-sided P-EN stimulation. See Figures
7, 10, and 13–14 and Table 1. Those results use the publication's dynamics and
parameters. They do not establish the same behavior in this adaptation.

CX60 preserves the source topology and fitted strengths but uses deliberately
new bounded fixed-point rate relaxation, a chosen global gain, clipping, leak,
and triangular cue profile. The paper's spiking/tanh-current simulations are
not rerun by this experiment panel. In particular, cue-off decay and profile
changes without a coarse-peak shift are legitimate measured outcomes of this
implementation, not failures to hide or force into a persistent-attractor claim.

[`CX60.md`](CX60.md) records the exact equations, source commit, data mapping,
input units, rounding rules and license. The original source and full MIT notice
are bundled in `data/pisokas2020/`. These experiments add no fitted weights,
connections, neurons or dynamics and do not promote any target feasibility gate.

## Reproducibility

The export includes both exact C command sequences, the committed protocol
configuration and phase boundaries, every raw sample and its derived metrics,
model source/approximation metadata, the validated build manifest with its source
hashes, and hashes identifying the embedded Wasm, original manifest bytes and
experiment runner. At build time, a live bundle requires the module's adjacent
`.wasm.json` manifest and verifies its module bytes plus every required source
and provenance digest against the current checkout. Missing or stale identities
fail closed with a rebuild instruction. This consistency check prevents
accidental stale/mislabeled builds; it is not cryptographic attestation against
a deliberately forged local manifest. Editing the form after a run does not rewrite that run's
export. The experiment instances never advance the interactive live specimen.

Tests replay commands against the actual Wasm, compare every captured state and
final framebuffer, check common-prefix identity and repeatability, and reject
invalid bounds or ambiguous sector metadata. DOM tests cover mode changes,
interrupted controls, missing engines, scrubbing and export. They are not browser
layout or physical-pointer validation. No watch or firmware input is used.
