# tests/test_ingest_credit_card.py
from datetime import date
from pathlib import Path
from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_basic_csv(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Merchant,Category
2026-03-05,87.50,REST LE PETIT,Dining
2026-03-05,55.00,TAXI PARIS,Transport
2026-03-06,12.00,CAFE DES ARTS,Dining
""")
    expenses = ingest_credit_card(csv_path)
    assert len(expenses) == 3
    assert expenses[0].merchant == "REST LE PETIT"
    assert expenses[0].amount == 87.50
    assert expenses[0].date == date(2026, 3, 5)
    assert expenses[0].source == "credit_card"


def test_csv_with_currency(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Currency,Merchant
2026-03-05,87.50,EUR,REST LE PETIT
""")
    expenses = ingest_credit_card(csv_path)
    assert expenses[0].currency == "EUR"


def test_csv_with_different_date_formats(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Merchant
03/05/2026,10.00,SHOP A
""")
    expenses = ingest_credit_card(csv_path)
    assert len(expenses) == 1
    assert expenses[0].date == date(2026, 3, 5)


def test_empty_csv(tmp_path):
    csv_path = tmp_path / "empty.csv"
    _write_csv(csv_path, """Date,Amount,Merchant
""")
    expenses = ingest_credit_card(csv_path)
    assert expenses == []
