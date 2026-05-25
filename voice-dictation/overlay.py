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
        w, h = 760, 560
        x = (sw - w) // 2
        y = (sh - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

        ftitle = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        ftime = tkfont.Font(family="Segoe UI", size=10)
        ftext = tkfont.Font(family="Segoe UI", size=10)
        fbtn = tkfont.Font(family="Segoe UI", size=9)

        header = tk.Frame(win, bg="#1a1a1a", padx=12, pady=8)
        header.pack(fill="x")
        title_lbl = tk.Label(
            header, text="Today's transcriptions", font=ftitle,
            fg="#4fc3f7", bg="#1a1a1a", cursor="fleur",
        )
        title_lbl.pack(side="left")
        tk.Button(
            header, text="✕", font=fbtn, fg="#cccccc", bg="#333333",
            activebackground="#555555", relief="flat", width=3,
            command=lambda: self._close_history_panel(win),
        ).pack(side="right")

        # Drag-to-move on header (since overrideredirect hides the titlebar)
        drag = {"x": 0, "y": 0}
        def _drag_start(e):
            drag["x"] = e.x_root - win.winfo_x()
            drag["y"] = e.y_root - win.winfo_y()
        def _drag_move(e):
            win.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
        for w_ in (header, title_lbl):
            w_.bind("<Button-1>", _drag_start)
            w_.bind("<B1-Motion>", _drag_move)

        list_frame = tk.Frame(win, bg="#1a1a1a")
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        canvas = tk.Canvas(list_frame, bg="#252525", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#252525")
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        text_labels: list[tk.Label] = []
        TIME_COL = 88
        COPY_COL = 78
        INNER_PAD = 32

        def _on_canvas_resize(event):
            canvas.itemconfigure(inner_id, width=event.width)
            wrap = max(120, event.width - TIME_COL - COPY_COL - INNER_PAD)
            for lbl in text_labels:
                lbl.configure(wraplength=wrap)

        canvas.bind("<Configure>", _on_canvas_resize)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        win.bind_all("<MouseWheel>", _on_mousewheel)

        def _copy_text(text: str, btn: tk.Button):
            if not text:
                return
            pyperclip.copy(text)
            orig = btn.cget("text")
            btn.config(text="Copied!")
            win.after(_COPY_FEEDBACK_MS, lambda: btn.config(text=orig))

        entries = history.list_today()
        if not entries:
            tk.Label(
                inner, text="No transcriptions yet today.", font=ftext,
                fg="#888888", bg="#252525", padx=8, pady=12,
            ).pack(fill="x")
        else:
            for entry in entries:
                full = entry.get("text", "")
                ts = history.format_time(entry.get("timestamp", ""))

                row = tk.Frame(inner, bg="#2a2a2a")
                row.pack(fill="x", padx=4, pady=2)

                tk.Label(
                    row, text=ts, font=ftime, fg="#4fc3f7", bg="#2a2a2a",
                    width=10, anchor="nw", padx=8, pady=8,
                ).pack(side="left", fill="y")

                copy_btn = tk.Button(
                    row, text="Copy", font=fbtn,
                    fg="#e0e0e0", bg="#333333", activebackground="#555555",
                    relief="flat", padx=10, pady=2, cursor="hand2",
                )
                copy_btn.config(command=lambda t=full, b=copy_btn: _copy_text(t, b))
                copy_btn.pack(side="right", padx=(4, 8), pady=8)

                lbl = tk.Label(
                    row, text=full, font=ftext, fg="#e0e0e0", bg="#2a2a2a",
                    anchor="nw", justify="left", padx=4, pady=8, wraplength=400,
                )
                lbl.pack(side="left", fill="x", expand=True)
                text_labels.append(lbl)

        def on_history_close():
            try:
                win.unbind_all("<MouseWheel>")
            except tk.TclError:
                pass
            self._history_open = False
            self._history_win = None
            if self._done and not self._history_only:
                self._schedule_auto_close()
            elif self._history_only:
                self._close_now()

        win.protocol("WM_DELETE_WINDOW", lambda: self._close_history_panel(win))
        win.bind("<Destroy>", lambda e, w_=win: on_history_close() if e.widget is w_ else None)

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
