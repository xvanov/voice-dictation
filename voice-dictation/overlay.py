#!/usr/bin/env python3
"""Always-on-top recording overlay (tkinter). Thread-safe via root.after()."""

import os
import sys
import tempfile
import tkinter as tk
import tkinter.font as tkfont

import pyperclip

import history

METER_WIDTH = 492
METER_HEIGHT = 12
# RMS that fills bar to 100% — set high so normal speech stays green/orange
_METER_FULL_RMS = 0.35
_DONE_AUTO_CLOSE_MS = 2500
_COPY_FEEDBACK_MS = 1500
_DISPLAY_MAX = 220


class Overlay:
    def __init__(self, silence_threshold: float = 0.01, history_only: bool = False):
        self._root = tk.Tk()
        self._status_var = tk.StringVar(value="Recording...")
        self._text_var = tk.StringVar(value="")
        self._info_var = tk.StringVar(value="")
        self._silence_threshold = silence_threshold
        self._mic = ""
        self._model = ""
        self._backend = ""
        self._full_text = ""
        self._done = False
        self._history_open = False
        self._interacting = False
        self._auto_close_id = None
        self._history_only = history_only
        self._history_win = None
        self._setup()
        if history_only:
            self._root.after(50, self._open_history_panel)

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
        fbtn = tkfont.Font(family="Segoe UI", size=9)

        # Title row: status + close button (hidden until Done)
        title_row = tk.Frame(root, bg="#1a1a1a")
        title_row.pack(fill="x", padx=14, pady=(4, 0))

        tk.Label(
            title_row, textvariable=self._status_var,
            fg="#4fc3f7", bg="#1a1a1a", font=fstatus, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self._close_btn = tk.Button(
            title_row, text="✕", font=fbtn,
            fg="#cccccc", bg="#333333", activebackground="#555555",
            activeforeground="#ffffff", relief="flat", bd=0,
            width=3, padx=4, pady=0, cursor="hand2",
            command=self._close_now,
        )
        # Hidden until Done state

        tk.Label(
            root, textvariable=self._text_var,
            fg="#e0e0e0", bg="#1a1a1a", font=ftext,
            wraplength=492, anchor="w", padx=14, pady=0,
        ).pack(fill="x")

        # VU meter (recording only)
        self._meter_frame = tk.Frame(root, bg="#1a1a1a", padx=14, pady=4)
        self._meter_frame.pack(fill="x")
        self._canvas = tk.Canvas(
            self._meter_frame, width=METER_WIDTH, height=METER_HEIGHT,
            bg="#2a2a2a", highlightthickness=0,
        )
        self._canvas.pack()
        self._bar = self._canvas.create_rectangle(0, 0, 0, METER_HEIGHT, fill="#4caf50", outline="")
        threshold_x = int(METER_WIDTH * min(self._silence_threshold / _METER_FULL_RMS, 1.0))
        self._canvas.create_line(threshold_x, 0, threshold_x, METER_HEIGHT, fill="#ffffff", width=1)

        # Done-state action bar (hidden until Done)
        self._actions_frame = tk.Frame(root, bg="#1a1a1a", padx=14, pady=4)

        self._copy_btn = tk.Button(
            self._actions_frame, text="Copy", font=fbtn,
            fg="#e0e0e0", bg="#333333", activebackground="#555555",
            relief="flat", padx=12, pady=2, cursor="hand2",
            command=self._on_copy,
        )
        self._copy_btn.pack(side="left", padx=(0, 8))
        self._copy_btn.bind("<Enter>", lambda _: self._set_interacting(True))
        self._copy_btn.bind("<Leave>", lambda _: self._set_interacting(False))

        self._history_btn = tk.Button(
            self._actions_frame, text="History", font=fbtn,
            fg="#4fc3f7", bg="#1a1a1a", activebackground="#333333",
            relief="flat", padx=8, pady=2, cursor="hand2",
            command=self._open_history_panel,
        )
        self._history_btn.pack(side="left")
        self._history_btn.bind("<Enter>", lambda _: self._set_interacting(True))
        self._history_btn.bind("<Leave>", lambda _: self._set_interacting(False))

        # Info line: mic + whisper model
        self._info_label = tk.Label(
            root, textvariable=self._info_var,
            fg="#666666", bg="#1a1a1a", font=fdevice, anchor="w", padx=14, pady=2,
        )
        self._info_label.pack(fill="x")

        root.bind("<Escape>", self._on_esc)

        if self._history_only:
            self._meter_frame.pack_forget()
            root.withdraw()

    @staticmethod
    def _on_esc(_event=None):
        flag = os.path.join(tempfile.gettempdir(), "vd-cancel.flag")
        open(flag, "w").close()

    def _set_interacting(self, active: bool):
        self._interacting = active
        if not active and self._done:
            self._schedule_auto_close()

    def _display_text(self, text: str):
        self._full_text = text
        display = text[:_DISPLAY_MAX] + ("…" if len(text) > _DISPLAY_MAX else "")
        self._text_var.set(display)

    def update(self, text: str, status: str = None):
        """Thread-safe update of transcript text and optional status."""
        def _do():
            if status:
                self._status_var.set(status)
            self._display_text(text)
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
            if self._done:
                return
            ratio = min(rms / _METER_FULL_RMS, 1.0)
            width = int(METER_WIDTH * ratio)
            color = "#f44336" if ratio > 0.85 else "#ff9800" if ratio > 0.5 else "#4caf50"
            self._canvas.coords(self._bar, 0, 0, width, METER_HEIGHT)
            self._canvas.itemconfig(self._bar, fill=color)
        self._root.after(0, _do)

    def show_done(self, text: str, status: str, delay_ms: int = _DONE_AUTO_CLOSE_MS):
        """Enter Done state with controls. Thread-safe."""
        def _do():
            self._done = True
            self._status_var.set(status)
            self._display_text(text)
            self._meter_frame.pack_forget()
            self._close_btn.pack(side="right")
            self._actions_frame.pack(fill="x", before=self._info_label)
            self._root.update_idletasks()
            self._resize_for_done()
            self._root.bind("<Button-1>", self._on_background_click, add="+")
            self._schedule_auto_close(delay_ms)
        self._root.after(0, _do)

    def _resize_for_done(self):
        """Grow window slightly to fit action buttons."""
        self._root.update_idletasks()
        h = max(128, self._root.winfo_reqheight())
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w = 520
        x = (sw - w) // 2
        y = sh - h - 64
        self._root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_background_click(self, event):
        """Dismiss on background click, not on buttons."""
        widget = event.widget
        if widget in (self._copy_btn, self._history_btn, self._close_btn):
            return
        if self._history_open:
            return
        self._close_now()

    def _cancel_auto_close(self):
        if self._auto_close_id is not None:
            self._root.after_cancel(self._auto_close_id)
            self._auto_close_id = None

    def _schedule_auto_close(self, delay_ms: int = _DONE_AUTO_CLOSE_MS):
        self._cancel_auto_close()
        if self._interacting or self._history_open:
            return

        def _try_close():
            self._auto_close_id = None
            if not self._interacting and not self._history_open:
                self._close_now()

        self._auto_close_id = self._root.after(delay_ms, _try_close)

    def _on_copy(self, text: str | None = None):
        full = text if text is not None else self._full_text
        if not full:
            return
        pyperclip.copy(full)
        if text is None:
            orig = self._copy_btn.cget("text")
            self._copy_btn.config(text="Copied!")
            self._cancel_auto_close()
            self._root.after(_COPY_FEEDBACK_MS, lambda: self._copy_btn.config(text=orig))
            self._root.after(_COPY_FEEDBACK_MS + 100, self._schedule_auto_close)

    def _close_now(self):
        self._cancel_auto_close()
        if self._history_win and self._history_win.winfo_exists():
            self._history_win.destroy()
        self._root.destroy()

    def close(self, delay_ms: int = 600):
        """Schedule window destruction (non-Done states: cancelled, errors)."""
        self._root.after(delay_ms, self._root.destroy)
        self._root.after(0, lambda: self._root.bind("<Button-1>", lambda _: self._root.destroy()))

    def _open_history_panel(self):
        if self._history_win and self._history_win.winfo_exists():
            self._history_win.lift()
            return

        self._history_open = True
        self._cancel_auto_close()

        win = tk.Toplevel(self._root)
        self._history_win = win
        win.title("Transcription History")
        win.configure(bg="#1a1a1a")
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        win.resizable(True, True)

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w, h = 480, 360
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

        ftitle = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        frow = tkfont.Font(family="Segoe UI", size=10)
        fpreview = tkfont.Font(family="Segoe UI", size=9)
        fbtn = tkfont.Font(family="Segoe UI", size=9)

        header = tk.Frame(win, bg="#1a1a1a", padx=12, pady=8)
        header.pack(fill="x")
        tk.Label(
            header, text="Today's transcriptions", font=ftitle,
            fg="#4fc3f7", bg="#1a1a1a",
        ).pack(side="left")
        tk.Button(
            header, text="✕", font=fbtn, fg="#cccccc", bg="#333333",
            relief="flat", width=3, command=lambda: self._close_history_panel(win),
        ).pack(side="right")

        list_frame = tk.Frame(win, bg="#1a1a1a")
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        canvas = tk.Canvas(list_frame, bg="#252525", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#252525")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=w - 40)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        detail_frame = tk.Frame(win, bg="#1a1a1a", padx=12, pady=8)
        detail_frame.pack(fill="x")

        detail_text = tk.Text(
            detail_frame, height=4, wrap="word", font=fpreview,
            fg="#e0e0e0", bg="#252525", relief="flat", padx=8, pady=6,
        )
        detail_text.pack(fill="x", pady=(0, 6))
        detail_text.config(state="disabled")

        copy_row = tk.Frame(detail_frame, bg="#1a1a1a")
        copy_row.pack(fill="x")
        detail_copy_btn = tk.Button(
            copy_row, text="Copy", font=fbtn,
            fg="#e0e0e0", bg="#333333", relief="flat", padx=12, pady=2,
            state="disabled",
        )
        detail_copy_btn.pack(side="left")

        selected_text = [""]

        def select_entry(entry: dict):
            full = entry.get("text", "")
            selected_text[0] = full
            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")
            detail_text.insert("1.0", full)
            detail_text.config(state="disabled")
            detail_copy_btn.config(state="normal" if full else "disabled")

        def copy_selected():
            if selected_text[0]:
                pyperclip.copy(selected_text[0])
                orig = detail_copy_btn.cget("text")
                detail_copy_btn.config(text="Copied!")
                win.after(_COPY_FEEDBACK_MS, lambda: detail_copy_btn.config(text=orig))

        detail_copy_btn.config(command=copy_selected)

        entries = history.list_today()
        if not entries:
            tk.Label(
                inner, text="No transcriptions yet today.", font=frow,
                fg="#888888", bg="#252525", padx=8, pady=12,
            ).pack(fill="x")
        else:
            for entry in entries:
                row = tk.Frame(inner, bg="#2a2a2a", pady=1)
                row.pack(fill="x", padx=4, pady=2)
                ts = history.format_time(entry.get("timestamp", ""))
                snippet = history.preview(entry.get("text", ""))
                tk.Label(
                    row, text=ts, font=frow, fg="#4fc3f7", bg="#2a2a2a",
                    width=10, anchor="w", padx=8, pady=6,
                ).pack(side="left")
                lbl = tk.Label(
                    row, text=snippet, font=fpreview, fg="#cccccc", bg="#2a2a2a",
                    anchor="w", padx=4, pady=6, cursor="hand2",
                )
                lbl.pack(side="left", fill="x", expand=True)
                lbl.bind("<Button-1>", lambda e, ent=entry: select_entry(ent))
                row.bind("<Button-1>", lambda e, ent=entry: select_entry(ent))
                row.bind("<Enter>", lambda e, r=row: r.config(bg="#333333"))
                row.bind("<Leave>", lambda e, r=row: r.config(bg="#2a2a2a"))

        def on_history_close():
            self._history_open = False
            self._history_win = None
            if self._done and not self._history_only:
                self._schedule_auto_close()
            elif self._history_only:
                self._close_now()

        win.protocol("WM_DELETE_WINDOW", lambda: self._close_history_panel(win))
        win.bind("<Destroy>", lambda _: on_history_close())

        win.bind("<Enter>", lambda _: self._set_interacting(True))
        win.bind("<Leave>", lambda _: self._set_interacting(False))

    def _close_history_panel(self, win=None):
        target = win or self._history_win
        if target and target.winfo_exists():
            target.destroy()
        self._history_open = False
        self._history_win = None
        if self._done and not self._history_only:
            self._schedule_auto_close()
        elif self._history_only:
            self._close_now()

    def mainloop(self):
        self._root.mainloop()


def show_history_standalone():
    """Open history UI without an active recording (tray menu entry point)."""
    history.prune_old_entries()
    overlay = Overlay(history_only=True)
    overlay._root.title("Voice Dictation History")
    overlay.mainloop()


if __name__ == "__main__":
    if "--history" in sys.argv:
        show_history_standalone()
    else:
        print("Usage: overlay.py --history", file=sys.stderr)
        sys.exit(1)
