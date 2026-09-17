# Windows PowerShell 5.1+. START.bat supplies a process-only policy bypass.
# This script never changes persistent execution policy or requests elevation.
[CmdletBinding()]
param([switch]$Headless, [switch]$SetupPython, [switch]$NoPause)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:Stage = 'BOOTSTRAP'
$script:ExitCode = 1
$script:Log = $null
$script:Secrets = @()
$script:LastDiagnostic = ''
$root = Split-Path -Parent $PSScriptRoot
$mark = 'ASTRA' + [char]::ConvertFromUtf32(0x1F4E1) + [char]::ConvertFromUtf32(0x1F30C)
$check = 'Check logs\astra_startup.log and the last startup stage.'
function Protect-Text([string]$Text) {
    foreach ($secret in $script:Secrets) {
        if ($secret.Length -ge 4) { $Text = $Text.Replace($secret, '[REDACTED]') }
    }
    $Text = $Text -replace '(?i)(https?://)[^\s/@]+:[^\s/@]+@', '$1[REDACTED]@'
    $Text = $Text -replace '(?i)(sb_secret_|sb_publishable_)[A-Za-z0-9_-]+', '[REDACTED]'
    $Text = $Text -replace 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED JWT]'
    $Text = $Text -replace '(?i)((?:password|secret|token|api_key|service_role|authorization)\s*[:=]\s*)\S+', '$1[REDACTED]'
    return $Text
}
function Say([string]$Text) {
    $safe = Protect-Text $Text
    Write-Host "[$mark] $safe"
    if ($script:Log) { Add-Content -LiteralPath $script:Log -Encoding UTF8 -Value "$(Get-Date -Format o) [$script:Stage] $safe" }
}
function Find-Tool([string]$Name) {
    # Never search the working directory for a tool; reject project-local PATH entries.
    $tools = @(Get-Command $Name -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($tool in $tools) {
        if (-not $tool.Source.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { return $tool.Source }
    }
    return $null
}
function Test-NativePE([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $stream = [IO.File]::OpenRead($Path)
    $reader = New-Object IO.BinaryReader($stream)
    try {
        if ($stream.Length -lt 256 -or $reader.ReadUInt16() -ne 0x5A4D) { return $false }
        $stream.Position = 60
        $offset = $reader.ReadUInt32()
        if ($offset -gt ($stream.Length - 26)) { return $false }
        $stream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x4550) { return $false }
        $machine = $reader.ReadUInt16()
        $stream.Position = $offset + 22
        $flags = $reader.ReadUInt16()
        return ($machine -eq 0x8664 -and ($flags -band 2) -ne 0 -and ($flags -band 0x2000) -eq 0)
    } finally { $reader.Dispose(); $stream.Dispose() }
}
function Run-Tool([string]$Exe, [string[]]$Arguments) {
    # PowerShell call operator passes arguments, never evaluates a command string.
    $savedPreference = $ErrorActionPreference
    try {
        # PS 5.1 represents redirected native stderr as ErrorRecord objects.
        $ErrorActionPreference = 'Continue'
        & $Exe @Arguments 2>&1 | ForEach-Object { Say ([string]$_) }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($code -ne 0) { $script:ExitCode = $code; throw "Dependency command failed with exit code $code." }
}
try {
    [Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
    Write-Host "============================================================`n                         $mark`n                     ASTRA COSMOS`n              Scientific Universe Simulator`n============================================================"
    if ($env:OS -ne 'Windows_NT') { throw 'This bootstrapper requires Windows.' }
    Set-Location -LiteralPath $root
    # Collect sensitive values before any diagnostic output. Never source .env as code.
    Get-ChildItem Env: | Where-Object { $_.Name -match '(?i)key|secret|token|password|credential|supabase' } | ForEach-Object { $script:Secrets += $_.Value }
    $envFile = Join-Path $root '.env'
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in [IO.File]::ReadAllLines($envFile)) {
            if ($line -match '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*(.*)$') { $script:Secrets += $Matches[1].Trim().Trim('"').Trim("'") }
        }
    }
    $logDir = Join-Path $root 'logs'
    [IO.Directory]::CreateDirectory($logDir) | Out-Null
    $script:Log = Join-Path $logDir 'astra_startup.log'
    Say 'Initializing...'
    Say 'PowerShell bootstrap started.'
    Say 'Checking dependencies...'
    $script:Stage = 'SYSTEM'
    Say "Checking system... Windows $([Environment]::OSVersion.VersionString); project root: $root"
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) { throw 'Use 64-bit Windows and 64-bit PowerShell for the x64 renderer.' }
    $script:Stage = 'CONFIGURATION'
    Say 'Checking configuration...'
    $check = 'Restore the tracked native_renderer source, shaders and assets from this checkout.'
    foreach ($required in @('native_renderer/CMakeLists.txt', 'native_renderer/src/main.cpp', 'native_renderer/shaders/common/common.glsl', 'native_renderer/assets', 'pyproject.toml')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $required))) { throw "Required project file/directory missing: $required" }
    }
    if (Test-Path -LiteralPath $envFile) {
        Say '.env found; values are not printed or executed. Native runtime does not consume Supabase configuration.'
        $number = 0
        foreach ($line in [IO.File]::ReadAllLines($envFile)) {
            $number++
            if ($line.Trim() -and $line -notmatch '^\s*#' -and $line -notmatch '^\s*(export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=') {
                Say "WARNING: .env line $number is not a KEY=value assignment. Correct it before using the optional Python product layer."
            }
        }
    } else { Say '.env absent: local native simulation remains available. Optional accounts require ASTRA_SUPABASE_URL and ASTRA_SUPABASE_PUBLISHABLE_KEY; see .env.example.' }
    $script:Stage = 'PYTHON'
    Say 'Checking Python... Native astra_native has no Python dependency.'
    if ($SetupPython) {
        $check = 'Install Python 3.9+ from python.org, then retry -SetupPython. Check pip output for the declared dependency failure.'
        $python = $null
        foreach ($folder in @('.venv', 'venv')) {
            $candidate = Join-Path $root "$folder\Scripts\python.exe"
            if (Test-Path -LiteralPath $candidate) { $python = $candidate; break }
        }
        if (-not $python) {
            $base = Find-Tool 'python.exe'
            if (-not $base) { throw 'Python missing. Automatic interpreter installation is not attempted.' }
            Run-Tool $base @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)')
            Run-Tool $base @('-m', 'venv', (Join-Path $root '.venv'))
            $python = Join-Path $root '.venv\Scripts\python.exe'
        }
        Say "Environment used: $python"
        Run-Tool $python @('--version')
        Run-Tool $python @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,9) and sys.prefix != sys.base_prefix else 1)')
        Say 'Checking dependencies declared in pyproject.toml...'
        & $python (Join-Path $PSScriptRoot 'check_python_dependencies.py')
        $depsCode = $LASTEXITCODE
        if ($depsCode -ne 0) {
            Say 'Declared dependencies missing or changed. Installing project into its virtual environment...'
            Run-Tool $python @('-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple', '-e', $root)
            Run-Tool $python @((Join-Path $PSScriptRoot 'check_python_dependencies.py'))
        } else { Say 'Declared dependencies OK; no installation needed.' }
        Run-Tool $python @('-m', 'pip', 'check')
    } else { Say 'Python packages skipped (optional product/developer layer); use -SetupPython to prepare them.' }
    $script:Stage = 'NATIVE_RENDERER'
    Say 'Checking native renderer...'
    $check = 'Install CMake 3.28+ and a C++20 Windows toolchain (Visual Studio C++ Build Tools), or provide a trusted x64 astra_native.exe built from this source.'
    $candidates = @('native_renderer/build-windows/Release/astra_native.exe', 'native_renderer/build-windows/astra_native.exe', 'native_renderer/build/Release/astra_native.exe', 'native_renderer/build/Debug/astra_native.exe', 'native_renderer/build/astra_native.exe', 'build/Release/astra_native.exe', 'build/astra_native.exe', 'native_renderer/astra_native.exe', 'release/ASTRA-COSMOS/bin/astra_native.exe')
    $native = $null
    foreach ($relative in $candidates) {
        $candidate = Join-Path $root $relative
        if (Test-NativePE $candidate) { $native = $candidate; break }
        if (Test-Path -LiteralPath $candidate) { Say "Rejected non-x64-PE renderer: $relative" }
    }
    if (-not $native) {
        Say 'Windows native renderer missing. The packaged extensionless Linux artifact is not usable on Windows.'
        $cmake = Find-Tool 'cmake.exe'
        if (-not $cmake) { throw 'CMake missing; cannot build astra_native.exe automatically.' }
        Say 'Building existing astra_native CMake target (no downloads, no legacy EXE launcher)...'
        $build = Join-Path $root 'native_renderer/build-windows'
        Run-Tool $cmake @('-S', (Join-Path $root 'native_renderer'), '-B', $build, '-DCMAKE_BUILD_TYPE=Release', '-DASTRA_BUILD_LAUNCHER=OFF', '-DASTRA_BUILD_TESTS=OFF', '-DASTRA_BUILD_TOOLS=OFF')
        Run-Tool $cmake @('--build', $build, '--config', 'Release', '--target', 'astra_native', '--parallel', '2')
        foreach ($relative in $candidates[0..1]) { $candidate = Join-Path $root $relative; if (Test-NativePE $candidate) { $native = $candidate; break } }
        if (-not $native) { throw 'Build produced no valid x64 Windows astra_native.exe.' }
    }
    Say "Native renderer artifact: $native (PE format checked, not a signature/trust guarantee)."
    $script:Stage = 'VULKAN_CHECK'
    Say 'Checking Vulkan runtime/loader (not headers)...'
    $loader = Join-Path ([Environment]::SystemDirectory) 'vulkan-1.dll'
    if (-not (Test-Path -LiteralPath $loader)) {
        Say 'WARNING: Vulkan runtime not detected. Install/update the official GPU vendor driver; the Vulkan SDK headers are not a runtime.'
        Say 'Normal native entry point will still be attempted; no headless option is silently added.'
    } else {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AstraLoaderProbe {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);
    [DllImport("kernel32.dll")]
    public static extern bool FreeLibrary(IntPtr module);
}
'@
        # Absolute System32 path; dependencies restricted to System32 too.
        $handle = [AstraLoaderProbe]::LoadLibraryEx($loader, [IntPtr]::Zero, 0x800)
        if ($handle -eq [IntPtr]::Zero) {
            $loaderError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            Say "WARNING: Vulkan loader could not load; Win32 error $loaderError. Repair the official GPU driver installation."
        } else {
            [AstraLoaderProbe]::FreeLibrary($handle) | Out-Null
            Say 'System Vulkan loader loaded successfully. Driver/device initialization and GPU rendering NOT VERIFIED.'
        }
    }
    Say 'WARNING: Current VulkanRHI uses mock devices and main.cpp has a finite diagnostic loop. Its output cannot establish GPU initialization or ASTRA_READY.'
    $script:Stage = 'PREPARING_RUNTIME'
    Say 'Preparing runtime... Working directory is the project root for native_renderer/shaders paths.'
    $check = 'Inspect the native stdout/stderr below and logs\astra_startup.log. A zero-code finite diagnostic exit is not a running GUI. Missing DLL errors require the official toolchain runtime, not downloaded DLLs.'
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $native
    $info.WorkingDirectory = $root
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.CreateNoWindow = $true
    if ($Headless) { $info.Arguments = '--headless' }
    Say "Launching ASTRA... Command: `"$native`" $($info.Arguments)"
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    if (-not $process.Start()) { throw 'Native process could not be created.' }
    $script:Stage = 'PROCESS_CREATED'
    Say "PROCESS_CREATED PID=$($process.Id); runtime/renderer/Vulkan readiness not established."
    # Drain both streams concurrently, without raw unredacted log files or pipe deadlocks.
    $outTask = $process.StandardOutput.ReadLineAsync()
    $errTask = $process.StandardError.ReadLineAsync()
    while ($null -ne $outTask -or $null -ne $errTask -or -not $process.HasExited) {
        foreach ($streamName in @('out', 'err')) {
            $task = if ($streamName -eq 'out') { $outTask } else { $errTask }
            if ($null -ne $task -and $task.IsCompleted) {
                $line = $task.GetAwaiter().GetResult()
                $next = $null
                if ($null -ne $line) {
                    if ($line -match '^\[Instance\]') { $script:Stage = 'VULKAN_INITIALIZATION_OUTPUT_UNVERIFIED' }
                    if ($line -match '^\[ASTRA Native\]') { $script:Stage = 'NATIVE_RUNTIME_OUTPUT' }
                    if ($streamName -eq 'err' -or $line -match '(?i)fail|error') { $script:LastDiagnostic = Protect-Text $line }
                    Say "${streamName}: $line"
                    $reader = if ($streamName -eq 'out') { $process.StandardOutput } else { $process.StandardError }
                    $next = $reader.ReadLineAsync()
                }
                if ($streamName -eq 'out') { $outTask = $next } else { $errTask = $next }
            }
        }
        Start-Sleep -Milliseconds 20
    }
    $process.WaitForExit()
    $script:ExitCode = $process.ExitCode
    $hex = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$script:ExitCode), 0).ToString('X8')
    Say "ASTRA process exited. Exit code: $script:ExitCode (0x$hex). Last startup stage: $script:Stage"
    $process.Dispose()
    if ($script:ExitCode -ne 0) { throw "Native renderer exited with code $script:ExitCode. Last diagnostic: $script:LastDiagnostic" }
    if (-not $Headless) { throw 'Native process exited with code 0 without establishing a persistent application or renderer readiness. Current source is a finite diagnostic runtime, not a verified running GUI.' }
    Say 'Explicit headless diagnostic process completed with code 0. GPU and application readiness NOT VERIFIED.'
} catch {
    Write-Host "============================================================`n$mark STARTUP FAILED`n============================================================"
    Say "Error: $($_.Exception.Message)"
    Say "Exit code: $script:ExitCode (native code when a child exited; otherwise bootstrap code). Last startup stage: $script:Stage"
    Say "Check: $check"
    # Preserve a native zero exit in diagnostics, but fail the bootstrap if readiness failed.
    if ($script:ExitCode -eq 0) { $script:ExitCode = 1 }
} finally {
    if (-not $NoPause) { Read-Host 'Press ENTER to close (START.bat keeps PowerShell available; type exit to close it)' | Out-Null }
}
exit $script:ExitCode
