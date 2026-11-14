from dataclasses import dataclass
from datetime import date as Date


class CalendarError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass
class Row:
    kind: str
    values: list[str]
    cells: list
    date: Date | None = None
    spans: list[int] | None = None
    style: dict | None = None
    event_id: str | None = None
    version: int | None = None


@dataclass
class Calendar:
    columns: list[str]
    rows: list[Row]
    revision: str = ""
    tab: str | None = None
    start: int = 0
    title: str = "EINGO Kudeaketa"

    def public(self):
        return {
            "title": self.title, "columns": self.columns,
            "rows": [{"kind": r.kind, "values": r.values, "spans": r.spans,
                      "date": r.date, **({"eventId": r.event_id, "version": r.version}
                                          if r.event_id else {})} for r in self.rows],
        }

    def events(self):
        return [{"id": i, "date": r.date, "values": r.values,
                 **({"eventId": r.event_id, "version": r.version} if r.event_id else {})}
                for i, r in enumerate(self.rows) if r.kind == "event"]
