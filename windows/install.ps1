# install.ps1 - Windows installer for voice-dictation
#
# Run from an elevated PowerShell (Run as Administrator) so it can install
# SoX/AutoHotkey via winget and register a per-user scheduled task.
#
#   PS> Set-ExecutionPolicy -Scope Process Bypass
#   PS> .\install.ps1
#
# Optional environment overrides (set before invoking):
#   $env:WHISPER_MODEL    = 'small'     # tiny/base/small/medium/large-v3
#   $env:WHISPER_DEVICE   = 'cuda'      # or 'cpu'
#   $env:WHISPER_COMPUTE  = 'float16'   # cpu: 'int8'

$ErrorActionPreference = 'Stop'

$RepoDir    = Split-Path -Parent $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA 'voice-dictation'
$VenvDir    = Join-Path $InstallDir 'venv'

$Model   = if ($env:WHISPER_MODEL)   { $env:WHISPER_MODEL }   else { 'small' }
$Device  = if ($env:WHISPER_DEVICE)  { $env:WHISPER_DEVICE }  else { 'cuda' }
$Compute = if ($env:WHISPER_COMPUTE) { $env:WHISPER_COMPUTE } else { 'float16' }

Write-Host "==> Installing voice-dictation to $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

function Require-Cmd($name, $wingetId) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "==> Installing $name via winget ($wingetId)"
        winget install --silent --accept-source-agreements --accept-package-agreements --id $wingetId
    }
}

Require-Cmd 'python'      'Python.Python.3.11'
Require-Cmd 'sox'         'ChrisBagwell.SoX'
Require-Cmd 'AutoHotkey'  'AutoHotkey.AutoHotkey'

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
Copy-Item (Join-Path $RepoDir 'transcribe.py')        (Join-Path $InstallDir 'transcribe.py')        -Force
Copy-Item (Join-Path $RepoDir 'transcribe_server.py') (Join-Path $InstallDir 'transcribe_server.py') -Force
Copy-Item (Join-Path $RepoDir 'transcribe_client.py') (Join-Path $InstallDir 'transcribe_client.py') -Force
Copy-Item (Join-Path $RepoDir 'windows\voice-toggle.ahk') (Join-Path $InstallDir 'voice-toggle.ahk') -Force

# Wrapper batch file that sets env vars and launches the server.
$LauncherBat = Join-Path $InstallDir 'start-server.bat'
@"
@echo off
set WHISPER_MODEL=$Model
set WHISPER_DEVICE=$Device
set WHISPER_COMPUTE=$Compute
"$VenvPy" "$InstallDir\transcribe_server.py"
"@ | Set-Content -Encoding ASCII $LauncherBat

Write-Host "==> Registering scheduled task to start the server at login"
$TaskName = 'VoiceDictationServer'
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null
schtasks /Create /TN $TaskName /SC ONLOGON /RL HIGHEST /TR "`"$LauncherBat`"" /F | Out-Null
schtasks /Run /TN $TaskName | Out-Null

Write-Host "==> Adding AutoHotkey script to startup (per-user)"
$StartupDir = [Environment]::GetFolderPath('Startup')
$AhkTarget  = Join-Path $InstallDir 'voice-toggle.ahk'
$ShortcutPath = Join-Path $StartupDir 'voice-toggle.lnk'
$WScript = New-Object -ComObject WScript.Shell
$Shortcut = $WScript.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = (Get-Command AutoHotkey).Source
$Shortcut.Arguments  = "`"$AhkTarget`""
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()

# Run it now so the hotkey is live immediately.
Start-Process (Get-Command AutoHotkey).Source -ArgumentList "`"$AhkTarget`""

Write-Host ""
Write-Host "==> Done."
Write-Host "Hotkey: Ctrl+Alt+V"
Write-Host "Server task: $TaskName (Task Scheduler -> $TaskName)"
Write-Host "Log files: %LOCALAPPDATA%\voice-dictation\ (server stdout goes to the task host)"
