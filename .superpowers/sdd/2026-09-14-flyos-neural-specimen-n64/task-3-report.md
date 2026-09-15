# Task 3 report - Read-only Garmin runtime-state evidence

## Status

Complete. The deterministic analyzer is bound to the exact Forerunner 245
non-Music 13.70 `fw_all` image and exposes only four runtime signals:

- watch-face image bodies `0x0005306c` / `0x000530cc`, callable Thumb
  addresses `0x0005306d` / `0x000530cd`, callback identity `0x0005adf5`, and
  list root `0x20003e84`;
- active-low BACK at GPIOD PDIR `0x400ff0d0`, bit 1;
- narrow USB mass-storage byte `0x1ffc6f25`, with only values 3/4 true;
- direct battery binary32 cache `0x1ffcccd8`, rejecting `-1.0`, non-finite,
  and values outside `[0,100]`.

Generic USB attachment, charging, update pending, HR BPM, and motion remain
explicitly unavailable and fall back to zero/`--`. Follow-up binary evidence
now makes the exact six-role target palette available without changing any
runtime-signal status.
The tool never opens the watch, reads live RAM/MMIO, invokes a Garmin getter or
callback, performs a peripheral transaction, modifies a target integration,
or creates/stages a package.

The implementation follows independent audit
`.superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-3-independent-audit.md`,
SHA-256
`ff2fcd25fa291e208c9741f8aac6f5bd204f1ce7e15b7dd5621be0157ace023b`.

## TDD evidence

The first RED run added only the test file, then ran:

```text
python -m unittest tools/garmin-firmware/tests/test_fr245_runtime_state.py
```

It failed at setup with the intended assertion
`runtime-state analyzer must exist`; no production analyzer existed.

After the initial implementation, a focused run exposed one exact contract
wording mismatch (`equals 1`), which was corrected in the report generator.
The test was not weakened.

A second RED cycle added schema attacks for an extra invented available signal
and a claimed target palette with no mapping proof. Both tests failed because
the first validator version accepted them. The validator was then tightened to
inspect every signal, including future/extra entries, and to require explicit
pinned color-role mapping evidence for any available palette.

Initial focused result before independent review:

```text
Ran 13 tests in 0.187s
OK
```

The initial focused suite covered the pinned image hash/base/size, all
evidence assertions, the exact four generated signals, fail-closed unavailable
signals, watch-face list semantics, exact cache/MMIO sources, prohibited
operations, basic schema rejection, and JSON reproduction.

## Static evidence pinned by the analyzer

- Exact SHA-256 of the 5,079,040-byte 13.70 image.
- Both watch-face predicate function bodies, their update-condition call site,
  callback and root literals, log-string pointer, and diagnostic string.
- Official USB mapper body and cached-enum address literal.
- Both battery getter front ends and their battery-object base literal.
- Full five-entry key table containing encoded BACK pin `0x61`.
- Framebuffer converter `0xea`/`0x15` mask sequence.
- Both RGB222 conversion functions, their static callback table and exact
  slots, and the setup routine that copies the table.
- `Install Now`, `Install Later`, and `Charging` resource strings, explicitly
  classified as insufficient runtime-state evidence.

Any image or byte-range mismatch aborts generation. The JSON has no timestamp
and sorts keys, so rerunning the CLI reproduces it byte-for-byte.

## Verification

Python compilation completed without output:

```text
python -m py_compile tools/garmin-firmware/fr245_runtime_state.py tools/garmin-firmware/tests/test_fr245_runtime_state.py
```

Before the independent review fixes, the complete Garmin firmware Python suite
passed:

```text
python -m unittest discover -s tools/garmin-firmware/tests -p 'test_*.py'
Ran 111 tests in 335.149s
OK
```

## Files and SHA-256

| File | SHA-256 |
| --- | --- |
| `tools/garmin-firmware/fr245_runtime_state.py` | `fcc0512696aeaa4fc9e8cfe7c3bd24f027ce2ee9639c1601ad95cc3ba047c1ab` |
| `tools/garmin-firmware/tests/test_fr245_runtime_state.py` | `fe35211f2e5b09966a0d6ded7b9f46549a788c722d4e132338c2dd4b71aff3aa` |
| `docs/runtime-state.md` | `79dbee4ccd78eff26a97e052099f689e5b816e13fcb1ceb11fc4262f8f5a8147` |
| `artifacts/firmware/analysis/fr245-1370-runtime-state.json` | `53d05da7623b14772e466118c45dda93fdae482085aa194100bbafeb474a7e5d` |

## Task 4 gate

Task 4 may consume only these four available sources. Before target
integration it must emulate both Garmin watch-face routines, constrain every
dynamic node read and control-flow target, and prove that false/invalid home
state or held BACK leaves the framebuffer byte-identical. All optional N64
inputs remain invalid until separate evidence meets this same standard. The
six static palette constants are also available; they require no runtime read.

## Independent review fix round

The independent review found that the first validator checked shape and prose
rather than the exact allowlist, exposed even image addresses as callable
getters, and accepted arbitrary CLI output paths. Adversarial tests were added
before the fixes. The RED run produced 45 failing mutation/output subtests and
one missing-field error, confirming all reported gaps.

`validate_report` now regenerates the canonical report from the pinned local
image, including every byte assertion, and recursively compares exact types,
keys, list lengths/order, and values. It rejects:

- unknown top-level, signal, source, proof, and assertion content;
- invented available or unavailable signals;
- address, semantics, proof prose, and prohibited-operation substitution;
- promoting any of the six unavailable signals with copied valid evidence;
- inconsistent unavailable blocks and every noncanonical palette state;
- changed image path, base, size, or SHA-256; and
- failed, changed, duplicated, or relocated evidence assertions.

The watch-face source now separates image addresses `0x0005306c` and
`0x000530cc` from callable Thumb addresses `0x0005306d` and `0x000530cd`, with
`instruction_set: thumb` and `thumb: true`. The validity contract explicitly
requires the odd callable addresses and prohibits calling the even image
locations.

The CLI no longer has an output option and writes only UTF-8/LF JSON to
standard output. Tests pass traversal, alternate-root/drive, non-JSON,
target-like, quarantine-like, staging-like, protected-input, and hard-link
destinations through the rejected `--output` interface and verify that none is
written or changed. A separate RED cycle caught Windows CRLF translation in
stdout; binary UTF-8 output now reproduces the checked-in JSON byte-for-byte.

Markdown punctuation was reduced to ASCII to avoid renderer-dependent mojibake.

Final post-review focused verification:

```text
python -B -m unittest tools/garmin-firmware/tests/test_fr245_runtime_state.py -v
Ran 15 tests in 1.479s
OK

python -m py_compile tools/garmin-firmware/fr245_runtime_state.py tools/garmin-firmware/tests/test_fr245_runtime_state.py
```

No file outside the Task 3 analyzer, tests, documentation, JSON, and this
report changed during the review fix. The completed 111/111 full-suite run
above remains the pre-review baseline; the stricter 15-test Task 3 suite and
Python compilation were rerun after every final code change.

## Color evidence extension

The follow-up audit
`.superpowers/sdd/2026-09-14-flyos-neural-specimen-n64/task-3-color-scout.md`
(SHA-256
`3c8f643f08d92de5682803a1e883ad1048bef36d97d471ad8eea9676fc6daad2`)
resolved the RGB/native conversion directly in the pinned 13.70 image.

The extension pins:

- native-to-RGB body `0x00063020..0x00063051`, SHA-256
  `96a9d40ac0e8277d634c16c4cc43bece9bb2f98295f8fb34d7e439a2e8cd1651`;
- RGB-to-native body `0x00063054..0x0006309f`, SHA-256
  `a9fe98122781c77f9b06b35eb05f1fc7d3547f1035f3b00af36eec8b61ecba05`;
- callback table `0x00064554..0x0006459b`, SHA-256
  `4bdaeb1c029ba0ef4c6d90a1b4d77040475fa48334dd75471a8bf091cc8a1ca7`;
- setup body `0x00063f1c..0x00063f45`, SHA-256
  `9d87b588e18b3106af96bf63e67333f243e60c79593dab528451d96ac3334985`;
- setup source literal `0x00063f48 -> 0x00064554`; and
- table slots `+0x0c -> 0x00063055` and `+0x2c -> 0x00063021`.

The exact encoding is
`native=(R_level<<4)|(G_level<<2)|B_level`, with channel components
`00/55/AA/FF` mapped to levels `0/1/2/3`. Tests enumerate all 64 RGB cube
points, verify the formula, convert each native value back to RGB, and require
the set of native results to equal `0x00..0x3f`.

The canonical target roles are background `0x00` (`#000000`), scaffold
`0x2a` (`#AAAAAA`), text `0x3f` (`#FFFFFF`), excitatory `0x0c` (`#00FF00`),
inhibitory `0x33` (`#FF00FF`), and saturated `0x38` (`#FFAA00`). The strict
validator rejects every role byte/RGB mutation, formula or channel-level
change, function/callable address substitution, table/slot/setup mutation,
audit-hash change, and failed color evidence assertion.

The RED run before implementation reported 3 failures and 11 errors because
the palette remained unavailable and the conversion/evidence interfaces did
not exist. Final focused verification is:

```text
python -B -m unittest tools/garmin-firmware/tests/test_fr245_runtime_state.py -v
Ran 20 tests in 1.877s
OK

python -m py_compile tools/garmin-firmware/fr245_runtime_state.py tools/garmin-firmware/tests/test_fr245_runtime_state.py
```

No target code, device, firmware package, quarantine artifact, or staging path
was touched by the color extension.
