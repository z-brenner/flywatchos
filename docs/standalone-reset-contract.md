# FR245 standalone reset contract

This report records the first evidence gate for replacing the GarminOS
application with FlyOS while retaining the resident loader below `0x00003000`.
It is an offline reverse-engineering result, not an installable firmware image.

The adjudicated result is **`go=false`**. It blocks target MMIO implementation,
standalone packaging, staging, and any watch write. A future `go=true` result
would authorize only a separately reviewed, offline board-support-package plan;
it would not authorize packaging or a live write.

## Pinned source and reset root

- Official application source SHA-256:
  `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`
- Reset vector: `0x000031f1`
- Reset handler: `0x000031f0`
- Stage-two pointer: `0x00019341`
- Stage-two entry: `0x00019340`
- Bounded inventory: 86 functions, maximum direct-call depth 3

The reset vector, handler bytes, Thumb state, and stage-two pointer are
statically confirmed against the pinned image. A separate hash-bound proof now
resolves all nine indirect sites in the bounded closure: the reset transfer,
four guarded table branches, and four callback sites. No hardware meaning is
inferred from those control transfers.

## Gate results

These values are copied from the committed sanitized receipt.

| Gate | Result | Meaning |
| --- | --- | --- |
| `analysis_complete` | `true` | The bounded analysis completed without cancellation or unresolved seeded functions. |
| `control_flow_closed` | `true` | All nine indirect sites are tied to exact source windows and resolved targets. |
| `memory_ranges_closed` | `false` | Computed memory operations still have unresolved target ranges. |
| `mmio_addresses_closed` | `false` | Computed accesses prevent a complete MMIO-address inventory. |
| `mmio_values_closed` | `false` | Required write values and their meanings are not proved. |
| `mmio_widths_closed` | `false` | Required access widths are not proved for all MMIO evidence. |
| `pinned_source` | `true` | The analysis input matches the exact official application SHA-256. |
| `polls_bounded` | `false` | Backward branches have not been proved bounded or classified as non-poll loops. |
| `reset_root_exact` | `true` | The reset handler and stage-two entry match the pinned root. |

The private inventory conservatively records 1,065 computed memory operations,
629 unresolved MMIO-width facts, 629 unresolved MMIO-value facts, 284
potentially unbounded backward branches, and 1,065 unknown memory ranges. These
are evidence backlogs, not claims that every row is a hardware transaction or a
poll loop.

## Evidence classification

### Confirmed

- The exact source identity and reset-root addresses listed above.
- A fresh scratch-project analysis completed with zero unresolved seeds and
  zero unresolved functions inside its direct-call depth bound.
- All nine indirect sites are closed by the committed control-flow receipt.
  The four switch tables have explicit guards and bounded target sets; every
  reachable callback argument is either null or the Thumb pointer
  `0x0001a299` targeting `0x0001a298`.
- The sanitized receipt contains no firmware bytes, instruction text, private
  filesystem paths, or decompiler output.

### Strongly inferred

- `0x00019340` is the official application's early startup entry reached by the
  reset trampoline.
- The bounded closure contains substantial clock, memory, and peripheral-facing
  work, but the current evidence does not safely separate essential standalone
  initialization from GarminOS runtime initialization.

### Unknown

- The minimal clock, watchdog, power, panel, button, storage, and USB sequences
  required by standalone FlyOS.
- The exact ordering, preconditions, widths, and values for all required MMIO
  transactions.
- Bounds and exit conditions for every startup polling loop.
- A proved complete SRAM map and a demonstrated nonboot recovery path.

### Refuted

- The current K28 RAM-framebuffer skeleton is not an installable standalone OS.
- Closing indirect control flow does not prove hardware transaction semantics.
- Removing the GarminOS application now would require guessing boot-critical
  behavior and is therefore outside the project's safety rules.

## Evidence integrity

The private evidence remains local. Its SHA-256 receipts are:

- Ghidra inventory: `afd7c6ecb339e52d4af37af9d6c46825d4cd4d8a6c0718a7662022940c27b0e9`
- Control-flow receipt file: `26b254184619ca42341857575b7d0ce5f3bca4a7e047d0417c3d75c7a97e21e8`
- Control-flow canonical content: `6f68ae0c2deb2799353e53202a5bb70d194d52808535705edfa0c66dd9b537d3`
- Private analysis text: `fb7623b5cd91cd21fb9a617a164d5b3a8a0cfc8e33b78efe6a265dc86a44f0e3`
- Headless analysis log: `0d5f73c6f6c6da99a520c2064b07a28eccda65ae5b632698f2ae0c832a5f1cb3`
- Script log: `a6eb00b5559b8a50e2e53e1fd957891e3ae55775ce8516327f3d4b36bed39d22`
- Sanitized committed receipt: `cd344a9c3e9fdc66d25be76ed1db9db270c8db8ae6770cec3847bc52556d294c`

The next safe step is separate offline evidence work on the five remaining
false hardware-semantics gates. No result in this report changes the
watch-safety or manual-flash boundary.
