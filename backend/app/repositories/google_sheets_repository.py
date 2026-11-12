from datetime import date, datetime
import hashlib
import json

from app.integrations.google.sheets_client import SheetsClient
from app.models.calendar import Calendar, CalendarError, Row
from app.utils.basque_dates import parse


class SheetsRepository:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or SheetsClient(settings)

    def read(self):
        document = self.client.execute()
        sheets = [sheet for sheet in document.get("sheets", [])
                  if sheet["properties"]["sheetId"] == self.settings.sheet_id]
        if len(sheets) != 1:
            raise CalendarError("sheet_not_found")
        data = sheets[0].get("data", [{}])[0].get("rowData", [])
        if len(data) >= 10000:
            raise CalendarError("sheet_row_limit")
        rows = []
        for raw in data:
            cells = raw.get("values", [])
            values = []
            for cell in cells:
                if "formulaValue" in cell.get("userEnteredValue", {}):
                    raise CalendarError("sheet_formulas_unsupported")
                values.append(cell.get("formattedValue", ""))
            rows.append(values)
        while rows and not any(rows[-1]):
            rows.pop()
        if not rows or len(rows[0]) != 9:
            raise CalendarError("invalid_headers")
        columns = [value.strip().upper() for value in rows[0]]
        if columns != ["DATA", "HERRIA", "NOR", "ORDUA", "FAKTURAZIOA", "KONFIRM", "AZALPENA", "WAWA", "WEWE"]:
            raise CalendarError("invalid_headers")
        result = [Row("header", columns, [], spans=[1] * 9)]
        for values in rows[1:]:
            values = (values + [""] * 9)[:9]
            try:
                if "-" in values[0]:
                    day = date.fromisoformat(values[0])
                elif "/" in values[0]:
                    day = datetime.strptime(values[0], "%d/%m/%Y").date()
                else:
                    day = parse(values[0], self.settings.year)
            except ValueError as exc:
                raise CalendarError("unsafe_structure") from exc
            if day.year != self.settings.year or not values[1]:
                raise CalendarError("unsafe_structure")
            result.append(Row("event", values, [], day, [1] * 9))
        dates = [row.date for row in result[1:]]
        if dates != sorted(dates):
            raise CalendarError("unsafe_structure")
        revision = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
        return Calendar(columns, result, revision=revision, title=document["properties"]["title"])

    def _check(self, calendar):
        if self.read().revision != calendar.revision:
            raise CalendarError("revision_conflict")

    def _write(self, row, values):
        return {"updateCells": {
            "start": {"sheetId": self.settings.sheet_id, "rowIndex": row, "columnIndex": 0},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": value}} for value in values]}],
            "fields": "userEnteredValue",
        }}

    def insert(self, calendar, anchor, below, values):
        self._check(calendar)
        index = anchor + int(below)
        self.client.execute([
            {"insertDimension": {"range": {"sheetId": self.settings.sheet_id, "dimension": "ROWS",
                                           "startIndex": index, "endIndex": index + 1},
                                 "inheritFromBefore": index > 1}},
            self._write(index, values),
        ])
        return self.read()

    def update(self, calendar, index, values):
        self._check(calendar)
        self.client.execute([self._write(index, values)])
        return self.read()

    def delete(self, calendar, index):
        self._check(calendar)
        self.client.execute([{"deleteDimension": {"range": {
            "sheetId": self.settings.sheet_id, "dimension": "ROWS",
            "startIndex": index, "endIndex": index + 1,
        }}}])
        return self.read()

    def insertion(self, calendar, day):
        for i, row in enumerate(calendar.rows[1:], 1):
            if row.date > day:
                return i, False
        return len(calendar.rows) - 1, True
