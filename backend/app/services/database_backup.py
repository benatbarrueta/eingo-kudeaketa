"""Hourly private SQLite backups with verification and bounded retention."""
from datetime import datetime, timezone
import fcntl
import hashlib
import logging
import os
import re
from uuid import uuid4

from app.core.database import resolve_database_path, verify_database


logger = logging.getLogger(__name__)


class DatabaseBackups:
    def __init__(self, database, directory, interval=3600, keep=48):
        if interval < 60 or keep < 1:
            raise ValueError("Invalid backup interval or retention")
        self.database = database
        self.directory = resolve_database_path(directory)
        self.interval, self.keep = interval, keep
        self.last_success = None
        self.error = None
        self.count = 0
        identity = hashlib.sha256(str(database.path).encode()).hexdigest()[:12]
        self.prefix = "eingo-" + identity + "-"
        self.pattern = re.compile(re.escape(self.prefix) + r"(\d{8}T\d{12}Z)-[a-f0-9]{8}\.sqlite3$")

    def _copies(self):
        result = []
        for path in self.directory.iterdir():
            match = self.pattern.fullmatch(path.name)
            if not match or path.is_symlink() or not path.is_file():
                continue
            try:
                timestamp = datetime.strptime(match[1], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            result.append((timestamp, path))
        return sorted(result, reverse=True)

    def tick(self, stop=None):
        try:
            return self._tick(stop)
        except Exception as exc:
            if stop is not None and stop.is_set():
                return None
            code = "backup_failed"
            if self.error != code:
                # Exception messages may include private paths; report only the type.
                logger.error("Automatic database backup failed (%s)", type(exc).__name__)
            self.error = code
            return None

    def _tick(self, stop):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.stat().st_mode & 0o077:
            raise PermissionError("Backup directory must be private")
        lock_path = self.directory / ("." + self.prefix + "lock")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(descriptor, "a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return None
            copies = self._copies()
            self.count = len(copies)
            now = datetime.now(timezone.utc)
            if copies and 0 <= (now - copies[0][0]).total_seconds() < self.interval:
                try:
                    verify_database(copies[0][1])
                except Exception:
                    pass  # A damaged recent copy must not postpone a new one.
                else:
                    self.last_success = copies[0][0].isoformat()
                    self.error = None
                    return None
            destination = self.directory / (self.prefix + now.strftime("%Y%m%dT%H%M%S%fZ")
                                             + "-" + uuid4().hex[:8] + ".sqlite3")
            self.database.backup(destination, stop)
            # Prune only our own complete files, and only after verifying the new copy.
            copies = self._copies()
            for _, path in copies[self.keep:]:
                path.unlink()
            self.count = len(self._copies())
            self.last_success = now.isoformat()
            self.error = None
            return destination

    def run(self, stop):
        while not stop.is_set():
            self.tick(stop)
            stop.wait(min(60, self.interval))

    def status(self):
        return {"enabled": True, "lastSuccess": self.last_success, "error": self.error,
                "intervalSeconds": self.interval, "retainedCopies": self.count, "keep": self.keep}
