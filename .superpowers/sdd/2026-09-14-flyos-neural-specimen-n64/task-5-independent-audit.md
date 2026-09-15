# Task 5 independent package-chain pre-review

Date: 2026-09-15. Scope: read-only/offline audit of the installed coherent-13.73
neural overlay, its uninstalled coherent-13.74 official-code restore wrapper,
the preserved official Forerunner 245 non-Music 13.70 package, the final N64
target evidence, package-format repair semantics, recovery limits, and the live
staging guard. This review did not create or edit a GCD, quarantine artifact,
staging profile, watch file, or implementation file. The only persistent output
is this report.

## Verdict

**VERSION CHAIN: PASS.** The next N64 candidate must use coherent main
descriptor/header version **13.74 (1374)**, and its official-code restore wrapper
must use **13.75 (1375)**. The exact 13.73 package was staged with full readback,
accepted by the user on the watch, booted, and produced the 32-neuron display.
The existing 13.74 restore was not staged. Therefore 13.74 is the smallest
normal-forward main version after the installed 13.73 image, and 13.75 is the
smallest normal-forward restore after a successful 13.74 N64 installation.
Merely having an uninstalled 13.74 file on the host does not consume that
version.

**OFFLINE BYTE STRATEGY: PASS WITH EXACT EXPECTATIONS.** Independent in-memory
construction from the pinned official package and the current reviewed N64
segments produced a deterministic 13.74 candidate and 13.75 restore. Both keep
the original 5,120,675-byte package layout, retain the exact official helper,
have zero main-stream additive sums, validate all five outer checkpoints, and
pass `full_image_validator.validate_bytes`. Their expected hashes and repairs
are recorded below. A Task 5 implementation must reproduce them exactly or
fail closed.

**TASK 5 IMPLEMENTATION: HOLD UNTIL CHECKLIST PASSES.** The old 32-neuron
strategy cannot be reused unchanged: it hard-codes versions 1373/1374,
filenames, report/profile names, decision hash, evidence inventory, and segment
lengths 794/2,044. During this audit, concurrent Task 5 work added recognized
but immediately blocked N64 modes and a filename/path/hash denylist to the
staging script. The new block executes before device discovery, but the current
implementation does not scan the enabled profile table for an alias to either
blocked path or hash. That future-edit bypass must be closed. Offline package
construction may proceed only through a new N64-specific, byte-pinned strategy
and the controls below.

**LIVE STAGING: CLOSED.** Nothing in this review authorizes copying either
future package to the watch. The future restore depends on GarminOS, USB mass
storage, and the normal updater continuing to boot. No Forerunner-245-specific
nonboot recovery path is known.

## Pinned source and prior chain

The official source is Garmin's HWID-3076, part `006-B3076-00`, non-Music 13.70
full update. `tools/garmin-firmware/firmware-sources.json` records Garmin's
download URL, exact size, and MD5; the preserved bytes independently match both
the recorded MD5 and the established SHA-256.

| Item | Bytes | SHA-256 |
| --- | ---: | --- |
| Official `Forerunner245_1370_GUPDATE.GCD` | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| Official decoded main stream `0x02bd` | 5,079,040 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| Official decoded helper stream `0x0505` | 37,120 | `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46` |
| Firmware source catalog | 3,195 | `7967121bde73a431a306ccca4f8dffe58e63332a3febaad873d08553ece9d3b2` |
| Installed prior 13.73 candidate | 5,120,675 | `4ec78eabd23a880ad5d4e9ff52e688e62397480a32070316b2748b70b771c9d7` |
| Existing uninstalled 13.74 restore | 5,120,675 | `4d47edfcaeb3585bd026ac89c8cc9fbeaa9168032d9569aa3885bfdb4880ffa4` |
| Prior live-stage receipt | 923 | `43f7c82ecb19f88c41834c673c9637e760509410a18d565a0bf888834a3466a5` |

The official package MD5 is `f1b9e00830dccd28660691f9cf299bb7`, matching
the Garmin catalog entry. Fresh parsing of the two prior quarantine files found
coherent main descriptor/header versions 1373 and 1374 respectively, exact
official helper hashes and descriptors, zero main sums, and valid outer
checkpoints. The receipt identifies the staged source and complete destination
readback as the exact 13.73 package hash. The user-observed boot, neural screen,
button response, and healthy reconnect are recorded in
`docs/neural-overlay-live-proposal.md` and `docs/session-report.md`.

The public `GarminDevice.xml` version remained 1370 after installation. That
public field is not a safe admission counter. The demonstrated transition from
the installed 13.72 overlay to the accepted 13.73 neural overlay is the stronger
chain evidence. The recovered selector also admits a component on the normal
path when the incoming descriptor version is greater than the installed/current
component version. Accordingly:

1. N64 candidate 1374 is greater than installed candidate 1373.
2. Restore 1375 is greater than an installed N64 candidate 1374.
3. The existing restore 1374 is not a dependable restore after installing an
   N64 candidate that also uses 1374; the normal selector may skip an equal
   version.
4. Official 1370 is older and is not a demonstrated post-N64 restore path.

## Final N64 inputs

The exact target segment files currently on disk match the Task 5 brief:

| Segment | Inclusive runtime range | Compiled bytes | SHA-256 |
| --- | --- | ---: | --- |
| Hook | `0x00009a20..0x00009a23` | 4 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Primary | `0x001f6000..0x001f63f7` | 1,016 | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| Secondary | `0x001fa400..0x001fabf1` | 2,034 | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |

The hook bytes are `ec f1 ee fa`, one Thumb-2 `bl 0x001f6000`. The official
hook bytes are `04 f0 c0 fb`. Primary has seven ordinary erased bytes at
`0x001f63f8..0x001f63fe`; `0x001f63ff` is reserved for additive repair.
Secondary has fourteen erased bytes at `0x001fabf2..0x001fabff`. The complete
official primary and secondary envelopes are 1,024 and 2,048 bytes of `0xff`.

| Evidence | Bytes | Current SHA-256 |
| --- | ---: | --- |
| N64 allocation JSON | 1,047 | `86251e3cbaa39fa46b0986d39a84f48864f9c51fb15b59fafec5b6af3406f4bb` |
| N64 runtime-state JSON | 21,112 | `53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d` |
| N64 target build manifest | 10,795 | `b358b89867076e594c545447267819fc92ba1fa8290c2d4c0213c1ec332acfbe` |
| Target build SHA ledger | 1,604 | `b35773fe1e568851d57d54a2afc18a45c56784321ae3871b3df99ce0430ab460` |
| N64 emulator report | 19,120 | `d11609d1bf4536141abb81762e9a973a82c3059aeb649632999ebb05d2323033` |
| N64 evidence manifest | 1,966 | `a0cc54142febda3d12033dc8d9a37358022ac871989aca0252ae475b110889ba` |
| N64 design specification | 6,181 | `5fe595ce8b08bb44afa39a4239df0c8b4bfd93a312adca2933c1693c14629e59` |
| N64 implementation plan | 8,635 | `74ac8a3b30ec357a45949737617df4d4169cd11a4e597ee4e80a7eaf83f047a1` |
| Task 5 brief | 3,999 | `6abb7ebe07351b6d968b30787cad031b49b38b4470cae1acddf23119af67dc01` |

The N64 decision/strategy must pin these current byte identities directly. It
must also validate every `files` and `sources` entry in the target manifest and
every referenced file in the evidence manifest, not merely pin the two manifest
files. It must retain `packaging_allowed:false`, `live_write_allowed:false`, and
the 384-byte target-owned stack limit.

All pre-Task-5 review/audit files in this workstream currently hash as follows:

| Review evidence | SHA-256 |
| --- | --- |
| `task-1-review.md` | `9c7b4e26bb5276e84cee52e14159254c611a06fdb9639b3e6a7ac8cbdf8b2154` |
| `task-2-review.md` | `276a441b6e4175fd3d0034053213bc3445a8585f59efccfe0b3686d3347b9789` |
| `task-3-independent-audit.md` | `ff2fcd25fa291e208c9741f8aac6f5bd204f1ce7e15b7dd5621be0157ace023b` |
| `task-3-color-scout.md` | `3c8f643f08d92de5682803a1e883ad1048bef36d97d471ad8eea9676fc6daad2` |
| `task-3-review.md` | `49584378f07dc7c114bd8413b91b3dd8eb1916c906c92797cad77f79543e56df` |
| `task-4-allocation-scout.md` | `f974941bf190cee48c68a1eb9d77c9d07be44b131f5580f7463f9f56d1716cb3` |
| `task-4-spec-review.md` | `999f10d29d5431645e6ec0e2d2188d7cd1d9b00f9428aee1df8fa0188015060b` |
| `task-4-allocation-review.md` | `ff342f90ed4591bdedd54da7356323d1290fff7f452b7b54833bd12ea7e6272c` |
| `task-4-emulator-review.md` | `42773a22c7a5ee4a2efd9d1abf41c271d70e5c1d4d22d5eb206d571cc36ccc16` |
| `task-4-report.md` | `9d25ee6e38a1b1dee053447f3983271b816f4f4387d65fa4c5d388c03718765e` |

One provenance nuance must be explicit. `task-4-allocation-review.md` contains
manifest/evidence hashes from an intermediate snapshot (`d659...`, `18481...`,
and `307b...`). The final canonical files are the `b358...`, `a0cc...`, and
`d116...` values above, which are recorded in the final Task 4 report and
validated by `task-4-emulator-review.md`. The segment hashes did not change.
The new decision should pin the review file as historical review evidence but
must not import those embedded intermediate artifact hashes as current inputs.
A final Task 5 reviewer must explicitly reconcile this drift rather than
silently accepting either set.

## Exact stream and file mappings

The main image load base is `0x00003000`. Runtime address minus `0x3000` gives
the decoded main-stream offset for all three custom regions. Parsing the
official package's 78 `0x02bd` data records gives these exact raw mappings:

| Purpose | Runtime range | Decoded main range | Raw GCD body range |
| --- | --- | --- | --- |
| Main header version | n/a | `0x0000022c..0x0000022d` | `0x0000a392..0x0000a393` |
| Display hook | `0x00009a20..0x00009a23` | `0x00006a20..0x00006a23` | `0x00010b86..0x00010b89` |
| Full primary envelope | `0x001f6000..0x001f63ff` | `0x001f3000..0x001f33ff` | `0x001fd1e2..0x001fd5e1` |
| Full secondary envelope | `0x001fa400..0x001fabff` | `0x001f7400..0x001f7bff` | `0x002015e2..0x00201de1` |
| Final main additive byte | n/a | `0x004d7fff` | `0x004e2299` |

The main descriptor version is raw `0x0000a160..0x0000a161`. The package has
93 records total: five `0x0001` checkpoints, two `0x0002`, one `0x0003`, one
`0x0005`, two `0x0006`, two `0x0007`, one helper `0x0505`, 78 main `0x02bd`,
and one terminating `0xffff`. Checkpoint body bytes are at raw offsets
`0x0000000c`, `0x00000072`, `0x00001004`, `0x0000a137`, and `0x004e229e`.
For the exact expected 13.74/13.75 mutations, only the final checkpoint at
`0x004e229e` changes. A broad allowlist may name all five checkpoint positions,
but the strict exact profile must reject a change to any of the first four.

## Independently predicted package pair

The following values were produced in memory only. The construction began with
the pinned official bytes, installed the complete N64 hook/primary/secondary
envelopes, repaired the primary checksum byte, applied a coherent main
descriptor/header version, repaired the final main additive byte, and
recomputed the outer checkpoints. No result was written to quarantine or any
other package path.

| Result | Expected value |
| --- | --- |
| Candidate filename | `Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL` |
| Candidate size | 5,120,675 |
| Candidate SHA-256 | `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd` |
| Candidate main SHA-256 | `66566f18da04936c9da0c4638860cb493421582e63d6a129f6ae206fb034a6f4` |
| Candidate descriptor/header | 1374 / 1374 |
| Candidate decoded/raw changed-byte count | 3,040 / 3,042 |
| Candidate primary repair | `0xff -> 0xb5` at decoded `0x1f33ff`, raw `0x1fd5e1`, runtime `0x001f63ff` |
| Candidate final-main repair | `0xc4 -> 0xc0` at decoded `0x4d7fff`, raw `0x4e2299` |
| Candidate changed outer checkpoint | raw `0x4e229e` only |
| Restore filename | `Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL` |
| Restore size | 5,120,675 |
| Restore SHA-256 | `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da` |
| Restore main SHA-256 | `b2eb6f13c1bffe59b0cb59e8b4c3811dcca46866b27dd51c315160f46c21905e` |
| Restore descriptor/header | 1375 / 1375 |
| Restore decoded/raw changed-byte count | 2 / 4 |
| Restore final-main repair | `0xc4 -> 0xbf` at decoded `0x4d7fff`, raw `0x4e2299` |
| Restore changed outer checkpoint | raw `0x4e229e` only |

The target insertion remainder before the primary repair is `0x4a`; subtracting
it from official `0xff` produces `0xb5`. The candidate then changes the decoded
header version from 1370 (`0x055a`) to 1374 (`0x055e`), so the separate final
main checksum changes by four from `0xc4` to `0xc0`. Restore 1375 changes the
header by five and therefore uses `0xbf`. Descriptor changes do not participate
in the decoded main sum, but they do participate in the final outer checkpoint.

The candidate's actual decoded differences are confined to: the low byte at
`0x22c`; hook `0x6a20..0x6a23`; non-`0xff` bytes within compiled primary
`0x1f3000..0x1f33f7`; repair byte `0x1f33ff`; non-`0xff` bytes within compiled
secondary `0x1f7400..0x1f7bf1`; and final byte `0x4d7fff`. The seven primary
gap bytes and fourteen secondary tail bytes remain `0xff`. The strict report
must enumerate every contiguous actual decoded and raw difference range and
also show the enclosing allowlist; substituting only the enclosing envelopes
for the actual-range report is insufficient.

The restore must reconstruct the official hook and all 3,072 official bytes in
the two complete allocation envelopes. Relative to official, its only decoded
changes are `0x22c` and `0x4d7fff`; its only raw changes are `0xa160`, `0xa392`,
`0x4e2299`, and `0x4e229e`. It is an **official-code restore wrapper**, not
byte-identical official firmware.

## Repair and reconstruction order

A safe builder must preserve the already validated operation order and make
each step independently checkable:

1. Parse the exact official GCD; require HWID 3076, main/helper uniqueness,
   official versions, size, 93-record layout, 5,079,040-byte main, and
   37,120-byte helper.
2. Create each full allocation from the official `0xff` envelope. Copy exactly
   1,016 primary bytes and 2,034 secondary bytes into those new in-memory
   buffers. Never carry padding from an unrelated previous candidate.
3. Replace the four official hook bytes and both complete envelopes in the
   decoded main stream. Require the hook to decode to one Thumb branch to
   `0x001f6000`.
4. Compute the main remainder, write only the reserved primary repair byte at
   decoded `0x1f33ff`, and require the main sum to become zero.
5. Change only the main descriptor and main decoded header to version 1374.
   Recompute the final main additive byte at decoded `0x4d7fff` and all outer
   checkpoints.
6. Construct restore separately from official bytes, set only coherent main
   descriptor/header version 1375, repair decoded `0x4d7fff`, and recompute
   outer checkpoints. Do not derive restore from the candidate.
7. Reparse both full byte strings, compare complete record layouts, reconstruct
   both expected byte strings from the immutable inputs, and demand byte-for-byte
   identity plus the exact hashes above.

`recompute_checkpoints` works cumulatively and must process checkpoint records
in file order. A builder must never treat a valid prefix sum as proof that an
unexpected byte is permitted. Checksum repair and difference confinement are
separate gates.

## Package-builder pitfalls

1. **Hard-coded old strategy.** `neural_overlay_version_strategy.py` names
   1373/1374 and requires old segment lengths 794/2,044. Editing its constants
   in place would break reproducibility of the installed pair. Prefer a new
   version-specific N64 strategy or a factored shared core with unchanged old
   behavior and full regression coverage.
2. **Stale decision provenance.** The former offline decision pins the 32-neuron
   manifest, emulator, reports, and old reviews. A new exact N64 decision must
   pin current target, runtime-state, emulator, evidence manifests, reviews,
   versions, names, and policy. A missing, extra, stale, false, or mismatched
   field must abort before output creation.
3. **TOCTOU between validation and use.** Do not hash a path and later reopen it
   unverified for construction. Load each immutable input once into a byte
   object after path/link checks and construct from those validated bytes; then
   rehash the source paths after construction and require they are unchanged.
4. **Partial success artifacts.** Build every package and report in memory
   first. Use exclusive create-new semantics and one rollback-capable
   transaction for the new package pair and version-specific reports, or an
   equivalent transaction whose failure removes every newly created file.
   Register a created path immediately after successful exclusive open and
   before write/flush/fsync. Short writes, write errors, flush errors, fsync
   errors, rename errors, cleanup errors, and readback mismatches must be fatal.
   A failed run may not leave a PASS manifest or a partial package pair.
5. **Existing-file destruction.** Refuse overwrite of originals, prior
   candidates/restores, new outputs, and reports. Reject hardlinks, symlinks,
   reparse points, traversal, UNC/device paths, non-fixed volumes, any `D:`
   alias, and input-output identity. Required names must be direct children of
   the resolved local quarantine root and end
   `.gcd.analysis-only.DO_NOT_INSTALL`.
6. **Broad difference allowlists.** A whole allocation envelope is valid as a
   confinement boundary, but the strict profile must also reconstruct exact
   expected bytes and list actual changed ranges. The first four outer
   checkpoint bytes must remain official for this pair.
7. **Restore derived from candidate.** That can preserve custom bytes in gaps or
   an unintended patch. Restore must start from the pinned official package and
   explicitly verify the official hook plus both complete official envelopes.
8. **Helper ambiguity.** Require both decoded helper bytes and parsed helper
   descriptor fields to remain official. Main descriptor/header coherence does
   not authorize changing the helper's official 1370 descriptor.
9. **Generic verifier weakening.** Add opt-in exact N64 candidate/restore
   profiles, or an equally strict dedicated verifier. Default generic behavior
   must continue rejecting descriptor-changing packages outside explicitly
   named profiles.
10. **Emulating the wrong bytes.** Re-run target/emulator evidence against the
    hook and segments extracted from the reconstructed candidate, and require
    them to equal the reviewed Task 4 binaries. Passing the canonical build
    alone does not prove the package contains it.
11. **Self-hash paradox or untracked outputs.** State explicitly when a manifest
    omits itself, enumerate every other generated file, reject untracked build
    or analysis residues, and verify all ledgers after the final write.
12. **Misstating recovery.** Package-format PASS proves recovered GarminOS-side
    structure/checksums and exact bytes. It does not prove resident-loader
    behavior, interrupted-update recovery, or acceptance of this workload.

## Staging guard audit

At the first read-only snapshot,
`tools/live-proof/stage-gupdate.ps1` had SHA-256
`0655965f02c43447cccc2be99475bcc0d3da200928b8c51d830b8fbcd1837662`,
contained only five older modes, and rejected an N64 mode at PowerShell
parameter validation before the script body ran. During this audit, concurrent
Task 5 implementation changed the script to 10,215 bytes, SHA-256
`864c9f5752b3782d9d9b52e035d8d51319d78a8bc757f5e2511116b73652f113`.
The new snapshot recognizes `NeuralSpecimenN64Overlay1374` and
`NeuralSpecimenN64Restore1375` only so an immediate `$BlockedN64Artifacts`
check can throw before `$profiles`, source access, volume discovery, or device
queries. The blocked records contain the two expected paths and hashes, and
neither record is an enabled staging profile.

One material gap remains: rejection is selected only by the requested mode.
The script does not compare every enabled profile's source path/basename/hash
to the blocked records. A later edit could therefore place a blocked N64 source
under a different allowed profile name and bypass the denylist. The final
script and its tests must satisfy all of these conditions:

- neither N64 package is present in the enabled `$profiles` table;
- any N64 names admitted by `ValidateSet` exist solely to reach an immediate
  deny branch before all device/path access and are absent from `$profiles`;
- a denylist names both exact forbidden modes, both exact filenames/relative
  paths, and both exact expected hashes from this audit;
- before selected-profile source access, startup validates every enabled
  profile against the denylist and throws if a
  future edit aliases a forbidden mode, basename, normalized source path, or
  hash;
- the denylist is data only and cannot be selected as a profile;
- regression tests prove ordinary invalid N64 mode invocation fails before
  volume/device discovery, and source-level mutation tests prove that adding a
  forbidden path/hash to an enabled profile trips the guard;
- no test invokes an enabled staging mode, uses `-Execute`, or touches a device
  volume.

Embedding the two N64 hashes in a **denylist** satisfies hash-based rejection;
embedding either in an enabled profile would violate the task. After any
future separately approved one-use staging event, the enabled profile must
again be removed, as was done for the 13.73 neural candidate.

## Recovery limits and rewrite scope

The official helper stages and rewrites the complete main image; this is not a
four-byte live patch. The recovered erase scope is internal application flash
`0x00003000..0x001fffff` and external QSPI
`0x68617000..0x68916fff`. The 0x4d8000-byte main programs internal
`0x00003000..0x001fffff` and external
`0x68617000..0x688f1fff`; the external erase tail
`0x688f2000..0x68916fff` is not populated by the decoded main. The resident
prefix `0x00000000..0x00002fff` is outside the observed helper rewrite, but its
behavior and other loader-owned state are not fully acquired.

The future 13.75 wrapper is the best application-level restore candidate only
while all of these remain true: GarminOS boots, USB mass storage enumerates,
the FAT volume is healthy, the updater accepts the package, and the resident
loader/helper reaches the rewrite path. It cannot recover a damaged resident
loader, a device that no longer enumerates, an early application crash that
prevents the updater, or an interrupted rewrite whose recovery behavior is
unknown. Accessible-file backups do not include all loader, option, calibration,
identity, or secondary-processor state. Brick risk remains nonzero and
unquantified; custom-firmware feasibility remains YELLOW.

## Exact Task 5 review checklist

The final Task 5 review should report RED if any item below is false.

### Immutable inputs and versions

- [ ] Official package, decoded main, and decoded helper match the three pinned
  SHA-256 values and sizes above; parsed device is non-Music HWID 3076.
- [ ] N64 hook/primary/secondary match exact sizes, ranges, hashes, manifest,
  allocation JSON, runtime-state JSON, emulator evidence, and final review pins.
- [ ] Candidate main descriptor/header are both 1374; restore main
  descriptor/header are both 1375; candidate is strictly newer than installed
  1373 and restore is strictly newer than candidate.
- [ ] Old package tools, reports, candidates, restores, originals, and source
  evidence are byte-identical before and after the run.

### Construction and confinement

- [ ] Candidate and restore have only the exact required names, direct local
  quarantine parents, warning suffixes, and create-new behavior.
- [ ] Traversal, alternate roots/drives, D/device/UNC/removable paths, reparse
  points, symlinks, hardlinks, aliases, input-output identity, and overwrite all
  fail before mutation.
- [ ] Candidate starts with official full envelopes, copies exact compiled
  prefixes, leaves seven/fourteen gap/tail bytes `0xff`, and uses primary repair
  `0xb5` only at the reserved byte.
- [ ] Restore starts independently from official and restores official hook plus
  every byte of both complete envelopes.
- [ ] Injected open, short-write, write, flush, fsync, rename, readback, and
  cleanup failures leave no new package, report, PASS manifest, temp, or backup
  residue; an unremovable residue produces a fatal path-specific error.

### Exact package verification

- [ ] Candidate package/main hashes equal `3a4a...34cd` and `66566...a6f4`;
  restore package/main hashes equal `ccd2...e5da` and `b2eb...905e`.
- [ ] Complete package size, all 93 record offsets/IDs/lengths, main/helper
  declared lengths, HWID, field `0x0b`, and stream ordering equal official.
- [ ] Decoded helper bytes and helper descriptor are byte-identical to official.
- [ ] Candidate decoded/raw differences total exactly 3,040/3,042 bytes and
  are both confined and byte-exact; restore differences total exactly 2/4.
- [ ] Candidate repair bytes are primary `0xb5`, final `0xc0`, and only changed
  outer checkpoint `0x4e229e`; restore final is `0xbf` with the same sole changed
  outer checkpoint.
- [ ] Both main additive sums are zero; all five outer checkpoints validate;
  both full-image validations pass; exact in-memory reconstruction matches both
  written files byte-for-byte.
- [ ] Candidate-extracted hook and segments are run through the final N64
  build/emulator/evidence checks and reproduce the reviewed behavior and hashes.
- [ ] Opt-in N64 generic profiles and dedicated pair verifier pass while default
  generic verification remains unchanged and restrictive.

### Evidence, live boundary, and documentation

- [ ] Every output/report has a SHA-256 ledger entry; every ledger entry is
  rehashed after all generation; untracked files are rejected.
- [ ] `stage-gupdate.ps1` has no enabled N64 profile and explicitly rejects both
  modes, names/paths, and hashes; its offline rejection tests do not access the
  watch.
- [ ] Reports state `packaging_allowed:false`, `live_staging_allowed:false`,
  `live_write_allowed:false`, semantic inventory incomplete, and feasibility
  YELLOW.
- [ ] The N64 live proposal lists exact artifacts, bytes, destination,
  internal/external erase and programmed ranges, nonzero brick risk, no known
  nonboot recovery, restore dependence on booting GarminOS/USB, and the exact
  official source hash.
- [ ] The proposal requires a new exact-action user approval after those final
  hashes and risks are presented. No package is copied, renamed, linked,
  redirected, staged, ejected, installed, or exposed to an updater during Task
  5.

## Conclusion

The correct monotonic pair is **13.74 candidate / 13.75 restore**. The expected
offline package identities are concrete and independently reproducible from
the preserved official bytes and final N64 segments. This supports strict local
quarantine construction. It does not improve nonboot recovery and does not
authorize a watch write. The staging guard must remain closed until a later
exact proposal is independently reviewed and explicitly approved.

## Final implementation re-review (2026-09-15)

**SPEC: FAIL**

**QUALITY: FAIL**

The completed artifacts reproduce the independently predicted package pair,
and the staging alias gap identified above is fixed. One core immutable-input
failure remains in the reusable construction path, so this review fails closed
despite the currently generated package bytes being exact.

1. **HIGH - validated input bytes are discarded and then reopened:**
   `tools/garmin-firmware/neural_specimen_n64_version_strategy.py:114-128`
   reads and hashes each pinned file but returns only metadata.
   `load_and_validate_decision` then reopens the official package, extracted
   streams, prior reports, allocation, manifests, and emulator report at
   `:300-441`; after it returns, `construct_pair` reopens the official package
   and all three target segments again at `:743-750`. The attestation path also
   validates candidate and restore and then separately rereads both at
   `:966-979`. A file changed between those opens can therefore supply bytes
   different from the bytes whose SHA-256 is recorded in `validated_inputs`.
   This violates Task 5's immutable-input and fail-closed requirements. Load
   each pinned file once and carry its validated byte snapshot through parsing,
   construction, and reporting, or rehash the exact consumed bytes after use
   and before any output creation. Add a regression test that substitutes a
   different second read and proves rejection with no output.

2. **MEDIUM - fault-injection coverage does not exercise two promised failure
   branches:** `tools/garmin-firmware/tests/test_neural_specimen_n64_version_strategy.py:176-197`
   injects raised write, flush, and fsync errors, but does not make `write`
   return a short count without raising and does not make cleanup unlink fail.
   The implementation detects a short count and raises a fatal, path-specific
   error when cleanup cannot be confirmed at
   `neural_specimen_n64_version_strategy.py:1048-1065`; focused tests should
   prove both branches because the pre-review checklist explicitly made them
   release conditions.

### Verified final package evidence

Fresh `verify_exact` execution against the two written quarantine files
returned `PASS` with all eight checks true:

| Artifact | Bytes | SHA-256 | Decoded-main SHA-256 |
| --- | ---: | --- | --- |
| 13.74 N64 candidate | 5,120,675 | `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd` | `66566f18da04936c9da0c4638860cb493421582e63d6a129f6ae206fb034a6f4` |
| 13.75 official-code restore | 5,120,675 | `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da` | `b2eb6f13c1bffe59b0cb59e8b4c3811dcca46866b27dd51c315160f46c21905e` |

The candidate and restore main sums are both zero. Candidate decoded/raw
changed-byte counts are 3,040/3,042; restore counts are 2/4. The exact repairs
remain candidate primary `0xff -> 0xb5` at decoded `0x1f33ff`, candidate final
`0xc4 -> 0xc0`, restore final `0xc4 -> 0xbf`, and the sole changed outer
checkpoint `0x4e229e` for both packages. Both retain helper SHA-256
`f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46`.

The focused strategy suite freshly passed **13/13** tests in 131.229 seconds.
All eight entries in
`artifacts/firmware/analysis/neural-specimen-n64-package-SHA256SUMS.txt`
freshly rehashed to their listed values. Candidate and restore generic profiles
both report `visible_gate_result: PASS`, byte-exact reconstruction, coherent
descriptor/header versions, and offline policy gates remaining false.

### Deliverables and live boundary

The required Task 5 report now exists. Its current SHA-256 is
`86f8f62b7472fbd4c476d2cb1331c5f7333f0ec51c54aed5cc8d052614b4c8aa`.
The build, strict, reconstruction, combined full-image, packaged-emulator,
exact-difference, risk, generic, per-package full-image, and ledger-verification
reports exist with the hashes recorded in that report. The N64 live proposal
was subsequently completed and now has SHA-256
`e2b0aa7e8523d8dd513335ca131ba749eec0fa68ce74cd05366206f49748ad46`.
The current proposal explicitly states YELLOW feasibility, GarminOS-resident
overlay limits, unavailable HR/motion/charging telemetry, nonzero brick risk,
zero measured target-stack margin, no known nonboot recovery, and the
restore's dependency on a booting GarminOS/USB update path. It also supplies
the conditional, exact-hash restore procedure and abort conditions rather than
implying that the earlier shorter proposal already contained those details.

`tools/live-proof/stage-gupdate.ps1` SHA-256 is
`eead19935f18aacf2fc015e1c90c8f875937528330419762702f773eb9c491ff`.
It has no enabled N64 profile. Lines 15-28 reject both recognized N64 modes,
and lines 63-81 audit every enabled profile against blocked mode keys,
normalized relative source strings, basenames, and hashes before line 83
selects a profile, line 85 resolves a package path, or line 100 queries a
volume. Mutation tests for path, basename, and hash aliases all pass. The live
boundary is therefore closed as required; this review accessed neither `D:`
nor the watch.

After the immutable-byte snapshot defect and missing fault-injection cases are
fixed and freshly verified, no other Task 5 spec or quality finding is known.

## Final fix-round re-review

**SPEC: PASS**

**QUALITY: PASS**

The two findings in the preceding review are addressed. No new finding was
identified.

1. **ADDRESSED - immutable input consumption:**
   `neural_specimen_n64_version_strategy.py:73-82` defines a frozen
   `PinnedSnapshot`. `load_pinned_snapshot` at `:131-149` performs one read,
   validates the size and SHA-256 of those exact bytes, and retains those bytes.
   `load_and_validate_decision` at `:311-338` deduplicates inputs by canonical
   path, rejects conflicting duplicate pins, and stores the same snapshot for
   every reference. Official stream comparison, version-chain evidence,
   allocation/manifest parsing, evidence validation, and emulator validation
   consume snapshot bytes at `:363-489`. Construction consumes the official,
   hook, primary, and secondary snapshots at `:795-845`; exact verification and
   attestation reuse the same validated set. Candidate and restore attestation
   also consumes the bytes from the single validated package snapshots at
   `:1037-1050`. The regression test mutates any second read of each construction
   binary and proves every tracked path is read exactly once while both expected
   package hashes are still reproduced.

2. **ADDRESSED - confinement and failure injection:** the focused suite now
   proves lexical `..` traversal rejection, create-new preservation, hardlink
   rejection, and symlink rejection when the host permits symlink creation.
   Separate tests inject a pure short-write return, cleanup-unlink failure,
   post-write readback mismatch, and final report-path corruption. They verify
   path-specific fatal errors, preservation of unrelated/existing bytes,
   transaction cleanup or explicit unconfirmed residue, report rollback with
   no temporary/backup residue, and successful retry after the injected
   condition is removed. `write_transaction` now reads every completed output
   back against its exact in-memory bytes at `:1131-1138` before success;
   `replace_reports_transaction` validates each installed final report at
   `:1194-1205` and restores the old reports on failure.

Fresh independent validation after the fixes:

- `python -B -m unittest tools.garmin-firmware.tests.test_neural_specimen_n64_version_strategy -v`
  passed **18/18** tests in **140.340 seconds**.
- A fresh `verify_exact` run returned `PASS` with all eight checks true,
  including byte-exact reconstruction and full-image validation for both
  packages and both offline policy gates remaining false.
- Candidate remains 5,120,675 bytes, SHA-256
  `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd`;
  restore remains 5,120,675 bytes, SHA-256
  `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da`.
- Refreshed build and strict reports both attest that package bytes and
  timestamps/creation metadata remained unchanged. Their current SHA-256
  values are respectively
  `8288628f26890412a1db6b82eac6b6cde6aa5e5d7e2c0a4f7269e43bc94a8009`
  and
  `878cf8de614b2fda5e9ebf9556aef77b40908251f8e6441d0b3cda1aea1176a6`.
- Every one of the eight package-ledger entries freshly rehashed exactly. The
  unchanged ledger SHA-256 is
  `96a4f8a42bd5e156a2c1fc6b6b7cdce5e6319413f3e55f906eb5899941b0da43`;
  the refreshed verification report SHA-256 is
  `4c8e008c7d6b776096926996ffb62f3662257544d58138e77533e4bf7962e90f`.
- Final strategy SHA-256 is
  `34b52ed750995a24c06c216437f3697ce9a2b6a9f5c341f07210f5a4ce11063e`;
  focused-test SHA-256 is
  `a25999f10d847bb2a2955239c660021b0f18ad07c66e745f84dc7191b2e56ab7`;
  Task 5 report SHA-256 is
  `86f8f62b7472fbd4c476d2cb1331c5f7333f0ec51c54aed5cc8d052614b4c8aa`;
  current live/recovery proposal SHA-256 is
  `e2b0aa7e8523d8dd513335ca131ba749eec0fa68ce74cd05366206f49748ad46`.

The staging guard remains unchanged at SHA-256
`eead19935f18aacf2fc015e1c90c8f875937528330419762702f773eb9c491ff`.
Both N64 artifacts remain unavailable through enabled profiles and are denied
by mode, normalized relative path, basename, and hash before package or device
access. Feasibility remains YELLOW, live staging remains closed, brick risk is
nonzero, and no nonboot recovery path is known. This re-review accessed neither
`D:` nor the watch.
