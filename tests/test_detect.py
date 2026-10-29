from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

from subspot.cli import main
from subspot.detect import find_subscriptions
from subspot.load import Transaction
from subspot.merchants import merchant_key

SAMPLE = Path(__file__).parent.parent / "examples" / "sample-statement.csv"


def tx(day: str, desc: str, amount: str) -> Transaction:
    return Transaction(dt.date.fromisoformat(day), desc, Decimal(amount))


def monthly(desc: str, amount: str, months: int, start=(2026, 1, 5)) -> list[Transaction]:
    y, m, d = start
    out = []
    for i in range(months):
        mm = (m - 1 + i) % 12 + 1
        yy = y + (m - 1 + i) // 12
        out.append(tx(f"{yy:04d}-{mm:02d}-{d:02d}", desc, amount))
    return out


def test_merchant_key():
    assert merchant_key("SQ *CORNER BAKERY #0412 SEATTLE WA") == "CORNER BAKERY"
    assert merchant_key("SQ *CORNER BAKERY #0398") == "CORNER BAKERY"
    assert merchant_key("STREAMFLIX.COM 866-579-1234 CA") == "STREAMFLIX"
    assert merchant_key("POS DEBIT PULSE FITNESS CLUB 4421") == "PULSE FITNESS CLUB"
    assert merchant_key("CITY POWER & LIGHT AUTOPAY") == "CITY POWER & LIGHT"
    assert merchant_key("NEWSDAILY ANNUAL MEMBERSHIP") == "NEWSDAILY"
    assert merchant_key("COLORADO TRAILS CO") == "COLORADO TRAILS"


def test_location_variants_merge():
    charges = [
        tx("2026-01-05", "PULSE FITNESS CLUB SAN DIEGO CA", "39"),
        tx("2026-02-05", "PULSE FITNESS CLUB", "39"),
        tx("2026-03-05", "PULSE FITNESS CLUB #22", "39"),
    ]
    (sub,) = find_subscriptions(charges)
    assert sub.name == "Pulse Fitness Club" and sub.count == 3


def test_monthly_detected():
    (sub,) = find_subscriptions(monthly("CLOUDBOX *1234", "2.99", 4))
    assert sub.frequency.label == "month" and sub.per_year == Decimal("35.88") and sub.active


def test_too_few_or_irregular_not_detected():
    assert find_subscriptions(monthly("CLOUDBOX", "2.99", 2)) == []
    irregular = [tx("2026-01-01", "CAFE", "5"), tx("2026-01-09", "CAFE", "5"), tx("2026-02-20", "CAFE", "5")]
    assert find_subscriptions(irregular) == []


def test_variable_grocery_not_detected():
    weekly = [
        tx(f"2026-01-{d:02d}", "FRESHMART", amt)
        for d, amt in [(3, "40"), (10, "155"), (17, "72"), (24, "110")]
    ]
    assert find_subscriptions(weekly) == []


def test_price_change_and_two_plans_same_merchant():
    charges = monthly("APPSTORE", "2.99", 4) + monthly("APPSTORE", "9.99", 3, (2026, 1, 20))
    charges += monthly("APPSTORE", "10.99", 2, (2026, 4, 20))
    subs = {s.amount: s for s in find_subscriptions(charges)}
    assert set(subs) == {Decimal("2.99"), Decimal("10.99")}
    assert subs[Decimal("10.99")].previous_amount == Decimal("9.99")


def test_cancelled_flagged():
    charges = monthly("GAMEHUB", "9.99", 4) + [tx("2026-09-30", "SHOP", "1")]
    (sub,) = find_subscriptions(charges)
    assert not sub.active


def test_income_and_ignore():
    charges = monthly("PAYROLL", "-2650", 6) + monthly("GYM", "39", 4)
    assert [s.name for s in find_subscriptions(charges)] == ["Gym"]
    assert find_subscriptions(charges, ignore=("gym",)) == []


def test_yearly_needs_two():
    charges = [tx("2025-03-01", "NEWSDAILY ANNUAL", "119"), tx("2026-03-02", "NEWSDAILY ANNUAL", "119")]
    (sub,) = find_subscriptions(charges)
    assert sub.frequency.label == "year"


def test_same_day_retry_counts_once():
    charges = monthly("CLOUDBOX", "2.99", 3) + [tx("2026-02-05", "CLOUDBOX", "2.99")]
    (sub,) = find_subscriptions(charges)
    assert sub.count == 3


def test_cli_on_sample(capsys):
    assert main([str(SAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "Streamflix" in out and "price up from $15.49" in out
    assert "Possibly cancelled" in out and "Gamehub Plus" in out
    assert "Freshmart" not in out and "Payroll" not in out


def test_cli_json_and_csv(capsys):
    import json

    main([str(SAMPLE), "--format", "json"])
    rows = json.loads(capsys.readouterr().out)
    assert {"name", "every", "per_year", "active"} <= set(rows[0])
    main([str(SAMPLE), "--format", "csv"])
    assert capsys.readouterr().out.startswith("name,every,amount")


def test_cli_errors(tmp_path, capsys):
    assert main([str(tmp_path / "missing.csv")]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    assert main([str(bad)]) == 2
    assert "--date-col" in capsys.readouterr().err
