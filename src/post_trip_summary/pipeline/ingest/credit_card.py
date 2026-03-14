# src/post_trip_summary/pipeline/ingest/credit_card.py
"""Parse credit card transaction CSV exports."""
import csv
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import Expense

_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d"]


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_headers(headers: list[str]) -> dict[str, int]:
    mapping = {}
    for i, h in enumerate(headers):
        key = h.strip().lower().replace(" ", "_").replace("-", "_")
        mapping[key] = i
    return mapping


def ingest_credit_card(path: Path) -> list[Expense]:
    expenses = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            return []
        col = _normalize_headers(headers)
        date_idx = col.get("date")
        amount_idx = col.get("amount")
        merchant_idx = col.get("merchant")
        currency_idx = col.get("currency")
        category_idx = col.get("category")
        if date_idx is None or amount_idx is None:
            return []
        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue
            exp_date = _parse_date(row[date_idx])
            if not exp_date:
                continue
            try:
                amount = float(row[amount_idx].strip().replace(",", ""))
            except (ValueError, IndexError):
                continue
            expenses.append(Expense(
                date=exp_date, amount=amount,
                currency=row[currency_idx].strip() if currency_idx is not None and currency_idx < len(row) else "USD",
                merchant=row[merchant_idx].strip() if merchant_idx is not None and merchant_idx < len(row) else "",
                category=row[category_idx].strip() if category_idx is not None and category_idx < len(row) else None,
                source="credit_card",
            ))
    return expenses
