[CmdletBinding()]
param(
    [string]$ToolchainRoot = 'tools/arm-toolchain/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi',
    [string]$PlacementEvidence = 'artifacts/analysis/fr245-1370-second-allocation.json'
)

$ErrorActionPreference = 'Stop'
$targetRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $targetRoot '../../..')).Path
$buildRoot = Join-Path $targetRoot 'build'
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
if (-not [IO.Path]::IsPathRooted($ToolchainRoot)) { $ToolchainRoot = Join-Path $repoRoot $ToolchainRoot }
if (-not [IO.Path]::IsPathRooted($PlacementEvidence)) { $PlacementEvidence = Join-Path $repoRoot $PlacementEvidence }

$placementHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PlacementEvidence).Hash.ToLowerInvariant()
$placement = Get-Content -Raw -LiteralPath $PlacementEvidence | ConvertFrom-Json
if ($placement.link_and_emulate_allowed -ne $true -or
    $placement.offline_interval.start -ne '0x001fa400' -or
    $placement.offline_interval.end -ne '0x001fabff' -or
    $placement.offline_interval.length -ne 2048 -or
    $placement.rtc_audit.read_audit_pass -ne $true) { throw 'Offline allocation/RTC gate is not satisfied' }
$imagePath = Join-Path $repoRoot 'artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin'
$imageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash.ToLowerInvariant()
if ($imageHash -ne $placement.image.sha256) { throw 'Pinned firmware image hash does not match placement evidence' }

$gcc = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-gcc.exe')).Path
$objcopy = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objcopy.exe')).Path
$objdump = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objdump.exe')).Path
$nm = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-nm.exe')).Path
$elf = Join-Path $buildRoot 'fr245-1370-neural-overlay.elf'
$map = Join-Path $buildRoot 'fr245-1370-neural-overlay.map'
$listing = Join-Path $buildRoot 'fr245-1370-neural-overlay.disassembly.txt'
$common = @('-mcpu=cortex-m4', '-mthumb', '-mfloat-abi=soft', '-Os', '-ffreestanding',
    '-fno-builtin', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
    '-ffunction-sections', '-fdata-sections', '-fstack-usage', '-Wall', '-Wextra', '-Werror',
    "-I$(Join-Path $repoRoot 'flyos')")
$sources = @((Join-Path $targetRoot 'hook.S'), (Join-Path $targetRoot 'overlay.c'),
    (Join-Path $repoRoot 'flyos/fly/brain32.c'), (Join-Path $repoRoot 'flyos/display/brain_ascii.c'))
$objects = @()
foreach ($source in $sources) {
    $object = Join-Path $buildRoot (([IO.Path]::GetFileNameWithoutExtension($source)) + '.o')
    & $gcc @common '-c' $source '-o' $object
    if ($LASTEXITCODE -ne 0) { throw "Compile failed: $source" }
    $objects += $object
}
& $gcc @common @objects '-nostdlib' '-Wl,--gc-sections' '-Wl,--no-undefined' "-Wl,-Map=$map" `
    "-T$(Join-Path $targetRoot 'linker.ld')" '-o' $elf
if ($LASTEXITCODE -ne 0) { throw 'Neural overlay link failed' }
& $objcopy '--dump-section' ".hook=$(Join-Path $buildRoot 'hook.bin')" `
    '--dump-section' ".primary=$(Join-Path $buildRoot 'primary.bin')" `
    '--dump-section' ".secondary=$(Join-Path $buildRoot 'secondary.bin')" $elf
if ($LASTEXITCODE -ne 0) { throw 'Section extraction failed' }
& $objdump '-d' '-s' $elf | Set-Content -LiteralPath $listing -Encoding ascii
if ($LASTEXITCODE -ne 0) { throw 'Disassembly failed' }
& $nm '-n' $elf | Set-Content -LiteralPath (Join-Path $buildRoot 'symbols.txt') -Encoding ascii
if ($LASTEXITCODE -ne 0) { throw 'Symbol extraction failed' }
$undefined = @(& $nm '-u' $elf)
if ($LASTEXITCODE -ne 0 -or $undefined.Count -ne 0) { throw "Undefined target symbols: $($undefined -join ', ')" }

& python '-B' (Join-Path $repoRoot 'tools/garmin-firmware/emulate_neural_overlay_payload.py') `
    '--check-build' $buildRoot '--placement' $PlacementEvidence '--expected-placement-sha256' $placementHash
if ($LASTEXITCODE -ne 0) { throw 'Linked placement, hook, or stack validation failed' }
Get-Content -LiteralPath (Join-Path $buildRoot 'SHA256SUMS.txt')
