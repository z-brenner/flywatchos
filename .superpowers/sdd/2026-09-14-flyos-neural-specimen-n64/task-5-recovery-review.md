# Task 5 recovery, risk, and live-proposal review

**SPEC: PASS**

**QUALITY: PASS**

## Initial findings (all addressed in final recheck)

- **ADDRESSED — HIGH:** [`docs/neural-specimen-n64-live-proposal.md:83`](../../../docs/neural-specimen-n64-live-proposal.md) now contains the exact conditional restore procedure, including identity/volume preflight, exact restore hash and size, separate approval, audited temporary profile, dry run, create-new staging and readback, flush/eject, Garmin START confirmation, post-boot checks, and guard closure.
- **ADDRESSED — MEDIUM:** [`docs/neural-specimen-n64-live-proposal.md:47`](../../../docs/neural-specimen-n64-live-proposal.md) now states that HR, motion, and charging telemetry are unavailable, gives exact `HR --` / `MOTION --` behavior, prohibits those channels from driving the model, and distinguishes stock charging/USB pass-through.
- **ADDRESSED — MEDIUM:** [`docs/neural-specimen-n64-live-proposal.md:9`](../../../docs/neural-specimen-n64-live-proposal.md) now states **YELLOW**, GarminOS-resident overlay, no standalone FlyOS, and no arbitrary-image/arbitrary-boot proof.
- **ADDRESSED — LOW:** The package review's appended current-evidence section pins focused-test SHA-256 `a25999f1...`, and the independent-audit statement about the proposal is now true after the proposal fix.

## Confirmed

- Candidate: synthetic 13.74, 5,120,675 bytes, SHA-256 `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`; restore: synthetic 13.75 official-code wrapper, 5,120,675 bytes, SHA-256 `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`. Fresh local hashes match the ledger, reconstruction, generic, and full-image reports.
- The proposal correctly identifies `D:\Garmin\GUPDATE.GCD`, the hook/payload/repair ranges, raw descriptor/checkpoint changes, complete internal/external erase and program scope, nonzero brick risk, exact 384-byte stack use with zero margin, the final-read-to-render freshness race, restore dependence on booting GarminOS/USB updater, and absence of known nonboot recovery.
- The N64 write remains **unapproved and unstaged in the reviewed offline evidence**. The live staging script has no enabled N64 profile and rejects both N64 modes before source resolution or device query. No `D:` or watch access was performed for this review.

## Final narrow recheck (2026-09-15)

**SPEC: PASS**  
**QUALITY: PASS**

No open finding remains in the requested recovery/document scope.

- The eight-step restore procedure is complete and explicitly conditional on normally booting GarminOS plus its USB mass-storage updater. Lines 127–139 require aborts for failed preflight, staging, hash, rename, eject, or unexpected on-watch flow; they forbid retry as an implied recovery action and state that early-boot, nonenumerating, and damaged-loader failures have no known recovery.
- Runtime disclosures are exact: unavailable HR, motion, and charging telemetry do not affect the model; the face shows `HR --` and `MOTION --`; Garmin charging/USB/update and other non-home screens pass through unchanged.
- The proposal is self-contained on **YELLOW** feasibility and the GarminOS-resident/no-standalone/no-arbitrary-boot boundary. Nonzero brick risk, zero stack margin, and the residual final-read-to-render view race remain disclosed.
- Candidate and restore remain unchanged at 5,120,675 bytes with SHA-256 `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd` and `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`. The exact-difference report remains SHA-256 `874f54be1bbdbf5b620102f49f91249ff516879eff1be22b94f5c37fc84cbccc`; the hook, primary, repair, secondary, version, checksum, erase, and program ranges in the proposal still match it and the prior review.
- The staging guard remains closed for both N64 artifacts. This recheck accessed neither `D:` nor the watch.
