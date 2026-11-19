"""Finance graphical interface."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from uikit import AppWindow, Dialog, Table, card_row

from .importer import Profile, ParsedRow, ReadReport, load_profile, read_rows_report
from .ledger import DEFAULT_ACCOUNT, Ledger, default_db_path
from .parsing import format_cents
from .report import summarize
from .rules import UNCATEGORIZED, UNCATEGORIZED_LEGACY

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


def month_label(month: str) -> str:
    """'2026-10' -> 'October 2026'"""
    year, number = month.split("-")
    return f"{MONTHS[int(number) - 1]} {year}"


def day_label(iso_day: str) -> str:
    return iso_day


class CategoryDialog(Dialog):
    def __init__(self, parent: tk.Widget, description: str, current: str, categories: list[str]):
        super().__init__(parent, "Change category")
        ttk.Label(self.body, text=description, wraplength=360).pack(anchor="w")
        ttk.Label(self.body, text="Choose a category or type a new one:", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        self.value = tk.StringVar(value=current if current != UNCATEGORIZED else "")
        self.box = ttk.Combobox(self.body, textvariable=self.value, values=categories, width=34)
        self.box.pack(fill="x")
        buttons = ttk.Frame(self.body)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self.save).pack(side="left")
        self.bind("<Return>", lambda event: self.save())
        self.box.focus_set()

    def save(self) -> None:
        if self.value.get().strip():
            self.result = self.value.get().strip()
            self.destroy()


class FinanceApp(AppWindow):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__("Finance", "Your transactions organized and summarized, without connecting to any bank.",
                         "finance", icon="assets/finance.ico", size=(1000, 700))
        self.ledger = Ledger(db_path or default_db_path())
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.month = tk.StringVar()
        self.month_first = tk.BooleanVar(value=False)
        self.only_pending = tk.BooleanVar(value=False)
        self.income, self.expenses, self.balance = (tk.StringVar(value="—") for _ in range(3))
        self._month_by_label: dict[str, str] = {}
        self._build()
        self.refresh_all()

    def _close(self) -> None:
        self.ledger.close()
        self.root.destroy()

    # -- construction ----------------------------------------------------------------
    def _build(self) -> None:
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Import transactions…", style="Accent.TButton", command=self.import_csv).pack(side="left")
        ttk.Button(bar, text="Export CSV…", command=self.export_csv).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Back up…", command=self.backup).pack(side="left", padx=(8, 0))

        filters = ttk.Frame(self.body)
        filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="Account").pack(side="left")
        self.account = tk.StringVar(value=DEFAULT_ACCOUNT)
        self.account_box = ttk.Combobox(filters, textvariable=self.account, width=16)
        self.account_box.pack(side="left", padx=(8, 20))
        ttk.Checkbutton(filters, text="Dates are month/day/year", variable=self.month_first).pack(side="left")
        self.month_box = ttk.Combobox(filters, textvariable=self.month, state="readonly", width=18)
        self.month_box.pack(side="right")
        ttk.Label(filters, text="Month").pack(side="right", padx=(0, 8))
        self.month_box.bind("<<ComboboxSelected>>", lambda event: self.refresh_month())

        tabs = ttk.Notebook(self.body)
        tabs.pack(fill="both", expand=True)
        summary, moves, rules = (ttk.Frame(tabs, padding=(0, 14, 0, 0)) for _ in range(3))
        tabs.add(summary, text="  Summary  ")
        tabs.add(moves, text="  Transactions  ")
        tabs.add(rules, text="  Rules  ")

        card_row(summary, [("Income", self.income), ("Expenses", self.expenses), ("Balance", self.balance)]).pack(fill="x", pady=(0, 14))
        self.summary_table = Table(summary, [("category", "Category", 220, "w"), ("total", "Spent", 120, "e"),
                                             ("share", "% of spending", 110, "e"), ("bar", "", 260, "w")],
                                   empty_text="Import your bank CSV to see\nhow much you spend in each category.")
        self.summary_table.pack(fill="both", expand=True)

        filters = ttk.Frame(moves)
        filters.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(filters, text="Show only uncategorized", variable=self.only_pending,
                        command=self.refresh_transactions).pack(side="left")
        self.change_button = ttk.Button(filters, text="Change category…", command=self.change_category, state="disabled")
        self.change_button.pack(side="right")
        self.moves_table = Table(moves, [("day", "Date", 100, "w"), ("description", "Description", 300, "w"),
                                         ("amount", "Amount", 105, "e"), ("category", "Category", 150, "w"),
                                         ("account", "Account", 110, "w")],
                                 on_open=self.change_category, on_select=self._update_buttons,
                                 empty_text="No transactions in this month.")
        self.moves_table.pack(fill="both", expand=True)

        ttk.Label(rules, wraplength=820, justify="left", style="Muted.TLabel",
                  text="A rule says: \"if the description contains this text, assign this category\". "
                       "They are applied automatically to whatever you did not categorize by hand.").pack(anchor="w", pady=(0, 10))
        form = ttk.Frame(rules)
        form.pack(fill="x", pady=(0, 10))
        self.rule_text, self.rule_category = tk.StringVar(), tk.StringVar()
        ttk.Entry(form, textvariable=self.rule_text, width=24).pack(side="left")
        ttk.Label(form, text="  →  ").pack(side="left")
        self.rule_box = ttk.Combobox(form, textvariable=self.rule_category, width=22)
        self.rule_box.pack(side="left")
        ttk.Button(form, text="Add rule", style="Accent.TButton", command=self.add_rule).pack(side="left", padx=10)
        ttk.Button(form, text="Remove selected", command=self.remove_rule).pack(side="right")
        self.rules_table = Table(rules, [("pattern", "If it contains…", 300, "w"), ("category", "Category", 250, "w")])
        self.rules_table.pack(fill="both", expand=True)

    # -- data ---------------------------------------------------------------------------
    def refresh_all(self) -> None:
        months = self.ledger.months()
        self._month_by_label = {month_label(m): m for m in months}
        self.month_box["values"] = list(self._month_by_label)
        self.account_box["values"] = self.ledger.accounts()
        if months and self.month.get() not in self._month_by_label:
            self.month.set(month_label(months[-1]))
        self.refresh_month()
        self.refresh_rules()

    def current_month(self) -> str | None:
        return self._month_by_label.get(self.month.get())

    def refresh_month(self) -> None:
        month = self.current_month()
        rows = self.ledger.month_rows(month) if month else []
        income, expenses, by_category = summarize(rows)
        self.income.set(format_cents(income) if month else "—")
        self.expenses.set(format_cents(expenses) if month else "—")
        self.balance.set(format_cents(income - expenses) if month else "—")
        top = max(by_category.values(), default=1)
        table_rows = [(name, (name, format_cents(cents), f"{cents / expenses:.0%}", "█" * max(1, round(cents / top * 22))), "")
                      for name, cents in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)]
        self.summary_table.set_rows(table_rows)
        self.refresh_transactions()

    def refresh_transactions(self) -> None:
        month = self.current_month()
        rows = []
        for tx_id, day, description, cents, category, account in (self.ledger.month_transactions(month) if month else []):
            if self.only_pending.get() and category not in (UNCATEGORIZED, UNCATEGORIZED_LEGACY):
                continue
            pending = category in (UNCATEGORIZED, UNCATEGORIZED_LEGACY)
            rows.append((str(tx_id), (day_label(day), description, format_cents(cents), category, account),
                         "warn" if pending else ""))
        self.moves_table.set_rows(rows)
        self._update_buttons()

    def refresh_rules(self) -> None:
        self.rules_table.set_rows([(pattern, (pattern, category), "") for pattern, category in self.ledger.rules()])
        self.rule_box["values"] = self.ledger.categories()

    def _update_buttons(self) -> None:
        self.change_button.config(state="normal" if self.moves_table.selected() else "disabled")

    # -- actions --------------------------------------------------------------------------
    def _read_csv(self, path: Path) -> ReadReport | None:
        try:
            return read_rows_report(path, Profile(day_first=not self.month_first.get()))
        except ValueError as error:
            if not messagebox.askyesno("Could not recognize the columns", f"{error}\n\nDo you have a profile (.json) file for this bank?"):
                return None
        profile_path = filedialog.askopenfilename(title="Choose your bank profile", filetypes=[("Profile (JSON)", "*.json")])
        if not profile_path:
            return None
        try:
            return read_rows_report(path, load_profile(Path(profile_path)))
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not read the file", str(error))
            return None

    def import_csv(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose your bank file",
                                            filetypes=[("Transactions (CSV)", "*.csv"), ("All files", "*.*")])
        if not chosen:
            return
        report = self._read_csv(Path(chosen))
        if report is not None:
            self.import_rows(report)

    def import_rows(self, rows: list[ParsedRow] | ReadReport) -> None:
        report = rows if isinstance(rows, ReadReport) else ReadReport(list(rows))
        if not report.rows:
            messagebox.showwarning("Nothing imported",
                                   "No rows could be read. Check the date format or create a profile for your bank.")
            return
        added, duplicates = self.ledger.import_rows(report.rows, self.account.get())
        self.refresh_all()
        pending = len(self.ledger.uncategorized(10_000))
        message = f"Imported: {added}. Already there: {duplicates}."
        if report.skipped:
            message += f" Rows skipped: {report.skipped}."
        if pending:
            message += f" Uncategorized: {pending} (check the Transactions tab)."
        self.set_status(message)
        if report.skipped:
            samples = "\n".join(report.skipped_samples)
            messagebox.showwarning(
                "Some rows could not be read",
                f"{report.skipped} row(s) looked like transactions but could not be imported.\n"
                "Check the date format or edit the CSV and import it again.\n\n"
                f"{samples}",
            )

    def export_csv(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Export every transaction", defaultextension=".csv", initialfile="finance-export.csv",
            filetypes=[("CSV (Excel)", "*.csv")])
        if not target:
            return
        try:
            self.ledger.export_csv(Path(target))
        except OSError as error:
            messagebox.showerror("Could not export", str(error))
            return
        self.set_status(f"All transactions exported to {target}")

    def backup(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Back up the database", defaultextension=".db",
            initialfile=f"finance-backup-{date.today().isoformat()}.db",
            filetypes=[("SQLite database", "*.db")])
        if not target:
            return
        try:
            saved = self.ledger.backup(Path(target))
        except OSError as error:
            messagebox.showerror("Could not back up", str(error))
            return
        self.set_status(f"Backup saved to {saved}")

    def change_category(self) -> None:
        selected = self.moves_table.selected()
        if not selected:
            return
        values = self.moves_table.tree.item(selected, "values")
        new = CategoryDialog(self.root, values[1], values[3], self.ledger.categories()).show()
        if new:
            self.ledger.set_category(int(selected), new)
            self.refresh_all()

    def add_rule(self) -> None:
        text, category = self.rule_text.get().strip(), self.rule_category.get().strip()
        if not text or not category:
            messagebox.showinfo("Missing information", "Type the text and choose the category.")
            return
        self.ledger.add_rule(text, category)
        changed = self.ledger.recategorize()
        self.rule_text.set("")
        self.refresh_all()
        self.set_status(f"Rule saved. {changed} transactions recategorized.")

    def remove_rule(self) -> None:
        pattern = self.rules_table.selected()
        if pattern:
            self.ledger.remove_rule(pattern)
            self.refresh_rules()


# Name used by the original Spanish version; kept so old imports keep working.
FinanzasApp = FinanceApp


def main() -> None:
    FinanceApp().run()
