import tempfile
import unittest
from datetime import date
from pathlib import Path

from billcutter.cli import main
from billcutter.csvio import parse_amount, parse_date, read_charges, read_charges_report
from billcutter.detector import detect_subscriptions, normalize_merchant
from billcutter.models import Charge


def monthly(desc, amount, year=2026, months=range(1, 9)):
    return [Charge(date(year, m, 5), desc, amount) for m in months]


class ParseTests(unittest.TestCase):
    def test_amounts(self):
        self.assertEqual(parse_amount("1,234.56"), 1234.56)
        self.assertEqual(parse_amount("1.234,56"), 1234.56)
        self.assertEqual(parse_amount("(12.00)"), -12.0)
        self.assertEqual(parse_amount("RD$ 450,50"), 450.5)
        self.assertIsNone(parse_amount("abc"))

    def test_dates(self):
        self.assertEqual(parse_date("2026-03-04"), date(2026, 3, 4))
        self.assertEqual(parse_date("04/03/2026"), date(2026, 3, 4))
        self.assertEqual(parse_date("04/03/2026", day_first=False), date(2026, 4, 3))

    def test_merchant(self):
        self.assertEqual(normalize_merchant("NETFLIX.COM 4455"), "netflix")
        self.assertEqual(normalize_merchant("POS COMPRA Spotify P3B2"), "spotify")
        self.assertEqual(normalize_merchant("ONLINE PAYMENT Spotify"), "spotify")


class DetectorTests(unittest.TestCase):
    def test_monthly_detected_and_noise_ignored(self):
        noise = [Charge(date(2026, 1, d), "SUPERMARKET", a) for d, a in [(3, 40), (11, 85), (19, 22), (27, 130)]]
        subs = detect_subscriptions(monthly("NETFLIX.COM", 15.49) + noise)
        self.assertEqual([s.merchant for s in subs], ["netflix"])
        self.assertEqual(subs[0].frequency, "monthly")
        self.assertEqual(subs[0].next_charge, date(2026, 9, 5))
        self.assertIn("netflix", subs[0].cancel_url)

    def test_yearly_with_two_charges(self):
        charges = [Charge(date(2025, 3, 10), "MYWEB DOMAIN", 14.0), Charge(date(2026, 3, 10), "MYWEB DOMAIN", 14.0)]
        subs = detect_subscriptions(charges)
        self.assertEqual(subs[0].frequency, "yearly")
        self.assertAlmostEqual(subs[0].monthly_cost, 1.17, places=2)

    def test_two_unrelated_charges_are_not_a_subscription(self):
        charges = [Charge(date(2026, 1, 10), "UBER TRIP", 55.89), Charge(date(2026, 4, 12), "UBER TRIP", 31.20)]
        self.assertEqual(detect_subscriptions(charges), [])

    def test_price_change_within_tolerance(self):
        charges = monthly("SPOTIFY", 9.99, months=range(1, 5)) + monthly("SPOTIFY", 10.99, months=range(5, 8))
        self.assertEqual(len(detect_subscriptions(charges)), 1)

    def test_large_price_increase_is_one_subscription(self):
        # A 30% jump used to split the service into two overlapping subscriptions.
        charges = monthly("SPOTIFY", 9.99, months=range(1, 6)) + monthly("SPOTIFY", 12.99, months=range(6, 9))
        subs = detect_subscriptions(charges)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0].charges, 8)
        self.assertEqual(subs[0].typical_amount, 12.99)
        self.assertEqual(subs[0].next_charge, date(2026, 9, 5))

    def test_two_concurrent_plans_are_not_merged(self):
        same_month = [Charge(date(2026, m, d), "NETFLIX.COM", amount)
                      for m in range(1, 5) for d, amount in ((5, 9.99), (20, 19.99))]
        self.assertEqual(len(detect_subscriptions(same_month)), 2)


class CsvAndCliTests(unittest.TestCase):
    def test_semicolon_csv_with_signed_amounts(self):
        content = "Date;Description;Amount\n05/01/2026;GYM FIT;-25,00\n05/02/2026;GYM FIT;-25,00\n05/03/2026;GYM FIT;-25,00\n06/03/2026;SALARY;50000,00\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.csv"
            path.write_text(content, encoding="utf-8")
            charges = read_charges(path)
            self.assertEqual(len(charges), 3)
            self.assertEqual(main([str(path), "--today", "2026-03-20"]), 0)

    def test_spanish_headers_still_work(self):
        content = "Fecha;Descripción;Monto\n05/01/2026;GYM FIT;-25,00\n05/02/2026;GYM FIT;-25,00\n05/03/2026;GYM FIT;-25,00\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.csv"
            path.write_text(content, encoding="cp1252")
            self.assertEqual(len(read_charges(path)), 3)

    def test_negative_debit_column_counts_expenses(self):
        content = "Date,Description,Debit\n05/01/2026,GYM FIT,-25.00\n05/02/2026,GYM FIT,-25.00\n05/03/2026,GYM FIT,-25.00\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.csv"
            path.write_text(content, encoding="utf-8")
            self.assertEqual([c.amount for c in read_charges(path)], [25.0, 25.0, 25.0])

    def test_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            self.assertEqual(main([str(path)]), 1)

    def test_unreadable_rows_are_reported(self):
        content = ("Date,Description,Amount\n"
                   "05/01/2026,GYM FIT,-25.00\n"
                   "31/02/2026,BAD DATE,-25.00\n"
                   "05/03/2026,BAD AMOUNT,abc\n"
                   ",,99.00\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text(content, encoding="utf-8")
            report = read_charges_report(path)
        self.assertEqual(len(report.charges), 1)
        self.assertEqual(report.skipped, 2)
        self.assertEqual(len(report.skipped_samples), 2)


if __name__ == "__main__":
    unittest.main()
