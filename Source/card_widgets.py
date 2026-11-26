"""Code-drawn portraits and rounded cards. No remote assets or extra dependencies."""

import tkinter as tk
from ui_text import VERDICTS
from ui_fonts import UIFonts, fit_line
from unicodedata import normalize
from zlib import crc32

BACKGROUND = "#211d19"
SURFACE = "#2e2723"
TEXT = "#f3eee3"
MUTED = "#aca394"
BORDER = "#5b514a"
GREEN = "#86bf9e"
RED = "#f18479"
GOLD = "#d9bd7b"


def rounded(canvas, x1, y1, x2, y2, radius=12, **kwargs):
    return canvas.create_polygon(
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        smooth=True, splinesteps=24, **kwargs)


def portrait(canvas, name, cx, cy, scale=1):
    """Deterministic cosmetic appearance derived solely from the public name."""
    seed = crc32(name.encode("utf-8"))
    skin = ("#e9bd95", "#c68f63", "#9b6243", "#f0cfb1", "#bd8059")[seed % 5]
    hair = ("#5c3426", "#bb7c36", "#d5b56e", "#382a24", "#885136")[(seed >> 4) % 5]
    shirt = ("#829dad", "#c78165", "#8b9f79", "#b3849c", "#bfaa69")[(seed >> 7) % 5]

    def oval(x1, y1, x2, y2, fill, **kw):
        canvas.create_oval(cx + x1 * scale, cy + y1 * scale,
                           cx + x2 * scale, cy + y2 * scale, fill=fill, outline="", **kw)

    def poly(points, fill):
        canvas.create_polygon(*[value for x, y in points
                                for value in (cx + x * scale, cy + y * scale)],
                              fill=fill, outline="", smooth=True)

    oval(-29, -31, 29, 31, "#40362e")
    oval(-23, 16, 23, 43, shirt)
    poly([(-10, 20), (0, 31), (10, 20), (6, 17), (-6, 17)], "#f2e9db")
    oval(-6, 10, 6, 24, skin)
    oval(-19, -25, 19, 21, hair)
    if seed % 3 == 0:
        oval(-12, -42, 12, -19, hair)
    oval(-17, -11, 17, 19, skin)
    oval(-21, -4, -13, 7, skin)
    oval(13, -4, 21, 7, skin)
    poly([(-17, -7), (-15, -26), (10, -29), (21, -13), (8, -10), (2, -20), (-6, -9)], hair)
    oval(-9, -1, -6, 3, "#30251e")
    oval(6, -1, 9, 3, "#30251e")
    canvas.create_arc(cx - 6 * scale, cy + 5 * scale, cx + 6 * scale, cy + 12 * scale,
                      start=200, extent=140, style="arc", outline="#82503d", width=max(1, scale))
    if seed % 4 == 0:
        for offset in (-7, 7):
            canvas.create_oval(cx + (offset - 5) * scale, cy - 4 * scale,
                               cx + (offset + 5) * scale, cy + 5 * scale,
                               outline="#453c34", width=1.2)
        canvas.create_line(cx - 2 * scale, cy, cx + 2 * scale, cy, fill="#453c34")


class SuspectCard(tk.Canvas):
    def __init__(self, parent, person, status, description, width, height, command, fonts=None):
        self.fonts = fonts or UIFonts(parent.winfo_toplevel())
        scale = self.fonts.scale
        self.clue_font = self.fonts.card_body
        clue_top = round(68 * scale)
        status_height = self.fonts.small_bold.metrics("linespace")
        height = max(height, clue_top + 2 * self.clue_font.metrics("linespace") + status_height + round(18 * scale))
        super().__init__(parent, width=width, height=height, bg=BACKGROUND,
                         highlightthickness=0, bd=0, cursor="hand2", takefocus=True)
        self.status = status
        self.default_outline = GREEN if status == "INNOCENT" else RED if status == "CRIMINAL" else BORDER
        fill = "#2c3930" if status == "INNOCENT" else "#49302c" if status == "CRIMINAL" else SURFACE
        self.edge = rounded(self, 2, 2, width - 2, height - 2, radius=12 * scale, fill=fill,
                            outline=self.default_outline, width=1.5)
        self.create_text(10 * scale, 11 * scale, anchor="nw", text=person["cell"], fill=MUTED,
                         font=self.fonts.small_bold)
        if status == "UNKNOWN":
            portrait(self, person["name"], width / 2, height * .39, .75 * scale)
            self.create_text(width / 2, height * .73,
                             text=fit_line(person["name"], self.fonts.card_name, width - 16 * scale),
                             fill=TEXT, font=self.fonts.card_name)
            self.create_text(width / 2, height * .87,
                             text=fit_line(person["profession"], self.fonts.small, width - 16 * scale),
                             fill=MUTED, font=self.fonts.small)
        else:
            portrait(self, person["name"], 28 * scale, 37 * scale, .30 * scale)
            self.create_text(48 * scale, 27 * scale, anchor="nw",
                             text=fit_line(person["name"], self.fonts.card_heading, width - 55 * scale),
                             fill=TEXT, font=self.fonts.card_heading)
            self.create_text(48 * scale, 44 * scale, anchor="nw",
                             text=fit_line(person["profession"], self.fonts.small, width - 55 * scale),
                             fill=MUTED, font=self.fonts.small)
            status_y = height - 15 * scale
            self.status_item = self.create_text(width / 2, status_y, text=VERDICTS[status],
                                                 fill=self.default_outline, font=self.fonts.small_bold)
            available_width = width - 24 * scale
            lines, line = [], ""
            for word in normalize("NFC", description).split():
                candidate = f"{line} {word}".strip()
                if line and self.clue_font.measure(candidate) > available_width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
            available_height = status_y - status_height / 2 - 8 * scale - clue_top
            max_lines = max(1, int(available_height / self.clue_font.metrics("linespace")))
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = fit_line(lines[-1].rstrip("., ") + "…", self.clue_font, available_width)
            self.clue_item = self.create_text(width / 2, clue_top, anchor="n", text="\n".join(lines),
                                              justify="center", width=available_width,
                                              fill=TEXT, font=self.clue_font)
        self.bind("<Button-1>", lambda event: command())
        self.bind("<Return>", lambda event: command())
        self.bind("<space>", lambda event: command())
        self.bind("<Enter>", lambda event: self.itemconfigure(self.edge, width=2.5))
        self.bind("<Leave>", lambda event: self.itemconfigure(self.edge, width=1.5))

    def set_outline(self, color=None, marked=False):
        self.itemconfigure(self.edge, outline=color or self.default_outline,
                           width=2.5 if color else 1.5)
        self.delete("mark")
        if marked:
            width = int(self.cget("width"))
            self.create_oval(width - 17, 10, width - 9, 18, fill=GOLD, outline="", tags="mark")
