#!/usr/bin/env python3
"""One-shot transcription. Loads the model on every call (slow).

Prefer the server (transcribe_server.py + transcribe_client.py) for hotkey use.
"""
import argparse
import sys
from faster_whisper import WhisperModel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("audio", help="Path to audio file (wav, mp3, m4a, ...)")
    p.add_argument("--model", default="small",
                   help="tiny/base/small/medium/large-v3 (default: small)")
    p.add_argument("--language", default="en", help="Language code or 'auto'")
    p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    p.add_argument("--compute-type", default="float16",
                   help="GPU: float16/int8_float16. CPU: int8/float32.")
    p.add_argument("--beam-size", type=int, default=1)
    args = p.parse_args()

    language = None if args.language == "auto" else args.language
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments, _ = model.transcribe(args.audio, language=language, beam_size=args.beam_size)
    print(" ".join(seg.text.strip() for seg in segments))
    return 0


if __name__ == "__main__":
    sys.exit(main())
