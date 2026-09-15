# FlyOS Neural Overlay Offline Package Addendum

## Decision

This addendum permits construction and strict verification of one local, quarantined Forerunner 245 neural-overlay package and its official-code restore wrapper. It does not change `packaging_allowed: false` in `artifacts/analysis/fr245-1370-second-allocation.json`; that field continues to mean the proprietary image lacks a complete semantic ownership inventory. A distinct `offline_quarantine_construction_allowed: true` decision authorizes only creation of reviewable host files.

`live_staging_allowed` remains false. No output from this addendum may be copied, renamed, linked, or redirected to `D:`, another removable volume, a device path, a network path, Garmin software, or any updater-visible directory. No reset, eject, install, or watch action is authorized.

## Basis

The exact secondary interval `0x001fa400..0x001fabff` is 2,048 erased `0xff` bytes in both official non-Music firmware 3.10 and 13.70. Fresh Ghidra queries found zero references, instructions, defined data, functions, or symbols in both versions. Full native little-endian stride-one pointer scans found zero exact or Thumb-normalized hits. The 13.70 metadata audit maps the interval to decoded offsets `0x001f7400..0x001f7bff` and raw GCD offsets `0x002015e2..0x00201de1`, entirely inside one ordinary `0x02bd` data-record body. It excludes every identified outer record/header/checkpoint, embedded header, startup table, update-region table, 622-entry relative table, known checksum repair byte, resident prefix, and internal/external image boundary.

The remaining uncertainty is explicit: no complete proprietary resource-directory or fixed-offset reservation inventory exists, and computed runtime use cannot be universally disproved. That uncertainty is material to live installation. It is not a reason to prevent construction of a nonexecuting local artifact when strict containment, exact byte allowlists, and a separate live approval boundary are enforced.

The prior synthetic 13.72 full-screen package was installed and its custom Thumb payload visibly executed. This demonstrates acceptance of the tested main-code modifications and is relevant to update-format feasibility. It does not prove this new interval or workload is safe on hardware.

## Exact construction scope

The decision artifact must pin all current source, evidence, model, renderer, target, emulator, and review hashes. The builder must reject a mismatch and may write only beneath the repository-local root `artifacts/firmware/quarantine`. Both filenames must end in `.gcd.analysis-only.DO_NOT_INSTALL`. The builder must reject path traversal, reparse/symlink escape, remote/device paths, input-output identity aliases, and overwrite of existing original or prior candidate artifacts.

The neural candidate uses synthetic main version 13.73 and the restore wrapper uses synthetic main version 13.74. Both descriptor and decoded header version fields must agree. Runtime version mirrors remain official 13.70. The helper stream and descriptor remain byte-identical to the official package.

Only these runtime regions may differ from official code/resources in the 13.73 candidate, in addition to declared version and additive/checkpoint repair bytes:

| Region | Inclusive runtime range | Payload bytes |
|---|---|---:|
| Display hook | `0x00009a20..0x00009a23` | 4 |
| Primary allocation | `0x001f6000..0x001f63ff` | 1,024 including `0xff` padding and its additive repair byte |
| Secondary allocation | `0x001fa400..0x001fabff` | 2,048 including four trailing `0xff` bytes |

The compiled segments within those allocations remain the reviewed hook 4 bytes, primary 794 bytes, and secondary 2,044 bytes. The 13.74 restore must restore the official hook and both full allocations. It carries official 13.70 code/resources except for the coherent 13.74 decoded header and the explicitly enumerated additive repair byte; it is not described as a byte-identical official package.

## Required verifier behavior

The builder and dedicated verifier must:

1. reconstruct both outputs from the pinned official package and frozen target segments;
2. require HWID 3076, exact stream lengths, exact record layout, and coherent versions 13.73 then 13.74;
3. enforce exact decoded and raw changed-range allowlists, including version fields and named checksum/checkpoint repairs;
4. verify the candidate hook target, both payload segments, official `0xff` padding, primary repair byte, full-screen behavior metadata, and unchanged helper;
5. verify the restore contains the official hook and official bytes throughout both allocations;
6. require the decoded main additive sum and every recovered outer checkpoint to pass;
7. run `full_image_validator.py` on both outputs;
8. use a dedicated neural exact profile or equivalent strict verifier without weakening generic verifier rules;
9. hash every output and report, preserve originals, and leave no passing manifest after a failed build;
10. perform a post-build read-only check that the watch has no `GUPDATE.GCD` or `force.tmp` and that the volume remains healthy.

Successful construction means only that the local bytes match this experiment. It does not authorize staging or installation.

## Live boundary

Any later live proposal must present the final candidate and restore filenames, sizes, SHA-256 hashes, exact destination, complete internal-flash and external-QSPI rewrite ranges, nonzero unquantified brick risk, absence of known nonboot recovery, dependence of the restore wrapper on GarminOS and USB still booting, and the exact official source hash. The user must approve that exact action after receiving those facts. Until then, the staging guard must reject the neural artifacts and no device write may occur.
