#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Cut a new maildigger release.
.DESCRIPTION
  Bumps version in pyproject.toml and src/maildigger/__init__.py,
  commits, tags, and pushes. The tag push triggers .github/workflows/release.yml,
  which builds and publishes to PyPI via trusted publishing.
.PARAMETER Version
  The new version (e.g. "0.1.1"). No leading "v".
.PARAMETER Force
  Skip the interactive confirmation prompt.
.EXAMPLE
  ./scripts/release.ps1 0.1.1
.EXAMPLE
  ./scripts/release.ps1 0.2.0 -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($Version -notmatch '^\d+\.\d+\.\d+([-.][A-Za-z0-9.-]+)?$') {
    throw "Version '$Version' doesn't look like semver (e.g. 0.1.1 or 0.1.1-rc.1)"
}

$tag = "v$Version"
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    $branch = git rev-parse --abbrev-ref HEAD
    if ($branch -ne "main") { throw "Not on main (current: $branch)" }

    $dirty = git status --porcelain
    if ($dirty) { throw "Working tree is dirty:`n$dirty" }

    git fetch origin | Out-Null
    $local = git rev-parse HEAD
    $remote = git rev-parse origin/main
    if ($local -ne $remote) { throw "Local main is out of sync with origin/main" }

    if (git tag --list $tag) { throw "Tag $tag already exists" }

    $pyproject = "pyproject.toml"
    $init = "src/maildigger/__init__.py"

    (Get-Content $pyproject -Raw) -replace '(?m)^version = "[^"]+"', "version = `"$Version`"" `
        | Set-Content $pyproject -NoNewline
    (Get-Content $init -Raw) -replace '__version__ = "[^"]+"', "__version__ = `"$Version`"" `
        | Set-Content $init -NoNewline

    Write-Host "`nVersion bump:" -ForegroundColor Cyan
    git --no-pager diff $pyproject $init

    if (-not $Force) {
        $confirm = Read-Host "`nCommit, tag $tag, and push? [y/N]"
        if ($confirm -ne "y" -and $confirm -ne "Y") {
            Write-Host "Aborting. Reverting files." -ForegroundColor Yellow
            git checkout -- $pyproject $init
            exit 1
        }
    }

    git add $pyproject $init
    git commit -m "Release $tag"
    git tag -a $tag -m "Release $tag"
    git push origin main
    git push origin $tag

    Write-Host "`nReleased $tag" -ForegroundColor Green
    Write-Host "Actions: https://github.com/kotsaris/maildigger/actions"
    Write-Host "PyPI:    https://pypi.org/project/maildigger/"
}
finally {
    Pop-Location
}
