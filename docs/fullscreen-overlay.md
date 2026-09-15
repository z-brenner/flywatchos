# FR245 full-screen FlyOS overlay

## Result

The offline successor to the successful bounded overlay now repaints the full
240-by-240 logical framebuffer on every eligible GarminOS display flush. This
prevents the underlying Garmin page from showing through. The face contains a
large `FLY LIVES` title, a centered dorsal fly silhouette, `STATE QUIET`,
`AGE 01:42:32`, and five raw active-low button markers labelled `L 1 2 3 4`.

The target is in `flyos/target/fr245_1370_fullscreen_overlay/`. It preserves
the experimentally successful hook, startup/backend guards, ABI, original
display tail dispatch, and audited allocation:

| Property | Value |
|---|---|
| Hook | `0x00009a20` -> `0x001f6000` |
| Hook SHA-256 | `49ff680c8b811f58b6747fea531fcbc8b88b3142946a1cad4271e0911f02a362` |
| Payload size | 974 bytes |
| Payload SHA-256 | `358d71190321f7dd9d51de8ac3c913e370b0fc23a25e7541d072d2ac83941ffb` |
| Audited allocation | `0x001f6000..0x001f63ff` (1,024 bytes) |
| Free allocation | 50 bytes |
| Released framebuffer SHA-256 | `15f644334fa872b0d44dec173b74e302c862eedbbc47c6c8ba285d2ba4881722` |
| Dirty rectangle | `(0, 0, 240, 240)` |

## Offline verification

Unicorn executes the compiled Thumb payload from its linked address. Two runs
starting with different framebuffer contents produce the same 57,600-byte
image, contain no untouched sentinel bytes, and preserve 64-byte canaries on
both sides of the framebuffer. The payload preserves callee-saved registers
and the stack pointer, marks the full screen dirty, and tail-dispatches the
original Garmin flush with the original framebuffer pointer.

The button test maps the K28 GPIO page, verifies exactly one 32-bit read from
each of `GPIOA_PDIR`, `GPIOC_PDIR`, and `GPIOD_PDIR`, and observes no peripheral
writes. Pulling each of the five inferred active-low inputs low changes pixels
only inside that input's 12-by-12 marker. When either initialization guard is
false, the payload skips framebuffer and GPIO access and still dispatches the
original flush.

Reproduce the focused checks with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File flyos/target/fr245_1370_fullscreen_overlay/test-build.ps1
python -m unittest tools/garmin-firmware/tests/test_emulate_fullscreen_overlay_payload.py -v
python tools/garmin-firmware/emulate_fullscreen_overlay_payload.py flyos/target/fr245_1370_fullscreen_overlay/build/overlay.bin --report artifacts/firmware/analysis/fullscreen-overlay-emulation-1370.json --preview artifacts/firmware/analysis/fullscreen-overlay-preview-1370.pgm
```

The rendered preview is
`artifacts/firmware/analysis/fullscreen-overlay-preview-1370.png`. The code-cave
evidence remains
`artifacts/firmware/analysis/code-cave-overlay-xrefs-1370.txt`.

## Limits

This payload interposes on GarminOS; it is not a standalone boot image. The
GPIO-to-physical-button mapping remains provisional except for key zero, which
is strongly inferred to be LIGHT/power. The emulator does not model GarminOS
scheduling, display DMA/FlexIO, switch bounce, or LCD electrical behavior.
Packaging, loader acceptance, and recovery require separate validation.
