# uninstall.ps1 - Remove voice-dictation from Windows.
$ErrorActionPreference = 'SilentlyContinue'

$InstallDir = Join-Path $env:LOCALAPPDATA 'voice-dictation'
$StartupDir = [Environment]::GetFolderPath('Startup')

schtasks /End    /TN 'VoiceDictationServer' | Out-Null
schtasks /Delete /TN 'VoiceDictationServer' /F | Out-Null

Get-Process AutoHotkey -ErrorAction SilentlyContinue | Stop-Process -Force

Remove-Item (Join-Path $StartupDir 'voice-toggle.lnk') -Force
Remove-Item $InstallDir -Recurse -Force

Write-Host "Removed $InstallDir, scheduled task, and startup shortcut."
