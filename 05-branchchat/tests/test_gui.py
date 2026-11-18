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

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "chats_example.json"


@unittest.skipUnless(HAS_DISPLAY, "requires a display (xvfb-run on Linux)")
class GuiTests(unittest.TestCase):
    def setUp(self):
        from branchchat.gui import BranchChatApp
        self.app = BranchChatApp()

    def tearDown(self):
        self.app.root.destroy()

    def test_open_file_selects_chosen_branch_and_previews_it(self):
        self.app.load(SAMPLE)
        self.app.root.update()
        self.assertEqual(self.app.conv_table.row_count(), 2)
        self.assertEqual(self.app.leaf_table.row_count(), 2)
        self.assertEqual(self.app.leaf_table.selected(), "a3b")
        text = self.app.preview.get("1.0", "end")
        self.assertIn("WhatsApp", text)
        self.assertNotIn("without a server", text)

    def test_choosing_other_leaf_changes_preview_and_saves_only_that_path(self):
        self.app.load(SAMPLE)
        self.app.root.update()  # process the conversation selection event
        self.app.leaf_table.tree.selection_set("a2")
        self.app.root.update()
        self.assertIn("without a server", self.app.preview.get("1.0", "end"))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "path.md"
            with mock.patch("branchchat.gui.filedialog.asksaveasfilename", return_value=str(target)):
                self.app.save_path()
            saved = target.read_text(encoding="utf-8")
        self.assertIn("without a server", saved)
        self.assertNotIn("WhatsApp", saved)

    def test_bad_file_warns(self):
        with mock.patch("branchchat.gui.messagebox.showwarning") as warn:
            self.app.load(Path(__file__))
        self.assertTrue(warn.called)


if __name__ == "__main__":
    unittest.main()
