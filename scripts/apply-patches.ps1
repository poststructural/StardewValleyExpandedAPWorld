# Apply patches/<half>/*.patch onto the matching .cache/ checkout.
[CmdletBinding()]
param(
    [string]$CacheRoot = (Join-Path $PSScriptRoot "..\.cache"),
    [switch]$Reverse,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$patchRoot = Join-Path $PSScriptRoot "..\patches"

$targets = @(
    @{ Half = 'world'; Dir = (Join-Path $CacheRoot 'archipelago') },
    @{ Half = 'mod';   Dir = (Join-Path $CacheRoot 'stardew_archipelago') }
)

$applied = 0
foreach ($target in $targets) {
    $patchDir = Join-Path $patchRoot $target.Half
    if (-not (Test-Path $patchDir)) { continue }
    $patches = Get-ChildItem -LiteralPath $patchDir -Filter '*.patch' | Sort-Object Name
    if (-not $patches) { continue }
    if (-not (Test-Path $target.Dir)) { throw "missing checkout for '$($target.Half)': run scripts/fetch-upstream.ps1 first" }

    foreach ($patch in $patches) {
        $args = @('-C', $target.Dir, 'apply', '--whitespace=nowarn')
        if ($Reverse) { $args += '--reverse' }
        if ($Check) { $args += '--check' }
        $args += $patch.FullName

        & git @args
        if ($LASTEXITCODE -ne 0) {
            # already applied is not an error for our purposes
            $alreadyArgs = @('-C', $target.Dir, 'apply', '--reverse', '--check', $patch.FullName)
            & git @alreadyArgs 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[$($target.Half)] $( $patch.Name ) already applied, skipping"
                continue
            }
            throw "failed to apply $($patch.Name) to $($target.Dir)"
        }
        Write-Host "[$($target.Half)] applied $($patch.Name)"
        $applied++
    }
}

Write-Host "`n$applied patch(es) applied$(if ($Check) { ' (check only)' } else { '' })."
