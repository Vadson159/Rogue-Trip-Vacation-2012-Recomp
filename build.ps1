<#
.SYNOPSIS
    Builds the Windows runtime with NTSC-U and PAL backends, or the setup host.
.EXAMPLE
    .\build.ps1 -UsDisc 'D:\discs\US.cue' -EuropeDisc 'D:\discs\Europe.cue'
#>
param(
    [ValidateSet("Release", "RelWithDebInfo", "Debug")]
    [string]$BuildType = "Release",
    [switch]$SetupHost,
    [string]$UsDisc,
    [string]$EuropeDisc,
    [ValidateRange(1, 1024)]
    [int]$Jobs = [Environment]::ProcessorCount
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "env.ps1")

$TcDir = $env:PSXRECOMP_TOOLCHAIN_DIR
$CMakeExe = Join-Path $TcDir "bin/cmake.exe"
$ClangC = (Join-Path $TcDir "bin/clang.exe") -replace '\\','/'
$ClangCXX = (Join-Path $TcDir "bin/clang++.exe") -replace '\\','/'

if (-not $SetupHost) {
    if (-not $UsDisc) {
        foreach ($version in "FullRUS", "Rus", "USA") {
            $stem = "Rogue Trip - Vacation 2012 ($version)"
            $candidate = Join-Path $GameFilesRoot "$stem/$stem.cue"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $UsDisc = $candidate
                break
            }
        }
    }
    if (-not $EuropeDisc) {
        $stem = "Rogue Trip - Vacation 2012 (Europe)"
        $EuropeDisc = Join-Path $GameFilesRoot "$stem/$stem.cue"
    }
    if (-not $UsDisc -or -not (Test-Path -LiteralPath $UsDisc -PathType Leaf)) {
        throw "Pass an NTSC-U CUE with -UsDisc (SLUS-00643)."
    }
    if (-not (Test-Path -LiteralPath $EuropeDisc -PathType Leaf)) {
        throw "Pass a PAL CUE with -EuropeDisc (SLES-01417)."
    }
    $UsDisc = (Resolve-Path -LiteralPath $UsDisc).Path
    $EuropeDisc = (Resolve-Path -LiteralPath $EuropeDisc).Path
}

Push-Location $RepoRoot
try {
    # Apply the project patches to the pinned dependencies.
    & $BashExe scripts/apply-patches.sh
    if ($LASTEXITCODE -ne 0) { throw "Failed to apply dependency patches" }

    # 2. Build/refresh PSXRecomp emitters & analyzer
    Write-Host "[build] Ensuring PSXRecomp emitters & analyzer are up to date..." -ForegroundColor Yellow
    if (-not (Test-Path "psxrecomp\recompiler\build\build.ninja")) {
        & $CMakeExe -S psxrecomp/recompiler -B psxrecomp/recompiler/build -G Ninja `
            "-DCMAKE_BUILD_TYPE=Release" `
            "-DCMAKE_C_COMPILER=$ClangC" `
            "-DCMAKE_CXX_COMPILER=$ClangCXX" `
            "-DPSXRECOMP_STATIC_CLI=ON"
        if ($LASTEXITCODE -ne 0) { throw "Recompiler CMake configure failed" }
    }
    & $CMakeExe --build psxrecomp/recompiler/build -j $Jobs
    if ($LASTEXITCODE -ne 0) { throw "Recompiler build failed" }

    # 3. Ensure OpenBIOS C backend exists
    if (-not (Test-Path "psxrecomp\generated\OpenBIOS_full.c")) {
        Write-Host "[build] Generating OpenBIOS C backend..." -ForegroundColor Yellow
        Push-Location (Join-Path $RepoRoot "psxrecomp")
        try {
            & $BashExe tools/regen_bios.sh --config bios/OpenBIOS.toml
            if ($LASTEXITCODE -ne 0) { throw "OpenBIOS generation failed" }
        } finally {
            Pop-Location
        }
    }

    if ($SetupHost) {
        Write-Host "[build] Building standalone Windows Setup Host (build-setup)..." -ForegroundColor Yellow
        & $CMakeExe -S . -B build-setup -G Ninja -DCMAKE_BUILD_TYPE=Release `
            -DCMAKE_C_COMPILER="$ClangC" `
            -DCMAKE_CXX_COMPILER="$ClangCXX" `
            -DPSXRECOMP_FORCE_SETUP_HOST=ON `
            -DPSXRECOMP_ALLOW_NO_BIOS=ON `
            -DPSX_SETUP_WIZARD=ON `
            -DPSX_DEBUG_TOOLS=OFF
        if ($LASTEXITCODE -ne 0) { throw "Setup-host configure failed" }
        & $CMakeExe --build build-setup --target psx-runtime -j $Jobs
        if ($LASTEXITCODE -ne 0) { throw "Setup-host build failed" }
        Write-Host "[build] Setup Host ready: $(Join-Path $RepoRoot 'build-setup\Rogue_Trip_Recompiled.exe')" -ForegroundColor Green
        return
    }

    # Read the boot executable from each disc's ISO filesystem.
    & $PyExe scripts/prepare_regions.py --us-disc $UsDisc --europe-disc $EuropeDisc
    if ($LASTEXITCODE -ne 0) { throw "Boot EXE extraction failed" }

    # Emit NTSC-U and PAL C shards from the selected discs.
    $RecompGame = Join-Path $RepoRoot "psxrecomp\recompiler\build\psxrecomp-game.exe"
    Set-Content -Path "disc\emit_us.toml" -Encoding utf8NoBOM -Value @"
[game]
name = "Rogue Trip - Vacation 2012 (US/RUS)"
id = "SLUS-00643"
players = 2
exe = "disc/SLUS_006.43"
load_address = "0x800EFA20"
entry_pc = "0x801549B0"
text_size = "0x000D4000"
stack_base = "0x801FFFF0"

[recompiler]
seeds = "seeds/ghidra_funcs.txt"
out_dir = "generated/us"
strict = true
"@
    Write-Host "[build] Emitting SLUS_006.43 (FullRUS + Rus) C shards..." -ForegroundColor Yellow
    & $RecompGame --config "disc\emit_us.toml"
    if ($LASTEXITCODE -ne 0) { throw "SLUS_006.43 codegen failed" }

    Set-Content -Path "disc\emit_eu.toml" -Encoding utf8NoBOM -Value @"
[game]
name = "Rogue Trip - Vacation 2012 (Europe)"
id = "SLES-01417"
players = 2
exe = "disc/SLES_014.17"
load_address = "0x800EFA20"
entry_pc = "0x801547B4"
text_size = "0x000D4000"
stack_base = "0x801FFFF0"

[recompiler]
seeds = "seeds/ghidra_funcs_eu.txt"
out_dir = "generated/eu"
strict = true
"@
    Write-Host "[build] Emitting SLES_014.17 (Europe) C shards..." -ForegroundColor Yellow
    & $RecompGame --config "disc\emit_eu.toml"
    if ($LASTEXITCODE -ne 0) { throw "SLES_014.17 codegen failed" }

    # Generate symbol namespace headers (rt_us_* and rt_eu_*)
    $RemapScript = Join-Path $RepoRoot "scripts\gen_sym_remap.py"
    & $PyExe $RemapScript --gen-dir "generated\us" --prefix "rt_us_" --out "generated\us_remap.h"
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate us_remap.h" }
    & $PyExe $RemapScript --gen-dir "generated\eu" --prefix "rt_eu_" --out "generated\eu_remap.h"
    if ($LASTEXITCODE -ne 0) { throw "Failed to generate eu_remap.h" }

    # Configure & build unified multi-region Windows executable
    $OutBuildDir = if ($BuildType -eq "Release") { "build-release" } else { "build-$($BuildType.ToLower())" }
    $DebugFlag   = if ($BuildType -eq "Release") { "OFF" } else { "ON" }
    $Version = (Get-Content -Raw VERSION).Trim()

    Write-Host "[build] Compiling unified multi-region Windows PC build ($BuildType -> $OutBuildDir)..." -ForegroundColor Yellow
    & $CMakeExe -S . -B $OutBuildDir -G Ninja `
        "-DCMAKE_BUILD_TYPE=$BuildType" `
        "-DCMAKE_C_COMPILER=$ClangC" `
        "-DCMAKE_CXX_COMPILER=$ClangCXX" `
        "-DPSX_DEBUG_TOOLS=$DebugFlag" `
        "-DPSX_STATIC_RUNTIME=ON" `
        "-DPSX_GAME_VERSION=$Version"
    if ($LASTEXITCODE -ne 0) { throw "Unified runtime CMake configure failed" }

    & $CMakeExe --build $OutBuildDir --target psx-runtime -j $Jobs
    if ($LASTEXITCODE -ne 0) { throw "Unified runtime build failed" }

    # Fix relative _game_files path in staged build-dir game.toml for direct Explorer launches
    $StagedToml = Join-Path $RepoRoot "$OutBuildDir\game.toml"
    if (Test-Path $StagedToml) {
        $rawToml = Get-Content -LiteralPath $StagedToml -Raw
        $fixedToml = $rawToml -replace '"\.\./_game_files/', '"../../_game_files/'
        Set-Content -LiteralPath $StagedToml -Value $fixedToml -Encoding utf8NoBOM -NoNewline
    }

    # Stage self-contained overlay_toolchain beside the exe (embedded Python + TinyCC + recompiler + headers)
    $OutFullDir = Join-Path $RepoRoot $OutBuildDir
    $TkDir = Join-Path $OutFullDir "overlay_toolchain"
    New-Item -ItemType Directory -Force (Join-Path $TkDir "include"), (Join-Path $TkDir "bios") | Out-Null
    if (-not (Test-Path (Join-Path $TkDir "python\python.exe"))) {
        Write-Host "[build] Staging overlay_toolchain beside executable for automatic overlay native compilation..." -ForegroundColor Yellow
        if (Test-Path (Join-Path $TcDir "python")) {
            Copy-Item -Recurse -Force (Join-Path $TcDir "python") (Join-Path $TkDir "python")
        }
    }
    if ((Test-Path -LiteralPath $TinyCcDir) -and -not (Test-Path (Join-Path $TkDir "tcc"))) {
        Copy-Item -Recurse -Force $TinyCcDir (Join-Path $TkDir "tcc")
    }
    Copy-Item -Force $RecompGame (Join-Path $TkDir "psxrecomp-game.exe")
    $MingwRuntimeBin = Join-Path $TcDir "x86_64-w64-mingw32\bin"
    foreach ($rtDll in @("libc++.dll", "libunwind.dll", "libwinpthread-1.dll")) {
        $srcDll = Join-Path $MingwRuntimeBin $rtDll
        if (Test-Path $srcDll) {
            Copy-Item -Force $srcDll (Join-Path $TkDir $rtDll)
        }
    }
    Copy-Item -Force "psxrecomp\tools\compile_overlays.py" (Join-Path $TkDir "compile_overlays.py")
    Get-ChildItem "psxrecomp\runtime\include\*" -Include "*.h", "*.c.inc" | Copy-Item -Force -Destination (Join-Path $TkDir "include")
    Copy-Item -Force "psxrecomp\bios\SCPH1001.toml", "psxrecomp\bios\OpenBIOS.toml" -Destination (Join-Path $TkDir "bios")

    # Compile and stage the AOT overlay cache for this build.
    & $PyExe scripts/build_overlay_cache.py --us-disc $UsDisc --europe-disc $EuropeDisc --build-dir $OutFullDir --jobs $Jobs
    if ($LASTEXITCODE -ne 0) { throw "Overlay AOT cache build failed" }

    $FinalExe = Join-Path $OutFullDir "Rogue_Trip_Recompiled.exe"
    Write-Host "[build] SUCCESS! Unified Multi-Region PC executable ready: $FinalExe" -ForegroundColor Green
} finally {
    Pop-Location
}
