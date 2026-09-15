# Host tooling

The current host build uses CMake and emits `flyos-screen.ppm`, a dependency-free 240×240
preview. Firmware extraction and device tools belong here only after their formats and
read-only behavior have tests and recorded provenance.

Convert the PPM preview to a PNG for ordinary image viewers without installing
an image library:

```powershell
python flyos/tools/ppm_to_png.py flyos-screen.ppm flyos-screen.png
```
