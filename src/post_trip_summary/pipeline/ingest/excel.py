# src/post_trip_summary/pipeline/ingest/excel.py
"""Parse trip itinerary from Excel workbook."""
from datetime import date, datetime
from pathlib import Path

import openpyxl

from post_trip_summary.models import (
    Accommodation, Transit, TransitPoint, Location, Expense,
)


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            pass
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return None


def _rows_as_dicts(ws) -> list[dict]:
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    headers = [str(h).strip().lower().replace(" ", "_").replace("-", "_") for h in rows[0]]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append(dict(zip(headers, row)))
    return result


def _parse_accommodations(ws) -> list[Accommodation]:
    accommodations = []
    for row in _rows_as_dicts(ws):
        check_in = _parse_date(row.get("check_in"))
        check_out = _parse_date(row.get("check_out"))
        if not check_in or not check_out:
            continue
        loc = Location(lat=0.0, lon=0.0, name=str(row.get("name", "")), address=row.get("address"), city=str(row.get("city", "")), country=str(row.get("country", "")))
        accommodations.append(Accommodation(name=str(row.get("name", "")), location=loc, check_in=check_in, check_out=check_out, sources=["itinerary"]))
    return accommodations


def _parse_transits(ws) -> list[Transit]:
    transits = []
    for row in _rows_as_dicts(ws):
        dep_time = _parse_datetime(row.get("departure"))
        arr_time = _parse_datetime(row.get("arrival"))
        if not dep_time or not arr_time:
            continue
        dep_loc = Location(lat=0.0, lon=0.0, name=str(row.get("from", "")), address=None, city="", country="")
        arr_loc = Location(lat=0.0, lon=0.0, name=str(row.get("to", "")), address=None, city="", country="")
        transits.append(Transit(mode=str(row.get("mode", "unknown")).lower(), departure=TransitPoint(location=dep_loc, time=dep_time, name=str(row.get("from", ""))), arrival=TransitPoint(location=arr_loc, time=arr_time, name=str(row.get("to", ""))), details={"info": row.get("details", "")}, sources=["itinerary"]))
    return transits


def _parse_activities(ws) -> list[dict]:
    activities = []
    for row in _rows_as_dicts(ws):
        act_date = _parse_date(row.get("date"))
        if not act_date:
            continue
        activities.append({
            "name": str(row.get("name", "")),
            "location": str(row.get("location", "")),
            "city": str(row.get("city", "")),
            "country": str(row.get("country", "")),
            "date": act_date.isoformat(),
            "time": str(row.get("time", "")),
            "notes": str(row.get("notes", "")),
        })
    return activities


def _parse_expenses(ws) -> list[Expense]:
    expenses = []
    for row in _rows_as_dicts(ws):
        exp_date = _parse_date(row.get("date"))
        if not exp_date:
            continue
        expenses.append(Expense(date=exp_date, amount=float(row.get("amount", 0)), currency=str(row.get("currency", "USD")), merchant=str(row.get("merchant", "")), category=row.get("category"), source="spreadsheet"))
    return expenses


def ingest_excel(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet_names_lower = {s.lower(): s for s in wb.sheetnames}
    result = {"accommodations": [], "transits": [], "activities": [], "expenses": []}
    if "accommodations" in sheet_names_lower:
        result["accommodations"] = _parse_accommodations(wb[sheet_names_lower["accommodations"]])
    if "transit" in sheet_names_lower:
        result["transits"] = _parse_transits(wb[sheet_names_lower["transit"]])
    if "activities" in sheet_names_lower:
        result["activities"] = _parse_activities(wb[sheet_names_lower["activities"]])
    if "expenses" in sheet_names_lower:
        result["expenses"] = _parse_expenses(wb[sheet_names_lower["expenses"]])
    wb.close()
    return result
