"""CSV import through column profiles."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
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


def read_rows(path: Path, profile: Profile | None = None) -> list[ParsedRow]:
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
    for record in reader:
        day = parse_date(record.get(cols["date"], ""), profile.day_first)
        if day is None:
            continue
        if cols["amount"]:
            cents = parse_amount_cents(record.get(cols["amount"], ""))
        else:
            debit = abs(parse_amount_cents(record.get(cols["debit"] or "", "")) or 0)
            credit = abs(parse_amount_cents(record.get(cols["credit"] or "", "")) or 0)
            cents = credit - debit
        if cents is None or cents == 0:
            continue
        rows.append(ParsedRow(day, (record.get(cols["description"]) or "").strip(), -cents if profile.invert else cents))
    return rows
