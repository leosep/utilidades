# BillCutter

Find subscriptions and recurring charges in the CSV you export from your bank or card. Everything runs on your computer: it never connects to a bank or sends data anywhere.

## Usage

```bash
python -m billcutter samples/statement_example.csv
python -m billcutter my_statement.csv --days 45 --json
```

Options: `--month-first` (mm/dd/yyyy dates), `--days N` (upcoming renewal window), `--json`. Dates are `dd/mm/yyyy` by default; if the file has dates like `05/13/2026` use the month-first option, otherwise rows are reported as unreadable. Rows that look like transactions but cannot be parsed are listed instead of being dropped silently.

The original Spanish aliases `--mes-primero`, `--dias` and `--hoy` still work.

## What it detects

- Weekly, monthly, quarterly, semiannual and yearly frequencies, with a tolerance in the dates and 15% in the amount (in case the price goes up). A price increase larger than that is still reported as one subscription, using the new price.
- Calculates the equivalent monthly cost, the yearly total and the next charge date.
- Reads CSV with `,`, `;` or tabs, and amounts with a sign, in parentheses or in a debit column.

Cancellation links (`detector.py`, `CANCEL_URLS`) cover only a few services and may change: check them.

## Tests

```bash
python -m unittest discover -s tests -v
```

No external dependencies. Requires Python 3.10+.
