# N64 target framebuffer-color scout

## Scope

This was an offline, read-only investigation of the Forerunner 245 non-Music
3.10 and 13.70 public firmware artifacts. No watch volume, USB device,
package candidate, staging directory, or implementation file was accessed or
changed. The only repository write is this report. Temporary decompiler and
verification output was kept under `%TEMP%`.

The acceptance rule was deliberately strict: a named color is available only
if public technical documentation or a preserved binary/resource artifact
directly correlates an RGB color with an exact logical framebuffer byte. Bit
masks, a likely panel pinout, visual similarity, and endpoint assumptions are
not sufficient.

## Verdict

**Exact logical framebuffer colors: RESOLVED by the follow-up at the end of
this report.**

The initial pass below is retained as an audit trail. Its `UNAVAILABLE`
entries describe the state before the internal callback implementations and
their static dispatch table were found. The later section supersedes that
intermediate verdict with exact firmware-backed RGB/native-byte pairs.

The converter proves how every logical byte is transported, and Garmin's
Connect IQ graphics code proves that an RGB888-to-native-byte callback exists.
The implementation installed in that callback table has not been resolved.
No public teardown or firmware artifact identifies the panel and its six data
lanes on the FR245 PCB. Consequently none of the requested semantic roles can
be assigned an exact byte without guessing.

| Requested role | Exact logical byte | Status | Reason |
|---|---:|---|---|
| Background | unavailable | **UNAVAILABLE** | No artifact identifies black, white, or either endpoint in logical-byte space |
| Text/scaffold | unavailable | **UNAVAILABLE** | Contrast is observable, but its hue and polarity are not proved |
| Excitatory | unavailable | **UNAVAILABLE** | No RGB-to-native correlation |
| Inhibitory | unavailable | **UNAVAILABLE** | No RGB-to-native correlation |
| Saturated/accent | unavailable | **UNAVAILABLE** | No RGB-to-native correlation |

Previously exercised values such as `0x00` and `0xff` may remain an **unnamed
contrast pair** in an already approved monochrome implementation. This report
does not rename either value black, white, or any hue. It provides no basis for
adding target color roles.

## Pinned artifacts

The hashes below were recomputed locally with `Get-FileHash -Algorithm SHA256`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `artifacts/firmware/originals/Forerunner245_1370_GUPDATE.GCD` | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |
| `artifacts/firmware/originals/Forerunner245_310.gcd` | 4,245,103 | `ffc802fd505cb62fe680dd50935654ef8177c8a0c74d20de3a6b32a4d185ff43` |
| `artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin` | 5,079,040 | `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6` |
| `artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_external_xip.bin` | 2,994,176 | `2fe66af98be9894949b0aece203378421ac3f263c208a8e8b402524be2e8209f` |
| `artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin` | 4,201,216 | `3225c50585503d331a9c0ee8faf342241207dd98825f4f0f9cf3fa23831c54ba` |
| `artifacts/firmware/analysis/Forerunner245_310/stream_01_external_xip.bin` | 2,116,352 | `17406fec718b2e477e2b35fbc3f902ed7b2068294aa6141e7fed2bcdda7ec66b` |

## What the display converter proves

The logical framebuffer is 240 by 240, one byte per pixel, at runtime address
`0x1ffde6e8` in the pinned 13.70 image. The homologous self-contained pixel
converters are:

| Version | Converter entry |
|---|---:|
| 3.10 | `0x000bf54c` |
| 13.70 | `0x0000e8fc` |

For adjacent logical pixels `(a,b)`, both versions generate the same two
packed bytes:

```text
primary   = ((a & 0xea) >> 1) | (b & 0xea)
secondary =  (a & 0x15)       | ((b & 0x15) << 1)
```

The masks are complementary. For values below 64 this transports the three
two-bit groups `(bit1,bit0)`, `(bit3,bit2)`, and `(bit5,bit4)` in two passes.
This is compatible with three two-bit color channels. It does **not** identify
which group is red, green, or blue, the significance/polarity of each bit, or
the mapping of logical bits 6 and 7.

The existing host model was rerun against the preserved Thumb code:

```powershell
python tools\garmin-firmware\display_row_model.py --verify --root . `
  --output $env:TEMP\n64-display-row-verify.json
Get-FileHash -Algorithm SHA256 `
  $env:TEMP\n64-display-row-verify.json
```

Result: 186 model-to-instruction comparisons passed, 63 cross-version
comparisons matched, and all 65,536 ordered input-byte pairs were checked.
Temporary report SHA-256:
`45dd56f563e81555120b04ef947d6798fd2ed508894abf05e890d758e2c7f122`.
The model itself states that it verifies packing and offsets, not panel color
semantics.

## Direct RGB conversion evidence in 13.70

The dual-map Ghidra project maps external XIP at `0x04600000`. Connect IQ
graphics routine `FUN_047cce70` parses 24-bit colors. At `0x047ccf24` and
`0x047ccf3e` it loads a callback from `[0x34038f38 + 0x0c]`, places
`(rgb >> 16) & 0xff`, `(rgb >> 8) & 0xff`, and `rgb & 0xff` in `r0`, `r1`,
and `r2`, then calls it. The returned low byte is stored as the native color.

The decisive instructions are:

```text
047ccf24  ldr   r3,[pc,#0x84]       ; literal -> 0x34038f38
047ccf26  ldr   r6,[r3,#0x0c]
047ccf2a  uxtb  r2,r0               ; blue
047ccf2c  ubfx  r1,r0,#8,#8         ; green
047ccf30  ubfx  r0,r0,#16,#8        ; red
047ccf34  blx   r6
...
047ccfac  .word 0x34038f38
```

The reverse conversion is equally explicit. `FUN_047cb398` loads the callback
at `[0x34038f38 + 0x2c]`, calls it with a native palette byte and three output
byte pointers, then computes squared Euclidean distance in the returned RGB
coordinates to select the nearest palette entry:

```text
047cb3e2  ldr   r0,[pc,#0x84]       ; literal -> 0x34038f38
047cb3e4  ldr   r6,[r0,#0x2c]
047cb3e8  ldrb  r0,[r5]             ; native byte
047cb3ea  blx   r6
...
047cb468  .word 0x34038f38
```

This is direct binary evidence that the firmware knows the exact mapping in a
platform callback. It is also direct evidence that the mapping is absent from
the recovered caller: the function pointers live in a RAM table. Static xrefs
found reads of that table and its `+0x0c` slot, but no statically resolved write
that names the installed callback. Calling the unresolved function on the
watch would violate this task's offline boundary.

The decompiler outputs used while checking this path were temporary files:

| Temporary output | Bytes | SHA-256 |
|---|---:|---|
| `n64-color-decompile.txt` | 3,014 | `5b266c1c1f9de9e9e678c04449a99c2b117af7c2684f50051beb4d3258ca5e47` |
| `n64-color-decompile2.txt` | 4,108 | `b8e513c9d1bb71518cbdddcd74422ce43371ee2be0a0e3e92fee8540a9e7f9dd` |
| `n64-color-decompile3.txt` | 8,653 | `295b2f31bdb39dc37b1828056d548fe6e643705d0f0f3e46257ff9be7d328a64` |

The instruction check can be reproduced without Ghidra by disassembling
external-XIP offsets `0x1cce70..0x1ccfa3` and
`0x1cb398..0x1cb46b` as little-endian Thumb with base `0x04600000`.

## Resource and cross-version checks

The 13.70 image contains the strings:

```text
external XIP +0x1cbe50  Color depth cannot exceed the system palette size
external XIP +0x1cbe84  Palette cannot exceed 256 colors
external XIP +0x1cbea8  Palette cannot exceed the system palette size
external XIP +0x1cd060  Bitmap source color cannot be found in the target palette
```

These strings surround the conversion code and support its palette semantics.
The same exact strings are absent from the smaller 3.10 external-XIP image, so
they do not supply an independent older mapping.

Both `fw_all` images contain a homologous table of Connect IQ color constants:

| Version | File offset |
|---|---:|
| 3.10 | `0x14c530` |
| 13.70 | `0x10e4e0` |

The table includes byte patterns corresponding to API RGB constants such as
`0xffffff`, `0xaaaaaa`, `0x555555`, `0x000000`, `0xff0000`, `0xaa0000`,
`0xff5500`, and `0xffaa00`. These are API/resource values, not a parallel
table of native framebuffer bytes. No adjacent field provides the needed
correlation.

The documented 64-color RGB cube was generated in Garmin's displayed order
with levels `ff, aa, 55, 00`. All six channel permutations were searched as
packed 24-bit bytes and as both common 32-bit layouts. No 8-, 16-, 32-, or
64-entry prefix was present in any of the four extracted images. The scan was:

```python
from itertools import permutations
levels = (0xff, 0xaa, 0x55, 0x00)
rgbs = [(r,g,b) for r in levels for g in levels for b in levels]
for order in permutations(range(3)):
    seq24 = b''.join(bytes(c[i] for i in order) for c in rgbs)
    seq32le = b''.join(bytes((*[c[i] for i in order], 0)) for c in rgbs)
    seq32be = b''.join(bytes((0, *[c[i] for i in order])) for c in rgbs)
    # Search the 8/16/32/64-entry prefixes of each sequence in each pinned image.
```

The negative scan rules out an obvious uncompressed canonical lookup table in
those layouts. It does not prove that no encoded, generated, or compressed
mapping exists.

## Public technical evidence and its limit

Garmin's official [compatible-device table](https://developer.garmin.com/connect-iq/compatible-devices/)
identifies the Forerunner 245 as a 240 by 240 round, 64-color MIP device.
Garmin's official [visual-design guidelines](https://developer.garmin.com/connect-iq/user-experience-guidelines/incorporating-the-visual-design-and-product-personalities/)
list the common MIP palette as all combinations of `00`, `55`, `aa`, and `ff`
in each RGB channel. Garmin's official [graphics documentation](https://developer.garmin.com/connect-iq/core-topics/graphics/)
says drawing colors are supplied as 24-bit `0xRRGGBB` and the device selects
the closest available system color. None of these pages specifies the native
framebuffer byte encoding.

Sharp's official [wearable LCD catalog](https://global.sharp/products/device/lineup/selection/lcd/mobile/index.html)
lists the `LS012B7DD06A` as a 1.19-inch, 240 by 240 circular, 64-color MIP
panel with a six-bit parallel interface. Its official specification,
`LCP-2619063A`, identifies six input signals `R[0]`, `R[1]`, `G[0]`, `G[1]`,
`B[0]`, and `B[1]` ([PDF](https://www.sharpsecd.com/static/media/Sharp-LCD-Specification-LS012B7DD06A-12-2-19.4b439705.pdf)).

That is a close mechanical and electrical match, but no public teardown or
preserved FR245 binary examined here identifies this panel part number or maps
the Kinetis/FlexIO shifter lanes to those six pins. Even a confirmed panel
would still require the board-lane order or the missing firmware callback.
Using the Sharp pin names to assign logical byte groups would therefore be an
inference from masks, which the acceptance rule forbids.

## Offline paths that could close the gap

1. **Resolve the RAM callback table initialization.** Continue cross-reference,
   relocation, constructor, and copy-chain analysis for `0x34038f38`. Success
   means recovering both the `+0x0c` RGB-to-native function and the `+0x2c`
   native-to-RGB function, then emulating all 64 documented RGB inputs against
   the pinned image. This is the strongest next path because the firmware
   already exposes both directions.
2. **Correlate a compiled Connect IQ color resource offline.** Build a test
   resource containing all 64 RGB colors for the FR245 target with the official
   SDK, unpack the resulting PRG/resource payload, and follow its palette
   through `FUN_047cc750`/`FUN_047cce70`. Accept the result only if each source
   RGB and resulting native byte are both visible in the offline artifact or
   resolved callback execution.
3. **Search encoded/generated tables.** Use the two callback algorithms as
   anchors, then search callers and constructors for arithmetic transforms,
   64-byte tables, nibble tables, or function-pointer tables rather than only
   raw RGB sequences. Verify any candidate in both conversion directions.
4. **Identify the actual panel and lane routing from public evidence.** A public
   schematic, PCB photograph with trace visibility, BOM, or service document
   could establish the panel and six-lane order. Mechanical similarity alone
   remains insufficient.
5. **Prepare preview palettes only.** Host renders may use aesthetic RGB values
   for design review if they are labeled `preview-only`. They must not be
   converted into a target byte map or included in a package until one of the
   correlations above succeeds.

All five options remain offline and require no device write. No live color
calibration, package construction, staging, or installation is recommended by
this report.

## Follow-up — callback table resolution (2026-09-14)

### Follow-up verdict

**RESOLVED.** Pinned 13.70 firmware contains both conversion functions and a
static 0x48-byte callback table that places them at the same `+0x0c` and
`+0x2c` offsets used by the Connect IQ runtime consumers. Offline execution of
the preserved Thumb instructions confirms all 64 native values round-trip to
the documented RGB cube and back.

The exact native format for the canonical channel levels is:

```text
native = (R_level << 4) | (G_level << 2) | B_level

RGB value:  00  55  AA  FF
level:       0   1   2   3
```

Bits 5:4 are red, bits 3:2 are green, and bits 1:0 are blue. Native bits 7:6
are not part of the canonical 64-color value. Canonical white is therefore
`0x3f`, not `0xff`.

For a restrained FlyOS palette, the byte mapping is proved; the assignment of
those colors to UI roles is a design choice:

| Role | RGB | Native byte |
|---|---:|---:|
| Background | `#000000` | `0x00` |
| Text | `#ffffff` | `0x3f` |
| Scaffold | `#555555` | `0x15` |
| Secondary scaffold | `#aaaaaa` | `0x2a` |
| Excitatory | `#ffaa00` | `0x38` |
| Inhibitory | `#00aaff` | `0x0b` |
| Saturated alert/accent | `#ff00ff` | `0x33` |

Other directly proved examples are red `#ff0000 = 0x30`, orange
`#ff5500 = 0x34`, green `#00ff00 = 0x0c`, blue `#0000ff = 0x03`, and cyan
`#00ffff = 0x0f`.

The six target bytes requested for the N64 design are now all proved:

| Target byte | Exact RGB | Mapping status |
|---:|---:|---|
| `0x00` | `#000000` | **PROVED** |
| `0x2a` | `#aaaaaa` | **PROVED** |
| `0x3f` | `#ffffff` | **PROVED** |
| `0x0c` | `#00ff00` | **PROVED** |
| `0x33` | `#ff00ff` | **PROVED** |
| `0x38` | `#ffaa00` | **PROVED** |

This proves their target display colors. Which UI or neural role receives each
byte remains an implementation/design decision.

### Exact 13.70 callback artifacts

All target addresses in this subsection are in the internal-flash image mapped
at `0x00003000`; the corresponding file offset is `target - 0x3000`.

| Artifact | Target range | File range | SHA-256 |
|---|---|---|---|
| Native byte to RGB | `[0x00063020,0x00063052)` | `[0x60020,0x60052)` | `96a9d40ac0e8277d634c16c4cc43bece9bb2f98295f8fb34d7e439a2e8cd1651` |
| RGB to native, including magic literal | `[0x00063054,0x000630a0)` | `[0x60054,0x600a0)` | `a9fe98122781c77f9b06b35eb05f1fc7d3547f1035f3b00af36eec8b61ecba05` |
| Static callback table | `[0x00064554,0x0006459c)` | `[0x61554,0x6159c)` | `4bdaeb1c029ba0ef4c6d90a1b4d77040475fa48334dd75471a8bf091cc8a1ca7` |
| Table setup routine | `[0x00063f1c,0x00063f46)` | `[0x60f1c,0x60f46)` | `9d87b588e18b3106af96bf63e67333f243e60c79593dab528451d96ac3334985` |

The callback table bytes are:

```text
00000000 a92f0600 b1250600 55300600
f5300600 d92f0600 cd300600 d1330600
55350600 e5320600 f5340600 21300600
e5300600 5d370600 00000000 a1300600
b1300600 cd2f0600
```

Interpreted as little-endian words, `+0x0c` is Thumb pointer `0x00063055`
(RGB to native) and `+0x2c` is Thumb pointer `0x00063021` (native to RGB).
Those are exactly the two offsets and signatures used by the runtime object at
`0x34038f38`.

The native-to-RGB function bytes are:

```text
70b400f00c06c0f30114c0f3810500f00300354404eb840400eb8000
04eb041405eb051500eb00100c70157070bc18707047
```

Its arithmetic is equivalent to:

```c
red   = ((native >> 4) & 3) * 85;
green = ((native >> 2) & 3) * 85;
blue  = ( native       & 3) * 85;
```

The RGB-to-native function and its literal are:

```text
d5289cbf2a30c0b2d52a98bf2a3210b498bfd2b20c4cd52998bf2a31
a4fb0232a4fb003098bfc9b2c0f387139009a4fb012140ea0310c1f3
871140ea8100c0b25df8044b704700bfc1c0c0c0
```

For inputs on the official four-level cube it returns
`(R_level << 4) | (G_level << 2) | B_level`. The caller at `0x047cce70`
passes `(rgb >> 16) & 0xff`, `(rgb >> 8) & 0xff`, and `rgb & 0xff` as the
three arguments. The reverse caller at `0x047cb398` compares the first,
second, and third output bytes against requested red, green, and blue. This
direct call-site evidence proves channel order independently of the display
transport masks.

### Setup, startup, and runtime-reference trace

At `0x00063f1c`, the setup routine loads source `0x00064554`, copies exactly
`0x48` bytes to its stack via the copy routine at `0x0003362c`, then passes the
stack pointer to the veneer at `0x001f14a0`:

```text
00063f20  ldr   r1,[pc,#0x24]  ; 0x00064554
00063f22  movs  r2,#0x48
00063f24  mov   r0,sp
00063f26  bl    0x0003362c
00063f30  mov   r0,sp
00063f32  bl    0x001f14a0
```

The reset startup tables prove this runtime object is not preinitialized
`.data`. The loop at `[0x0001939a,0x000193c6)` consumes three zero ranges from
`0x00003234`:

```text
0x20000000 .. 0x20017460
0x1ffc0000 .. 0x1fff5af0
0x34000000 .. 0x3403f2ac
```

Thus `0x34038f38..0x34038f7f` starts zeroed. The copy loop at
`[0x000193e4,0x0001941e)` consumes only one record:

```text
destination 0x20017460 .. 0x2001b12c
source      0x048ee26c
```

It does not populate the callback table. Exact hashes are:

| Region | SHA-256 |
|---|---|
| Zero loop `[0x1939a,0x193c6)` | `7cc4ff716a66a14eb694cc8e42ca7b6b149d4c1f26bf82f9d6df882198e7d00c` |
| Copy loop `[0x193e4,0x1941e)` | `7682ca4d9ba20f86f4fbc1798925e14ec0746c55883e3d09ed4d90153e6c8195` |
| Startup tables `[0x3234,0x3258)` | `f3acb6da3c216918b4c6ce4d303fe6b08ade4c2f5a6f4d3aba240298b8593442` |

A complete Ghidra reference scan found 34 references into the 0x48-byte
runtime table, all reads or base-address parameters and no writes. Grouped by
slot, the instruction addresses are:

| Slot | Reference instructions |
|---:|---|
| `+0x00` | `0x047d8808`, `0x047ccf24`, `0x047ccf3e`, `0x047ed24e`, `0x047edc76` |
| `+0x04` | `0x047d3854`, `0x047d388c`, `0x047ed252`, `0x047edc78` |
| `+0x08` | `0x047cb642` |
| `+0x0c` | `0x047cb7aa`, `0x047cc80a`, `0x047ccf26`, `0x047ccf40` |
| `+0x10` | `0x047aef18`, `0x047af28c`, `0x047cea0e`, `0x047d3840`, `0x047d8f96` |
| `+0x18` | `0x047e5476`, `0x047e54bc` |
| `+0x1c` | `0x047c3796`, `0x047c37c6` |
| `+0x20` | `0x047c37fa` |
| `+0x24` | `0x047d7188` |
| `+0x28` | `0x047d6fc2` |
| `+0x2c` | `0x047cb3e4` |
| `+0x30` | `0x047bc9d4`, `0x047be786`, `0x047c0950` |
| `+0x3c` | `0x047e8430`, `0x047e8528`, `0x047e9f16` |
| `+0x40` | `0x047eca30` |

Slots `+0x14`, `+0x34`, `+0x38`, and `+0x44` have no statically resolved
consumer. The only resolved write in the nearby range is to `0x34038f90` at
`0x047d8828`, 0x10 bytes beyond this table, so it is not a slot write.

The final destination write performed below the `0x001f14a0` registration
veneer is not independently resolved. Its literal is `0x047ebd45`; in the
static 13.70 mapping that lands on an interior shared label with an
incompatible surrounding stack frame. No reset copy record, relocation record,
direct pointer, or constructor reference examined here explains that veneer.
Accordingly, the link between the static table and runtime object is supported
by the exact slot layout, matching function signatures, setup copy, and all
consumer offsets, but the last copy into `0x34038f38` remains **strongly
linked rather than separately proved**. This caveat does not weaken the color
mapping itself: the two function bodies are exact inverses and the callers
prove their RGB argument order.

### Offline execution and cross-version confirmation

The preserved Thumb functions were executed offline with Unicorn 2.1.4. All
64 native bytes `0x00..0x3f` converted to RGB and round-tripped to the original
byte. All 64 RGB cube points over `{0,85,170,255}^3` converted to the formula
above. The temporary JSON has 8,171 bytes and SHA-256
`1ef4a0be57ddef09ade0e520ee94aa60382f628c87678734115550de46a718cb`.

Firmware 3.10 independently contains the same arithmetic in external XIP:

| Direction | Target range | External-XIP file range | Region SHA-256 |
|---|---|---|---|
| Native to RGB | `[0x046c29e0,0x046c2a10)` | `[0x0c29e0,0x0c2a10)` | `1decf718b6ba92484bffdae5e0c5e69fede52c2bd72751d673ba2325e3a6d13d` |
| RGB to native | `[0x046c2a10,0x046c2a5c)` | `[0x0c2a10,0x0c2a5c)` | `f13fb421209d52636a8498b0131260e7a7693229024ac0ac0619790b2f3d0eb6` |

Those regions are in `stream_01_external_xip.bin` with SHA-256
`17406fec718b2e477e2b35fbc3f902ed7b2068294aa6141e7fed2bcdda7ec66b`.
This cross-version match rules out the 13.70 result being an isolated table or
disassembly coincidence.

The extracted Connect IQ constant table supplies API-side RGB values but no
second adjacent native-byte field. No constant input/output pair was found in
the resource tables themselves. The resolved callbacks now provide the direct
correlation the earlier resource scan lacked.

### Reproduction commands

```powershell
Get-FileHash -Algorithm SHA256 `
  artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin, `
  artifacts/firmware/analysis/Forerunner245_310/stream_01_external_xip.bin

python -c "from pathlib import Path; import hashlib; p=Path(r'artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin'); b=p.read_bytes(); [(print(hex(o),hex(n),hashlib.sha256(b[o:o+n]).hexdigest(),b[o:o+n].hex())) for o,n in [(0x60020,0x32),(0x60054,0x4c),(0x61554,0x48),(0x60f1c,0x2a)]]"

python -c "from pathlib import Path; import hashlib; p=Path(r'artifacts/firmware/analysis/Forerunner245_310/stream_01_external_xip.bin'); b=p.read_bytes(); [(print(hex(o),hex(n),hashlib.sha256(b[o:o+n]).hexdigest(),b[o:o+n].hex())) for o,n in [(0xc29e0,0x30),(0xc2a10,0x4c)]]"
```

Capstone was used in little-endian Thumb mode with base `0x00003000` for the
13.70 internal image and `0x04600000` for the 3.10 external image. Unicorn
mapped the preserved 13.70 internal bytes at `0x00003000`, entered the two
functions with the Thumb bit set, and stopped at a synthetic return address.
All generated execution output remained under `%TEMP%`.

If proof of the final RAM destination is later required, the smallest
offline-only experiment is to clone the Ghidra project into `%TEMP%`, seed
functions at `0x00063f1c`, `0x00063020`, and `0x00063054`, then trace the
`0x001f14a0` import/fixup ABI and any dispatcher table that reaches the setup
routine. This requires no live color calibration, device access, package
construction, or staging write.
