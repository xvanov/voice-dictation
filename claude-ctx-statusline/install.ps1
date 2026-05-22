#Requires -Version 5.1
<#
.SYNOPSIS
    Install Claude Code context statusline display.
.DESCRIPTION
    Copies ctx-statusline.js to ~/.claude/scripts/ and patches
    ~/.claude/settings.json to wire up the statusLine command.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- paths ---
$ClaudeDir   = Join-Path $env:USERPROFILE '.claude'
$ScriptsDir  = Join-Path $ClaudeDir 'scripts'
$SettingsFile = Join-Path $ClaudeDir 'settings.json'
$ScriptSrc   = Join-Path $PSScriptRoot 'ctx-statusline.js'
$ScriptDest  = Join-Path $ScriptsDir 'ctx-statusline.js'

# --- prereqs ---
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js not found. Install from https://nodejs.org and re-run."
    exit 1
}

# --- copy script ---
New-Item -ItemType Directory -Force -Path $ScriptsDir | Out-Null
Copy-Item -Path $ScriptSrc -Destination $ScriptDest -Force
Write-Host "Copied ctx-statusline.js -> $ScriptDest"

# --- patch settings.json ---
$statusLineValue = @{
    type    = 'command'
    command = "node `"$ScriptDest`""
}

if (Test-Path $SettingsFile) {
    $settings = Get-Content $SettingsFile -Raw | ConvertFrom-Json
} else {
    New-Item -ItemType File -Force -Path $SettingsFile | Out-Null
    $settings = [PSCustomObject]@{}
}

# Add/overwrite statusLine key
$settings | Add-Member -MemberType NoteProperty -Name 'statusLine' -Value $statusLineValue -Force

$settings | ConvertTo-Json -Depth 10 | Out-File -FilePath $SettingsFile -Encoding utf8
Write-Host "Patched $SettingsFile"
Write-Host ""
Write-Host "Done. Restart Claude Code to see: Ctx: 30k/200k (15%)"
