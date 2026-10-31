# Fetch the upstream checkouts pinned in versions.lock into .cache/
[CmdletBinding()]
param([string]$CacheRoot = (Join-Path $PSScriptRoot "..\.cache"))

$ErrorActionPreference = 'Stop'
$lockPath = Join-Path $PSScriptRoot "..\versions.lock"
$lock = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null

function Invoke-Git {
    param([string[]]$Arguments)
    # schannel has no credentials in some sandboxed environments; openssl works.
    & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        & git -c http.sslBackend=openssl @Arguments 2>&1
    }
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed" }
}

function Sync-Upstream {
    param([string]$Name, [string]$Repo, [string]$Commit)

    $dir = Join-Path $CacheRoot $Name
    if (Test-Path (Join-Path $dir ".git")) {
        $head = (& git -C $dir rev-parse HEAD) 2>$null
        if ($head -eq $Commit) { Write-Host "[$Name] already at $Commit"; return }
    } else {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Invoke-Git @('-C', $dir, 'init', '--quiet') | Out-Null
        Invoke-Git @('-C', $dir, 'remote', 'add', 'origin', $Repo) 2>$null
    }

    Write-Host "[$Name] fetching $Commit"
    Invoke-Git @('-C', $dir, 'fetch', '--quiet', '--depth', '1', 'origin', $Commit) | Out-Null
    Invoke-Git @('-C', $dir, 'checkout', '--quiet', '--force', 'FETCH_HEAD') | Out-Null
    Write-Host "[$Name] at $((& git -C $dir rev-parse HEAD))"
}

$ap = $lock.upstream.archipelago
$sa = $lock.upstream.stardew_archipelago
Sync-Upstream -Name 'archipelago' -Repo $ap.repo -Commit $ap.commit
Sync-Upstream -Name 'stardew_archipelago' -Repo $sa.repo -Commit $sa.commit

Write-Host "`nDone. Sources are in $CacheRoot"
