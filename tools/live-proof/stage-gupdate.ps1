[CmdletBinding()]
param(
    [ValidateSet('Candidate1369', 'ForwardOverlay1371', 'ForwardRestore1372', 'FullscreenOverlay1372', 'FullscreenRestore1373', 'NeuralSpecimenN64Overlay1374', 'NeuralSpecimenN64Restore1375')]
    [string]$Mode = 'Candidate1369',
    [ValidatePattern('^[A-Z]$')]
    [string]$DriveLetter = 'D',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'

# Explicit denylist for offline Task 5 artifacts. These entries are intentionally
# not staging profiles, so a future live write requires a fresh deliberate change.
$BlockedN64Artifacts = @{
    NeuralSpecimenN64Overlay1374 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1374-flyos-neural-specimen-n64.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = '3A4A4AF6355C132571C1158667CC43C96BF5DA7A67737AB028267930E71134CD'
    }
    NeuralSpecimenN64Restore1375 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1375-official-payload-restore-n64.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = 'CCD2A29C51A41A436111239C7181E1CB0CEA1F2FAC1C48D600FFF6DEC103E5DA'
    }
}
if ($BlockedN64Artifacts.ContainsKey($Mode)) {
    $blocked = $BlockedN64Artifacts[$Mode]
    throw "N64 artifact is explicitly blocked from live staging: mode=$Mode source=$($blocked.Source) sha256=$($blocked.Sha256)"
}

$profiles = @{
    Candidate1369 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1369-matched-fly-visible.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = 'D89D52CA82586D7CEA003C2F5B65B854790B572246164064FE3DF079FA36CA2F'
        ExpectedReportedVersion = '1040'
        Description = 'matched 13.69 resource-only visible proof'
    }
    ForwardOverlay1371 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1371-flyos-scientific-fly-overlay.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = '1F7DE5EC5EA224EF337C3934E0F7EBC1445F0C6C7B8CB4201180CBEB1772A469'
        ExpectedReportedVersion = '1370'
        Description = 'synthetic 13.71 normal-forward scientific-fly executable overlay'
    }
    ForwardRestore1372 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1372-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = 'F0A6B316CAB5F941125CBE896E6E260196BC0BA4A02F5B475FA55DE241522EB1'
        ExpectedReportedVersion = '1370'
        Description = 'synthetic 13.72 normal-forward wrapper carrying official 13.70 executable payload'
    }
    FullscreenOverlay1372 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1372-flyos-fullscreen-overlay.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = '6394FD73CC3E7A5660A6FE9CDE3CC0B6617C21F8A24F2B6319B328882D662713'
        ExpectedReportedVersion = '1370'
        Description = 'synthetic 13.72 normal-forward button-enabled full-screen FlyOS overlay'
    }
    FullscreenRestore1373 = @{
        Source = 'artifacts\firmware\quarantine\Forerunner245_1373-official-payload-restore.gcd.analysis-only.DO_NOT_INSTALL'
        Sha256 = '869D62AB829AC7B75A079EFFD4D7D0B1E71A5E8A0D1C7D2C94FA686D907AA4E6'
        ExpectedReportedVersion = '1370'
        Description = 'synthetic 13.73 normal-forward wrapper carrying official 13.70 executable code and resources'
    }
}

# Audit every enabled profile against the denylist before resolving paths,
# opening package files, or querying a device.  This prevents a future alias
# profile from enabling the same artifact under a different mode key.
$blockedSources = @($BlockedN64Artifacts.Values | ForEach-Object { $_.Source.ToLowerInvariant().Replace('/', '\') })
$blockedNames = @($BlockedN64Artifacts.Values | ForEach-Object { [IO.Path]::GetFileName($_.Source).ToLowerInvariant() })
$blockedHashes = @($BlockedN64Artifacts.Values | ForEach-Object { $_.Sha256.ToUpperInvariant() })
foreach ($entry in $profiles.GetEnumerator()) {
    $entrySource = $entry.Value.Source.ToLowerInvariant().Replace('/', '\')
    $entryName = [IO.Path]::GetFileName($entry.Value.Source).ToLowerInvariant()
    $entryHash = $entry.Value.Sha256.ToUpperInvariant()
    if (
        $BlockedN64Artifacts.ContainsKey([string]$entry.Key) -or
        $blockedSources -contains $entrySource -or
        $blockedNames -contains $entryName -or
        $blockedHashes -contains $entryHash
    ) {
        throw "N64 artifact is explicitly blocked from live staging: enabled profile alias=$($entry.Key) source=$($entry.Value.Source) sha256=$($entry.Value.Sha256)"
    }
}

$profile = $profiles[$Mode]
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$sourcePath = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $profile.Source))
$volumeRoot = "$DriveLetter`:\"
$garminDirectory = Join-Path $volumeRoot 'Garmin'
$deviceXmlPath = Join-Path $garminDirectory 'GarminDevice.xml'
$destinationPath = Join-Path $garminDirectory 'GUPDATE.GCD'
$temporaryPath = Join-Path $garminDirectory 'GUPDATE.GCD.flyos.tmp'

if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Pinned source artifact is absent: $sourcePath"
}
$source = Get-Item -LiteralPath $sourcePath
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sourcePath).Hash
if ($sourceHash -ne $profile.Sha256) {
    throw "Pinned source hash mismatch: $sourceHash"
}

$volume = Get-Volume -DriveLetter $DriveLetter -ErrorAction Stop
if ($volume.FileSystemLabel -ne 'GARMIN' -or $volume.FileSystem -ne 'FAT') {
    throw "Drive $DriveLetter is not the expected GARMIN FAT volume"
}
if ($volume.HealthStatus -ne 'Healthy') {
    throw "GARMIN volume health is $($volume.HealthStatus)"
}

$logicalDeviceId = "$DriveLetter`:"
$logicalDisks = @(Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$logicalDeviceId'" -ErrorAction Stop)
if ($logicalDisks.Count -ne 1) {
    throw "Expected exactly one logical disk for $logicalDeviceId, found $($logicalDisks.Count)"
}
$partitions = @(Get-CimAssociatedInstance -InputObject $logicalDisks[0] -Association Win32_LogicalDiskToPartition -ErrorAction Stop)
if ($partitions.Count -ne 1) {
    throw "Expected exactly one partition for $logicalDeviceId, found $($partitions.Count)"
}
$physicalDisks = @(
    $partitions |
        ForEach-Object { Get-CimAssociatedInstance -InputObject $_ -Association Win32_DiskDriveToDiskPartition -ErrorAction Stop } |
        Sort-Object -Property DeviceID -Unique
)
if ($physicalDisks.Count -ne 1) {
    throw "Expected exactly one physical disk for $logicalDeviceId, found $($physicalDisks.Count)"
}
$physicalDisk = $physicalDisks[0]
if ($physicalDisk.InterfaceType -ne 'USB' -or $physicalDisk.Model -ne 'Garmin FR245 Flash USB Device') {
    throw "Drive $DriveLetter is not the expected Garmin FR245 USB disk"
}
if ($physicalDisk.PNPDeviceID -notmatch '^USBSTOR\\DISK&VEN_GARMIN&PROD_FR245_FLASH&REV_[^\\]+\\') {
    throw "Unexpected Garmin disk PNP identity: $($physicalDisk.PNPDeviceID)"
}
$diskPnpNode = Get-PnpDevice -PresentOnly -InstanceId $physicalDisk.PNPDeviceID -ErrorAction Stop
if ($diskPnpNode.Status -ne 'OK') {
    throw "Garmin disk PNP status is $($diskPnpNode.Status)"
}
$parentProperty = Get-PnpDeviceProperty -InstanceId $physicalDisk.PNPDeviceID -KeyName 'DEVPKEY_Device_Parent' -ErrorAction Stop
$usbParentId = [string]$parentProperty.Data
if ($usbParentId -notmatch '^USB\\VID_091E&PID_2C04\\') {
    throw "Unexpected Garmin USB parent identity: $usbParentId"
}
$usbParentNode = Get-PnpDevice -PresentOnly -InstanceId $usbParentId -ErrorAction Stop
if ($usbParentNode.Status -ne 'OK') {
    throw "Garmin USB parent PNP status is $($usbParentNode.Status)"
}

if (-not (Test-Path -LiteralPath $deviceXmlPath -PathType Leaf)) {
    throw 'GarminDevice.xml is absent'
}
if (Test-Path -LiteralPath $destinationPath) {
    throw "Refusing to replace existing $destinationPath"
}
if (Test-Path -LiteralPath $temporaryPath) {
    throw "Refusing to replace existing $temporaryPath"
}
if ($volume.SizeRemaining -lt ($source.Length + 1MB)) {
    throw 'Insufficient free space with 1 MiB safety margin'
}

[xml]$deviceXml = Get-Content -LiteralPath $deviceXmlPath -Raw
$modelNode = $deviceXml.SelectSingleNode("//*[local-name()='Model']")
$descriptionNode = $modelNode.SelectSingleNode("./*[local-name()='Description']")
$partNumberNode = $modelNode.SelectSingleNode("./*[local-name()='PartNumber']")
$softwareNode = $modelNode.SelectSingleNode("./*[local-name()='SoftwareVersion']")
if ($descriptionNode.InnerText -ne 'Forerunner 245') {
    throw "Unexpected model: $($descriptionNode.InnerText)"
}
if ($partNumberNode.InnerText -ne '006-B3076-00') {
    throw "Unexpected part number: $($partNumberNode.InnerText)"
}
if ($softwareNode.InnerText -ne $profile.ExpectedReportedVersion) {
    throw "Expected reported software $($profile.ExpectedReportedVersion), found $($softwareNode.InnerText)"
}

$plan = [ordered]@{
    mode = $Mode
    description = $profile.Description
    source = $sourcePath
    source_size = $source.Length
    source_sha256 = $sourceHash
    destination = $destinationPath
    destination_exists = $false
    device_model = $descriptionNode.InnerText
    device_part_number = $partNumberNode.InnerText
    device_software = $softwareNode.InnerText
    volume_label = $volume.FileSystemLabel
    volume_filesystem = $volume.FileSystem
    volume_health = $volume.HealthStatus
    physical_disk_model = $physicalDisk.Model
    physical_disk_pnp_id = $physicalDisk.PNPDeviceID
    usb_parent_pnp_id = $usbParentId
    execute = [bool]$Execute
}
$plan | ConvertTo-Json

if (-not $Execute) {
    Write-Host 'DRY RUN ONLY: no watch file was created or changed.'
    exit 0
}

$temporaryCreated = $false
$destinationCreated = $false
try {
    $inputStream = [IO.File]::Open($sourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $outputStream = [IO.File]::Open($temporaryPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $temporaryCreated = $true
        try {
            $inputStream.CopyTo($outputStream, 1MB)
            $outputStream.Flush($true)
        }
        finally {
            $outputStream.Dispose()
        }
    }
    finally {
        $inputStream.Dispose()
    }

    $temporary = Get-Item -LiteralPath $temporaryPath
    $temporaryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $temporaryPath).Hash
    if ($temporary.Length -ne $source.Length -or $temporaryHash -ne $sourceHash) {
        throw 'Temporary copy size or SHA-256 verification failed'
    }

    [IO.File]::Move($temporaryPath, $destinationPath)
    $temporaryCreated = $false
    $destinationCreated = $true

    $destination = Get-Item -LiteralPath $destinationPath
    $destinationHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $destinationPath).Hash
    if ($destination.Length -ne $source.Length -or $destinationHash -ne $sourceHash) {
        throw 'Final destination size or SHA-256 verification failed'
    }
}
catch {
    $stagingError = $_
    if ($temporaryCreated -or $destinationCreated) {
        try {
            if (-not (Test-Path -LiteralPath $volumeRoot -PathType Container)) {
                throw 'GARMIN volume is unavailable, so cleanup cannot be confirmed'
            }
            if (Test-Path -LiteralPath $destinationPath) {
                Remove-Item -LiteralPath $destinationPath -Force
            }
            if (Test-Path -LiteralPath $temporaryPath) {
                Remove-Item -LiteralPath $temporaryPath -Force
            }
            if ((Test-Path -LiteralPath $destinationPath) -or (Test-Path -LiteralPath $temporaryPath)) {
                throw 'newly created staging file still exists after cleanup'
            }
        }
        catch {
            throw "Staging failed and cleanup could not be confirmed. Original error: $($stagingError.Exception.Message) Cleanup error: $($_.Exception.Message)"
        }
        throw "Staging failed; the newly created destination is absent after cleanup. Cause: $($stagingError.Exception.Message)"
    }
    throw
}

Write-Host "STAGED AND VERIFIED: $destinationPath"
Write-Host "SHA-256: $destinationHash"
Write-Host 'The script does not eject the volume, restart the watch, or accept an on-watch update prompt.'
