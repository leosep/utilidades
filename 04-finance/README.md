# Finance

A simple replacement for budgeting apps that disappear or fill up with ads: import your bank CSV, categorize with rules you control and see the month's summary. **It does not connect to your bank or send anything to the internet.** Your data lives in a local SQLite file.

## Usage

```bash
python -m finance import samples/transactions_example.csv
python -m finance pending                      # uncategorized transactions
python -m finance rule add transfer Family
python -m finance recategorize
python -m finance summary --month 2026-10
```

Commands: `import`, `rule add|remove|list`, `recategorize`, `pending`, `set ID CATEGORY`, `summary [--month yyyy-mm]`.

The original Spanish commands (`importar`, `regla`, `recategorizar`, `pendientes`, `asignar`, `resumen`, `--mes`, `--perfil`) still work.

The database is in `~/.finance/finance.db` (change it with `--db` or `$FINANCE_DB`). An existing `~/.finanzas/finanzas.db` is picked up automatically.

## How it works

- **Rules:** if the description contains the text (ignoring case and accents), the category is assigned. The first matching rule wins. A set of English rules is included, with Spanish bank keywords too; edit them to taste.
- **No duplicates:** you can import the same file twice or overlapping statements. Two identical purchases on the same day do count as two.
- **Assigning by hand** protects a category: `recategorize` will not change it.
- **Integer cents:** amounts are stored as integers, with no rounding errors.

## Profiles for your bank

If the columns are not detected automatically (date, description, amount), create a JSON file and pass it with `--profile`:

```json
{ "date": "Posting Date", "description": "Details", "debit": "Debit", "credit": "Credit", "day_first": true }
```

With `"invert": true` it reads credit cards that show expenses as positive amounts. There are two examples in `profiles/`. I do not include profiles for specific banks because I cannot check their real formats: if you give me a sample CSV (without real data), one can be prepared in minutes.

## Tests

```bash
python -m unittest discover -s tests -v
```

No external dependencies. Requires Python 3.10+.
