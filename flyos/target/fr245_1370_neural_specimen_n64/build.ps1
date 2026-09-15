[CmdletBinding()]
param([string]$BuildRoot = '', [string]$EvidenceRoot = '')
$ErrorActionPreference='Stop'
$target=$PSScriptRoot
$root=(Resolve-Path (Join-Path $target '../../..')).Path
$build=if($BuildRoot){[IO.Path]::GetFullPath($BuildRoot)}else{Join-Path $target 'build'}
New-Item -ItemType Directory -Force $build | Out-Null
$tc=Join-Path $root 'tools/arm-toolchain/arm-gnu-toolchain-15.2.rel1-mingw-w64-i686-arm-none-eabi/bin'
$gcc=Join-Path $tc 'arm-none-eabi-gcc.exe'; $objcopy=Join-Path $tc 'arm-none-eabi-objcopy.exe'
$objdump=Join-Path $tc 'arm-none-eabi-objdump.exe'; $nm=Join-Path $tc 'arm-none-eabi-nm.exe'
& python -B (Join-Path $root 'tools/garmin-firmware/emulate_neural_specimen_n64.py') --check-evidence
if($LASTEXITCODE){throw 'pinned evidence gate failed'}
$common=@('-mcpu=cortex-m4','-mthumb','-mfloat-abi=soft','-Os','-ffreestanding','-fno-builtin',
 '-fno-unwind-tables','-fno-asynchronous-unwind-tables','-ffunction-sections','-fdata-sections',
 '-fstack-usage','-Wall','-Wextra','-Werror',"-I$(Join-Path $root 'flyos')")
$sources=@((Join-Path $target 'hook.S'),(Join-Path $target 'overlay.c'),
 (Join-Path $target 'renderer.c'),(Join-Path $root 'flyos/fly/brain64.c'))
$objects=@()
foreach($s in $sources){$o=Join-Path $build (([IO.Path]::GetFileNameWithoutExtension($s))+'.o'); & $gcc @common -c $s -o $o; if($LASTEXITCODE){throw "compile failed: $s"};$objects+=$o}
$elf=Join-Path $build 'fr245-1370-neural-specimen-n64.elf';$map=Join-Path $build 'fr245-1370-neural-specimen-n64.map'
& $gcc @common @objects -nostdlib '-Wl,--gc-sections' '-Wl,--no-undefined' "-Wl,-Map=$map" "-T$(Join-Path $target 'linker.ld')" -o $elf
if($LASTEXITCODE){throw 'link failed'}
(Get-Content $map -Raw).Replace($build,'<BUILD>') | Set-Content $map -Encoding ascii -NoNewline
& $objcopy --dump-section ".hook=$(Join-Path $build 'hook.bin')" --dump-section ".primary=$(Join-Path $build 'primary.bin')" --dump-section ".secondary=$(Join-Path $build 'secondary.bin')" $elf
if($LASTEXITCODE){throw 'extract failed'}
((& $objdump -d -s $elf) -join "`n").Replace($build,'<BUILD>') + "`n" | Set-Content (Join-Path $build 'fr245-1370-neural-specimen-n64.disassembly.txt') -Encoding ascii -NoNewline
& $nm -n $elf | Set-Content (Join-Path $build 'symbols.txt') -Encoding ascii
if(@(& $nm -u $elf).Count){throw 'undefined symbols'}
& python -B (Join-Path $root 'tools/garmin-firmware/emulate_neural_specimen_n64.py') --check-build $build
if($LASTEXITCODE){throw 'offline N64 build gate failed'}
if($EvidenceRoot){
 & python -B (Join-Path $root 'tools/garmin-firmware/emulate_neural_specimen_n64.py') --build $build --publish-evidence $EvidenceRoot
 if($LASTEXITCODE){throw 'offline N64 evidence generation failed'}
}
Get-Content (Join-Path $build 'SHA256SUMS.txt')
