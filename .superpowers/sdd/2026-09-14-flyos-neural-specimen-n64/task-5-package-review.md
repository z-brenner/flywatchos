# Task 5 final independent package review

Date: 2026-09-15. Scope: the Task 5 brief, independent audit and fix round,
pinned decision, version-specific strategy and tests, exact quarantined package
pair, package/reconstruction/validator/emulator evidence, checksum ledger,
transactional output controls, and staging exclusion.

## Verdict

**SPEC PASS**  
**QUALITY PASS**

No open Task 5 finding was identified. The prior immutable-input high finding
and missing fault-injection medium finding are addressed. The exact 13.74 and
13.75 quarantine packages remain unchanged and reproduce byte-for-byte from
the current pinned inputs.

This review did not write or modify either package, any firmware input,
analysis report other than this reviewer document, a staging path, a removable
volume, or the watch.

## Prior findings

### Addressed: validated input bytes are now consumed exactly once

`PinnedSnapshot` is frozen and retains the exact byte string, length, and
SHA-256. `load_pinned_snapshot` performs one content read and validates the
size and SHA-256 of that same byte string. `load_and_validate_decision` caches
snapshots by canonical path, rejects conflicting duplicate pins, and uses the
cached bytes for official stream extraction, the prior-version chain,
allocation data, target and evidence manifests, every referenced file/source,
and emulator evidence.

`_construct_pair_from_validated`, `_verify_exact_from_validated`, and
`build_attestation_bundle` consume those retained snapshots. The public
construction, exact-verification, build, attestation, and report-refresh paths
therefore do not discard validated bytes and reopen inputs for construction.
The candidate and restore packages are likewise passed from a single pinned
package snapshot into attestation and verification. Remaining `read_bytes`
calls are the one decision read, the one read inside `load_pinned_snapshot`,
intentional post-write readback, the report-refresh before/after immutability
check, and hashes of reports after their validated replacement.

I repeated the original substitution attack with broader coverage. The probe
tracked the decision plus all unique directly pinned, target-manifest,
source-manifest, and evidence-manifest paths, and returned changed bytes on any
second content read. All **58/58 unique paths were read exactly once**. The
attestation still reproduced reconstruction SHA-256
`9d2d4b315eea90a95464bd64f4bea2a2201fcfd64293fe31272b1c841f4c227c`
and ledger SHA-256
`96a4f8a42bd5e156a2c1fc6b6b7cdce5e6319413f3e55f906eb5899941b0da43`.
The exact decision itself was read once. This closes the earlier demonstrated
validation/use mismatch.

### Addressed: transaction and path-failure coverage is complete

`write_transaction` now treats a non-raising short write as fatal, flushes and
fsyncs completed writes, reads every final file back against the exact
in-memory bytes, and removes every created file on failure. If cleanup cannot
be confirmed, it raises a path-specific fatal error instead of reporting
success. `replace_reports_transaction` reads each installed final report back,
restores all prior reports on mismatch, removes temporary state, and supports a
clean retry.

The new tests exercise the actual branches rather than only inspecting source:

- a file object returns a short count after writing partial bytes; the partial
  target is removed, an unrelated sentinel is preserved, and retry succeeds;
- injected `unlink` failure leaves explicit residue and produces a fatal error
  containing the target path; it never overwrites the unrelated sentinel, and
  retry succeeds after the residue is deliberately removed;
- injected post-write readback corruption removes the new output and permits a
  clean retry;
- corruption after a report rename is detected at the installed final path;
  both old reports are restored with no temporary or backup residue, and retry
  succeeds;
- lexical `..` traversal, a nested destination, `D:`, a wrong name, a
  preexisting output, a hardlink, and a symlink (when the host permits its
  creation) are rejected. The preexisting and hardlink source bytes remain
  unchanged.

The existing raised `write`, `flush`, and `fsync` injections also continue to
prove removal of partial outputs. Exclusive `xb` creation and the exact-root,
direct-child, filename, suffix, fixed-volume, reparse-point, hardlink, and input
alias checks remain in force.

## Exact package evidence

| Artifact | Version | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| Candidate | 13.74 | 5,120,675 | `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd` |
| Official-code restore wrapper | 13.75 | 5,120,675 | `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da` |

The files are the only occurrences of their exact names under the reviewed
repository roots. Each is a direct child of
`artifacts/firmware/quarantine/`, has the required
`.gcd.analysis-only.DO_NOT_INSTALL` suffix, has one filesystem link, and is not
a symlink. Descriptor and decoded-header versions are coherent with the
smallest proved forward sequence: installed prior wrapper 13.73, candidate
13.74, restore wrapper 13.75.

Fresh `verify_exact` returned `PASS` with **8/8** checks true. In-memory
construction reproduced both on-disk packages exactly. Both preserve the
official 93-record layout and the exact 37,120-byte helper stream with SHA-256
`f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46`.

The candidate contains the exact Task 4 binaries:

| Segment | Runtime range | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Hook | `0x00009a20..0x00009a23` | 4 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Primary | `0x001f6000..0x001f63f7` | 1,016 | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| Secondary | `0x001fa400..0x001fabf1` | 2,034 | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |

Seven primary gap bytes and fourteen secondary tail bytes remain official
`0xff`. Candidate repairs remain the additive byte `0xff -> 0xb5` at runtime
`0x001f63ff` and the final-main checksum byte `0xc4 -> 0xc0`. The restore puts
official bytes back over the hook and both full allocation envelopes, and its
final-main checksum byte is `0xc4 -> 0xbf`.

Fresh all-byte evidence remains exact: candidate decoded/raw change counts are
3,040/3,042 and restore counts are 2/4. Only the final outer checkpoint changes
in either package. Main additive checksums are zero. Candidate decoded-main
SHA-256 remains
`66566f18da04936c9da0c4638860cb493421582e63d6a129f6ae206fb034a6f4`;
restore decoded-main SHA-256 remains
`b2eb6f13c1bffe59b0cb59e8b4c3811dcca46866b27dd51c315160f46c21905e`.

## Reports and validators

Freshly regenerated in-memory evidence matched every corresponding persisted
report byte-for-byte:

| Evidence | SHA-256 | Result |
| --- | --- | --- |
| Reconstruction | `9d2d4b315eea90a95464bd64f4bea2a2201fcfd64293fe31272b1c841f4c227c` | match |
| Combined full-image | `9c9d8d2bbaaf25250ada32e468a9a6528ee64ebf31883ef67030765f58d28de1` | match |
| Packaged emulator | `deb8c1042504891da3aa5b46a1ae67c3890d8f70775c4ec4b9642142183e2e0a` | match / PASS |
| Exact differences | `874f54be1bbdbf5b620102f49f91249ff516879eff1be22b94f5c37fc84cbccc` | match |
| Risk | `ba1b20563b0c641dc9ed85e2be9d2a72547a1ab7f2fc46ec7fd9434813d95324` | match |
| Package ledger | `96a4f8a42bd5e156a2c1fc6b6b7cdce5e6319413f3e55f906eb5899941b0da43` | match |

Both opt-in N64 generic profiles report `PASS`; their hashes are
`8f61ad35ad5f2026f92c289d9af9ed3bcbb3f7a6aa57f365fad6cd93a0bff808`
and `bbba041b47378ed97cb63b5661bd311634db0030c74e1926fa1f61d0c7618feb`.
Candidate and restore full-image validators remain true at hashes
`a234538b7af9abe0be34a658fe6a8d375a714c3d7724093605c4dd45edef76d5`
and `e585ae5aad1f7cab5f0ea313e6923bb5ca56659b5506b762ce23703f18a32551`.
The packaged emulator binds the extracted payloads to the reviewed Task 4
binaries and pinned 64-cell/384-byte-stack evidence. All **8/8** package-ledger
entries rehashed exactly; ledger verification is `PASS`, SHA-256
`4c8e008c7d6b776096926996ffb62f3662257544d58138e77533e4bf7962e90f`.

The refreshed build and strict reports are respectively
`8288628f26890412a1db6b82eac6b6cde6aa5e5d7e2c0a4f7269e43bc94a8009`
and `878cf8de614b2fda5e9ebf9556aef77b40908251f8e6441d0b3cda1aea1176a6`.
Both record the read-only package refresh and unchanged package bytes and
metadata. The final Task 5 report is SHA-256
`86f8f62b7472fbd4c476d2cb1331c5f7333f0ec51c54aed5cc8d052614b4c8aa`
and pins the current strategy and test hashes
`34b52ed750995a24c06c216437f3697ce9a2b6a9f5c341f07210f5a4ce11063e`
and `a25999f10d847bb2a2955239c660021b0f18ad07c66e745f84dc7191b2e56ab7`.
Its referenced live/recovery proposal is SHA-256
`e2b0aa7e8523d8dd513335ca131ba749eec0fa68ce74cd05366206f49748ad46`.

## Focused verification

```text
python -B -m unittest tools.garmin-firmware.tests.test_neural_specimen_n64_version_strategy -v
Ran 18 tests in 158.540s
OK

fresh verify_exact
PASS; 8/8 checks true

fresh in-memory attestation regeneration
six persisted evidence blobs matched byte-for-byte; ledger entries 8/8

second-read mutation probe over complete pinned inventory
58 unique paths; minimum reads 1; maximum reads 1; canonical reports reproduced
```

The staging script still has no enabled N64 profile and denies the two N64
modes, normalized paths, basenames, and package hashes before source or device
access. Its two direct rejection tests and three future-profile alias mutation
tests passed.

Feasibility remains **YELLOW**. The restore is only usable while GarminOS and
its normal USB update service still boot, no nonboot recovery is known, and the
reviewed target reaches the 384-byte stack ceiling with zero measured margin.
Those are explicit experiment risks, not Task 5 package-integrity defects.
