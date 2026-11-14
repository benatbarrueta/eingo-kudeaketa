from threading import Lock
from app.models.calendar import CalendarError
from app.services.chronological_service import insertion
from app.utils.basque_dates import format_date


class EventService:
    def __init__(self, repo, year):
        self.repo, self.year = repo, year
        self.lock = Lock()
        self.synchronizer = None

    def synchronize(self):
        if self.synchronizer:
            self.synchronizer.run()

    def _after_write(self):
        if getattr(self.synchronizer, "database", None) is self.repo:
            try:
                self.synchronize()
                return self.repo.read()
            except Exception as exc:
                # The transaction is durable even if Google could not be updated.
                raise CalendarError("database_sync_pending") from exc

    def _preflight(self, calendar, target):
        if getattr(self.synchronizer, "database", None) is self.repo:
            self.synchronizer.validate_change(calendar, target)

    def _index(self, calendar, index):
        if isinstance(index, str) and not index.isdecimal():
            for position, row in enumerate(calendar.rows):
                if row.event_id == index:
                    return position
            raise CalendarError("revision_conflict")
        try:
            return int(index)
        except (ValueError, TypeError) as exc:
            raise CalendarError("revision_conflict") from exc

    def create(self, event):
        with self.lock:
            self.synchronize()
            calendar = self.repo.read()
            if event.date.year != self.year:
                raise CalendarError("wrong_year", 422)
            if event.fields.keys() - (set(calendar.columns) - {"DATA", "HERRIA"}):
                raise CalendarError("invalid_fields", 422)
            data = {**event.fields, "DATA": format_date(event.date), "HERRIA": event.town}
            values = [data.get(col, "") for col in calendar.columns]
            # Natural idempotency survives process restarts and ambiguous responses.
            for existing in calendar.events():
                if existing["date"] == event.date and existing["values"] == values:
                    return {"event": existing, "table": calendar.public(), "created": False}
            anchor, below = (self.repo.insertion(calendar, event.date) if hasattr(self.repo, "insertion")
                             else insertion(calendar, event.date))
            target = [row.values for row in calendar.rows if row.kind == "event"]
            position = sum(row.kind == "event" for row in calendar.rows[:anchor + int(below)])
            target.insert(position, values)
            self._preflight(calendar, target)
            final = self.repo.insert(calendar, anchor, below, values)
            index = anchor + int(below)
            event_id = final.rows[index].event_id
            final = self._after_write() or final
            return {"event": next(e for e in final.events()
                                  if (e.get("eventId") == event_id if event_id else e["id"] == index)),
                    "table": final.public(), "created": True}

    def _target(self, calendar, index, expected, version=None):
        if not 0 <= index < len(calendar.rows):
            raise CalendarError("revision_conflict")
        row = calendar.rows[index]
        if row.kind != "event" or row.values != expected:
            raise CalendarError("revision_conflict")
        if version is not None and row.version != version:
            raise CalendarError("revision_conflict")
        if any(candidate.kind == "unknown" for candidate in calendar.rows):
            raise CalendarError("unsafe_structure")
        return row

    def update(self, index, event):
        with self.lock:
            self.synchronize()
            calendar = self.repo.read()
            index = self._index(calendar, index)
            row = self._target(calendar, index, event.expected, event.expectedVersion)
            if event.date.year != self.year:
                raise CalendarError("wrong_year", 422)
            if event.fields.keys() - (set(calendar.columns) - {"DATA", "HERRIA"}):
                raise CalendarError("invalid_fields", 422)
            dates = [r.date for r in calendar.rows if r.kind == "event"]
            if dates != sorted(dates):
                raise CalendarError("unsafe_structure")
            if event.date != row.date:
                before = [r.date for r in calendar.rows[:index] if r.kind == "event"]
                after = [r.date for r in calendar.rows[index + 1:] if r.kind == "event"]
                if (event.date.month != row.date.month
                        or (before and event.date < before[-1])
                        or (after and event.date > after[0])):
                    raise CalendarError("date_changes_position")
            changes = {**event.fields, "HERRIA": event.town}
            if event.date != row.date:
                changes["DATA"] = format_date(event.date)
            values = [changes.get(column, value)
                      for column, value in zip(calendar.columns, row.values)]
            target = [candidate.values for candidate in calendar.rows if candidate.kind == "event"]
            position = sum(candidate.kind == "event" for candidate in calendar.rows[:index])
            target[position] = values
            self._preflight(calendar, target)
            final = self.repo.update(calendar, index, values)
            final = self._after_write() or final
            return {"event": next(e for e in final.events()
                                  if (e.get("eventId") == row.event_id if row.event_id else e["id"] == index)),
                    "table": final.public(), "created": False}

    def delete(self, index, target):
        with self.lock:
            self.synchronize()
            calendar = self.repo.read()
            index = self._index(calendar, index)
            self._target(calendar, index, target.expected, target.expectedVersion)
            proposed = [row.values for row in calendar.rows if row.kind == "event"]
            position = sum(row.kind == "event" for row in calendar.rows[:index])
            proposed.pop(position)
            self._preflight(calendar, proposed)
            final = self.repo.delete(calendar, index)
            final = self._after_write() or final
            return final.public()

    def reset(self):
        with self.lock:
            self.repo.reset()
