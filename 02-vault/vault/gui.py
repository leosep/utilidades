"""Vault graphical interface."""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from uikit import ERROR_FG, AppWindow, Dialog, Table

from . import crypto
from .crypto import WrongPassword
from .store import Document, Vault, VaultError, default_root

SOON_DAYS = 60
IDLE_LOCK_MS = 10 * 60 * 1000
COLUMNS = [
    ("name", "Document", 240, "w"),
    ("tags", "Tags", 180, "w"),
    ("file", "File", 190, "w"),
    ("size", "Size", 90, "e"),
    ("expires", "Expires", 170, "w"),
]


def parse_user_date(text: str) -> date | None:
    """Accept yyyy-mm-dd or dd/mm/yyyy. Empty means 'no expiry'."""
    text = text.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("The date should look like 2027-12-31")


def human_size(size: int) -> str:
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    return f"{max(1, round(size / 1024))} KB"


def expiry_text(doc: Document, today: date) -> tuple[str, str]:
    """(text, color tag)"""
    if not doc.expires:
        return "—", ""
    days = (doc.expires - today).days
    label = doc.expires.isoformat()
    if days < 0:
        return f"{label} · expired", "danger"
    if days <= SOON_DAYS:
        return f"{label} · in {days} days", "warn"
    return label, ""


class AddDialog(Dialog):
    def __init__(self, parent: tk.Widget, default_name: str):
        super().__init__(parent, "Add document")
        self.name = tk.StringVar(value=default_name)
        self.tags = tk.StringVar()
        self.expires = tk.StringVar()
        self.notes = tk.StringVar()
        self.error = tk.StringVar()
        fields = [("Name", self.name, ""), ("Tags", self.tags, "Comma-separated: travel, identity"),
                  ("Expires on", self.expires, "Optional. Example: 2027-12-31"), ("Notes", self.notes, "Optional")]
        for row, (label, variable, hint) in enumerate(fields):
            ttk.Label(self.body, text=label).grid(row=row * 2, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(self.body, textvariable=variable, width=42).grid(row=row * 2, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))
            if hint:
                ttk.Label(self.body, text=hint, style="Muted.TLabel").grid(row=row * 2 + 1, column=1, sticky="w", padx=(12, 0))
        ttk.Label(self.body, textvariable=self.error, style="Error.TLabel").grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))
        buttons = ttk.Frame(self.body)
        buttons.grid(row=9, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save to vault", style="Accent.TButton", command=self.save).pack(side="left")
        self.bind("<Return>", lambda event: self.save())

    def save(self) -> None:
        name = self.name.get().strip()
        if not name:
            self.error.set("Give the document a name.")
            return
        try:
            expires = parse_user_date(self.expires.get())
        except ValueError as error:
            self.error.set(str(error))
            return
        self.result = {"name": name, "tags": self.tags.get().split(","), "notes": self.notes.get().strip(), "expires": expires}
        self.destroy()


class ChangePasswordDialog(Dialog):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, "Change master password")
        self.first, self.second = tk.StringVar(), tk.StringVar()
        self.error = tk.StringVar()
        ttk.Label(self.body, justify="left", style="Muted.TLabel", wraplength=360,
                  text="The documents will be re-encrypted. If you forget the new password, "
                       "nobody will be able to recover them.").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.body, text="New password").grid(row=1, column=0, sticky="w", pady=(14, 0))
        ttk.Entry(self.body, textvariable=self.first, show="•", width=34).grid(
            row=1, column=1, sticky="ew", padx=(12, 0), pady=(14, 0))
        ttk.Label(self.body, text="Repeat it").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(self.body, textvariable=self.second, show="•", width=34).grid(
            row=2, column=1, sticky="ew", padx=(12, 0), pady=(10, 0))
        ttk.Label(self.body, textvariable=self.error, style="Error.TLabel").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        buttons = ttk.Frame(self.body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Change password", style="Accent.TButton", command=self.save).pack(side="left")
        self.bind("<Return>", lambda event: self.save())

    def save(self) -> None:
        if len(self.first.get()) < 10:
            self.error.set("Use at least 10 characters.")
            return
        if self.first.get() != self.second.get():
            self.error.set("The passwords do not match.")
            return
        self.result = self.first.get()
        self.destroy()


class VaultApp(AppWindow):
    def __init__(self, root_dir: Path | None = None, scrypt_n: int = crypto.DEFAULT_SCRYPT_N) -> None:
        super().__init__("Vault", "Your important documents, encrypted on your computer.", "vault",
                         icon="assets/vault.ico", size=(1000, 660))
        self.root_dir = Path(root_dir) if root_dir else default_root()
        self.scrypt_n = scrypt_n
        self.vault: Vault | None = None
        self.docs: list[Document] = []
        self._idle_job: str | None = None
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind_all("<Key>", self._touch, add="+")
        self.root.bind_all("<ButtonPress>", self._touch, add="+")
        self.show_unlock()

    def _close(self) -> None:
        if self.vault:
            self.vault.close()
            self.vault = None
        self.root.destroy()

    # -- locking and unlocking -----------------------------------------------
    def _clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()

    def show_unlock(self) -> None:
        self._clear()
        self.set_status("Your documents are encrypted and locked.")
        creating = not (self.root_dir / "vault.db").exists() and not (self.root_dir / "boveda.db").exists()
        card = ttk.Frame(self.body, style="Card.TFrame", padding=30)
        card.place(relx=0.5, rely=0.42, anchor="center")
        ttk.Label(card, text="Create your vault" if creating else "Unlock your vault", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(card, justify="left", style="Muted.TLabel", wraplength=360,
                  text=("Choose a master password of at least 10 characters.\nIf you forget it, nobody will be able to recover your documents."
                        if creating else "Enter your master password to see your documents.")).pack(anchor="w", pady=(4, 14))
        first, second = tk.StringVar(), tk.StringVar()
        entry = ttk.Entry(card, textvariable=first, show="•", width=36)
        entry.pack(fill="x")
        if creating:
            ttk.Label(card, text="Repeat the password", style="Muted.TLabel").pack(anchor="w", pady=(10, 2))
            ttk.Entry(card, textvariable=second, show="•", width=36).pack(fill="x")
        self.unlock_error = ttk.Label(card, text="", style="Error.TLabel")
        self.unlock_error.pack(anchor="w", pady=(8, 0))
        submit = lambda *_: self.submit_password(creating, first.get(), second.get())  # noqa: E731
        ttk.Button(card, text="Create vault" if creating else "Unlock", style="Accent.TButton", command=submit).pack(fill="x", pady=(10, 0))
        self.root.bind("<Return>", submit)
        entry.focus_set()

    def submit_password(self, creating: bool, password: str, repeat: str) -> None:
        try:
            if creating:
                if len(password) < 10:
                    raise ValueError("Use at least 10 characters.")
                if password != repeat:
                    raise ValueError("The passwords do not match.")
                self.vault = Vault.create(self.root_dir, password, self.scrypt_n)
            else:
                self.vault = Vault.open(self.root_dir, password)
        except WrongPassword:
            self.unlock_error.config(text="Wrong password.")
            return
        except (ValueError, VaultError) as error:
            self.unlock_error.config(text=str(error))
            return
        self.root.unbind("<Return>")
        self.show_main()

    def lock(self) -> None:
        if self.vault:
            self.vault.close()
            self.vault = None
        if self._idle_job:
            self.root.after_cancel(self._idle_job)
            self._idle_job = None
        self.show_unlock()

    def _touch(self, _event=None) -> None:
        if self.vault is None:
            return
        if self._idle_job:
            self.root.after_cancel(self._idle_job)
        self._idle_job = self.root.after(IDLE_LOCK_MS, self.lock)

    # -- main screen ----------------------------------------------------------
    def show_main(self) -> None:
        self._clear()
        self.query = tk.StringVar()
        self.only_soon = tk.BooleanVar(value=False)
        self.banner = tk.StringVar()

        top = ttk.Frame(self.body)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Search").pack(side="left")
        ttk.Entry(top, textvariable=self.query, width=30).pack(side="left", padx=(8, 16))
        ttk.Checkbutton(top, text="Only expiring soon", variable=self.only_soon, command=self.refresh).pack(side="left")
        ttk.Button(top, text="Lock", command=self.lock).pack(side="right")
        self.query.trace_add("write", lambda *_: self.refresh())

        ttk.Label(self.body, textvariable=self.banner, foreground="#8a5a00").pack(anchor="w", pady=(0, 6))
        self.table = Table(self.body, COLUMNS, on_select=self._update_buttons,
                           empty_text="Your vault is empty.\nPress \"Add document\" to store the first one.")
        self.table.pack(fill="both", expand=True)

        actions = ttk.Frame(self.body)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Add document…", style="Accent.TButton", command=self.add_document).pack(side="left")
        self.copy_button = ttk.Button(actions, text="Save a copy…", command=self.save_copy, state="disabled")
        self.copy_button.pack(side="left", padx=8)
        self.delete_button = ttk.Button(actions, text="Delete", command=self.delete, state="disabled")
        self.delete_button.pack(side="left")
        ttk.Button(actions, text="Change password…", command=self.change_password).pack(side="right")
        ttk.Button(actions, text="Back up vault…", command=self.backup).pack(side="right", padx=8)
        self.set_status(f"Vault open · {self.root_dir} · locks itself after 10 minutes idle")
        self._touch()
        self.refresh()

    def _selected_doc(self) -> Document | None:
        selected = self.table.selected()
        return next((d for d in self.docs if str(d.id) == selected), None)

    def _update_buttons(self) -> None:
        state = "normal" if self.table.selected() else "disabled"
        self.copy_button.config(state=state)
        self.delete_button.config(state=state)

    def refresh(self) -> None:
        if self.vault is None:
            return
        today = date.today()
        query = self.query.get().strip()
        docs = self.vault.search(query) if query else self.vault.list()
        if self.only_soon.get():
            docs = [d for d in docs if d.expires and (d.expires - today).days <= SOON_DAYS]
        self.docs = docs
        rows = []
        for doc in docs:
            text, tag = expiry_text(doc, today)
            rows.append((str(doc.id), (doc.name, ", ".join(doc.tags), doc.filename, human_size(doc.size), text), tag))
        self.table.set_rows(rows)
        urgent = len(self.vault.expiring(SOON_DAYS, today))
        self.banner.set(f"Warning: {urgent} document(s) expired or expiring in the next {SOON_DAYS} days." if urgent else "")
        self._update_buttons()

    # -- actions -----------------------------------------------------------------
    def add_document(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose the document you want to store")
        if not chosen:
            return
        source = Path(chosen)
        details = AddDialog(self.root, source.stem).show()
        if not details:
            return
        try:
            self.vault.add(source, details["name"], details["tags"], details["notes"], details["expires"])
        except OSError as error:
            messagebox.showerror("Could not save the document", str(error))
            return
        self.refresh()
        self.set_status(f"\"{details['name']}\" saved and encrypted. The original is still in its folder: delete it if you no longer need it.")

    def save_copy(self) -> None:
        doc = self._selected_doc()
        if not doc:
            return
        target = filedialog.asksaveasfilename(title="Save a decrypted copy", initialfile=doc.filename)
        if target:
            self.vault.get(doc.id, Path(target), overwrite=True)  # the save dialog already asked
            self.set_status(f"Copy saved to {target}. That copy is NOT encrypted.")

    def delete(self) -> None:
        doc = self._selected_doc()
        if doc and messagebox.askyesno("Delete document", f"Delete \"{doc.name}\" from the vault?\nThis cannot be undone.", default="no"):
            self.vault.remove(doc.id)
            self.refresh()

    def backup(self) -> None:
        target = filedialog.askdirectory(title="Choose a new, empty folder for the backup")
        if not target:
            return
        try:
            saved = self.vault.backup(Path(target))
        except (VaultError, OSError) as error:
            messagebox.showerror("Could not back up the vault", str(error))
            return
        messagebox.showinfo("Backup ready",
                            f"The encrypted vault was copied to:\n{saved}\n\nKeep that folder somewhere safe.")

    def change_password(self) -> None:
        new_password = ChangePasswordDialog(self.root).show()
        if not new_password:
            return
        try:
            self.vault.change_password(new_password)
        except (VaultError, OSError) as error:
            messagebox.showerror("Could not change the password", str(error))
            return
        messagebox.showinfo("Password changed",
                            "The documents were re-encrypted. Use the new password from now on.")


# Name used by the original Spanish version; kept so old imports keep working.
BovedaApp = VaultApp


def main() -> None:
    VaultApp().run()
