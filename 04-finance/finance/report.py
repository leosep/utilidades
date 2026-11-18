from __future__ import annotations

from collections import defaultdict

from .parsing import format_cents


def summarize(rows: list[tuple[str, int]]) -> tuple[int, int, dict[str, int]]:
    """(income, expenses, spending by category) in cents."""
    income = sum(c for _, c in rows if c > 0)
    expenses = -sum(c for _, c in rows if c < 0)
    by_category: dict[str, int] = defaultdict(int)
    for category, cents in rows:
        if cents < 0:
            by_category[category] += -cents
    return income, expenses, dict(by_category)


def render_month(month: str, rows: list[tuple[str, int]], bar_width: int = 24) -> str:
    income, expenses, by_category = summarize(rows)

    lines = [
        f"Summary for {month}",
        f"  Income    {format_cents(income):>12}",
        f"  Expenses  {format_cents(expenses):>12}",
        f"  Balance   {format_cents(income - expenses):>12}",
        "",
        "Spending by category",
    ]
    if not by_category:
        return "\n".join(lines + ["  (no expenses)"])
    top = max(by_category.values())
    for category, cents in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True):
        # Plain ASCII bars: the Windows console cannot always print block characters.
        bar = "#" * max(1, round(cents / top * bar_width))
        lines.append(f"  {category:<18}{format_cents(cents):>12}  {cents / expenses:>4.0%}  {bar}")
    return "\n".join(lines)
