# voice-dictation

Push-to-talk voice dictation using [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
Press a global hotkey (`Ctrl+Alt+V` by default), speak, press again — the transcript
lands on your clipboard. Works on Linux (X11/GNOME) and Windows.

Architecture is dead simple:

```
hotkey -> record .wav -> TCP client -> always-warm server -> faster-whisper -> clipboard
```

The model stays loaded in GPU memory between presses, so the second press to
clipboard takes ~1 second for short utterances. The server unloads itself
after 30 min idle to free VRAM.

## Quick install

### Linux (Ubuntu / GNOME)

```bash
git clone https://github.com/xvanov/voice-dictation.git
cd voice-dictation
./linux/install.sh
```

Then bind a global hotkey in **Settings -> Keyboard -> Custom Shortcuts** to:

```
~/.local/voice-dictation/voice-toggle.sh
```

Suggested binding: `Ctrl+Alt+V`.

### Windows 10/11

Open an **elevated PowerShell** in the cloned repo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\install.ps1
```

The installer registers the server as a Scheduled Task at logon and drops the
AutoHotkey hotkey script into your Startup folder. Hotkey is `Ctrl+Alt+V`.

## Configuration

Both platforms read these environment variables (defaults shown):

| Variable           | Default     | Notes                                       |
| ------------------ | ----------- | ------------------------------------------- |
| `WHISPER_MODEL`    | `small`     | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE`   | `cuda`      | Set to `cpu` if you have no NVIDIA GPU      |
| `WHISPER_COMPUTE`  | `float16`   | CPU users: set to `int8`                    |
| `WHISPER_LANGUAGE` | `en`        | Use `auto` for multilingual                 |
| `TRANSCRIBE_PORT`  | `47821`     | Loopback TCP port                           |
| `IDLE_TIMEOUT_SEC` | `1800`      | Seconds before unloading the model          |

On Linux they go in the systemd unit (`~/.config/systemd/user/voice-dictation.service`).
On Windows they're baked into `start-server.bat` by the installer.

## Picking a model

- **`small`** (default): ~470 MB, very accurate for short utterances, GPU 1-2 GB.
- `tiny`: ~75 MB, low-latency, mediocre accuracy. Good for slow CPUs.
- `large-v3`: best accuracy, needs ~5 GB VRAM and is noticeably slower.

The weights download to `~/.cache/huggingface/hub/` (Linux) or
`%USERPROFILE%\.cache\huggingface\hub\` (Windows) on first run.

## Files

| Path                          | Purpose                                      |
| ----------------------------- | -------------------------------------------- |
| `transcribe.py`               | One-shot CLI (loads model every call; slow)  |
| `transcribe_server.py`        | Always-warm TCP server                       |
| `transcribe_client.py`        | TCP client used by the hotkey wrappers       |
| `linux/voice-toggle.sh`       | Linux hotkey toggle (uses `arecord` + `xclip`) |
| `linux/install.sh`            | Linux installer + systemd --user unit         |
| `windows/voice-toggle.ahk`    | Windows hotkey (AutoHotkey v2)               |
| `windows/install.ps1`         | Windows installer + scheduled task           |
| `AGENT.md`                    | Detailed install/troubleshoot guide for agents |

## Troubleshooting

- **"No speech detected"** — the server probably isn't running.
  - Linux: `systemctl --user status voice-dictation` and `journalctl --user -u voice-dictation -n 50`.
  - Windows: open Task Scheduler, find `VoiceDictationServer`, check Last Run Result.
- **CUDA / cuDNN error on first request** — the installer should have pip-installed
  `nvidia-cudnn-cu12` and `nvidia-cublas-cu12`. If it didn't, install them manually
  into the venv, or switch to CPU mode (`WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE=int8`).
- **Hotkey does nothing on Linux** — confirm the custom shortcut command path is
  correct and that `arecord`, `xclip`, and `notify-send` are installed.

See [AGENT.md](AGENT.md) for step-by-step install instructions structured for
coding agents.
