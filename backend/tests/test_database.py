from copy import deepcopy
from datetime import date
import sqlite3
import stat

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from app.models.calendar import CalendarError
from app.repositories.database_repository import DatabaseRepository
from app.services.database_sync import DatabaseSync
from test_bidirectional_sync import make_engine, record


def make_database_engine(tmp_path):
    remote_engine, sheets, docs = make_engine(tmp_path)
    database = DatabaseRepository(tmp_path / "agenda.sqlite3", 2027, ["test"])
    engine = DatabaseSync(remote_engine.repository, database, tmp_path / "state.json", 2027, ["test"])
    return engine, database, sheets, docs


def test_migrations_are_idempotent_private_and_enforce_relations(tmp_path):
    path = tmp_path / "private" / "agenda.sqlite3"
    Database(path)
    db = Database(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with db.transaction() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"events", "sync_configurations", "sync_states", "sync_operations", "sync_conflicts", "event_changes"}
    with pytest.raises(sqlite3.IntegrityError), db.transaction(write=True) as connection:
        connection.execute("INSERT INTO sync_states VALUES ('missing', 'missing', 0, '[]', 1, 1, 'now')")


def test_transactions_rollback_and_backup_is_consistent(tmp_path):
    repo = DatabaseRepository(tmp_path / "agenda.sqlite3", 2027)
    with pytest.raises(RuntimeError), repo.database.transaction(write=True) as connection:
        connection.execute("UPDATE sync_configurations SET revision=99")
        raise RuntimeError("interrupted")
    assert repo.read().revision == "0"
    repo.insert(repo.read(), 0, True, record())
    destination = tmp_path / "backup.sqlite3"
    repo.database.backup(destination)
    backup = DatabaseRepository(destination, 2027)
    assert backup.read().events() == repo.read().events()
    assert backup.history() == repo.history()
    with pytest.raises(ValueError):
        repo.database.backup(destination)


def test_persistent_api_uses_stable_identifiers_and_versions(tmp_path):
    settings = Settings("database", 2027, database_path=str(tmp_path / "agenda.sqlite3"))
    client = TestClient(create_app(settings))
    assert client.get("/api/events").json()["events"] == []
    config = client.get("/api/config").json()
    assert config["source"] == "database" and config["documentUrl"] is None
    payload = {"date": "2027-02-17", "town": "BILBO", "fields": {"WAWA": "private", "WEWE": "other", "FAKTURAZIOA": "1250.50"}}
    response = client.post("/api/events", json=payload)
    assert response.status_code == 201
    event = response.json()["event"]
    assert event["eventId"] and event["version"] == 1
    assert client.post("/api/events", json=payload).status_code == 200
    # Adding an earlier event changes row positions, but UUID endpoints still target BILBO.
    assert client.post("/api/events", json={"date": "2027-01-10", "town": "GERNIKA"}).status_code == 201
    endpoint = f"/api/events/{event['eventId']}"
    update = {"date": event["date"], "town": "DONOSTIA", "expected": event["values"], "expectedVersion": 1}
    changed = client.post(endpoint + "/edit", json=update)
    assert changed.status_code == 200
    updated = changed.json()["event"]
    assert updated["eventId"] == event["eventId"] and updated["version"] == 2
    assert updated["values"][7:] == ["private", "other"]
    assert updated["values"][4] == "1250.50"
    assert client.post(endpoint + "/edit", json=update).status_code == 409
    restart = TestClient(create_app(settings))
    events = restart.get("/api/events").json()["events"]
    assert events[-1] == updated
    assert len(restart.get("/api/calendar").json()["columns"]) == 9
    assert len(restart.get("/api/document/structure").json()["columns"]) == 7
    assert restart.post("/api/demo/reset").status_code == 404
    assert restart.post(endpoint + "/delete", json={"expected": updated["values"], "expectedVersion": 1}).status_code == 409
    assert restart.post(endpoint + "/delete", json={"expected": updated["values"], "expectedVersion": 2}).status_code == 200
    repo = DatabaseRepository(settings.database_path, 2027)
    assert [change.action for change in repo.history()] == ["created", "created", "updated", "deleted"]
    assert all(change.origin == "web" for change in repo.history())
    assert any(event.deleted_at for event in repo.records())


def test_cross_connection_revision_conflicts_do_not_leave_history(tmp_path):
    path = tmp_path / "agenda.sqlite3"
    one, two = DatabaseRepository(path, 2027), DatabaseRepository(path, 2027)
    stale = two.read()
    one.insert(one.read(), 0, True, record())
    with pytest.raises(CalendarError, match="revision_conflict"):
        two.insert(stale, 0, True, record("Other"))
    assert len(one.history()) == 1


def test_import_and_three_way_reconciliation_preserve_uuid_and_private_fields(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    first = db.records()[0]
    assert db.read().events()[0]["values"] == record()
    assert db.history()[0].origin == "import"
    config, states, operation = db.synchronization()
    assert config.initialized and operation is None
    assert states[0].sheet_row == 1 and states[0].document_row == 1
    # Three independent edits, including a Sheets-only column.
    local = record()
    local[3] = "17:00"
    db.update(db.read(), 1, local)
    docs.calendar.rows[1].values[1] = "Docs town"
    sheets.client.rows[1][7] = "Sheets private"
    engine.run()
    merged = record("Docs town", "Sheets private")
    merged[3] = "17:00"
    assert db.read().events()[0]["values"] == merged
    assert sheets.read().events()[0]["values"] == merged
    assert docs.read().events()[0]["values"] == merged[:7]
    assert db.records()[0].id == first.id
    assert db.records()[0].version == 3


def test_conflict_is_durable_and_writes_no_remote_data(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    db.update(db.read(), 1, record("Local"))
    sheets.client.rows[1][1] = "Remote"
    before_sheets = deepcopy(sheets.client.rows)
    before_docs = docs.read().events()
    engine.tick()
    assert engine.error == "sync_conflict"
    assert sheets.client.rows == before_sheets
    assert docs.read().events() == before_docs
    conflicts = db.conflicts()
    assert len(conflicts) == 1 and conflicts[0].resolved_at is None
    assert conflicts[0].snapshots["database"] == [record("Local")]
    # Explicit agreement of all three sides resolves the incident.
    sheets.client.rows[1][1] = "Local"
    docs.calendar.rows[1].values[1] = "Local"
    engine.run()
    assert db.conflicts()[0].resolved_at is not None


def test_private_column_conflict_is_detected(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    db.update(db.read(), 1, record(extra="Local"))
    sheets.client.rows[1][7] = "Remote"
    engine.tick()
    assert engine.error == "sync_conflict"


def test_restart_recovers_write_with_lost_acknowledgement(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    db.update(db.read(), 1, record("Local"))
    update = sheets.update

    def lost_ack(*args):
        update(*args)
        raise RuntimeError("connection lost after remote commit")

    sheets.update = lost_ack
    engine.tick()
    assert engine.error == "sync_unavailable"
    _, _, operation = db.synchronization()
    assert operation and "next" in operation.payload
    assert operation.error == "sync_unavailable" and operation.attempts == 1
    assert docs.read().events()[0]["values"][1] == "A"
    sheets.update = update
    restarted = DatabaseSync(engine.repository, DatabaseRepository(db.database.path, 2027, ["test"]),
                             engine.path, 2027, ["test"])
    restarted.run()
    assert restarted.error is None
    assert docs.read().events()[0]["values"][1] == "Local"
    assert db.synchronization()[2] is None
    assert len(db.history()) == 2


def test_new_external_edit_during_pending_operation_stops_recovery(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    db.update(db.read(), 1, record("Local"))
    original_update = docs.update
    docs.update = lambda *args: (_ for _ in ()).throw(RuntimeError("offline"))
    engine.tick()
    assert db.synchronization()[2] is not None
    sheets.client.rows[1][1] = "New edit"
    docs.update = original_update
    engine.tick()
    assert engine.error == "sync_conflict"
    assert sheets.client.rows[1][1] == "New edit"
    assert docs.read().events()[0]["values"][1] == "A"


def test_initial_mismatch_and_rebinding_are_rejected(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    docs.calendar.rows[1].values[1] = "Different"
    engine.tick()
    assert engine.error == "sync_initial_mismatch"
    assert db.records() == [] and sheets.client.requests == []
    with pytest.raises(CalendarError, match="sync_state_mismatch"):
        DatabaseRepository(db.database.path, 2027, ["different files"])


def test_unavailable_month_is_rejected_before_any_remote_write(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    calendar = db.read()
    february = record("February")
    february[0] = "OTSAILAK 17"
    db.insert(calendar, 1, True, february)
    requests = len(sheets.client.requests)
    engine.tick()
    assert engine.error == "month_without_block"
    assert len(sheets.client.requests) == requests


def test_database_settings_require_no_google_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_SOURCE", "database")
    monkeypatch.setenv("CALENDAR_YEAR", "2027")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "agenda.sqlite3"))
    monkeypatch.setenv("GOOGLE_SYNC", "false")
    monkeypatch.setenv("GOOGLE_DOCUMENT_ID", "")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", "")
    assert Settings.load().source == "database"
    monkeypatch.setenv("GOOGLE_SYNC", "true")
    with pytest.raises(ValueError):
        Settings.load()


def test_database_api_sync_and_failed_remote_write_are_recoverable(tmp_path):
    settings = Settings("database", 2027, google_sync=True, auto_sync=False,
                        database_path=str(tmp_path / "agenda.sqlite3"),
                        sync_state_path=str(tmp_path / "state.json"))
    remote_engine, sheets, docs = make_engine(tmp_path)
    identity = ["", 0, "", None, 0, 2027]
    db = DatabaseRepository(settings.database_path, 2027, identity)
    db.remote = remote_engine.repository
    client = TestClient(create_app(settings, db))
    assert client.post("/api/document/sync").status_code == 200
    event = client.get("/api/events").json()["events"][0]
    endpoint = f"/api/events/{event['eventId']}/edit"
    payload = {"date": event["date"], "town": "Local", "expected": event["values"], "expectedVersion": 1}
    original = docs.update
    docs.update = lambda *args: (_ for _ in ()).throw(RuntimeError("offline"))
    response = client.post(endpoint, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "database_sync_pending"
    assert db.read().events()[0]["values"][1] == "Local"
    assert db.synchronization()[2] is not None
    assert client.get("/api/sync/status").json()["error"] == "sync_unavailable"
    assert client.get("/api/document/status").json()["writable"] is False
    docs.update = original
    assert client.post("/api/document/sync").status_code == 200
    assert db.synchronization()[2] is None
    assert docs.read().events()[0]["values"][1] == "Local"
    assert client.get("/api/document/status").json()["writable"] is True
    assert len(client.get("/api/document/structure").json()["columns"]) == 7
    # Invalid month is detected before saving the local transaction.
    before = db.read().events()
    response = client.post("/api/events", json={"date": "2027-02-10", "town": "February"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "month_without_block"
    assert db.read().events() == before


def test_remote_insert_delete_keeps_neighbor_uuid_and_history(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    engine.run()
    first_id = db.records()[0].id
    new = record("B")
    new[0] = "URTARRILAK 9"
    sheets.insert(sheets.read(), 1, True, new)
    engine.run()
    events = db.read().events()
    assert events[0]["eventId"] == first_id
    second_id = events[1]["eventId"]
    docs.delete(docs.read(), 1)
    engine.run()
    assert db.read().events()[0]["eventId"] == second_id
    assert [change.action for change in db.history()] == ["created", "created", "deleted"]
    assert len(db.records()) == 2


def test_legacy_pending_plan_is_never_discarded(tmp_path):
    engine, db, sheets, docs = make_database_engine(tmp_path)
    state = '{"identity": ["test"], "base": [], "target": []}'
    engine.path.write_text(state)
    engine.tick()
    assert engine.error == "manual_review"
    assert engine.path.read_text() == state
    assert db.records() == []
    assert sheets.client.requests == []


def test_legacy_baseline_is_used_without_modifying_original(tmp_path):
    import json
    engine, db, sheets, docs = make_database_engine(tmp_path)
    content = json.dumps({"identity": ["test"], "base": [record()]})
    engine.path.write_text(content)
    docs.calendar.rows[1].values[1] = "New from Docs"
    engine.run()
    assert db.read().events()[0]["values"] == record("New from Docs")
    assert engine.path.read_text() == content


def test_future_schema_is_rejected_and_failed_migration_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "agenda.sqlite3"
    db = Database(path)
    with db.transaction(write=True) as connection:
        connection.execute("PRAGMA user_version = 2")
    with pytest.raises(RuntimeError, match="newer"):
        Database(path)
    # Failure after one DDL statement leaves neither the table nor its version behind.
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    migration = migrations / "001_initial.sql"
    migration.write_text("CREATE TABLE example(id INTEGER);\nINVALID SQL;\n")
    from pathlib import Path
    original = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pattern: [migration] if self.name == "migrations" else original(self, pattern))
    failed = tmp_path / "failed.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        Database(failed)
    with sqlite3.connect(failed) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_existing_demo_edits_and_deletes_after_month_separators():
    client = TestClient(create_app(Settings("mock", 2027)))
    event = client.get("/api/events").json()["events"][-1]
    response = client.post(f"/api/events/{event['id']}/edit", json={
        "date": event["date"], "town": "Changed", "expected": event["values"]})
    assert response.status_code == 200
    updated = response.json()["event"]
    response = client.post(f"/api/events/{updated['id']}/delete", json={"expected": updated["values"]})
    assert response.status_code == 200


def test_relative_database_path_uses_same_events_from_any_working_directory(tmp_path, monkeypatch):
    from app.core import database

    backend = tmp_path / "backend"
    backend.mkdir()
    monkeypatch.setattr(database, "BACKEND_ROOT", backend)
    monkeypatch.chdir(backend)
    first = DatabaseRepository(".local-data/eingo.sqlite3", 2027)
    first.insert(first.read(), 0, True, record())
    event_id = first.read().events()[0]["eventId"]
    monkeypatch.chdir(tmp_path)
    second = DatabaseRepository(".local-data/eingo.sqlite3", 2027)
    assert second.database.path == first.database.path == backend / ".local-data/eingo.sqlite3"
    assert second.read().events()[0]["eventId"] == event_id
    assert not (tmp_path / ".local-data/eingo.sqlite3").exists()
