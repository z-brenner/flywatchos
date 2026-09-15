# SDD ledger — plan: docs/superpowers/plans/2026-09-14-flyos-neural-specimen-n64.md

Preflight: repository has no Git HEAD; file hashes and scoped review packages replace commit ranges.

| Task(s) | Interface/file overlap | Finding |
| --- | --- | --- |
| 1 -> 2 | Brain64 types/functions consumed by renderer | Clean; renderer waits for Task 1 interface. |
| 2 -> 4 | Renderer and preview consumed by target | Clean; target waits for renderer. |
| 3 -> 4 | Proven runtime-state allowlist consumed by target | Clean; target must fail closed for unavailable signals. |
| 4 -> 5 | Exact target binaries and allocation manifest consumed by packager | Clean; packaging waits for target review. |
| 1 | Tests match fixed-point model API | Clean. |
| 2 | Tests match safe-area and 64-cell renderer | Clean. |
| 3 | Report schema requires honest unavailable states | Clean. |
| 4 | Emulator constraints match target wrapper | Clean. |
| 5 | Quarantine and live-write boundary match spec | Clean. |

Ruling: Work proceeds in the current non-HEAD repository because no worktree can be created; every task gets targeted hashes and independent review — if wrong, rollback depends on file backups rather than Git history.
Task 1: fix round 1/5 (5 addressed, 0 open; file hashes in task-1-report.md)
Task 1: complete (review clean; repository has no commits)
Task 2: fix round 1/6 (6 addressed, 0 open; actual C renderer now owns golden previews).
Task 2: fix round 2/4 (4 addressed, 0 open; no-op gate, exact labels, meaningful ownership, quiet state).
Task 2: complete (SPEC PASS / QUALITY PASS; stale preview-count documentation corrected after review).
Task 3: fix round 1/3 important (strict canonical allowlist, Thumb callables, stdout-only CLI; all addressed).
Task 3: complete (SPEC PASS / QUALITY PASS; 15/15 focused tests and prior 111/111 full Garmin baseline).
Task 3 color extension: complete (SPEC PASS / QUALITY PASS; exact RGB222 mapping and six roles proved, 20/20 focused tests).
Task 4: fix round 1 (view-walk memory/control-flow race removed; B100, MOTION, saturation, evidence, reproducibility, canonical I/O, oracle isolation addressed).
Task 4: housekeeping fix (legacy shared oracle outputs removed; manifest cleanliness enforced).
Task 4: complete (three independent reviews clean; 19/19 focused, 137/137 firmware-analysis, 7/7 CTest; 3,050/3,071 bytes; 384/384 stack).
Task 5: fix round 1 (single-read immutable snapshots, traversal/reparse confinement, write/cleanup/rollback fault injection, staging alias denial).
Task 5: fix round 2 (Windows junction and exact-root tests; privileged symlink explicit skip).
Task 5: recovery documentation completed with exact restore/abort procedure and YELLOW GarminOS-resident boundary.
Task 5: complete (package, staging, immutable-input, and recovery reviews all SPEC PASS / QUALITY PASS; candidate/restore hashes frozen).
