"""Calendar persistence; mutations and their history commit in one transaction."""
from datetime import date, datetime, timezone
import json
from uuid import uuid4

from app.core.database import Database
from app.models.calendar import Calendar, CalendarError, Row
from app.models.database import (COLUMNS, Event, EventChange, SyncConfiguration,
                                 SyncConflict, SyncOperation, SyncState)
from app.utils.basque_dates import format_date, parse


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, ensure_ascii=False)


def values(row):
    return [row[key] for key in ("date_label", "town", "nor", "time", "billing",
                                "confirmation", "description", "wawa", "wewe")]


class DatabaseRepository:
    def __init__(self, path, year, identity=None):
        self.database = Database(path)
        self.year = year
        identity = identity or []
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT * FROM sync_configurations WHERE year = ?", (year,)).fetchone()
            if row is None:
                self.configuration_id = str(uuid4())
                connection.execute("INSERT INTO sync_configurations(id, year, identity) VALUES (?, ?, ?)",
                                   (self.configuration_id, year, encode(identity)))
            else:
                self.configuration_id = row["id"]
                if json.loads(row["identity"]) == [] and identity and not row["initialized"]:
                    connection.execute("UPDATE sync_configurations SET identity=? WHERE id=?",
                                       (encode(identity), self.configuration_id))
                elif json.loads(row["identity"]) != identity:
                    raise CalendarError("sync_state_mismatch")

    @property
    def needs_review(self):
        with self.database.transaction() as connection:
            return bool(connection.execute("""SELECT 1 FROM sync_conflicts WHERE configuration_id=? AND resolved_at IS NULL
                UNION ALL SELECT 1 FROM sync_operations WHERE configuration_id=? AND status='pending'""",
                (self.configuration_id, self.configuration_id)).fetchone())

    def configuration(self, connection):
        row = connection.execute("SELECT * FROM sync_configurations WHERE id = ?",
                                 (self.configuration_id,)).fetchone()
        return SyncConfiguration(row["id"], row["year"], json.loads(row["identity"]),
                                 bool(row["initialized"]), row["revision"])

    def _active(self, connection):
        return connection.execute(
            "SELECT * FROM events WHERE configuration_id = ? AND deleted_at IS NULL ORDER BY date, position, id",
            (self.configuration_id,)).fetchall()

    def _read(self, connection):
        configuration = self.configuration(connection)
        rows = [Row("header", COLUMNS.copy(), [], spans=[1] * 9)]
        for row in self._active(connection):
            rows.append(Row("event", values(row), [], date.fromisoformat(row["date"]),
                            [1] * 9, event_id=row["id"], version=row["version"]))
        return Calendar(COLUMNS.copy(), rows, revision=str(configuration.revision))

    def read(self):
        with self.database.transaction() as connection:
            return self._read(connection)

    def _check(self, connection, calendar):
        if str(self.configuration(connection).revision) != calendar.revision:
            raise CalendarError("revision_conflict")
        if connection.execute("SELECT 1 FROM sync_operations WHERE configuration_id = ? AND status = 'pending'",
                              (self.configuration_id,)).fetchone():
            raise CalendarError("database_sync_pending")
        if connection.execute("SELECT 1 FROM sync_conflicts WHERE configuration_id = ? AND resolved_at IS NULL",
                              (self.configuration_id,)).fetchone():
            raise CalendarError("sync_conflict")

    def _validate(self, data):
        if len(data) != 9 or not all(isinstance(value, str) for value in data) or not data[1].strip():
            raise CalendarError("unsafe_structure")
        try:
            day = parse(data[0], self.year)
        except ValueError as exc:
            raise CalendarError("unsafe_structure") from exc
        if day.year != self.year:
            raise CalendarError("wrong_year", 422)
        return day

    def _change(self, connection, event_id, before, after, origin):
        action = "created" if before is None else "deleted" if after is None else "updated"
        connection.execute(
            "INSERT INTO event_changes VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), event_id, action, origin, encode(before) if before is not None else None,
             encode(after) if after is not None else None, now()))

    def _create(self, connection, data, position, origin):
        day = self._validate(data)
        event_id, timestamp = str(uuid4()), now()
        connection.execute(
            """INSERT INTO events(id, configuration_id, date, date_label, town, nor, time,
               billing, confirmation, description, wawa, wewe, position, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, self.configuration_id, day.isoformat(), *data, position, timestamp, timestamp))
        self._change(connection, event_id, None, data, origin)
        return event_id

    def _update(self, connection, row, data, position, origin):
        day = self._validate(data)
        if values(row) != data:
            connection.execute(
                """UPDATE events SET date=?, date_label=?, town=?, nor=?, time=?, billing=?,
                   confirmation=?, description=?, wawa=?, wewe=?, position=?, version=version+1,
                   updated_at=? WHERE id=?""", (day.isoformat(), *data, position, now(), row["id"]))
            self._change(connection, row["id"], values(row), data, origin)
        else:
            connection.execute("UPDATE events SET position=? WHERE id=?", (position, row["id"]))

    def _delete(self, connection, row, origin):
        timestamp = now()
        connection.execute("UPDATE events SET deleted_at=?, updated_at=?, version=version+1 WHERE id=?",
                           (timestamp, timestamp, row["id"]))
        self._change(connection, row["id"], values(row), None, origin)

    def _bump(self, connection):
        connection.execute("UPDATE sync_configurations SET revision=revision+1 WHERE id=?",
                           (self.configuration_id,))

    def insertion(self, calendar, day):
        for index, row in enumerate(calendar.rows[1:], 1):
            if row.date > day:
                return index, False
        return len(calendar.rows) - 1, True

    def insert(self, calendar, anchor, below, data):
        with self.database.transaction(write=True) as connection:
            self._check(connection, calendar)
            position = anchor + int(below) - 1
            rows = self._active(connection)
            for index, row in enumerate(rows):
                connection.execute("UPDATE events SET position=? WHERE id=?",
                                   (index + int(index >= position), row["id"]))
            self._create(connection, data, position, "web")
            self._bump(connection)
            return self._read(connection)

    def update(self, calendar, index, data):
        with self.database.transaction(write=True) as connection:
            self._check(connection, calendar)
            row = self._active(connection)[index - 1]
            self._update(connection, row, data, row["position"], "web")
            if values(row) != data:
                self._bump(connection)
            return self._read(connection)

    def delete(self, calendar, index):
        with self.database.transaction(write=True) as connection:
            self._check(connection, calendar)
            self._delete(connection, self._active(connection)[index - 1], "web")
            self._bump(connection)
            return self._read(connection)

    def records(self):
        with self.database.transaction() as connection:
            return [Event(row["id"], row["configuration_id"], date.fromisoformat(row["date"]),
                          *values(row)[1:], row["version"], datetime.fromisoformat(row["created_at"]),
                          datetime.fromisoformat(row["updated_at"]),
                          datetime.fromisoformat(row["deleted_at"]) if row["deleted_at"] else None)
                    for row in connection.execute("SELECT * FROM events WHERE configuration_id=?",
                                                  (self.configuration_id,))]

    def history(self):
        with self.database.transaction() as connection:
            return [EventChange(row["id"], row["event_id"], row["action"], row["origin"],
                                json.loads(row["before_json"]) if row["before_json"] else None,
                                json.loads(row["after_json"]) if row["after_json"] else None, row["created_at"])
                    for row in connection.execute("""SELECT c.* FROM event_changes c JOIN events e ON e.id=c.event_id
                        WHERE e.configuration_id=? ORDER BY c.rowid""", (self.configuration_id,))]

    def synchronization(self):
        with self.database.transaction() as connection:
            config = self.configuration(connection)
            states = [SyncState(row["event_id"], row["ordinal"], json.loads(row["values_json"]),
                                row["sheet_row"], row["document_row"], row["verified_at"])
                      for row in connection.execute("SELECT * FROM sync_states WHERE configuration_id=? ORDER BY ordinal",
                                                    (self.configuration_id,))]
            row = connection.execute("SELECT * FROM sync_operations WHERE configuration_id=? AND status='pending'",
                                     (self.configuration_id,)).fetchone()
            operation = SyncOperation(row["id"], row["configuration_id"], row["status"],
                                      json.loads(row["payload"]), row["attempts"], row["error"]) if row else None
            return config, states, operation

    def checkpoint(self, payload, expected_revision=None):
        with self.database.transaction(write=True) as connection:
            if expected_revision is not None and str(self.configuration(connection).revision) != expected_revision:
                raise CalendarError("conflict_changed")
            row = connection.execute("SELECT id FROM sync_operations WHERE configuration_id=? AND status='pending'",
                                     (self.configuration_id,)).fetchone()
            if expected_revision is not None and row:
                raise CalendarError("conflict_changed")
            timestamp = now()
            if row:
                connection.execute("UPDATE sync_operations SET payload=?, updated_at=? WHERE id=?",
                                   (encode(payload), timestamp, row["id"]))
            else:
                connection.execute("INSERT INTO sync_operations VALUES (?, ?, 'pending', ?, 0, NULL, ?, ?)",
                                   (str(uuid4()), self.configuration_id, encode(payload), timestamp, timestamp))

    def conflict(self, code, snapshots):
        with self.database.transaction(write=True) as connection:
            row = connection.execute("SELECT id FROM sync_conflicts WHERE configuration_id=? AND resolved_at IS NULL",
                                     (self.configuration_id,)).fetchone()
            if row:
                connection.execute("UPDATE sync_conflicts SET code=?, snapshots=? WHERE id=?",
                                   (code, encode(snapshots), row["id"]))
            else:
                connection.execute("INSERT INTO sync_conflicts VALUES (?, ?, NULL, ?, ?, ?, NULL)",
                                   (str(uuid4()), self.configuration_id, code, encode(snapshots), now()))
            connection.execute("""UPDATE sync_operations SET error=?, attempts=attempts+1, updated_at=?
                WHERE configuration_id=? AND status='pending'""", (code, now(), self.configuration_id))

    def operation_error(self, code):
        with self.database.transaction(write=True) as connection:
            connection.execute("""UPDATE sync_operations SET error=?, attempts=attempts+1, updated_at=?
                WHERE configuration_id=? AND status='pending'""", (code, now(), self.configuration_id))

    def conflicts(self):
        with self.database.transaction() as connection:
            return [SyncConflict(row["id"], row["configuration_id"], row["event_id"], row["code"],
                                 json.loads(row["snapshots"]), row["resolved_at"])
                    for row in connection.execute("SELECT * FROM sync_conflicts WHERE configuration_id=?",
                                                  (self.configuration_id,))]

    def accept(self, target, expected, sheet_rows, document_rows, origin="reconciliation"):
        """Advance the common baseline only after both remote files were reread."""
        from app.services.bidirectional_sync import align

        if len(target) != len(sheet_rows) or len(target) != len(document_rows):
            raise CalendarError("unsafe_structure")
        with self.database.transaction(write=True) as connection:
            rows = self._active(connection)
            current = [values(row) for row in rows]
            if current != expected:
                raise CalendarError("revision_conflict")
            mapped, inserted = align(current, target, width=9)
            ids = []
            for index in range(len(rows) + 1):
                for data in inserted.get(index, []):
                    ids.append(self._create(connection, data, len(ids), origin))
                if index == len(rows):
                    break
                data = mapped[index]
                if data is None:
                    self._delete(connection, rows[index], origin)
                else:
                    self._update(connection, rows[index], data, len(ids), origin)
                    ids.append(rows[index]["id"])
            if current != target:
                self._bump(connection)
            connection.execute("DELETE FROM sync_states WHERE configuration_id=?", (self.configuration_id,))
            for ordinal, (event_id, data, sheet_row, document_row) in enumerate(zip(ids, target, sheet_rows, document_rows)):
                connection.execute("INSERT INTO sync_states VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (event_id, self.configuration_id, ordinal, encode(data), sheet_row, document_row, now()))
            connection.execute("UPDATE sync_configurations SET initialized=1 WHERE id=?", (self.configuration_id,))
            connection.execute("""UPDATE sync_operations SET status='completed', error=NULL, updated_at=?
                WHERE configuration_id=? AND status='pending'""", (now(), self.configuration_id))
            connection.execute("UPDATE sync_conflicts SET resolved_at=? WHERE configuration_id=? AND resolved_at IS NULL",
                               (now(), self.configuration_id))
