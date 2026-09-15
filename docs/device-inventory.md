# Forerunner 245 device inventory

Inventory time: 2026-09-13 17:19 PDT (2026-09-14 00:19 UTC)

Scope: normal operating mode, host-side read operations only. No Garmin protocol commands, mode changes, resets, installs, firmware transfers, raw-device writes, filesystem writes, or source deletions were issued. Device-specific identifiers are redacted from this document.

## Host

Command:

```powershell
$os = Get-CimInstance Win32_OperatingSystem
$os | Select-Object Caption, Version, BuildNumber, OSArchitecture
```

Sanitized result:

```text
Caption:        Microsoft Windows 11 Pro
Version:        10.0.26200
BuildNumber:    26200
OSArchitecture: 64-bit
Shell:          PowerShell
```

## USB presentation

Commands:

```powershell
Get-PnpDevice -PresentOnly |
  Where-Object {
    $_.FriendlyName -match 'Garmin|Forerunner' -or
    $_.Manufacturer -match 'Garmin'
  }

Get-PnpDeviceProperty -InstanceId '<Garmin device instance>' |
  Where-Object KeyName -in @(
    'DEVPKEY_Device_HardwareIds',
    'DEVPKEY_Device_CompatibleIds',
    'DEVPKEY_Device_Service',
    'DEVPKEY_Device_Children'
  )

Get-PnpDevice -PresentOnly |
  Where-Object InstanceId -like 'USB\VID_091E&PID_2C04*'
```

Sanitized result:

| Property | Value |
|---|---|
| USB vendor ID | `091e` (Garmin) |
| USB product ID | `2c04` |
| USB descriptor revision code | `0509`; its meaning is not established and it is not treated as the bootloader version |
| USB function | USB mass storage |
| Compatible class | `08` mass storage |
| Subclass | `06` SCSI transparent command set |
| Protocol | `50` USB bulk-only transport |
| Windows service | `USBSTOR` |
| USB product | `Garmin FR245 Flash` |
| Storage product revision | `1.00` |
| PnP status | OK |

Windows exposes a single, non-composite USB device node. No `MI_xx` interface nodes were present. There was no Garmin HID, serial/COM, or separate proprietary interface in the present-device set. The class/protocol combination implies bulk IN and bulk OUT transport, but endpoint addresses were not available through the host metadata used here.

Windows also created these higher-level nodes:

```text
DiskDrive: Garmin FR245 Flash USB Device
WPD:       GARMIN (service WUDFWpdFs)
```

The WPD node is Windows' portable-device/filesystem representation of the mounted mass-storage volume. It is not evidence of a separate MTP interface. This connected unit is operating as USB mass storage, not MTP.

All USB instance suffixes, Windows container identifiers, and unit-specific identifiers are redacted.

## Disk, partition, volume, and filesystem

Commands:

```powershell
Get-Disk |
  Where-Object FriendlyName -match 'Garmin|FR245' |
  Select-Object Number, FriendlyName, BusType, PartitionStyle,
                IsReadOnly, IsOffline, Size,
                LogicalSectorSize, PhysicalSectorSize

Get-Partition |
  Where-Object DriveLetter -eq 'D' |
  Select-Object DiskNumber, PartitionNumber, DriveLetter, Type, Size, Offset

Get-Volume -DriveLetter D |
  Select-Object DriveLetter, FileSystemLabel, FileSystem, DriveType,
                HealthStatus, AllocationUnitSize, Size, SizeRemaining
```

Result:

| Property | Value |
|---|---:|
| Mount | `D:\` |
| Label | `GARMIN` |
| Bus | USB |
| Media | Removable |
| Partition style reported by Windows | MBR |
| Partition type | FAT16 |
| Filesystem | FAT |
| Disk size | 20,807,680 bytes |
| Volume size | 20,738,048 bytes |
| Free space at inventory time | 15,730,688 bytes |
| Logical / physical sector | 512 / 512 bytes |
| Allocation unit | 2,048 bytes |
| Health | Healthy |

Windows reported the device as writable (`IsReadOnly: False`). The investigation did not use that capability and did not attempt to change the device's read-only state, because doing so could itself alter device or host storage metadata.

## Model and installed software

`GarminDevice.xml` was read from the copied backup, not reparsed from the live volume.

Command pattern:

```powershell
[xml]$xml = Get-Content '<backup>\GarminDevice.xml' -Raw
$xml.Device.Model |
  Select-Object Description, PartNumber, SoftwareVersion
```

Sanitized result:

| Property | Value |
|---|---|
| Model | Forerunner 245 |
| Garmin part/HWID | `006-B3076-00` |
| Installed software value | `1040` |
| Displayed version interpretation | `10.40` |
| Connect IQ VM version advertised | `3.3.1` |
| Unit ID | Present, redacted |

The model string, small FAT16 storage volume, `FR245 Flash` USB identity, and part number identify this as the non-Music Forerunner 245 variant.

Neither hardware revision nor bootloader version is exposed in `GarminDevice.xml`. No accessible metadata was found that safely establishes either value. The USB revision code `0509` and storage-product revision `1.00` must not be substituted for a bootloader version.

## Read-only backup

Destination:

```text
%USERPROFILE%\flywatchos\artifacts\original-device-files\
```

Copy command:

```powershell
robocopy.exe D:\ %USERPROFILE%\flywatchos\artifacts\original-device-files /E /COPY:DAT /DCOPY:DAT /R:0 /W:0 /XJ /SL /NFL /NDL /NJH /NJS /NP
```

`/E` copies every accessible directory, including empty directories. `/COPY:DAT` preserves file data, attributes, and timestamps. `/DCOPY:DAT` requests the same preservation for directories. `/R:0 /W:0` prevents retry loops, `/XJ` prevents junction traversal, and `/SL` copies links themselves if present. No mirroring, purge, move, delete, or source-write option was used. Robocopy exit code `1` means files were copied successfully.

Backup result:

| Measure | Result |
|---|---:|
| Source files | 204 |
| Destination files | 204 |
| Source directories | 53 |
| Destination directories | 53 |
| Copied bytes | 4,630,156 |
| Files with matching length | 204 |
| Files with matching SHA-256 | 204 |
| Missing or mismatched files | 0 |
| File timestamps preserved exactly | 204 / 204 |
| Directory timestamps preserved exactly | 49 / 53 |

Four source directories expose the Windows epoch year 1601, consistent with unrepresentable/zero FAT directory dates. NTFS destination directories received normal creation dates. Their contents and file timestamps still verified.

Hashes were calculated independently against the source and destination with `Get-FileHash -Algorithm SHA256`. The detailed manifest contains relative paths, lengths, timestamps, source hashes, destination hashes, and a verification flag.

Local manifests:

| Artifact | SHA-256 |
|---|---|
| `original-device-files-sha256.csv` | `b24374cafe57773c574613ddf656be05668f4e6375842f944a1a4a47f0dbdd4d` |
| `original-device-files-tree.txt` | `98b42531719a9f5555ce7133fb57e4bb99ce93e7cd70a7e2f46557cee3343d8e` |
| `original-device-files-summary.json` | `b646788e69a5e92603a103836d9ac98cabd90bbf7ca085e40705f5d4cc8ef694` |
| `file-category-summary.json` | `119d022a3cb79c52ec2a083db7bc06363a7de3f70be174ea414ba8ac618226e8` |
| `manifest-artifacts-sha256.csv` | `74b07f0ccecee15518738645f8667a77ef5c3dd1d673d3cd393178b24d4829ba` |

They are stored in `artifacts/manifests/`. The final index hashes every manifest except itself.

An additional read-only image of the complete normal-mode FAT volume was made
through `\\.\D:` using a source handle opened with `FileAccess.Read`. The image
is 20,807,680 bytes and has SHA-256
`256d1794be151fe435a0ef61eeb6dcbabdea8fc8e49029ef36199df94723087`.
Extracting it locally with 7-Zip independently reproduced all 204 file hashes
from the file-level backup. The image may contain deleted data and filesystem
slack, so it remains private under `artifacts/raw-device/`.

## Accessible-file classification

Classification was based on copied relative paths, extensions, and known Garmin directories. File contents were not opened for this step.

| Category | Files | Bytes | Assessment |
|---|---:|---:|---|
| Firmware/update packages | 0 | 0 | No `.GCD`/`.RGN`, `GUPDATE.GCD`, or `REMOTESW` package was present |
| Bootloader images | 0 | 0 | No accessible file identified as a bootloader |
| Resources / language / images | 24 | 2,814,957 | Present |
| Fonts | 0 | 0 | No standalone font file identified |
| Maps | 0 | 0 | No Garmin `.IMG`, map, or DEM file identified |
| Settings/configuration | 6 | 29,595 | Present, including device metadata |
| Logs / error reports | 3 | 96,307 | Present; contents were not included in documentation |
| Databases | 0 | 0 | No conventional database file identified |
| Activity and other potentially personal FIT data | 153 | 1,207,412 | Backed up locally; names and contents withheld |
| Other | 18 | 481,885 | Preserved for later offline classification |

The backup and its exact-path manifests may contain activity history, settings, identifiers, logs, and other private data. They must remain local and must not be published or sent to external analysis services.

## Limits of this inventory

- USB configuration and endpoint descriptors were not obtained; the interface assessment relies on Windows PnP class/compatible IDs.
- Hardware revision and bootloader version remain unknown.
- No diagnostic, recovery, test, preboot, ROM-loader, or forced-update mode was entered.
- No raw flash, hidden partition, bootloader region, MCU internal flash, sensor-hub firmware, or radio firmware was dumped.
- The backups contain only the normal FAT16 volume and the files it exposes;
  they do not contain K28 internal flash or hidden secondary storage regions.
