"""Conversion of statement amount and date strings."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _decimal_separator(cleaned: str) -> str | None:
    """Guess whether '.' or ',' is the decimal mark; None means both are thousands separators."""
    dot, comma = cleaned.rfind("."), cleaned.rfind(",")
    if dot >= 0 and comma >= 0:
        return "," if comma > dot else "."
    separator = "." if dot >= 0 else "," if comma >= 0 else None
    if separator is None:
        return None
    parts = cleaned.split(separator)
    # "1.234" is 1234 in Spanish bank files; "1.23" is 1.23 in English ones.
    return separator if len(parts) == 2 and 1 <= len(parts[1]) <= 2 else None


def parse_amount_cents(text: str) -> int | None:
    """'1,234.56', '1.234,56', '(12.00)', '-12,50', '15,49-' -> cents (integer, no floating point errors)."""
    cleaned = re.sub(r"[^\d,.\-()]", "", text or "")
    if not cleaned:
        return None
    negative = cleaned.startswith("-") or cleaned.endswith("-") or (cleaned.startswith("(") and cleaned.endswith(")"))
    cleaned = cleaned.strip("-()")
    if not cleaned:
        return None
    decimal = _decimal_separator(cleaned)
    if decimal:
        cleaned = cleaned.replace("," if decimal == "." else ".", "")
        whole, _, frac = cleaned.partition(decimal)
    else:
        whole, frac = cleaned.replace(".", "").replace(",", ""), ""
    if not whole.isdigit():
        return None
    try:
        cents = int(whole or "0") * 100 + int((frac + "00")[:2])
    except ValueError:
        return None
    return -cents if negative else cents


_FORMATS_DAY_FIRST = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%m/%d/%Y")
_FORMATS_MONTH_FIRST = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%d/%m/%Y")


def parse_date(text: str, day_first: bool = True) -> date | None:
    text = (text or "").strip()[:10]
    for fmt in _FORMATS_DAY_FIRST if day_first else _FORMATS_MONTH_FIRST:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_cents(cents: int) -> str:
    return f"{cents / 100:,.2f}"
