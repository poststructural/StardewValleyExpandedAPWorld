# Package the patched world into artifacts/stardew_valley.apworld
[CmdletBinding()]
param([string]$CacheRoot = (Join-Path $PSScriptRoot "..\.cache"))

$ErrorActionPreference = 'Stop'
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\versions.lock") -Raw | ConvertFrom-Json
$worldName = 'stardew_valley'

$worldSrc = Join-Path $CacheRoot "archipelago\worlds\$worldName"
if (-not (Test-Path $worldSrc)) { throw "missing $worldSrc - run scripts/fetch-upstream.ps1 first" }

$stage = Join-Path $PSScriptRoot "..\artifacts\_stage"
$artifacts = Join-Path $PSScriptRoot "..\artifacts"
if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $stage $worldName) | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

Write-Host "staging patched world..."
Copy-Item -Path (Join-Path $worldSrc '*') -Destination (Join-Path $stage $worldName) -Recurse -Force

# do not ship caches or bytecode that happen to be lying around
Get-ChildItem -LiteralPath (Join-Path $stage $worldName) -Recurse -Directory -Include '__pycache__' -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

$apworld = Join-Path $artifacts $lock.artifacts.apworld
if (Test-Path $apworld) { Remove-Item -LiteralPath $apworld -Force }

Write-Host "zipping -> $apworld"
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    # python's zipfile keeps paths stable; PSCompression rewrites separators
    & $python.Source -c @"
import shutil, sys
shutil.make_archive(sys.argv[1], 'zip', sys.argv[2], sys.argv[3])
"@ (Join-Path $artifacts 'stardew_valley') (Join-Path $artifacts '_stage') $worldName
    Move-Item -LiteralPath (Join-Path $artifacts 'stardew_valley.zip') -Destination $apworld -Force
} else {
    Compress-Archive -Path (Join-Path $stage $worldName) -DestinationPath $apworld -Force
}

$size = (Get-Item $apworld).Length
Write-Host ("created {0} ({1:N0} KB)" -f $apworld, ($size / 1KB))
Write-Host "install it as a custom world, or drop it in lib/worlds to replace the built-in one."
