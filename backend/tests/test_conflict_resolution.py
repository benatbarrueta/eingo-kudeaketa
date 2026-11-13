from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.calendar import CalendarError
from app.schemas.sync import ConflictResolution
from app.services.conflict_resolution import preview, resolve
from test_database import make_database_engine
from test_bidirectional_sync import make_engine, record
from app.repositories.database_repository import DatabaseRepository


def conflict(tmp_path):
    engine, database, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    sheets.client.rows[1][3] = "18:00"
    docs.calendar.rows[1].values[3] = "19:00"
    engine.tick()
    assert engine.error == "sync_conflict"
    return engine, database, sheets, docs


@pytest.mark.parametrize("choice,expected", [("sheets", "18:00"), ("docs", "19:00")])
def test_choose_either_source_and_preserve_independent_fields(tmp_path, choice, expected):
    engine, database, sheets, docs = conflict(tmp_path)
    sheets.client.rows[1][7] = "private-new"
    docs.calendar.rows[1].values[4] = "1250"
    before = len(sheets.client.requests)
    selection = preview(engine).public
    assert len(sheets.client.requests) == before
    assert selection["canResolve"]
    field = selection["fields"][0]
    assert field["column"] == "ORDUA"
    assert field["options"] == [{"source": "sheets", "value": "18:00"}, {"source": "docs", "value": "19:00"}]
    assert "identity" not in str(selection) and "Revision" not in str(selection)
    resolve(engine, ConflictResolution(token=selection["token"], choices={field["key"]: choice}))
    final = database.read().events()[0]["values"]
    assert final[3] == expected
    assert final[4] == "1250"
    assert final[7:] == ["private-new", "other"]
    assert sheets.read().events()[0]["values"] == final
    assert docs.read().events()[0]["values"] == final[:7]
    assert database.conflicts()[0].resolved_at is not None
    assert database.synchronization()[2] is None
    assert engine.error is None


def test_stale_choice_writes_nothing_and_needs_a_new_preview(tmp_path):
    engine, database, sheets, docs = conflict(tmp_path)
    selection = preview(engine).public
    docs.calendar.rows[1].values[3] = "20:00"
    sheets_before, docs_before = deepcopy(sheets.client.rows), docs.read().events()
    request = ConflictResolution(token=selection["token"], choices={selection["fields"][0]["key"]: "docs"})
    with pytest.raises(CalendarError, match="conflict_changed"):
        resolve(engine, request)
    assert sheets.client.rows == sheets_before
    assert docs.read().events() == docs_before
    assert database.synchronization()[2] is None


def test_local_revision_change_invalidates_choice_even_if_values_return(tmp_path):
    engine, database, sheets, docs = conflict(tmp_path)
    selection = preview(engine).public
    with database.database.transaction(write=True) as connection:
        connection.execute("UPDATE sync_configurations SET revision=revision+1")
    with pytest.raises(CalendarError, match="conflict_changed"):
        resolve(engine, ConflictResolution(token=selection["token"], choices={selection["fields"][0]["key"]: "sheets"}))


def test_multiple_fields_require_all_explicit_choices(tmp_path):
    engine, database, sheets, docs = conflict(tmp_path)
    sheets.client.rows[1][4] = "100"
    docs.calendar.rows[1].values[4] = "200"
    selection = preview(engine).public
    assert len(selection["fields"]) == 2
    with pytest.raises(CalendarError, match="validation_error"):
        resolve(engine, ConflictResolution(token=selection["token"], choices={selection["fields"][0]["key"]: "sheets"}))
    assert database.synchronization()[2] is None
    choices = {field["key"]: "sheets" if field["column"] == "ORDUA" else "docs" for field in selection["fields"]}
    resolve(engine, ConflictResolution(token=selection["token"], choices=choices))
    assert database.read().events()[0]["values"][3:5] == ["18:00", "200"]


def test_private_conflict_offers_only_sheets_and_database(tmp_path):
    engine, database, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    database.update(database.read(), 1, record(extra="local"))
    sheets.client.rows[1][7] = "remote"
    selection = preview(engine).public
    assert selection["fields"][0]["column"] == "WAWA"
    assert {option["source"] for option in selection["fields"][0]["options"]} == {"sheets", "database"}
    key = selection["fields"][0]["key"]
    with pytest.raises(CalendarError, match="validation_error"):
        resolve(engine, ConflictResolution(token=selection["token"], choices={key: "docs"}))
    resolve(engine, ConflictResolution(token=selection["token"], choices={key: "database"}))
    assert sheets.read().events()[0]["values"][7] == "local"
    assert len(docs.read().events()[0]["values"]) == 7


def test_three_distinct_changes_include_local_agenda_option(tmp_path):
    engine, database, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    local = record()
    local[3] = "17:00"
    database.update(database.read(), 1, local)
    sheets.client.rows[1][3] = "18:00"
    docs.calendar.rows[1].values[3] = "19:00"
    selection = preview(engine).public
    assert len(selection["fields"][0]["options"]) == 3


@pytest.mark.parametrize("kind", ["delete", "identity", "pending"])
def test_structural_or_pending_conflicts_offer_no_unsafe_resolution(tmp_path, kind):
    engine, database, sheets, docs = conflict(tmp_path)
    if kind == "delete":
        docs.delete(docs.read(), 1)
    elif kind == "identity":
        docs.calendar.rows[1].values[1] = "Other town"
    else:
        database.checkpoint({"target": [record()], "database": [record()],
                             "sheets": [record()], "docs": [record()[:7]]})
    selection = preview(engine).public
    assert not selection["canResolve"] and selection["fields"] == []
    assert selection["reason"] == ("pending_operation" if kind == "pending" else "ambiguous_structure")


def test_resolution_survives_interrupted_remote_write(tmp_path):
    engine, database, sheets, docs = conflict(tmp_path)
    selection = preview(engine).public
    original = docs.update
    docs.update = lambda *args: (_ for _ in ()).throw(RuntimeError("offline"))
    with pytest.raises(CalendarError, match="sync_unavailable"):
        resolve(engine, ConflictResolution(token=selection["token"], choices={selection["fields"][0]["key"]: "sheets"}))
    operation = database.synchronization()[2]
    assert operation and operation.payload["resolution"]
    docs.update = original
    engine.run()
    assert database.read().events()[0]["values"][3] == "18:00"
    assert database.synchronization()[2] is None


def test_api_preview_and_resolution_validate_payload_and_mode(tmp_path):
    remote, sheets, docs = make_engine(tmp_path)
    settings = Settings("database", 2027, google_sync=True, auto_sync=False,
                        database_path=str(tmp_path / "agenda.sqlite3"), sync_state_path=str(tmp_path / "state.json"))
    database = DatabaseRepository(settings.database_path, 2027, ["", 0, "", None, 0, 2027])
    database.remote = remote.repository
    client = TestClient(create_app(settings, database))
    assert client.post("/api/document/sync").status_code == 200
    sheets.client.rows[1][3] = "18:00"
    docs.calendar.rows[1].values[3] = "19:00"
    assert client.post("/api/document/sync").status_code == 409
    selection = client.get("/api/sync/conflict").json()
    assert selection["canResolve"]
    field = selection["fields"][0]
    assert client.post("/api/sync/conflict/resolve", json={"token": selection["token"], "choices": {field["key"]: "invalid"}}).status_code == 422
    result = client.post("/api/sync/conflict/resolve", json={"token": selection["token"], "choices": {field["key"]: "docs"}})
    assert result.status_code == 200 and result.json()["rows"][1]["values"][3] == "19:00"
    mock = TestClient(create_app(Settings("mock", 2027)))
    assert mock.get("/api/sync/conflict").status_code == 404


def test_existing_sheets_sync_response_keeps_document_seven_columns(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    settings = Settings("sheets", 2027, auto_sync=True, sync_state_path=str(tmp_path / "state.json"))
    client = TestClient(create_app(settings, engine.repository))
    response = client.post("/api/document/sync")
    assert response.status_code == 200
    assert len(response.json()["columns"]) == 7
