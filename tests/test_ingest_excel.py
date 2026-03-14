# tests/test_ingest_excel.py
from datetime import date, datetime
from pathlib import Path
from openpyxl import Workbook
from post_trip_summary.pipeline.ingest.excel import ingest_excel


def _create_test_workbook(path: Path) -> None:
    wb = Workbook()
    ws_acc = wb.active
    ws_acc.title = "Accommodations"
    ws_acc.append(["Name", "Address", "City", "Country", "Check-In", "Check-Out"])
    ws_acc.append(["Hotel Le Marais", "123 Rue de Rivoli", "Paris", "France", "2026-03-05", "2026-03-08"])
    ws_transit = wb.create_sheet("Transit")
    ws_transit.append(["Mode", "From", "To", "Departure", "Arrival", "Details"])
    ws_transit.append(["flight", "JFK", "CDG", "2026-03-05 08:00", "2026-03-05 14:00", "AF001"])
    ws_act = wb.create_sheet("Activities")
    ws_act.append(["Name", "Location", "City", "Country", "Date", "Time", "Notes"])
    ws_act.append(["Seine River Cruise", "Port de la Bourdonnais", "Paris", "France", "2026-03-06", "19:00", "Reservation #12345"])
    ws_exp = wb.create_sheet("Expenses")
    ws_exp.append(["Date", "Amount", "Currency", "Merchant", "Category"])
    ws_exp.append(["2026-03-05", 87.50, "EUR", "REST LE PETIT", "dining"])
    wb.save(path)


def test_ingest_accommodations(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["accommodations"]) == 1
    acc = result["accommodations"][0]
    assert acc.name == "Hotel Le Marais"
    assert acc.check_in == date(2026, 3, 5)


def test_ingest_transit(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["transits"]) == 1
    t = result["transits"][0]
    assert t.mode == "flight"
    assert t.departure.name == "JFK"


def test_ingest_activities(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["activities"]) == 1
    act = result["activities"][0]
    assert act["name"] == "Seine River Cruise"


def test_ingest_expenses(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["expenses"]) == 1
    exp = result["expenses"][0]
    assert exp.amount == 87.50
    assert exp.currency == "EUR"


def test_ingest_missing_tab(tmp_path):
    wb_path = tmp_path / "minimal.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Accommodations"
    ws.append(["Name", "Address", "City", "Country", "Check-In", "Check-Out"])
    wb.save(wb_path)
    result = ingest_excel(wb_path)
    assert result["transits"] == []
    assert result["expenses"] == []
