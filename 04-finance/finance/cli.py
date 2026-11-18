from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .importer import load_profile, read_rows
from .ledger import Ledger, default_db_path
from .parsing import format_cents
from .report import render_month

_ALIASES = {"importar": "import", "regla": "rule", "recategorizar": "recategorize",
            "pendientes": "pending", "asignar": "set", "resumen": "summary"}
_RULE_ALIASES = {"agregar": "add", "listar": "list", "quitar": "remove"}


def _safe_stdout() -> None:
    """Never crash because the Windows console cannot encode a description."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="finance", description="Offline personal finance.")
    p.add_argument("--db", type=Path, default=None, help="Database (default ~/.finance/finance.db or $FINANCE_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import", aliases=["importar"], help="Import a bank CSV")
    imp.add_argument("file", type=Path)
    imp.add_argument("--profile", "--perfil", dest="profile", type=Path, help="JSON with your bank's columns")

    rule = sub.add_parser("rule", aliases=["regla"], help="Manage categorization rules")
    rsub = rule.add_subparsers(dest="rule_cmd", required=True)
    add = rsub.add_parser("add", aliases=["agregar"])
    add.add_argument("text", help="Text the description must contain")
    add.add_argument("category")
    rsub.add_parser("list", aliases=["listar"])
    rm = rsub.add_parser("remove", aliases=["quitar"])
    rm.add_argument("text")

    sub.add_parser("recategorize", aliases=["recategorizar"], help="Reapply the rules (does not touch manual categories)")
    sub.add_parser("pending", aliases=["pendientes"], help="Uncategorized transactions, largest first")
    setc = sub.add_parser("set", aliases=["asignar"], help="Set the category of a transaction")
    setc.add_argument("id", type=int)
    setc.add_argument("category")
    rep = sub.add_parser("summary", aliases=["resumen"], help="Monthly summary")
    rep.add_argument("--month", "--mes", dest="month", help="yyyy-mm (default: the last month with data)")
    return p


def main(argv: list[str] | None = None) -> int:
    _safe_stdout()
    args = build_parser().parse_args(argv)
    cmd = _ALIASES.get(args.cmd, args.cmd)
    ledger = Ledger(args.db or default_db_path())
    try:
        if cmd == "import":
            profile = load_profile(args.profile) if args.profile else None
            added, dup = ledger.import_rows(read_rows(args.file, profile))
            print(f"Imported: {added}. Duplicates (already there): {dup}.")
            pending = len(ledger.uncategorized(10_000))
            if pending:
                print(f"{pending} uncategorized transactions. Review with: finance pending")
        elif cmd == "rule":
            action = _RULE_ALIASES.get(args.rule_cmd, args.rule_cmd)
            if action == "add":
                ledger.add_rule(args.text, args.category)
                print("Rule saved. Apply it to what you imported with: finance recategorize")
            elif action == "remove":
                print("Rule deleted." if ledger.remove_rule(args.text) else "That rule does not exist.")
            else:
                for pattern, category in ledger.rules():
                    print(f"  {pattern:<20} -> {category}")
        elif cmd == "recategorize":
            print(f"{ledger.recategorize()} transactions updated.")
        elif cmd == "pending":
            for tx_id, day, desc, cents in ledger.uncategorized():
                print(f"{tx_id:>5}  {day}  {desc[:40]:<40} {format_cents(cents):>12}")
        elif cmd == "set":
            print("Done." if ledger.set_category(args.id, args.category) else "That transaction does not exist.")
        elif cmd == "summary":
            month = args.month or (ledger.months() or [None])[-1]
            if month is None:
                print("No transactions yet. Import a CSV first.")
            else:
                print(render_month(month, ledger.month_rows(month)))
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        ledger.close()
    return 0
