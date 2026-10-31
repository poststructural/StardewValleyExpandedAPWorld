# Build the patched StardewArchipelago mod into artifacts/StardewArchipelago/
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GamePath,
    [string]$CacheRoot = (Join-Path $PSScriptRoot "..\.cache"),
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'
$lock = Get-Content -LiteralPath (Join-Path $PSScriptRoot "..\versions.lock") -Raw | ConvertFrom-Json
$project = Join-Path $CacheRoot 'stardew_archipelago\StardewArchipelago\StardewArchipelago.csproj'
if (-not (Test-Path $project)) { throw "missing $project - run scripts/fetch-upstream.ps1 first" }
if (-not (Test-Path (Join-Path $GamePath 'Stardew Valley.dll'))) { throw "GamePath does not look like a Stardew Valley install: $GamePath" }

$gameVersion = (Get-Item (Join-Path $GamePath 'Stardew Valley.dll')).VersionInfo.FileVersion
$expected = $lock.game.version
if ($gameVersion -notlike "$expected*") {
    Write-Warning "game build is $gameVersion but versions.lock pins $expected - build against the pinned version before shipping"
}

Write-Host "building $Configuration against $GamePath"
& dotnet build $project -c $Configuration "-p:GamePath=$GamePath" --nologo
if ($LASTEXITCODE -ne 0) { throw 'dotnet build failed' }

$binDir = Join-Path (Split-Path $project) "bin\$Configuration\net6.0"
if (-not (Test-Path (Join-Path $binDir 'StardewArchipelago.dll'))) { throw "build output not found in $binDir" }

$outDir = Join-Path $PSScriptRoot "..\artifacts\$($lock.artifacts.mod_dir)"
if (Test-Path $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Copy-Item -Path (Join-Path $binDir '*') -Destination $outDir -Recurse -Force

# BSD-3 requires the notice to travel with binary redistributions
$license = Join-Path $CacheRoot 'stardew_archipelago\LICENSE.md'
if (Test-Path $license) { Copy-Item -LiteralPath $license -Destination (Join-Path $outDir 'LICENSE.md') -Force }

$dll = Get-Item (Join-Path $outDir 'StardewArchipelago.dll')
Write-Host ("built {0} ({1:N0} KB, mod version {2})" -f $outDir, ($dll.Length / 1KB), (Get-Content (Join-Path $outDir 'manifest.json') -Raw | ConvertFrom-Json).Version)
