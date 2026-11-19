"""Tolerant reading of bank statements in CSV format."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .models import Charge

DATE_HEADERS = ("date", "fecha", "posted", "transaction date")
DESC_HEADERS = ("description", "descripcion", "details", "detail", "detalle", "concept", "concepto",
                "merchant", "comercio", "payee", "memo")
AMOUNT_HEADERS = ("amount", "monto", "importe", "value", "valor")
DEBIT_HEADERS = ("debit", "debito", "charge", "cargo", "withdrawal", "retiro")

_ISO = "%Y-%m-%d"
_DAY_FIRST = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y")
_MONTH_FIRST = ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y")


def _norm(header: str) -> str:
    table = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouaeiou")
    return header.translate(table).strip().lower()


def _find_column(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {h: _norm(h) for h in headers}
    for candidate in candidates:
        for original, name in normalized.items():
            if name == candidate:
                return original
    for candidate in candidates:
        for original, name in normalized.items():
            if candidate in name:
                return original
    return None


def _read_text(path: Path) -> str:
    """Bank exports are often UTF-8, but some are still Windows-1252/Latin-1."""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_amount(text: str) -> float | None:
    """Turn '1,234.56', '1.234,56', '(12.00)' or '-12,50' into a float."""
    cleaned = re.sub(r"[^\d,.\-()]", "", text or "")
    if not cleaned:
        return None
    negative = cleaned.startswith("-") or (cleaned.startswith("(") and cleaned.endswith(")"))
    cleaned = cleaned.strip("-()")
    if "," in cleaned and "." in cleaned:
        decimal = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
    elif "," in cleaned:
        decimal = "," if re.search(r",\d{1,2}$", cleaned) else "."
    else:
        decimal = "."
    thousands = "." if decimal == "," else ","
    cleaned = cleaned.replace(thousands, "").replace(decimal, ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def parse_date(text: str, day_first: bool = True) -> date | None:
    text = (text or "").strip()[:10]
    formats = (_ISO,) + (_DAY_FIRST + _MONTH_FIRST if day_first else _MONTH_FIRST + _DAY_FIRST)
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class ChargesReport:
    """Expenses that could be read, plus rows that looked like transactions and were not."""

    charges: list[Charge]
    skipped: int = 0
    skipped_samples: list[str] = field(default_factory=list)


def read_charges_report(path: Path, day_first: bool = True) -> ChargesReport:
    """Read a CSV, return the expenses and report the rows that could not be understood."""
    raw = _read_text(Path(path))
    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    headers = reader.fieldnames or []

    date_col = _find_column(headers, DATE_HEADERS)
    desc_col = _find_column(headers, DESC_HEADERS)
    debit_col = _find_column(headers, DEBIT_HEADERS)
    amount_col = _find_column(headers, AMOUNT_HEADERS)
    if not (date_col and desc_col and (amount_col or debit_col)):
        raise ValueError(
            "I could not find the date, description and amount columns. "
            f"Columns in the file: {', '.join(headers)}"
        )

    rows: list[tuple[date, str, float]] = []
    skipped = 0
    samples: list[str] = []
    for row in reader:
        values = [v.strip() for key, v in row.items() if key is not None and v and v.strip()]
        if not values:
            continue
        date_text = (row.get(date_col) or "").strip()
        day = parse_date(date_text, day_first)
        value = parse_amount(row.get(debit_col or amount_col, ""))
        if day is None or value is None:
            # Ignore notes and totals without a date; warn about a row that has a date but
            # no usable amount, or a date cell that cannot be read.
            if day is not None or date_text:
                skipped += 1
                if len(samples) < 3:
                    samples.append(" | ".join(values)[:160])
            continue
        rows.append((day, (row.get(desc_col) or "").strip(), value))

    # If the amounts have mixed signs, expenses are the negative ones.
    has_negative = any(v < 0 for _, _, v in rows)
    charges = []
    for day, desc, value in rows:
        # A debit column always means money going out, even when the bank writes it as negative.
        spent = abs(value) if debit_col else (-value if has_negative else value)
        if spent > 0:
            charges.append(Charge(day, desc, round(spent, 2)))
    return ChargesReport(charges, skipped, samples)


def read_charges(path: Path, day_first: bool = True) -> list[Charge]:
    """Read a CSV and return only the expenses (positive amounts)."""
    return read_charges_report(path, day_first).charges
