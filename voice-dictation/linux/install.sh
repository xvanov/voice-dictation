#!/bin/bash
# Linux installer for voice-dictation.
#
# Installs into ~/.local/voice-dictation:
#   - Python venv with faster-whisper + sounddevice + CUDA libs
#   - transcribe_server.py running as a systemd --user service
#   - recorder.py, overlay.py, llm_cleanup.py, voice-toggle.sh
# After running, bind a global hotkey to ~/.local/voice-dictation/voice-toggle.sh.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$HOME/.local/voice-dictation"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_DIR="$HOME/.config/systemd/user"

echo "==> Installing voice-dictation to $INSTALL_DIR"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing dependency: $1 — install it and retry"; exit 1; }; }
need python3
need systemctl

# portaudio19-dev: required by sounddevice
# xdotool: auto-paste (Ctrl+V simulation) + pyperclip clipboard fallback
# python3-tk: tkinter overlay
# libnotify-bin: notify-send (optional, used by voice-toggle.sh)
echo "==> Installing OS packages (may prompt for sudo)"
sudo apt-get install -y portaudio19-dev xdotool python3-tk libnotify-bin 2>/dev/null || \
    echo "  (apt-get failed — on non-Debian distros install portaudio, xdotool, python3-tk manually)"

mkdir -p "$INSTALL_DIR" "$SERVICE_DIR"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating venv"
    python3 -m venv "$VENV_DIR"
fi

echo "==> Installing Python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt"

if [ "${INSTALL_GPU:-1}" = "1" ]; then
    echo "==> Installing CUDA runtime libraries (cuDNN + cuBLAS for CUDA 12)"
    "$VENV_DIR/bin/pip" install nvidia-cudnn-cu12 nvidia-cublas-cu12
fi

echo "==> Copying Python scripts"
for script in transcribe.py transcribe_server.py transcribe_client.py \
              recorder.py overlay.py llm_cleanup.py; do
    install -m 0644 "$REPO_DIR/$script" "$INSTALL_DIR/$script"
done
install -m 0755 "$REPO_DIR/linux/voice-toggle.sh" "$INSTALL_DIR/voice-toggle.sh"

echo "==> Writing systemd --user service"
SERVICE_FILE="$SERVICE_DIR/voice-dictation.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Voice dictation transcription server (faster-whisper)
After=default.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/transcribe_server.py
Environment=WHISPER_MODEL=${WHISPER_MODEL:-small}
Environment=WHISPER_DEVICE=${WHISPER_DEVICE:-cuda}
Environment=WHISPER_COMPUTE=${WHISPER_COMPUTE:-float16}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now voice-dictation.service
sleep 1
systemctl --user status voice-dictation.service --no-pager | head -8 || true

echo ""
echo "==> Done."
echo "Next: bind a global hotkey (GNOME: Settings -> Keyboard -> Custom Shortcuts)"
echo "  Command: $INSTALL_DIR/voice-toggle.sh"
echo "  Suggested binding: Ctrl+Alt+V"
echo ""
echo "Optional (LLM cleanup): install Ollama (ollama.ai) and pull a model:"
echo "  ollama pull llama3.2"
