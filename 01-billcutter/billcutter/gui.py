"""BillCutter graphical interface."""
from __future__ import annotations

import csv
import tkinter as tk
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from uikit import AppWindow, Table, card_row, money

from .csvio import read_charges_report
from .detector import detect_subscriptions
from .models import Subscription

COLUMNS = [
    ("merchant", "Merchant", 200, "w"),
    ("frequency", "Frequency", 110, "w"),
    ("amount", "Amount", 110, "e"),
    ("monthly", "Per month", 110, "e"),
    ("next", "Next charge", 130, "e"),
]


class BillCutterApp(AppWindow):
    def __init__(self) -> None:
        super().__init__("BillCutter", "Find out which subscriptions eat your money every month.",
                         "billcutter", icon="assets/billcutter.ico")
        self.path: Path | None = None
        self.subs: list[Subscription] = []
        self.month_first = tk.BooleanVar(value=False)
        self.monthly = tk.StringVar(value="—")
        self.yearly = tk.StringVar(value="—")
        self.count = tk.StringVar(value="—")
        self._build()
        self.set_status("Everything is analyzed on your computer; nothing is sent to the internet.")

    def _build(self) -> None:
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=(0, 14))
        ttk.Button(bar, text="Choose statement…", style="Accent.TButton", command=self.choose_file).pack(side="left")
        ttk.Checkbutton(bar, text="Dates are month/day/year", variable=self.month_first,
                        command=self.reload).pack(side="left", padx=18)
        self.export_button = ttk.Button(bar, text="Save report…", command=self.export, state="disabled")
        self.export_button.pack(side="right")

        card_row(self.body, [("Monthly spend", self.monthly), ("Yearly spend", self.yearly),
                             ("Subscriptions found", self.count)]).pack(fill="x", pady=(0, 14))

        self.table = Table(self.body, COLUMNS, on_open=self.open_cancel_page,
                           empty_text="Choose the CSV file you download from your bank or card\nand your recurring charges will appear here.")
        self.table.pack(fill="both", expand=True)
        self.table.set_rows([])
        ttk.Label(self.body, text="Double-click a merchant to open its cancellation page (available for some services only).",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    # -- actions --------------------------------------------------------------
    def choose_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose your statement",
                                            filetypes=[("Statements (CSV)", "*.csv"), ("All files", "*.*")])
        if chosen:
            self.load(Path(chosen))

    def reload(self) -> None:
        if self.path:
            self.load(self.path)

    def load(self, path: Path) -> None:
        try:
            report = read_charges_report(path, day_first=not self.month_first.get())
        except (OSError, ValueError) as error:
            messagebox.showwarning("Could not read the file", f"{error}\n\nTry the CSV you download from your bank's website.")
            return
        self.path = path
        self.subs = detect_subscriptions(report.charges)
        self._show()
        status = f"File: {path.name} · {len(report.charges)} expenses analyzed"
        if report.skipped:
            status += f" · {report.skipped} rows skipped"
        self.set_status(status)
        if report.skipped:
            samples = "\n".join(report.skipped_samples)
            messagebox.showwarning(
                "Some rows could not be read",
                f"{report.skipped} row(s) looked like transactions but could not be imported.\n"
                "Check the date format (the checkbox at the top) or edit the CSV.\n\n"
                f"{samples}",
            )

    def _show(self) -> None:
        soon = date.today() + timedelta(days=7)
        rows = []
        for index, sub in enumerate(self.subs):
            values = (sub.merchant.title(), sub.frequency.capitalize(), money(sub.typical_amount),
                      money(sub.monthly_cost), sub.next_charge.isoformat())
            rows.append((str(index), values, "warn" if date.today() <= sub.next_charge <= soon else ""))
        self.table.set_rows(rows)
        monthly = sum(s.monthly_cost for s in self.subs)
        self.monthly.set(money(monthly))
        self.yearly.set(money(monthly * 12))
        self.count.set(str(len(self.subs)))
        self.export_button.config(state="normal" if self.subs else "disabled")

    def open_cancel_page(self) -> None:
        selected = self.table.selected()
        sub = self.subs[int(selected)] if selected is not None else None
        if sub and sub.cancel_url:
            webbrowser.open(sub.cancel_url)
        elif sub:
            messagebox.showinfo("BillCutter", f"I don't have the cancellation page for {sub.merchant.title()}.\n"
                                "Look for it on their website, under \"Account\" or \"Subscription\".")

    def export(self) -> None:
        target = filedialog.asksaveasfilename(title="Save report", defaultextension=".csv", initialfile="subscriptions.csv",
                                              filetypes=[("CSV (Excel)", "*.csv")])
        if not target:
            return
        with open(target, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Merchant", "Frequency", "Amount", "Per month", "Next charge", "Cancellation page"])
            for s in self.subs:
                writer.writerow([s.merchant, s.frequency, s.typical_amount, s.monthly_cost, s.next_charge.isoformat(), s.cancel_url or ""])
        self.set_status(f"Report saved to {target}")


# Name used by the original Spanish version; kept so old imports keep working.
CortaCobrosApp = BillCutterApp


def main() -> None:
    BillCutterApp().run()
