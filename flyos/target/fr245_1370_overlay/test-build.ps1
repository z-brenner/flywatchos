$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'build.ps1') | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'build.ps1 returned a failure status' }

$buildRoot = Join-Path $PSScriptRoot 'build'
$hook = [IO.File]::ReadAllBytes((Join-Path $buildRoot 'hook.bin'))
$payload = [IO.File]::ReadAllBytes((Join-Path $buildRoot 'overlay.bin'))
if ($hook.Length -ne 4) { throw 'hook length changed' }
if ($payload.Length -eq 0 -or $payload.Length -gt 0x400) {
    throw 'payload length is outside the reserved cave allocation'
}

Write-Output 'overlay build assertions passed'
