# Read-only device backup

`read-garmin-disk.ps1` creates a host-side raw image of the small USB volume
exported by the Forerunner 245 in normal mode. It refuses a non-USB disk, a
device name outside the expected Garmin FR245 family, or a source disk larger than
64 MiB. The source handle uses `FileAccess.Read`; only the ignored host artifact
is opened for writing.

The resulting image can contain personal or deleted filesystem data. Keep it
local under `artifacts/`.
