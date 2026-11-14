from datetime import datetime, timedelta, timezone
import fcntl
from pathlib import Path
import sqlite3
import stat
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import backup_database, verify_database
from app.main import create_app
from app.repositories.database_repository import DatabaseRepository
from app.services import database_backup
from app.services.database_backup import DatabaseBackups
from test_bidirectional_sync import record


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        instant = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.instant

    monkeypatch.setattr(database_backup, "datetime", Clock)
    return Clock


def repository(tmp_path):
    repo = DatabaseRepository(tmp_path / "agenda.sqlite3", 2027)
    repo.insert(repo.read(), 0, True, record())
    return repo


def dump(path):
    connection = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    try:
        return list(connection.iterdump())
    finally:
        connection.close()


def test_automatic_copy_is_private_complete_and_restart_does_not_duplicate(tmp_path, clock):
    repo = repository(tmp_path)
    copies = DatabaseBackups(repo.database, tmp_path / "backups")
    first = copies.tick()
    assert first and first.is_file()
    assert dump(first) == dump(repo.database.path)
    assert stat.S_IMODE(first.stat().st_mode) == 0o600
    assert stat.S_IMODE(first.parent.stat().st_mode) == 0o700
    verify_database(first)
    restarted = DatabaseBackups(repo.database, copies.directory)
    assert restarted.tick() is None
    assert restarted.count == 1 and restarted.last_success
    clock.instant += timedelta(hours=1)
    repo.update(repo.read(), 1, record("New"))
    second = restarted.tick()
    assert second and second != first
    assert dump(second) == dump(repo.database.path)
    assert dump(first) != dump(second)


def test_retention_keeps_latest_copies_and_never_touches_other_files(tmp_path, clock):
    repo = repository(tmp_path)
    copies = DatabaseBackups(repo.database, tmp_path / "backups", keep=2)
    first = copies.tick()
    manual = copies.directory / "manual.sqlite3"
    repo.database.backup(manual)
    other_repo = DatabaseRepository(tmp_path / "other.sqlite3", 2027)
    other_copy = DatabaseBackups(other_repo.database, copies.directory).tick()
    clock.instant += timedelta(hours=1)
    second = copies.tick()
    clock.instant += timedelta(hours=1)
    third = copies.tick()
    assert not first.exists()
    assert second.exists() and third.exists() and manual.exists() and other_copy.exists()
    assert copies.status()["retainedCopies"] == 2


def test_failed_backup_does_not_prune_existing_copies(tmp_path, clock, monkeypatch):
    repo = repository(tmp_path)
    copies = DatabaseBackups(repo.database, tmp_path / "backups", keep=1)
    first = copies.tick()
    clock.instant += timedelta(hours=1)
    monkeypatch.setattr(repo.database, "backup", lambda *args: (_ for _ in ()).throw(OSError("private detail")))
    assert copies.tick() is None
    assert copies.error == "backup_failed" and first.exists()
    assert list(copies.directory.glob("*.sqlite3")) == [first]


def test_corrupt_recent_copy_is_replaced_immediately(tmp_path, clock):
    repo = repository(tmp_path)
    copies = DatabaseBackups(repo.database, tmp_path / "backups")
    first = copies.tick()
    first.write_bytes(b"damaged")
    replacement = copies.tick()
    assert replacement and replacement != first
    verify_database(replacement)
    assert copies.error is None


def test_restore_preserves_events_history_sync_state_and_pending_plan(tmp_path):
    repo = repository(tmp_path)
    repo.accept([record()], [record()], [1], [1])
    repo.conflict("sync_conflict", {"base": [record()]})
    repo.checkpoint({"target": [record("New")], "database": [record()], "sheets": [record()], "docs": [record()[:7]]})
    source_dump = dump(repo.database.path)
    backup = tmp_path / "backup.sqlite3"
    repo.database.backup(backup)
    restored = tmp_path / "restored.sqlite3"
    backup_database(backup, restored)
    verify_database(restored)
    assert dump(restored) == source_dump == dump(repo.database.path)
    reopened = DatabaseRepository(restored, 2027)
    assert reopened.read().events()[0]["eventId"] == repo.read().events()[0]["eventId"]
    assert reopened.history() == repo.history()
    assert reopened.synchronization()[2].payload == repo.synchronization()[2].payload
    assert reopened.conflicts() == repo.conflicts()
    with pytest.raises(ValueError):
        backup_database(backup, repo.database.path)
    assert dump(repo.database.path) == source_dump


def test_cancelled_or_invalid_backup_is_never_published(tmp_path):
    repo = repository(tmp_path)
    stop = Event()
    stop.set()
    target = tmp_path / "interrupted.sqlite3"
    with pytest.raises(TimeoutError):
        repo.database.backup(target, stop)
    assert not target.exists()
    assert not list(tmp_path.glob(".backup-*"))
    wrong = tmp_path / "wrong.sqlite3"
    with sqlite3.connect(wrong) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    with pytest.raises(ValueError):
        verify_database(wrong)
    with pytest.raises(ValueError):
        backup_database(wrong, target)
    assert not target.exists()


def test_backup_checks_foreign_keys_without_repairing_data(tmp_path):
    repo = repository(tmp_path)
    backup = tmp_path / "backup.sqlite3"
    repo.database.backup(backup)
    with sqlite3.connect(backup) as connection:
        connection.execute("DELETE FROM sync_configurations")
    with pytest.raises(ValueError, match="Invalid"):
        verify_database(backup)


def test_backup_lock_prevents_two_workers_from_writing(tmp_path):
    repo = repository(tmp_path)
    copies = DatabaseBackups(repo.database, tmp_path / "backups")
    copies.directory.mkdir(mode=0o700)
    with open(copies.directory / ("." + copies.prefix + "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert copies.tick() is None
        assert not list(copies.directory.glob("*.sqlite3"))
    assert copies.tick() is not None


def test_lifespan_runs_backup_and_exposes_status_without_paths(tmp_path):
    settings = Settings("database", 2027, database_path=str(tmp_path / "agenda.sqlite3"),
                        backup_directory=str(tmp_path / "backups"))
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/backup/status").json()
        assert status["enabled"] and status["lastSuccess"] and status["retainedCopies"] == 1
        assert status["error"] is None and status["keep"] == 48
        assert str(tmp_path) not in str(status)
    mock = TestClient(create_app(Settings("mock", 2027)))
    assert not mock.get("/api/backup/status").json()["enabled"]


def test_cli_restore_and_verify_never_overwrite_original(tmp_path, monkeypatch, capsys):
    from app.database_cli import main

    repo = repository(tmp_path)
    backup = tmp_path / "backup.sqlite3"
    repo.database.backup(backup)
    restored = tmp_path / "restored.sqlite3"
    monkeypatch.setattr("sys.argv", ["database_cli", "restore", str(backup), str(restored)])
    main()
    assert dump(restored) == dump(backup)
    monkeypatch.setattr("sys.argv", ["database_cli", "verify", str(restored)])
    main()
    assert "verified" in capsys.readouterr().out
