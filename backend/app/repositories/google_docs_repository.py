from app.models.calendar import CalendarError
from app.integrations.google.docs_client import DocsClient
from app.integrations.google.document_parser import read
from app.integrations.google.table_writer import insert_row, fill_row, edit_row, delete_row, unmerge_row


class GoogleRepository:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or DocsClient(settings)
        self.needs_review = False

    def read(self):
        try:
            return read(self.client.get(), self.settings.tab, self.settings.table, self.settings.year)
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise CalendarError("unsafe_structure") from exc

    def insert(self, calendar, anchor, below, values):
        if self.needs_review:
            raise CalendarError("manual_review")
        index = anchor + int(below)
        template = calendar.rows[anchor]
        requests = [insert_row(calendar, anchor, below)]
        if template.kind == "separator":
            if template.spans == [len(calendar.columns)]:
                # Docs copies the anchor's horizontal merge into the new row.
                requests.append(unmerge_row(calendar, index))
            template = min(
                ((abs(i - anchor), i, row) for i, row in enumerate(calendar.rows) if row.kind == "event"),
                default=(0, 0, None),
            )[2]
        # Block all further writes if a two-phase edit may have been interrupted.
        self.needs_review = True
        try:
            result = self.client.write(requests, calendar.revision)
        except CalendarError as exc:
            if exc.code in {"revision_conflict", "missing_revision", "google_access_denied"}:
                self.needs_review = False
                raise
            raise CalendarError("manual_review") from exc
        except Exception as exc:
            raise CalendarError("manual_review") from exc
        try:
            updated = self.read()
            signature = lambda rows: [(r.kind, r.values, r.spans) for r in rows]
            if (not updated.revision or updated.revision == calendar.revision
                    or result.get("writeControl", {}).get("requiredRevisionId") != updated.revision
                    or updated.tab != calendar.tab or updated.start != calendar.start
                    or len(updated.rows) != len(calendar.rows) + 1
                    or signature(updated.rows[:index] + updated.rows[index + 1:]) != signature(calendar.rows)):
                raise CalendarError("unexpected_new_row")
            style = {"cells": template.cells, "row_style": template.style or {}} if template else None
            requests = fill_row(updated, index, values, style)
            self.client.write(requests, updated.revision)
            final = self.read()
            if (len(final.rows) != len(updated.rows) or final.rows[index].kind != "event"
                    or final.rows[index].values != values
                    or signature(final.rows[:index] + final.rows[index + 1:]) != signature(calendar.rows)):
                raise CalendarError("unexpected_new_row")
        except Exception as exc:
            raise CalendarError("manual_review") from exc
        self.needs_review = False
        return final

    def update(self, calendar, index, values):
        if self.needs_review:
            raise CalendarError("manual_review")
        requests = edit_row(calendar, index, values)
        if requests:
            self.client.write(requests, calendar.revision)
            return self.read()
        return calendar

    def delete(self, calendar, index):
        if self.needs_review:
            raise CalendarError("manual_review")
        self.client.write([delete_row(calendar, index)], calendar.revision)
        return self.read()
