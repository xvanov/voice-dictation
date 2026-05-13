#!/usr/bin/env python3
"""TCP client for transcribe_server.py. Prints the transcript to stdout."""
import os
import socket
import sys

HOST = os.environ.get("TRANSCRIBE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TRANSCRIBE_PORT", "47821"))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: transcribe_client.py <audio_file>", file=sys.stderr)
        return 2
    audio = os.path.abspath(sys.argv[1])
    try:
        with socket.create_connection((HOST, PORT), timeout=300) as s:
            s.sendall(audio.encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                buf = s.recv(65536)
                if not buf:
                    break
                chunks.append(buf)
        text = b"".join(chunks).decode("utf-8", errors="replace")
        if text.startswith("ERROR:"):
            print(text, file=sys.stderr)
            return 1
        print(text)
        return 0
    except (ConnectionRefusedError, OSError) as exc:
        print(f"Server not reachable on {HOST}:{PORT} ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
