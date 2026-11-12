from app.models.calendar import CalendarError
from app.services.chronological_service import insertion
from app.utils.basque_dates import format_date, parse


class SyncedRepository:
    """Sheets owns all fields; Docs contains only the configured projection."""

    def __init__(self, source, document):
        self.source = source
        self.document = document
        self.sync_pending = False

    @property
    def needs_review(self):
        return self.sync_pending or self.document.needs_review

    def read(self):
        return self.source.read()

    def insertion(self, calendar, day):
        return self.source.insertion(calendar, day)

    def _project(self, calendar, document):
        expected = calendar.columns[:7]
        if document.columns != expected:
            raise CalendarError("document_columns_mismatch")
        return [[format_date(row.date), *row.values[1:7]]
                for row in calendar.rows if row.kind == "event"]

    def _preflight(self, calendar):
        if self.needs_review:
            raise CalendarError("sync_pending")
        document = self.document.read()
        if any(row.kind == "unknown" for row in document.rows):
            raise CalendarError("unsafe_structure")
        if [event["values"] for event in document.events()] != self._project(calendar, document):
            raise CalendarError("sources_differ")
        return document

    def _finish(self, operation):
        self.sync_pending = True
        try:
            operation()
        except Exception as exc:
            raise CalendarError("sync_pending") from exc
        self.sync_pending = False

    def insert(self, calendar, anchor, below, values):
        document = self._preflight(calendar)
        day = parse(values[0], self.source.settings.year)
        doc_anchor, doc_below = insertion(document, day)
        final = self.source.insert(calendar, anchor, below, values)
        projected = [format_date(day), *values[1:7]]
        self._finish(lambda: self.document.insert(document, doc_anchor, doc_below, projected))
        return final

    def update(self, calendar, index, values):
        document = self._preflight(calendar)
        ordinal = sum(row.kind == "event" for row in calendar.rows[:index])
        doc_index = document.events()[ordinal]["id"]
        final = self.source.update(calendar, index, values)
        day = final.rows[index].date
        self._finish(lambda: self.document.update(document, doc_index, [format_date(day), *values[1:7]]))
        return final

    def delete(self, calendar, index):
        document = self._preflight(calendar)
        ordinal = sum(row.kind == "event" for row in calendar.rows[:index])
        doc_index = document.events()[ordinal]["id"]
        final = self.source.delete(calendar, index)
        self._finish(lambda: self.document.delete(document, doc_index))
        return final

    def import_document(self):
        source = self.source.read()
        document = self.document.read()
        if any(row.kind == "unknown" for row in document.rows):
            raise CalendarError("unsafe_structure")
        projected = self._project(source, document)
        events = document.events()
        if projected != [event["values"] for event in events[:len(projected)]]:
            raise CalendarError("sources_differ")
        dates = [event["date"] for event in events]
        if dates != sorted(dates):
            raise CalendarError("unsafe_structure")
        for event in events[len(projected):]:
            values = [*event["values"], "", ""]
            source = self.source.insert(source, len(source.rows) - 1, True, values)
        return source

    def synchronize(self):
        source = self.source.read()
        document = self.document.read()
        values = self._project(source, document)
        events = document.events()
        if any(row.kind == "unknown" for row in document.rows):
            raise CalendarError("manual_review")
        # Resume a single interrupted mutation, including after a process restart.
        old = [event["values"] for event in events]
        if old == values:
            self.sync_pending = False
            return document
        if len(old) == len(values):
            differences = [i for i, pair in enumerate(zip(old, values)) if pair[0] != pair[1]]
            if len(differences) != 1:
                raise CalendarError("sources_differ")
            i = differences[0]
            if parse(values[i][0], self.source.settings.year).month != events[i]["date"].month:
                raise CalendarError("sources_differ")
            result = self.document.update(document, events[i]["id"], values[i])
        elif len(values) == len(old) + 1:
            candidates = [i for i in range(len(values)) if values[:i] + values[i + 1:] == old]
            if not candidates:
                raise CalendarError("sources_differ")
            i = candidates[-1]
            anchor, below = insertion(document, parse(values[i][0], self.source.settings.year))
            result = self.document.insert(document, anchor, below, values[i])
        elif len(old) == len(values) + 1:
            candidates = [i for i in range(len(old)) if old[:i] + old[i + 1:] == values]
            if not candidates:
                raise CalendarError("sources_differ")
            result = self.document.delete(document, events[candidates[-1]]["id"])
        else:
            raise CalendarError("sources_differ")
        self.sync_pending = False
        return result
