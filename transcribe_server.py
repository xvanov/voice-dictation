#!/usr/bin/env python3
"""Always-warm transcription server.

Listens on a TCP loopback socket. Loads the model on first request, unloads
after IDLE_TIMEOUT seconds to free GPU memory.

Configure via environment variables:
  WHISPER_MODEL       Model name (default: small)
  WHISPER_DEVICE      cuda or cpu (default: cuda)
  WHISPER_COMPUTE     float16 / int8_float16 / int8 (default: float16)
  WHISPER_LANGUAGE    Language code or 'auto' (default: en)
  TRANSCRIBE_HOST     Bind host (default: 127.0.0.1)
  TRANSCRIBE_PORT     Bind port (default: 47821)
  IDLE_TIMEOUT_SEC    Seconds before unloading (default: 1800)
"""
import gc
import os
import socket
import sys
import threading
import time

from faster_whisper import WhisperModel

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
DEVICE = os.environ.get("WHISPER_DEVICE", "cuda")
COMPUTE = os.environ.get("WHISPER_COMPUTE", "float16")
LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "en")
HOST = os.environ.get("TRANSCRIBE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TRANSCRIBE_PORT", "47821"))
IDLE_TIMEOUT = int(os.environ.get("IDLE_TIMEOUT_SEC", "1800"))

_model = None
_lock = threading.Lock()
_last_used = 0.0


def _load() -> None:
    global _model, _last_used
    if _model is None:
        print(f"Loading {MODEL_NAME} on {DEVICE} ({COMPUTE})...", flush=True)
        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE)
        print("Model loaded.", flush=True)
    _last_used = time.time()


def _unload() -> None:
    global _model
    if _model is not None:
        print("Unloading model (idle timeout).", flush=True)
        del _model
        _model = None
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass


def _idle_watcher() -> None:
    while True:
        time.sleep(60)
        with _lock:
            if _model is not None and (time.time() - _last_used) > IDLE_TIMEOUT:
                _unload()


def _transcribe(audio_path: str) -> str:
    global _last_used
    with _lock:
        _load()
        lang = None if LANGUAGE == "auto" else LANGUAGE
        segments, _info = _model.transcribe(audio_path, language=lang, beam_size=1)
        _last_used = time.time()
        return " ".join(seg.text.strip() for seg in segments)


def main() -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(4)

    threading.Thread(target=_idle_watcher, daemon=True).start()

    print(f"Listening on {HOST}:{PORT}. Idle unload after {IDLE_TIMEOUT}s.", flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            data = conn.recv(8192).decode("utf-8", errors="replace").strip()
            if not data:
                conn.sendall(b"")
                continue
            text = _transcribe(data)
            conn.sendall(text.encode("utf-8"))
        except Exception as exc:
            try:
                conn.sendall(f"ERROR: {exc}".encode("utf-8"))
            except Exception:
                pass
            print(f"request error: {exc}", file=sys.stderr, flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
