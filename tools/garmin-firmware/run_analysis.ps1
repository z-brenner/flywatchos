[CmdletBinding()]
param(
    [string]$InputDirectory = "artifacts/firmware/originals",
    [string]$OutputDirectory = "artifacts/firmware/analysis"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-ChildItem -LiteralPath $InputDirectory -File -Filter "*.gcd" | ForEach-Object {
    $name = [IO.Path]::GetFileNameWithoutExtension($_.Name)
    & python (Join-Path $scriptDir "gcd_inspect.py") $_.FullName (Join-Path $OutputDirectory $name) --extract
    if ($LASTEXITCODE -ne 0) { throw "Analysis failed for $($_.FullName)" }
}
