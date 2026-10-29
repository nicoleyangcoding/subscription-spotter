"""Generate examples/sample-statement.csv: a year of made-up transactions.

All merchant names are fictional. Run: python examples/make_sample.py
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

START = dt.date(2025, 10, 1)
END = dt.date(2026, 9, 30)


def monthly(day: int, amount: float, desc: str, until: dt.date = END, raise_on=None, new_amount=None):
    d = START.replace(day=day)
    while d <= until:
        value = new_amount if raise_on and d >= raise_on else amount
        yield d, desc.format(n=random.randint(1000, 9999)), -value
        month = d.month % 12 + 1
        d = d.replace(year=d.year + (d.month == 12), month=month)


def build(seed: int = 7) -> list[tuple[dt.date, str, float]]:
    random.seed(seed)
    rows: list[tuple[dt.date, str, float]] = []
    rows += monthly(3, 15.49, "STREAMFLIX.COM 866-{n} CA", raise_on=dt.date(2026, 4, 1), new_amount=17.99)
    rows += monthly(9, 2.99, "CLOUDBOX STORAGE *{n}")
    rows += monthly(14, 39.00, "PULSE FITNESS CLUB #{n} SEATTLE WA")
    rows += monthly(21, 9.99, "SQ *GAMEHUB PLUS {n}", until=dt.date(2026, 5, 31))
    rows += monthly(1, 1850.00, "ACH DEBIT MAPLE COURT APTS RENT")
    rows += monthly(18, 64.20, "CITY POWER & LIGHT AUTOPAY")
    rows.append((dt.date(2025, 10, 6), "NEWSDAILY ANNUAL MEMBERSHIP", -119.00))
    rows.append((dt.date(2026, 9, 29), "NEWSDAILY ANNUAL MEMBERSHIP", -129.00))

    d = START
    while d <= END:
        if d.weekday() == 5:
            rows.append(
                (d, f"FRESHMART GROCERY #{random.randint(10, 99)}", -round(random.uniform(40, 160), 2))
            )
        if random.random() < 0.25:
            place = random.choice(["NOODLE BAR", "CORNER BAKERY", "TACO STAND", "BLUE DOOR CAFE"])
            rows.append((d, f"TST* {place} {random.randint(100, 999)}", -round(random.uniform(6, 48), 2)))
        if d.day in (1, 15):
            rows.append((d, "PAYROLL DEPOSIT ACME CORP", 2650.00))
        d += dt.timedelta(days=1)
    return sorted(rows, key=lambda r: r[0])


def main() -> None:
    out = Path(__file__).with_name("sample-statement.csv")
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Date", "Description", "Amount"])
        for day, desc, amount in build():
            writer.writerow([day.strftime("%m/%d/%Y"), desc, f"{amount:.2f}"])
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
