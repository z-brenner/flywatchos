# Independent audit of the first live proof

Date: 2026-09-13

Scope: offline review only. The watch volume was not accessed. No package was
renamed, copied to the watch, staged, installed, or executed.

## Decision

**NO-GO for the selected matched-13.69 candidate**, SHA-256
`d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.
It is a well-formed, strictly pinned offline mutation, but the proposed live
installation cannot truthfully be called reversible. If accepted, the update
helper erases and rewrites the full application and external code/resource
regions. The resident loader's authentication and failure ordering are
unknown. Official 13.70 is a credible forward-restore candidate only after a
normal boot and only if the installed-version path uses the inferred 13.69
field; there is no established recovery when the application does not boot.

The decision is `hold_for_evidence`, rather than a claim that installation is
known to fail. The missing evidence could change the recommendation.

## Exact artifact identity and independent diff

The official non-Music HWID-3076 package is 5,120,675 bytes and has SHA-256
`8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`.
The selected candidate is the same length and has SHA-256
`d89d52ca82586d7cea003c2f5b65b854790b572246164064fe3df079fa36ca2f`.

An independent flat-record parser and raw byte comparison, implemented without
calling the repository verifier, found exactly 93 records and exactly 20
changed bytes:

| Raw offset | Change | Purpose |
|---:|---|---|
| `0x0000a160` | `0x055a` -> `0x0559` | Main GCD descriptor 13.70 -> 13.69 |
| `0x0000a392` | `0x5a` -> `0x59` | Decoded main header version low byte at `0x22c` |
| `0x00448d1a..0x00448d29` | 16-byte text replacement | Decoded main resource at `0x43eaa4..0x43eab3` |
| `0x004e2299` | `0xc4` -> `0xc5` | Decoded main additive repair at `0x4d7fff` |
| `0x004e229e` | `0xf7` -> `0xf8` | Final outer checkpoint repair |

The resource change is:

```text
536f6674776172652056657273696f6e  Software Version
464c59204c495645532032414c495645  FLY LIVES 2ALIVE
```

The record layout is identical. The decoded main hashes are
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`
for the official package and
`f63c628af1e3b7df8232dc309d839d09265b9f906f9401e84bbad941e988c478`
for the selected candidate. Both main streams sum to zero modulo 256. The
selected main descriptor and inner header both report 13.69. The 37,120-byte
helper is byte-identical in both packages, SHA-256
`f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46`.
All five outer checkpoint prefixes and the prefix before the end record also
sum to zero modulo 256.

The resource classification is strong but not executable proof. Official 13.70
contains one occurrence of `Software Version` at decoded `0x43eaa4`, adjacent
to `Unit ID` and `Bluetooth MAC Address`. Official 3.10 contains the same unique
cluster at `0x3dca88`. The fixed-length edit preserves the terminating NUL and
allocation boundary. The indirect resource resolver was not traced to the
renderer, so a visible About-page change remains strongly inferred.

The earlier resource-only candidate
`b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba`
changed only the 16 text bytes and remained 13.70. It is superseded as the live
proposal because byte-identical official 13.70 is not a dependable
normal-mode same-version restore.

## Acceptance probability

There is no defensible numerical probability because the resident loader was
not acquired and there are no device trials. The evidence supports this
ordinal assessment:

| Outcome | Assessment | Basis |
|---|---|---|
| Candidate installs and GarminOS boots | Plausible; somewhat favored, low confidence | Current 10.40 is older than incoming main 13.69 and helper 13.70, the strict exact profile passes every recovered full-image check, no full-image signature object was identified, and the helper is official and unchanged. |
| Candidate is rejected safely | Plausible, low confidence | The resident loader may enforce an unobserved signature, digest, or version-consistency rule. Whether it rejects before destination erase is unknown. |
| Candidate causes a partial or non-booting install | Plausible and non-negligible | The helper's destination erase is destructive, and no power-loss or late-validation recovery behavior has been demonstrated. |

Thus the package may be more likely to install than to be rejected by the
checks already recovered, but that observation does not make the experiment
safe. The unknown path controls the worst outcome.

## Full-application brick scenarios

| Point of failure | Expected effect | Recovery status |
|---|---|---|
| Host copy fails before disconnect | Incomplete FAT file or filesystem damage; installed application is still present | File cleanup may be possible if normal USB remains, but this is not the principal firmware risk. |
| GarminOS preflight rejects before staging | Installed application remains intact | Likely recoverable by deleting the rejected file, but the exact rejection behavior is not observed. |
| Power loss while staging type `0x0e` | The active application may remain intact; external staging is incomplete | Unknown update-state cleanup or retry behavior. |
| Resident loader rejects before helper launch | Active application may remain intact | Safe only if validation conclusively precedes destination erase; this ordering is unknown. |
| Power loss or error after type `0xaf` erase starts | Internal `0x00003000..0x001fffff` or external `0x68617000..0x68916fff` is erased or partially programmed | High brick risk. The resident prefix survives, but no FR245 recovery protocol through it is established. |
| Destination checksum fails after programming | The helper should avoid jumping to a bad application, but its retry/recovery handoff is not proven | Unknown; the watch may stop normal USB enumeration. |
| Patched application boots | The same-length resource edit is unlikely to destabilize code; expected result is a changed About label | Official 13.70 should be a forward update if GarminOS reads the selected 13.69 header as the installed version, but this linkage is not fully proven. |

The static copy target excludes internal `0x00000000..0x00002fff`, but survival
of that resident prefix is not a recovery mechanism by itself.

## Restore eligibility

The selected candidate sets both the incoming main descriptor and inner image
header to 13.69. It remains newer than the connected watch's 10.40 application,
while preserved official 13.70 is numerically newer than the candidate. Its
strict named profile `flyos-visible-proof-matched1369` passes and pins all 20
raw changes.

The inner version field is not arbitrary: in the stable Garmin image header it
is 28 bytes after the marker pair used by the recovered header scanner, exactly
where the caller receives its current-version value. This makes a normal
candidate-to-official forward restore credible after a successful boot. The
remaining 13.70 identity mirrors, the exact 13.70 call/region linkage, and the
resident loader's consistency rules are not fully established. If the
candidate does not boot or enumerate, the version advantage is unusable
because no FR245-specific preboot reinstall path has been demonstrated.

The superseded and alternate candidates are:

| Variant | SHA-256 | Assessment |
|---|---|---|
| Superseded same-version resource proof | `b6e61518890d8082d96baf9bd89dcb131317f40060136093c9250e343a8ab4ba` | Exact 16-byte text edit, but an installed 13.70 application is expected to skip official 13.70. **NO-GO.** |
| Header-only 13.69, descriptor 13.70 | `da4e5d5f2d19ae8312cf56937873495547ea3c74142a26ae535c1059aa75b90b` | Better only if the later installed-version read comes from header offset `0x22c`. It creates a descriptor/header mismatch that the resident loader may reject. **NO-GO.** |

The same-version code-overlay candidate
`2ff367c2e7a80ec9ea2397352cba99c1f4d3212ab6dbea561050715155b1bf76`
changes 278 bytes, including executable instructions and a code cave. It has
the same unresolved loader and restore risks plus runtime-hook risk. It is a
clearer **NO-GO** than the resource-only candidate. Its reserved allocation is
exactly `0x001f6000..0x001f63ff`; Ghidra reports zero static references into
that 1 KiB interval. The wider erased tail is not wholly unused and has 19
later data references, so only the exact allocation has placement evidence.

## Validation and limits

The selected matched-13.69 strict profile rerun passed and produced
`matched1369-strict-verifier-rerun.json`, SHA-256
`4b728ab256a759494d0066335a729fd4a68c15bc8437b4edec3633a21900c2a6`.
The selected candidate's independent full-image validator rerun also passed
and produced `matched1369-full-image-validator-rerun.json`, SHA-256
`5a4976afe5d46df5735f703d1b6d6bebfcb1ce8ae91d593bc3064b26c270d35d`.
The superseded same-version profile also remains pinned in the audit directory;
it is not the subject of this decision.
The complete 29-test `garmin-firmware` suite passed after the working files
settled. It includes the selected candidate, strict verifier, full-image
validator, and 13.69 lab builder.

These checks protect package identity, layout, the intended byte diff, and the
known GarminOS application checks. They do not exercise resident-loader
authentication, flash interruption, boot, USB recovery, or official
reinstallation.

## Minimum evidence required to change the verdict

1. Recover the resident `0x00000000..0x00002fff` loader from a legitimate
   artifact or an expendable identical unit and show that complete validation
   precedes type-`0xaf` erase, including its signature-failure and interrupted
   update paths.
2. Establish a Forerunner-245-specific recovery mode that can rewrite the
   application with the preserved official package when the normal application
   does not boot, demonstrated on an expendable identical unit.
3. For a 13.69 approach, trace the 13.70 installed-version getter to the exact
   inner field and destination region, determine whether the remaining 13.70
   identity mirrors are loader-relevant, and demonstrate the strict-profile-
   pinned candidate to official-13.70 restoration sequence on an expendable
   identical unit.

Until at least one complete recovery route and the loader's pre-erase behavior
are demonstrated, no exact live action involving this package is reversible.
