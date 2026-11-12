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
            final = self.repo.insert(calendar, anchor, below, values)
            index = anchor + int(below)
            return {"event": next(e for e in final.events() if e["id"] == index),
                    "table": final.public(), "created": True}

    def _target(self, calendar, index, expected):
        if not 0 <= index < len(calendar.rows):
            raise CalendarError("revision_conflict")
        row = calendar.rows[index]
        if row.kind != "event" or row.values != expected:
            raise CalendarError("revision_conflict")
        if any(candidate.kind == "unknown" for candidate in calendar.rows):
            raise CalendarError("unsafe_structure")
        return row

    def update(self, index, event):
        with self.lock:
            self.synchronize()
            calendar = self.repo.read()
            row = self._target(calendar, index, event.expected)
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
            final = self.repo.update(calendar, index, values)
            return {"event": next(e for e in final.events() if e["id"] == index),
                    "table": final.public(), "created": False}

    def delete(self, index, target):
        with self.lock:
            self.synchronize()
            calendar = self.repo.read()
            self._target(calendar, index, target.expected)
            return self.repo.delete(calendar, index).public()

    def reset(self):
        with self.lock:
            self.repo.reset()
