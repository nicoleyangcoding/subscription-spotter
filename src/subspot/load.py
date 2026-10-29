"""Read transaction CSV exports with automatic column and date detection."""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATE_HEADERS = ("transaction date", "posted date", "posting date", "date", "booking date", "value date")
DESC_HEADERS = ("description", "merchant", "payee", "name", "details", "memo", "narrative", "transaction")
AMOUNT_HEADERS = ("amount", "transaction amount", "value")
DEBIT_HEADERS = ("debit", "withdrawal", "withdrawals", "money out", "paid out", "outflow", "charge")
CREDIT_HEADERS = ("credit", "deposit", "deposits", "money in", "paid in", "inflow", "payment")

MDY = ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y")
DMY = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y")
ISO = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d")


class LoadError(Exception):
    pass


@dataclass(frozen=True)
class Transaction:
    date: dt.date
    description: str
    amount: Decimal  # charges are positive, money in is negative


@dataclass(frozen=True)
class Columns:
    date: str
    description: str
    amount: str | None = None
    debit: str | None = None
    credit: str | None = None


def _norm(header: str) -> str:
    return re.sub(r"[^a-z ]", "", header.lower()).strip()


def _find(headers: list[str], wanted: tuple[str, ...], exclude: set[str] = frozenset()) -> str | None:
    normal = {h: _norm(h) for h in headers if h not in exclude}
    for want in wanted:  # exact matches first, in priority order
        for header, norm in normal.items():
            if norm == want:
                return header
    for want in wanted:
        for header, norm in normal.items():
            if want in norm.split() or norm.startswith(want):
                return header
    return None


def detect_columns(headers: list[str]) -> Columns:
    date = _find(headers, DATE_HEADERS)
    desc = _find(headers, DESC_HEADERS, {date} if date else set())
    taken = {h for h in (date, desc) if h}
    amount = _find(headers, AMOUNT_HEADERS, taken)
    debit = _find(headers, DEBIT_HEADERS, taken)
    credit = _find(headers, CREDIT_HEADERS, taken | ({debit} if debit else set()))
    missing = [name for name, col in (("date", date), ("description", desc)) if not col]
    if not amount and not debit:
        missing.append("amount")
    if missing:
        raise LoadError(
            f"could not find the {', '.join(missing)} column(s) in: {', '.join(headers)}. "
            "Name them with --date-col, --desc-col and --amount-col."
        )
    return Columns(date, desc, amount if not debit else None, debit, credit)


def parse_amount(text: str) -> Decimal | None:
    raw = (text or "").strip()
    if not raw:
        return None
    negative = raw.startswith("(") and raw.endswith(")") or raw.startswith("-") or raw.endswith("-")
    upper = raw.upper()
    if upper.endswith("DR"):
        negative = True
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned:
        return None
    # "1.234,56" (European) vs "1,234.56"
    if "," in cleaned and (cleaned.rfind(",") > cleaned.rfind(".")) and len(cleaned.rsplit(",", 1)[1]) <= 2:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -value if negative else value


def choose_date_format(samples: list[str], dayfirst: bool | None) -> str:
    samples = [s.strip() for s in samples if s.strip()]
    if not samples:
        raise LoadError("no dates found")
    order = ISO + (DMY + MDY if dayfirst else MDY + DMY)
    if dayfirst is False:
        order = ISO + MDY
    for fmt in order:
        try:
            for sample in samples:
                dt.datetime.strptime(sample, fmt)
        except ValueError:
            continue
        return fmt
    raise LoadError(
        f"could not read dates like '{samples[0]}'. Use --date-format, e.g. --date-format %d/%m/%Y"
    )


def read_csv(
    path: str | Path,
    columns: Columns | None = None,
    date_format: str | None = None,
    dayfirst: bool | None = None,
    charges_positive: bool | None = None,
) -> list[Transaction]:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise LoadError(f"{path}: file not found") from None
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Some exports put account details above the header row; skip to the first row that looks like a header.
    start = next(
        (i for i, line in enumerate(lines[:30]) if re.search(r"\bdate\b", line, re.IGNORECASE)),
        0,
    )
    body = "\n".join(lines[start:])
    try:
        dialect = csv.Sniffer().sniff(body[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(body), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h]
    if not headers:
        raise LoadError(f"{path}: no header row found")
    cols = columns or detect_columns(headers)
    rows = list(reader)

    fmt = date_format or choose_date_format([r.get(cols.date) or "" for r in rows], dayfirst)

    parsed: list[tuple[dt.date, str, Decimal]] = []
    for row in rows:
        date_text = (row.get(cols.date) or "").strip()
        desc = " ".join((row.get(cols.description) or "").split())
        if not date_text or not desc:
            continue
        try:
            day = dt.datetime.strptime(date_text, fmt).date()
        except ValueError:
            continue
        if cols.debit:
            debit = parse_amount(row.get(cols.debit) or "")
            credit = parse_amount(row.get(cols.credit) or "") if cols.credit else None
            if debit:
                parsed.append((day, desc, abs(debit)))
            elif credit:
                parsed.append((day, desc, -abs(credit)))
            continue
        amount = parse_amount(row.get(cols.amount) or "")
        if amount is not None and amount != 0:
            parsed.append((day, desc, amount))

    if not parsed:
        raise LoadError(f"{path}: no transactions could be read")

    if not cols.debit:
        if charges_positive is None:
            # Most exports list spending as negative. Card statements often list it as positive.
            negatives = sum(1 for _, _, a in parsed if a < 0)
            charges_positive = negatives < len(parsed) / 2
        if not charges_positive:
            parsed = [(d, s, -a) for d, s, a in parsed]

    return [Transaction(d, s, a) for d, s, a in parsed]
