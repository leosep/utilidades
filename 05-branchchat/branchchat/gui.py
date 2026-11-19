"""BranchChat graphical interface."""
from __future__ import annotations

import atexit
import tempfile
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from uikit import AppWindow, Table

from .loaders import load_conversations
from .model import Conversation
from .render import _preview, path_to_markdown, to_html


class BranchChatApp(AppWindow):
    def __init__(self) -> None:
        super().__init__("BranchChat", "See your AI chats as a tree and save only the path you care about.",
                         "branchchat", icon="assets/branchchat.ico", size=(1040, 680))
        self.conversations: list[Conversation] = []
        self.conv: Conversation | None = None
        self._temp_files: list[Path] = []
        self._clean_stale_temp_files()
        atexit.register(self._cleanup)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self.set_status("Everything is processed on your computer.")

    def _build(self) -> None:
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Button(bar, text="Open chat export…", style="Accent.TButton", command=self.choose_file).pack(side="left")
        self.tree_button = ttk.Button(bar, text="View tree in browser", command=self.open_tree, state="disabled")
        self.tree_button.pack(side="right")
        self.save_button = ttk.Button(bar, text="Save this path…", command=self.save_path, state="disabled")
        self.save_button.pack(side="right", padx=8)

        panes = ttk.PanedWindow(self.body, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(left, weight=2)
        panes.add(right, weight=3)
        self.root.after(80, lambda: panes.sashpos(0, 400))  # initial width of the conversations panel

        ttk.Label(left, text="1. Conversations", style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        self.conv_table = Table(left, [("title", "Title", 150, "w"), ("msgs", "Messages", 85, "e"), ("forks", "Branches", 65, "e")],
                                on_select=self.select_conversation,
                                empty_text="Open the JSON file you exported\nfrom your AI chat service.")
        self.conv_table.pack(fill="both", expand=True, padx=(0, 10))
        self.conv_table.set_rows([])

        ttk.Label(right, text="2. Choose how it ended", style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        self.leaf_table = Table(right, [("who", "Who", 70, "w"), ("text", "Last message in that branch", 330, "w"), ("chosen", "", 90, "w")],
                                height=5, on_select=self.select_leaf)
        self.leaf_table.pack(fill="x")
        ttk.Label(right, text="Preview of the conversation up to that ending", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        holder = ttk.Frame(right)
        holder.pack(fill="both", expand=True)
        body_font = tkfont.nametofont("TkDefaultFont")
        self.preview = tk.Text(holder, wrap="word", state="disabled", relief="flat", padx=12, pady=10, highlightthickness=1,
                               highlightbackground="#cdd5dc", background="#ffffff", foreground="#1c1c1c",
                               font=body_font, insertwidth=0)
        scroll = ttk.Scrollbar(holder, command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.preview.pack(side="left", fill="both", expand=True)
        self._bold = body_font.copy()  # keep a reference so Tk does not free the font
        self._bold.configure(weight="bold")
        self.preview.tag_configure("who", font=self._bold, spacing1=8)

    # -- temporary files ----------------------------------------------------------------
    @staticmethod
    def _clean_stale_temp_files() -> None:
        """Remove pages left behind by a previous crash; the chats are private."""
        for path in Path(tempfile.gettempdir()).glob("branchchat-*.html"):
            try:
                if time.time() - path.stat().st_mtime > 24 * 60 * 60:
                    path.unlink(missing_ok=True)
            except OSError:
                pass

    def _cleanup(self) -> None:
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

    def _close(self) -> None:
        self._cleanup()
        self.root.destroy()

    # -- data ---------------------------------------------------------------------------
    def choose_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose the chat file",
                                            filetypes=[("Exported chats (JSON)", "*.json"), ("All files", "*.*")])
        if chosen:
            self.load(Path(chosen))

    def load(self, path: Path) -> None:
        try:
            self.conversations = load_conversations(path)
        except (OSError, ValueError) as error:
            messagebox.showwarning("Could not read the file", str(error))
            return
        rows = [(str(i), (c.title, str(len(c.messages)), str(c.branch_points())), "") for i, c in enumerate(self.conversations)]
        self.conv_table.set_rows(rows)
        self.conv_table.tree.selection_set("0")
        self.set_status(f"{path.name}: {len(self.conversations)} conversations")

    def select_conversation(self) -> None:
        selected = self.conv_table.selected()
        if selected is None:
            return
        self.conv = self.conversations[int(selected)]
        chosen = self.conv.default_leaf()
        rows = [(leaf.id, ({"user": "You", "assistant": "AI"}.get(leaf.role, leaf.role), _preview(leaf.text, 70),
                           "✓ chosen" if leaf.id == chosen else ""), "") for leaf in self.conv.leaves()]
        self.leaf_table.set_rows(rows)
        self.tree_button.config(state="normal")
        if chosen:
            self.leaf_table.tree.selection_set(chosen)

    def select_leaf(self) -> None:
        leaf_id = self.leaf_table.selected()
        self.save_button.config(state="normal" if leaf_id else "disabled")
        if not (leaf_id and self.conv):
            return
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        for message in self.conv.path_to(leaf_id):
            self.preview.insert("end", ("You" if message.role == "user" else "AI") + "\n", "who")
            self.preview.insert("end", message.text + "\n")
        self.preview.config(state="disabled")

    # -- actions ------------------------------------------------------------------------------
    def open_tree(self) -> None:
        if not self.conv:
            return
        with tempfile.NamedTemporaryFile("w", suffix=".html", prefix="branchchat-", delete=False, encoding="utf-8") as handle:
            handle.write(to_html(self.conv))
        page = Path(handle.name)
        self._temp_files.append(page)
        webbrowser.open(page.as_uri())

    def save_path(self) -> None:
        leaf_id = self.leaf_table.selected()
        if not (leaf_id and self.conv):
            return
        target = filedialog.asksaveasfilename(title="Save the chosen path", defaultextension=".md",
                                              initialfile="conversation.md", filetypes=[("Markdown", "*.md")])
        if target:
            Path(target).write_text(path_to_markdown(self.conv, leaf_id), encoding="utf-8")
            self.set_status(f"Saved to {target}")


# Name used by the original Spanish version; kept so old imports keep working.
RamaChatApp = BranchChatApp


def main() -> None:
    BranchChatApp().run()
