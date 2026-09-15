# Task 3 independent review

Date: 2026-09-14. Scope: the Task 3 runtime-state analyzer, focused tests,
generated JSON, documentation, implementation report, color scout, independent
static audit, and the preserved Forerunner 245 non-Music 13.70 and 3.10 decoded
images. This revision includes the scoped review of the RGB222 color extension.

## Result

**SPEC PASS**  
**QUALITY PASS**

The color extension is supported by exact pinned bytes, inverse conversion
functions, callback-table slots, setup-copy evidence, direct caller argument
order, exhaustive offline execution, and independent 3.10 corroboration. The
strict canonical validator and the four-entry runtime-signal allowlist remain
intact. No Critical, Important, or Minor finding remains.

No implementation, firmware, device, target, package, quarantine artifact, or
staging path was modified during this review. Only this review record was
updated.

## Reviewed evidence

| File | SHA-256 |
| --- | --- |
| `tools/garmin-firmware/fr245_runtime_state.py` | `fcc0512696aeaa4fc9e8cfe7c3bd24f027ce2ee9639c1601ad95cc3ba047c1ab` |
| `tools/garmin-firmware/tests/test_fr245_runtime_state.py` | `fe35211f2e5b09966a0d6ded7b9f46549a788c722d4e132338c2dd4b71aff3aa` |
| `docs/runtime-state.md` | `79dbee4ccd78eff26a97e052099f689e5b816e13fcb1ceb11fc4262f8f5a8147` |
| `artifacts/firmware/analysis/fr245-1370-runtime-state.json` | `53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d` |
| `task-3-report.md` | `52eb974ac06893e538f33bd81277c6d8fca1216b27bb3024d086527734ad079c` |
| `task-3-color-scout.md` | `3c8f643f08d92de5682803a1e883ad1048bef36d97d471ad8eea9676fc6daad2` |
| `task-3-independent-audit.md` | `ff2fcd25fa291e208c9741f8aac6f5bd204f1ce7e15b7dd5621be0157ace023b` |
| Pinned decoded 13.70 internal image | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| Pinned decoded 13.70 external-XIP image | `2fe66af98be9894949b0aece203378421ac3f263c208a8e8b402524be2e8209f` |
| Pinned decoded 3.10 external-XIP image | `17406fec718b2e477e2b35fbc3f902ed7b2068294aa6141e7fed2bcdda7ec66b` |

The JSON's `source_audit.sha256` exactly matches the current color-scout file.
The documentation, report, and scout decode as strict UTF-8 without a
replacement character.

## Verification performed

Focused suite:

```text
python -B -m unittest tools/garmin-firmware/tests/test_fr245_runtime_state.py -v
Ran 20 tests in 1.802s
OK
```

The suite covers all 64 RGB/native round trips, exact role values, pinned
function/table/setup addresses and hashes, odd Thumb callable addresses,
canonical mutations, unchanged runtime signals, byte-for-byte stdout JSON,
and the earlier no-write CLI attacks.

An independent Capstone pass decoded the exact preserved Thumb bytes. An
independent Unicorn pass then executed both conversion functions for every
native value and every canonical RGB cube point. Results were:

```text
13.70 errors 0; native set exactly 0x00..0x3f
3.10  errors 0; native set exactly 0x00..0x3f
```

This execution used the bytes from the preserved images directly rather than
calling the analyzer's Python conversion helpers.

Independent canonical probes also rejected added/deleted/swapped roles,
formula substitution, an even callable address, callback-slot and setup-source
changes, altered round-trip counts, a changed scout hash, and a changed color
evidence assertion. Independent serialization remains byte-identical to the
checked-in JSON.

## Pinned 13.70 color evidence

Direct recomputation from the exact internal image produced:

| Artifact | Image range | Length | Recomputed SHA-256 |
| --- | --- | ---: | --- |
| Native to RGB | `0x00063020..0x00063051` | 50 | `96a9d40ac0e8277d634c16c4cc43bece9bb2f98295f8fb34d7e439a2e8cd1651` |
| RGB to native plus literal | `0x00063054..0x0006309f` | 76 | `a9fe98122781c77f9b06b35eb05f1fc7d3547f1035f3b00af36eec8b61ecba05` |
| Static callback table | `0x00064554..0x0006459b` | 72 | `4bdaeb1c029ba0ef4c6d90a1b4d77040475fa48334dd75471a8bf091cc8a1ca7` |
| Setup body | `0x00063f1c..0x00063f45` | 42 | `9d87b588e18b3106af96bf63e67333f243e60c79593dab528451d96ac3334985` |

The setup literal at `0x00063f48` is `0x00064554`. The setup body loads that
source, sets the length to `0x48`, copies it to its stack, and submits the stack
table to the registration veneer.

The callback table contains:

- offset `+0x0c`: `0x00063055`, the odd Thumb pointer for RGB to native;
- offset `+0x2c`: `0x00063021`, the odd Thumb pointer for native to RGB.

The even addresses `0x00063054` and `0x00063020` are image/disassembly
locations only. The analyzer records both forms, declares Thumb explicitly,
and the canonical validator rejects replacing either callable pointer with an
even address. Setup follows the same contract: image `0x00063f1c`, callable
Thumb pointer `0x00063f1d`.

External-XIP call-site decoding confirms the signatures and channel order.
At `0x047ccf24`, the caller loads `[0x34038f38 + 0x0c]`, extracts RGB888 as
red into `r0`, green into `r1`, and blue into `r2`, then uses `blx`. At
`0x047cb3e2`, the reverse caller loads `[0x34038f38 + 0x2c]` and supplies three
ordered output-byte pointers. Both literal pools resolve to `0x34038f38`.

## Encoding and exhaustive round trips

The decoded native-to-RGB function implements:

```text
red   = ((native >> 4) & 3) * 85
green = ((native >> 2) & 3) * 85
blue  = ( native       & 3) * 85
```

For the canonical components `00`, `55`, `AA`, and `FF`, the inverse function
implements:

```text
native=(R_level<<4)|(G_level<<2)|B_level
```

All 64 native values `0x00..0x3f` map to 64 unique points in
`{0,85,170,255}^3` and return to the original byte. All 64 cube points produce
the exact formula value and return to the original RGB triple. Native bits 7:6
are outside the canonical palette and are not used by the target mapping.

The six canonical N64 roles are internally consistent with that formula:

| Role | Native byte | RGB |
| --- | ---: | ---: |
| Background | `0x00` | `#000000` |
| Scaffold | `0x2a` | `#AAAAAA` |
| Text | `0x3f` | `#FFFFFF` |
| Excitatory | `0x0c` | `#00FF00` |
| Inhibitory | `0x33` | `#FF00FF` |
| Saturated | `0x38` | `#FFAA00` |

The firmware evidence proves each RGB/native-byte pair. Assigning those proved
colors to semantic UI roles is the design policy recorded in the canonical
report.

## Cross-version corroboration

The preserved 3.10 external-XIP image contains equivalent conversion routines:

| Direction | Image range | Length | Recomputed SHA-256 |
| --- | --- | ---: | --- |
| Native to RGB | `0x046c29e0..0x046c2a0f` | 48 | `1decf718b6ba92484bffdae5e0c5e69fede52c2bd72751d673ba2325e3a6d13d` |
| RGB to native | `0x046c2a10..0x046c2a5b` | 76 | `f13fb421209d52636a8498b0131260e7a7693229024ac0ac0619790b2f3d0eb6` |

Capstone shows the same channel extraction, multiplication by 85, RGB-level
quantization, and bit placement. Independent Unicorn execution of those 3.10
bytes also passed every one of the 64 forward and reverse cases. This is useful
corroboration; the emitted target values remain bound to the pinned 13.70
image and do not carry 3.10 addresses into integration.

## Runtime allowlist and canonical boundary

The color extension does not add a runtime read. Exactly four runtime signals
remain available:

- `watch_face_active`;
- `back_button_pass_through`;
- `usb_mass_storage`; and
- `battery_percent`.

Generic `usb_attached`, `charging`, `update_pending`, `heart_rate_bpm`,
`motion`, and `raw_framebuffer_color_mapping` remain unavailable with the same
fail-closed fallback. `target_palette` is a separate static constant mapping;
its availability does not promote the runtime color signal.

`validate_report` still regenerates a report from the exact pinned 13.70 image
and recursively compares exact types, keys, list order/length, and scalar
values. The added palette roles, formula, channel levels, image/callable
addresses, function lengths, table slots, setup record, round-trip counts,
scout hash, and color evidence assertions are all within that canonical
boundary. The previous runtime-state mutation and stdout-only CLI protections
continue to pass.

## Registration caveat and residual risk

The final destination write below the `0x001f14a0` registration veneer remains
unresolved. The evidence linking the static table to the runtime object is
therefore strong rather than independently complete: exact function signatures
occupy the exact consumer offsets, setup copies the exact 72-byte table, and a
complete static reference scan found the consumer reads but no competing slot
writes.

This caveat does not change the encoding result. The preserved conversion
functions are exact inverses for the complete 64-color domain, and the
external-XIP callers independently establish red/green/blue argument order.
Task 4 consumes the resulting static bytes and does not need to call the
registration veneer or either conversion routine. The residual risk is that
the final runtime-table installation path has not been separately traced; it
should remain documented and must not be generalized into permission for any
new runtime call or read.

## Task 4 gate

Task 4 may consume the six canonical static palette bytes and only the four
canonical available runtime signals. It must still emulate and bound the
watch-face predicate, enforce the read allowlist, retain fail-closed optional
inputs and BACK pass-through, and satisfy the allocation and 384-byte stack
gates. This review grants no package, staging, installation, or live-watch
permission.
