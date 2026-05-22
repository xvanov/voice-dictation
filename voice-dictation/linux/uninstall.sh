#!/bin/bash
# Remove voice-dictation from the user's account.
set -u

INSTALL_DIR="$HOME/.local/voice-dictation"
SERVICE_FILE="$HOME/.config/systemd/user/voice-dictation.service"

systemctl --user disable --now voice-dictation.service 2>/dev/null || true
rm -f "$SERVICE_FILE"
systemctl --user daemon-reload

rm -rf "$INSTALL_DIR"
echo "Removed $INSTALL_DIR and systemd unit."
echo "Remove your hotkey binding manually from GNOME Settings."
