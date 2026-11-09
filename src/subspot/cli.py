"""subspot command line."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from decimal import Decimal, InvalidOperation

from . import __version__
from .detect import Subscription, find_subscriptions
from .load import Columns, LoadError, read_csv


def money(value: Decimal, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def _note(sub: Subscription, symbol: str) -> str:
    if sub.price_changed:
        direction = "up" if sub.amount > sub.previous_amount else "down"
        return f"price {direction} from {money(sub.previous_amount, symbol)}"
    return ""


def table(subs: list[Subscription], symbol: str) -> str:
    head = ("MERCHANT", "EVERY", "AMOUNT", "PER YEAR", "LAST CHARGE", "NOTE")
    rows = [
        (
            s.name,
            s.frequency.label,
            money(s.amount, symbol),
            money(s.per_year, symbol),
            s.last.isoformat(),
            _note(s, symbol),
        )
        for s in subs
    ]
    widths = [max(len(r[i]) for r in (head, *rows)) for i in range(len(head))]
    right = {2, 3}
    lines = []
    for row in (head, *rows):
        cells = [c.rjust(widths[i]) if i in right else c.ljust(widths[i]) for i, c in enumerate(row)]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def report(subs: list[Subscription], symbol: str) -> str:
    active = [s for s in subs if s.active]
    ended = [s for s in subs if not s.active]
    if not subs:
        return "No recurring charges found. A statement covering 3 months or more gives the best results."
    parts = []
    if active:
        total = sum((s.per_year for s in active), Decimal(0))
        noun = "recurring charge" if len(active) == 1 else "recurring charges"
        parts += [
            table(active, symbol),
            "",
            f"{len(active)} {noun}, about {money(total, symbol)} per year "
            f"({money(total / 12, symbol)} per month).",
        ]
    if ended:
        parts += ["", "Possibly cancelled (no recent charge):", table(ended, symbol)]
    raised = [s for s in active if s.price_changed and s.amount > s.previous_amount]
    if raised:
        parts += ["", f"Price increases: {', '.join(s.name for s in raised)}."]
    return "\n".join(parts)


def as_rows(subs: list[Subscription]) -> list[dict[str, object]]:
    return [
        {
            "name": s.name,
            "every": s.frequency.label,
            "amount": str(s.amount),
            "per_year": str(s.per_year),
            "previous_amount": str(s.previous_amount) if s.previous_amount is not None else None,
            "first_charge": s.first.isoformat(),
            "last_charge": s.last.isoformat(),
            "next_expected": s.next_expected.isoformat() if s.active else None,
            "charges_seen": s.count,
            "active": s.active,
        }
        for s in subs
    ]


def iso_date(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a date like 2026-01-31, got {text!r}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subspot",
        description="Find recurring charges in bank or card CSV exports. Runs offline; nothing is uploaded.",
        epilog=(
            "Examples:\n"
            "  subspot transactions.csv\n"
            "  subspot jan-jun.csv jul-dec.csv --currency EUR\n"
            "  subspot transactions.csv --since 2026-01-01"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="+", help="one or more CSV exports")
    parser.add_argument("--format", choices=["table", "csv", "json"], default="table")
    parser.add_argument("--currency", default="$", help="symbol to show before amounts (default: $)")
    parser.add_argument(
        "--ignore", action="append", default=[], metavar="TEXT", help="skip descriptions containing TEXT"
    )
    parser.add_argument("--min-amount", default="0", metavar="N", help="ignore charges smaller than N")
    parser.add_argument(
        "--since", type=iso_date, metavar="DATE", help="only use transactions on or after DATE (YYYY-MM-DD)"
    )

    cols = parser.add_argument_group("column and format overrides (normally detected automatically)")
    cols.add_argument("--date-col", metavar="NAME")
    cols.add_argument("--desc-col", metavar="NAME")
    cols.add_argument("--amount-col", metavar="NAME")
    cols.add_argument("--debit-col", metavar="NAME")
    cols.add_argument("--credit-col", metavar="NAME")
    cols.add_argument("--date-format", metavar="FMT", help="strptime format, e.g. %%d/%%m/%%Y")
    cols.add_argument("--dayfirst", action="store_true", help="read 03/04/2026 as 3 April")
    sign = cols.add_mutually_exclusive_group()
    sign.add_argument("--charges-positive", action="store_true", help="spending is shown as positive numbers")
    sign.add_argument("--charges-negative", action="store_true", help="spending is shown as negative numbers")
    parser.add_argument("--version", action="version", version=f"subspot {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        min_amount = Decimal(args.min_amount)
    except InvalidOperation:
        parser.error("--min-amount must be a number")

    columns = None
    if args.date_col or args.desc_col or args.amount_col or args.debit_col:
        if not (args.date_col and args.desc_col and (args.amount_col or args.debit_col)):
            parser.error("when naming columns, give --date-col, --desc-col and --amount-col (or --debit-col)")
        columns = Columns(args.date_col, args.desc_col, args.amount_col, args.debit_col, args.credit_col)
    charges_positive = True if args.charges_positive else False if args.charges_negative else None

    transactions = []
    try:
        for path in args.files:
            transactions += read_csv(
                path,
                columns=columns,
                date_format=args.date_format,
                dayfirst=True if args.dayfirst else None,
                charges_positive=charges_positive,
            )
    except LoadError as exc:
        print(f"subspot: {exc}", file=sys.stderr)
        return 2

    if args.since:
        transactions = [t for t in transactions if t.date >= args.since]
        if not transactions:
            print(f"subspot: no transactions on or after {args.since}", file=sys.stderr)
            return 2

    subs = find_subscriptions(transactions, tuple(args.ignore), min_amount)

    if args.format == "json":
        print(json.dumps(as_rows(subs), indent=2))
    elif args.format == "csv":
        rows = as_rows(subs)
        writer = csv.DictWriter(
            sys.stdout, fieldnames=list(rows[0]) if rows else ["name"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    else:
        first = min(t.date for t in transactions)
        last = max(t.date for t in transactions)
        print(f"Read {len(transactions)} transactions from {first} to {last}.\n")
        print(report(subs, args.currency))
    return 0


if __name__ == "__main__":
    sys.exit(main())
