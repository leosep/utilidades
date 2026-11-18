import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

try:
    import tkinter as tk
    tk.Tk().destroy()
    HAS_DISPLAY = True
except Exception:  # no tkinter or no display (use xvfb-run on Linux)
    HAS_DISPLAY = False

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "statement_example.csv"


@unittest.skipUnless(HAS_DISPLAY, "requires a display (xvfb-run on Linux)")
class GuiTests(unittest.TestCase):
    def test_load_sample_fills_table_and_totals(self):
        from billcutter.gui import BillCutterApp
        app = BillCutterApp()
        try:
            app.load(SAMPLE)
            app.root.update()
            self.assertEqual(app.table.row_count(), 4)
            self.assertEqual(app.count.get(), "4")
            self.assertEqual(app.monthly.get(), "51.65")
            self.assertEqual(str(app.export_button.cget("state")), "normal")
        finally:
            app.root.destroy()

    def test_bad_file_keeps_table_empty(self):
        from unittest import mock
        from billcutter.gui import BillCutterApp
        app = BillCutterApp()
        try:
            with mock.patch("billcutter.gui.messagebox.showwarning") as warn:
                app.load(Path(__file__))  # a .py file is not a valid CSV
            self.assertTrue(warn.called)
            self.assertEqual(app.table.row_count(), 0)
        finally:
            app.root.destroy()


if __name__ == "__main__":
    unittest.main()
