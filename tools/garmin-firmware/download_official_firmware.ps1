[CmdletBinding()]
param(
    [string]$Destination = "artifacts/firmware/originals",
    [string]$Manifest = "artifacts/firmware/manifest.json"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sources = Get-Content -Raw -LiteralPath (Join-Path $scriptDir "firmware-sources.json") |
    ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $Destination | Out-Null

$result = foreach ($source in $sources) {
    $target = Join-Path $Destination $source.filename
    if (-not (Test-Path -LiteralPath $target)) {
        $temporary = "$target.partial"
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
        & curl.exe -fL --retry 3 --remote-time --output $temporary $source.url
        if ($LASTEXITCODE -ne 0) { throw "Download failed: $($source.url)" }
        Move-Item -LiteralPath $temporary -Destination $target
    }

    $item = Get-Item -LiteralPath $target
    if ($item.Length -ne $source.expected_size) {
        throw "Size mismatch for $($source.filename): $($item.Length)"
    }
    $md5 = (Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLowerInvariant()
    if ($source.expected_md5 -and $md5 -ne $source.expected_md5) {
        throw "Garmin catalog MD5 mismatch for $($source.filename)"
    }
    $sha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    [ordered]@{
        filename = $source.filename
        component = $source.component
        variant = $source.variant
        part_number = $source.part_number
        version = $source.version
        source = $source.url
        size = $item.Length
        md5 = $md5
        garmin_catalog_md5_validated = [bool]$source.expected_md5
        sha256 = $sha256
        last_write_time_utc = $item.LastWriteTimeUtc.ToString("o")
        matches_connected_backup = [bool]$source.matches_connected_backup
    }
}

$manifestParent = Split-Path -Parent $Manifest
if ($manifestParent) { New-Item -ItemType Directory -Force -Path $manifestParent | Out-Null }
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Manifest -Encoding utf8
$result | ForEach-Object { "$($_.sha256) *$($_.filename)" } |
    Set-Content -LiteralPath (Join-Path (Split-Path -Parent $Manifest) "SHA256SUMS") -Encoding ascii
$result
