# install.ps1 - Windows installer for voice-dictation
#
# Run from an elevated PowerShell (Run as Administrator):
#
#   PS> Set-ExecutionPolicy -Scope Process Bypass
#   PS> .\windows\install.ps1
#
# Optional env overrides (set before invoking):
#   $env:WHISPER_MODEL    = 'medium'    # tiny/base/small/medium/large-v3
#   $env:WHISPER_DEVICE   = 'cuda'      # or 'cpu'
#   $env:WHISPER_COMPUTE  = 'float16'   # cpu: 'int8'

$ErrorActionPreference = 'Stop'

$RepoDir    = Split-Path -Parent $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA 'voice-dictation'
$VenvDir    = Join-Path $InstallDir 'venv'

$Model   = if ($env:WHISPER_MODEL)   { $env:WHISPER_MODEL }   else { 'medium' }
$Device  = if ($env:WHISPER_DEVICE)  { $env:WHISPER_DEVICE }  else { 'cuda' }
$Compute = if ($env:WHISPER_COMPUTE) { $env:WHISPER_COMPUTE } else { 'float16' }

Write-Host "==> Installing voice-dictation to $InstallDir (model=$Model device=$Device compute=$Compute)"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# winget lives in LocalAppData\Microsoft\WindowsApps which is NOT in PATH
# for elevated shells. Resolve it explicitly.
$_wcmd = Get-Command winget -ErrorAction SilentlyContinue
$WingetExe = if ($_wcmd) { $_wcmd.Source } else { $null }
if (-not $WingetExe) {
    foreach ($candidate in @(
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Microsoft\WindowsApps\winget.exe"
    )) {
        if (Test-Path $candidate) { $WingetExe = $candidate; break }
    }
}
if (-not $WingetExe) {
    throw "winget not found. Install 'App Installer' from the Microsoft Store and retry."
}
Write-Host "==> winget: $WingetExe"

function Require-Cmd($name, $wingetId) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "==> Installing $name via winget ($wingetId)"
        & $WingetExe install --silent --accept-source-agreements --accept-package-agreements --id $wingetId
        # Refresh PATH in this session so newly installed tools are visible.
        $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    }
}

Require-Cmd 'python'     'Python.Python.3.11'
Require-Cmd 'sox'        'ChrisBagwell.SoX'
Require-Cmd 'AutoHotkey' 'AutoHotkey.AutoHotkey'

# Copy sox.exe + its DLLs into InstallDir so voice-toggle.ahk finds them without
# PATH lookup. AHK does not inherit user PATH; sox also needs its bundled DLLs
# (libssp-0.dll, libgcc_s_sjlj-1.dll, etc.) in the same directory as sox.exe.
$_soxCmd = Get-Command sox -ErrorAction SilentlyContinue
if ($_soxCmd) {
    $_soxDir = Split-Path $_soxCmd.Source
    Copy-Item $_soxCmd.Source (Join-Path $InstallDir 'sox.exe') -Force
    Get-ChildItem $_soxDir -Filter '*.dll' | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $InstallDir $_.Name) -Force
    }
    Write-Host "==> Copied sox.exe + DLLs to $InstallDir"
} else {
    Write-Warning "sox not found in PATH after install - voice-toggle.ahk may fail. Re-run installer from a fresh shell."
}

if (-not (Test-Path (Join-Path $VenvDir 'Scripts\python.exe'))) {
    Write-Host "==> Creating venv"
    python -m venv $VenvDir
}
$VenvPy  = Join-Path $VenvDir 'Scripts\python.exe'
$VenvPip = Join-Path $VenvDir 'Scripts\pip.exe'

Write-Host "==> Installing Python dependencies"
& $VenvPip install --upgrade pip wheel | Out-Null
& $VenvPip install -r (Join-Path $RepoDir 'requirements.txt')

if ($Device -eq 'cuda') {
    Write-Host "==> Installing CUDA runtime DLLs (cuDNN + cuBLAS for CUDA 12)"
    & $VenvPip install nvidia-cudnn-cu12 nvidia-cublas-cu12
}

Write-Host "==> Copying scripts"
Copy-Item (Join-Path $RepoDir 'transcribe.py')            (Join-Path $InstallDir 'transcribe.py')        -Force
Copy-Item (Join-Path $RepoDir 'transcribe_server.py')     (Join-Path $InstallDir 'transcribe_server.py') -Force
Copy-Item (Join-Path $RepoDir 'transcribe_client.py')     (Join-Path $InstallDir 'transcribe_client.py') -Force
Copy-Item (Join-Path $RepoDir 'windows\voice-toggle.ahk') (Join-Path $InstallDir 'voice-toggle.ahk')     -Force

# Batch launcher — sets env vars and starts the server.
$LauncherBat = Join-Path $InstallDir 'start-server.bat'
@"
@echo off
set WHISPER_MODEL=$Model
set WHISPER_DEVICE=$Device
set WHISPER_COMPUTE=$Compute
"$VenvPy" "$InstallDir\transcribe_server.py"
"@ | Set-Content -Encoding ASCII $LauncherBat

Write-Host "==> Registering scheduled task VoiceDictationServer (run at logon)"
$TaskName = 'VoiceDictationServer'
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
schtasks /Create /TN $TaskName /SC ONLOGON /RL HIGHEST /RU "$env:USERDOMAIN\$env:USERNAME" /TR "`"$LauncherBat`"" /F | Out-Null
schtasks /Run /TN $TaskName | Out-Null

Write-Host "==> Adding AutoHotkey script to startup (per-user)"

# Get-Command may not find AutoHotkey immediately after winget installs it in
# the same session. Fall back to known install locations.
$_ahkcmd = Get-Command AutoHotkey -ErrorAction SilentlyContinue
$AhkExe = if ($_ahkcmd) { $_ahkcmd.Source } else { $null }
if (-not $AhkExe) {
    foreach ($candidate in @(
        "${env:ProgramFiles}\AutoHotkey\v2\AutoHotkey64.exe",
        "${env:ProgramFiles}\AutoHotkey\v2\AutoHotkey.exe",
        "${env:ProgramFiles}\AutoHotkey\AutoHotkey.exe",
        "${env:ProgramFiles(x86)}\AutoHotkey\v2\AutoHotkey.exe",
        "${env:ProgramFiles(x86)}\AutoHotkey\AutoHotkey.exe"
    )) {
        if (Test-Path $candidate) { $AhkExe = $candidate; break }
    }
}
if (-not $AhkExe) { throw "AutoHotkey not found after installation. Check winget output above." }

$StartupDir   = [Environment]::GetFolderPath('Startup')
$AhkTarget    = Join-Path $InstallDir 'voice-toggle.ahk'
$ShortcutPath = Join-Path $StartupDir 'voice-toggle.lnk'
$WScript  = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $AhkExe
$Shortcut.Arguments        = "`"$AhkTarget`""
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

# Launch immediately so the hotkey is live without a reboot.
Start-Process $AhkExe -ArgumentList "`"$AhkTarget`""

Write-Host ""
Write-Host "==> Done. Model: $Model | Device: $Device | Compute: $Compute"
Write-Host "Hotkey  : Ctrl+Alt+V (toggle record/transcribe)"
Write-Host "Task    : VoiceDictationServer (Task Scheduler)"
Write-Host "Install : $InstallDir"
