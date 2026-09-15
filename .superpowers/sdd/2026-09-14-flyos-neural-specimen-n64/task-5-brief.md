### Task 5: Quarantined N64 package pair and exact review evidence

Implement Task 5 from `docs/superpowers/plans/2026-09-14-flyos-neural-specimen-n64.md`. This task is offline only.

#### Version chain and immutable inputs

- The currently installed prior overlay used wrapper version 13.73. Determine the next monotonic package versions from existing verified strategy evidence; expected N64 candidate is 13.74 and its official-code restore wrapper is 13.75. Fail closed if the version chain cannot be proved.
- Pin the official non-Music HWID 3076 13.70 source GCD and decoded-image hashes, Task 4 hook/primary/secondary binary hashes, Task 4 build-manifest/evidence-manifest hashes, runtime-state JSON hash, and all independent review hashes.
- Never alter or replace any original firmware, prior candidate, or prior restore artifact.

#### Outputs and isolation

- Create a version-specific N64 package strategy/tool and tests under `tools/garmin-firmware/`.
- Candidate and restore files may exist only under `artifacts/firmware/quarantine/` and must end `.analysis-only.DO_NOT_INSTALL`.
- Suggested names: `Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL` and `Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL`.
- Do not add an enabled N64 profile or hash to `tools/live-proof/stage-gupdate.ps1`; the live staging script must explicitly reject both new artifacts by name/path/hash/mode.
- Do not access or modify the connected watch.

#### Candidate and restore semantics

- Candidate may differ from official decoded application/resource content only at the exact 4-byte hook, the two audited allocation envelopes/code ranges, coherent version/header/descriptor fields, and enumerated checksum/additive/checkpoint repair bytes required by the package format.
- The candidate must use the exact reviewed Task 4 binaries: hook `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362`, primary `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282`, secondary `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406`.
- Restore must carry the official 13.70 application/resources, restore the official hook and complete primary/secondary envelopes, use a coherent higher wrapper version, and retain the official helper stream. Describe it accurately as an official-code restore wrapper, not byte-identical official firmware.
- Candidate and restore must preserve exact package length/record structure and pass parse/reconstruction/checksum validation. Enumerate every changed raw-GCD and decoded-image range.

#### Tests and reports

- Start with failing tests for exact version sequence, immutable inputs, quarantine-only paths, create-new/no-overwrite semantics, exact binary hashes and placement, allowed difference ranges, full allocation restoration, helper-stream identity, reconstruction, record/checkpoint/additive repairs, failure cleanup, and staging-script rejection.
- Reuse/extend existing Garmin unpackers and verified neural-overlay strategy rather than inventing a new format implementation.
- Run target build/emulator/evidence verification against the exact packaged payload, generic and strict GCD validators, full-image validation, exact reconstruction, complete firmware Python discovery, CTest, and checksum-ledger checks.
- Produce build, strict verification, reconstruction, full-image, emulator, exact-difference, risk, and SHA-256 reports under `artifacts/firmware/analysis/`.
- Update `docs/investigation-log.md`, `docs/session-report.md`, `docs/boot-chain.md`, and create an N64 live proposal that states exact bytes/locations, destination, nonzero brick risk, absence of known nonboot recovery, and restore limits. The proposal must say separate exact user approval is still required.
- Write `.superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-5-report.md` with RED/GREEN evidence and final hashes.

No file may be staged to `D:` or any removable/device volume.
