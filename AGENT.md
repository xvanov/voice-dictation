# AGENT.md - install instructions for coding agents

This document is the source of truth for installing voice-dictation on a fresh
machine. It is written for an autonomous coding agent (Claude Code, Cursor,
etc.). Follow it top to bottom for the target platform. Stop and report when a
step requires the human (interactive auth, BIOS, etc.).

The end state is: pressing `Ctrl+Alt+V` records audio, releases the hotkey
transcribes it via faster-whisper, and the transcript is on the clipboard.

## Decision tree

1. Detect the platform: `uname` -> Linux, or `$PSVersionTable` -> Windows.
2. Detect GPU: `nvidia-smi` -> CUDA, else fall back to CPU (`WHISPER_DEVICE=cpu`,
   `WHISPER_COMPUTE=int8`).
3. Run the platform-specific section below.
4. Run the **Verification** section.

---

## Linux (Ubuntu 22.04+ / GNOME / X11)

### Prerequisites the user must have

- `sudo` access (only needed if any system packages are missing).
- An NVIDIA driver if GPU mode is desired. The agent must **not** install
  drivers; if `nvidia-smi` fails, switch to CPU and warn the user.

### Steps

1. **Install OS dependencies** (skip any already present):
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-venv alsa-utils xclip libnotify-bin
   ```

2. **Clone the repo** (the agent should have done this already to read this file):
   ```bash
   git clone https://github.com/xvanov/voice-dictation.git ~/voice-dictation
   cd ~/voice-dictation
   ```

3. **Run the installer**:
   ```bash
   ./linux/install.sh
   ```
   - This creates `~/.local/voice-dictation/venv`, pip-installs
     `faster-whisper`, and (if GPU) `nvidia-cudnn-cu12 nvidia-cublas-cu12`.
   - It installs a systemd --user service `voice-dictation.service` and
     enables/starts it.
   - For CPU-only install, prefix with `INSTALL_GPU=0 WHISPER_DEVICE=cpu WHISPER_COMPUTE=int8`.

4. **Bind the global hotkey** (cannot be done from a non-interactive shell on
   modern GNOME without dbus). Run this script as the user:
   ```bash
   SCHEMA=org.gnome.settings-daemon.plugins.media-keys
   PATHKEY=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voice-dictation/
   gsettings set $SCHEMA custom-keybindings "['$PATHKEY']"
   gsettings set $SCHEMA.custom-keybinding:$PATHKEY name 'Voice Dictation'
   gsettings set $SCHEMA.custom-keybinding:$PATHKEY command "$HOME/.local/voice-dictation/voice-toggle.sh"
   gsettings set $SCHEMA.custom-keybinding:$PATHKEY binding '<Ctrl><Alt>v'
   ```
   If `gsettings` is unavailable (KDE / Wayland / sway), tell the user to bind
   the hotkey manually to `~/.local/voice-dictation/voice-toggle.sh`.

5. **Verify** (see Verification section below).

### Common Linux failure modes

- `arecord` exits immediately with "no soundcards found" -> user is in the
  wrong audio group. `sudo usermod -aG audio $USER`, then re-login.
- Server starts but first transcription fails with `Could not load library libcudnn_ops.so.9`
  -> cuDNN wheel didn't land. Run
  `~/.local/voice-dictation/venv/bin/pip install --force-reinstall nvidia-cudnn-cu12 nvidia-cublas-cu12`.
- Hotkey fires but nothing is recorded -> X11 vs Wayland. On Wayland, the
  toggle script still works but some terminals print warnings; ignore them.

---

## Windows 10 / 11

### Prerequisites the user must have

- A working `winget` (preinstalled on Win 11; on Win 10 install "App Installer"
  from the Microsoft Store first).
- Local admin rights for the first run (so winget can install Python / SoX /
  AutoHotkey machine-wide).
- An NVIDIA driver if GPU mode is desired.

### Steps

1. **Clone the repo** in any user-writable location:
   ```powershell
   git clone https://github.com/xvanov/voice-dictation.git $env:USERPROFILE\voice-dictation
   cd $env:USERPROFILE\voice-dictation
   ```

2. **Open an elevated PowerShell** (Right-click -> Run as Administrator) and
   navigate back to the repo. Then:
   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\windows\install.ps1
   ```
   The installer will:
   - Install Python 3.11, SoX, AutoHotkey v2 via winget if missing.
   - Create a venv at `%LOCALAPPDATA%\voice-dictation\venv`.
   - Pip-install `faster-whisper` and (for GPU) `nvidia-cudnn-cu12 nvidia-cublas-cu12`.
   - Register a Scheduled Task `VoiceDictationServer` that runs at logon as the
     current user with highest privileges.
   - Copy `voice-toggle.ahk` to startup and start it immediately.

3. **CPU-only install** (no NVIDIA GPU): before invoking the installer:
   ```powershell
   $env:WHISPER_DEVICE  = 'cpu'
   $env:WHISPER_COMPUTE = 'int8'
   .\windows\install.ps1
   ```

4. **Verify** (see Verification section below).

### Common Windows failure modes

- `winget` not found -> install "App Installer" from the Microsoft Store and
  retry. Do not try to install winget via PowerShell scripts.
- `sox` records 0-byte WAV files -> default input device is wrong. Run
  `sox -t waveaudio -? default` to list devices; replace `default` with the
  correct device index in `voice-toggle.ahk`.
- Scheduled task shows "0x41301" (still running) but transcripts come back
  empty -> CUDA DLLs missing. Activate the venv and run
  `pip install --force-reinstall nvidia-cudnn-cu12 nvidia-cublas-cu12`.
- The first model download stalls behind a corporate proxy -> set
  `HF_HUB_ETAG_TIMEOUT=30` and `HTTPS_PROXY` in the task's environment.
- Hotkey doesn't fire -> another app is bound to `Ctrl+Alt+V`. Edit
  `%LOCALAPPDATA%\voice-dictation\voice-toggle.ahk`, change the `^!v::` line
  to something else (e.g. `^!d::`), and restart AutoHotkey.

---

## Verification (both platforms)

1. **Server is up**:
   - Linux: `systemctl --user is-active voice-dictation` -> `active`.
   - Windows: `schtasks /Query /TN VoiceDictationServer /V /FO LIST` -> Last
     Result `0` or `0x41301`.

2. **Server responds**: record a 2-second clip and pipe it through the client.
   - Linux:
     ```bash
     arecord -f cd -d 2 /tmp/test.wav
     ~/.local/voice-dictation/venv/bin/python ~/.local/voice-dictation/transcribe_client.py /tmp/test.wav
     ```
   - Windows (PowerShell):
     ```powershell
     sox -t waveaudio default -c 1 -r 16000 -b 16 $env:TEMP\test.wav trim 0 2
     & "$env:LOCALAPPDATA\voice-dictation\venv\Scripts\python.exe" `
       "$env:LOCALAPPDATA\voice-dictation\transcribe_client.py" "$env:TEMP\test.wav"
     ```
   - The first call may take 10-30 s while the model loads. Subsequent calls
     should return in ~1 s for short clips.

3. **Hotkey works end-to-end**: press `Ctrl+Alt+V`, say "this is a test", press
   `Ctrl+Alt+V` again. A toast should appear with "Copied: this is a test" and
   the clipboard should contain the text. Paste into a text editor to confirm.

If all three checks pass, report success and stop.

---

## Updating

`git pull` in the cloned repo, then re-run the installer. It is idempotent and
will reuse the existing venv and model cache.

## Uninstall

- Linux: `~/voice-dictation/linux/uninstall.sh`
- Windows: `.\windows\uninstall.ps1` from an elevated PowerShell.

Both leave the model cache (`~/.cache/huggingface`) alone so re-installing
doesn't redownload weights. Delete that directory manually if you want to
reclaim the disk space.

---

## What the agent should NOT do

- Do not install NVIDIA drivers. That requires reboots and varies by distro.
- Do not modify global Python or system Python; everything goes in the venv.
- Do not change the hotkey binding without telling the user.
- Do not commit any files from `~/.cache/huggingface` to git (the weights are
  large and re-downloadable).
- Do not edit `transcribe_server.py` to add network bindings other than
  loopback. The server has no auth.
