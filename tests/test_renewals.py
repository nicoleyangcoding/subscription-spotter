from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

from subspot.cli import main
from subspot.detect import FREQUENCIES, Subscription
from subspot.renewals import _fold, ics

SAMPLE = Path(__file__).parent.parent / "examples" / "sample-statement.csv"
NOW = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)
FREQ = {f.label: f for f in FREQUENCIES}


def sub(name: str, every: str, last: str, amount: str = "9.99", active: bool = True) -> Subscription:
    return Subscription(
        name=name,
        frequency=FREQ[every],
        amount=Decimal(amount),
        previous_amount=None,
        first=dt.date(2025, 1, 1),
        last=dt.date.fromisoformat(last),
        count=4,
        active=active,
    )


def events(text: str) -> list[str]:
    return text.split("BEGIN:VEVENT")[1:]


def test_ics_events_rules_and_reminders():
    text = ics(
        [
            sub("Streamflix", "month", "2026-09-03", "17.99"),
            sub("Newsdaily", "year", "2026-09-29", "129"),
            sub("Gamehub Plus", "month", "2026-05-21", active=False),
        ],
        "$",
        now=NOW,
    )
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    monthly, yearly = events(text)
    assert "DTSTART;VALUE=DATE:20261003" in monthly
    assert "SUMMARY:Streamflix due ($17.99)" in monthly
    assert "RRULE:FREQ=MONTHLY\r\n" in monthly and "TRIGGER:-P1D" in monthly
    assert "DTSTART;VALUE=DATE:20270929" in yearly
    assert "RRULE:FREQ=YEARLY" in yearly and "TRIGGER:-P14D" in yearly
    assert "Gamehub" not in text
    assert "DTSTAMP:20261001T120000Z" in text


def test_ics_uid_is_stable_and_text_escaped():
    one = ics([sub("Pay, Inc; Plus", "month", "2026-09-01")], "$", now=NOW)
    two = ics([sub("Pay, Inc; Plus", "month", "2026-10-01")], "$", now=NOW)
    uid = [line for line in one.split("\r\n") if line.startswith("UID:")]
    assert uid and uid[0] in two
    assert "SUMMARY:Pay\\, Inc\\; Plus due ($9.99)" in one


def test_ics_month_end_and_half_month():
    (end,) = events(ics([sub("Rent", "month", "2026-08-01")], "$", now=NOW))
    assert "DTSTART;VALUE=DATE:20260831" in end
    assert "RRULE:FREQ=MONTHLY;BYMONTHDAY=31,-1;BYSETPOS=1" in end
    (half,) = events(ics([sub("Payroll", "half month", "2026-09-15")], "$", now=NOW))
    assert "RRULE" not in half


def test_fold_long_lines():
    folded = _fold("SUMMARY:" + "é" * 60)
    parts = folded.split("\r\n ")
    assert len(parts) > 1 and all(len(p.encode()) <= 75 for p in parts)
    assert "".join(parts) == "SUMMARY:" + "é" * 60


def test_cli_ics(tmp_path, capsys):
    out = tmp_path / "renewals.ics"
    assert main([str(SAMPLE), "--ics", str(out), "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert captured.out.lstrip().startswith("[")
    assert "Wrote 6 renewals" in captured.err
    text = out.read_bytes().decode()
    assert text.count("BEGIN:VEVENT") == 6 and "\r\n" in text
    assert "Streamflix due" in text and "Gamehub" not in text


def test_cli_ics_unwritable(tmp_path, capsys):
    assert main([str(SAMPLE), "--ics", str(tmp_path / "missing" / "r.ics")]) == 2
    assert "can't write" in capsys.readouterr().err
