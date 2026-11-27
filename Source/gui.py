"""Tkinter board and public deduction inspector; no access to hidden puzzle data."""

from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import monotonic
import tkinter as tk
from tkinter import ttk
from random import choice
from tkinter.scrolledtext import ScrolledText

import agent
import encoder
from ui_fonts import UIFonts
from ui_text import VERDICTS, EMPTY_TRACE, clue_text, feedback_text
from engine import GameEngine
from card_widgets import (SuspectCard, portrait, BACKGROUND, SURFACE, TEXT,
                          MUTED, BORDER, GREEN, RED, GOLD)


PUZZLES = Path(__file__).resolve().parent / "puzzles"
SIZE_PUZZLES = {
    "3 × 3": ("sample_3x3.json", "puzzle_3x3_02.json"),
    "4 × 4": ("puzzle_4x4_01.json", "puzzle_4x4_02.json"),
    "5 × 5": ("puzzle_5x5_stress.json", "puzzle_5x5_02.json"),
}
BG = BACKGROUND
INK = TEXT
BLUE = GOLD


class GriductiveApp:
    def __init__(self, root, puzzle=None):
        self.root = root
        self.engine = None
        self.current_path = None
        self.toast_job = None
        self.marked = set()
        self.analysis_visible = False
        self.verdict_dialog = None
        self.statistics_dialog = None
        self.log_visible = False
        self.started_at = monotonic()
        self.finished_at = None
        self.timer_job = None
        self.state = None
        self.selected = None
        self.highlights = set()
        self.trace = []
        self.events = []
        self.clues = []
        self.cards = {}
        self.busy = False
        self.closed = False
        self.results = Queue()
        self.controls = []
        self.auto_job = None
        self.scroll_job = None
        self.auto_running = False
        self.run_totals = {"sat_calls": 0, "decisions": 0, "propagations": 0,
                           "backtracks": 0, "runtime_ms": 0.0}
        root.title("Griductive")
        root.geometry("1120x900")
        root.minsize(940, 760)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.fonts = UIFonts(root)
        self._style()
        self._build()
        self._tick_clock()
        self.poll_job = root.after(60, self._poll)
        root.bind("<Escape>", lambda event: self.stop_auto())
        if puzzle:
            self.load(Path(puzzle))
        else:
            self.load(PUZZLES / SIZE_PUZZLES["3 × 3"][0])

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=self.fonts.body, background=BG, foreground=INK)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=self.fonts.title)
        style.configure("Heading.TLabel", font=self.fonts.heading)
        style.configure("TButton", padding=(13, 8), background=SURFACE, foreground=INK,
                        bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE, borderwidth=1)
        style.map("TButton", background=[("active", "#40372f"), ("disabled", "#29241f")],
                  foreground=[("disabled", "#72695e")])
        style.configure("Accent.TButton", background="#344539", foreground=GREEN, bordercolor=GREEN)
        style.configure("Danger.TButton", background="#49302c", foreground=RED, bordercolor=RED)
        style.configure("TCheckbutton", background=BG, foreground=INK)
        style.map("TCheckbutton", background=[("active", SURFACE)])
        style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                        foreground=INK, arrowcolor=MUTED, bordercolor=BORDER, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)],
                  selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", INK)])
        self.root.option_add("*TCombobox*Listbox.background", SURFACE)
        self.root.option_add("*TCombobox*Listbox.foreground", INK)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#4b4339")
        style.configure("Treeview", rowheight=max(34, self.fonts.body.metrics("linespace") + 16), fieldbackground=SURFACE, background=SURFACE,
                        foreground=INK, bordercolor=BORDER)
        style.configure("Treeview.Heading", background="#38302a", foreground=MUTED,
                        font=self.fonts.heading, relief="flat")
        style.map("Treeview", background=[("selected", "#4b4939")], foreground=[("selected", INK)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 10), background=BG, foreground=MUTED)
        style.map("TNotebook.Tab", background=[("selected", SURFACE)], foreground=[("selected", INK)])
        style.configure("TPanedwindow", background=BG)
        style.configure("TScrollbar", background=SURFACE, troughcolor=BG, arrowcolor=MUTED,
                        borderwidth=0, width=10)
        style.configure("Horizontal.TProgressbar", background=GREEN, troughcolor=SURFACE,
                        borderwidth=0, thickness=3)

    def _button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append(button)
        return button

    def _text(self, parent, **kwargs):
        widget = ScrolledText(parent, wrap="word", relief="flat", padx=14, pady=12,
                              bg=SURFACE, fg=INK, insertbackground=INK,
                              selectbackground="#4c5744", **kwargs)
        widget.vbar.configure(bg=SURFACE, troughcolor=BG, activebackground=BORDER,
                              highlightthickness=0, bd=0)
        return widget

    def _build(self):
        shell = ttk.Frame(self.root, padding=(28, 16, 28, 16))
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Griductive", style="Title.TLabel").pack(side="left")
        ttk.Button(header, text="Cách chơi", command=self.show_help).pack(side="right", padx=(10, 0))
        self.analysis_button = ttk.Button(header, text="Xem suy luận", command=self.toggle_analysis)
        self.analysis_button.pack(side="right", padx=(10, 0))
        self.clock = tk.StringVar(value="00:00")
        ttk.Label(header, textvariable=self.clock, font=self.fonts.clock).pack(side="right", padx=14)
        tk.Frame(shell, height=1, bg="#39312b").pack(fill="x")
        toolbar = ttk.Frame(shell, padding=(0, 12, 0, 12))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Kích thước", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        self.size_name = tk.StringVar(value="3 × 3")
        self.size_picker = ttk.Combobox(toolbar, textvariable=self.size_name, state="readonly",
                                        values=list(SIZE_PUZZLES), width=9)
        self.size_picker.pack(side="left", padx=(0, 8))
        self.size_picker.bind("<<ComboboxSelected>>", lambda event: self.new_game())
        self._button(toolbar, "Ván mới", self.new_game).pack(side="left", padx=3)
        self._button(toolbar, "Chơi lại", self.restart).pack(side="left", padx=3)

        self.panes = ttk.Panedwindow(shell, orient="horizontal")
        self.panes.pack(fill="both", expand=True)
        left = ttk.Frame(self.panes)
        self.inspector = ttk.Frame(self.panes, width=370, padding=(18, 0, 0, 0))
        self.panes.add(left, weight=3)
        self.board_guidance = tk.StringVar()
        self.board_guidance_label = ttk.Label(left, textvariable=self.board_guidance,
                                              style="Muted.TLabel", anchor="center", justify="center",
                                              wraplength=650)
        self.board_guidance_label.pack(fill="x", pady=(0, 10))
        board_outer = ttk.Frame(left)
        board_outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(board_outer, bg=BG, highlightthickness=0, width=650, height=470)
        scroll_y = ttk.Scrollbar(board_outer, orient="vertical", command=self.canvas.yview)
        scroll_x = ttk.Scrollbar(board_outer, orient="horizontal", command=self.canvas.xview)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.board = tk.Frame(self.canvas, bg=BG)
        self.board_window = self.canvas.create_window(0, 0, window=self.board, anchor="nw")
        self.board.bind("<Configure>", lambda event: self._layout_board())
        self.canvas.bind("<Configure>", self._resize_board)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.mark_mode = tk.BooleanVar(value=False)
        self.mark_mode.trace_add("write", lambda *args: self._update_board_guidance())
        self._update_board_guidance()
        actions = ttk.Frame(left, padding=(0, 12, 0, 8))
        actions.pack(anchor="center")
        marking = ttk.Frame(actions)
        marking.pack(pady=(0, 8))
        self.mark_button = ttk.Checkbutton(marking, text="Đánh dấu thẻ", variable=self.mark_mode)
        self.mark_button.pack(side="left", padx=7)
        hint_button = self._button(marking, "Gợi ý", self.show_hint)
        hint_button.pack(side="left", padx=5)
        solving = ttk.Frame(actions)
        solving.pack()
        step_button = self._button(solving, "Giải một bước", self.next_step)
        step_button.pack(side="left", padx=5)
        auto_button = self._button(solving, "Tự động giải", self.start_auto, style="Accent.TButton")
        auto_button.pack(side="left", padx=5)
        self.game_controls = [hint_button, step_button, auto_button, self.mark_button]
        self.stop_button = ttk.Button(solving, text="Dừng giải", command=self.stop_auto, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        inspector_actions = ttk.Frame(self.inspector, padding=(8, 0, 8, 12))
        inspector_actions.pack(fill="x")
        ttk.Button(inspector_actions, text="Xem thống kê", command=self.show_statistics).pack(side="left")
        self.log_button = ttk.Button(inspector_actions, text="Xem nhật ký", command=self.toggle_log)
        self.log_button.pack(side="left", padx=(8, 0))
        self.tabs = ttk.Notebook(self.inspector)
        self.tabs.pack(fill="both", expand=True)
        clue_tab = ttk.Frame(self.tabs, padding=8)
        trace_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(clue_tab, text="Manh mối")
        self.tabs.add(trace_tab, text="Các bước giải")
        ttk.Label(clue_tab, text="Chọn một manh mối để xem các ô liên quan.", wraplength=330,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        clue_list = ttk.Frame(clue_tab)
        clue_list.pack(fill="both", expand=True)
        self.clue_tree = ttk.Treeview(clue_list, columns=("cell", "type"), show="headings", height=5)
        for key, title, width in (("cell", "Ô", 50), ("type", "Nội dung", 240)):
            self.clue_tree.heading(key, text=title)
            self.clue_tree.column(key, width=width, minwidth=40)
        self._scroll_tree(clue_list, self.clue_tree)
        self.clue_tree.bind("<<TreeviewSelect>>", self.select_clue)
        self.clue_detail = self._text(clue_tab, height=7, font=self.fonts.body)
        self.clue_detail.pack(fill="both", expand=True, pady=(10, 0))
        self._write(self.clue_detail, "Chưa chọn manh mối.")
        self._button(clue_tab, "Bỏ tô sáng", self.clear_highlights).pack(anchor="w", pady=(8, 0))
        ttk.Label(trace_tab, text="Chọn một bước để xem chi tiết.",
                  style="Muted.TLabel", wraplength=330).pack(fill="x", pady=(0, 10))
        trace_list = ttk.Frame(trace_tab)
        trace_list.pack(fill="x")
        self.trace_tree = ttk.Treeview(trace_list, columns=("step", "cell", "verdict"), show="headings", height=5)
        for key, title, width in (("step", "Bước", 45), ("cell", "Ô", 45), ("verdict", "Kết luận", 190)):
            self.trace_tree.heading(key, text=title)
            self.trace_tree.column(key, width=width, minwidth=35)
        self._scroll_tree(trace_list, self.trace_tree)
        self.trace_tree.tag_configure("innocent", foreground=GREEN)
        self.trace_tree.tag_configure("criminal", foreground=RED)
        self.trace_tree.bind("<<TreeviewSelect>>", self.select_trace)
        self.trace_detail = self._text(trace_tab, height=10, font=self.fonts.body, spacing1=3, spacing3=7)
        self.trace_detail.tag_configure("heading", font=self.fonts.section, foreground=GOLD, spacing1=10)
        self.trace_detail.tag_configure("query", font=self.fonts.query, spacing3=5)
        self.trace_detail.tag_configure("unsat", foreground=GREEN)
        self.trace_detail.tag_configure("muted", foreground=MUTED)
        self.trace_detail.pack(fill="both", expand=True, pady=(10, 0))
        self._write(self.trace_detail, EMPTY_TRACE)
        self.event_text = self._text(trace_tab, height=4, font=self.fonts.body)
        self._write(self.event_text, "Nhật ký thao tác")
        self.message = tk.StringVar(value="Sẵn sàng")
        # Feedback is transient and overlays the board; no persistent footer text.
        self.toast = tk.Label(self.root, bg=SURFACE, fg=INK, padx=18, pady=10,
                              font=self.fonts.body, wraplength=700, justify="center",
                              highlightthickness=1, highlightbackground=BORDER)

    def _scroll_tree(self, parent, tree):
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.event_text.pack(fill="x", pady=(10, 0))
            self.tabs.select(1)
        else:
            self.event_text.pack_forget()
        self.log_button.configure(text="Ẩn nhật ký" if self.log_visible else "Xem nhật ký")

    def show_statistics(self):
        if self.statistics_dialog is not None:
            self.statistics_dialog.lift()
            return
        dialog = tk.Toplevel(self.root)
        self.statistics_dialog = dialog
        dialog.title("Thống kê lượt giải")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.geometry("620x590")
        dialog.minsize(560, 540)
        dialog.protocol("WM_DELETE_WINDOW", self._close_statistics)
        dialog.bind("<Escape>", lambda event: self._close_statistics())
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Thống kê lượt giải", font=self.fonts.dialog_title).pack(anchor="w")
        self.statistics_context = tk.StringVar()
        ttk.Label(body, textvariable=self.statistics_context, style="Muted.TLabel",
                  wraplength=520).pack(anchor="w", pady=(6, 18))
        self.statistics_table = ttk.Treeview(body, columns=("metric", "total", "step"),
                                             show="headings", height=10, selectmode="none")
        for column, title, width in (("metric", "Chỉ số", 230), ("total", "Toàn lượt", 130),
                                      ("step", "Bước đang chọn", 150)):
            self.statistics_table.heading(column, text=title)
            self.statistics_table.column(column, width=width, minwidth=100,
                                         anchor="w" if column == "metric" else "center")
        self.statistics_table.pack(fill="both", expand=True)
        ttk.Button(body, text="Đóng", command=self._close_statistics).pack(anchor="e", pady=(16, 0))
        self._refresh_statistics()

    def _close_statistics(self):
        if self.statistics_dialog is not None:
            self.statistics_dialog.destroy()
            self.statistics_dialog = None

    def _refresh_statistics(self):
        if self.statistics_dialog is None:
            return
        self.statistics_table.delete(*self.statistics_table.get_children())
        selection = self.trace_tree.selection()
        entry = self.trace[int(selection[0])] if selection else None
        context = f"Bàn {self.state.size} × {self.state.size}" if self.state else "Chưa có bàn chơi"
        context += f"  •  Bước {entry['step']} / {entry['verdict']['cell']}" if entry else "  •  Chưa chọn bước suy luận"
        self.statistics_context.set(context)
        step_stats = entry["solver_stats"] if entry else {}
        rows = [("Bước suy luận", len(self.trace), entry["step"] if entry else "—")]
        for key, title in (("sat_calls", "Lần gọi SAT"), ("decisions", "Quyết định"),
                           ("propagations", "Lan truyền"), ("backtracks", "Quay lui"),
                           ("runtime_ms", "Thời gian SAT (ms)")):
            total, current = self.run_totals[key], step_stats.get(key, "—")
            if key == "runtime_ms":
                total = f"{total:.3f}"
                current = f"{current:.3f}" if current != "—" else current
            rows.append((title, total, current))
        if self.state:
            _, kb = encoder.build_kb(self.state.revealed_clues, self.state.known, self.state.size)
            rows.extend([("Biến chính", kb["primary_vars"], "—"), ("Biến phụ", kb["aux_vars"], "—"),
                         ("Mệnh đề KB", kb["clauses"], entry["kb_clauses"] if entry else "—"),
                         ("Nhân vật đã xác định", f"{len(self.state.known)}/{self.state.size ** 2}", "—")])
        for row in rows:
            self.statistics_table.insert("", "end", values=row)

    @staticmethod
    def _write(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def _resize_board(self, event):
        self._layout_board()
        self.board_guidance_label.configure(wraplength=max(240, event.width - 20))

    def _update_board_guidance(self):
        if self.mark_mode.get():
            self.board_guidance.set("Bấm thẻ để thêm/bỏ dấu. Tắt “Đánh dấu thẻ” để chọn trạng thái.")
        else:
            self.board_guidance.set("Thẻ chưa mở: chọn trạng thái · Thẻ đã mở: xem manh mối")

    def _layout_board(self):
        if self.closed:
            return
        width = self.board.winfo_reqwidth()
        height = self.board.winfo_reqheight()
        viewport = self.canvas.winfo_width()
        self.canvas.coords(self.board_window, max(0, (viewport - width) / 2), 0)
        self.canvas.configure(scrollregion=(0, 0, max(viewport, width), height))

    def _wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _tick_clock(self):
        if self.closed:
            return
        elapsed = max(0, int((self.finished_at or monotonic()) - self.started_at))
        self.clock.set(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        self.timer_job = self.root.after(1000, self._tick_clock)

    def toggle_analysis(self, show=None):
        visible = not self.analysis_visible if show is None else show
        if visible == self.analysis_visible:
            return
        self.analysis_visible = visible
        if visible:
            self.panes.add(self.inspector, weight=2)
            self.analysis_button.configure(text="Ẩn suy luận")
        else:
            self.panes.forget(self.inspector)
            self.analysis_button.configure(text="Xem suy luận")
        self._layout_board()

    def show_help(self):
        from tkinter import messagebox
        messagebox.showinfo("Cách chơi Griductive",
            "Bấm thẻ chưa mở, chọn Vô tội hoặc Tội phạm.\n\n"
            "Bấm thẻ đã mở để xem manh mối và tô sáng các ô liên quan.\n\n"
            "Bật Đánh dấu thẻ để thêm hoặc bỏ dấu ghi chú; tắt để chơi tiếp.\n\n"
            "Gợi ý: xem một nước đi tiếp theo.\n"
            "Giải một bước: thực hiện một nước đi.\n"
            "Tự động giải: chạy đến khi kết thúc; Dừng giải để dừng.\n\n"
            "Xem suy luận: mở lịch sử giải. Chọn một dòng để xem chi tiết.\n"
            "Xem thống kê và Xem nhật ký: mở thông tin tương ứng.", parent=self.root)

    def _availability(self):
        for control in self.controls:
            control.configure(state="disabled" if self.busy or self.auto_running else "normal")
        self.root.configure(cursor="watch" if self.busy else "")
        self.size_picker.configure(state="disabled" if self.busy or self.auto_running else "readonly")
        self.stop_button.configure(state="normal" if self.auto_running else "disabled")
        can_play = self.state is not None and not self.state.solved and not self.busy and not self.auto_running
        for control in self.game_controls:
            control.configure(state="normal" if can_play else "disabled")

    def _task(self, operation, done, message):
        if self.busy or self.closed:
            return
        self.busy = True
        self.message.set(message)
        self._availability()

        def worker():
            try:
                self.results.put((done, operation(), None))
            except Exception as error:
                self.results.put((done, None, error))

        Thread(target=worker, daemon=True).start()

    def _poll(self):
        if self.closed:
            return
        try:
            done, result, error = self.results.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False
            if error:
                self.stop_auto()
                if self.state:
                    self.size_name.set(f"{self.state.size} × {self.state.size}")
                self._notify(f"Lỗi: {error}", error=True)
            else:
                try:
                    done(result)
                except Exception as callback_error:
                    self.stop_auto()
                    self._notify(f"Lỗi cập nhật giao diện: {callback_error}", error=True)
            self._availability()
        self.poll_job = self.root.after(60, self._poll)

    def _hide_toast(self):
        self.toast_job = None
        self.toast.place_forget()

    def _notify(self, message, error=False, transient=True):
        self.message.set(message)
        display = feedback_text(message)
        self.events.append(display)
        self._write(self.event_text, "\n".join(self.events[-100:]))
        self.event_text.see("end")
        if transient:
            if self.toast_job is not None:
                self.root.after_cancel(self.toast_job)
            self.toast.configure(text=display, fg=RED if error else INK)
            self.toast.place(relx=.5, rely=.92, anchor="s")
            self.toast.lift()
            self.toast_job = self.root.after(4500, self._hide_toast)

    def new_game(self):
        if self.busy or self.auto_running:
            return
        candidates = [PUZZLES / name for name in SIZE_PUZZLES[self.size_name.get()]
                      if (PUZZLES / name).exists()]
        if not candidates:
            if self.state:
                self.size_name.set(f"{self.state.size} × {self.state.size}")
            self._notify("Không có bàn chơi cho kích thước này.", error=True)
            return
        alternatives = [path for path in candidates if path != self.current_path]
        self.load(choice(alternatives or candidates))

    def load(self, path):
        path = Path(path)

        def loaded(engine):
            self.engine = engine
            self.current_path = path
            n = engine.public_state().size
            self.size_name.set(f"{n} × {n}")
            self._reset_view()
            self._notify("Ván chơi đã sẵn sàng.", transient=False)

        self._task(lambda: GameEngine(str(path)), loaded, "Đang đọc và kiểm tra puzzle…")

    def _reset_view(self):
        self._dismiss_dialog()
        self.started_at = monotonic()
        self.finished_at = None
        self.clock.set("00:00")
        self.marked.clear()
        self.mark_mode.set(False)
        if self.toast_job is not None:
            self.root.after_cancel(self.toast_job)
        self._hide_toast()
        self.selected = None
        self.highlights.clear()
        self.trace.clear()
        self.events.clear()
        for key in self.run_totals:
            self.run_totals[key] = 0
        self.trace_tree.delete(*self.trace_tree.get_children())
        self._write(self.trace_detail, EMPTY_TRACE)
        self._write(self.clue_detail, "Chưa chọn manh mối.")
        self.render()

    def restart(self):
        if self.engine:
            self.engine.restart()
            self._reset_view()
            self._notify("Đã khởi động lại puzzle.")

    def render(self):
        self.state = self.engine.public_state()
        state = self.state
        for widget in self.board.winfo_children():
            widget.destroy()
        for col in range(len(encoder.COLS) + 1):
            self.board.columnconfigure(col, weight=0, uniform="")
        self.cards.clear()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        card_width, card_height = ((150, 150) if state.size <= 3 else
                                   (132, 142) if state.size == 4 else (116, 138))
        card_width = round(card_width * self.fonts.scale)
        card_height = round(card_height * self.fonts.scale)
        for col in range(state.size):
            tk.Label(self.board, text=encoder.COLS[col], bg=BG, fg=MUTED,
                     font=self.fonts.small).grid(row=0, column=col + 1, pady=(0, 4))
        for row in range(state.size):
            tk.Label(self.board, text=str(row + 1), bg=BG, fg=MUTED,
                     font=self.fonts.small).grid(row=row + 1, column=0, padx=(0, 5))
        for person in state.characters:
            cell = person["cell"]
            row, col = encoder.parse_cell(cell, state.size)
            status = ("CRIMINAL" if state.known[cell] else "INNOCENT") if cell in state.known else "UNKNOWN"
            clue = state.clues_by_cell.get(cell)
            description = clue_text(clue, state.size) if clue else ""
            card = SuspectCard(self.board, person, status, description, card_width, card_height,
                               lambda c=cell: self._card_clicked(c), fonts=self.fonts)
            card.grid(row=row + 1, column=col + 1, padx=3, pady=3)
            card.bind("<MouseWheel>", self._wheel)
            self.cards[cell] = card
        if state.solved and self.finished_at is None:
            self.finished_at = monotonic()
        self._layout_board()
        self.clue_tree.delete(*self.clue_tree.get_children())
        self.clues = list(state.clues_by_cell.items())
        for i, (cell, clue) in enumerate(self.clues):
            self.clue_tree.insert("", "end", iid=str(i), values=(cell, clue_text(clue, state.size)))
        self._refresh_statistics()
        self._paint_borders()
        self._availability()
        if self.scroll_job is not None:
            self.root.after_cancel(self.scroll_job)
        self.scroll_job = self.root.after_idle(self._reset_scroll)

    def _reset_scroll(self):
        self.scroll_job = None
        if not self.closed:
            self._layout_board()
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

    def _paint_borders(self):
        for cell, card in self.cards.items():
            color = GOLD if cell == self.selected else "#d2b46c" if cell in self.highlights else None
            card.set_outline(color, cell in self.marked)

    def _card_clicked(self, cell):
        if self.busy or self.auto_running:
            return
        self.select_cell(cell)
        if self.mark_mode.get():
            if cell in self.marked:
                self.marked.remove(cell)
            else:
                self.marked.add(cell)
            self._paint_borders()
            return
        if cell in self.state.known:
            for index, (owner, _) in enumerate(self.clues):
                if owner == cell:
                    self.clue_tree.selection_set(str(index))
                    self.select_clue()
                    self.toggle_analysis(True)
                    self.tabs.select(0)
                    break
        else:
            self._open_verdict_dialog(cell)

    def _dismiss_dialog(self):
        if self.verdict_dialog is not None:
            self.verdict_dialog.grab_release()
            self.verdict_dialog.destroy()
            self.verdict_dialog = None

    def _open_verdict_dialog(self, cell):
        self._dismiss_dialog()
        person = next(p for p in self.state.characters if p["cell"] == cell)
        dialog = tk.Toplevel(self.root)
        self.verdict_dialog = dialog
        dialog.title(f"{person['name']} · {cell}")
        dialog.configure(bg=SURFACE, padx=24, pady=20)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.protocol("WM_DELETE_WINDOW", self._dismiss_dialog)
        dialog.bind("<Escape>", lambda event: self._dismiss_dialog())
        avatar = tk.Canvas(dialog, width=90, height=90, bg=SURFACE, highlightthickness=0)
        avatar.pack()
        portrait(avatar, person["name"], 45, 43, 1)
        tk.Label(dialog, text=person["name"], bg=SURFACE, fg=INK,
                 font=self.fonts.person).pack(pady=(4, 0))
        tk.Label(dialog, text=f"{cell}  ·  {person['profession']}", bg=SURFACE,
                 fg=MUTED, font=self.fonts.body).pack(pady=(4, 18))
        tk.Label(dialog, text="Chọn trạng thái", bg=SURFACE, fg=INK,
                 font=self.fonts.dialog_title).pack(pady=(0, 18))
        actions = tk.Frame(dialog, bg=SURFACE)
        actions.pack(fill="x")

        def choose(verdict):
            self._dismiss_dialog()
            self.select_cell(cell)
            self.submit(verdict)

        ttk.Button(actions, text="Vô tội", style="Accent.TButton", width=15,
                   command=lambda: choose("INNOCENT")).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Tội phạm", style="Danger.TButton", width=15,
                   command=lambda: choose("CRIMINAL")).pack(side="left")
        cancel = tk.Button(dialog, text="Hủy", command=self._dismiss_dialog, bg=SURFACE,
                           fg=MUTED, activebackground=SURFACE, activeforeground=INK,
                           relief="flat", bd=0, cursor="hand2", font=self.fonts.body)
        cancel.pack(pady=(16, 0))
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.grab_set()
        cancel.focus_set()

    def select_cell(self, cell):
        if self.busy or self.auto_running:
            return
        self.selected = cell
        self._paint_borders()
        self._availability()

    def select_clue(self, event=None):
        selected = self.clue_tree.selection()
        if not selected or not self.state:
            return
        cell, clue = self.clues[int(selected[0])]
        self.highlights = set(encoder.referenced_cells(clue, self.state.size))
        self._write(self.clue_detail, f"Manh mối từ ô {cell}\n\n"
                    f"{clue_text(clue, self.state.size)}\n\n"
                    f"Các ô liên quan: {', '.join(encoder.referenced_cells(clue, self.state.size))}")
        self._paint_borders()

    def clear_highlights(self):
        self.highlights.clear()
        self.clue_tree.selection_remove(*self.clue_tree.selection())
        self._write(self.clue_detail, "Chưa chọn manh mối.")
        self._paint_borders()

    def submit(self, verdict):
        if not self.selected or not self.engine or self.selected in self.state.known:
            return
        cell = self.selected

        def done(result):
            self.render()
            self._notify(f"{result['status']} • {cell}: {result['message']}", result["status"] != "ACCEPTED")

        self._task(lambda: self.engine.submit_verdict(cell, verdict), done, f"Đang kiểm tra {cell}: {verdict}…")

    def show_hint(self):
        if not self.engine:
            return
        state = self.engine.public_state()

        def operation():
            classifications = agent.classify(state)
            if "INCONSISTENT" in classifications.values():
                return "INCONSISTENT", None
            return "READY", agent.hint(state)

        def done(result):
            status, hint = result
            if status == "INCONSISTENT":
                self._notify("INCONSISTENT • Dữ kiện công khai mâu thuẫn.", True)
            elif hint is None:
                self._notify("SOLVED • Đã xác định tất cả nhân vật." if state.solved else
                             "STUCK • Chưa có gợi ý từ các manh mối hiện tại.")
            else:
                self.selected = hint["cell"]
                relevant = [c for c in state.revealed_clues if c["id"] in hint["clue_ids"]]
                self.highlights = {cell for c in relevant for cell in encoder.referenced_cells(c, state.size)}
                self._paint_borders()
                self.toggle_analysis(True)
                self.tabs.select(0)
                self._write(self.clue_detail, f"Gợi ý: {hint['cell']} → {VERDICTS[hint['verdict']]}\n\n"
                            "Manh mối liên quan:\n" + "\n\n".join(
                                f"{c['id']}: {clue_text(c, state.size)}" for c in relevant))
                self._notify(f"HINT • Có thể chứng minh {hint['cell']}: {hint['verdict']}. Thẻ chưa được mở.")

        self._task(operation, done, "Đang tìm gợi ý từ dữ kiện công khai…")

    def next_step(self):
        if self.engine:
            self._task(lambda: agent.step(self.engine), self._step_done, "Agent đang tìm bước suy luận tiếp theo…")

    def _step_done(self, result):
        for key in self.run_totals:
            self.run_totals[key] += result["totals"][key]
        for entry in result["trace"]:
            entry["step"] = len(self.trace) + 1
            self.trace.append(entry)
            verdict = entry["verdict"]
            self.selected = verdict["cell"]
            iid = str(len(self.trace) - 1)
            self.trace_tree.insert("", "end", iid=iid,
                                   values=(entry["step"], verdict["cell"], VERDICTS[verdict["status"]]),
                                   tags=("innocent" if verdict["status"] == "INNOCENT" else "criminal",))
            self.trace_tree.selection_set(iid)
            self.trace_tree.see(iid)
        self.render()
        self.toggle_analysis(True)
        self.tabs.select(1)
        if result["trace"]:
            self.select_trace()
        else:
            self._write(self.trace_detail, {"SOLVED": "Đã hoàn thành bàn chơi.", "STUCK": "Chưa thể xác định thêm nhân vật.", "INCONSISTENT": "Dữ kiện không hợp lệ."}.get(result["status"], result["status"]) + "\n\n" + "\n".join(
                f"{q['cell']}: {q['query']} → {q['result']}" for q in result.get("queries", [])))
        status = result["status"]
        descriptions = {"PROGRESS": "Đã mở một thẻ bằng suy luận.", "SOLVED": "Đã hoàn thành bàn chơi.",
                        "STUCK": "Chưa thể xác định thêm nhân vật. Đã dừng giải.",
                        "INCONSISTENT": "Dữ kiện không hợp lệ. Đã dừng giải."}
        if status == "PROGRESS" and result["trace"]:
            verdict = result["trace"][-1]["verdict"]
            descriptions[status] = f"Đã xác định {verdict['cell']}: {VERDICTS[verdict['status']].lower()}."
        self._notify(f"{status} • {descriptions.get(status, status)}", status == "INCONSISTENT",
                     transient=not self.auto_running or status != "PROGRESS")
        if self.auto_running and status == "PROGRESS":
            self.auto_job = self.root.after(450, self._auto_tick)
        else:
            self.stop_auto(notify=False)

    def select_trace(self, event=None):
        selected = self.trace_tree.selection()
        if not selected:
            return
        entry = self.trace[int(selected[0])]
        verdict = entry["verdict"]
        widget = self.trace_detail
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", f"Bước {entry['step']} · {verdict['cell']}\n", "heading")
        verdict_name = VERDICTS[verdict["status"]]
        widget.insert("end", f"Kết luận: {verdict_name}\n")
        widget.insert("end", "Truy vấn SAT\n", "heading")
        for query in entry["queries"]:
            widget.insert("end", f"{query['query']}  →  ", "query")
            widget.insert("end", f"{query['result']}\n", ("query", "unsat")
                          if query["result"] == "UNSAT" else "query")
        widget.insert("end", "Dữ kiện sử dụng\n", "heading")
        clue_owners = {clue["id"]: f"Ô {cell}" for cell, clue in self.state.clues_by_cell.items()}
        widget.insert("end", ", ".join(clue_owners.get(cid, cid) for cid in entry["active_clues"])
                      or "Không có manh mối", "muted")
        widget.insert("end", "\n")
        widget.insert("end", "Manh mối mới\n", "heading")
        widget.insert("end", f"{clue_owners.get(entry['revealed_clue'], entry['revealed_clue'])}\n")
        widget.configure(state="disabled")
        self._refresh_statistics()

    def start_auto(self):
        if not self.engine or self.busy or self.auto_running:
            return
        self.auto_running = True
        self._availability()
        self._auto_tick()

    def _auto_tick(self):
        self.auto_job = None
        if self.auto_running:
            self.next_step()

    def stop_auto(self, notify=True):
        was_running = self.auto_running
        self.auto_running = False
        if self.auto_job is not None:
            self.root.after_cancel(self.auto_job)
            self.auto_job = None
        if was_running and notify:
            self._notify("Đã yêu cầu dừng tự giải. Bước đang chạy sẽ hoàn tất trước khi dừng.")
        self._availability()

    def close(self):
        self._close_statistics()
        self._dismiss_dialog()
        if self.toast_job is not None:
            self.root.after_cancel(self.toast_job)
        self.closed = True
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
        self.auto_running = False
        self.root.after_cancel(self.poll_job)
        if self.auto_job is not None:
            self.root.after_cancel(self.auto_job)
        if self.scroll_job is not None:
            self.root.after_cancel(self.scroll_job)
        self.root.destroy()
