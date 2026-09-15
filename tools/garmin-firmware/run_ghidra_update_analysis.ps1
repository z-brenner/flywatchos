param(
    [Parameter(Mandatory = $true)]
    [string]$GhidraHome,

    [Parameter(Mandatory = $true)]
    [string]$FirmwareImage,

    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $true)]
    [string]$ReportPath,

    [ValidateSet('3.10', '13.70')]
    [string]$ImageVersion,

    [string]$ProjectDirectory = "$PSScriptRoot\..\..\artifacts\firmware\ghidra-code"
)

$ErrorActionPreference = 'Stop'
$headless = Join-Path $GhidraHome 'support\analyzeHeadless.bat'
if (-not (Test-Path -LiteralPath $headless)) {
    throw "analyzeHeadless.bat not found under $GhidraHome"
}
if (-not (Test-Path -LiteralPath $FirmwareImage)) {
    throw "firmware image not found: $FirmwareImage"
}

$projectDirectory = [IO.Path]::GetFullPath($ProjectDirectory)
$reportPath = [IO.Path]::GetFullPath($ReportPath)
$scriptDirectory = Join-Path $PSScriptRoot 'ghidra_scripts'
if (-not $ImageVersion) {
    if ($ProjectName -match '1370') { $ImageVersion = '13.70' }
    elseif ($ProjectName -match '310') { $ImageVersion = '3.10' }
    else { throw 'Specify -ImageVersion when ProjectName does not contain 310 or 1370' }
}
New-Item -ItemType Directory -Force -Path $projectDirectory | Out-Null
New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($reportPath)) | Out-Null

# The extracted fw_all file is immutable input.  All Ghidra state and reports
# are written under artifacts/firmware.
& $headless $projectDirectory $ProjectName `
    -import ([IO.Path]::GetFullPath($FirmwareImage)) `
    -loader BinaryLoader `
    -loader-baseAddr 0x3000 `
    -loader-length 0x1fd000 `
    -processor 'ARM:LE:32:Cortex' `
    -overwrite `
    -scriptPath $scriptDirectory `
    -preScript SeedCortexM.java 0x3000 128 `
    -analysisTimeoutPerFile 600 `
    -postScript ExportUpdateEvidence.java $reportPath $ImageVersion
if ($LASTEXITCODE -ne 0) {
    throw "Ghidra analysis failed with exit code $LASTEXITCODE"
}
