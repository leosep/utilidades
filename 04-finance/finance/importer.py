"""CSV import through column profiles."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .parsing import parse_amount_cents, parse_date, strip_accents


@dataclass(frozen=True)
class Profile:
    """How to read a bank's CSV. Columns set to None are detected by name."""

    date: str | None = None
    description: str | None = None
    amount: str | None = None
    debit: str | None = None
    credit: str | None = None
    invert: bool = False        # True if the bank shows expenses as positive amounts (credit cards)
    day_first: bool = True      # dd/mm/yyyy dates


@dataclass(frozen=True)
class ParsedRow:
    day: date
    description: str
    cents: int  # expenses negative, income positive


@dataclass(frozen=True)
class ReadReport:
    """Rows that could be imported, plus the ones that could not be understood."""

    rows: list[ParsedRow]
    skipped: int = 0
    skipped_samples: list[str] = field(default_factory=list)


_AUTO = {
    "date": ("date", "fecha", "posted", "posting date"),
    "description": ("description", "descripcion", "details", "detail", "detalle", "concept", "concepto", "merchant", "memo"),
    "amount": ("amount", "monto", "importe", "value", "valor"),
    "debit": ("debit", "debito", "charge", "cargo", "withdrawal", "retiro"),
    "credit": ("credit", "credito", "deposit", "abono", "deposito"),
}


def load_profile(path: Path) -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(data) - set(Profile.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown fields in the profile: {', '.join(sorted(unknown))}")
    return Profile(**data)


def _read_text(path: Path) -> str:
    """Bank exports are often UTF-8, but some are still Windows-1252/Latin-1."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _resolve(headers: list[str], wanted: str | None, field: str) -> str | None:
    if wanted:
        if wanted not in headers:
            raise ValueError(f"The column \"{wanted}\" does not exist. Columns: {', '.join(headers)}")
        return wanted
    normalized = {h: strip_accents(h).strip().lower() for h in headers}
    for candidate in _AUTO[field]:
        for original, name in normalized.items():
            if name == candidate or candidate in name:
                return original
    return None


def _cell(record: dict, column: str | None) -> str:
    return (record.get(column) or "").strip() if column else ""


def read_rows_report(path: Path, profile: Profile | None = None) -> ReadReport:
    """Read a CSV and also count the rows that looked like transactions but could not be parsed.

    Bank statements often end with totals or notes. Those lines are ignored, but a row with a
    valid date and a broken amount (or the other way around) is reported as skipped so it
    cannot disappear silently.
    """
    profile = profile or Profile()
    raw = _read_text(Path(path))
    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    headers = reader.fieldnames or []

    cols = {f: _resolve(headers, getattr(profile, f), f) for f in _AUTO}
    if not (cols["date"] and cols["description"] and (cols["amount"] or cols["debit"] or cols["credit"])):
        raise ValueError(
            "I could not identify the date, description and amount columns. "
            f"File columns: {', '.join(headers)}. Create a JSON profile (see README)."
        )

    rows: list[ParsedRow] = []
    skipped = 0
    samples: list[str] = []
    for record in reader:
        values = [v.strip() for key, v in record.items() if key is not None and v and v.strip()]
        if not values:  # blank line between sections
            continue
        date_text = _cell(record, cols["date"])
        day = parse_date(date_text, profile.day_first)
        if cols["amount"]:
            cents = parse_amount_cents(_cell(record, cols["amount"]))
        else:
            debit_text = _cell(record, cols["debit"])
            credit_text = _cell(record, cols["credit"])
            debit = parse_amount_cents(debit_text) if debit_text else None
            credit = parse_amount_cents(credit_text) if credit_text else None
            if (debit_text and debit is None) or (credit_text and credit is None):
                cents = None  # an amount cell exists but cannot be read
            else:
                cents = abs(credit or 0) - abs(debit or 0)

        if day is None or cents is None or cents == 0:
            # A line without a date is a total or a note, not a transaction. A line with a date
            # that cannot be used is a real row that would otherwise disappear silently.
            if day is not None or date_text:
                skipped += 1
                if len(samples) < 3:
                    samples.append(" | ".join(values)[:160])
            continue
        rows.append(ParsedRow(day, _cell(record, cols["description"]),
                              -cents if profile.invert else cents))
    return ReadReport(rows, skipped, samples)


def read_rows(path: Path, profile: Profile | None = None) -> list[ParsedRow]:
    return read_rows_report(path, profile).rows
