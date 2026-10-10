# Host tooling

The current host build uses CMake and emits `flyos-screen.ppm`, a dependency-free 240×240
preview. Firmware extraction and device tools belong here only after their formats and
read-only behavior have tests and recorded provenance.

Convert the PPM preview to a PNG for ordinary image viewers without installing
an image library:

```powershell
python flyos/tools/ppm_to_png.py flyos-screen.ppm flyos-screen.png
```

`build_interaction_lab.py` invokes the host-only `flyos-interaction-exporter`
and bundles its real C neural/framebuffer traces into a standalone HTML lab.
See [`flyos/README.md`](../README.md#interactive-replay-lab). Native screens,
queue outcomes, view classifications, and display acknowledgments are fixture
inputs; the artifact cannot validate Garmin callbacks, RAM, or live timing.
