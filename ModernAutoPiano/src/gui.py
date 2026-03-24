"""
AutoPiano — Synthesia visualizer, borderless modern UI
"""

import customtkinter as ctk
import tkinter as tk
import os, sys, threading, time
import mido

from midi_parser import parse_midi, load_mapping, get_tracks_info
from player import AutoPianoPlayer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Piano range ───────────────────────────────────────────────────────────────
START_MIDI = 36
END_MIDI   = 96
IS_WHITE   = [True,False,True,False,True,True,False,True,False,True,False,True]
NUM_WHITES = sum(1 for n in range(START_MIDI, END_MIDI+1) if IS_WHITE[n%12])

PIANO_H         = 130
LOOKAHEAD_BEATS = 6

# ── Colors ────────────────────────────────────────────────────────────────────
BG       = "#0a0a14"
SURFACE  = "#1e1e2e"
SURFACE2 = "#313244"
MUTED    = "#45475a"
TEXT     = "#cdd6f4"
SUBTEXT  = "#6c7086"
ACCENT   = "#89b4fa"

PIANO_BG  = "#0f0f1c"
WHITE_KEY = "#d0d5e8"
BLACK_KEY = "#0d0d1a"
WHITE_ACT = "#89b4fa"
BLACK_ACT = "#7287fd"
BAR_WHITE = "#89b4fa"
BAR_BLACK = "#7287fd"
BAR_LIGHT = "#b4befe"


def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _extract_bpm(path: str) -> float:
    try:
        for track in mido.MidiFile(path).tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    return float(mido.tempo2bpm(msg.tempo))
    except Exception:
        pass
    return 120.0


# ══════════════════════════════════════════════════════════════════════════════
# Floating search — manages its own widgets on the parent window
# ══════════════════════════════════════════════════════════════════════════════

class FloatingSearch:
    ENTRY_H   = 40
    ENTRY_W   = 420
    ENTRY_Y   = 16
    ITEM_H    = 34
    MAX_ITEMS = 9

    def __init__(self, parent: tk.Misc, on_select):
        self._parent    = parent
        self._on_select = on_select
        self._all:      list[tuple[str, str]] = []
        self._filtered: list[tuple[str, str]] = []
        self._open    = False
        self._is_sel  = False   # entry currently shows a selected filename

        # ── Pill-shaped container ─────────────────────────────────────────────
        self._container = ctk.CTkFrame(
            parent,
            corner_radius=self.ENTRY_H // 2,
            fg_color=SURFACE,
            border_width=1,
            border_color=SURFACE2,
            width=self.ENTRY_W,
            height=self.ENTRY_H,
        )
        self._container.place(relx=0.5, y=self.ENTRY_Y, anchor="n")

        tk.Label(self._container, text="🔍", bg=SURFACE, fg=SUBTEXT,
                 font=("Segoe UI", 10)).place(x=12, y=9)

        self._entry = tk.Entry(
            self._container,
            font=("Segoe UI", 11),
            bg=SURFACE, fg=SUBTEXT,
            insertbackground=TEXT,
            relief="flat", bd=0, highlightthickness=0,
        )
        self._entry.place(x=36, y=7, relwidth=1, width=-48, height=26)
        self._entry.insert(0, "Search MIDI files…")

        self._entry.bind("<FocusIn>",    self._focus_in)
        self._entry.bind("<FocusOut>",   self._focus_out)
        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<Return>",     self._on_return)
        self._entry.bind("<Down>",       self._arrow_down)
        self._entry.bind("<Escape>",     lambda _: parent.focus_set())

        # ── Dropdown ──────────────────────────────────────────────────────────
        self._dropdown = ctk.CTkFrame(
            parent,
            corner_radius=14,
            fg_color=SURFACE,
            border_width=1,
            border_color=SURFACE2,
            width=self.ENTRY_W,
            height=self.ITEM_H,
        )
        self._listbox = tk.Listbox(
            self._dropdown,
            bg=SURFACE, fg=TEXT,
            selectbackground="#1f6aa5", selectforeground=TEXT,
            borderwidth=0, highlightthickness=0,
            font=("Segoe UI", 11),
            activestyle="none",
            cursor="hand2",
        )
        self._listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self._listbox.bind("<ButtonRelease-1>", self._item_click)
        self._listbox.bind("<Return>",           self._item_click)
        self._listbox.bind("<FocusOut>",         self._focus_out)
        self._listbox.bind("<Up>",               self._arrow_up)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_files(self, files: list[tuple[str, str]]):
        self._all      = files
        self._filtered = files[:]

    def update_width(self, window_w: int):
        w = min(self.ENTRY_W, window_w - 40)
        self._container.configure(width=w)
        if self._open:
            self._dropdown.configure(width=w)

    def close_if_open(self) -> bool:
        if self._open:
            self._hide_dropdown()
            self._container.configure(border_color=SURFACE2)
            return True
        return False

    # ── Focus ─────────────────────────────────────────────────────────────────

    def _focus_in(self, _=None):
        # If we're displaying a selected name, clear it so user can type a new search
        if self._is_sel:
            self._entry.config(fg=TEXT)
            self._entry.delete(0, tk.END)
            self._is_sel = False
        elif self._entry.get() == "Search MIDI files…":
            self._entry.config(fg=TEXT)
            self._entry.delete(0, tk.END)
        self._container.configure(border_color=ACCENT)

    def _focus_out(self, _=None):
        self._parent.after(180, self._check_hide)

    def _check_hide(self):
        fw = self._parent.focus_get()
        # Walk hierarchy to see if focus is still inside our widgets
        w = fw
        while w is not None:
            if w is self._dropdown or w is self._container:
                return
            try:
                w = w.master
            except AttributeError:
                break
        self._hide_dropdown()
        self._container.configure(border_color=SURFACE2)
        # Restore placeholder if empty
        if not self._entry.get().strip():
            self._entry.config(fg=SUBTEXT)
            self._entry.insert(0, "Search MIDI files…")

    # ── Typing ────────────────────────────────────────────────────────────────

    def _on_key(self, _=None):
        q = self._entry.get().strip()
        if not q:
            self._hide_dropdown()
            return
        self._filtered = [
            (n, p) for n, p in self._all if q.lower() in n.lower()
        ]
        if not self._filtered:
            self._hide_dropdown()
            return
        self._show_dropdown()

    # ── Dropdown ──────────────────────────────────────────────────────────────

    def _show_dropdown(self):
        w = max(self.ENTRY_W, int(self._container.winfo_width() or self.ENTRY_W))
        n = min(len(self._filtered), self.MAX_ITEMS)
        h = n * self.ITEM_H + 12
        drop_y = self.ENTRY_Y + self.ENTRY_H + 4

        self._listbox.delete(0, tk.END)
        for name, _ in self._filtered[:self.MAX_ITEMS]:
            display = os.path.splitext(name)[0].replace("\\", " / ")
            self._listbox.insert(tk.END, f"  {display}")

        self._dropdown.configure(width=w, height=h)
        self._dropdown.place(relx=0.5, y=drop_y, anchor="n")
        self._dropdown.lift()
        self._open = True

    def _hide_dropdown(self):
        if self._open:
            self._dropdown.place_forget()
            self._open = False

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_return(self, _=None):
        if self._filtered:
            self._select(0)

    def _arrow_down(self, _=None):
        if self._listbox.size() > 0:
            self._listbox.focus_set()
            self._listbox.selection_set(0)
            self._listbox.activate(0)

    def _arrow_up(self, _=None):
        if self._listbox.curselection() == (0,):
            self._entry.focus_set()

    def _item_click(self, _=None):
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._filtered):
            self._select(sel[0])

    def _select(self, idx: int):
        name, path = self._filtered[idx]
        display = os.path.splitext(os.path.basename(name))[0]
        self._entry.config(fg=TEXT)
        self._entry.delete(0, tk.END)
        self._entry.insert(0, display)
        self._is_sel = True
        self._hide_dropdown()
        self._container.configure(border_color=SURFACE2)
        self._parent.focus_set()
        self._on_select(name, path)


# ══════════════════════════════════════════════════════════════════════════════
# Main window
# ══════════════════════════════════════════════════════════════════════════════

class AutoPianoGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)   # borderless

        W, H = 1000, 680
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.minsize(700, 500)
        self.configure(fg_color=BG)

        self._drag_x = self._drag_y = 0
        self._rsz_w  = self._rsz_h  = 0
        self._rsz_x0 = self._rsz_y0 = 0

        base = _get_base_dir()
        self.midi_dir    = os.path.join(os.path.dirname(base), "Midi")
        self.config_path = os.path.join(base, "config", "mappings.json")

        try:
            self.mapping_str = load_mapping(self.config_path)
        except Exception:
            self.mapping_str = ""

        self.char_to_note: dict[str, int] = {}
        for i, ch in enumerate(self.mapping_str):
            n = START_MIDI + i
            if n <= END_MIDI:
                self.char_to_note[ch] = n

        self.all_files:   list = []
        self.events:      list = []
        self.abs_times:   list = []
        self.note_segs:   list = []
        self.active_notes: set = set()
        self.player        = AutoPianoPlayer(on_event=self._on_player_event)
        self.bpm           = 120.0
        self.practice_mode = False

        self.current_t       = 0.0
        self.play_start_wall = 0.0
        self.play_start_midi = 0.0
        self._animating      = False

        self._cw = W;  self._ch = H
        self._ww = 0.0; self._bw = 0.0; self._bh = 0.0
        self._pps   = 180.0
        self._key_x: dict[int, float] = {}

        self._build_ui()
        self.after(60,  self._init_geometry)
        self.after(120, self._apply_win_style)
        self._scan_midi_files()

        self.bind("<Delete>", lambda _: self._toggle_play())
        self.bind("<Escape>", lambda _: self._on_escape())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Win API tweaks ────────────────────────────────────────────────────────

    def _apply_win_style(self):
        """Make borderless window appear in taskbar."""
        try:
            import ctypes
            self.update()
            hwnd = self.winfo_id()
            p = ctypes.windll.user32.GetParent(hwnd)
            if p:
                hwnd = p
            GWL_EXSTYLE     = -20
            WS_EX_APPWINDOW = 0x40000
            WS_EX_TOOLWINDOW = 0x80
            s = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, (s & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW)
            ctypes.windll.user32.SetWindowPos(
                hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception:
            pass

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Main canvas — fills the whole window, acts as background
        self.cv = tk.Canvas(self, bg=BG, bd=0, highlightthickness=0)
        self.cv.place(x=0, y=0, relwidth=1, relheight=1)
        self.cv.bind("<Configure>", self._on_resize)
        self.cv.bind("<Button-1>",  self._drag_start)
        self.cv.bind("<B1-Motion>", self._drag)

        # 3px progress strip above piano
        self.prog = tk.Canvas(self, bg=MUTED, bd=0, highlightthickness=0, height=3)
        self.prog.place(x=0, rely=1.0, y=-(PIANO_H + 40), relwidth=1)

        # ── Floating search ────────────────────────────────────────────────────
        self.search = FloatingSearch(self, on_select=self._load_file)

        # ── Info labels (below search) ────────────────────────────────────────
        self.lbl_title = tk.Label(self, text="", bg=BG, fg=ACCENT,
                                  font=("Segoe UI", 14, "bold"))
        self.lbl_title.place(relx=0.5, y=68, anchor="n")
        self.lbl_title.bind("<Button-1>",  self._drag_start)
        self.lbl_title.bind("<B1-Motion>", self._drag)

        self.lbl_sub = tk.Label(
            self, text="Click the search bar to find a MIDI file",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.lbl_sub.place(relx=0.5, y=92, anchor="n")
        self.lbl_sub.bind("<Button-1>",  self._drag_start)
        self.lbl_sub.bind("<B1-Motion>", self._drag)

        # ── Controls (centered, just above piano) ─────────────────────────────
        ctrl = tk.Frame(self, bg=BG)
        ctrl.place(relx=0.5, rely=1.0, y=-(PIANO_H + 14), anchor="s")

        self.play_btn = ctk.CTkButton(
            ctrl, text="▶  Play",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=20, height=40, width=128,
            command=self._toggle_play)
        self.play_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ctrl, text="■  Stop",
            font=ctk.CTkFont(size=11),
            corner_radius=20, height=40, width=100,
            fg_color=MUTED, hover_color=SURFACE2,
            command=self._stop,
        ).pack(side="left", padx=(0, 8))

        self.practice_btn = ctk.CTkButton(
            ctrl, text="🎓  Learn",
            font=ctk.CTkFont(size=11),
            corner_radius=20, height=40, width=110,
            fg_color=SURFACE2, hover_color=SURFACE,
            text_color=SUBTEXT,
            command=self._toggle_practice,
        )
        self.practice_btn.pack(side="left", padx=(0, 12))

        self.lbl_status = tk.Label(ctrl, text="", bg=BG, fg=SUBTEXT,
                                   font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")

        # ── Window controls (top-right, created last → on top) ────────────────
        ctk.CTkButton(
            self, text="×",
            width=26, height=26, corner_radius=13,
            font=ctk.CTkFont(size=14),
            fg_color=SURFACE2, hover_color="#f38ba8", text_color=SUBTEXT,
            command=self._on_close,
        ).place(relx=1.0, x=-12, y=12, anchor="ne")

        ctk.CTkButton(
            self, text="−",
            width=26, height=26, corner_radius=13,
            font=ctk.CTkFont(size=14),
            fg_color=SURFACE2, hover_color=SURFACE, text_color=SUBTEXT,
            command=self._minimize,
        ).place(relx=1.0, x=-44, y=12, anchor="ne")

        # ── Resize grip (bottom-right) ────────────────────────────────────────
        grip = tk.Frame(self, bg=SURFACE2, cursor="size_nw_se",
                        width=14, height=14)
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<Button-1>",  self._rsz_start)
        grip.bind("<B1-Motion>", self._rsz_drag)

    def _init_geometry(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1:
            self._compute_keys(w, h)
            self._draw_frame()

    # ── Window chrome ─────────────────────────────────────────────────────────

    def _drag_start(self, ev):
        self._drag_x = ev.x_root - self.winfo_x()
        self._drag_y = ev.y_root - self.winfo_y()

    def _drag(self, ev):
        self.geometry(f"+{ev.x_root - self._drag_x}+{ev.y_root - self._drag_y}")

    def _rsz_start(self, ev):
        self._rsz_w  = self.winfo_width()
        self._rsz_h  = self.winfo_height()
        self._rsz_x0 = ev.x_root
        self._rsz_y0 = ev.y_root

    def _rsz_drag(self, ev):
        w = max(700, self._rsz_w + ev.x_root - self._rsz_x0)
        h = max(500, self._rsz_h + ev.y_root - self._rsz_y0)
        self.geometry(f"{w}x{h}")

    def _minimize(self):
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(self.winfo_id(), 6)  # SW_MINIMIZE
        except Exception:
            self.iconify()

    # ── Resize & key geometry ─────────────────────────────────────────────────

    def _on_resize(self, ev):
        self._compute_keys(ev.width, ev.height)
        self.search.update_width(ev.width)
        if not self._animating:
            self._draw_frame()

    def _compute_keys(self, w: int, h: int):
        self._cw, self._ch = w, h
        self._ww = w / NUM_WHITES
        self._bw = self._ww * 0.58
        self._bh = PIANO_H * 0.63
        self._key_x.clear()
        wi = 0
        for n in range(START_MIDI, END_MIDI + 1):
            if IS_WHITE[n % 12]:
                self._key_x[n] = wi * self._ww
                wi += 1
        for n in range(START_MIDI, END_MIDI + 1):
            if not IS_WHITE[n % 12] and (n - 1) in self._key_x:
                self._key_x[n] = self._key_x[n - 1] + self._ww - self._bw / 2
        self._update_pps()

    def _update_pps(self):
        avail = self._ch - PIANO_H
        if avail > 0 and self.bpm > 0:
            self._pps = avail / (LOOKAHEAD_BEATS * 60.0 / self.bpm)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_frame(self):
        cv = self.cv
        cv.delete("all")
        w, h = self._cw, self._ch
        if w < 10 or h < 10 or not self._key_x:
            return

        piano_top = h - PIANO_H
        ct  = self.current_t
        pps = self._pps

        cv.create_rectangle(0, 0, w, h, fill=BG, outline="")

        # Falling note bars
        for on_t, off_t, char in self.note_segs:
            note = self.char_to_note.get(char)
            if note is None:
                continue
            x = self._key_x.get(note)
            if x is None:
                continue
            is_w  = IS_WHITE[note % 12]
            bar_w = (self._ww - 2) if is_w else self._bw
            color = BAR_WHITE if is_w else BAR_BLACK
            bot   = piano_top - (on_t  - ct) * pps
            top   = piano_top - (off_t - ct) * pps
            if bot < 0 or top > piano_top:
                continue
            bot = min(bot, piano_top)
            top = max(top, 0)
            if bot - top < 1:
                continue
            bx = x + 1
            cv.create_rectangle(bx, top, bx + bar_w - 1, bot, fill=color, outline="")
            cv.create_line(bx + 1, top + 1, bx + 1, bot - 1, fill=BAR_LIGHT, width=1)

        # Octave guide lines
        for n in range(START_MIDI, END_MIDI + 1, 12):
            x = self._key_x.get(n, 0)
            cv.create_line(x, 0, x, piano_top - 2, fill=SURFACE, width=1)

        # Hit line
        cv.create_rectangle(0, piano_top - 2, w, piano_top, fill=SURFACE2, outline="")

        # Piano background
        cv.create_rectangle(0, piano_top, w, h, fill=PIANO_BG, outline="")

        ww, bw, bh = self._ww, self._bw, self._bh

        # White keys
        for n in range(START_MIDI, END_MIDI + 1):
            if not IS_WHITE[n % 12]:
                continue
            x   = self._key_x.get(n, 0)
            act = n in self.active_notes
            cv.create_rectangle(x + 1, piano_top + 2, x + ww - 1, h - 3,
                                 fill=(WHITE_ACT if act else WHITE_KEY),
                                 outline=PIANO_BG)
            if act:
                cv.create_rectangle(x + 1, piano_top + 2, x + ww - 1,
                                     piano_top + 12, fill=ACCENT, outline="")

        # Black keys
        for n in range(START_MIDI, END_MIDI + 1):
            if IS_WHITE[n % 12]:
                continue
            x   = self._key_x.get(n, 0)
            act = n in self.active_notes
            cv.create_rectangle(x, piano_top + 2, x + bw, piano_top + bh,
                                 fill=(BLACK_ACT if act else BLACK_KEY),
                                 outline=PIANO_BG)

        # Key labels (drawn last so they sit on top of everything)
        fs_w = max(7, min(11, int(ww * 0.38)))   # font size for white keys
        fs_b = max(6, fs_w - 1)                   # slightly smaller for black

        for n in range(START_MIDI, END_MIDI + 1):
            idx = n - START_MIDI
            if idx < 0 or idx >= len(self.mapping_str):
                continue
            x   = self._key_x.get(n)
            if x is None:
                continue
            char = self.mapping_str[idx]
            act  = n in self.active_notes

            if IS_WHITE[n % 12]:
                cx   = x + ww / 2
                cy   = h - 10
                fill = "#1a1a2e" if act else "#909090"
                cv.create_text(cx, cy, text=char, fill=fill,
                               font=("Segoe UI", fs_w, "bold"))
            else:
                cx   = x + bw / 2
                cy   = piano_top + bh - 9
                fill = "#e0e0ff" if act else "#666677"
                cv.create_text(cx, cy, text=char, fill=fill,
                               font=("Segoe UI", fs_b))

    def _animate(self):
        if not self._animating:
            return
        if self.player.is_playing:
            self.current_t = self.play_start_midi + (time.time() - self.play_start_wall)
        self._draw_frame()
        self._update_progress()
        self.after(33, self._animate)

    def _update_progress(self):
        total = self.abs_times[-1] if self.abs_times else 0
        frac  = min(1.0, self.current_t / total) if total > 0 else 0
        pw    = self.prog.winfo_width()
        self.prog.delete("all")
        if pw > 0:
            self.prog.create_rectangle(0, 0, int(pw * frac), 3,
                                        fill=ACCENT, outline="")

    # ── Player event callback ─────────────────────────────────────────────────

    def _on_player_event(self, action: str, char: str):
        note = self.char_to_note.get(char)
        if note is None:
            return
        if action == "down":
            self.active_notes.add(note)
        else:
            self.active_notes.discard(note)

    # ── File scanning ─────────────────────────────────────────────────────────

    def _scan_midi_files(self):
        self.all_files.clear()
        if not os.path.exists(self.midi_dir):
            self._set_sub(f"MIDI folder not found: {self.midi_dir}")
            return
        for root, dirs, files in os.walk(self.midi_dir):
            dirs.sort()
            for f in sorted(files):
                if f.lower().endswith((".mid", ".midi")):
                    full = os.path.join(root, f)
                    self.all_files.append(
                        (os.path.relpath(full, self.midi_dir), full))
        self.search.set_files(self.all_files)
        self._set_sub(f"{len(self.all_files)} files — use the search bar to begin")

    # ── File loading ──────────────────────────────────────────────────────────

    def _load_file(self, name: str, path: str):
        display = os.path.splitext(os.path.basename(name))[0]
        self.lbl_title.configure(text=display)
        self._set_sub("Loading…")
        self._status("Loading…")

        def work():
            try:
                bpm     = _extract_bpm(path)
                tracks  = get_tracks_info(path)
                indices = [i for i, t in enumerate(tracks)
                           if t["is_piano"] and not t["is_drum"]]
                if not indices:
                    indices = [i for i, t in enumerate(tracks)
                               if not t["is_drum"]]
                mapping = load_mapping(self.config_path)
                events  = parse_midi(path, mapping, indices)
                self.after(0, lambda: self._file_loaded(events, bpm))
            except Exception as e:
                self.after(0, lambda: self._set_sub(f"Error: {e}"))
                self.after(0, lambda: self._status("Error"))

        threading.Thread(target=work, daemon=True).start()

    def _file_loaded(self, events: list, bpm: float):
        self.events = events
        self.bpm    = bpm

        t = 0.0
        self.abs_times = []
        for wait, _, _ in events:
            t += wait
            self.abs_times.append(t)

        # Build note segments for falling bars
        self.note_segs = []
        pending: dict[str, float] = {}
        for i, (_, action, char) in enumerate(events):
            at = self.abs_times[i]
            if action == "down":
                pending[char] = at
            elif action == "up" and char in pending:
                self.note_segs.append((pending.pop(char), at, char))
        last = self.abs_times[-1] if self.abs_times else 0
        for char, st in pending.items():
            self.note_segs.append((st, last, char))

        self._update_pps()
        dur = self.abs_times[-1] if self.abs_times else 0
        self._set_sub(f"{len(events)} events · {dur:.0f}s · {bpm:.0f} BPM")
        self._status("Ready")
        self._start_playback()

    # ── Playback ──────────────────────────────────────────────────────────────

    def _toggle_practice(self):
        self.practice_mode = not self.practice_mode
        self.player.practice_mode = self.practice_mode
        if self.practice_mode:
            self.practice_btn.configure(
                text="🤖  Auto", fg_color="#2a4a2e", hover_color="#1a3a1e",
                text_color="#a6e3a1")
        else:
            self.practice_btn.configure(
                text="🎓  Learn", fg_color=SURFACE2, hover_color=SURFACE,
                text_color=SUBTEXT)

    def _start_playback(self):
        self.player.stop()
        self.player          = AutoPianoPlayer(on_event=self._on_player_event)
        self.player.practice_mode = self.practice_mode
        self.active_notes.clear()
        self.current_t       = 0.0
        self.play_start_midi = 0.0
        self.play_start_wall = time.time()
        self.player.play(self.events)
        self.play_btn.configure(text="⏸  Pause")
        self._status("Playing")
        self._animating = True
        self._animate()

    def _toggle_play(self):
        if not self.events:
            return
        if self.player.is_playing:
            idx = self.player.current_index
            self.current_t = (self.abs_times[idx]
                              if idx < len(self.abs_times) else self.current_t)
            self.player.stop()
            self.active_notes.clear()
            self._animating = False
            self._draw_frame()
            self.play_btn.configure(text="▶  Play")
            self._status("Paused")
        else:
            idx = self.player.current_index
            self.play_start_midi = (self.abs_times[idx]
                                    if idx < len(self.abs_times) else self.current_t)
            self.play_start_wall = time.time()
            self.player.play(self.events)
            self.play_btn.configure(text="⏸  Pause")
            self._status("Playing…")
            self._animating = True
            self._animate()

    def _stop(self):
        self.player.stop()
        self.player.current_index = 0
        self.active_notes.clear()
        self.current_t = 0.0
        self._animating = False
        self._draw_frame()
        self._update_progress()
        self.play_btn.configure(text="▶  Play")
        self._status("Stopped")

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        self.lbl_status.configure(text=msg)

    def _set_sub(self, msg: str):
        self.lbl_sub.configure(text=msg)

    def _on_escape(self):
        if not self.search.close_if_open():
            self._on_close()

    def _on_close(self):
        self._animating = False
        self.player.stop()
        self.destroy()


def main():
    app = AutoPianoGUI()
    app.mainloop()