# Synthetic 13.80 five-key candidate: offline decision

This is an **offline-only** candidate for the user-observed synthetic 13.76
GarminOS-resident overlay. It does not replace GarminOS and has not been
copied to the watch. The watch's internal flash has not been read back, so
13.76 is identified by the previous installation record and observed face,
not by a flash dump.

## Exact change

The candidate changes 11 instruction bytes in the existing 996-byte primary
FlyOS payload. Its key filter admits indices 0 through 4 on stable HOME
instead of 1, 3, and 4; it removes the BACK-held START escape. The filter
still passes native/non-HOME views, malformed view state, and USB mass-storage
cache states 3/4 to Garmin. Existing framebuffer and neuron code is unchanged.
The synthetic main-image version advances from 13.76 to 13.80, with necessary
additive/checkpoint repairs. The official update helper remains byte exact.

The existing renderer shows temporary button state only for START, DOWN, and
UP after a short tap. LIGHT and BACK are sampled physically while held, but
the current status/pulse display does not reliably acknowledge a completed
short tap of those keys. Also, consuming LIGHT on FlyOS HOME makes Garmin's
normal backlight behavior unavailable on that view. An event that begins on
HOME and ends after a view transition can still cross the HOME/pass-through
boundary; this candidate has no proven per-key sequence owner. These are
material UX and input-policy limitations.

The candidate does **not** change USB detach or native view teardown. The
user reported that the charging view returns to FlyOS by itself after more
than ten seconds, while START has no immediate visible effect. The 13.80
candidate is not a fix for that delay.

## Reproduction and checks

The local builder is `tools/garmin-firmware/n64_fivekey_patch_package.py`.
It accepts only SHA-pinned official 13.70 and previous 13.76 package bytes,
and its `build` command requires the SHA-pinned private instruction-emulator
receipt. It uses fixed, create-new filenames in ignored quarantine; it has
no USB or watch-staging action. `verify` reconstructs the packages and
compares exact bytes. The private emulator exercised 34 key/view cases and
one full HOME frame with the original 384-byte stack peak. Five package
unit tests, full-image application-side checks, and official-helper identity
checks pass. These checks cannot prove resident-loader admission or live
behavior.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Quarantined 13.80 candidate | 5,120,675 | `2054be63e12531c61c7417156fa208b27db82af70b518dbf9fd0f8df1e2a7dbd` |
| Quarantined 13.81 official-code restore wrapper | 5,120,675 | `b62be4c422dfe03f83fef30139557143ad285abc18b733899801dba16ffd9f5b` |
| Preserved official 13.70 source | 5,120,675 | `8ebefacf6bcc00bec0fb271596abfb9618f9a3114d32b3a106fbd27d5a366adc` |

The 13.81 wrapper carries official 13.70 code/resources with only synthetic
version and checksum repair. It can be offered through the normal updater
only if GarminOS boots, USB mass storage enumerates, and the updater works.
There is no established nonboot recovery path. The 13.80/13.81 artifacts
remain unrecognized by the locked staging script and outside Git.

## Decision

**NO-GO for live staging at present.** The package is a useful bounded
binary-patch experiment, but it does not address the reported charging delay,
weakens the LIGHT/backlight behavior, and lacks full event-sequence ownership.
Those limitations do not justify another full application/resource rewrite
with nonzero, unquantified brick risk. Future live consideration requires a
candidate whose exact behavior, rollback conditions, and write scope are
reviewed after these issues are resolved.
