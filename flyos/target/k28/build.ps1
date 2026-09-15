[CmdletBinding()]
param(
    [string]$ToolchainRoot = "tools/arm-toolchain/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi"
)

$ErrorActionPreference = 'Stop'
$gcc = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-gcc.exe')).Path
$objcopy = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objcopy.exe')).Path
$objdump = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-objdump.exe')).Path
$nm = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-nm.exe')).Path
$size = (Resolve-Path (Join-Path $ToolchainRoot 'bin/arm-none-eabi-size.exe')).Path
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$build = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null

$common = @(
    '-mcpu=cortex-m4', '-mthumb', '-mfloat-abi=soft', '-std=c11', '-Os',
    '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
    '-Wall', '-Wextra', '-Werror', "-I$root"
)
$sources = @(
    (Join-Path $PSScriptRoot 'startup.c'),
    (Join-Path $PSScriptRoot 'runtime.c'),
    (Join-Path $PSScriptRoot 'main.c'),
    (Join-Path $root 'fly/network.c'),
    (Join-Path $root 'display/garmin_row_packer.c')
)
$elf = Join-Path $build 'flyos-k28.elf'
$binary = Join-Path $build 'flyos-k28.bin'
$map = Join-Path $build 'flyos-k28.map'
$listing = Join-Path $build 'flyos-k28.disassembly.txt'

& $gcc @common @sources '-nostdlib' '-Wl,--gc-sections' "-Wl,-Map=$map" `
    "-T$PSScriptRoot/linker.ld" '-o' $elf
if ($LASTEXITCODE -ne 0) { throw 'Target link failed' }
& $objcopy '-O' 'binary' $elf $binary
if ($LASTEXITCODE -ne 0) { throw 'Target binary conversion failed' }
& $objdump '-d' '-S' $elf | Set-Content -LiteralPath $listing -Encoding ascii
$undefined = @(& $nm '-u' $elf)
if ($undefined.Count -ne 0) { throw "Target contains undefined symbols: $undefined" }

$bytes = [IO.File]::ReadAllBytes($binary)
if ($bytes.Length -lt 0x1f0) { throw 'Target binary is shorter than its vector table' }
$initialStack = [BitConverter]::ToUInt32($bytes, 0)
$resetVector = [BitConverter]::ToUInt32($bytes, 4)
if ($initialStack -ne 0x2002e000) {
    throw ('Unexpected initial stack: 0x{0:x8}' -f $initialStack)
}
if ($resetVector -ne 0x000031f1) {
    throw ('Unexpected reset vector: 0x{0:x8}' -f $resetVector)
}

& $size $elf
$hashes = Get-FileHash -Algorithm SHA256 -LiteralPath $elf, $binary
$manifest = [ordered]@{
    target = 'NXP Kinetis K28F / Cortex-M4 structural skeleton'
    flash_origin = '0x00003000'
    initial_stack = ('0x{0:x8}' -f $initialStack)
    reset_vector = ('0x{0:x8}' -f $resetVector)
    binary_length = $bytes.Length
    elf_sha256 = $hashes[0].Hash.ToLowerInvariant()
    binary_sha256 = $hashes[1].Hash.ToLowerInvariant()
    installable = $false
    ram_only_display_stage = 'verified 240-byte row to 244-byte Garmin staging-row converter'
    missing_drivers = @('clock','watchdog','power','display-transport','buttons','storage','update-wrapper')
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $build 'manifest.json') -Encoding utf8
$hashes
