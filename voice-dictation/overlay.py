#!/usr/bin/env python3
"""Always-on-top recording overlay (tkinter). Thread-safe via root.after()."""

import os
import tempfile
import tkinter as tk
import tkinter.font as tkfont

METER_WIDTH = 492
METER_HEIGHT = 12
# RMS that fills bar to 100% — set high so normal speech stays green/orange
_METER_FULL_RMS = 0.35


class Overlay:
    def __init__(self, silence_threshold: float = 0.01):
        self._root = tk.Tk()
        self._status_var = tk.StringVar(value="Recording...")
        self._text_var = tk.StringVar(value="")
        self._info_var = tk.StringVar(value="")
        self._silence_threshold = silence_threshold
        self._mic = ""
        self._model = ""
        self._backend = ""
        self._setup()

    def _setup(self):
        root = self._root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.90)
        root.configure(bg="#1a1a1a")

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 520, 128
        x = (sw - w) // 2
        y = sh - h - 64
        root.geometry(f"{w}x{h}+{x}+{y}")

        fstatus = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        ftext = tkfont.Font(family="Segoe UI", size=10)
        fdevice = tkfont.Font(family="Segoe UI", size=9)

        tk.Label(
            root, textvariable=self._status_var,
            fg="#4fc3f7", bg="#1a1a1a", font=fstatus, anchor="w", padx=14, pady=4,
        ).pack(fill="x")
        tk.Label(
            root, textvariable=self._text_var,
            fg="#e0e0e0", bg="#1a1a1a", font=ftext,
            wraplength=492, anchor="w", padx=14, pady=0,
        ).pack(fill="x")

        # VU meter
        meter_frame = tk.Frame(root, bg="#1a1a1a", padx=14, pady=4)
        meter_frame.pack(fill="x")
        self._canvas = tk.Canvas(
            meter_frame, width=METER_WIDTH, height=METER_HEIGHT,
            bg="#2a2a2a", highlightthickness=0,
        )
        self._canvas.pack()
        self._bar = self._canvas.create_rectangle(0, 0, 0, METER_HEIGHT, fill="#4caf50", outline="")
        # Threshold marker — white line shows where speech detection kicks in
        threshold_x = int(METER_WIDTH * min(self._silence_threshold / _METER_FULL_RMS, 1.0))
        self._canvas.create_line(threshold_x, 0, threshold_x, METER_HEIGHT, fill="#ffffff", width=1)

        # Info line: mic + whisper model
        tk.Label(
            root, textvariable=self._info_var,
            fg="#666666", bg="#1a1a1a", font=fdevice, anchor="w", padx=14, pady=2,
        ).pack(fill="x")

        root.bind("<Escape>", self._on_esc)

    @staticmethod
    def _on_esc(_event=None):
        flag = os.path.join(tempfile.gettempdir(), "vd-cancel.flag")
        open(flag, "w").close()

    def update(self, text: str, status: str = None):
        """Thread-safe update of transcript text and optional status."""
        def _do():
            if status:
                self._status_var.set(status)
            display = text[:220] + ("…" if len(text) > 220 else "")
            self._text_var.set(display)
        self._root.after(0, _do)

    def set_status(self, status: str):
        """Thread-safe status-only update."""
        self._root.after(0, lambda: self._status_var.set(status))

    def _refresh_info(self) -> None:
        parts = []
        if self._mic:
            parts.append(f"Mic: {self._mic}")
        if self._model:
            parts.append(f"Whisper: {self._model}")
        if self._backend:
            parts.append(f"Cleanup: {self._backend}")
        self._info_var.set("  |  ".join(parts))

    def set_device(self, name: str):
        """Thread-safe mic name update."""
        short = name if len(name) <= 55 else name[:52] + "..."
        def _do():
            self._mic = short
            self._refresh_info()
        self._root.after(0, _do)

    def set_model(self, model_info: str):
        """Thread-safe Whisper model info update (e.g. 'small/cuda')."""
        def _do():
            self._model = model_info
            self._refresh_info()
        self._root.after(0, _do)

    def set_backend(self, backend: str):
        """Thread-safe cleanup backend display update."""
        def _do():
            self._backend = backend
            self._refresh_info()
        self._root.after(0, _do)

    def update_level(self, rms: float):
        """Thread-safe VU meter update."""
        def _do():
            ratio = min(rms / _METER_FULL_RMS, 1.0)
            width = int(METER_WIDTH * ratio)
            color = "#f44336" if ratio > 0.85 else "#ff9800" if ratio > 0.5 else "#4caf50"
            self._canvas.coords(self._bar, 0, 0, width, METER_HEIGHT)
            self._canvas.itemconfig(self._bar, fill=color)
        self._root.after(0, _do)

    def close(self, delay_ms: int = 6000):
        """Schedule window destruction after delay_ms. Click overlay to dismiss early."""
        self._root.after(delay_ms, self._root.destroy)
        self._root.after(0, lambda: self._root.bind("<Button-1>", lambda _: self._root.destroy()))

    def mainloop(self):
        self._root.mainloop()
