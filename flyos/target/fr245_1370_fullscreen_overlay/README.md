# FR245 13.70 full-screen in-app overlay

This offline target is the successor to the experimentally successful bounded
overlay. It retains the same guarded display-update interposition at
`0x00009a20`, payload entry at `0x001f6000`, full-screen dirty notification,
ABI behavior, and tail dispatch to Garmin's original backend. On every eligible
flush it deterministically repaints all 57,600 logical framebuffer bytes before
drawing a sparse scientific-instrument face: large `FLY LIVES` title, centered
dorsal fly specimen, `STATE QUIET`, `AGE 01:42:32`, and five raw active-low
button markers (`L 1 2 3 4`). The input sampler performs exactly one read from
each relevant GPIO PDIR word and does not write peripheral registers.

This is still GarminOS interposition, not standalone firmware or hardware
initialization. It is tied to the pinned non-Music FR245 13.70 code image and
must remain offline until separately packaged, validated, reviewed, and
explicitly approved for a specific device write.
