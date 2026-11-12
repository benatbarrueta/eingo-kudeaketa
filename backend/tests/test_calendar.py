
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.core.config import Settings
from app.integrations.google import docs_client
from app.integrations.google.document_parser import read
from app.main import create_app
from app.models.calendar import CalendarError
from app.repositories.google_docs_repository import GoogleRepository
from app.services.chronological_service import insertion
from app.utils.basque_dates import format_date, parse


def document(rows, revision="r1"):
    # Docs structural shape: row/cell boundaries, paragraph and text run indices.
    index = 8
    table_rows = []
    for values in rows:
        start = index
        index += 1
        cells = []
        for value in values:
            gray = value is None
            content = (value or "") + "\n"
            end = index + 1 + len(content.encode("utf-16-le")) // 2
            style = {"rowSpan": 1, "columnSpan": 3 if gray else 1}
            if gray:
                style["backgroundColor"] = {"color": {"rgbColor": dict.fromkeys(("red", "green", "blue"), .7)}}
            cells.append({"startIndex": index, "endIndex": end, "tableCellStyle": style,
                          "content": [{"startIndex": index + 1, "endIndex": end, "paragraph": {
                              "elements": [{"startIndex": index + 1, "endIndex": end,
                                            "textRun": {"content": content, "textStyle": {"bold": True}}}],
                              "paragraphStyle": {"alignment": "CENTER"}}}]})
            index = end
        table_rows.append({"startIndex": start, "endIndex": index, "tableCells": cells})
    table = {"startIndex": 7, "endIndex": index, "table": {
        "columns": 3, "rows": len(rows), "tableRows": table_rows}}
    return {"title": "Egutegia", "revisionId": revision, "tabs": [
        {"tabProperties": {"tabId": "other"}, "documentTab": {"body": {"content": []}},
         "childTabs": [{"tabProperties": {"tabId": "calendar"}, "documentTab": {"body": {"content": [
             {"startIndex": 2, "table": {"columns": 1, "tableRows": []}}, table]}}}]}]}


@pytest.fixture
def rows():
    return [["DATA", "HERRIA", "MOTA"], ["URTARRILAK 7", "A", "Kalejira"], [None],
            ["OTSAILAK 13", "B", ""], ["OTSAILAK 14", "C", "Dantza"], ["OTSAILAK 14", "D", ""]]


@pytest.mark.parametrize("month", range(1, 13))
def test_basque_round_trip(month):
    day = date(2027, month, 15)
    assert parse(format_date(day).lower(), 2027) == day


def test_invalid_day():
    with pytest.raises(ValueError):
        parse("OTSAILAK 29", 2027)


def test_tables_tabs_headers_and_merged_separator(rows):
    doc = document(rows)
    with pytest.raises(CalendarError, match="select_document_tab"):
        read(doc, None, 0, 2027)
    with pytest.raises(CalendarError, match="invalid_headers"):
        read(doc, "calendar", 0, 2027)
    cal = read(doc, "calendar", 1, 2027)
    assert cal.columns == rows[0]
    assert cal.rows[2].kind == "separator"
    assert cal.rows[2].spans == [3]
    assert cal.events()[2]["values"] == rows[4]


@pytest.mark.parametrize(("day", "expected"), [(12, (3, False)), (14, (5, True)), (20, (5, True))])
def test_insertion_positions(rows, day, expected):
    cal = read(document(rows), "calendar", 1, 2027)
    assert insertion(cal, date(2027, 2, day)) == expected


def test_between_dates(rows):
    rows[-1][0] = "OTSAILAK 20"
    cal = read(document(rows), "calendar", 1, 2027)
    assert insertion(cal, date(2027, 2, 15)) == (5, False)


@pytest.mark.parametrize("changed", [["", "", ""], ["baliogabea", "B", ""], ["OTSAILAK 12", "B", ""]])
def test_unsafe_structure(rows, changed):
    rows[4] = changed
    cal = read(document(rows), "calendar", 1, 2027)
    with pytest.raises(CalendarError, match="unsafe_structure"):
        insertion(cal, date(2027, 2, 12))


def test_merged_event_blocks_write(rows):
    doc = document(rows)
    table = doc["tabs"][0]["childTabs"][0]["documentTab"]["body"]["content"][1]["table"]
    table["tableRows"][3]["tableCells"][0]["tableCellStyle"]["rowSpan"] = 2
    with pytest.raises(CalendarError, match="unsafe_structure"):
        insertion(read(doc, "calendar", 1, 2027), date(2027, 2, 12))


class FakeDocs:
    def __init__(self, docs, fail=None):
        self.docs = iter(docs)
        self.writes = []
        self.fail = fail

    def get(self):
        return next(self.docs)

    def write(self, requests, revision):
        self.writes.append((requests, revision))
        if self.fail == revision:
            raise CalendarError("revision_conflict")
        return {"writeControl": {"requiredRevisionId": "r2"}}


def test_two_phase_insert_uses_refetched_indices(rows):
    values = ["OTSAILAK 12", "Gernika 🎵", "Kalejira"]
    docs = FakeDocs([document(rows), document(rows[:3] + [["", "", ""]] + rows[3:], "r2"),
                     document(rows[:3] + [values] + rows[3:], "r3")])
    repo = GoogleRepository(Settings("google", 2027, tab="calendar", table=1), docs)
    old = repo.read()
    final = repo.insert(old, 3, False, values)
    (first, rev1), (second, rev2) = docs.writes
    assert (rev1, rev2) == ("r1", "r2")
    anchor = first[0]["insertTableRow"]["tableCellLocation"]
    assert anchor == {"rowIndex": 3, "columnIndex": 0, "tableStartLocation": {"index": 7, "tabId": "calendar"}}
    positions = [r["insertText"]["location"]["index"] for r in second if "insertText" in r]
    fresh = read(document(rows[:3] + [["", "", ""]] + rows[3:], "r2"), "calendar", 1, 2027)
    assert positions == [c["content"][0]["startIndex"] for c in reversed(fresh.rows[3].cells)]
    assert final.rows[2].kind == "separator"
    assert final.rows[3].values == values


def test_concurrent_change_after_row_stops_write(rows):
    docs = FakeDocs([document(rows), document(rows[:3] + [["", "", ""]] + rows[3:], "other-revision")])
    repo = GoogleRepository(Settings("google", 2027, tab="calendar", table=1), docs)
    old = repo.read()
    with pytest.raises(CalendarError, match="manual_review"):
        repo.insert(old, 3, False, ["OTSAILAK 12", "Gernika", ""])
    assert len(docs.writes) == 1 and repo.needs_review


def test_revision_conflict_before_row(rows):
    docs = FakeDocs([document(rows)], fail="r1")
    repo = GoogleRepository(Settings("google", 2027, tab="calendar", table=1), docs)
    with pytest.raises(CalendarError, match="revision_conflict"):
        repo.insert(repo.read(), 3, False, ["OTSAILAK 12", "Gernika", ""])
    assert not repo.needs_review


@pytest.mark.parametrize(("status", "body", "code"), [
    (403, b"forbidden", "google_access_denied"), (503, b"offline", "google_api_error"),
    (400, b"required revision mismatch", "revision_conflict"),
])
def test_google_errors(monkeypatch, status, body, code):
    def rejected(*args, **kwargs):
        raise HttpError(Response({"status": str(status), "reason": "failed"}), body)
    monkeypatch.setattr(docs_client, "credentials", lambda _: None)
    monkeypatch.setattr(docs_client, "AuthorizedHttp", lambda *a, **kw: None)
    monkeypatch.setattr(docs_client, "build", rejected)
    with pytest.raises(CalendarError, match=code):
        docs_client.DocsClient(SimpleNamespace(credentials="")).get()


def test_missing_credentials_is_controlled():
    with pytest.raises(CalendarError, match="google_unavailable"):
        docs_client.DocsClient(SimpleNamespace(credentials="/nonexistent/eingo.json")).get()


def test_demo_workflow():
    client = TestClient(create_app(Settings("mock", 2027)))
    assert client.get("/api/health").json()["ok"]
    initial = client.get("/api/events").json()["events"]
    assert len(initial) == 11
    payload = {"date": "2027-02-12", "town": "GERNIKA", "fields": {"EKITALDIA": "Kalejira"}}
    response = client.post("/api/events", json=payload)
    assert response.status_code == 201
    assert response.json()["table"]["rows"][5]["kind"] == "separator"
    assert client.post("/api/events", json=payload).status_code == 200
    assert len(client.get("/api/events").json()["events"]) == 12
    assert client.post("/api/events", json={**payload, "date": "2027-04-07"}).status_code == 409
    assert client.post("/api/events", json={**payload, "town": "a\nb"}).status_code == 422
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/events").json()["events"] == initial


def test_real_mode_allows_writes_without_admin_token():
    from app.repositories.mock_repository import MockRepository

    client = TestClient(create_app(Settings("google", 2027), MockRepository(2027)))
    result = client.post("/api/events", json={"date": "2027-02-12", "town": "GERNIKA"})
    assert result.status_code == 201
    assert result.json()["event"]["values"][1] == "GERNIKA"
    assert client.post("/api/demo/reset").status_code == 404


def test_named_merged_month_with_placeholder_cells(rows):
    doc = document(rows)
    table = doc["tabs"][0]["childTabs"][0]["documentTab"]["body"]["content"][1]["table"]
    separator = table["tableRows"][2]["tableCells"]
    first = separator[0]
    first["content"][0]["paragraph"]["elements"][0]["textRun"]["content"] = "OTSAILA\n"
    for _ in range(2):
        separator.append({
            "tableCellStyle": {**first["tableCellStyle"], "columnSpan": 1},
            "content": [{"paragraph": {"elements": [{"textRun": {"content": "\n"}}]}}],
        })
    calendar = read(doc, "calendar", 1, 2027)
    assert calendar.rows[2].kind == "separator"
    assert calendar.rows[2].values == ["OTSAILA"]
    assert calendar.rows[2].spans == [3]
    assert insertion(calendar, date(2027, 2, 12)) == (3, False)


def test_edit_delete_workflow_rejects_stale_rows():
    client = TestClient(create_app(Settings("mock", 2027)))
    original = client.get("/api/events").json()["events"][0]
    endpoint = f"/api/events/{original['id']}"
    edit = {"expected": original["values"], "date": original["date"], "town": "BILBO"}
    moved = client.post(endpoint + "/edit", json={**edit, "date": "2027-02-01"})
    assert moved.json()["error"]["code"] == "date_changes_position"

    response = client.post(endpoint + "/edit", json=edit)
    assert response.status_code == 200
    updated = response.json()["event"]
    assert updated["values"] == [original["values"][0], "BILBO", original["values"][2]]

    stale = client.post(endpoint + "/delete", json={"expected": original["values"]})
    assert stale.status_code == 409
    deleted = client.post(endpoint + "/delete", json={"expected": updated["values"]})
    assert deleted.status_code == 200
    assert sum(row["kind"] == "separator" for row in deleted.json()["rows"]) == 2
    assert all("BILBO" not in row["values"] for row in deleted.json()["rows"])


def test_first_event_in_empty_named_month(rows):
    doc = document(rows[:3])
    table = doc["tabs"][0]["childTabs"][0]["documentTab"]["body"]["content"][1]["table"]
    separator = table["tableRows"][2]["tableCells"][0]
    separator["content"][0]["paragraph"]["elements"][0]["textRun"]["content"] = "OTSAILA\n"
    calendar = read(doc, "calendar", 1, 2027)
    assert insertion(calendar, date(2027, 2, 17)) == (2, True)
    with pytest.raises(CalendarError, match="month_without_block"):
        insertion(calendar, date(2027, 3, 17))
