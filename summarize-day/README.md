# summarize-day

Batch transcribe long audio recordings with faster-whisper and summarize them via Azure OpenAI / AI Foundry.

Same Whisper engine as [voice-dictation](../voice-dictation/), but geared for offline batch processing of meetings and day recordings.

## Requirements

- Python 3.10+
- Azure OpenAI or AI Foundry endpoint + API key

## Configuration

Create a `.env` file in the **repo root** (or set environment variables):

| Variable | Description |
|---|---|
| `AZURE_OPENAI_ENDPOINT` or `AZURE_FOUNDRY_ENDPOINT` | Endpoint URL |
| `AZURE_OPENAI_API_KEY` or `AZURE_FOUNDRY_API_KEY` | API key |
| `AZURE_OPENAI_DEPLOYMENT` or `AZURE_FOUNDRY_DEPLOYMENT` | Model deployment name |
| `AZURE_OPENAI_API_VERSION` or `AZURE_FOUNDRY_API_VERSION` | API version (default: `2024-05-01-preview`) |

## Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```bash
# Full pipeline: transcribe then summarize
python summarize-day.py run recording.mp3
python summarize-day.py run /path/to/recordings/

# Step by step
python summarize-day.py transcribe recording.mp3
python summarize-day.py summarize recording.json

# Combine existing summaries into a day-summary
python summarize-day.py combine /path/to/recordings/
```

Options: `--force` to redo, `--device cpu` for CPU, `--model tiny` for a smaller model.

## Output

For each audio file `recording.mp3`:

- `recording.json` — aligned segments with timestamps
- `recording.srt` / `recording.vtt` / `recording.txt` — subtitle/text exports
- `recording.summary.md` — AI-generated summary

When processing multiple files, `day-summary.md` merges them into one digest.
