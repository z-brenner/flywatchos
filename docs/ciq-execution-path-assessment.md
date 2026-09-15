# Connect IQ execution-path assessment

## Scope

This assessment reviews public research for whether it supplies a path from the
connected non-Music Forerunner 245 (HWID 3076, system 10.40) to a replacement
of Garmin firmware. It is an offline document. No CIQ application, PRG file,
protocol command, update file, or other data from this research has been sent
to the watch.

## Preserved source

The public repository `anvilsecure/garmin-ciq-app-research` was cloned at Git
commit `216749fe32a81f33e20959db0de680c470bbbffe` into the private artifact
area. Its recursive file-hash manifest is
`artifacts/external-sources/anvilsecure-garmin-ciq-app-research-sha256.csv`,
SHA-256 `ea550fedbc2171d1824d0c2ab10878d2000b86762509a5f327069b60f9d8ba52`.

The associated public report describes research on a **Forerunner 245 Music**
and Connect IQ's MonkeyC virtual machine. It documents application-layer
vulnerabilities, including memory-safety bugs and permission bypasses. The
repository's included demonstration is for a different Forerunner 55 firmware
and states that it uploads extracted memory to a remote URL. It was not run.

## Applicability

| Question | Evidence | Conclusion |
|---|---|---|
| Is this a Garmin main-firmware update bypass? | The repository contains CIQ/PRG parsers and CIQ proof-of-concept applications, rather than a GCD loader exploit or signed-image forgery. | **No evidence.** |
| Does it match the connected watch? | Research target is 245 Music; connected watch is non-Music HWID 3076, system 10.40. Several documented virtual addresses are explicitly firmware-version-specific. | **Unproven and not transferable.** |
| Does it establish a persistent FlyOS boot path? | The findings concern code executing through Garmin's existing CIQ virtual machine and native API implementation. | **No.** It neither replaces the resident loader nor establishes boot-time control. |
| Is a live proof-of-concept acceptable? | It would be a speculative exploit on a device with personal data. One included demonstration is designed to export memory remotely. | **No.** It violates the project privacy and live-exploit constraints. |
| Does it change the boot-chain verdict? | The resident loader remains absent from analyzed packages and recovery is still unknown. | **No.** The verdict remains **YELLOW**. |

## Result

This research establishes that Garmin's application layer has had serious
historical bugs. It does not demonstrate that the connected watch is vulnerable,
does not identify a safe payload for this watch, and does not establish a
custom-firmware installation mechanism. It must not be treated as authorization
or evidence for an unsigned GCD, signature bypass, unlocked debug port, or
recovery path.

The only defensible uses of the source are offline format comparison and
version-specific code review. Any future live experiment would need a separate
model-and-version-specific validation and the recovery evidence required by
`recovery.md`.

## Sources

- Anvil Secure, [Compromising Garmin's Sport Watches](https://www.anvilsecure.com/blog/compromising-garmins-sport-watches-a-deep-dive-into-garminos-and-its-monkeyc-virtual-machine.html), accessed 2026-09-13.
- [anvilsecure/garmin-ciq-app-research](https://github.com/anvilsecure/garmin-ciq-app-research), pinned locally as above.
