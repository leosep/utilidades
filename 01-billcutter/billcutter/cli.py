from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from .csvio import read_charges
from .detector import detect_subscriptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="billcutter",
        description="Find subscriptions and recurring charges in a CSV statement.",
    )
    parser.add_argument("file", type=Path, help="CSV exported from your bank or card")
    parser.add_argument("--month-first", action="store_true", help="Dates in mm/dd/yyyy format (default dd/mm/yyyy)")
    parser.add_argument("--days", type=int, default=30, help="Window for upcoming renewals (30)")
    parser.add_argument("--today", type=date.fromisoformat, default=None, help="Reference date yyyy-mm-dd (for testing)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    # Hidden aliases kept for compatibility with the original Spanish CLI.
    parser.add_argument("--mes-primero", dest="month_first", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dias", dest="days", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--hoy", dest="today", type=date.fromisoformat, help=argparse.SUPPRESS)
    return parser


def _format_report(subs, today: date, window: int) -> str:
    if not subs:
        return "I found no recurring charges."
    lines = [f"{'Merchant':<18}{'Frequency':<12}{'Amount':>10}{'Per month':>11}  Next charge"]
    for s in subs:
        lines.append(f"{s.merchant:<18}{s.frequency:<12}{s.typical_amount:>10,.2f}{s.monthly_cost:>11,.2f}  {s.next_charge}")
    monthly = sum(s.monthly_cost for s in subs)
    lines += ["", f"Monthly total: {monthly:,.2f}   Yearly total: {monthly * 12:,.2f}"]

    limit = today + timedelta(days=window)
    upcoming = [s for s in subs if today <= s.next_charge <= limit]
    if upcoming:
        lines += ["", f"Renewing in the next {window} days:"]
        for s in sorted(upcoming, key=lambda s: s.next_charge):
            extra = f"  -> cancel: {s.cancel_url}" if s.cancel_url else ""
            lines.append(f"  {s.next_charge}  {s.merchant} ({s.typical_amount:,.2f}){extra}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        charges = read_charges(args.file, day_first=not args.month_first)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    subs = detect_subscriptions(charges)
    if args.json:
        print(json.dumps([asdict(s) for s in subs], default=str, ensure_ascii=False, indent=2))
    else:
        print(_format_report(subs, args.today or date.today(), args.days))
    return 0
