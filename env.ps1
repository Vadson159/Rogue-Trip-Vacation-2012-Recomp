# Load the Windows build prerequisites for this checkout.
$RepoRoot = $PSScriptRoot
$WorkspaceRoot = Split-Path $RepoRoot -Parent
$GameFilesRoot = $env:ROGUETRIP_GAME_FILES
if (-not $GameFilesRoot) { $GameFilesRoot = Join-Path $WorkspaceRoot "_game_files" }

$TcDir = $env:PSXRECOMP_TOOLCHAIN_DIR
if (-not $TcDir) {
    $caches = @(
        (Join-Path $WorkspaceRoot "tools/cmake-clang-v1"),
        (Join-Path $env:LOCALAPPDATA "retcomm/toolchains/cmake-clang-v1")
    )
    foreach ($cache in $caches) {
        $pack = Get-ChildItem -LiteralPath $cache -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "bin/cmake.exe") } |
            Sort-Object Name -Descending | Select-Object -First 1
        if ($pack) {
            $TcDir = $pack.FullName
            break
        }
    }
}
if (-not $TcDir -or -not (Test-Path -LiteralPath (Join-Path $TcDir "bin/cmake.exe"))) {
    throw "Set PSXRECOMP_TOOLCHAIN_DIR to the extracted Windows cmake-clang-v1 package. See docs/DEVELOPING.md."
}
$env:PSXRECOMP_TOOLCHAIN_DIR = (Resolve-Path -LiteralPath $TcDir).Path
$env:ROGUETRIP_PROJECT_ROOT = $RepoRoot
$env:Path = "$(Join-Path $env:PSXRECOMP_TOOLCHAIN_DIR 'bin');$env:Path"

$GitExe = (Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$BashExe = Join-Path (Split-Path (Split-Path $GitExe -Parent) -Parent) "bin/bash.exe"
if (-not (Test-Path -LiteralPath $BashExe)) {
    throw "Use Git for Windows with its bundled Bash on the build machine."
}

$PyExe = $env:ROGUETRIP_PYTHON
if (-not $PyExe) {
    foreach ($venv in (Join-Path $RepoRoot ".venv"), (Join-Path $WorkspaceRoot ".venv")) {
        $candidate = Join-Path $venv "Scripts/python.exe"
        if (Test-Path -LiteralPath $candidate) {
            $PyExe = $candidate
            break
        }
    }
}
if (-not $PyExe) { $PyExe = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source }

$TinyCcDir = $env:ROGUETRIP_TCC_DIR
if (-not $TinyCcDir) { $TinyCcDir = Join-Path $WorkspaceRoot "tools/tcc" }
