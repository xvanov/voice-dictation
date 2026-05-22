#!/usr/bin/env python3
"""Transcribe audio with faster-whisper and summarize via Azure OpenAI.

Usage:
  summarize-recording.py transcribe <audio>
  summarize-recording.py summarize <json>
  summarize-recording.py run <file-or-dir>...
  summarize-recording.py combine <file-or-dir>...

Environment (repo-root .env or shell):
  AZURE_FOUNDRY_ENDPOINT     Azure AI Foundry endpoint URL
  AZURE_FOUNDRY_API_KEY      API key
  AZURE_FOUNDRY_API_VERSION  API version (default: 2024-05-01-preview)
  AZURE_FOUNDRY_DEPLOYMENT   Model name (default: deepseek-r1)
"""
from summarize_recording.cli import cli

cli()
