import json
import tempfile
import unittest
from pathlib import Path

from branchchat.cli import main
from branchchat.loaders import load_conversations
from branchchat.render import path_to_markdown, to_html

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "chats_example.json"


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tree, self.linear = load_conversations(SAMPLE)

    def test_tree_structure_skips_empty_root(self):
        self.assertEqual(self.tree.roots, ["u1"])
        self.assertEqual(len(self.tree.messages), 8)
        self.assertEqual(self.tree.messages["a1"].children, ["u2", "u2b"])
        self.assertEqual(self.tree.branch_points(), 1)
        self.assertEqual({m.id for m in self.tree.leaves()}, {"a2", "a3b"})

    def test_main_path_follows_current_node(self):
        self.assertEqual([m.id for m in self.tree.path_to("a3b")], ["u1", "a1", "u2b", "a2b", "u3b", "a3b"])
        self.assertEqual(self.tree.main_path_ids(), {"u1", "a1", "u2b", "a2b", "u3b", "a3b"})

    def test_linear_format(self):
        self.assertEqual(len(self.linear.messages), 2)
        self.assertEqual(self.linear.messages["m1"].role, "assistant")
        self.assertEqual(self.linear.default_leaf(), "m1")

    def test_invalid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.json"
            bad.write_text('{"foo": 1}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_conversations(bad)

    def test_cyclic_mapping_is_rejected(self):
        def node(node_id, parent, child, role, text):
            return {node_id: {"id": node_id, "parent": parent, "children": [child],
                              "message": {"author": {"role": role}, "content": {"parts": [text]}}}}

        mapping = {}
        mapping.update(node("a", "b", "b", "user", "A"))
        mapping.update(node("b", "a", "a", "assistant", "B"))
        data = [{"title": "loop", "mapping": mapping}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "loop.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                load_conversations(path)
        self.assertIn("cycle", str(caught.exception))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tree = load_conversations(SAMPLE)[0]

    def test_html_shows_both_branches_and_escapes(self):
        self.tree.messages["a2"].text = "<script>alert(1)</script>"
        html = to_html(self.tree)
        self.assertIn("Here there are 2 branches", html)
        self.assertIn("chosen branch", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_markdown_contains_only_chosen_path(self):
        md = path_to_markdown(self.tree, "a2")
        self.assertIn("Make it simpler", md)
        self.assertNotIn("WhatsApp", md)

    def test_long_linear_chat_does_not_hit_recursion_limit(self):
        from branchchat.loaders import _from_linear
        conv = _from_linear("long", [("user" if i % 2 == 0 else "assistant", f"message {i}") for i in range(5000)])
        self.assertIn("message 4999", to_html(conv))


class CliTests(unittest.TestCase):
    def test_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.html"
            md = Path(tmp) / "t.md"
            self.assertEqual(main([str(SAMPLE), "list"]), 0)
            self.assertEqual(main([str(SAMPLE), "endings"]), 0)
            self.assertEqual(main([str(SAMPLE), "html", "-o", str(out)]), 0)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
            self.assertEqual(main([str(SAMPLE), "export", "--ending", "a2", "-o", str(md)]), 0)
            self.assertIn("local HTML page", md.read_text(encoding="utf-8"))
            self.assertEqual(main([str(SAMPLE), "export", "--ending", "zzz"]), 1)
            self.assertEqual(main([str(SAMPLE), "html", "-c", "9"]), 1)

    def test_legacy_spanish_commands_still_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "t.md"
            self.assertEqual(main([str(SAMPLE), "listar"]), 0)
            self.assertEqual(main([str(SAMPLE), "finales"]), 0)
            self.assertEqual(main([str(SAMPLE), "exportar", "--final", "a2", "--salida", str(md)]), 0)
            self.assertIn("local HTML page", md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
