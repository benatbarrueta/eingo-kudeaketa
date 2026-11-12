from copy import deepcopy
from datetime import date

import pytest

from app.models.calendar import CalendarError
from app.services.bidirectional_sync import merge, BidirectionalSync
from app.core.config import Settings
from app.repositories.google_sheets_repository import SheetsRepository
from app.repositories.synced_repository import SyncedRepository
from app.repositories.mock_repository import MockRepository
from test_sheets import FakeSheets, COLUMNS


def record(town="A", extra="private"):
    return ["URTARRILAK 7", town, "", "12:00", "", "", "ERROMERIA", extra, "other"]


def test_doc_edit_keeps_private_columns():
    base = [record()]
    docs = [record("B")[:7]]
    assert merge(base, base, docs) == [record("B")]


def test_sheets_edit_reaches_doc_projection():
    base = [record()]
    sheets = [record("B", "new-private")]
    assert merge(base, sheets, [record()[:7]]) == sheets


def test_non_overlapping_fields_merge():
    base = [record()]
    sheets = deepcopy(base)
    sheets[0][3] = "16:00"
    docs = [record("B")[:7]]
    assert merge(base, sheets, docs)[0] == ["URTARRILAK 7", "B", "", "16:00", "", "", "ERROMERIA", "private", "other"]


def test_same_field_conflict():
    with pytest.raises(CalendarError, match="sync_conflict"):
        merge([record()], [record("B")], [record("C")[:7]])


def test_doc_add_delete_and_private_data():
    original = record()
    second = ["OTSAILAK 17", "B", "", "", "", "", "", "", ""]
    assert merge([original], [original], [original[:7], second[:7]]) == [original, second]
    assert merge([original], [original], []) == []
    with pytest.raises(CalendarError, match="sync_conflict"):
        merge([original], [record(extra="edited")], [])


def test_duplicate_events_stop_ambiguous_edit():
    original = record()
    with pytest.raises(CalendarError, match="sync_ambiguous_events"):
        merge([original, original], [original, original], [original[:7], record("B")[:7]])


def make_engine(tmp_path):
    source = SheetsRepository(Settings("sheets", 2027), FakeSheets([COLUMNS, record()]))
    document = MockRepository(2027)
    document.calendar.columns = COLUMNS[:7]
    document.calendar.rows = document.calendar.rows[:2]
    document.calendar.rows[0].values = COLUMNS[:7]
    document.calendar.rows[1].values = record()[:7]
    document.calendar.rows[1].date = date(2027, 1, 7)
    document.needs_review = False
    repo = SyncedRepository(source, document)
    engine = BidirectionalSync(repo, tmp_path / "state.json", 2027, ["test"])
    return engine, source, document


def test_poll_both_directions_and_restart(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    engine.run()
    docs.calendar.rows[1].values[1] = "From Docs"
    engine.run()
    assert sheets.read().rows[1].values == record("From Docs")
    sheets.client.rows[1][3] = "18:00"
    engine = BidirectionalSync(engine.repository, tmp_path / "state.json", 2027, ["test"])
    engine.run()
    assert docs.read().events()[0]["values"][3] == "18:00"
    assert sheets.read().events()[0]["values"][7:] == ["private", "other"]


def test_poll_conflict_writes_neither_side(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    engine.run()
    sheets.client.rows[1][1] = "Sheets"
    docs.calendar.rows[1].values[1] = "Docs"
    engine.tick()
    assert engine.error == "sync_conflict"
    assert sheets.read().rows[1].values[1] == "Sheets"
    assert docs.read().events()[0]["values"][1] == "Docs"


def test_initial_difference_has_no_authoritative_side(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    docs.calendar.rows[1].values[1] = "Different"
    engine.tick()
    assert engine.error == "sync_initial_mismatch"
    assert sheets.client.requests == []


def test_moved_event_cannot_lose_private_values():
    one = record()
    two = record("B", "second-private")
    two[0] = "URTARRILAK 10"
    moved = record()
    moved[0] = "URTARRILAK 15"
    with pytest.raises(CalendarError, match="sync_ambiguous_events"):
        merge([one, two], [one, two], [two[:7], moved[:7]])


def test_manual_agreement_resolves_conflict(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    engine.run()
    sheets.client.rows[1][1] = "Sheets"
    docs.calendar.rows[1].values[1] = "Docs"
    engine.tick()
    assert engine.error == "sync_conflict"
    docs.calendar.rows[1].values[1] = "Sheets"
    engine.tick()
    assert engine.error is None


def test_tick_does_not_overwrite_new_edit_during_pending_plan(tmp_path):
    engine, sheets, docs = make_engine(tmp_path)
    engine.run()
    baseline = [record()]
    engine._save({
        "base": baseline,
        "target": [record("Wanted")],
        "sheets": baseline,
        "docs": [record()[:7]],
    })
    sheets.client.rows[1][1] = "New edit"
    engine.tick()
    assert engine.error == "sync_conflict"
    assert sheets.read().rows[1].values[1] == "New edit"
    assert docs.read().events()[0]["values"][1] == "A"
