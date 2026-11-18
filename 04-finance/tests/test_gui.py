import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

try:
    import tkinter as tk
    tk.Tk().destroy()
    HAS_DISPLAY = True
except Exception:
    HAS_DISPLAY = False

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "transactions_example.csv"


@unittest.skipUnless(HAS_DISPLAY, "requires a display (xvfb-run on Linux)")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from finance.gui import FinanceApp
        self.app = FinanceApp(Path(self._tmp.name) / "f.db")

    def tearDown(self):
        self.app._close()
        self._tmp.cleanup()

    def test_month_labels(self):
        from finance.gui import month_label
        self.assertEqual(month_label("2026-10"), "October 2026")

    def test_import_shows_summary_and_last_month(self):
        from finance.importer import read_rows
        self.assertEqual(self.app.income.get(), "—")
        self.app.import_rows(read_rows(SAMPLE))
        self.app.root.update()
        self.assertEqual(self.app.month.get(), "October 2026")
        self.assertEqual(self.app.income.get(), "2,500.00")
        self.assertEqual(self.app.expenses.get(), "669.74")
        self.assertGreater(self.app.summary_table.row_count(), 3)

    def test_rule_recategorizes_and_pending_filter(self):
        from finance.importer import read_rows
        self.app.import_rows(read_rows(SAMPLE))
        self.app.only_pending.set(True)
        self.app.refresh_transactions()
        self.assertEqual(self.app.moves_table.row_count(), 1)  # the October transfer
        self.app.rule_text.set("transfer")
        self.app.rule_category.set("Family")
        self.app.add_rule()
        self.assertEqual(self.app.moves_table.row_count(), 0)

    def test_change_category_by_hand(self):
        from finance.importer import read_rows
        self.app.import_rows(read_rows(SAMPLE))
        tx_id = self.app.moves_table.tree.get_children()[0]
        self.app.moves_table.tree.selection_set(tx_id)
        with mock.patch("finance.gui.CategoryDialog") as dialog:
            dialog.return_value.show.return_value = "Gifts"
            self.app.change_category()
        row = self.app.moves_table.tree.item(tx_id, "values")
        self.assertEqual(row[3], "Gifts")


if __name__ == "__main__":
    unittest.main()
