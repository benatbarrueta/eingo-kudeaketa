from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.calendar import CalendarError
from app.repositories.google_sheets_repository import SheetsRepository
from app.repositories.synced_repository import SyncedRepository
from app.repositories.mock_repository import MockRepository

COLUMNS = ["DATA", "HERRIA", "NOR", "ORDUA", "FAKTURAZIOA", "KONFIRM", "AZALPENA", "WAWA", "WEWE"]


class FakeSheets:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.requests = []

    def execute(self, requests=None):
        if requests is not None:
            self.requests.append(requests)
            for request in requests:
                if "insertDimension" in request:
                    self.rows.insert(request["insertDimension"]["range"]["startIndex"], [])
                elif "deleteDimension" in request:
                    self.rows.pop(request["deleteDimension"]["range"]["startIndex"])
                else:
                    update = request["updateCells"]
                    self.rows[update["start"]["rowIndex"]] = [
                        cell["userEnteredValue"]["stringValue"] for cell in update["rows"][0]["values"]
                    ]
            return {}
        return {
            "properties": {"title": "Agenda"},
            "sheets": [{
                "properties": {"sheetId": 0},
                "data": [{"rowData": [{"values": [{"formattedValue": value} for value in row]} for row in self.rows]}],
            }],
        }


def test_sheets_crud_keeps_nine_columns_and_checks_changes():
    settings = Settings("sheets", 2027)
    client = FakeSheets([COLUMNS])
    repo = SheetsRepository(settings, client)
    calendar = repo.read()
    anchor, below = repo.insertion(calendar, date(2027, 2, 17))
    values = ["OTSAILAK 17", "ASFA", "", "", "", "", "", "private-a", "private-b"]
    created = repo.insert(calendar, anchor, below, values)
    assert created.events()[0]["values"] == values
    assert client.requests[0][1]["updateCells"]["fields"] == "userEnteredValue"
    with pytest.raises(CalendarError, match="revision_conflict"):
        repo.update(calendar, 1, values)
    values = [*values[:7], "changed", "private-b"]
    edited = repo.update(created, 1, values)
    assert edited.rows[1].values[-2] == "changed"
    assert len(repo.delete(edited, 1).rows) == 1


def test_sheets_web_projection_and_import():
    settings = Settings("sheets", 2027)
    source = SheetsRepository(settings, FakeSheets([COLUMNS]))
    document = MockRepository(2027)
    # Use the actual seven-column document contract.
    document.calendar.columns = COLUMNS[:7]
    for row in document.calendar.rows:
        if row.kind == "header":
            row.values = COLUMNS[:7]
        elif row.kind == "event":
            row.values = [*row.values[:2], "", "", "", "", row.values[2]]
    document.needs_review = False
    repo = SyncedRepository(source, document)
    calendar = repo.import_document()
    assert len(calendar.events()) == 11
    assert all(len(event["values"]) == 9 for event in calendar.events())
    first = calendar.events()[0]
    values = [*first["values"][:7], "secret", "hidden"]
    final = repo.update(calendar, first["id"], values)
    assert final.events()[0]["values"][-2:] == ["secret", "hidden"]
    assert all(len(event["values"]) == 7 for event in document.read().events())
    api = TestClient(create_app(settings, repo))
    assert len(api.get("/api/calendar").json()["columns"]) == 9
    assert len(api.get("/api/document/structure").json()["columns"]) == 7
    assert "secret" not in api.get("/api/document/structure").text


def test_empty_sheet_does_not_erase_document():
    source = SheetsRepository(Settings("sheets", 2027), FakeSheets([COLUMNS]))
    document = MockRepository(2027)
    document.needs_review = False
    document.calendar.columns = COLUMNS[:7]
    repo = SyncedRepository(source, document)
    with pytest.raises(CalendarError, match="sources_differ"):
        repo._preflight(source.read())
    assert len(document.read().events()) == 11
    assert source.client.requests == []
