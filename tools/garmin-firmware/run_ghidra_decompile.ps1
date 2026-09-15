[CmdletBinding()]
param(
    [string]$GhidraRoot = "tools/ghidra/ghidra_12.1.3_PUBLIC",
    [string]$ProjectRoot = "artifacts/firmware/ghidra-code",
    [string]$ProjectName = "FR245_310_CODE",
    [string]$ProgramName = "stream_01_fw_all_bin.bin",
    [string]$ReportPath = "artifacts/firmware/analysis/decompile-update-310.txt",
    [string[]]$Addresses = @(
        '0xa0474', '0xce154', '0xa0184', '0x9fdac', '0x9fd10',
        '0x10aecc', '0x10ab74'
    )
)

$ErrorActionPreference = "Stop"
$launcher = (Resolve-Path (Join-Path $GhidraRoot "support/analyzeHeadless.bat")).Path
$scriptPath = (Resolve-Path "tools/garmin-firmware/ghidra_scripts").Path
$projectPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $ProjectRoot))
$outputPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $ReportPath))
New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($outputPath)) |
    Out-Null

& $launcher $projectPath $ProjectName `
    -process $ProgramName `
    -noanalysis `
    -scriptPath $scriptPath `
    -postScript DecompileFunctions.java $outputPath $Addresses
if ($LASTEXITCODE -ne 0) {
    throw "Ghidra decompilation failed with exit code $LASTEXITCODE"
}
