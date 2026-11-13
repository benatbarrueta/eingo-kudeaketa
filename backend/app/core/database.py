"""Private SQLite storage, explicit transactions and ordered schema migrations."""
from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import tempfile
from time import monotonic

from app.models.calendar import CalendarError


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def resolve_database_path(path):
    """Anchor relative database paths to the backend, independent of launch cwd."""
    candidate = Path(path).expanduser()
    return (candidate if candidate.is_absolute() else BACKEND_ROOT / candidate).resolve()


def verify_database(path):
    """Read-only integrity and relation checks; never migrate a backup."""
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"events", "sync_configurations", "sync_states", "sync_operations", "sync_conflicts", "event_changes"}
        if not 1 <= version <= len(list((Path(__file__).parents[1] / "migrations").glob("*.sql"))) or not required <= tables:
            raise ValueError("Unsupported database backup schema")
        if (connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise ValueError("Invalid database backup")
    finally:
        connection.close()


def backup_database(source, destination, stop=None):
    """Publish a verified, consistent backup atomically, without overwriting files."""
    source, target = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or target == source or target.exists():
        raise ValueError("Choose an existing source and a new backup file")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".backup-", suffix=".sqlite3")
    os.close(descriptor)
    deadline = monotonic() + 60

    def progress(status, remaining, total):
        if (stop is not None and stop.is_set()) or monotonic() > deadline:
            raise TimeoutError("Backup interrupted")

    try:
        connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=1)
        output = None
        try:
            output = sqlite3.connect(temporary)
            connection.backup(output, pages=128, progress=progress, sleep=.05)
        finally:
            if output is not None:
                output.close()
            connection.close()
        verify_database(temporary)
        with open(temporary, "rb") as backup:
            os.fsync(backup.fileno())
        # A hard link publishes the complete file and refuses an existing destination.
        os.link(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Database:
    def __init__(self, path):
        self.path = resolve_database_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        self.migrate()

    @contextmanager
    def transaction(self, write=False):
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.OperationalError as exc:
            connection.rollback()
            if "locked" in str(exc) or "busy" in str(exc):
                raise CalendarError("database_busy", 503) from exc
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self):
        migrations = sorted((Path(__file__).parents[1] / "migrations").glob("*.sql"))
        with self.transaction(write=True) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > len(migrations):
                raise RuntimeError("Database schema is newer than this application")
            for number, migration in enumerate(migrations, 1):
                if number <= version:
                    continue
                # executescript commits implicitly; execute each complete statement instead.
                statement = ""
                for line in migration.read_text().splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise RuntimeError("Incomplete database migration")
                connection.execute(f"PRAGMA user_version = {number}")

    def backup(self, destination, stop=None):
        """SQLite's backup API produces a consistent copy even while the app runs."""
        backup_database(self.path, destination, stop)
