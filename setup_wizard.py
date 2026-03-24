"""
AutoPiano Setup Wizard
A self-contained tkinter wizard (no external deps required to run this).
"""
import tkinter as tk
from tkinter import ttk
import subprocess, sys, os, threading, platform

BG      = "#0a0a14"
SURFACE = "#1e1e2e"
S2      = "#313244"
ACCENT  = "#89b4fa"
TEXT    = "#cdd6f4"
MUTED   = "#6c7086"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQ_FILE = os.path.join(BASE_DIR, "ModernAutoPiano", "requirements.txt")
LAUNCHER = os.path.join(BASE_DIR, "AutoPiano.bat")


def create_launcher():
    with open(LAUNCHER, "w") as f:
        f.write('@echo off\ncd /d "%~dp0"\nstart "" pythonw ModernAutoPiano\\run.py\n')


class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoPiano Setup")
        self.configure(bg=BG)
        self.resizable(False, False)
        W, H = 560, 420
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._step = 0   # 0=welcome, 1=installing, 2=done/error
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header strip
        hdr = tk.Frame(self, bg=SURFACE, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="AutoPiano", bg=SURFACE, fg=ACCENT,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=24, pady=18)
        tk.Label(hdr, text="Setup Wizard", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 13)).pack(side="left", pady=22)

        # Step indicator
        steps_frame = tk.Frame(self, bg=BG)
        steps_frame.pack(fill="x", padx=24, pady=(16, 0))
        self._step_labels = []
        for i, name in enumerate(["Welcome", "Install", "Done"]):
            col = tk.Frame(steps_frame, bg=BG)
            col.pack(side="left", expand=True)
            dot = tk.Label(col, text="●", bg=BG,
                           fg=ACCENT if i == 0 else MUTED,
                           font=("Segoe UI", 10))
            dot.pack()
            lbl = tk.Label(col, text=name, bg=BG,
                           fg=TEXT if i == 0 else MUTED,
                           font=("Segoe UI", 9))
            lbl.pack()
            self._step_labels.append((dot, lbl))
            if i < 2:
                tk.Label(steps_frame, text="────", bg=BG, fg=MUTED,
                         font=("Segoe UI", 9)).pack(side="left", expand=True)

        # Content area (swapped per step)
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True, padx=24, pady=12)

        # Button row
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(0, 20))
        self._btn_cancel = tk.Button(
            btn_row, text="Cancel", bg=S2, fg=MUTED,
            font=("Segoe UI", 10), relief="flat", bd=0,
            padx=20, pady=8, cursor="hand2",
            activebackground=S2, activeforeground=TEXT,
            command=self.destroy)
        self._btn_cancel.pack(side="left")

        self._btn_next = tk.Button(
            btn_row, text="Install  →", bg=ACCENT, fg=BG,
            font=("Segoe UI", 11, "bold"), relief="flat", bd=0,
            padx=24, pady=8, cursor="hand2",
            activebackground="#6f9fe0", activeforeground=BG,
            command=self._next)
        self._btn_next.pack(side="right")

        self._show_welcome()

    def _set_step(self, idx: int):
        self._step = idx
        for i, (dot, lbl) in enumerate(self._step_labels):
            if i < idx:
                dot.configure(fg=GREEN); lbl.configure(fg=GREEN)
            elif i == idx:
                dot.configure(fg=ACCENT); lbl.configure(fg=TEXT)
            else:
                dot.configure(fg=MUTED); lbl.configure(fg=MUTED)

    # ── Step 0: Welcome ───────────────────────────────────────────────────────

    def _show_welcome(self):
        for w in self._content.winfo_children():
            w.destroy()
        self._set_step(0)

        tk.Label(self._content, text="Welcome!", bg=BG, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 4))
        tk.Label(
            self._content,
            text=(
                "This wizard will install the Python dependencies\n"
                "required by AutoPiano and create a launch shortcut.\n\n"
                "Requirements:\n"
                "  • Python 3.10 or newer  (already running ✓)\n"
                "  • Internet connection for pip packages\n\n"
                "The following packages will be installed:\n"
                "  mido · python-rtmidi · pynput · customtkinter"
            ),
            bg=BG, fg=TEXT, font=("Segoe UI", 11),
            justify="left"
        ).pack(anchor="w", pady=4)

        py_ver = sys.version.split()[0]
        ok = sys.version_info >= (3, 10)
        ver_color = GREEN if ok else RED
        tk.Label(self._content, text=f"Python {py_ver} detected",
                 bg=BG, fg=ver_color, font=("Segoe UI", 10, "italic")
                 ).pack(anchor="w", pady=(8, 0))

        self._btn_next.configure(text="Install  →",
                                 state="normal" if ok else "disabled")

    # ── Step 1: Installing ────────────────────────────────────────────────────

    def _show_install(self):
        for w in self._content.winfo_children():
            w.destroy()
        self._set_step(1)
        self._btn_next.configure(state="disabled", text="Installing…")
        self._btn_cancel.configure(state="disabled")

        tk.Label(self._content, text="Installing packages…", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(4, 8))

        self._progress = ttk.Progressbar(self._content, mode="indeterminate",
                                         length=500)
        # Style the progressbar
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TProgressbar", troughcolor=S2,
                        background=ACCENT, thickness=6)
        self._progress.pack(fill="x", pady=(0, 10))
        self._progress.start(12)

        log_frame = tk.Frame(self._content, bg=S2, bd=0)
        log_frame.pack(fill="both", expand=True)
        self._log = tk.Text(
            log_frame, bg=S2, fg=TEXT, font=("Consolas", 9),
            relief="flat", bd=0, state="disabled",
            wrap="word", highlightthickness=0)
        sb = tk.Scrollbar(log_frame, command=self._log.yview, bg=S2,
                          troughcolor=S2, bd=0)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(fill="both", expand=True, padx=8, pady=8)

        threading.Thread(target=self._run_install, daemon=True).start()

    def _log_append(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _run_install(self):
        self._log_append(f"python -m pip install -r {REQ_FILE}\n\n")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", REQ_FILE],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in proc.stdout:
                self.after(0, self._log_append, line)
            proc.wait()
            success = proc.returncode == 0
        except Exception as e:
            self.after(0, self._log_append, f"\nError: {e}\n")
            success = False

        if success:
            try:
                create_launcher()
                self.after(0, self._log_append,
                           f"\nLauncher created: {LAUNCHER}\n")
            except Exception as e:
                self.after(0, self._log_append,
                           f"\nWarning: could not create launcher: {e}\n")

        self.after(0, self._install_done, success)

    def _install_done(self, success: bool):
        self._progress.stop()
        self._show_done(success)

    # ── Step 2: Done ──────────────────────────────────────────────────────────

    def _show_done(self, success: bool):
        for w in self._content.winfo_children():
            w.destroy()
        self._set_step(2)

        if success:
            tk.Label(self._content, text="✓  Setup complete!", bg=BG, fg=GREEN,
                     font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 6))
            tk.Label(
                self._content,
                text=(
                    "All dependencies are installed.\n\n"
                    f"A launcher has been created:\n  {LAUNCHER}\n\n"
                    "Double-click AutoPiano.bat to start the app."
                ),
                bg=BG, fg=TEXT, font=("Segoe UI", 11), justify="left"
            ).pack(anchor="w")
            self._btn_next.configure(
                text="Launch now  ▶", state="normal",
                command=self._launch_and_exit)
        else:
            tk.Label(self._content, text="✗  Installation failed", bg=BG, fg=RED,
                     font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 6))
            tk.Label(
                self._content,
                text=(
                    "Something went wrong. Check the log above for details.\n\n"
                    "Common fixes:\n"
                    "  • Run this wizard as Administrator\n"
                    "  • Check your internet connection\n"
                    "  • Run:  python -m pip install -r ModernAutoPiano\\requirements.txt"
                ),
                bg=BG, fg=TEXT, font=("Segoe UI", 11), justify="left"
            ).pack(anchor="w")
            self._btn_next.configure(text="Close", state="normal",
                                     command=self.destroy)

        self._btn_cancel.configure(state="normal", text="Close",
                                   command=self.destroy)

    def _launch_and_exit(self):
        try:
            os.startfile(LAUNCHER)
        except Exception:
            subprocess.Popen(
                [sys.executable,
                 os.path.join(BASE_DIR, "ModernAutoPiano", "run.py")],
                creationflags=0x00000008  # DETACHED_PROCESS
            )
        self.destroy()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _next(self):
        if self._step == 0:
            self._show_install()


if __name__ == "__main__":
    app = SetupWizard()
    app.mainloop()