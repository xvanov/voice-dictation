#!/usr/bin/env python3
"""Local transcription history — JSONL append-only storage with 7-day retention."""

import json
import os
import platform
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

_LOCK = threading.Lock()
_RETENTION_DAYS = 7


def data_dir() -> str:
    """Platform install/data directory (matches installer layout)."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".local")
    path = os.path.join(base, "voice-dictation")
    os.makedirs(path, exist_ok=True)
    return path


def history_path() -> str:
    return os.path.join(data_dir(), "history.jsonl")


def _parse_ts(raw: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _load_all() -> list[dict[str, Any]]:
    path = history_path()
    if not os.path.isfile(path):
        return []
    entries: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return entries


def _rewrite(entries: list[dict[str, Any]]) -> None:
    path = history_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def prune_old_entries(retention_days: int = _RETENTION_DAYS) -> None:
    """Drop entries older than retention_days (default 7). Fast no-op if nothing to prune."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with _LOCK:
        entries = _load_all()
        kept = []
        for e in entries:
            ts = _parse_ts(e.get("timestamp", ""))
            if ts is None or ts >= cutoff:
                kept.append(e)
        if len(kept) != len(entries):
            _rewrite(kept)


def append_entry(
    text: str,
    *,
    whisper_seconds: float | None = None,
    cleanup_seconds: float | None = None,
    cleanup_backend: str = "",
    whisper_model: str = "",
    duration_seconds: float | None = None,
) -> None:
    """Append one successful transcription. Non-blocking for callers (uses lock only briefly)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
    }
    meta: dict[str, Any] = {}
    if whisper_seconds is not None:
        meta["whisper_seconds"] = round(whisper_seconds, 3)
    if cleanup_seconds is not None:
        meta["cleanup_seconds"] = round(cleanup_seconds, 3)
    if cleanup_backend:
        meta["cleanup_backend"] = cleanup_backend
    if whisper_model:
        meta["whisper_model"] = whisper_model
    if duration_seconds is not None:
        meta["duration_seconds"] = round(duration_seconds, 2)
    if meta:
        entry["meta"] = meta

    with _LOCK:
        path = history_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Prune occasionally (cheap check: only when file has many lines)
        try:
            if os.path.getsize(path) > 512_000:
                prune_old_entries()
        except OSError:
            pass


def list_today() -> list[dict[str, Any]]:
    """Return today's entries, newest first."""
    today = datetime.now().date()
    entries = _load_all()
    result = []
    for e in reversed(entries):
        ts = _parse_ts(e.get("timestamp", ""))
        if ts and ts.date() == today:
            result.append(e)
    return result


def preview(text: str, max_len: int = 80) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"


def format_time(iso_ts: str) -> str:
    ts = _parse_ts(iso_ts)
    if ts is None:
        return "?"
    local = ts.astimezone()
    return local.strftime("%H:%M:%S")
