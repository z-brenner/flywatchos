# FlyOS neural overlay: placement and RTC audit

The exact 2,048-byte candidate `0x001fa400..0x001fabff` has no observed
references or occupied Ghidra units, but it is **not an approved allocation**.
The strict machine-readable placement result is `selected_interval: null`
and `packaging_allowed: false`. A separate `link_and_emulate_allowed: true`
permits offline ELF/link/Unicorn work within this exact observed-clean range.
Installable packaging remains blocked; host simulation and preview can continue.

## Pinned input and mapping

The audit opened only the preserved decoded non-Music FR245 13.70 image:

`artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`

- Size: 5,079,040 bytes.
- SHA-256: `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`.
- File offsets `0..0x1fcfff` map to internal addresses `0x00003000..0x001fffff`.
- File offsets `0x1fd000..0x4d7fff` map to external XIP `0x04600000..0x048dafff`.
- Internal slice SHA-256: `86c465ac975c6d061fe7831c45eb0529692e85f6e1128e8360fbaae5f98dbb5f`.
- External slice SHA-256: `2fe66af98be9894949b0aece203378421ac3f263c208a8e8b402524be2e8209f`.

The full-image sliding pointer scan uses file offsets for source locations.
The scanner's generic evidence-coverage convention is `base + file_offset`;
this does not assign appended XIP bytes a false runtime address. The report
records the actual two-segment mapping separately. Both Ghidra memory-block
hashes were compared with the corresponding pinned image slices.

## Exact placement evidence

| Candidate, inclusive | Length | `0xff` throughout | Existing Ghidra targets | Sliding pointer hits | Verdict |
|---|---:|---|---|---:|---|
| `0x001f5e0c..0x001fffff` | 41,460 | Yes | 19 edges, 12 distinct targets | 1,066 | Rejected; references and existing overlay overlap |
| `0x001f6000..0x001f63ff` | 1,024 | Yes | 0 in existing exact export | 1 | Rejected as a second interval; already allocated and too short |
| `0x001f6400..0x001fbfff` | 23,552 | Yes | 0 in the broad-tail export | 110 | Rejected; conservative pointer hits |
| `0x001fa400..0x001fabff` | 2,048 | Yes | 0 in fresh CODE and DUAL queries | 0 | Observed clean; incomplete semantic placement evidence |

Every possible four-byte little-endian word in the full input is examined,
including unaligned starts and the final possible word. A value targets a
candidate if either the exact value or its even Thumb address lies inside the
inclusive bounds. These are conservative relocation-like hits; coincidental
instruction and resource bytes are not classified as confirmed pointers.
Their presence rejects a candidate without asserting that the stock firmware
actually follows them. In particular, this does not revise the earlier
single-allocation hardware result.

The fresh read-only Ghidra script queried every byte of the exact 2 KiB
candidate, including both endpoints and any unit beginning before the
candidate. It found:

- 2,048 bytes examined, all `0xff`;
- zero references from the databases to any candidate byte;
- zero overlapping instructions, defined data units, or function bodies;
- one containing internal memory block, with no coarse block boundary inside
  the candidate.

The query ran against both `FR245_1370_CODE` and `FR245_1370_DUAL`, with
`-readOnly -noanalysis`. The DUAL query includes the existing external XIP
analysis. These results measure the existing Ghidra databases; they do not
prove that every computed reference or semantic reserved field was recovered.
The whole erased tail is not free storage.

The exact candidate's file interval is `0x001f7400..0x001f7bff`. It does not
overlap the four-byte hook at `0x00009a20` or the existing
`0x001f6000..0x001f63ff` allocation (including its checksum-adjustment byte).
Architectural Thumb-2 `BL` reach checks pass in both directions between
candidate extremes and the hook/first allocation. This proves encoding reach
only, not any actual linked branch or executed control flow.

## Why packaging remains blocked

The repository does not contain a complete, image-bound semantic inventory
of section boundaries, update metadata, resource-directory spans, and
checksum/signature fields. A raw Ghidra `ram` memory block does not supply that
inventory. `docs/firmware-format.md`, under “Not established,” explicitly
leaves opaque firmware or device trust metadata unresolved. Observing erased
bytes and no database references is insufficient to certify that an interval
is not reserved metadata.

The scanner consequently does not turn the exact-range observations into
complete full-image evidence blocks. Missing or incomplete coverage remains
explicit, and every supplied candidate carries those rejection reasons.
The exact range is recorded only as `candidate_interval_observed_clean`.

Closing the static gate requires a verified pinned-image section and reserved
field map, from Garmin linker/update metadata or a complete recovered parser,
with byte-precise spans and explicit exclusion of this exact candidate. It
also requires complete image-bound decoded/reference/protected evidence for
the scanner. The fresh DUAL query closes the exact candidate database-query
gap; it does not close semantic metadata classification.

At the time of this audit, no neural target ELF/map with assertions for both
allocation bounds, full-image validation, or Unicorn execution of its
inter-allocation branches had been supplied. Prior single-allocation overlay
results do not satisfy those checks.
Those linked artifact and execution checks remain required. The controller
separately authorized offline linking and emulation using only
`0x001fa400..0x001fabff`, allowing that evidence to be developed while semantic
placement remains unresolved. The report records this as
`link_and_emulate_allowed` and `offline_interval`; neither field overrides
`packaging_allowed: false` or approves an installable package. No `.GCD`, target
payload, or quarantine artifact was created or modified by this audit.

## RTC read audit

The pinned 13.70 routine is `0x00009038..0x0000906b`. Its literal at
`0x0000906c` is `00 d0 03 40`, the little-endian address `0x4003d000`.
Ghidra and Capstone 5.0.7 agree on the instructions. The full disassembly is
embedded in the JSON report.

| Instruction addresses | Observed behavior |
|---|---|
| `0x903a` | Load RTC base from literal `0x906c` |
| `0x903c`, `0x9040` | Load seconds at base `+0x00`, repeat until equal |
| `0x9046`, `0x904a` | Load prescaler at base `+0x04`, repeat until equal |
| `0x9050`, `0x9054` | Load seconds again, repeat until equal |
| `0x905a`, `0x905c` | Compare seconds across the sample and retry on rollover |
| `0x905e`, `0x9062` | Mask prescaler to 15 bits and combine with seconds shifted 15 |
| `0x9066`, `0x906a` | Restore stack register and return |

The function writes its saved register to the stack and makes **no RTC
writes**. Repeated polling of the same words supports nondestructive reads in
the existing initialized GarminOS runtime. This supports the static RTC-read
audit; it does not establish standalone clock initialization or clock-source
configuration.

Do not call the stock 13.70 routine at `0x00009038`: its stabilization loops
are unbounded. `0x000c4438` is the corresponding **3.10** routine address, as documented in
`docs/driver-leads.md`. In the pinned 13.70 image that address is instead
`strh r6, [r0]` inside another function. It must never be called as the 13.70
RTC accessor.

The approved bounded overlay contract returns exactly one `uint32_t`. All
packing arithmetic is unsigned modulo 2^32; a second mismatch returns the
exact sentinel `0xffffffff`:

```text
for attempt in 0, 1:
    before = volatile_u32_read(0x4003d000)
    prescaler = volatile_u32_read(0x4003d004)
    after = volatile_u32_read(0x4003d000)
    if before == after:
        return ((after << 15) | (prescaler & 0x7fff)) & 0xffffffff
return 0xffffffff
```

Retry once after a mismatch; return `uint32_t` sentinel `0xffffffff` after a
second mismatch. Do not initialize or write any RTC register, and do not call
either `0x00009038` or `0x000c4438`. This bounded
seconds-prescaler-seconds sequence is the design contract, not a claim that
the stock routine has bounded loops. Target guard, rollover, access-width,
and write-confinement emulation is still required. If a later RTC audit fails,
the deterministic framebuffer-call counter is restricted to host/emulation
builds and the target package remains prohibited.

## Scanner interface and reproduction

`tools/garmin-firmware/find_overlay_allocation.py` takes explicit image, base,
minimum length, fill byte, candidate intervals, branch anchors, and four
evidence blocks: protected ranges, reference targets, decoded instruction/data
ranges, and section/metadata ranges. Each block must name its source, bind its
hash/base/length to the input image, declare literal Boolean completeness,
and cover the complete image. Empty findings require complete evidence.
Missing or malformed blocks, partial coverage, non-fill bytes, reference hits,
overlaps, section boundaries, and unusable Thumb reach all reject selection.
A candidate must fit at least one complete four-byte Thumb `BL`, even when
the caller requests a smaller minimum. Candidate-origin branch checks are
constructed only when their last source and all four bytes lie in the interval.

The CLI accepts `--image`, `--base`, `--minimum-length`, `--fill-byte`, repeated
`--candidate START:END`, repeated `--branch-anchor`, `--evidence`, and optional
`--output`. It emits deterministic JSON and exits 2 when no interval can be
selected. It never emits firmware. Static selection alone always leaves
packaging false because linked target execution evidence is outside this
scanner's scope.
Existing output files are checked with `Path.samefile` against both inputs
to reject hard-link aliases; an inability to establish identity fails closed.
Distinct new or existing JSON output files remain supported.

The JSON artifact contains the precise scanner inputs,
source paths/hashes, Ghidra command lines and report contents, every candidate
rejection, and RTC instructions. Reproduce the placement evaluation read-only
from the repository root:

```python
import json, sys
from pathlib import Path
sys.path.insert(0, "tools/garmin-firmware")
import find_overlay_allocation as scanner
report = json.loads(Path("artifacts/analysis/fr245-1370-second-allocation.json").read_text())
inputs = report["scanner_input"]
result = scanner.scan_allocation(
    image=Path(inputs["image_path"]).read_bytes(),
    **inputs["parameters"], **inputs["evidence"])
for key in result:
    if key != "packaging_blockers":  # audit report adds specific blocker descriptions
        assert result[key] == report[key], key
assert result["selected_interval"] is None
assert result["packaging_allowed"] is False
```

The authorized transient Ghidra evidence is under
`.superpowers/sdd/2026-09-14-flyos-ascii-brain/task-3-ghidra/`:
`ExactAllocationAudit.java`, `exact-allocation-code.txt`,
`exact-allocation-dual.txt`, `headless-code.log`, `headless-dual.log`,
`script-code.log`, and `script-dual.log`. Their hashes and exact commands are
in `artifacts/analysis/fr245-1370-second-allocation.json`.

## Validation

- Initial scanner test run failed as expected with `ModuleNotFoundError`
  before implementation.
- `python tools/garmin-firmware/tests/test_find_overlay_allocation.py -v`:
  **20 tests passed** in 0.245 seconds.
- Review fix round: `python -B tools/garmin-firmware/tests/test_find_overlay_allocation.py -v`:
  **25 tests passed** in 0.310 seconds, including 1/2/3-byte rejections,
  four-byte acceptance, and real temporary hard links to each input.
- Review fix round also verified **17/17 evidence-source hashes** and exact
  pinned scanner replay. The controller independently confirmed 25 focused
  passes and owns the final full firmware discovery rerun with Task 4 after
  rebuilding its manifest against the refreshed placement JSON.
- `python -m unittest discover -s tools/garmin-firmware/tests -p 'test_*.py' -v`:
  pre-review rerun **69 tests passed** in 162.312 seconds. The earlier run, before
  the additional CLI output-protection test, passed 68 tests in 163.993 seconds.
- Both read-only Ghidra runs completed successfully; complete report markers
  and both mapped-block hashes were checked against the pinned input.

The tests exercise every fail-closed input category, each reference byte and
boundary, unaligned/final-word pointer hits, branch encoding limits, a fully
covered accepted synthetic interval, deterministic JSON/selection order, and
CLI refusal to overwrite input evidence/images or emit non-JSON outputs.
