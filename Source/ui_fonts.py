"""Persistent Tk fonts, scoped to one application's Tcl interpreter."""

from tkinter import font as tkfont
from unicodedata import normalize


class UIFonts:
    def __init__(self, root):
        available = set(tkfont.families(root))
        default = tkfont.nametofont("TkDefaultFont", root=root).actual("family")
        self.family = next((f for f in ("Segoe UI", "Arial", "Noto Sans", "DejaVu Sans")
                            if f in available), default)
        self.mono_family = next((f for f in ("Consolas", "DejaVu Sans Mono", "Liberation Mono")
                                 if f in available), self.family)
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)

        def make(size, weight="normal", mono=False):
            return tkfont.Font(root=root, family=self.mono_family if mono else self.family,
                               size=size, weight=weight)

        self.body = make(11)
        self.small = make(9)
        self.small_bold = make(9, "bold")
        self.heading = make(12, "bold")
        self.section = make(13, "bold")
        self.title = make(24, "bold")
        self.dialog_title = make(18, "bold")
        self.person = make(15, "bold")
        self.clock = make(14, "bold", mono=True)
        self.query = make(11, mono=True)
        self.card_name = make(11, "bold")
        self.card_heading = make(10, "bold")
        self.card_body = make(10)

        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                     "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
            tkfont.nametofont(name, root=root).configure(family=self.family, size=11)
        tkfont.nametofont("TkFixedFont", root=root).configure(family=self.mono_family, size=11)
        root.option_add("*Font", self.body)
        root.option_add("*TCombobox*Listbox.font", self.body)


def fit_line(text, font, width):
    """Keep one-line card labels inside their allocated pixel width."""
    text = normalize("NFC", text)
    if font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"
