# Task 5 report - quarantined Neural Specimen N64 package pair

## Result

**PASS — offline construction and verification only.**

The exact reviewed Task 4 hook/primary/secondary binaries were wrapped from the
pinned official Forerunner 245 non-Music HWID-3076 13.70 package as the next
monotonic pair after the live-proven synthetic 13.73 overlay. No watch,
removable volume, Garmin updater directory, `GUPDATE.GCD`, reset, eject, or
install action was accessed or performed.

| Artifact | Version | Bytes | SHA-256 |
|---|---:|---:|---|
| `Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL` | 13.74 | 5,120,675 | `3a4a4af6355c132571c1158667cc43c96bf5da7a67737ab028267930e71134cd` |
| `Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL` | 13.75 | 5,120,675 | `ccd2a29c51a41a436111239c7181e1cb0cea1f2fac1c48d600fff6dec103e5da` |

Both exist only under `artifacts/firmware/quarantine/` and retain the warning
suffix. They were created with exclusive create-new semantics and were never
staged.

## TDD evidence

RED was observed before implementation for each new behavior:

- Missing strategy module: `ModuleNotFoundError`.
- Missing pinned decision/strategy interface: `DECISION_RELATIVE_PATH` absent.
- Missing report bundle: `build_attestation_bundle` absent.
- Staging alias regression: an enabled profile pointed at the blocked N64 path
  and reached source lookup instead of an explicit pre-device rejection.
- Immutable-input regression: a second read after successful SHA-256 validation
  consumed mutated official/segment bytes.
- Lexical traversal regression: an output containing `alias/../` was accepted.
- Final report readback regression: report replacement did not verify the bytes
  at the installed final path.
- Test-quality regression: Windows symlink creation failure was silently
  accepted, so the passing test did not prove a reparse alias was rejected.

GREEN evidence:

- N64 package strategy after final review fixes: **20 passed, 1 explicit
  host-capability skip (21 discovered)** in 156.606 s.
- N64 target/Unicorn suite after tool changes: **20/20 passed** in 216.344 s.
- Complete firmware Python discovery: **151/151 passed** in 661.229 s.
- Shared C/CTest: **7/7 passed**.
- Target rebuild: hook 4 bytes, primary 1,016, secondary 2,034, stack 384;
  hashes exactly matched Task 4.
- Python bytecode compilation: passed.
- Package SHA ledger: **8/8 entries rehashed exactly**.

The tests cover the exact 1373 -> 1374 -> 1375 version sequence, all pinned
inputs/reviews, full envelope reconstruction, helper identity, exact segment
placement, confinement of every decoded/raw difference, additive/checkpoint
repairs, strict reconstruction, opt-in generic profiles, create-new/no-overwrite
semantics, pure short-write detection, path-specific cleanup-unlink failure,
post-write and post-rename readback, safe retry, lexical traversal, a real NTFS
junction/reparse alias, hardlink rejection, alternate exact-root rejection,
output-path confinement, and pre-device staging rejection by mode, path,
basename, and hash. Ordinary symlink creation is unavailable to this process
(`WinError 1314`), and that case is now reported as an explicit skip instead of
a false pass.

## Immutable inputs

| Input | SHA-256 |
|---|---|
| Official 13.70 GCD | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| Official decoded main | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| Official helper | `f2351f808c0510baba6aae045867d8a366646511da662a411038426107725e46` |
| N64 decision | `bd1cf1e2565889195c84f5d8504c07dd4e49d572a96b9692c0ec2f18e276c123` |
| Allocation JSON | `86251e3cbaa39fa46b0986d39a84f48864f9c51fb15b59fafec5b6af3406f4bb` |
| Runtime-state JSON | `53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d` |
| Target manifest | `b358b89867076e594c545447267819fc92ba1fa8290c2d4c0213c1ec332acfbe` |
| Evidence manifest | `a0cc54142febda3d12033dc8d9a37358022ac871989aca0252ae475b110889ba` |
| Hook | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Primary | `fd7e2064e0e513169b6f2aa4643603e0ea1c274a695960a6d436d54dbb2ca282` |
| Secondary | `f8c7f544f9bbf72fc1dd164852ebdc8c7e1d5f53c52e68f9be83f781ed3d2406` |

The decision also pins and validates every target-manifest file/source entry,
every evidence-manifest file/build entry, pre-Task-5 review hashes, the exact
prior 13.73 package, its build and strict reports, and the read-only post-install
observation.

Every pinned path is opened once into an immutable byte snapshot. Duplicate
manifest references reuse the canonical snapshot after checking that their
expected size and SHA-256 agree. Parsing, construction, exact verification,
attestation, and report hashes all derive from those snapshots. Candidate and
restore outputs are checked against the exact in-memory bytes after the atomic
write; report replacements are likewise reread at their final paths and roll
back on mismatch.

## Package semantics

Candidate main SHA-256 is
`66566f18da04936c9da0c4638860cb493421582e63d6a129f6ae206fb034a6f4`.
It contains the exact hook at `0x00009a20..0x00009a23`, primary payload at
`0x001f6000..0x001f63f7`, secondary payload at
`0x001fa400..0x001fabf1`, and coherent 13.74 metadata. Seven primary gap bytes
and fourteen secondary tail bytes remain official `0xff`. Primary additive
repair is `0xff -> 0xb5` at runtime `0x001f63ff`; final decoded-main repair is
`0xc4 -> 0xc0`; only outer checkpoint raw `0x4e229e` changes.

Restore main SHA-256 is
`b2eb6f13c1bffe59b0cb59e8b4c3811dcca46866b27dd51c315160f46c21905e`.
It is built independently from official 13.70, restores the official hook and
every byte of both complete allocation envelopes, retains official resources
and helper, and applies coherent 13.75 metadata. Final decoded-main repair is
`0xc4 -> 0xbf`; only outer checkpoint raw `0x4e229e` changes. It is accurately
described as an official-code restore wrapper, not byte-identical official
firmware.

Candidate decoded/raw changed-byte counts are 3,040/3,042. Restore counts are
2/4. Every contiguous actual change is recorded in
`neural-specimen-n64-exact-differences-1374-1375.json`.

## Reports and hashes

| Report/tool | SHA-256 |
|---|---|
| Build report | `8288628f26890412a1db6b82eac6b6cde6aa5e5d7e2c0a4f7269e43bc94a8009` |
| Strict verification | `878cf8de614b2fda5e9ebf9556aef77b40908251f8e6441d0b3cda1aea1176a6` |
| Reconstruction | `9d2d4b315eea90a95464bd64f4bea2a2201fcfd64293fe31272b1c841f4c227c` |
| Combined full-image | `9c9d8d2bbaaf25250ada32e468a9a6528ee64ebf31883ef67030765f58d28de1` |
| Packaged-emulator binding | `deb8c1042504891da3aa5b46a1ae67c3890d8f70775c4ec4b9642142183e2e0a` |
| Exact differences | `874f54be1bbdbf5b620102f49f91249ff516879eff1be22b94f5c37fc84cbccc` |
| Risk report | `ba1b20563b0c641dc9ed85e2be9d2a72547a1ab7f2fc46ec7fd9434813d95324` |
| Package SHA ledger | `96a4f8a42bd5e156a2c1fc6b6b7cdce5e6319413f3e55f906eb5899941b0da43` |
| Ledger verification | `4c8e008c7d6b776096926996ffb62f3662257544d58138e77533e4bf7962e90f` |
| Candidate generic verifier | `8f61ad35ad5f2026f92c289d9af9ed3bcbb3f7a6aa57f365fad6cd93a0bff808` |
| Restore generic verifier | `bbba041b47378ed97cb63b5661bd311634db0030c74e1926fa1f61d0c7618feb` |
| Candidate full-image validator | `a234538b7af9abe0be34a658fe6a8d375a714c3d7724093605c4dd45edef76d5` |
| Restore full-image validator | `e585ae5aad1f7cab5f0ea313e6923bb5ca56659b5506b762ce23703f18a32551` |
| N64 strategy | `34b52ed750995a24c06c216437f3697ce9a2b6a9f5c341f07210f5a4ce11063e` |
| Strategy tests | `a25999f10d847bb2a2955239c660021b0f18ad07c66e745f84dc7191b2e56ab7` |
| Generic verifier | `c1000c4e4375ae3d74401f11e00f88295ef9999f43ce25ea3581a786bcc5494f` |
| Staging guard | `eead19935f18aacf2fc015e1c90c8f875937528330419762702f773eb9c491ff` |
| N64 live/recovery proposal | `e2b0aa7e8523d8dd513335ca131ba749eec0fa68ce74cd05366206f49748ad46` |

## Live boundary and recovery

The staging guard contains no enabled N64 profile. It recognizes the two N64
mode names solely to throw an explicit error before source resolution or any
volume/device query. It also scans every enabled profile for aliases to the
blocked N64 relative paths, basenames, and hashes. The independent pre-review
identified the alias gap; the final implementation and mutation tests address
it.

Brick risk remains nonzero. The restore requires GarminOS, USB mass storage,
and the normal updater to boot and accept its synthetic wrapper. No known
nonboot recovery exists. Target-owned stack use reaches 384 bytes with zero
measured margin, and the final-read-to-render home-view freshness race remains.
Feasibility stays **YELLOW**.

This is a GarminOS-resident overlay, not standalone FlyOS, a bootloader
replacement, or proof of arbitrary-image/arbitrary-boot execution. HR BPM,
motion, and charging telemetry are unavailable in this build; the face shows
`HR --` and `MOTION --`, while stock Garmin non-home charging, USB, update,
notification, menu, and critical screens pass through unchanged.

`docs/neural-specimen-n64-live-proposal.md` records the complete-image erase and
program scope, exact candidate/destination proposal, risks, and a conditional
step-by-step restore procedure. Restore is possible only if GarminOS and USB
storage still boot. It requires read-only device/volume/pending-update checks,
the exact 5,120,675-byte 13.75 restore hash, separate exact approval, a temporary
independently audited restore profile because the current guard blocks it,
atomic create-new staging to `D:\Garmin\GUPDATE.GCD`, destination rehash, safe
eject, Garmin UI installation, and read-only post-boot behavior/version/file
verification. It explicitly aborts on any identity, volume, pending-file,
hash, write, flush, rename, eject, UI, or post-boot mismatch and cannot recover
no-enumeration, early-boot/updater, or resident-loader damage.
