[CmdletBinding()]
param(
    [string]$GhidraRoot = "tools/ghidra/ghidra_12.1.3_PUBLIC",
    [string]$ProjectRoot = "artifacts/firmware/ghidra-dual",
    [int]$AnalysisTimeoutSeconds = 1800
)

$ErrorActionPreference = "Stop"
$launcher = (Resolve-Path (Join-Path $GhidraRoot "support/analyzeHeadless.bat")).Path
$scriptPath = (Resolve-Path "tools/garmin-firmware/ghidra_scripts").Path
$projectPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $ProjectRoot))
New-Item -ItemType Directory -Force -Path $projectPath | Out-Null

$images = @(
    @{ Project = "FR245_310_DUAL"; Image = "artifacts/firmware/analysis/Forerunner245_310/stream_01_fw_all_bin.bin" },
    @{ Project = "FR245_1370_DUAL"; Image = "artifacts/firmware/analysis/Forerunner245_1370_GUPDATE/stream_01_fw_all_bin.bin" }
)

foreach ($item in $images) {
    $imagePath = (Resolve-Path $item.Image).Path
    & $launcher $projectPath $item.Project `
        -import $imagePath `
        -overwrite `
        -processor "ARM:LE:32:Cortex" `
        -loader BinaryLoader `
        -loader-baseAddr 0x3000 `
        -loader-length 0x1fd000 `
        -preScript MapExternalSegment.java $imagePath 0x1fd000 0x04600000 `
        -preScript SeedCortexM.java 0x3000 124 `
        -scriptPath $scriptPath `
        -analysisTimeoutPerFile $AnalysisTimeoutSeconds `
        -log (Join-Path $projectPath "$($item.Project)-analysis.log") `
        -scriptlog (Join-Path $projectPath "$($item.Project)-scripts.log")
    if ($LASTEXITCODE -ne 0) { throw "Dual-map analysis failed for $($item.Image)" }
}
