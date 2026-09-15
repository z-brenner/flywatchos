[CmdletBinding()]
param(
    [char]$DriveLetter = 'D',
    [string]$OutputPath = 'artifacts/raw-device/forerunner245-physical-disk.img'
)

$ErrorActionPreference = 'Stop'
$partition = Get-Partition -DriveLetter $DriveLetter
$disk = Get-Disk -Number $partition.DiskNumber
if ($disk.BusType -ne 'USB' -or $disk.FriendlyName -notlike 'Garmin FR245*') {
    throw "Refusing unexpected source disk: $($disk.FriendlyName), $($disk.BusType)"
}
if ($disk.Size -le 0 -or $disk.Size -gt 64MB) {
    throw "Refusing unexpected source size: $($disk.Size)"
}

$volume = Get-Volume -DriveLetter $DriveLetter
$output = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($output)) |
    Out-Null
$sourcePath = "\\.\${DriveLetter}:"
$source = [IO.File]::Open($sourcePath, [IO.FileMode]::Open,
    [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
try {
    $destination = [IO.File]::Open($output, [IO.FileMode]::Create,
        [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $buffer = New-Object byte[] (1MB)
        # The FAT boot sector declares the full exported disk size. Windows'
        # Volume.Size excludes filesystem overhead, so read the verified small
        # disk length through the read-only volume handle.
        [int64]$remaining = $disk.Size
        while ($remaining -gt 0) {
            $count = [Math]::Min([int64]$buffer.Length, $remaining)
            $read = $source.Read($buffer, 0, [int]$count)
            if ($read -le 0) { throw "Unexpected end of source with $remaining bytes remaining" }
            $destination.Write($buffer, 0, $read)
            $remaining -= $read
        }
        $destination.Flush()
    } finally {
        $destination.Dispose()
    }
} finally {
    $source.Dispose()
}

$item = Get-Item -LiteralPath $output
if ($item.Length -ne $disk.Size) { throw 'Raw image length does not match source disk' }
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $output
[ordered]@{
    source = 'sanitized Garmin FR245 USB raw volume'
    source_bytes = $disk.Size
    windows_volume_usable_bytes = $volume.Size
    physical_disk_bytes = $disk.Size
    partition_offset = $partition.Offset
    partition_bytes = $partition.Size
    filesystem = $volume.FileSystem
    output = $output
    sha256 = $hash.Hash.ToLowerInvariant()
    source_open_mode = 'FileAccess.Read'
} | ConvertTo-Json | Set-Content -LiteralPath "$output.json" -Encoding utf8
$hash
