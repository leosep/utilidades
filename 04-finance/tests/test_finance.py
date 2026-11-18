import tempfile
import unittest
from datetime import date
from pathlib import Path

from finance.cli import main
from finance.importer import Profile, load_profile, read_rows
from finance.ledger import Ledger
from finance.parsing import parse_amount_cents
from finance.report import render_month

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "transactions_example.csv"
PROFILES = Path(__file__).resolve().parent.parent / "profiles"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.ledger = Ledger(self.tmp / "f.db")

    def tearDown(self):
        self.ledger.close()
        self._tmp.cleanup()

    def csv(self, content: str, name="m.csv") -> Path:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path


class ParsingTests(unittest.TestCase):
    def test_cents_have_no_float_errors(self):
        self.assertEqual(parse_amount_cents("1,234.56"), 123456)
        self.assertEqual(parse_amount_cents("1.234,56"), 123456)
        self.assertEqual(parse_amount_cents("-0.10"), -10)
        self.assertEqual(parse_amount_cents("(12.5)"), -1250)
        self.assertEqual(parse_amount_cents("19.99"), 1999)
        self.assertIsNone(parse_amount_cents(""))
        self.assertIsNone(parse_amount_cents("abc"))

    def test_thousands_separator_and_trailing_minus(self):
        # "1.234" is 1,234.00, not 1.23; a trailing minus also means an expense.
        self.assertEqual(parse_amount_cents("1.234"), 123400)
        self.assertEqual(parse_amount_cents("1,234"), 123400)
        self.assertEqual(parse_amount_cents("1.234.567"), 123456700)
        self.assertEqual(parse_amount_cents("15,49-"), -1549)
        self.assertEqual(parse_amount_cents("1,5"), 150)


class ImportTests(Base):
    def test_import_categorizes_and_is_idempotent(self):
        rows = read_rows(SAMPLE)
        added, dup = self.ledger.import_rows(rows)
        self.assertEqual((added, dup), (len(rows), 0))
        self.assertEqual(self.ledger.import_rows(rows), (0, len(rows)))

    def test_identical_purchases_same_day_both_count(self):
        path = self.csv("Date,Description,Amount\n2026-10-01,COFFEE,-3.00\n2026-10-01,COFFEE,-3.00\n")
        rows = read_rows(path)
        self.assertEqual(self.ledger.import_rows(rows), (2, 0))
        self.assertEqual(self.ledger.import_rows(rows), (0, 2))

    def test_debit_credit_profile(self):
        path = self.csv("Posting Date;Details;Debit;Credit\n03/10/2026;PURCHASE X;45,50;\n04/10/2026;DEPOSIT;;1.000,00\n")
        rows = read_rows(path, load_profile(PROFILES / "debit_credit.json"))
        self.assertEqual([r.cents for r in rows], [-4550, 100000])

    def test_inverted_profile_for_credit_cards(self):
        path = self.csv("Date,Description,Amount\n03/10/2026,STORE,20.00\n")
        rows = read_rows(path, load_profile(PROFILES / "positive_card_expenses.json"))
        self.assertEqual(rows[0].cents, -2000)

    def test_unknown_columns_give_helpful_error(self):
        with self.assertRaises(ValueError):
            read_rows(self.csv("a,b\n1,2\n"))
        with self.assertRaises(ValueError):
            read_rows(self.csv("Date,Description,Amount\n"), Profile(amount="Nope"))

    def test_spanish_headers_still_work(self):
        path = self.csv("Fecha,Descripción,Monto\n03/10/2026,TIENDA,-20,00\n")
        self.assertEqual(read_rows(path)[0].cents, -2000)


class RulesAndReportTests(Base):
    def test_rules_manual_and_recategorize(self):
        self.ledger.import_rows(read_rows(SAMPLE))
        pending = {desc for _, _, desc, _ in self.ledger.uncategorized()}
        self.assertIn("TRANSFER TO JOHN DOE", pending)
        self.assertNotIn("NETFLIX.COM", pending)

        self.ledger.add_rule("transfer", "Family")
        self.assertGreater(self.ledger.recategorize(), 0)
        self.assertEqual(self.ledger.uncategorized(), [])

        tx_id = self.ledger.db.execute("SELECT id FROM tx WHERE description LIKE 'UBER%' LIMIT 1").fetchone()[0]
        self.ledger.set_category(tx_id, "Work")
        self.ledger.recategorize()
        self.assertEqual(self.ledger.db.execute("SELECT category FROM tx WHERE id=?", (tx_id,)).fetchone()[0], "Work")

    def test_editing_a_rule_keeps_its_position(self):
        self.ledger.add_rule("alpha", "First")
        self.ledger.add_rule("beta", "Second")
        self.ledger.add_rule("alpha", "Updated")
        rules = self.ledger.rules()
        self.assertEqual(dict(rules)["alpha"], "Updated")
        order = [pattern for pattern, _ in rules]
        self.assertLess(order.index("alpha"), order.index("beta"))

    def test_monthly_report_totals(self):
        self.ledger.import_rows(read_rows(SAMPLE))
        self.assertEqual(self.ledger.months(), ["2026-09", "2026-10"])
        text = render_month("2026-10", self.ledger.month_rows("2026-10"))
        self.assertIn("Income", text)
        self.assertIn("2,500.00", text)
        self.assertIn("Groceries", text)
        rows = self.ledger.month_rows("2026-10")
        income = sum(c for _, c in rows if c > 0)
        self.assertEqual(income, 250000)

    def test_cli_end_to_end(self):
        db = str(self.tmp / "cli.db")
        self.assertEqual(main(["--db", db, "import", str(SAMPLE)]), 0)
        self.assertEqual(main(["--db", db, "rule", "add", "transfer", "Family"]), 0)
        self.assertEqual(main(["--db", db, "recategorize"]), 0)
        self.assertEqual(main(["--db", db, "summary", "--month", "2026-10"]), 0)
        self.assertEqual(main(["--db", db, "import", str(self.tmp / "missing.csv")]), 1)

    def test_legacy_spanish_commands_still_work(self):
        db = str(self.tmp / "legacy.db")
        self.assertEqual(main(["--db", db, "importar", str(SAMPLE)]), 0)
        self.assertEqual(main(["--db", db, "regla", "agregar", "transfer", "Family"]), 0)
        self.assertEqual(main(["--db", db, "resumen", "--mes", "2026-10"]), 0)


if __name__ == "__main__":
    unittest.main()
