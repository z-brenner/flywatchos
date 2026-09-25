[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,

    [string]$GhidraRoot = '',

    [int]$AnalysisTimeoutSeconds = 1800
)

$ErrorActionPreference = 'Stop'

# Collision refusal comes first so an occupied evidence directory is never
# affected by dependency or input validation.
if (Test-Path -LiteralPath $OutputRoot) {
    throw "output collision: $OutputRoot already exists"
}

if ([string]::IsNullOrWhiteSpace($GhidraRoot)) {
    $GhidraRoot = Join-Path $PSScriptRoot '..\ghidra\ghidra_12.1.3_PUBLIC'
}

$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$image = Join-Path $repository 'artifacts\firmware\analysis\Forerunner245_1370_GUPDATE\stream_01_fw_all_bin.bin'
$launcher = Join-Path ([IO.Path]::GetFullPath($GhidraRoot)) 'support\analyzeHeadless.bat'
$scriptDirectory = Join-Path $PSScriptRoot 'ghidra_scripts'

if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    throw "analyzeHeadless.bat not found: $launcher"
}
if (-not (Test-Path -LiteralPath $image -PathType Leaf)) {
    throw "pinned firmware image not found: $image"
}

$output = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $output | Out-Null
$project = Join-Path $output 'ghidra-project'
New-Item -ItemType Directory -Path $project | Out-Null
$inventory = Join-Path $output 'ghidra-inventory.json'
$decompilation = Join-Path $output 'decompilation.txt'
$headlessLog = Join-Path $output 'headless.log'
$scriptLog = Join-Path $output 'script.log'

& $launcher $project 'FR245_1370_STANDALONE_RESET_CONTRACT' `
    -import $image `
    -processor 'ARM:LE:32:Cortex' `
    -loader BinaryLoader `
    -loader-baseAddr 0x3000 `
    -loader-length 0x1fd000 `
    -scriptPath $scriptDirectory `
    -preScript SeedCortexM.java 0x3000 124 `
    -preScript SeedThumbFunctions.java 0x19340 `
    -analysisTimeoutPerFile $AnalysisTimeoutSeconds `
    -postScript K28ResetContractReport.java $inventory $decompilation 0x19340 3 `
    -log $headlessLog `
    -scriptlog $scriptLog

if ($LASTEXITCODE -ne 0) {
    throw "Ghidra analysis failed with exit code $LASTEXITCODE"
}

$required = @($inventory, $decompilation, $headlessLog, $scriptLog)
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($missing.Count -ne 0) {
    throw "missing evidence output: $($missing -join ', ')"
}

$logs = (Get-Content -Raw -LiteralPath $headlessLog) + "`n" + (Get-Content -Raw -LiteralPath $scriptLog)
if ($logs -match '(?i)SCRIPT ERROR|post-script|output collision') {
    throw 'Ghidra log reports a post-script error or output collision'
}

Write-Output $output
