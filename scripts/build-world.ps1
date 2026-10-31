# Package the patched world into artifacts/stardew_valley.apworld
[CmdletBinding()]
param([string]$CacheRoot = (Join-Path $PSScriptRoot "..\.cache"))

$ErrorActionPreference = 'Stop'
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\versions.lock") -Raw | ConvertFrom-Json

function Invoke-Robocopy {
    param([string]$Source, [string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy $Source $Destination /MIR /NFL /NDL /NJH /NJS /NP /R:1 /W:1 | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $Source -> $Destination (exit $LASTEXITCODE)" }
}
$worldName = 'stardew_valley'

$worldSrc = Join-Path $CacheRoot "archipelago\worlds\$worldName"
if (-not (Test-Path $worldSrc)) { throw "missing $worldSrc - run scripts/fetch-upstream.ps1 first" }

$stage = Join-Path $PSScriptRoot "..\artifacts\_stage"
$artifacts = Join-Path $PSScriptRoot "..\artifacts"
if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $stage $worldName) | Out-Null
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

Write-Host "staging patched world..."
# copy the directory itself, not its wildcard contents: Copy-Item -Path "dir\*" silently drops subdirectories
Invoke-Robocopy $worldSrc (Join-Path $stage $worldName)

# do not ship caches or bytecode that happen to be lying around.
# NB: use -Filter, not -Include: with -Recurse, -Include without -Filter matches every directory and the
# Remove-Item below would delete the whole tree.
Get-ChildItem -LiteralPath (Join-Path $stage $worldName) -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
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
