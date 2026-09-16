# FR245 atlas-shell feasibility gate

The current result is **BLOCKED: `go=false`**. The public tools reproduce a
partial offline evidence inventory and preserve every unresolved condition.
They do not authorize Task 2, create a target, or construct a package. The
installed synthetic 13.76 target and the watch are outside this analysis.

The input is the exact FR245 13.70 image, 5,079,040 bytes, SHA-256
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`, loaded at
`0x3000`. A missing or changed image closes every dependent gate. The required
private path is
`artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`.
No firmware, decompilation, watch data, or generated report belongs in Git.

## What was established

The key audit searches the entire image at every byte alignment for the
workspace base `0x1FFDBBC8`. It finds exactly `0xF840`, `0xFA3C`, `0xFA80`,
`0xFB0C`, `0xFCA0`, `0xFCD0`, and `0xFD00`. It hashes all seven required owners,
the schedule/cancel helpers `0x8844` and `0x8B04`, and list insertion at
`0x7BDC`. Capstone re-decodes the widths and offsets of reviewed memory access
sites. A four-byte access at offset `0x34` would fail; a two-byte access ends
at `0x35` and excludes the proposed pad.

The reviewed key accesses end at `0x35`. The two embedded scheduled objects
start at offsets `4` and `0x1C`; their reviewed fields and the separately
written tag words end by `0x33`. This is **not a complete alias proof**:
escaped scheduler pointers, dispatch consumers, computed aliases, callbacks,
and bulk initialization remain open. Consequently, each record reports
`max_audited_offset=53` but `max_stock_offset=null`, and `proved=false`.

Pinned key timing is: phase 0 publishes immediately; the initial deferred
request is 750 ms for LIGHT and 500 ms for the other keys; subsequent requested
periods are at most 200 ms; phase 2 compares elapsed time against 1000/500 ms;
phase 3 uses the later 5000 ms elapsed threshold. These are scheduler requests
and thresholds, not wall-clock execution bounds. Stock state can suppress
phase 4 publication.

The USB state-machine interval `0x20858..0x20A3F`, including the switch table,
has SHA-256
`2f9c2ca2710dae634ce952ba48ae34789e83fb902106e39869c0d9d36f93020a`.
The worker interval is `0x20A64..0x20AB7`. The report contains a reviewed local
state graph and the Ghidra control-flow graph, without treating unknown
external callees as proved.

State 4 tests input byte `0x1FFC6F24` for value 2 and reaches the common
teardown call at `0x2093E`. Teardown writes **0** to cache `0x1FFC6F25` at
`0x207E4`; state 2 is a separate transition. State 3 has an external readiness
guard path through `0x20892` to a 100 ms return at `0x2089A`, without first
testing detach input. Its route to teardown is conditional `3 -> 4 -> 0`.
The report's counterexample is a symbolic guard result, not a reproduced
watch failure: the relationship between external readiness and detach input
is unproved.

Both proposed hook entries hold USB mutex `0x1FFC6EEC`. The unscheduled tail
at `0x20A8A` branches to the unlock routine after restoring the worker stack
and registers. A future trampoline must replay that unlock before submitting
anything. The current inventory does not establish calling context, recursion
depth, or a safe queue integration. The queue primitive at `0x67D8` has a
back-of-queue, zero-timeout candidate contract; it is not an approved hook.

Observer publication at `0x1EF1C` dispatches through `0x7720` from RAM list
`0x1FFC8AA0`. The dispatcher uses node offsets 0/8/12 for next/callback/context
and synchronously invokes dynamic callbacks while holding the observer-list
mutex. Registration closure, observer reentry, and modal outcomes are
unproved. The USB worker does not reschedule after return `-1`; that worker
therefore supplies no bounded post-detach retry. Examined UI scheduling APIs
also do not establish a free object and a recurring safe callback.

## Failed gates

| Gate | Missing evidence |
| --- | --- |
| `five_key_halfwords` | Complete transitive stock access/alias closure for every pad. |
| `tri_state_view_classifier` | Completed bounded HOME/NON_HOME/INVALID proof for malformed, cyclic, and changing views. |
| `observed_update_prompt_non_home` | A pinned observed modal callback or first-visible view fixture. Eligibility and text resources are insufficient. |
| `usb_3_and_4_detach_convergence` | Complete cache alias coverage, state 3 external-guard convergence, and once-per-epoch observer/reentry proof. |
| `post_unlock_hook_site` | Safe callback context, mutex recursion-depth proof, and queue submission after unlock. |
| `bounded_retry_context` | A pinned post-unlock callback with a bounded cadence and lifecycle. |
| `modal_outcome_or_native_refresh` | Guaranteed home after observers or an exact safe native modal-refresh path. |
| `atomic_storage_map` | Exclusive workspace proof and concurrent halfword CAS transition proof. |
| `projected_flash_fit` | Measured replacement bounds and destinations for every group, trampoline, table, literal, and alignment gap. |

`phase_timing` passes only for the pinned scheduling semantics described above.
The ten-gate list is fixed and complete; missing values and truthy strings
cannot become proof. The positive `go=true` acceptance condition in the plan
remains unmet. Regression tests assert the honest blocked result, rather than
leaving intentionally failing assertions in the suite.

## Exact storage and flash contracts

The proposed halfwords are `0x1FFDBBFE`, `0x1FFDBC36`, `0x1FFDBC6E`,
`0x1FFDBCA6`, and `0x1FFDBCDE`. All are aligned and distinct. Their bit capacity
is ten bytes; that arithmetic is not a storage-ownership proof.

Each word is `local | ((local ^ 15) << 4) | (mode << 8) | ((mode ^ 15) << 12)`.
Local values are IDLE=0, FLY_HELD=1, FLY_PULSE=2, and GARMIN_HELD=3. LIGHT mode
values are NORMAL=0, CHORD_HOLD=1, SYSTEM_PENDING=2, SYSTEM_HOME=3, and
SYSTEM_EXCURSION=4. START values are DETACH_NONE=0, PENDING=1, RETRY1=2,
RETRY2=3, RETRY3=4, QUEUED=5, and EXHAUSTED=6. BACK, DOWN, and UP require
mode zero. Writers require aligned halfword compare/exchange and preservation
of the other subsystem's byte. Invalid words select Garmin ownership.

Primary payload capacity is exactly 1023 bytes from `0x1F6000`; secondary is
2048 bytes from `0x1FA400`. Repair byte `0x1F63FF` is excluded. The projection
validator rejects missing groups, unknown bounds, duplicate groups, overlaps,
and repair-byte use. It imposes no spare-byte minimum. Actual replacement
group bounds remain `null`: the blocked hook/retry design has not been compiled
into a throwaway projection. Existing 996/2044-byte usage is not reused as a
replacement measurement. No target scaffold was made to satisfy this gate.

## Reproduction

Use Python 3 with Capstone (audited here with 5.0.7) and the existing Ghidra
12.1.3 offline project `FR245_1370_CODE`, program `stream_01_fw_all_bin.bin`.
The project must stay read-only. Ghidra rejects dot-prefixed path components;
resolve the ignored project junction before invoking headless analysis.

```powershell
$projectPath = python -B -c "from pathlib import Path; print(Path('artifacts/firmware/ghidra-code').resolve())"
& ./tools/ghidra/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat $projectPath FR245_1370_CODE -process stream_01_fw_all_bin.bin -readOnly -noanalysis -scriptPath tools/garmin-firmware/ghidra_scripts -postScript UsbDetachReport.java artifacts/firmware/analysis/fr245-1370-usb-detach-ghidra.json artifacts/firmware/analysis/fr245-1370-usb-detach-decompilation.txt *> artifacts/firmware/analysis/fr245-1370-usb-detach-ghidra.log
Get-FileHash artifacts/firmware/analysis/fr245-1370-usb-detach-ghidra.log -Algorithm SHA256 | Format-List | Out-File artifacts/firmware/analysis/fr245-1370-usb-detach-ghidra.log.sha256 -Encoding utf8

python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_key_workspace_audit.py
python -B -m unittest -v tools/garmin-firmware/tests/test_fr245_usb_detach.py
python -B -m unittest -v tools/garmin-firmware/tests/test_atlas_shell_feasibility.py
python -B tools/garmin-firmware/atlas_shell_feasibility.py --root . --write-private-report artifacts/firmware/analysis/fr245-1370-atlas-shell-feasibility.json
```

The three test files include private-evidence integration tests; those require
the exact offline image and the Ghidra inventory above. Missing-evidence tests
use temporary directories. The final command writes all three private reports,
prints `go=false` with the nine gates above, and exits **1** to stop automation.
All three analyzer CLIs use exit 1 for an unproved result.

`UsbDetachReport.java` emits function ranges and hashes, code-block destinations,
known RAM references, aligned literals, and seeded high-P-code memory operations.
Its console pins the inventory JSON hash. The Python consumer checks that
receipt, the original image identity, and **every** extracted function extent
against the pinned image. A complete computed-alias proof is never inferred
from a successful Ghidra run or from the inventory's booleans. Decompilation,
console output, inventory, reports, and their checksum receipts remain private.
