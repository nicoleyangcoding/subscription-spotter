"""Find charges that repeat on a regular schedule."""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .load import Transaction
from .merchants import display_name, merchant_key


@dataclass(frozen=True)
class Frequency:
    label: str
    days: float
    tolerance: float
    per_year: int
    min_charges: int


FREQUENCIES = (
    Frequency("week", 7, 2, 52, 4),
    Frequency("2 weeks", 14, 3, 26, 4),
    Frequency("month", 30.44, 4.5, 12, 3),
    Frequency("3 months", 91.3, 10, 4, 3),
    Frequency("6 months", 182.6, 15, 2, 2),
    Frequency("year", 365.25, 20, 1, 2),
)

AMOUNT_SPREAD = Decimal("0.25")  # charges within 25% of each other count as the same plan
MATCH_SHARE = 0.75  # share of gaps that must fit the schedule


@dataclass(frozen=True)
class Subscription:
    name: str
    frequency: Frequency
    amount: Decimal  # most recent charge
    previous_amount: Decimal | None  # set when the price changed
    first: dt.date
    last: dt.date
    count: int
    active: bool

    @property
    def per_year(self) -> Decimal:
        return self.amount * self.frequency.per_year

    @property
    def next_expected(self) -> dt.date:
        return self.last + dt.timedelta(days=round(self.frequency.days))

    @property
    def price_changed(self) -> bool:
        return self.previous_amount is not None


def _clusters(charges: list[Transaction]) -> list[list[Transaction]]:
    """Split one merchant's charges into groups of similar amounts (separate plans)."""
    groups: list[list[Transaction]] = []
    for tx in sorted(charges, key=lambda t: t.amount):
        if groups:
            anchor = statistics.median(t.amount for t in groups[-1])
            if abs(tx.amount - anchor) <= anchor * AMOUNT_SPREAD:
                groups[-1].append(tx)
                continue
        groups.append([tx])
    return groups


def _schedule(dates: list[dt.date]) -> Frequency | None:
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    if not gaps:
        return None
    for freq in FREQUENCIES:
        if len(dates) < freq.min_charges:
            continue
        fits = sum(1 for g in gaps if abs(g - freq.days) <= freq.tolerance)
        if fits / len(gaps) >= MATCH_SHARE:
            return freq
    return None


def _merge_similar(groups: dict[str, list[Transaction]]) -> dict[str, list[Transaction]]:
    """Merge keys like "CORNER BAKERY SAN" into "CORNER BAKERY" when one starts with the other."""
    merged: dict[str, list[Transaction]] = {}
    for key in sorted(groups, key=lambda k: (len(k.split()), k)):
        words = key.split()
        target = next(
            (
                m
                for m in merged
                if words[: len(m.split())] == m.split() and (len(m.split()) >= 2 or len(m) >= 6)
            ),
            None,
        )
        merged.setdefault(target or key, []).extend(groups[key])
    return merged


def find_subscriptions(
    transactions: list[Transaction],
    ignore: tuple[str, ...] = (),
    min_amount: Decimal = Decimal("0"),
) -> list[Subscription]:
    if not transactions:
        return []
    statement_end = max(t.date for t in transactions)
    ignore_upper = tuple(word.upper() for word in ignore)

    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        if tx.amount <= 0 or tx.amount < min_amount:
            continue
        if any(word in tx.description.upper() for word in ignore_upper):
            continue
        by_merchant[merchant_key(tx.description)].append(tx)

    found: list[Subscription] = []
    for key, charges in _merge_similar(by_merchant).items():
        for group in _clusters(charges):
            # Same-day duplicates (a charge and its retry) count once.
            unique: dict[dt.date, Transaction] = {}
            for tx in sorted(group, key=lambda t: t.date):
                unique[tx.date] = tx
            ordered = list(unique.values())
            freq = _schedule([t.date for t in ordered])
            if not freq:
                continue
            last = ordered[-1]
            previous = next(
                (t.amount for t in reversed(ordered) if abs(t.amount - last.amount) > Decimal("0.01")),
                None,
            )
            overdue = (statement_end - last.date).days > freq.days * 1.5 + freq.tolerance
            found.append(
                Subscription(
                    name=display_name(key),
                    frequency=freq,
                    amount=last.amount,
                    previous_amount=previous,
                    first=ordered[0].date,
                    last=last.date,
                    count=len(ordered),
                    active=not overdue,
                )
            )
    return sorted(found, key=lambda s: (-s.per_year, s.name))
