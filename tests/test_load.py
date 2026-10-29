from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from subspot.load import LoadError, choose_date_format, detect_columns, parse_amount, read_csv


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("-12.34", Decimal("-12.34")),
        ("$1,234.56", Decimal("1234.56")),
        ("(9.99)", Decimal("-9.99")),
        ("12.00 DR", Decimal("-12.00")),
        ("1.234,56", Decimal("1234.56")),
        ("-4,50", Decimal("-4.50")),
        ("€ 7", Decimal("7")),
        ("", None),
        ("n/a", None),
    ],
)
def test_parse_amount(text, value):
    assert parse_amount(text) == value


def test_detect_columns_variants():
    cols = detect_columns(["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount"])
    assert (cols.date, cols.description, cols.amount) == ("Transaction Date", "Description", "Amount")
    cols = detect_columns(["Date", "Payee", "Withdrawal", "Deposit", "Balance"])
    assert (cols.debit, cols.credit, cols.amount) == ("Withdrawal", "Deposit", None)
    cols = detect_columns(["Booking Date", "Narrative", "Money Out", "Money In"])
    assert (cols.date, cols.description, cols.debit) == ("Booking Date", "Narrative", "Money Out")
    with pytest.raises(LoadError):
        detect_columns(["foo", "bar"])


def test_date_format_choice():
    assert choose_date_format(["2026-01-31"], None) == "%Y-%m-%d"
    assert choose_date_format(["01/31/2026", "02/01/2026"], None) == "%m/%d/%Y"
    assert choose_date_format(["31/01/2026", "01/02/2026"], None) == "%d/%m/%Y"
    assert choose_date_format(["03/04/2026"], True) == "%d/%m/%Y"
    with pytest.raises(LoadError):
        choose_date_format(["yesterday"], None)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_read_signed_amounts(tmp_path):
    path = _write(tmp_path, "a.csv", "Date,Description,Amount\n2026-01-01,SHOP,-10.00\n2026-01-02,PAY,500\n")
    txs = read_csv(path)
    assert [t.amount for t in txs] == [Decimal("10.00"), Decimal("-500")]


def test_read_card_statement_with_positive_charges(tmp_path):
    text = (
        "Date,Description,Amount\n01/01/2026,SHOP,10.00\n"
        "01/02/2026,CAFE,4.00\n01/03/2026,PAYMENT THANK YOU,-50\n"
    )
    txs = read_csv(_write(tmp_path, "card.csv", text))
    assert txs[0].amount == Decimal("10.00") and txs[2].amount == Decimal("-50")


def test_read_debit_credit_semicolon_and_preamble(tmp_path):
    text = (
        "Account;12345678\nExported;2026-02-01\n\n"
        "Booking date;Payee;Money out;Money in\n"
        "15.01.2026;Cloudbox;2,99;\n16.01.2026;Employer;;1.500,00\n"
    )
    txs = read_csv(_write(tmp_path, "eu.csv", text))
    assert txs[0].date == dt.date(2026, 1, 15)
    assert txs[0].amount == Decimal("2.99")
    assert txs[1].amount == Decimal("-1500.00")


def test_utf8_bom_and_quotes(tmp_path):
    text = '﻿Date,Description,Amount\n2026-01-01,"SHOP, INC",-1.00\n'
    (tx,) = read_csv(_write(tmp_path, "bom.csv", text))
    assert tx.description == "SHOP, INC"


def test_missing_file_and_empty(tmp_path):
    with pytest.raises(LoadError):
        read_csv(tmp_path / "nope.csv")
    with pytest.raises(LoadError):
        read_csv(_write(tmp_path, "empty.csv", "Date,Description,Amount\n"))
