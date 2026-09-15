# FR245 13.70 in-app overlay

This target is an offline interposition experiment for the SHA-256-pinned
Forerunner 245 non-Music 13.70 main image. It does not initialize hardware or
replace GarminOS. It replaces the `BL` at `0x00009a20` with a call to a payload
at `0x001f6000`. The payload draws a bounded scientific specimen plate with a
small dorsal fly silhouette and `FLY LIVES` into the logical framebuffer, then
invokes the original display-backend dispatcher.

The payload assumes the exact addresses and initialized state documented in
`artifacts/firmware/analysis/display-inapp-render-1370.md`. It is not safe to
use on another model or firmware version. The generated GCD remains quarantined
analysis material because resident-loader acceptance and recovery are not
proven.
