"""Interface pieces shared by the apps: theme, base window, cards, tables and dialogs."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Callable, Sequence

try:
    import sv_ttk  # modern theme (Windows 11 style)
except ImportError:  # without the theme the apps still work, they just look plainer
    sv_ttk = None

MUTED = "#5b6770"
ZEBRA = "#f5f7f9"
WARN_BG = "#fff1cc"
DANGER_BG = "#fde2de"
ERROR_FG = "#b3261e"


def resource_path(relative: str) -> Path:
    """Path to a resource, both in development and inside the PyInstaller executable."""
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) / relative if bundled else Path(__file__).resolve().parent.parent / relative


def log_file(app_id: str) -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    folder = base / "UsefulUtilities"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{app_id}.log"


def money(value: float) -> str:
    return f"{value:,.2f}"


def apply_theme(root: tk.Tk) -> str:
    if sv_ttk:
        sv_ttk.set_theme("light")
        root.update()  # sv_ttk applies the theme lazily: let it finish before creating widgets
    default = tkfont.nametofont("TkDefaultFont")
    family = "Segoe UI" if "Segoe UI" in set(tkfont.families()) else default.actual("family")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        tkfont.nametofont(name).configure(family=family, size=10)
    style = ttk.Style(root)
    style.configure("Title.TLabel", font=(family, 20, "bold"))
    style.configure("Heading.TLabel", font=(family, 14, "bold"))
    style.configure("Subtitle.TLabel", foreground=MUTED)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Error.TLabel", foreground=ERROR_FG)
    style.configure("CardValue.TLabel", font=(family, 22, "bold"))
    style.configure("Treeview", rowheight=30)
    style.configure("Treeview.Heading", font=(family, 10, "bold"))
    return family


class AppWindow:
    """Main window with a header, a content area and a status bar."""

    def __init__(self, title: str, subtitle: str, app_id: str, icon: str | None = None, size: tuple[int, int] = (960, 640)):
        if sys.platform == "win32":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # avoids blurry text on high-density screens
            except Exception:  # noqa: BLE001
                pass
        self.app_id = app_id
        self.root = tk.Tk()
        self.root.title(title)
        self.root.minsize(int(size[0] * 0.8), int(size[1] * 0.75))
        apply_theme(self.root)
        if icon and sys.platform == "win32":
            try:
                self.root.iconbitmap(str(resource_path(icon)))
            except tk.TclError:
                pass
        self._install_error_handler()

        header = ttk.Frame(self.root, padding=(24, 20, 24, 8))
        header.pack(fill="x")
        ttk.Label(header, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text=subtitle, foreground=MUTED).pack(anchor="w")  # direct color: the style was not applied in time
        self.body = ttk.Frame(self.root, padding=(24, 10, 24, 10))
        self.body.pack(fill="both", expand=True)
        ttk.Separator(self.root).pack(fill="x")
        self._status = tk.StringVar()
        ttk.Label(self.root, textvariable=self._status, foreground=MUTED, padding=(24, 6)).pack(fill="x")

        self.root.geometry(f"{size[0]}x{size[1]}")
        self.root.update_idletasks()
        x = max((self.root.winfo_screenwidth() - size[0]) // 2, 0)
        y = max((self.root.winfo_screenheight() - size[1]) // 3, 0)
        self.root.geometry(f"+{x}+{y}")

    def _install_error_handler(self) -> None:
        logging.basicConfig(filename=log_file(self.app_id), level=logging.ERROR, format="%(asctime)s %(message)s", encoding="utf-8")

        def handler(exc, value, tb):
            logging.error("".join(traceback.format_exception(exc, value, tb)))
            messagebox.showerror(
                self.root.title(),
                "Something unexpected happened, but the application is still open.\n\n"
                f"If it keeps happening, send this file to whoever gave you the application:\n{log_file(self.app_id)}",
            )

        self.root.report_callback_exception = handler

    def set_status(self, text: str) -> None:
        self._status.set(text)

    def run(self) -> None:
        self.root.mainloop()


def stat_card(parent: tk.Widget, label: str, variable: tk.StringVar) -> ttk.Frame:
    card = ttk.Frame(parent, style="Card.TFrame", padding=(18, 14))
    ttk.Label(card, text=label, style="Muted.TLabel").pack(anchor="w")
    ttk.Label(card, textvariable=variable, style="CardValue.TLabel").pack(anchor="w")
    return card


def card_row(parent: tk.Widget, cards: Sequence[tuple[str, tk.StringVar]]) -> ttk.Frame:
    row = ttk.Frame(parent)
    for index, (label, variable) in enumerate(cards):
        stat_card(row, label, variable).grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 12, 0))
        row.columnconfigure(index, weight=1, uniform="cards")
    return row


class Table(ttk.Frame):
    """Table with a scrollbar, alternating rows and a message when it is empty."""

    def __init__(self, parent: tk.Widget, columns: Sequence[tuple[str, str, int, str]], empty_text: str = "",
                 height: int = 10, on_open: Callable[[], None] | None = None, on_select: Callable[[], None] | None = None):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, columns=[c[0] for c in columns], show="headings", height=height, selectmode="browse")
        for key, heading, width, anchor in columns:
            self.tree.heading(key, text=heading, anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor, stretch=(anchor == "w"))
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        for tag, color in (("odd", ZEBRA), ("warn", WARN_BG), ("danger", DANGER_BG)):
            self.tree.tag_configure(tag, background=color)
        self._empty = ttk.Label(self, text=empty_text, style="Muted.TLabel", justify="center")
        if on_open:
            self.tree.bind("<Double-1>", lambda event: on_open() if self.selected() else None)
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda event: on_select())

    def set_rows(self, rows: Sequence[tuple[str, Sequence[str], str]]) -> None:
        """Each row is (id, values, tag). Tags: '', 'warn' or 'danger'."""
        self.tree.delete(*self.tree.get_children())
        for index, (iid, values, tag) in enumerate(rows):
            tags = (tag,) if tag else (("odd",) if index % 2 else ())
            self.tree.insert("", "end", iid=str(iid), values=list(values), tags=tags)
        if rows:
            self._empty.place_forget()
        else:
            self._empty.place(relx=0.5, rely=0.45, anchor="center")

    def selected(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def row_count(self) -> int:
        return len(self.tree.get_children())


class Dialog(tk.Toplevel):
    """Modal dialog centered over the window that opens it."""

    def __init__(self, parent: tk.Widget, title: str):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.body = ttk.Frame(self, padding=22)
        self.body.pack(fill="both", expand=True)
        self.result = None
        self.bind("<Escape>", lambda event: self.destroy())

    def show(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.wait_visibility()
        self.grab_set()
        self.focus_set()
        self.wait_window(self)
        return self.result
