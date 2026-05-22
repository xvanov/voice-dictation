#!/bin/bash
# Toggle voice recording. First press starts, second press stops and transcribes.
# Esc cancel is handled by the overlay window's Esc binding.
# Requires a running transcribe_server.py and xdotool for auto-paste.

set -u

INSTALL_DIR="${VOICE_INSTALL_DIR:-$HOME/.local/voice-dictation}"
PYTHON="$INSTALL_DIR/venv/bin/python"
RECORDER="$INSTALL_DIR/recorder.py"

RUNNING_FLAG="/tmp/vd-running.flag"
STOP_FLAG="/tmp/vd-stop.flag"

notify() {
    notify-send -t 1500 "Voice" "$1" 2>/dev/null || echo "$1"
}

if [ -f "$RUNNING_FLAG" ]; then
    # 2nd press: request stop → transcribe
    touch "$STOP_FLAG"
else
    # 1st press: launch recorder
    rm -f "/tmp/vd-cancel.flag" "$STOP_FLAG"
    if [ ! -f "$PYTHON" ]; then
        notify "voice-dictation not installed — run linux/install.sh"
        exit 1
    fi
    "$PYTHON" "$RECORDER" &
fi
