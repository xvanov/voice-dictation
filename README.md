# ai-tools

Internal tooling for AI-assisted workflows: push-to-talk dictation, batch transcription/summarization, and Claude Code utilities.

## Tools

| Tool | Description |
|------|-------------|
| [voice-dictation](./voice-dictation/) | Push-to-talk voice transcription via faster-whisper → auto-paste (Windows + Linux) |
| [summarize-day](./summarize-day/) | Batch transcribe long recordings and summarize via Azure OpenAI |
| [claude-ctx-statusline](./claude-ctx-statusline/) | Shows context window usage in the Claude Code status bar |

## Quick start

### Voice dictation (Windows)

```powershell
cd voice-dictation
Set-ExecutionPolicy -Scope Process Bypass
.\windows\install.ps1
```

Press `Ctrl+Alt+V` to record. Recording auto-stops on silence; transcript is cleaned up and pasted at the cursor.

### Voice dictation (Linux)

```bash
cd voice-dictation
./linux/install.sh
```

Bind `~/.local/voice-dictation/voice-toggle.sh` to `Ctrl+Alt+V` in keyboard settings.

### summarize-day

```bash
cd summarize-day
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Set AZURE_OPENAI_* or AZURE_FOUNDRY_* in repo-root .env
python summarize-day.py run recording.mp3
```

### Claude context status line

```powershell
cd claude-ctx-statusline
.\install.ps1
```

Restart Claude Code to see `Ctx: 30k/200k (15%)` in the status bar.

## Repo layout

```
voice-dictation/          # real-time dictation (recorder + overlay + warm server)
summarize-day/              # batch transcribe + Azure summarization CLI
claude-ctx-statusline/      # Claude Code statusLine helper
```

Each tool has its own README, requirements, and install scripts.
