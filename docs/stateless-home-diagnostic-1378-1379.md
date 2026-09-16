# FR245 stateless HOME diagnostic, offline 13.78/13.79 pair

**Decision: NO-GO for live use.** These two quarantined images are analysis objects. The 13.78 image instruments the normal GarminOS display submission; it is neither a FlyOS replacement nor proof that an update will be accepted by the watch. The 13.79 image is a coherent forward-version wrapper around the official 13.70 executable/resources. It is a *conditional* rollback only while GarminOS and its normal USB updater still work. No nonboot recovery path is known. No device-ready proposal, staging profile, watch write, or personal-data upload was made.

The earlier 1,078-byte Round 5 probe drew a panel over every native frame. That could obscure an update or recovery prompt. The reviewed variant draws only when a bounded double-snapshot classifies the first visible view as the stable HOME identity. NON_HOME, INVALID, and null-framebuffer cases pass through without any framebuffer write. This protection makes the experiment less informative: a frozen panel after USB detach cannot distinguish a missing display call from a native view hiding HOME, absent physical refresh, or display trouble. It does not justify exposing the watch to update risk.

## Construction and custody

The public constructor is `tools/garmin-firmware/stateless_home_diagnostic_package.py`. The public C/assembly/linker source is in `tools/garmin-firmware/stateless_home_diagnostic/`. The exact private Round 6 source, build outputs, Unicorn harness, and 49-case receipt are retained under the ignored `artifacts/firmware/analysis/atlas-shell-runs/round6-home-only-diagnostic/`. The constructor pins every input by SHA-256, recompiles the public source with Arm GNU Toolchain 15.2.1, and requires byte-for-byte identical hook and payload sections. It requires the 49-case receipt, including zero framebuffer writes and exactly one original flush call for NON_HOME and INVALID cases. The seeded framebuffer has varied 6-bit pixel values and is compared byte-for-byte. The null case also has zero framebuffer writes. The original Round 5 evidence remains intact.

The input GCD is the original non-Music 13.70 `Forerunner245_1370_GUPDATE.GCD`, 5,120,675 bytes, SHA-256 `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc`. Its decoded `fw_all` is 5,079,040 bytes, SHA-256 `b45be1baf98999af10f073bef52b284beb2aea6abbb7cde2ffa59fb6bcedeab6`. The previous 13.76 candidate is pinned at SHA-256 `9dc61b99cebacc50f121b9145ddfab21445344fac6f70a4ab68dde205fcf84de` only to establish the prior hook baseline; construction starts from the official image, never from 13.76. The new public `probe.c` is SHA-256 `b94533b210e72c074616d7f3d1a777fc18eeacfa1d9bfbe4c9bbf4601207b688`. The four-byte hook is SHA-256 `e121cf4022946627b5e0f510bb3a51c26b560e6bf6d0d0c2110981ada161b170`; the 1,066-byte payload is SHA-256 `38ec0e691aaa24e28e3eac734eed7051eb6f599305696410346c608bb1e62a94`. The private Unicorn receipt SHA-256 is `b323e10de231c19cf6b505ebd04a64ef231618d7dce32adfd1572b414b5e03ae`.

Candidate 13.78 replaces exactly the stock display `BL` at runtime `0x00009A20` with a `BL` to `0x001FA400`, places the 1,066-byte HOME-only probe in the 2,048-byte secondary cave, and makes coherent descriptor/header-version and additive/checkpoint repairs. Its key hook at `0x0000FA48`, the prior primary payload region at `0x001F6000..0x001F63FE`, and secondary padding are all reconstructed from official 13.70 bytes. The one-byte primary additive repair at `0x001F63FF` computes to its official `0xFF` value in this build, so no primary byte actually differs. The candidate's only decoded differences from official occur in the version byte, display hook, secondary payload, and final checksum byte. Exact disjoint raw and decoded diff ranges are in the private construction report.

Restore 13.79 has official 13.70 decoded application and resources byte-for-byte apart from the version byte and final additive repair. The helper stream, descriptors other than version, record layout, and package size remain official. Both packages pass the confirmed application-side full-image validator; that validator does **not** model resident-loader authentication, update acceptance, version policy, installation, or recovery.

| Artifact | SHA-256 | Bytes |
| --- | --- | ---: |
| 13.78 HOME diagnostic (`.gcd.analysis-only.DO_NOT_INSTALL`) | `92ce1e4bf9360cdda6fac37729f8b7bd85e5ab398482a4aa1b7b04f929509e5e` | 5,120,675 |
| 13.79 official-code restore (`.gcd.analysis-only.DO_NOT_INSTALL`) | `7a4fc373c0ceb7d0fbdaffa3bdacde0bc92668c17ebec389d6d4573d8a8c58fe` | 5,120,675 |

Both exist only beneath the ignored local `artifacts/firmware/quarantine/` root. Create-new naming and a transaction with readback prevent overwrites and clean up newly created outputs on failure. The locked `stage-gupdate.ps1` has no modes, source filenames, or SHA-256 pins for these artifacts; its pinned source was inspected without invoking it. This is a containment fact, not approval for a live experiment.

## Reproduction and validation

From the repository root, with the private original image/evidence and pinned local toolchain available:

```powershell
python -B -m unittest -v tools/garmin-firmware/tests/test_stateless_home_diagnostic_package.py
python -B tools/garmin-firmware/stateless_home_diagnostic_package.py construct-report
python -B tools/garmin-firmware/stateless_home_diagnostic_package.py verify
```

The initial create-new build used `python -B tools/garmin-firmware/stateless_home_diagnostic_package.py build`; it deliberately fails on a second invocation while the outputs exist. Tests passed 7/7, Round 6 Unicorn passed 49/49, construction and post-write exact verification passed. The private build report, strict report, and SHA ledger are respectively SHA-256 `b48537b880526e3e64d5be88fc565c44bab7531cc16d9b6dd5f4d402d3f7f54a`, `fd6fa542a805b850bc5992f34d9f9258fd8e7cfc4eac1644a86aa874e576268c`, and `61c5a699de87665a95b4dd79361ce4c01867257e8a71a5002f5a8d95a5b9a450`. Source SHA-256 checks before and after matched. Corruption, changed source pin, missing receipt, output collision, wrong output root, and transaction cleanup have regression coverage.

The safest next work is read-only analysis of display cadence and native-view/USB event transitions. The package pair must remain quarantined.
