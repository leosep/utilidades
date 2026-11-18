"""SQLite storage. Amounts are stored as integer cents."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from collections import Counter
from pathlib import Path

from .importer import ParsedRow
from .rules import DEFAULT_RULES, UNCATEGORIZED, UNCATEGORIZED_LEGACY, categorize, normalize

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tx (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    description TEXT NOT NULL,
    cents INTEGER NOT NULL,
    category TEXT NOT NULL,
    manual INTEGER NOT NULL DEFAULT 0,
    dedupe TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    """`~/.finance/finance.db`, or the old `~/.finanzas/finanzas.db` when it already exists."""
    explicit = os.environ.get("FINANCE_DB") or os.environ.get("FINANZAS_DB")
    if explicit:
        return Path(explicit)
    modern = Path.home() / ".finance" / "finance.db"
    legacy = Path.home() / ".finanzas" / "finanzas.db"
    return modern if modern.exists() or not legacy.exists() else legacy


class Ledger:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)
        if is_new:
            self.db.executemany("INSERT INTO rules (pattern, category) VALUES (?, ?)", DEFAULT_RULES)
            self.db.commit()

    def close(self) -> None:
        self.db.close()

    # -- rules ----------------------------------------------------------------
    def rules(self) -> list[tuple[str, str]]:
        return list(self.db.execute("SELECT pattern, category FROM rules ORDER BY id"))

    def add_rule(self, pattern: str, category: str) -> None:
        # Upsert: editing a rule keeps its position, and the first matching rule still wins.
        self.db.execute(
            "INSERT INTO rules (pattern, category) VALUES (?, ?) "
            "ON CONFLICT(pattern) DO UPDATE SET category = excluded.category",
            (normalize(pattern), category.strip()),
        )
        self.db.commit()

    def remove_rule(self, pattern: str) -> bool:
        cursor = self.db.execute("DELETE FROM rules WHERE pattern = ?", (normalize(pattern),))
        self.db.commit()
        return cursor.rowcount > 0

    # -- transactions -----------------------------------------------------------
    def import_rows(self, rows: list[ParsedRow]) -> tuple[int, int]:
        """Return (new, duplicates). Re-importing the same file does not duplicate anything."""
        rules = self.rules()
        seen: Counter = Counter()
        added = duplicates = 0
        for row in rows:
            base = f"{row.day.isoformat()}|{normalize(row.description)}|{row.cents}"
            seen[base] += 1  # two identical purchases on the same day in one file count as two
            key = hashlib.sha1(f"{base}|{seen[base]}".encode()).hexdigest()
            try:
                self.db.execute(
                    "INSERT INTO tx (day, description, cents, category, dedupe) VALUES (?, ?, ?, ?, ?)",
                    (row.day.isoformat(), row.description, row.cents, categorize(row.description, rules), key),
                )
                added += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        self.db.commit()
        return added, duplicates

    def recategorize(self) -> int:
        """Reapply the rules to everything that was not categorized by hand."""
        rules = self.rules()
        changed = 0
        for tx_id, description, current in self.db.execute("SELECT id, description, category FROM tx WHERE manual = 0").fetchall():
            new = categorize(description, rules)
            if new != current:
                self.db.execute("UPDATE tx SET category = ? WHERE id = ?", (new, tx_id))
                changed += 1
        self.db.commit()
        return changed

    def set_category(self, tx_id: int, category: str) -> bool:
        cursor = self.db.execute("UPDATE tx SET category = ?, manual = 1 WHERE id = ?", (category.strip(), tx_id))
        self.db.commit()
        return cursor.rowcount > 0

    def uncategorized(self, limit: int = 30) -> list[tuple]:
        return list(self.db.execute(
            "SELECT id, day, description, cents FROM tx WHERE category IN (?, ?) ORDER BY ABS(cents) DESC LIMIT ?",
            (UNCATEGORIZED, UNCATEGORIZED_LEGACY, limit)))

    def months(self) -> list[str]:
        return [m for (m,) in self.db.execute("SELECT DISTINCT substr(day, 1, 7) FROM tx ORDER BY 1")]

    def month_rows(self, month: str) -> list[tuple[str, int]]:
        return list(self.db.execute("SELECT category, cents FROM tx WHERE substr(day, 1, 7) = ?", (month,)))

    def month_transactions(self, month: str) -> list[tuple]:
        """(id, day, description, cents, category) for the month, newest first."""
        return list(self.db.execute(
            "SELECT id, day, description, cents, category FROM tx WHERE substr(day, 1, 7) = ? ORDER BY day DESC, id DESC", (month,)))

    def categories(self) -> list[str]:
        found = {c for (c,) in self.db.execute("SELECT DISTINCT category FROM tx")}
        found |= {c for _, c in self.rules()}
        found.discard(UNCATEGORIZED)
        found.discard(UNCATEGORIZED_LEGACY)
        return sorted(found)
