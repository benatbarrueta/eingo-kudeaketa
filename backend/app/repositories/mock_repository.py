from copy import deepcopy
from datetime import date

from app.data.demo import SAMPLE
from app.models.calendar import Calendar, Row
from app.utils.basque_dates import format_date, parse


class MockRepository:
    def __init__(self, year):
        self.year = year
        self.reset()

    def reset(self):
        columns = ["DATA", "HERRIA", "EKITALDIA"]
        rows = [Row("header", columns, [])]
        month = 1
        for m, d, town, name in SAMPLE:
            if m != month:
                rows.append(Row("separator", [""], [], spans=[len(columns)]))
            day = date(self.year, m, d)
            rows.append(Row("event", [format_date(day), town, name], [], day))
            month = m
        self.calendar = Calendar(columns, rows)

    def read(self):
        return deepcopy(self.calendar)

    def insert(self, calendar, anchor, below, values):
        day = parse(values[calendar.columns.index("DATA")], self.year)
        self.calendar.rows.insert(anchor + int(below), Row("event", values, [], day))
        return self.read()

    def update(self, calendar, index, values):
        row = self.calendar.rows[index]
        row.values = values
        row.date = parse(values[calendar.columns.index("DATA")], self.year)
        return self.read()

    def delete(self, calendar, index):
        self.calendar.rows.pop(index)
        return self.read()
