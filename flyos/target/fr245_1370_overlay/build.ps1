[CmdletBinding()]
param(
    [string]$ToolchainRoot = "tools/arm-toolchain/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi"
)

$ErrorActionPreference = 'Stop'
$targetRoot = $PSScriptRoot
$buildRoot = Join-Path $targetRoot 'build'
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

$gcc = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-gcc.exe')).Path
$objcopy = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objcopy.exe')).Path
$objdump = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objdump.exe')).Path
$nm = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-nm.exe')).Path
$elf = Join-Path $buildRoot 'fr245-1370-overlay.elf'
$map = Join-Path $buildRoot 'fr245-1370-overlay.map'
$hook = Join-Path $buildRoot 'hook.bin'
$payload = Join-Path $buildRoot 'overlay.bin'
$listing = Join-Path $buildRoot 'fr245-1370-overlay.disassembly.txt'

$common = @(
    '-mcpu=cortex-m4', '-mthumb', '-mfloat-abi=soft', '-Os', '-ffreestanding',
    '-fno-builtin', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
    '-ffunction-sections', '-fdata-sections', '-Wall', '-Wextra', '-Werror'
)
& $gcc @common (Join-Path $targetRoot 'hook.S') (Join-Path $targetRoot 'overlay.c') `
    '-nostdlib' '-Wl,--gc-sections' "-Wl,-Map=$map" `
    "-T$(Join-Path $targetRoot 'linker.ld')" '-o' $elf
if ($LASTEXITCODE -ne 0) { throw 'Overlay link failed' }

& $objcopy '--dump-section' ".hook=$hook" '--dump-section' ".overlay=$payload" $elf
if ($LASTEXITCODE -ne 0) { throw 'Section extraction failed' }
& $objdump '-d' '-s' $elf | Set-Content -LiteralPath $listing -Encoding ascii
if ($LASTEXITCODE -ne 0) { throw 'Disassembly failed' }

$symbols = @(& $nm '-n' $elf)
if (-not ($symbols -match '^001f6000 T overlay_then_flush$')) {
    throw 'overlay_then_flush is not linked at 0x001f6000'
}
$undefined = @(& $nm '-u' $elf)
if ($undefined.Count -ne 0) {
    throw "Overlay has undefined symbols: $($undefined -join ', ')"
}
$hookBytes = [IO.File]::ReadAllBytes($hook)
$payloadBytes = [IO.File]::ReadAllBytes($payload)
if ($hookBytes.Length -ne 4) { throw 'Hook is not exactly four bytes' }
if ($payloadBytes.Length -gt 0x400) { throw 'Payload exceeds reserved cave allocation' }

Get-FileHash -Algorithm SHA256 -LiteralPath $elf, $hook, $payload, $listing
