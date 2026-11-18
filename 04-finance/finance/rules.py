"""Categorization rules: if the description contains the text, assign the category."""
from __future__ import annotations

from .parsing import strip_accents

UNCATEGORIZED = "Uncategorized"
UNCATEGORIZED_LEGACY = "Sin categoría"  # databases created by the Spanish version

DEFAULT_RULES = [
    ("supermerc", "Groceries"), ("grocery", "Groceries"), ("market", "Groceries"), ("colmado", "Groceries"),
    ("pharmac", "Health"), ("farmacia", "Health"), ("clinic", "Health"), ("clinica", "Health"),
    ("uber", "Transport"), ("gasolina", "Transport"), ("combustible", "Transport"), ("fuel", "Transport"),
    ("restaurant", "Dining"), ("restaurante", "Dining"), ("pizz", "Dining"), ("cafe", "Dining"), ("coffee", "Dining"),
    ("netflix", "Subscriptions"), ("spotify", "Subscriptions"),
    ("internet", "Utilities"), ("electric", "Utilities"), ("water", "Utilities"), ("agua", "Utilities"),
    ("salary", "Income"), ("salario", "Income"), ("payroll", "Income"), ("nomina", "Income"),
]


def normalize(text: str) -> str:
    return strip_accents(text).lower().strip()


def categorize(description: str, rules: list[tuple[str, str]]) -> str:
    """First matching rule wins. `rules` is ordered from oldest to newest."""
    haystack = normalize(description)
    for pattern, category in rules:
        if pattern in haystack:
            return category
    return UNCATEGORIZED
