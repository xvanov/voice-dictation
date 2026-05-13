#!/bin/bash
# Toggle voice recording: first press starts recording, second press transcribes
# and copies the result to the clipboard. Bind this to a global hotkey
# (e.g. Ctrl+Alt+V).
#
# Requires: arecord (alsa-utils), xclip, and a running transcribe_server.py.

set -u

PIDFILE="/tmp/voice-recording.pid"
WAVFILE="/tmp/voice-recording.wav"
CLIENT="${VOICE_CLIENT:-$HOME/.local/voice-dictation/venv/bin/python $HOME/.local/voice-dictation/transcribe_client.py}"

notify() {
    notify-send -t 1500 "Voice" "$1" 2>/dev/null || echo "$1"
}

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    kill "$PID" 2>/dev/null
    rm -f "$PIDFILE"

    notify "Transcribing..."
    TEXT=$($CLIENT "$WAVFILE" 2>/dev/null)
    rm -f "$WAVFILE"

    if [ -n "$TEXT" ]; then
        printf '%s' "$TEXT" | xclip -selection clipboard
        notify "Copied: ${TEXT:0:60}"
    else
        notify "No speech detected (is the server running?)"
    fi
else
    notify "Recording..."
    arecord -f cd -t wav "$WAVFILE" >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
fi
