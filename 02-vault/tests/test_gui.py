import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

try:
    import tkinter as tk
    tk.Tk().destroy()
    HAS_DISPLAY = True
except Exception:
    HAS_DISPLAY = False

FAST = 2**10


class PureTests(unittest.TestCase):
    def test_parse_user_date(self):
        if not HAS_DISPLAY:
            self.skipTest("requires tkinter")
        from vault.gui import parse_user_date
        self.assertIsNone(parse_user_date("  "))
        self.assertEqual(parse_user_date("31/12/2027"), date(2027, 12, 31))
        self.assertEqual(parse_user_date("2027-12-31"), date(2027, 12, 31))
        with self.assertRaises(ValueError):
            parse_user_date("tomorrow")


@unittest.skipUnless(HAS_DISPLAY, "requires a display (xvfb-run on Linux)")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.doc = self.tmp / "passport.txt"
        self.doc.write_text("secret", encoding="utf-8")
        self.app = None

    def tearDown(self):
        if self.app is not None:
            self.app._close()
        self._tmp.cleanup()

    def test_create_unlock_add_lock_flow(self):
        from vault.gui import VaultApp
        self.app = VaultApp(self.tmp / "v", scrypt_n=FAST)
        self.app.show_unlock()
        self.app.submit_password(True, "short", "short")
        self.assertIsNone(self.app.vault)  # password too short
        self.app.submit_password(True, "long-enough-pass-1", "long-enough-pass-1")
        self.assertIsNotNone(self.app.vault)
        self.app.vault.add(self.doc, name="Passport", tags=["travel"], expires=date(2020, 1, 1))
        self.app.refresh()
        self.assertEqual(self.app.table.row_count(), 1)
        self.assertIn("expired", self.app.table.tree.item(self.app.table.tree.get_children()[0], "values")[4])
        self.assertIn("1 document", self.app.banner.get())
        self.app.query.set("missing")
        self.assertEqual(self.app.table.row_count(), 0)
        self.app.lock()
        self.assertIsNone(self.app.vault)
        self.app.show_unlock()
        self.app.submit_password(False, "another-long-key", "")
        self.assertIsNone(self.app.vault)
        self.app.submit_password(False, "long-enough-pass-1", "")
        self.assertIsNotNone(self.app.vault)

    def test_delete_asks_confirmation(self):
        from vault.gui import VaultApp
        self.app = VaultApp(self.tmp / "v2", scrypt_n=FAST)
        self.app.submit_password(True, "long-enough-pass-1", "long-enough-pass-1")
        doc_id = self.app.vault.add(self.doc, name="One")
        self.app.refresh()
        self.app.table.tree.selection_set(str(doc_id))
        with mock.patch("vault.gui.messagebox.askyesno", return_value=False):
            self.app.delete()
        self.assertEqual(len(self.app.vault.list()), 1)
        with mock.patch("vault.gui.messagebox.askyesno", return_value=True):
            self.app.delete()
        self.assertEqual(self.app.vault.list(), [])


if __name__ == "__main__":
    unittest.main()
