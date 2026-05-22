#!/usr/bin/env python3
"""Transcribe audio with faster-whisper and summarize via Azure AI Foundry.

Usage:
  summarize-day.py transcribe <audio>
  summarize-day.py summarize <json>
  summarize-day.py run <file-or-dir>...
  summarize-day.py combine <file-or-dir>...

Environment (repo-root .env or shell):
  AZURE_FOUNDRY_ENDPOINT     Azure AI Foundry endpoint URL
  AZURE_FOUNDRY_API_KEY      API key
  AZURE_FOUNDRY_API_VERSION  API version (default: 2024-05-01-preview)
  AZURE_FOUNDRY_DEPLOYMENT   Model name (default: deepseek-r1)
"""
from summarize_day.cli import cli

cli()
