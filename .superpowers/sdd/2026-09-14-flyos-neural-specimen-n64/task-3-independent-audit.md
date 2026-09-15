# Task 3 independent runtime-state evidence audit

## Scope and rule

This is an offline, read-only audit of the pinned Forerunner 245 non-Music
13.70 `fw_all` image. No device, package, target binary, quarantine artifact,
or staging script was accessed or changed.

The image audited is
`artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin`,
SHA-256
`b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`.
A signal is **PROVED AVAILABLE** only when the pinned image establishes its
meaning and a read path that neither calls a callback nor performs peripheral
I/O. Anything weaker is **UNAVAILABLE** and must contribute zero/display `--`.

## Result

| Signal | Verdict | Safe source | Validity semantics | Principal limitation |
|---|---|---|---|---|
| Watch face/home active | **PROVED AVAILABLE** | Pure predicate pair `0x0005306c` then `0x000530cc`, using watch-face callback identity `0x0005adf5` | First result must be nonzero; second result must equal one | Walks a dynamic Garmin view list; pin to 13.70 and fail closed on any unexpected pointer/control flow |
| Update pending/install modal | **UNAVAILABLE** | None | None | Update eligibility code is not an update-pending flag; `Install Now`/`Install Later` are resource strings only |
| Safe critical-screen pass-through | **PROVED AVAILABLE** | Render only when the watch-face predicate is affirmatively true; independent BACK-held override uses active-low GPIOD PDIR bit 1 at `0x400ff0d0` | False/invalid home predicate or held BACK means leave the framebuffer byte-identical | Must be proved in Task 4 emulation at the actual hook; it does not identify which non-home screen is visible |
| USB mass-storage mode | **PROVED AVAILABLE** | Atomic byte read at `0x1ffc6f25` | Values 3 or 4 mean mass-storage mode; every other value is false/invalid for this narrow signal | Does not prove generic cable insertion, USB charging, or every USB mode |
| USB attached (generic) | **UNAVAILABLE** | None | None | Nearby USB-manager bytes have not been semantically tied to cable-present state |
| Charging | **UNAVAILABLE** | None | None | The observed charger-state accessor dispatches through a callback; PMIC/fuel-gauge alternatives perform bus I/O |
| Battery percentage | **PROVED AVAILABLE** | Direct IEEE-754 binary32 cache at `0x1ffcccd8` | `-1.0f` is the firmware sentinel; additionally accept only finite values in `[0,100]` | Read the cache directly; do not call the fallback-capable getters |
| Heart-rate BPM | **UNAVAILABLE** | None | None | A boolean "broadcasting HR" check and HR-related resource text do not expose BPM, freshness, or off-wrist validity |
| Motion magnitude/state | **UNAVAILABLE** | None | None | Apollo2 transport and activity bookkeeping are not a pure, normalized motion snapshot |
| Raw framebuffer byte-to-color mapping | **UNAVAILABLE** | None | None | Converter bit packing is exact, but bit-to-hue/palette semantics are not |

## Watch-face predicate

The previous tentative interpretation of external target `0x04724040` was
incorrect. In `FUN_0006beec`, the call at `0x0006bfde` is followed by the log
selected through literal `0x0006c0e0`, whose text is
`software update condition not met, user is asleep`. It is not the watch-face
test.

The actual watch-face test is visible immediately afterward:

```text
0006bfec  ldr  r0, [pc, #0xb8]  ; 0x0005adf5
0006bfee  bl   0x0005306c
0006bff2  bl   0x000530cc
0006bff6  mov  r4, r0
0006bff8  cmp  r0, #0
0006bffa  beq  0x0006c09e       ; log "not on watch face"
```

The literal at `0x0006c0a8` is `0x0005adf5`. The log pointer loaded at
`0x0006c09e` is stored at `0x0006c0e4` and resolves to `0x0006be90`,
`software update condition not met, not on watch face`.

`0x0005306c` reads the list root at `0x20003e84`, follows each node's `+4`
next pointer, and returns the node whose `+8` callback equals its input.
`0x000530cc` reads the same root, skips nodes whose `+0x50` flags have bit 1
set, and returns one exactly when the first unskipped node equals its input.
Both functions contain only loads, comparisons, branches, and a return. They
make no call, store, lock, or peripheral access.

The fail-closed predicate is therefore:

```c
node = ((void *(*)(void *))0x0005306d)((void *)0x0005adf5);
home = node != NULL && ((int (*)(void *))0x000530cd)(node) == 1;
```

The odd addresses above include the Thumb bit. Task 4 must preserve registers
and stack alignment, test empty/missing/multiple/list-flag cases, and reject
execution outside the exact two function bodies. The view list is dynamic, so
the emulator must also audit every synthetic node read. A bounded inline walk
would reduce corrupted-list risk, but it would need separate equivalence tests
against these official routines.

An affirmative result is suitable to gate FlyOS rendering. A false result
leaves all non-watch-face pages untouched, which includes menus, alerts, the
charging page, and the stock update prompt without needing to recognize each
screen separately. The independent active-low BACK read at GPIOD PDIR bit 1
provides an additional user-controlled pass-through path.

## Update state

`FUN_0006beec` at `0x0006beec` answers whether all conditions permit a
software update. Its checks include battery reserve, mass-storage mode,
auto-update setting, HR broadcast, timers/activity, sleep, alarms, and the
watch-face predicate. A true return does not prove that an update exists or
that an install modal is active.

`FUN_0006c51c` calls message/database routine `0x0009c938` with ID `0x04e3`,
but the available evidence does not establish a stable pending-update RAM bit.
The external-resource strings `Install Now` at `0x04842a64` and `Install Later`
at `0x04842a70` have no resolving direct code xref in the current reports.
Consequently a custom update prompt is unavailable. The required behavior is
to pass through Garmin's stock prompt; START remains Garmin's own confirmation
key.

## USB state

`0x00020578` locks semaphore `0x1ffc6eec`, reads the cached enum byte at
`0x1ffc6f25`, then maps state 2 to zero, states 3/4 to one, and other values to
three. `0x000205b0` reduces that result to true only for the 3/4 case. The
update-condition call at `0x0006bf64` branches to the message selected by
`0x0006c0b4`, which resolves to
`software update condition not met, in mass storage mode`.

This pins states 3 and 4 to mass-storage mode. A direct byte read is atomic and
avoids the semaphore calls. It may drive a narrow `USB MASS STORAGE` status,
but it must not be renamed `USB attached` or `charging`. Nearby bytes
`0x1ffc6f24` and `0x1ffc6f26` are read by USB-manager functions, but their
precise cable/role semantics are not established.

## Battery and charging

The direct battery cache is supported by two identical front ends,
`0x0000bf68` and `0x0000bfb8`. Their instructions load base `0x1ffccc10`,
read its binary32 field at `+0xc8` (`0x1ffcccd8`), and return immediately when
the value differs from `-1.0f`. If the cache is `-1.0f`, both tail into
`0x0000bccc`, which may call the function pointer at
`*(0x1ffccc10 + 4)`. The getters therefore are not themselves safe to call,
but the cache address is safe to read directly.

The semantic link to battery percentage is strong and specific:
`0x001cc8e4` calls `0x0000bf68` and compares the returned float against
`10.0f`; failure is the path reported by `FUN_0006beec` as
`software update condition not met, not enough juice`. The fallback also
clamps its result to the `100.0f` literal at `0x0000bd18`. A target adapter
must accept only a finite `[0,100]` value and treat the sentinel or any invalid
encoding as unavailable.

Charging does not meet the same bar. Battery telemetry aggregator
`0x0000cab0` obtains its charger-state argument through `0x000115c8`.
`0x000115c8` tail-dispatches through the function pointer at
`*(0x1ffdbfd8 + 0x0c)`. Its implementation and side effects are not pinned.
The alternatives in this cluster are also unsafe: `0x0000c3a0` performs a bus
transaction and `0x000107d8` calls bus 3/address `0x28`. The `Charging`
resource string at `0x04844e64` does not establish a cache. Charging must
remain invalid/`--`; the stock charging screen will remain visible through the
non-home pass-through.

## Heart rate and motion

The update checker has a boolean HR-broadcast condition through veneer
`0x001f1b68` to external target `0x0475fb0c`, followed by the message
`software update condition not met, device is broadcasting HR`. That is not a
BPM value, and the current Ghidra report does not recover the external target
as a trustworthy standalone pure function. The string
`heartRateBeatsPerMin` at `0x04812d7c` is resource/schema evidence only; it has
no direct address/getter/validity proof. No cache with freshness and off-wrist
semantics is established.

For motion, the recovered `0x00015704` cluster initializes the SPI transport
to the Apollo2 sensor hub. The strings around external address `0x04717588`
name a motion-activity list semaphore, but the current evidence does not bind
a stable field to normalized motion, freshness, or validity. Neither direct
sensor-hub transactions nor list/lock-dependent activity code is allowed in
this revision. HR and motion must contribute zero and display `--`.

## Framebuffer color

The logical framebuffer is one byte per pixel at `0x1ffde6e8`. Converter
`0x0000e8fc` transforms each adjacent source pair `(a,b)` as:

```text
primary   = ((a & 0xea) >> 1) | (b & 0xea)
secondary =  (a & 0x15)       | ((b & 0x15) << 1)
```

The complementary masks prove that all eight logical bits reach the transfer
layout. Existing firmware uses values including `0x00`, `0x2a`, and `0xff`.
No current artifact ties the six effective display bits to RGB components,
named palette entries, or measured panel colors. Therefore no raw value may
be assigned to scaffold/excitatory/inhibitory/saturated roles. The live target
must retain the previously exercised two-value monochrome treatment until an
offline resource correlation or a separately approved, non-destructive color
calibration proves the mapping.

## Evidence provenance

| Artifact | SHA-256 |
|---|---|
| `n64-runtime-state-seed-decompile.txt` | `769d5efad5ded36d88d4d491a0e526f301ef13c5655cb20b5ad411caa77782fb` |
| `n64-battery-getters-decompile.txt` | `87bfe58162719494dd8eb42fd8a18f3c8e64f8aae4f59298f8aea5cc9573fa50` |
| `n64-watchface-string-xrefs.txt` | `73e6aeb42160e09e4551618bb0b6ea6e8590ddd86a16e09a03e4a22d6ef1c526` |
| `n64-watchface-update-decompile.txt` | `2c0c5368b17f487f0ed3ddc7038c659aec0599e9590fba513f15216616d6e8e6` |
| `n64-external-watchface-decompile.txt` | `57dcf7f3cfa13f555fb9f3b770d91cb3e729454c28dc5718f202c6196f5c1861` |
| `display-inapp-render-1370.md` | `c9e1de3971e8d7301067b2c5a1cc505bb666867e9ca1d898ee6c3986870f3daf` |
| `docs/driver-leads.md` | `d324c056ef023b4dd746c4284eac8e5a975729bab20e372c2cc6cc6bc8947d0c` |
| `docs/display-flexio.md` | `f6642a2cf3b49bf88549aa3016cd4f24d7846c6185529dc5b57b219e332b58ce` |

## Task 4 gate

The target may enable only the home predicate, BACK pass-through, narrow
mass-storage indication, and battery cache from this audit. It must leave
charging, generic USB attach, update pending, HR, motion, and color roles
invalid. Before package construction, emulation must show that a false or
invalid home result performs no framebuffer write, the predicate's read/control
flow stays within the modeled Garmin list and exact function bodies, and BACK
suppression always wins.
