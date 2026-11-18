<#
.SYNOPSIS
    Launches the unified multi-region Rogue Trip: Vacation 2012 Recompiled PC build.
    Supports FullRUS, Rus (SLUS-00643 60 Hz), and Europe (SLES-01417 50 Hz).

.EXAMPLE
    .\launch.ps1
    # Opens the GUI launcher with FullRUS, Rus, and Europe preloaded in the Disc dropdown.

.EXAMPLE
    .\launch.ps1 -Version FullRUS -DirectBoot
    .\launch.ps1 -Version Rus -DirectBoot
    .\launch.ps1 -Version Europe -DirectBoot
#>
param(
    [ValidateSet("", "FullRUS", "Rus", "Europe")]
    [string]$Version = "",
    [string]$Disc = "",
    [switch]$DebugBuild,
    [switch]$DirectBoot
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$GameFilesRoot = $env:ROGUETRIP_GAME_FILES
if (-not $GameFilesRoot) { $GameFilesRoot = Join-Path (Split-Path $RepoRoot -Parent) "_game_files" }
$env:ROGUETRIP_PROJECT_ROOT = $RepoRoot

$Candidates = if ($DebugBuild) {
    $env:PSXRECOMP_NO_FORWARD = "1"
    @("build-relwithdebinfo", "build-debug", "build-release", "build-setup")
} else {
    @("build-release", "build-relwithdebinfo", "build-setup")
}

$ExePath = $null
foreach ($dir in $Candidates) {
    $candidate = Join-Path $RepoRoot "$dir\Rogue_Trip_Recompiled.exe"
    if (Test-Path $candidate) {
        $ExePath = $candidate
        break
    }
}

if (-not $ExePath) {
    throw "No built executable found. Run .\build.ps1 first."
}

if (-not $Disc -and $Version) {
    $VersionMap = @{
        "FullRUS" = Join-Path $GameFilesRoot "Rogue Trip - Vacation 2012 (FullRUS)\Rogue Trip - Vacation 2012 (FullRUS).cue"
        "Rus"     = Join-Path $GameFilesRoot "Rogue Trip - Vacation 2012 (Rus)\Rogue Trip - Vacation 2012 (Rus).cue"
        "Europe"  = Join-Path $GameFilesRoot "Rogue Trip - Vacation 2012 (Europe)\Rogue Trip - Vacation 2012 (Europe).cue"
    }
    $Disc = $VersionMap[$Version]
}

$LaunchArgs = @("--game", (Join-Path $RepoRoot "game.toml"))
if (-not $DirectBoot) {
    $LaunchArgs += "--launcher"
}

if ($Disc) {
    if (-not (Test-Path -LiteralPath $Disc -PathType Leaf)) { throw "Disc not found: $Disc" }
    $LaunchArgs += @("--disc", (Resolve-Path -LiteralPath $Disc).Path)
}

Write-Host "[launch] Starting: $ExePath $($LaunchArgs -join ' ')" -ForegroundColor Green
& $ExePath @LaunchArgs
